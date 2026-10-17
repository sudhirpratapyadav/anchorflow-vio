#!/usr/bin/env python3
"""Run the frozen test cohort serially as atomic downloads become ready; never upload."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

import numpy as np
from create_manifest import create
from run_sequence import verify_files
from common import ROOT, digest
from package_submission import package, validate_poses


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    os.replace(temp, path)


def sequence_key(name):
    return tuple(map(int, name.split('_')[1:]))


def expected_timestamps(sequence):
    paths = list((sequence/'asl_folder').glob('**/cam0/data.csv'))
    if len(paths) != 1:
        raise ValueError('Expected exactly one original cam0 CSV')
    rows = [line.split(',') for line in paths[0].read_text().splitlines()
            if line.strip() and not line.startswith('#')]
    times = np.array([int(row[0]) for row in rows], dtype=np.int64)
    if not len(times) or np.any(np.diff(times) <= 0):
        raise ValueError('Invalid original image timestamps')
    if any(len(row) != 2 or not (paths[0].parent/'data'/Path(row[1]).name).is_file() for row in rows):
        raise ValueError('Missing original camera image')
    return times


def verify_readiness(sequence):
    receipt = json.loads((sequence/'.download_complete.json').read_text())
    if receipt['sequence'] != sequence.name:
        raise ValueError('Readiness receipt sequence mismatch')
    csv = Path(receipt['camera_csv'])
    if csv.is_absolute() or '..' in csv.parts:
        raise ValueError('Unsafe receipt camera path')
    if digest(sequence/csv) != receipt['camera_csv_sha256']:
        raise ValueError('Original camera CSV differs from readiness receipt')
    if digest(sequence/'extracted_files.jsonl') != receipt['file_ledger_sha256']:
        raise ValueError('Extraction ledger changed')
    for kind, sha in receipt['calibration_sha256'].items():
        if kind not in ('aria_calibrations','pinhole_calibrations'):
            raise ValueError('Unexpected calibration kind')
        if digest(sequence/kind/(sequence.name+'.json')) != sha:
            raise ValueError('Calibration differs from readiness receipt')
    if set(receipt['calibration_sha256']) != {'aria_calibrations','pinhole_calibrations'}:
        raise ValueError('Missing calibration receipt')
    if len(expected_timestamps(sequence)) != receipt['expected_image_count']:
        raise ValueError('Original image count differs from readiness receipt')
    return receipt


def audit(sequence, prepared, run):
    expected = expected_timestamps(sequence)
    actual = np.loadtxt(prepared/'image_timestamps_ns.txt', dtype=np.int64, ndmin=1)
    if not np.array_equal(expected, actual):
        raise ValueError('Prepared timestamps differ from independent full original CSV')
    text = (run/'estimate.txt').read_text()
    count = validate_poses(text, expected)
    if (prepared/'dataset/mav0/cam1').exists():
        raise ValueError('Unexpected second camera')
    manifest = json.loads((prepared/'manifest.json').read_text())
    verify_files(prepared, manifest['output_sha256'])
    result = json.loads((run/'result.json').read_text())
    if result['estimate_sha256'] != digest(run/'estimate.txt') or result['input_manifest_sha256'] != digest(prepared/'manifest.json'):
        raise ValueError('Completed run provenance changed')
    if manifest['max_frames'] or manifest['sensors'] != ['cam0','imu0']:
        raise ValueError('Cropped or incorrect sensor input')
    cameras, observations, obs_hash = set(), 0, hashlib.sha256()
    for file in sorted((run/'obs').glob('*.bin')):
        raw = file.read_bytes()
        if len(raw) % 16:
            raise ValueError('Malformed observations')
        obs_hash.update(file.name.encode() + b'\0' + hashlib.sha256(raw).digest())
        for _, camera, x, y in struct.iter_unpack('<iiff', raw):
            cameras.add(camera)
            observations += 1
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError('Nonfinite observations')
    if cameras != {0}:
        raise ValueError('Observation camera audit failed')
    poses = np.array([list(map(float, row.split()[1:])) for row in text.splitlines() if row.strip()])
    steps = np.linalg.norm(np.diff(poses[:,:3], axis=0), axis=1)
    speeds = steps / (np.diff(expected).astype(float) * 1e-9)
    return dict(poses=count, full_original_coverage=True, camera_ids=[0], observations=observations,
        observation_digest=obs_hash.hexdigest(), estimate_sha256=digest(run/'estimate.txt'),
        original_timestamps_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),
        max_step_m=float(steps.max(initial=0)), max_speed_m_s=float(speeds.max(initial=0)),
        steps_over_10m=int(np.sum(steps > 10)), accuracy_evaluated=False,
        diagnostic_note='Motion extremes are reported, never used for tuning or selecting configurations.')


def source_pins(runtime):
    paths = [ROOT/'scripts'/name for name in ('run_test_queue.py','prepare_input.py',
        'run_sequence.py','package_submission.py','create_manifest.py','tum_to_submission.py','common.py')]
    paths += list((ROOT/'configs').rglob('*.json'))
    paths += [ROOT/'docs/test_inventory.json', ROOT/'native/calibration_template.json', runtime/'manifest.json']
    pins = {str(p.resolve()):digest(p) for p in paths}
    manifest = json.loads((runtime/'manifest.json').read_text())
    for name, expected in manifest['sha256'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or digest(runtime/name) != expected:
            raise ValueError('Invalid runtime pin')
        pins[str((runtime/name).resolve())] = expected
    return pins


def verify_pins(pins):
    if any(digest(path) != sha for path, sha in pins.items()):
        raise ValueError('Frozen queue source/runtime changed; restart requires explicit review')


def run_command(command, log):
    with log.open('a') as stream:
        stream.write(json.dumps(command) + '\n')
        stream.flush()
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)


def make_packages(root, names, records):
    outputs = {}
    groups = {f'category_{c}':[n for n in names if sequence_key(n)[0] == c] for c in range(1,6)}
    groups['all_63'] = names
    for group, members in groups.items():
        if not members or any(records.get(n,{}).get('status') != 'complete' for n in members):
            continue
        folder = root/'packages'/group
        manifest_path = root/'packages'/(group + '.json')
        manifest = create([root/'runs'/n for n in members], 'test', 'anchorflow_mono_' + group)
        for record in manifest['records'].values():
            for key in ('estimate','timestamps','input_manifest'):
                record[key] = os.path.relpath(record[key], manifest_path.parent)
        if folder.exists():
            if json.loads(manifest_path.read_text()) != manifest:
                raise ValueError('Existing package input changed')
            report = json.loads((folder/'package_report.json').read_text())
            if digest(Path(report['archive'])) != report['archive_sha256']:
                raise ValueError('Existing package archive changed')
        else:
            atomic_json(manifest_path, manifest)
            report = package(manifest_path, folder)
        outputs[group] = report
    return outputs


def queue(args):
    root, runtime = args.root.resolve(), args.runtime.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in ('inputs','runs','packages','logs'):
        (root/name).mkdir(exist_ok=True)
    with (root/'queue.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        proof = json.loads(args.training_proof.read_text())
        if not proof.get('passed') or proof['runtime_sha256'] != json.loads((runtime/'manifest.json').read_text())['sha256']:
            raise ValueError('Full training reproduction proof missing or runtime differs')
        names = sorted([r['sequence'] for r in json.loads((ROOT/'docs/test_inventory.json').read_text())['records']], key=sequence_key)
        status_path = root/'queue_status.json'
        pins = source_pins(runtime)
        if status_path.exists():
            status = json.loads(status_path.read_text())
            if status['pins'] != pins:
                raise ValueError('Queue pins changed; explicit review required')
        else:
            status = dict(pins=pins, records={}, started=time.time(), command=sys.argv,
                          git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                          training_proof_sha256=digest(args.training_proof), accuracy_evaluated=False)
        for name, rec in status['records'].items():
            if rec['status'] == 'running':
                rec.update(status='failed', error='Interrupted previous attempt; no automatic retry')
            if rec['status'] == 'complete':
                if digest(root/'data/test'/name/'.download_complete.json') != rec['readiness_sha256']:
                    raise ValueError('Completed readiness receipt changed')
                verify_readiness(root/'data/test'/name)
                fresh = audit(root/'data/test'/name, root/'inputs'/name, root/'runs'/name)
                if fresh != rec['audit']:
                    raise ValueError('Completed record changed: ' + name)
        while True:
            verify_pins(pins)
            ready = [n for n in names if n not in status['records'] and (root/'data/test'/n/'.download_complete.json').exists()]
            status.update(pid=os.getpid(), updated=time.time(), status='running' if ready else 'waiting_for_download')
            atomic_json(status_path,status)
            for name in ready:
                sequence, prepared, run = root/'data/test'/name, root/'inputs'/name, root/'runs'/name
                rec = dict(status='running', started=time.time(), readiness_sha256=digest(sequence/'.download_complete.json'))
                status['records'][name] = rec
                status['active_sequence'] = name
                atomic_json(status_path,status)
                try:
                    verify_pins(pins)
                    receipt = verify_readiness(sequence)
                    if prepared.exists() or run.exists():
                        raise ValueError('Existing partial output; explicit review required, no silent retry')
                    run_command([sys.executable,str(ROOT/'scripts/prepare_input.py'),str(sequence),str(prepared)],root/'logs'/(name+'.log'))
                    run_command([sys.executable,str(ROOT/'scripts/run_sequence.py'),str(prepared),str(run),'--runtime',str(runtime)],root/'logs'/(name+'.log'))
                    verify_pins(pins)
                    rec['audit'] = audit(sequence,prepared,run)
                    if rec['audit']['poses'] != receipt['expected_image_count']:
                        raise ValueError('Download receipt image count differs from independent audit')
                    rec['coverage'] = json.loads((run/'coverage.json').read_text())
                    rec['native_timing'] = (run/'time.txt').read_text()
                    rec.update(status='complete', finished=time.time())
                    atomic_json(run/'queue_audit.json',rec)
                except Exception as error:
                    rec.update(status='failed', finished=time.time(), error=repr(error))
                status.pop('active_sequence',None)
                status['packages'] = make_packages(root,names,status['records'])
                atomic_json(status_path,status)
            download = root/'download_status.json'
            terminal = download.exists() and json.loads(download.read_text()).get('status') in ('complete','complete_with_errors')
            if len(status['records']) == len(names) or (terminal and not ready):
                status.update(status='complete' if all(status['records'].get(n,{}).get('status') == 'complete' for n in names) else 'complete_with_errors',
                              missing=[n for n in names if n not in status['records']],finished=time.time())
                status['packages'] = make_packages(root,names,status['records'])
                atomic_json(status_path,status)
                return
            if args.once:
                return
            time.sleep(args.poll_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--training-proof',type=Path,required=True)
    parser.add_argument('--poll-seconds',type=float,default=30)
    parser.add_argument('--once',action='store_true')
    queue(parser.parse_args())

#!/usr/bin/env python3
"""Run the frozen monocular estimator and write world_from_imu poses."""
import argparse
import json
import os
from pathlib import Path
import socket
import signal
import struct
import subprocess
import sys
import time

from common import ROOT, digest, read_policy, write_json
from package_submission import validate_poses
import numpy as np


def verify_files(root, pins):
    for name, expected in pins.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Release manifests require relative file paths')
        if digest(root/path) != expected:
            raise ValueError(f'File differs from manifest: {root/path}')


def run(src, out, runtime, policy_path):
    policy = read_policy(policy_path)
    manifest = json.loads((src/'manifest.json').read_text())
    if manifest['sensors'] != ['cam0','imu0'] or (src/'dataset/mav0/cam1').exists():
        raise ValueError('Expected a strictly monocular sensor view')
    if manifest['policy_sha256'] != digest(policy_path):
        raise ValueError('Input was prepared with a different policy')
    verify_files(src, manifest['output_sha256'])
    runtime_manifest = json.loads((runtime/'manifest.json').read_text())
    verify_files(runtime, runtime_manifest['sha256'])
    calibration = json.loads((src/'calib.json').read_text())['value0']
    if any(len(calibration[k]) != 1 for k in ('intrinsics','T_imu_cam','resolution')):
        raise ValueError('Native calibration must have exactly one camera')
    config = ROOT/policy['native_config']
    out.mkdir(parents=True, exist_ok=False)
    env = {k:v for k,v in os.environ.items() if not k.startswith('BASALT_')}
    env.update(policy['environment'])
    env.update(LD_PRELOAD=str(runtime/'libmono_reader.so'), LD_LIBRARY_PATH=str(runtime),
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', BASALT_OBS_DUMP=str(out/'obs'))
    command = [str(runtime/'basalt_vio'),'--dataset-path',str(src/'dataset'),
        '--dataset-type','euroc','--cam-calib',str(src/'calib.json'), '--config-path',str(config),
        '--save-trajectory','tum','--show-gui','false','--num-threads',str(policy['threads']),
        '--use-imu','true']
    pins = {str(p):digest(p) for p in (Path(__file__), policy_path, config)}
    info = dict(command=command, host=socket.gethostname(), started=time.time(), sha256=pins,
                input_manifest_sha256=digest(src/'manifest.json'),
                runtime_manifest_sha256=digest(runtime/'manifest.json'),
                environment={k:v for k,v in env.items() if k.startswith('BASALT_')},
                pose_frame='world_from_imu', input=str(src), policy=str(policy_path))
    write_json(out/'run_info.json', info)
    started = time.monotonic()
    try:
        with (out/'native.log').open('w') as log:
            process = subprocess.Popen(['/usr/bin/time','-v','-o',str(out/'time.txt')] + command,
                cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=policy['native_timeout_s'])
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise
        info['returncode'] = code
        if code:
            raise subprocess.CalledProcessError(code, command)
    except Exception as error:
        info['error'] = str(error)
        raise
    finally:
        info['native_wrapper_wall_s'] = time.monotonic() - started
        write_json(out/'run_info.json', info)
    for name, sha in pins.items():
        if digest(name) != sha:
            raise ValueError('Run source changed while processing')
    if 'MONO_READER: exactly one camera, cam0' not in (out/'native.log').read_text():
        raise ValueError('One-camera reader override was not active')
    with (out/'coverage.json').open('w') as stream:
        subprocess.run([sys.executable,str(ROOT/'scripts/tum_to_submission.py'),
            str(out/'trajectory.txt'),str(src/'image_timestamps_ns.txt'),str(out/'estimate.txt')],
            stdout=stream, check=True)
    validate_poses((out/'estimate.txt').read_text(),
                   np.loadtxt(src/'image_timestamps_ns.txt', dtype=np.int64, ndmin=1))
    cameras, observations = set(), 0
    files = sorted((out/'obs').glob('*.bin'))
    for file in files:
        raw = file.read_bytes()
        if len(raw) % 16:
            raise ValueError('Malformed native observation file')
        for _, camera, _, _ in struct.iter_unpack('<iiff', raw):
            cameras.add(camera)
            observations += 1
    if cameras != {0}:
        raise ValueError('Non-mono or empty observations')
    write_json(out/'sensor_audit.json', dict(camera_ids=sorted(cameras),
        observations=observations, frames=len(files), input_cameras=1, no_cam1_view=True))
    write_json(out/'result.json', dict(sequence=manifest['sequence'], input=str(src),
        estimate_sha256=digest(out/'estimate.txt'), pose_frame='world_from_imu',
        policy_sha256=digest(policy_path), native_config_sha256=digest(config),
        input_manifest_sha256=digest(src/'manifest.json'),
        runtime_manifest_sha256=digest(runtime/'manifest.json'),
        format_complete=True, accuracy_evaluated=False))
    print(f'Wrote {out / "estimate.txt"}; sensor/coverage checks passed, accuracy not evaluated.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--runtime', type=Path, default=ROOT/'build/native/runtime')
    parser.add_argument('--policy', type=Path, default=ROOT/'configs/mono.json')
    args = parser.parse_args()
    run(args.input.resolve(), args.out.resolve(), args.runtime.resolve(), args.policy.resolve())

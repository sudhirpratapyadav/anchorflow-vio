#!/usr/bin/env python3
"""Validate full image coverage and create a deterministic LaMAria ZIP; never uploads."""
import argparse
import json
from pathlib import Path
import re
import zipfile

import numpy as np

from common import ROOT, digest, write_json


def validate_poses(text, expected):
    rows = [line.split() for line in text.splitlines() if line.strip()]
    if not rows or any(len(row) != 8 or not re.fullmatch(r'[0-9]+', row[0]) for row in rows):
        raise ValueError('Expected eight columns and integer nanosecond timestamps')
    timestamps = np.array([int(r[0]) for r in rows], dtype=np.int64)
    if np.any(np.diff(timestamps) <= 0) or not np.array_equal(timestamps, expected):
        raise ValueError('Timestamp order or full-image coverage differs')
    poses = np.array([r[1:] for r in rows], dtype=float)
    if not np.isfinite(poses).all() or not np.allclose(np.linalg.norm(poses[:,3:], axis=1), 1., atol=1e-5, rtol=0):
        raise ValueError('Nonfinite pose or nonunit quaternion')
    return len(rows)


def package(manifest_path, output, official_parser=False):
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('pose_frame') != 'world_from_imu' or manifest.get('sensors') != ['cam0','imu0']:
        raise ValueError('Wrong pose frame or sensor contract')
    if manifest.get('dataset_scope') not in ('training','test') or not manifest.get('records'):
        raise ValueError('Declare dataset_scope training/test and nonempty records')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', manifest['name']):
        raise ValueError('Unsafe archive name')
    test_inventory = json.loads((ROOT/'docs/test_inventory.json').read_text())
    test_names = {r['sequence'] for r in test_inventory['records']}
    supplied = set(manifest['records'])
    if manifest['dataset_scope'] == 'test' and not supplied <= test_names:
        raise ValueError('Test manifest contains sequences outside the checked main-test inventory')
    if manifest['dataset_scope'] == 'training' and supplied & test_names:
        raise ValueError('Training manifest contains main-test sequence names')
    records, contents = {}, {}
    for sequence, record in manifest['records'].items():
        if not re.fullmatch(r'[A-Za-z0-9_]+', sequence):
            raise ValueError('Unsafe sequence name')
        paths = {k:(manifest_path.parent/record[k]).resolve() for k in ('estimate','timestamps','input_manifest')}
        for key, path in paths.items():
            if digest(path) != record['sha256'][key]:
                raise ValueError(f'Pinned {key} changed for {sequence}')
        prepared = json.loads(paths['input_manifest'].read_text())
        if prepared['sequence'] != sequence or prepared['sensors'] != ['cam0','imu0']:
            raise ValueError('Sequence or sensors do not match input manifest')
        if prepared.get('source_intentionally_skipped_images',0) or prepared.get('max_frames',0):
            raise ValueError('Cropped inputs cannot be submitted as full recordings')
        expected = np.loadtxt(paths['timestamps'], dtype=np.int64, ndmin=1)
        text = paths['estimate'].read_text()
        count = validate_poses(text, expected)
        if count != prepared['images']:
            raise ValueError('Input image count mismatch')
        if official_parser:
            from lamaria.structs.trajectory import Trajectory
            trajectory = Trajectory.load_from_file(paths['estimate'], invert_poses=False, corresponding_sensor='imu')
            if len(trajectory) != count:
                raise ValueError('Official parser count differs')
        member = f'slam/{sequence}.txt'
        contents[member] = text.encode()
        records[sequence] = dict(poses=count, member=member, sha256=digest(paths['estimate']))
    output.mkdir(parents=True, exist_ok=False)
    archive = output/(manifest['name'] + '.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as stream:
        for member, content in sorted(contents.items()):
            info = zipfile.ZipInfo(member, date_time=(2026,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            stream.writestr(info, content)
    with zipfile.ZipFile(archive) as stream:
        if stream.testzip() or set(stream.namelist()) != set(contents):
            raise ValueError('Archive integrity failed')
        if any(stream.read(k) != v for k, v in contents.items()):
            raise ValueError('Archive contents differ')
    report = dict(archive=str(archive), archive_sha256=digest(archive),
        manifest_sha256=digest(manifest_path), dataset_scope=manifest['dataset_scope'],
        format_ok=True, official_parser_checked=official_parser, records=records,
        note='Format checks do not certify accuracy or test-set completeness. No upload performed.')
    if manifest['dataset_scope'] == 'test':
        report['challenge_coverage'] = {}
        for category in range(1,6):
            expected = {s for s in test_names if s.startswith(f'sequence_{category}_')}
            present = supplied & expected
            report['challenge_coverage'][str(category)] = dict(provided=len(present),
                required=len(expected), complete=present == expected, missing=sorted(expected-present))
    write_json(output/'package_report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--official-parser', action='store_true', help='Also check with installed official LaMAria parser')
    args = parser.parse_args()
    print(json.dumps(package(args.manifest.resolve(), args.out.resolve(), args.official_parser), indent=2))

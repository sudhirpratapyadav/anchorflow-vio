#!/usr/bin/env python3
"""Prepare a cam0/imu0-only ASL view, without loading ground truth."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from common import ROOT, digest, read_policy, write_json


def exactly_one(paths, description):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError(f'Expected exactly one {description}, found {len(paths)}')
    return paths[0]


def calibration(pinhole, template, policy):
    source = json.loads(pinhole.read_text())
    reference = json.loads(template.read_text())['value0']
    cam = source['cam0']
    if cam['model'] != 'PINHOLE':
        raise ValueError('Use the ASL pinhole calibration for the undistorted ASL images')
    q, t = cam['T_b_s']['qvec'], cam['T_b_s']['tvec']
    imu = source['imu0']
    identity = dict(px=0., py=0., pz=0., qx=0., qy=0., qz=0., qw=1.)
    return {'value0': {
        'T_imu_cam': [dict(zip(('px','py','pz','qx','qy','qz','qw'), t + q))],
        'intrinsics': [{'camera_type': 'pinhole', 'intrinsics': dict(zip(('fx','fy','cx','cy'), cam['params'][:4]))}],
        'resolution': [[cam['resolution']['width'], cam['resolution']['height']]],
        'vignette': reference['vignette'][:1],
        'calib_accel_bias': [0.] * len(reference['calib_accel_bias']),
        'calib_gyro_bias': [0.] * len(reference['calib_gyro_bias']),
        'imu_update_rate': float(imu['imu_rate']),
        'accel_noise_std': [imu['acc_noise_density'] * policy['noise_scale']] * 3,
        'gyro_noise_std': [imu['gyro_noise_density'] * policy['gyro_noise_scale']] * 3,
        'accel_bias_std': [imu['acc_bias_random_walk_sigma'] * policy['walk_scale']] * 3,
        'gyro_bias_std': [imu['gyro_bias_random_walk_sigma'] * policy['gyro_walk_scale']] * 3,
        'T_mocap_world': identity, 'T_imu_marker': identity,
        'mocap_time_offset_ns': 0, 'mocap_to_imu_offset_ns': 0, 'cam_time_offset_ns': 0,
    }}


def inventory(sequence, factory_dir):
    imu = exactly_one((sequence/'asl_folder').glob('**/imu0/data.csv'), 'ASL imu0 CSV')
    aria = exactly_one(sequence.glob('aria_calibrations/*.json'), 'Aria calibration')
    pinhole = exactly_one(sequence.glob('pinhole_calibrations/*.json'), 'pinhole calibration')
    # Historical device key used by the frozen training configuration.
    device = hashlib.md5(aria.read_bytes()).hexdigest()[:8]
    factory = factory_dir/(device + '.json')
    if not factory.is_file():
        raise ValueError(f'Missing factory IMU calibration for {device}: {factory}. '
                         'Provide verified coefficients; no identity fallback is allowed.')
    return imu, aria, pinhole, factory


def audit_imu_span(ns, timestamps):
    # Sensor streams need not end on exactly the same sample. Preserve the
    # historical data; reject gross truncation, but report sub-frame tail gaps.
    period = int(np.median(np.diff(timestamps))) if len(timestamps) > 1 else 0
    start_gap = max(0, int(ns[0]) - timestamps[0])
    end_gap = max(0, timestamps[-1] - int(ns[-1]))
    if start_gap > period or end_gap > period:
        raise ValueError('IMU endpoint gap exceeds one observed image period')
    return dict(image_period_ns=period, imu_start_gap_ns=start_gap, imu_end_gap_ns=end_gap,
                note='No samples added or removed to repair endpoint gaps.')


def prepare(sequence, out, policy_path, factory_dir, template, max_frames=0):
    policy = read_policy(policy_path)
    if max_frames < 0:
        raise ValueError('max-frames must be nonnegative')
    imu, aria, pinhole, factory = inventory(sequence, factory_dir)
    camera = imu.parent.parent/'cam0'
    rows = [r.split(',') for r in (camera/'data.csv').read_text().splitlines()
            if r.strip() and not r.startswith('#')]
    if max_frames:
        rows = rows[:max_frames]
    timestamps = [int(r[0]) for r in rows]
    if not timestamps or any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError('Image timestamps must be nonempty and increasing')
    for row in rows:
        if len(row) != 2 or not (camera/'data'/Path(row[1]).name).is_file():
            raise ValueError('Missing image or malformed camera CSV')
    fac = json.loads(factory.read_text())
    data = np.loadtxt(imu, delimiter=',', comments='#', ndmin=2)
    if data.shape[1] != 7 or not np.isfinite(data).all():
        raise ValueError('IMU rows must contain seven finite columns')
    ns = data[:,0].astype(np.int64) - policy['subtract_imu_timestamp_ns']
    if np.any(np.diff(ns) <= 0):
        raise ValueError('IMU timestamps must increase')
    for name, cols in [('gyro', slice(1,4)), ('accel', slice(4,7))]:
        matrix, bias = np.asarray(fac[name]['M']), np.asarray(fac[name]['bias'])
        if matrix.shape != (3,3) or bias.shape != (3,) or not np.isfinite(matrix).all() or not np.isfinite(bias).all():
            raise ValueError('Invalid factory IMU coefficients')
        data[:,cols] = np.linalg.solve(matrix, (data[:,cols] - bias).T).T
    if max_frames:
        keep = ns <= timestamps[-1] + 1000000000
        data, ns = data[keep], ns[keep]
    endpoint_audit = audit_imu_span(ns, timestamps)
    cal = calibration(pinhole, template, policy)
    out.mkdir(parents=True, exist_ok=False)
    view = out/'dataset/mav0'
    (view/'cam0').mkdir(parents=True)
    (view/'imu0').mkdir()
    (view/'cam0/data').symlink_to((camera/'data').resolve(), target_is_directory=True)
    (view/'cam0/data.csv').write_text('#timestamp [ns],filename\n' + ''.join(
        f'{t},{Path(r[1]).name}\n' for t, r in zip(timestamps, rows)))
    (out/'image_timestamps_ns.txt').write_text(''.join(f'{t}\n' for t in timestamps))
    with (view/'imu0/data.csv').open('w') as stream:
        stream.write('#timestamp [ns],wx,wy,wz,ax,ay,az\n')
        for t, row in zip(ns, data):
            stream.write(f'{t},' + ','.join(f'{v:.10g}' for v in row[1:7]) + '\n')
    write_json(out/'calib.json', cal)
    sources = [imu, camera/'data.csv', factory, pinhole, aria, policy_path, template, Path(__file__)]
    outputs = ['dataset/mav0/imu0/data.csv','dataset/mav0/cam0/data.csv','calib.json','image_timestamps_ns.txt']
    write_json(out/'manifest.json', dict(sequence=sequence.name, images=len(rows), imu_rows=len(ns),
        max_frames=max_frames, source_intentionally_skipped_images=0, sensors=['cam0','imu0'],
        policy_sha256=digest(policy_path),
        endpoint_audit=endpoint_audit,
        source_sha256={str(p.resolve()):digest(p) for p in sources},
        output_sha256={p:digest(out/p) for p in outputs}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sequence', type=Path)
    parser.add_argument('out', type=Path, nargs='?')
    parser.add_argument('--policy', type=Path, default=ROOT/'configs/mono.json')
    parser.add_argument('--factory-dir', type=Path, default=ROOT/'configs/factory_imu')
    parser.add_argument('--template', type=Path, default=ROOT/'native/calibration_template.json')
    parser.add_argument('--max-frames', type=int, default=0, help='Smoke only; cropped outputs cannot be submitted')
    parser.add_argument('--check', action='store_true', help='Check sensor/calibration availability without writing')
    args = parser.parse_args()
    if args.check:
        paths = inventory(args.sequence.resolve(), args.factory_dir.resolve())
        print(json.dumps(dict(sequence=args.sequence.name, calibration_ready=True,
                              factory_sha256=digest(paths[-1]))))
    elif args.out is None:
        parser.error('out is required without --check')
    else:
        prepare(args.sequence.resolve(), args.out.resolve(), args.policy.resolve(),
                args.factory_dir.resolve(), args.template.resolve(), args.max_frames)


if __name__ == '__main__':
    main()

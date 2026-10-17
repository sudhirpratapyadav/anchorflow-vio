#!/usr/bin/env python3
"""Collect completed release runs into a pinned, single-policy submission manifest."""
import argparse
import json
from pathlib import Path

from common import digest, write_json


def create(runs, scope, name):
    records, policies, configs, runtimes = {}, set(), set(), set()
    for run in runs:
        result = json.loads((run/'result.json').read_text())
        source = Path(result['input'])
        if digest(source/'manifest.json') != result['input_manifest_sha256']:
            raise ValueError('Input manifest changed after run')
        manifest = json.loads((source/'manifest.json').read_text())
        sequence = manifest['sequence']
        if sequence in records:
            raise ValueError('Duplicate sequence: ' + sequence)
        if manifest.get('max_frames',0) or manifest.get('source_intentionally_skipped_images',0):
            raise ValueError('Only full-record runs may be submitted')
        if result['pose_frame'] != 'world_from_imu' or not result['format_complete']:
            raise ValueError('Run incomplete or wrong pose frame')
        estimate = run/'estimate.txt'
        if digest(estimate) != result['estimate_sha256']:
            raise ValueError('Estimate changed after run')
        policies.add(result['policy_sha256'])
        configs.add(result['native_config_sha256'])
        runtimes.add(result['runtime_manifest_sha256'])
        paths = dict(estimate=estimate, timestamps=source/'image_timestamps_ns.txt', input_manifest=source/'manifest.json')
        records[sequence] = {**{k:str(v.resolve()) for k,v in paths.items()},
                             'sha256':{k:digest(v) for k,v in paths.items()}}
    if len(policies) != 1 or len(configs) != 1 or len(runtimes) != 1:
        raise ValueError('Require nonempty runs with one policy and runtime')
    return dict(name=name, dataset_scope=scope, pose_frame='world_from_imu', sensors=['cam0','imu0'],
                policy_sha256=policies.pop(), native_config_sha256=configs.pop(),
                runtime_manifest_sha256=runtimes.pop(), records=records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--scope', choices=['training','test'], required=True)
    parser.add_argument('--name', default='anchorflow-vio')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output already exists; use a fresh manifest')
    write_json(args.out, create([r.resolve() for r in args.runs], args.scope, args.name))

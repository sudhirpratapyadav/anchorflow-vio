"""Portable paths and file fingerprints for the release tools."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def read_policy(path):
    policy = json.loads(Path(path).read_text())
    if policy['camera'] != 'cam0' or policy['imu'] != 'imu0':
        raise ValueError('This release supports only cam0 + imu0')
    if not policy['factory_rectification']:
        raise ValueError('The frozen policy requires factory IMU rectification')
    return policy

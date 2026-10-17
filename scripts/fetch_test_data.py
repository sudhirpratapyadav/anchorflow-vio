#!/usr/bin/env python3
"""Resume all pinned test ASL downloads and publish verified sequence directories."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import socket
import stat
import subprocess
import time
import urllib.request
import zipfile

from common import ROOT, digest

BASE = 'https://cvg-data.inf.ethz.ch/lamaria'
RESERVE = 20 * 1024**3


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def remote_info(url):
    request = urllib.request.Request(url, method='HEAD')
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 200 or not response.headers.get('Content-Length'):
            raise ValueError('Remote object has no reliable size: ' + url)
        return dict(url=url, bytes=int(response.headers['Content-Length']),
                    etag=response.headers.get('ETag'), last_modified=response.headers.get('Last-Modified'))


def safe_members(archive):
    seen = set()
    for member in archive.infolist():
        path = PurePosixPath(member.filename)
        mode = member.external_attr >> 16
        if path.is_absolute() or '..' in path.parts or '\\' in member.filename or stat.S_ISLNK(mode):
            raise ValueError('Unsafe ZIP member: ' + member.filename)
        if not path.parts or member.filename in seen:
            raise ValueError('Empty or duplicate ZIP member')
        if member.flag_bits & 1:
            raise ValueError('Encrypted ZIP member')
        seen.add(member.filename)
        yield member


def enough_space(directory, required):
    free = shutil.disk_usage(directory).free
    if free < required + RESERVE:
        raise OSError(f'Insufficient disk space: {free} bytes free, {required} plus {RESERVE} reserve needed')


def fetch(url, target, status, save):
    metadata = remote_info(url)
    meta_path = target.with_suffix(target.suffix + '.remote.json')
    if meta_path.exists():
        previous = json.loads(meta_path.read_text())
        if previous != metadata:
            raise ValueError('Remote identity changed; preserve partial for inspection: ' + str(target))
    atomic_json(meta_path, metadata)
    existing = target.stat().st_size if target.exists() else 0
    if existing > metadata['bytes']:
        raise ValueError('Local file larger than pinned remote object')
    enough_space(target.parent, metadata['bytes'] - existing)
    status.update(url=url, target=str(target), total_bytes=metadata['bytes'], downloaded_bytes=existing)
    save()
    if existing < metadata['bytes']:
        command = ['curl','--fail','--location','--silent','--show-error','--continue-at','-',
            '--retry','8','--retry-all-errors','--retry-delay','10','--connect-timeout','30',
            '--speed-limit','1024','--speed-time','120','--output',str(target),url]
        with target.with_suffix(target.suffix+'.download.log').open('a') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            status['transfer_pid'] = process.pid
            save()
            try:
                while process.poll() is None:
                    status['downloaded_bytes'] = target.stat().st_size if target.exists() else 0
                    save()
                    time.sleep(5)
                if process.returncode:
                    raise subprocess.CalledProcessError(process.returncode, command)
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                raise
            finally:
                status.pop('transfer_pid',None)
    if target.stat().st_size != metadata['bytes']:
        raise ValueError('Downloaded byte count differs from remote length')
    status['downloaded_bytes'] = metadata['bytes']
    save()
    return metadata


def extract(archive_path, staging, status, save):
    if staging.exists():
        # Only remove the incomplete staging directory owned by this downloader.
        shutil.rmtree(staging)
    staging.mkdir()
    output = staging/'asl_folder'
    output.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        members = list(safe_members(archive))
        unpacked = sum(m.file_size for m in members)
        enough_space(staging, unpacked)
        status.update(stage='extracting', archive_uncompressed_bytes=unpacked, extracted_bytes=0,
                      archive_members=len(members), extracted_members=0)
        save()
        last_update = time.monotonic()
        with (staging/'extracted_files.jsonl').open('w') as ledger:
            for index, member in enumerate(members):
                target = output.joinpath(*PurePosixPath(member.filename).parts)
                if member.is_dir():
                    target.mkdir(parents=True,exist_ok=True)
                    continue
                target.parent.mkdir(parents=True,exist_ok=True)
                checksum, written = hashlib.sha256(), 0
                with archive.open(member) as src, target.open('xb') as dst:
                    for block in iter(lambda:src.read(1024*1024), b''):
                        dst.write(block)
                        checksum.update(block)
                        written += len(block)
                # ZipExtFile validates each member's CRC at EOF.
                if written != member.file_size:
                    raise ValueError('Extracted size differs: ' + member.filename)
                ledger.write(json.dumps(dict(path='asl_folder/'+member.filename, bytes=written,
                                              crc32=member.CRC, sha256=checksum.hexdigest()))+'\n')
                status['extracted_bytes'] += written
                status['extracted_members'] = index + 1
                if time.monotonic()-last_update > 5:
                    save()
                    last_update = time.monotonic()
    save()
    return unpacked


def verify_layout(sequence, staging):
    sources = list((staging/'asl_folder').glob('**/cam0/data.csv'))
    if len(sources) != 1:
        raise ValueError('Expected exactly one camera0 CSV')
    camera = sources[0].parent
    timestamps = []
    for line in sources[0].read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        columns = line.split(',')
        if len(columns) != 2 or not (camera/'data'/Path(columns[1]).name).is_file():
            raise ValueError('Incomplete camera0 image set')
        timestamps.append(int(columns[0]))
    if not timestamps or any(b<=a for a,b in zip(timestamps,timestamps[1:])):
        raise ValueError('Invalid camera0 timestamps')
    if not (camera.parent/'imu0/data.csv').is_file():
        raise ValueError('Missing imu0 CSV')
    return dict(sequence=sequence, expected_image_count=len(timestamps),
        first_image_timestamp_ns=timestamps[0], last_image_timestamp_ns=timestamps[-1],
        camera_csv=str(sources[0].relative_to(staging)), camera_csv_sha256=digest(sources[0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path,help='Owned external-drive data/log root')
    parser.add_argument('--inventory',type=Path,default=ROOT/'docs/test_inventory.json')
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True,exist_ok=True)
    lock = (root/'download.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    archives, data, partials = root/'archives', root/'data/test', root/'staging'
    for directory in (archives,data,partials):
        directory.mkdir(parents=True,exist_ok=True)
    inventory = json.loads(args.inventory.read_text())
    sequences = sorted([r['sequence'] for r in inventory['records']],key=lambda s:tuple(map(int,s.split('_')[1:])))
    path = root/'download_status.json'
    state = json.loads(path.read_text()) if path.exists() else {'records':{}}
    state.update(status='running', pid=os.getpid(), host=socket.gethostname(), started_at=time.time(),
        inventory_sha256=digest(args.inventory), downloader_sha256=digest(Path(__file__)),
        total_records=len(sequences), active_record=None)
    def save():
        state['updated_at'] = time.time()
        atomic_json(path,state)
    save()
    for sequence in sequences:
        destination = data/sequence
        receipt = destination/'.download_complete.json'
        if receipt.exists():
            info = json.loads(receipt.read_text())
            if info['sequence'] != sequence or digest(destination/'extracted_files.jsonl') != info['file_ledger_sha256']:
                raise ValueError('Existing ready directory identity differs')
            state['records'][sequence] = dict(status='complete', receipt=str(receipt),
                receipt_sha256=digest(receipt), expected_image_count=info['expected_image_count'])
            save()
            continue
        if destination.exists():
            raise ValueError('Destination exists without readiness receipt; inspect manually: '+str(destination))
        state['active_record'] = sequence
        record = state['records'][sequence] = dict(status='running',stage='calibrations',started_at=time.time())
        save()
        try:
            calibration_cache = archives/(sequence+'-calibrations')
            calibration_cache.mkdir(exist_ok=True)
            calibration_meta = {}
            for kind in ('aria_calibrations','pinhole_calibrations'):
                url = f'{BASE}/{kind}/test/{sequence}.json'
                target = calibration_cache/(kind+'.json')
                calibration_meta[kind] = fetch(url,target,record,save)
                payload = json.loads(target.read_text())
                if 'cam0' not in payload or 'imu0' not in payload:
                    raise ValueError('Incomplete camera/IMU calibration JSON')
            record['stage'] = 'downloading'
            archive = archives/(sequence+'.zip.part')
            identity = fetch(f'{BASE}/asl_folder/test/{sequence}.zip', archive, record, save)
            record['stage'] = 'hashing_archive'
            save()
            archive_hash = digest(archive)
            staging = partials/sequence
            unpacked = extract(archive,staging,record,save)
            for kind in calibration_meta:
                (staging/kind).mkdir()
                shutil.copy2(calibration_cache/(kind+'.json'),staging/kind/(sequence+'.json'))
            info = verify_layout(sequence,staging)
            info.update(schema_version=1, archive=identity, archive_sha256=archive_hash,
                uncompressed_bytes=unpacked, file_ledger_sha256=digest(staging/'extracted_files.jsonl'),
                calibration_sha256={kind:digest(staging/kind/(sequence+'.json')) for kind in calibration_meta},
                completed_at=time.time(), verification='All ZIP members read to EOF/CRC checked; SHA256 file ledger; image CSV coverage checked.')
            atomic_json(staging/'.download_complete.json',info)
            staging.rename(destination)
            # Keep metadata/logs/hash receipts; delete only this verified owned archive.
            archive.unlink()
            record.update(status='complete',stage='ready',receipt=str(receipt),receipt_sha256=digest(receipt),
                          expected_image_count=info['expected_image_count'],completed_at=time.time())
        except Exception as error:
            record.update(status='failed',error=f'{type(error).__name__}: {error}',completed_at=time.time())
            save()
            if isinstance(error,OSError) and ('disk space' in str(error) or error.errno == 28):
                state['status']='waiting_for_disk_space'
                save()
                raise
        save()
    state.update(status='complete' if all(r['status']=='complete' for r in state['records'].values()) else 'complete_with_errors',
                 active_record=None,completed_at=time.time())
    save()


if __name__ == '__main__':
    main()

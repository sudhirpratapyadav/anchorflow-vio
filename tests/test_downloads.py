import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fetch_test_data import safe_members, extract, verify_layout, fetch


class DownloadTests(unittest.TestCase):
    def test_retry_preserves_partial_and_rechecks_remote(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'archive.part'
            metadata = dict(url='https://example.invalid/data', bytes=6, etag='same')
            offsets = []
            class Process:
                pid = 123
                def __init__(self, command, **kwargs):
                    self.returncode = 56 if not offsets else 0
                    offsets.append(target.stat().st_size if target.exists() else 0)
                    self_command = command
                    assert self_command[self_command.index('--retry')+1] == '0'
                    with target.open('ab') as stream:
                        stream.write(b'abc' if self.returncode else b'def')
                def poll(self):
                    return self.returncode
            with patch('fetch_test_data.remote_info', return_value=metadata) as remote, \
                 patch('fetch_test_data.enough_space'), \
                 patch('fetch_test_data.subprocess.Popen', Process), \
                 patch('fetch_test_data.time.sleep'):
                self.assertEqual(fetch(metadata['url'], target, {}, lambda:None), metadata)
            self.assertEqual(offsets, [0, 3])
            self.assertEqual(remote.call_count, 2)
            self.assertEqual(target.read_bytes(), b'abcdef')

    def test_segmented_full_size_file_requires_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'archive.zip.part'
            target.write_bytes(b'abcdef')
            control = Path(str(target)+'.aria2')
            control.write_bytes(b'unfinished pieces')
            metadata = dict(url='https://example.invalid/data.zip', bytes=6, etag='same')
            commands = []
            class Process:
                pid = 123
                returncode = 0
                def __init__(self, command, **kwargs):
                    commands.append(command)
                    control.unlink()
                def poll(self):
                    return 0
            with patch('fetch_test_data.remote_info', return_value=metadata), \
                 patch('fetch_test_data.enough_space'), \
                 patch('fetch_test_data.subprocess.Popen', Process):
                fetch(metadata['url'], target, {}, lambda:None)
            self.assertEqual(commands[0][0], 'aria2c')
            self.assertIn('--max-connection-per-server=4', commands[0])

    def test_traversal_and_symlink_rejected(self):
        for name, mode in [('../escape',0),('/absolute',0),('link',stat.S_IFLNK|0o777)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/'input.zip'
                with zipfile.ZipFile(path,'w') as stream:
                    entry=zipfile.ZipInfo(name)
                    entry.external_attr=mode<<16
                    stream.writestr(entry,'payload')
                with zipfile.ZipFile(path) as archive, self.assertRaisesRegex(ValueError,'Unsafe'):
                    list(safe_members(archive))

    def test_extract_crc_ledger_and_camera_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); archive=root/'input.zip'; staging=root/'staging'
            files={'sequence_1_1/aria/cam0/data.csv':'#timestamp,filename\n100,100.png\n150,150.png\n',
                'sequence_1_1/aria/cam0/data/100.png':'first',
                'sequence_1_1/aria/cam0/data/150.png':'second',
                'sequence_1_1/aria/imu0/data.csv':'#imu\n'}
            with zipfile.ZipFile(archive,'w') as stream:
                for name,content in files.items():stream.writestr(name,content)
            with patch('fetch_test_data.enough_space'):
                extract(archive,staging,{},lambda:None)
            rows=[json.loads(x) for x in (staging/'extracted_files.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),4)
            self.assertEqual(verify_layout('sequence_1_1',staging)['expected_image_count'],2)
            (staging/'asl_folder/sequence_1_1/aria/cam0/data/150.png').unlink()
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                verify_layout('sequence_1_1',staging)


if __name__=='__main__':unittest.main()

import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fetch_test_data import safe_members, extract, verify_layout


class DownloadTests(unittest.TestCase):
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

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from common import digest
from package_submission import package, validate_poses
from create_manifest import create


class SubmissionTests(unittest.TestCase):
    valid = '1000000000 0 0 0 0 0 0 1\n1050000000 1 0 0 0 0 0 1\n'
    timestamps = np.array([1000000000,1050000000], dtype=np.int64)

    def test_missing_duplicate_and_reversed_timestamps(self):
        for text in [self.valid.splitlines()[0], self.valid.replace('1050000000','1000000000'),
                     '\n'.join(reversed(self.valid.splitlines()))]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_poses(text, self.timestamps)

    def test_invalid_numbers_and_columns(self):
        for text in [self.valid.replace('1000000000','1.0'), self.valid.replace('1 0 0','nan 0 0'),
                     self.valid.replace('0 0 0 1\n','0 0 0 2\n'), self.valid.replace('1\n','1 2\n')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_poses(text, self.timestamps)

    def fixture(self, directory):
        paths = {k:directory/v for k,v in dict(estimate='estimate.txt',timestamps='timestamps.txt',input_manifest='input.json').items()}
        paths['estimate'].write_text(self.valid)
        paths['timestamps'].write_text('1000000000\n1050000000\n')
        paths['input_manifest'].write_text(json.dumps(dict(sequence='sequence_1_19', sensors=['cam0','imu0'], images=2, max_frames=0)))
        manifest = dict(name='anchorflow-training',dataset_scope='training',pose_frame='world_from_imu',sensors=['cam0','imu0'],records={
            'sequence_1_19':{**{k:v.name for k,v in paths.items()},'sha256':{k:digest(v) for k,v in paths.items()}}})
        target = directory/'manifest.json'
        target.write_text(json.dumps(manifest))
        return target, paths, manifest

    def test_deterministic_package_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, paths, _ = self.fixture(root)
            first = package(target, root/'first')
            second = package(target, root/'second')
            self.assertEqual(first['archive_sha256'],second['archive_sha256'])
            self.assertTrue(first['format_ok'])
            paths['estimate'].write_text(self.valid.replace('1 0 0','2 0 0'))
            with self.assertRaisesRegex(ValueError,'Pinned estimate'):
                package(target,root/'tampered')

    def test_cropped_and_unsafe_names_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, paths, manifest = self.fixture(root)
            prepared = json.loads(paths['input_manifest'].read_text())
            prepared['max_frames'] = 2
            paths['input_manifest'].write_text(json.dumps(prepared))
            manifest['records']['sequence_1_19']['sha256']['input_manifest'] = digest(paths['input_manifest'])
            target.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Cropped'):
                package(target,root/'cropped')
            manifest['records']['../escape'] = manifest['records'].pop('sequence_1_19')
            target.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Unsafe sequence'):
                package(target,root/'unsafe')

    def test_training_cannot_be_labeled_as_main_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, _, manifest = self.fixture(root)
            manifest['dataset_scope'] = 'test'
            target.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'main-test inventory'):
                package(target,root/'wrong-split')

    def test_manifest_rejects_mixed_native_configs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runs = []
            for index in (19,20):
                run = root/str(index)
                run.mkdir()
                _, paths, _ = self.fixture(run)
                prepared = json.loads(paths['input_manifest'].read_text())
                prepared['sequence'] = f'sequence_1_{index}'
                paths['input_manifest'].write_text(json.dumps(prepared))
                # A completed release run references its prepared input directory.
                (run/'manifest.json').write_text(paths['input_manifest'].read_text())
                result = dict(input=str(run), pose_frame='world_from_imu', format_complete=True,
                    input_manifest_sha256=digest(run/'manifest.json'),
                    estimate_sha256=digest(paths['estimate']), policy_sha256='same',
                    native_config_sha256=str(index), runtime_manifest_sha256='same')
                (run/'result.json').write_text(json.dumps(result))
                (run/'image_timestamps_ns.txt').write_text(paths['timestamps'].read_text())
                runs.append(run)
            with self.assertRaisesRegex(ValueError,'one policy and runtime'):
                create(runs,'training','test')


if __name__ == '__main__':
    unittest.main()

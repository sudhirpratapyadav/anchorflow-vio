import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from common import ROOT, read_policy
from prepare_input import calibration, inventory, audit_imu_span
from run_sequence import verify_files


class InputTests(unittest.TestCase):
    def test_subframe_imu_tail_preserved_but_truncation_rejected(self):
        timestamps = [1000000000,1050000000,1100000000]
        result = audit_imu_span([990000000,1095195638],timestamps)
        self.assertEqual(result['imu_end_gap_ns'],4804362)
        with self.assertRaisesRegex(ValueError,'exceeds one'):
            audit_imu_span([990000000,1040000000],timestamps)

    def test_camera1_not_used_to_build_calibration(self):
        policy = read_policy(ROOT/'configs/mono.json')
        source = {'cam0': {'model':'PINHOLE','params':[200.,201.,100.,101.],
            'T_b_s': {'qvec':[0.,0.,0.,1.], 'tvec':[1.,2.,3.]},
            'resolution': {'width':640,'height':480}},
            'imu0': {'imu_rate':1000.,'acc_noise_density':0.1,'gyro_noise_density':0.01,
                'acc_bias_random_walk_sigma':0.001,'gyro_bias_random_walk_sigma':0.0001}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'pinhole.json'
            path.write_text(json.dumps(source))
            result = calibration(path, ROOT/'native/calibration_template.json', policy)['value0']
        for key in ('intrinsics','T_imu_cam','resolution','vignette'):
            self.assertEqual(len(result[key]),1)
        self.assertEqual(result['T_imu_cam'][0]['px'],1.)
        self.assertEqual(result['intrinsics'][0]['intrinsics']['fx'],200.)

    def test_unknown_factory_calibration_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ('asl_folder/aria/imu0','aria_calibrations','pinhole_calibrations','factory'):
                (root/directory).mkdir(parents=True)
            (root/'asl_folder/aria/imu0/data.csv').write_text('')
            (root/'aria_calibrations/cal.json').write_text('{}')
            (root/'pinhole_calibrations/cal.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Missing factory IMU calibration'):
                inventory(root, root/'factory')

    def test_runtime_manifest_does_not_follow_external_paths(self):
        for path in ('/tmp/external','../external'):
            with self.assertRaisesRegex(ValueError,'relative'):
                verify_files(ROOT,{path:'0'*64})


if __name__ == '__main__':
    unittest.main()

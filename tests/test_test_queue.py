import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_test_queue import audit, expected_timestamps, sequence_key, verify_pins, verify_readiness
from common import digest


class TestQueueAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sequence = self.root/'sequence_1_1'
        self.camera = self.sequence/'asl_folder/mav0/cam0'
        (self.camera/'data').mkdir(parents=True)
        (self.camera/'data.csv').write_text('#time,file\n1000000000,a.png\n1050000000,b.png\n')
        for name in ('a.png','b.png'):
            (self.camera/'data'/name).write_bytes(b'image')
        self.prepared = self.root/'input'
        self.prepared.mkdir()
        (self.prepared/'manifest.json').write_text(json.dumps(dict(max_frames=0,sensors=['cam0','imu0'],output_sha256={})))
        (self.prepared/'image_timestamps_ns.txt').write_text('1000000000\n1050000000\n')
        self.run = self.root/'run'
        (self.run/'obs').mkdir(parents=True)
        (self.run/'obs/1000000000.bin').write_bytes(struct.pack('<iiff',1,0,2.,3.))
        (self.run/'estimate.txt').write_text('1000000000 0 0 0 0 0 0 1\n1050000000 20 0 0 0 0 0 1\n')
        (self.run/'result.json').write_text(json.dumps(dict(estimate_sha256=digest(self.run/'estimate.txt'),
            input_manifest_sha256=digest(self.prepared/'manifest.json'))))

    def test_complete_and_motion_warning_is_not_selection(self):
        result = audit(self.sequence,self.prepared,self.run)
        self.assertEqual(result['poses'],2)
        self.assertEqual(result['steps_over_10m'],1)
        self.assertFalse(result['accuracy_evaluated'])

    def test_independent_original_detects_truncated_input(self):
        (self.prepared/'image_timestamps_ns.txt').write_text('1000000000\n')
        with self.assertRaisesRegex(ValueError,'independent full'):
            audit(self.sequence,self.prepared,self.run)

    def test_nonmono_observations_fail(self):
        (self.run/'obs/1000000000.bin').write_bytes(struct.pack('<iiff',1,1,2.,3.))
        with self.assertRaisesRegex(ValueError,'camera audit'):
            audit(self.sequence,self.prepared,self.run)

    def test_nonfinite_observations_fail(self):
        (self.run/'obs/1000000000.bin').write_bytes(struct.pack('<iiff',1,0,float('nan'),3.))
        with self.assertRaisesRegex(ValueError,'Nonfinite'):
            audit(self.sequence,self.prepared,self.run)

    def test_missing_original_image_fails(self):
        (self.camera/'data/b.png').unlink()
        with self.assertRaisesRegex(ValueError,'Missing original'):
            expected_timestamps(self.sequence)

    def test_source_mutation_fails(self):
        path = self.prepared/'manifest.json'
        pins = {str(path):digest(path)}
        verify_pins(pins)
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'changed'):
            verify_pins(pins)

    def test_readiness_checks_calibration_ledger_and_count(self):
        receipt = dict(sequence=self.sequence.name, expected_image_count=2,
            camera_csv='asl_folder/mav0/cam0/data.csv',camera_csv_sha256=digest(self.camera/'data.csv'),
            calibration_sha256={})
        ledger = self.sequence/'extracted_files.jsonl'
        ledger.write_text('ledger')
        receipt['file_ledger_sha256'] = digest(ledger)
        for kind in ('aria_calibrations','pinhole_calibrations'):
            folder = self.sequence/kind
            folder.mkdir()
            path = folder/(self.sequence.name+'.json')
            path.write_text('{}')
            receipt['calibration_sha256'][kind] = digest(path)
        target = self.sequence/'.download_complete.json'
        target.write_text(json.dumps(receipt))
        self.assertEqual(verify_readiness(self.sequence)['expected_image_count'],2)
        receipt['expected_image_count'] = 1
        target.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'image count'):
            verify_readiness(self.sequence)
        ledger.write_text('tampered')
        with self.assertRaisesRegex(ValueError,'ledger changed'):
            verify_readiness(self.sequence)

    def test_numeric_sequence_order(self):
        self.assertEqual(sorted(['sequence_2_1','sequence_1_10','sequence_1_2'],key=sequence_key),
                         ['sequence_1_2','sequence_1_10','sequence_2_1'])

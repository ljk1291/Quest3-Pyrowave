import json
from pathlib import Path
import tempfile
import unittest

from tools.quest3.preflight import snapshot_files, verify_snapshot, nvidia_driver, runtime_manifest
from unittest.mock import patch


class PreflightTests(unittest.TestCase):
    def test_backup_is_immutable_and_reports_subsequent_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'settings.json'
            source.write_text(json.dumps({'enabled': True}))
            records = snapshot_files({'settings': source, 'missing': root / 'absent'}, root / 'backup')
            self.assertEqual(verify_snapshot(records)[0]['current_matches'], True)
            source.write_text(json.dumps({'enabled': False}))
            check = verify_snapshot(records)[0]
            self.assertTrue(check['backup_valid'])
            self.assertFalse(check['current_matches'])
            self.assertEqual(json.loads(source.read_text()), {'enabled': False})
            self.assertIsNone(verify_snapshot(records)[1]['backup_valid'])
            with self.assertRaises(FileExistsError):
                snapshot_files({'settings': source}, root / 'backup')

    def test_corrupt_backup_cannot_verify(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'settings.json'
            source.write_text('{}')
            records = snapshot_files({'../settings': source}, root / 'backup')
            backup = Path(records[0]['snapshot'])
            self.assertEqual(backup.parent, root / 'backup')
            backup.write_text('corrupt')
            self.assertFalse(verify_snapshot(records)[0]['backup_valid'])

    def test_nvidia_driver_is_read_only_and_parses_csv(self):
        class Run:
            returncode=0
            stdout='NVIDIA GeForce RTX 5080, 600.12\n'
            stderr=''
        with patch('tools.quest3.preflight.shutil.which', return_value='nvidia-smi'), \
             patch('tools.quest3.preflight.subprocess.run', return_value=Run()) as run:
            result=nvidia_driver()
        self.assertEqual(result['gpus'][0]['driver_version'],'600.12')
        self.assertIn('--query-gpu=name,driver_version',run.call_args.args[0])

    def test_runtime_manifest_keeps_missing_runtime_explicit(self):
        result=runtime_manifest(None)
        self.assertFalse(result['exists'])
        self.assertIsNone(result['sha256'])


if __name__ == '__main__':
    unittest.main()

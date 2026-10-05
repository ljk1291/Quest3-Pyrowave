import os, tempfile, unittest
from pathlib import Path
from unittest import mock
from tools.xrbench import framebank as fb

class LeaseStatusDiagnostics(unittest.TestCase):
 def result(self, text): return type('R',(),{'returncode':0,'stdout':text,'stderr':'status stderr'})()
 def test_default_does_not_write_and_malformed_refuses(self):
  with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ,{},clear=True), mock.patch.object(fb,'_private_root',return_value=Path(t)), mock.patch.object(fb.subprocess,'run',return_value=self.result('{')):
   with self.assertRaisesRegex(PermissionError,'not valid JSON'): fb.WindowGuard(Path(t)/'lease',status_command=['status']).status()
   self.assertFalse((Path(t)/'lease'/'status-diagnostics').exists())
 def test_optin_records_malformed_and_never_retries(self):
  with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ,{'XRBENCH_LEASE_STATUS_DIAGNOSTICS':'1'},clear=True), mock.patch.object(fb,'_private_root',return_value=Path(t)), mock.patch.object(fb.subprocess,'run',return_value=self.result('{')) as run:
   lease=Path(t)/'lease'; lease.mkdir()
   with self.assertRaises(PermissionError): fb.WindowGuard(lease,status_command=['status']).status()
   rows=list((lease/'status-diagnostics').glob('*.json')); self.assertEqual(len(rows),1); self.assertEqual(run.call_count,1); self.assertIn('status stderr',rows[0].read_text())
 def test_outside_private_path_never_logs(self):
  with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as outside, mock.patch.dict(os.environ,{'XRBENCH_LEASE_STATUS_DIAGNOSTICS':'1'},clear=True), mock.patch.object(fb,'_private_root',return_value=Path(t)), mock.patch.object(fb.subprocess,'run',return_value=self.result('{')):
   p=Path(outside); self.assertRaises(PermissionError,fb.WindowGuard(p,status_command=['status']).status); self.assertFalse((p/'status-diagnostics').exists())
 def test_timeout_preserves_partial_bytes_and_remains_fatal(self):
  timeout=fb.subprocess.TimeoutExpired(['status'],10,output=b'partial\xff',stderr=b'error\xfe')
  with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ,{'XRBENCH_LEASE_STATUS_DIAGNOSTICS':'1'},clear=True), mock.patch.object(fb,'_private_root',return_value=Path(t)), mock.patch.object(fb.subprocess,'run',side_effect=timeout) as run:
   lease=Path(t)/'lease'; lease.mkdir(); self.assertRaisesRegex(PermissionError,'unavailable',fb.WindowGuard(lease,status_command=['status']).status); rows=list((lease/'status-diagnostics').glob('*.json')); self.assertEqual(run.call_count,1); self.assertEqual(len(rows),1); self.assertIn('partial�',rows[0].read_text())

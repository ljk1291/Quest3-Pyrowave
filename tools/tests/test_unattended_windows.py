"""Finite Windows ownership checks using only our disposable CPU child."""
import os
import subprocess
import sys
import unittest
from tools.quest3 import unattended as u


@unittest.skipUnless(os.name=='nt','Windows process handles required')
class OwnedProcessTest(unittest.TestCase):
    def test_comfy_discovery_ignores_its_own_and_parallel_probe_shells(self):
        child=subprocess.Popen(['powershell','-NoProfile','-NonInteractive','-Command',
                               '# ComfyUI discovery probe, no inference\nStart-Sleep -Seconds 20'],
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            rows=u.Host()._comfy_pids()
            self.assertNotIn(child.pid,[r['ProcessId'] for r in rows])
            self.assertFalse(any('Get-CimInstance Win32_Process' in r.get('CommandLine','') for r in rows))
        finally:
            if child.poll() is None: child.terminate()
            child.wait(timeout=5)

    def test_completed_owned_child_is_already_stopped(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(.1)'],
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            host=u.Host(); record=host.process_identity(child.pid); record['nonce']='test'
            child.wait(timeout=3)
            self.assertTrue(host.stop_owned_runtime(record))
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=3)
    def test_short_lived_child_identity_can_be_claimed_without_a_shell(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(.1)'],
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            record=u.Host().process_identity(child.pid)
            self.assertEqual(record['pid'],child.pid)
            self.assertTrue(record['path'].lower().endswith('python.exe'))
            self.assertGreater(record['started_epoch_s'],0)
            child.wait(timeout=3)
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=3)

    def test_handle_identity_rejects_mismatch_and_stops_owned_child(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(40)'],
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            host=u.Host(); record=host.process_identity(child.pid)
            record['nonce']='test'
            bad=dict(record,started_epoch_s=record['started_epoch_s']+1)
            with self.assertRaises(u.Refusal):
                host.run('powershell','-NoProfile','-NonInteractive','-Command',u.owned_stop_script(bad),timeout=10)
            self.assertIsNone(child.poll())
            host.stop_owned_runtime(record)
            child.wait(timeout=3)
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=3)


if __name__=='__main__': unittest.main()

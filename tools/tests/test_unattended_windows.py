"""Finite Windows ownership checks using only our disposable CPU child."""
import os
import subprocess
import sys
import unittest
from tools.quest3 import unattended as u


@unittest.skipUnless(os.name=='nt','Windows process handles required')
class OwnedProcessTest(unittest.TestCase):
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

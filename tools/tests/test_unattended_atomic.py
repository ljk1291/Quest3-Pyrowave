"""CPU-only Windows replacement and cleanup contracts."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.quest3 import unattended as u


def sharing_error():
    error = PermissionError(5, "sharing violation")
    error.winerror = 32
    return error


class AtomicWriteTests(unittest.TestCase):
    def test_windows_sharing_violation_retries_with_bounded_delays(self):
        sleeps = []
        with mock.patch.object(u.os, "name", "nt"), \
             mock.patch.object(u.os, "replace", side_effect=[sharing_error(), sharing_error(), None]) as replace:
            u._replace_with_retry("temporary", "state", sleep=sleeps.append)
        self.assertEqual(replace.call_count, 3)
        self.assertEqual(sleeps, [.02, .05])

    def test_nontransient_or_exhausted_replace_fails_closed(self):
        nontransient = PermissionError(5, "denied"); nontransient.winerror = 87
        with mock.patch.object(u.os, "name", "nt"), mock.patch.object(u.os, "replace", side_effect=nontransient) as replace:
            with self.assertRaises(PermissionError):
                u._replace_with_retry("temporary", "state", sleep=lambda _: None)
        self.assertEqual(replace.call_count, 1)
        with mock.patch.object(u.os, "name", "nt"), mock.patch.object(u.os, "replace", side_effect=[sharing_error() for _ in range(5)]) as replace:
            with self.assertRaises(PermissionError):
                u._replace_with_retry("temporary", "state", sleep=lambda _: None)
        self.assertEqual(replace.call_count, len(u._ATOMIC_REPLACE_DELAYS_S) + 1)

    def test_atomic_write_removes_temp_after_terminal_replacement_failure(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            with mock.patch.object(u, "_replace_with_retry", side_effect=PermissionError("terminal")):
                with self.assertRaises(PermissionError):
                    u.atomic_write(path, {"value": 1})
            self.assertEqual(list(Path(root).glob("state.json.*.tmp")), [])

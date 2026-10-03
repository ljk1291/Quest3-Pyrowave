import unittest
from pathlib import Path


class DualStreamDesignTests(unittest.TestCase):
    def test_note_is_design_only_and_has_the_required_trigger(self):
        text = (Path(__file__).parents[2] / "docs" / "WO-11-DUALSTREAM-H264-DESIGN.md").read_text(encoding="utf-8")
        for term in ("design note only", "h264fit", "best PyroWave", "fence", "HVS"):
            self.assertIn(term, text)

    def test_note_requires_pairing_lifecycle_and_timing_contracts(self):
        text = (Path(__file__).parents[2] / "docs" / "WO-11-DUALSTREAM-H264-DESIGN.md").read_text(encoding="utf-8")
        for term in ("stream_id", "stereo_frame_id", "pose_id", "never reuses a wrong frame", "IDR", "matching signed pair", "optical latency"):
            self.assertIn(term, text)

import unittest
from pathlib import Path


class StockCodecAuditTests(unittest.TestCase):
    def test_audit_preserves_source_and_proxy_boundaries(self):
        text = (Path(__file__).parents[2] / "docs" / "WO-12-STOCK-CODEC-AUDIT.md").read_text(encoding="utf-8")
        for expected in ("7eda092dbf0002281410a4222683ec228700cffb", "4096", "Main10", "FFmpeg 6.1", "candidates until Q3"):
            self.assertIn(expected, text)
        self.assertIn("not a hardware-capability or quality result", text)

    def test_audit_links_current_control_and_limit_sources(self):
        root = Path(__file__).parents[2]
        text = (root / "docs" / "WO-12-STOCK-CODEC-AUDIT.md").read_text(encoding="utf-8")
        for relative in ("tools/quest3/control.py", "tools/xrbench/plan.py", "patches/quest3-alvr.patch"):
            self.assertTrue((root / relative).exists())
            self.assertIn(relative, text)

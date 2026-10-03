import unittest
from pathlib import Path


class StockCodecAuditTests(unittest.TestCase):
    def test_audit_preserves_source_and_proxy_boundaries(self):
        text = (Path(__file__).parents[2] / "docs" / "WO-12-STOCK-CODEC-AUDIT.md").read_text(encoding="utf-8")
        for expected in (
            "7eda092dbf0002281410a4222683ec228700cffb",
            "one side-by-side elementary stream",
            "does **not** source-prove selection of H.264 High",
            "server_overrides_use_10bit = true",
            "use_10bit = false",
            "NV_ENC_CAPS_WIDTH_MAX",
            "legacy planning guard",
            "HEVC/AV1 Main10 candidates",
            "offline FFmpeg/NVENC proxy",
        ):
            self.assertIn(expected, text)
        self.assertIn("not a hardware\ncapability, quality, or live-stream result", text)

    def test_audit_links_current_control_and_limit_sources(self):
        root = Path(__file__).parents[2]
        text = (root / "docs" / "WO-12-STOCK-CODEC-AUDIT.md").read_text(encoding="utf-8")
        for relative in ("tools/quest3/control.py", "tools/xrbench/plan.py"):
            self.assertTrue((root / relative).exists())
            self.assertIn(relative, text)

    def test_audit_records_windows_nvenc_control_boundaries(self):
        text = (Path(__file__).parents[2] / "docs" / "WO-12-STOCK-CODEC-AUDIT.md").read_text(encoding="utf-8")
        for expected in (
            "platform/win32/VideoEncoderNVENC.cpp",
            "NV_ENC_PRESET_P1_GUID",
            "P7_GUID",
            "enableTemporalAQ",
            "4096×2048",
        ):
            self.assertIn(expected, text)

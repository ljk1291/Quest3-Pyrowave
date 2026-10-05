"""Static source-wiring checks for the inactive NVENC dimension preflight overlay."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH = (ROOT / "patches/nvenc-dimension-preflight.patch").read_text(encoding="utf-8")


class NvencDimensionPreflightWiringTests(unittest.TestCase):
    def test_overlay_is_explicitly_opt_in_and_runs_after_config_before_creation(self):
        env = PATCH.index('std::getenv("ALVR_NVENC_DIMENSION_PREFLIGHT")')
        create = PATCH.index('m_NvNecoder->CreateEncoder(&initializeParams)')
        self.assertLess(env, create)
        self.assertIn('std::strcmp(preflight, "1") == 0', PATCH)
        self.assertIn('NVENC dimension preflight failed:', PATCH)

    def test_overlay_fails_closed_on_unavailable_or_invalid_capability_values(self):
        self.assertIn('*value = 0;', PATCH)
        self.assertIn('!m_hEncoder || !m_nvenc.nvEncGetEncodeCaps', PATCH)
        self.assertIn('== NV_ENC_SUCCESS', PATCH)
        self.assertIn('NV_ENC_CAPS_WIDTH_MAX', PATCH)
        self.assertIn('NV_ENC_CAPS_HEIGHT_MAX', PATCH)
        self.assertIn('NV_ENC_CODEC_H264_GUID', PATCH)
        self.assertIn('NV_ENC_CODEC_HEVC_GUID', PATCH)
        self.assertIn('NV_ENC_CODEC_AV1_GUID', PATCH)

    def test_authoritative_fetch_stack_pins_and_applies_the_overlay(self):
        fetch = (ROOT / "tools/ci/fetch_sources.sh").read_text(encoding="utf-8")
        lock = (ROOT / "sources.lock.json").read_text(encoding="utf-8")
        self.assertIn('nvenc_dimension_preflight_patch', fetch)
        self.assertIn('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/nvenc-dimension-preflight.patch"', fetch)
        self.assertIn('"nvenc_dimension_preflight"', lock)


if __name__ == "__main__":
    unittest.main()

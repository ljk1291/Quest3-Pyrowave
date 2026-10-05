import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from xrbench import wo8_width_prepare as prep


class WidthPrepareTests(unittest.TestCase):
    def test_duplicate_preflight_accepts_incomplete_and_rejects_complete_exact_row(self):
        candidate={"experiment_id":"wo8_width_only_h264_p7_700","source_sha256":"a", "source_transform":{"profile":"h264width"}, "codec":"h264","rate_mbps":700,"encoded_eye":[2048,2784]}
        with tempfile.TemporaryDirectory() as root:
            ledger=Path(root)/"ledger.json"
            ledger.write_text(json.dumps({"rows":[dict(candidate, complete=False)]}))
            self.assertEqual(len(prep._assert_unique(candidate,[ledger])),1)
            ledger.write_text(json.dumps({"rows":[dict(candidate, complete=True)]}))
            with self.assertRaisesRegex(ValueError,"exact completed duplicate"):
                prep._assert_unique(candidate,[ledger])


    def test_prepare_uses_nested_mapped_crop_descriptor_for_periphery(self):
        source_hash = "a" * 64
        module_hash = "f" * 64
        mapped = {"x": 100, "y": 120, "width": 240, "height": 274}
        plan = {
            "cells": [{"experiment_id": "wo8_width_only_h264_p7_700", "source_transform": {
                "profile": "h264width", "softness": .5, "blur_only": False,
                "implementation_source_sha256": module_hash}, "eye_width": 2048,
                "eye_height": 2784, "stereo_width": 4096, "codec": "h264", "rate_mbps": 700}],
            "source": {"sha256": source_hash, "frame_identity": [
                {"source_sha256": source_hash} for _ in range(90)]},
            "source_adapter": {"geometry": {"input": [6144, 2776]}},
            "fence_rectangles": {"cropped": {"mapped": mapped, "review_label": "edge ROI"}},
        }
        identities = [{"source_sha256": source_hash} for _ in range(90)]
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            plan_path, source, ledger, output = root / "plan.json", root / "source.y4m", root / "ledger.json", root / "prepared"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            source.write_bytes(b"fixture")
            ledger.write_text(json.dumps({"rows": []}), encoding="utf-8")
            score_info = object()
            with mock.patch.object(prep.nvenc, "validate_plan", return_value=plan), \
                 mock.patch.object(prep.nvenc, "_require_jpeg_full_y4m", return_value={}), \
                 mock.patch.object(prep.fb, "sha256_file", return_value=source_hash), \
                 mock.patch.object(prep.fb, "inspect_y4m", return_value=object()), \
                 mock.patch.object(prep, "_sha", return_value=module_hash), \
                 mock.patch.object(prep.nvenc, "_stream_q3b_sources", return_value=(object(), score_info, identities, {})), \
                 mock.patch.object(prep.nvenc, "_q3b_periphery_mask", return_value=(None, {"kind": "periphery"})) as mask, \
                 mock.patch.object(prep.nvenc, "_q3b_centre_rect", return_value={"kind": "centre"}):
                prep.prepare(plan_path, source, output, [ledger])
            mask.assert_called_once_with(plan["cells"][0], score_info, mapped)
            self.assertTrue((output / "width-only-preparation.json").exists())


if __name__ == "__main__":
    unittest.main()

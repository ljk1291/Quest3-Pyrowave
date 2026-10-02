import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xrbench import framebank as fb


def tiny_source(tmp_path, *, frames=2, fps=90):
    """Two 4x4 eyes, deliberately sharing frame content to test ID not pixels."""
    p = tmp_path / "metro-input.y4m"
    info = fb.Y4MInfo(8, 4, fps, 1, "444", "FULL", 8 * 4 * 3, frames)
    frame = [np.hstack((np.zeros((4, 4), np.uint8), np.full((4, 4), 255, np.uint8))) for _ in range(3)]
    fb.write_y4m(p, info, [frame for _ in range(frames)])
    return p


class FrameBankTests(unittest.TestCase):
    def tmp(self):
        return tempfile.TemporaryDirectory()

    def test_tiny_y4m_identity_schema_and_default_matrix(self):
        with self.tmp() as temp:
            source = tiny_source(Path(temp))
            plan = fb.build_plan(source, 24.2, projection_evidence="test-projection", display_eye=(4, 4), geometries=((4, 4), (3, 2)))
            self.assertEqual(fb.inspect_y4m(source).frames, 2)
            self.assertEqual(len(plan["cells"]), 3 * 4 * 2)
            self.assertEqual([row["source_frame"] for row in plan["source"]["frame_identity"]], [0, 1])
            self.assertEqual(plan["source"]["frame_identity"][0]["source_sha256"], plan["source"]["frame_identity"][1]["source_sha256"])
            self.assertIs(fb.validate_plan(plan), plan)

    def test_cap_math_and_plan_cap_tampering_fail(self):
        self.assertEqual(fb.cap_bytes(500, 90), 694_444)
        self.assertAlmostEqual(fb.bpp(694_444, 3072, 3232), 694_444 * 8 / (2 * 3072 * 3232))
        with self.tmp() as temp:
            plan = fb.build_plan(tiny_source(Path(temp)), 24, projection_evidence="test-projection", display_eye=(4, 4), geometries=((4, 4),))
            plan["cells"][0]["cap_bytes"] += 1
            with self.assertRaisesRegex(ValueError, "cap math"):
                fb.validate_plan(plan)

    def test_resize_never_filters_across_stereo_seam(self):
        planes = [np.hstack((np.zeros((4, 4), np.uint8), np.full((4, 4), 255, np.uint8))) for _ in range(3)]
        out = fb.resize_per_eye(planes, 7, 5)
        self.assertEqual(out[0].shape, (5, 14)); self.assertEqual(np.max(out[0][:, :7]), 0); self.assertEqual(np.min(out[0][:, 7:]), 255)

    def test_seam_crossing_or_invalid_crops_fail(self):
        for crop in ({"name": "bad", "eye": "left", "x": .9, "y": 0, "w": .2, "h": .2}, {"name": "bad", "eye": "middle", "x": 0, "y": 0, "w": .2, "h": .2}, {"name": "bad", "eye": "right", "x": 0, "y": 0, "w": 0, "h": .2}):
            with self.assertRaises(ValueError):
                fb.validate_crops([crop])

    def test_c444_full_range_and_truncation_are_required(self):
        with self.tmp() as temp:
            temp = Path(temp)
            bad_range = temp / "limited.y4m"; bad_range.write_bytes(b"YUV4MPEG2 W8 H4 F90:1 Ip C444\nFRAME\n" + b"\0" * 96)
            with self.assertRaisesRegex(ValueError, "XCOLORRANGE"): fb.inspect_y4m(bad_range)
            bad_chroma = temp / "420.y4m"; bad_chroma.write_bytes(b"YUV4MPEG2 W8 H4 F90:1 Ip C420 XCOLORRANGE=FULL\nFRAME\n" + b"\0" * 48)
            with self.assertRaisesRegex(ValueError, "C444"): fb.inspect_y4m(bad_chroma)
            short = temp / "short.y4m"; short.write_bytes(b"YUV4MPEG2 W8 H4 F90:1 Ip C444 XCOLORRANGE=FULL\nFRAME\n" + b"\0" * 95)
            with self.assertRaisesRegex(ValueError, "truncated"): fb.inspect_y4m(short)

    def test_plan_rejects_wrong_source_geometry_and_identity_order(self):
        with self.tmp() as temp:
            source = tiny_source(Path(temp))
            with self.assertRaisesRegex(ValueError, "presentation input"): fb.build_plan(source, 24.0, projection_evidence="test-projection")
            plan = fb.build_plan(source, 24.0, projection_evidence="test-projection", display_eye=(4, 4), geometries=((4, 4),)); plan["source"]["frame_identity"][1]["source_frame"] = 7
            with self.assertRaisesRegex(ValueError, "ordered"): fb.validate_plan(plan)
            with self.assertRaisesRegex(ValueError, "90 Hz"):
                fb.build_plan(tiny_source(Path(temp), fps=72), 24.0, projection_evidence="test-projection", display_eye=(4, 4))

    def test_missing_tool_bad_hvs_and_window_fail_closed(self):
        with self.assertRaisesRegex(FileNotFoundError, "psnr_hvs_m_h"):
            fb.required_tools({"encode": sys.executable, "decode": sys.executable, "ffmpeg": sys.executable})
        with self.assertRaisesRegex(ValueError, "no finite"): fb.parse_hvs_m_h("some unrelated score=33")
        self.assertEqual(fb.parse_hvs_m_h("PSNR-HVS-M-H: 31.25"), 31.25)
        with self.tmp() as temp:
            inactive = Path(temp) / "window.json"; inactive.write_text(json.dumps({"active": False, "allow": ["frame_bank_pc"]}))
            with self.assertRaises(PermissionError): fb._window_allowed(inactive)

    def test_sanitized_report_omits_private_identity(self):
        result = {"complete": False, "failure_reasons": ["scoring_failed"], "projection_px_per_deg": 24, "cells": [{"wavelet": "haar", "source_frame_identity": ["private"], "error": "scoring_failed"}]}
        public = fb.sanitized_report(result)
        self.assertFalse(public["complete"]); self.assertNotIn("source_frame_identity", public["cells"][0])

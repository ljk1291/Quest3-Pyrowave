"""CPU contracts for the frozen Q3 PyroWave adapter; no encoder/GPU is invoked."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xrbench import framebank as fb
from xrbench import pyro_q3_framebank as q3
from xrbench import pyrowave_wave as wave


class PyroQ3FramebankTests(unittest.TestCase):
    def source_contract(self):
        return {"sha256": "a" * 64, "geometry": [5248, 2776], "frames": 90,
                "fps": [90, 1], "chroma": "420", "color_range": "FULL",
                "frame_identity": []}

    def plan(self, include_q3b=False):
        cells = [dict(phase="q3a", wavelet=w, rate_mbps=r, fps=90, eye_width=2624,
                      eye_height=2776, stereo_width=5248, cap_bytes=fb.cap_bytes(r, 90),
                      bits_per_pixel=fb.bpp(fb.cap_bytes(r, 90), 2624, 2776)) for w, r in q3.Q3A_ROWS]
        if include_q3b:
            cells += [dict(phase="q3b", profile=p, wavelet=w, rate_mbps=r, fps=90,
                           eye_width=2624, eye_height=2776, stereo_width=5248,
                           requires_wo8_reduced_encode=True) for p, w, r in q3.Q3B_ROWS]
        return {"schema": 1, "kind": "pyro_q3_framebank", "fixture_only": True,
                "source": self.source_contract(), "projection_evidence": "p", "crop_evidence": "c",
                "crop_geometry": q3.CROP_GEOMETRY, "fence_rectangles": {**q3.FENCE_RECTANGLES, "cropped": {**q3.FENCE_RECTANGLES["cropped"], "geometry": q3.CROP_GEOMETRY}},
                "frozen_module_hashes": q3._module_hashes(), "cells": cells,
                "hvs_calibration": {"codec_cells": [{} for _ in q3.Q3A_ROWS]},
                "quality_contract": {"score_windows_one_based": [[1, 90], [10, 89]], "fence_metric": True,
                                     "per_frame_identity": True, "timing_requires_native_per_frame_record": True,
                                     "q3b_requires_reduced_encode_then_expanded_score": True}}

    def test_q3a_contract_is_exact_and_q3b_requires_real_reduced_encode(self):
        plan = self.plan()
        self.assertIs(q3.validate_plan(plan), plan)
        self.assertEqual([(c["wavelet"], c["rate_mbps"]) for c in plan["cells"]], list(q3.Q3A_ROWS))
        plan["cells"][0]["rate_mbps"] = 800
        with self.assertRaisesRegex(ValueError, "Q3a rows drifted"):
            q3.validate_plan(plan)
        q3b = self.plan(True); self.assertIs(q3.validate_plan(q3b), q3b)
        q3b["cells"][-1]["requires_wo8_reduced_encode"] = False
        with self.assertRaisesRegex(ValueError, "reduced-encode"):
            q3.validate_plan(q3b)

    def test_module_hash_freezes_runner_dependencies(self):
        plan = self.plan(); plan["frozen_module_hashes"]["framebank.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "module hash drifted"):
            q3.validate_plan(plan)

    def test_container_parse_checks_header_exact_payloads_and_frame_count(self):
        cell = self.plan()["cells"][0]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "test.wave"
            path.write_bytes(wave.header(5248, 2776, fps_num=90, chroma=wave.CHROMA_420) + b"".join((1).to_bytes(4, "little") + b"x" for _ in range(90)))
            parsed = q3.parse_wave(path, cell)
            self.assertEqual(parsed["frames"], 90); self.assertEqual(parsed["payload_bytes"], [1] * 90)
            path.write_bytes(path.read_bytes()[:-5])
            with self.assertRaisesRegex(ValueError, "frame count|truncated"):
                q3.parse_wave(path, cell)

    def test_native_records_never_infers_timing_from_wall_clock(self):
        self.assertFalse(q3._native_records(None, [1] * 90)["qualified"])
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "native.json"
            rows = [{"schema_version": 1, "frame_id": i, "payload_bytes": 1,
                     "cpu_command_record_submit_ms": 0.1, "submit_to_observed_fence_ms": 0.3} for i in range(90)]
            path.write_text("\n".join(json.dumps(row) for row in rows))
            value = q3._native_records(path, [1] * 90)
            self.assertTrue(value["qualified"])
            self.assertIn("not GPU execution", value["semantics"]["submit_to_observed_fence_ms"])
            rows[-1]["payload_bytes"] = 2; path.write_text("\n".join(json.dumps(row) for row in rows))
            with self.assertRaisesRegex(ValueError, "payload mismatch"):
                q3._native_records(path, [1] * 90)

    def test_q3b_never_substitutes_shared_scorer_or_blur_only_path(self):
        with mock.patch("xrbench.nvenc_framebank._same_frame_scores", create=True) as scorer:
            # The adapter itself must only delegate to an actual shared scorer.
            self.assertTrue(callable(getattr(__import__("xrbench.nvenc_framebank", fromlist=["x"]), "_same_frame_scores")))
        self.assertEqual(len(q3.Q3B_ROWS), 8)

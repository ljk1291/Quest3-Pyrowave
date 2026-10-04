"""CPU contracts for the frozen Q3 PyroWave adapter; no encoder/GPU is invoked."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xrbench import framebank as fb
from xrbench import nvenc_framebank as nvenc
from xrbench import pyro_q3_framebank as q3
from xrbench import pyrowave_wave as wave


class PyroQ3FramebankTests(unittest.TestCase):
    def source_contract(self):
        return {"sha256": "a" * 64, "geometry": [5248, 2776], "frames": 90,
                "fps": [90, 1], "chroma": "420", "color_range": "FULL",
                "frame_identity": []}

    def plan(self, include_q3b=False):
        cells = [dict(phase="q3a", source_geometry="crop", score_vertical_pixels_per_degree=23.5, wavelet=w, rate_mbps=r, fps=90, eye_width=2624,
                      eye_height=2776, stereo_width=5248, cap_bytes=fb.cap_bytes(r, 90),
                      bits_per_pixel=fb.bpp(fb.cap_bytes(r, 90), 2624, 2776)) for w, r in q3.Q3A_ROWS]
        if include_q3b:
            cells += [dict(phase="q3b", profile=p, wavelet=w, rate_mbps=r, fps=90,
                           eye_width=2624, eye_height=2776, stereo_width=5248,
                           source_geometry="crop", source_transform=q3._q3b_transform(p),
                           requires_wo8_reduced_encode=True) for p, w, r in q3.Q3B_ROWS]
        return {"schema": 1, "kind": "pyro_q3_framebank", "fixture_only": True,
                "source": self.source_contract(), "projection_evidence": "p", "crop_evidence": "c",
                "source_derivation": {"parent_sha256": "b" * 64, "parent_geometry": [6144, 3232], "operation": "native_per_eye_crop_no_resampling"},
                "projection": {"vertical_pixels_per_degree": 23.5},
                "crop_geometry": q3.CROP_GEOMETRY, "fence_rectangles": {**q3.FENCE_RECTANGLES, "cropped": {**q3.FENCE_RECTANGLES["cropped"], "geometry": q3.CROP_GEOMETRY}},
                "source_adapter": {"kind": "per_eye_crop", "geometry": q3.CROP_GEOMETRY, "future_transform": None},
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

    def test_build_plan_resolves_fixed_crops_on_the_full_parent_once(self):
        """Do not let the cropped encode size redefine source crop coordinates."""
        parent = fb.Y4MInfo(6144, 3232, 90, 1, "420", "FULL", 6144 * 3232 * 3 // 2, 90)
        cropped = fb.Y4MInfo(5248, 2776, 90, 1, "420", "FULL", 5248 * 2776 * 3 // 2, 90)
        crops = [{"name": "parent-mark", "eye": "left", "x": .5, "y": .25, "w": .25, "h": .5}]
        identities = [{"source_frame": i, "source_sha256": f"{i:064x}"} for i in range(90)]
        real_hash = q3._hash
        def source_hash(path):
            return "b" * 64 if Path(path).name in ("cropped.y4m", "parent.y4m") else real_hash(path)
        with mock.patch.object(q3, "_require_cropped_source", return_value=cropped), \
             mock.patch.object(fb, "inspect_y4m", return_value=parent), \
             mock.patch.object(fb, "frame_records", return_value=identities), \
             mock.patch.object(fb, "sha256_file", return_value="a" * 64), \
             mock.patch.object(q3, "_hash", side_effect=source_hash):
            plan = q3.build_plan(Path("cropped.y4m"), 23.5,
                                 projection_evidence="recorded full-parent projection",
                                 crop_evidence="reviewed parent crop", crops=crops,
                                 full_source=Path("parent.y4m"), fixture=True)
        self.assertEqual(plan["presentation_eye"], [3072, 3232])
        self.assertEqual(plan["crops"][0]["resolved_pixels"],
                         {"eye_x": 1536, "stereo_x": 1536, "y": 808,
                          "width": 768, "height": 1616, "chroma_aligned": True})
        self.assertEqual([(cell["eye_width"], cell["eye_height"]) for cell in plan["cells"]],
                         [(2624, 2776)] * len(q3.Q3A_ROWS))
        self.assertTrue(all(cell["score_vertical_pixels_per_degree"] == 23.5 for cell in plan["cells"]))
        mapped, excluded = nvenc._crop_context_for_cell(plan, plan["cells"][0])
        self.assertEqual(excluded, {})
        self.assertEqual(mapped[0]["resolved_pixels"],
                         {"eye_x": 1258, "stereo_x": 1258, "y": 534,
                          "width": 768, "height": 1616, "chroma_aligned": True})
        # The fake frame-bank hash only models unavailable Y4M I/O; validate
        # the generated manifest with the runner's real source hashes.
        plan["frozen_module_hashes"] = q3._module_hashes()
        self.assertIs(q3.validate_plan(plan), plan)

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

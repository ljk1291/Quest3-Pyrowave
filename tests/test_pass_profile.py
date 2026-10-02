import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.quest3.pass_profile import main, parse


ACTIVATION = "[Q3PW_GPU_PASS] enabled=1 cadence_completed_frames=90 scope=granite_frame_context_mean"


class PassProfileTests(unittest.TestCase):
    def test_valid_fragment_phase_is_a_window_mean(self):
        result = parse("\n".join((
            ACTIVATION,
            "[Q3PW_GPU_PASS] completed_frames=90 wall_ms=1000 phase=iDWT fragment avg_ms=2.500 scope=granite_frame_context_mean",
            "[Q3PW_GPU_PASS] completed_frames=90 wall_ms=1100 phase=iDWT fragment avg_ms=3.500 scope=granite_frame_context_mean",
        )))
        self.assertTrue(result["healthy_profiling_claim"])
        phase = result["phase_window_means_ms"]["iDWT fragment"]
        self.assertEqual(phase["windows"], 2)
        self.assertEqual(phase["mean_avg_ms"], 3.0)
        self.assertIn("not exact-frame latency", result["limitations"])

    def test_missing_activation_cannot_be_healthy(self):
        result = parse("[Q3PW_GPU_PASS] completed_frames=90 wall_ms=1000 phase=Dequant avg_ms=1.0 scope=granite_frame_context_mean")
        self.assertFalse(result["healthy_profiling_claim"])
        self.assertIn("activation_missing_or_invalid", result["failure_reasons"])

    def test_nan_or_malformed_sample_fails_closed(self):
        result = parse("\n".join((
            ACTIVATION,
            "[Q3PW_GPU_PASS] completed_frames=90 wall_ms=1000 phase=Dequant avg_ms=nan scope=granite_frame_context_mean",
            "[Q3PW_GPU_PASS] completed_frames=oops wall_ms=1000 phase=iDWT avg_ms=1 scope=granite_frame_context_mean",
        )))
        self.assertFalse(result["healthy_profiling_claim"])
        self.assertEqual(result["samples"]["valid"], 0)
        self.assertIn("invalid_gpu_pass_samples", result["failure_reasons"])
        self.assertIn("no_valid_phase_samples", result["failure_reasons"])

    def test_native_no_valid_warning_blocks_claim_even_with_sample(self):
        result = parse("\n".join((
            ACTIVATION,
            "[Q3PW_GPU_PASS] completed_frames=90 wall_ms=1000 phase=iDWT avg_ms=1.25 scope=granite_frame_context_mean",
            "[Q3PW_GPU_PASS] no valid Granite timestamp labels; window completed_frames=90 wall_ms=1000",
        )))
        self.assertFalse(result["healthy_profiling_claim"])
        self.assertIn("native_no_valid_timestamp_labels", result["failure_reasons"])

    def test_unknown_phase_and_sample_before_activation_fail_closed(self):
        result = parse("\n".join((
            "[Q3PW_GPU_PASS] completed_frames=90 wall_ms=1000 phase=Dequant avg_ms=1 scope=granite_frame_context_mean",
            ACTIVATION,
            "[Q3PW_GPU_PASS] completed_frames=90 wall_ms=1000 phase=Unknown avg_ms=1 scope=granite_frame_context_mean",
        )))
        self.assertFalse(result["healthy_profiling_claim"])
        self.assertEqual(result["samples"]["valid"], 0)
        self.assertIn("invalid_gpu_pass_samples", result["failure_reasons"])
        self.assertIn("sample_before_valid_activation", result["warnings"])

    def test_cli_returns_nonzero_for_unhealthy_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "log.txt", root / "out.json"
            source.write_text("[Q3PW_GPU_PASS] no valid Granite timestamp labels; window completed_frames=90 wall_ms=1\n")
            with patch.object(sys, "argv", ["pass_profile", "--log", str(source), "--out", str(output)]):
                self.assertEqual(main(), 1)
            self.assertFalse(__import__("json").loads(output.read_text())["healthy_profiling_claim"])


if __name__ == "__main__":
    unittest.main()

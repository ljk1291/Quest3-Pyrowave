import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "quest3-pyrowave.patch"


def encode_cpp_diff() -> str:
    """Return the cumulative PyroWave patch's encode.cpp hunk only."""
    patch = PATCH.read_text(encoding="utf-8")
    start = patch.index("diff --git a/encode.cpp b/encode.cpp")
    end = patch.find("\ndiff --git ", start + 1)
    return patch[start:] if end == -1 else patch[start:end]


class PyroWaveEncodeTimingContractTests(unittest.TestCase):
    def test_optional_jsonl_has_frame_identity_payload_and_two_distinct_cpu_timings(self):
        source = encode_cpp_diff()

        self.assertIn("--timing-jsonl <path>", source)
        for field in (
            "schema_version",
            "frame_id",
            "payload_bytes",
            "cpu_command_record_submit_ms",
            "submit_to_observed_fence_ms",
        ):
            self.assertIn(field, source)

        # Keep measurement names explicit: neither wall time nor the existing aggregate
        # GPU timestamp intervals can be reinterpreted as a per-frame completion value.
        self.assertIn("command_record_start", source)
        self.assertIn("submit_returned", source)
        self.assertIn("fence_observed", source)

    def test_timing_file_is_flushed_after_fence_observation_not_on_submission_path(self):
        source = encode_cpp_diff()

        wait = source.index("q.fence->wait();")
        observed = source.index("const auto fence_observed", wait)
        collect = source.index("collect_frame_timing(timings, q", observed)
        flush = source.index("write_timing_jsonl(timing_jsonl_path, timings)")

        self.assertLess(wait, observed)
        self.assertLess(observed, collect)
        self.assertLess(collect, flush)
        self.assertIn("cannot perturb\n+\t// command recording or queue submission", source)


if __name__ == "__main__":
    unittest.main()

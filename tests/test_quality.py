import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.xrbench import bitstream, pyrowave_wave, quality
from tools.xrbench.quality import match


class QualityMatchTests(unittest.TestCase):
    def test_duplicate_distinct_tap_records_fail_closed(self):
        dumps = [{"index": 7, "frame": 12, "ts": 101}]
        taps = [
            {"pts_ns": 101, "offset": 10, "bytes": 20},
            {"pts_ns": 101, "offset": 30, "bytes": 40},
        ]

        pairs, missing, ambiguity = match(dumps, taps, include_ambiguity=True)

        self.assertEqual(pairs, [])
        self.assertEqual(missing, [7])
        self.assertEqual(ambiguity["dump_target_timestamps"], [])
        self.assertEqual(ambiguity["tap_target_timestamps"], [101])

    def test_duplicate_dump_records_fail_closed_against_unique_tap(self):
        dumps = [
            {"index": 2, "frame": 9, "ts": 202},
            {"index": 3, "frame": 10, "ts": 202},
        ]
        taps = [{"pts_ns": 202, "offset": 10, "bytes": 20}]

        pairs, missing, ambiguity = match(dumps, taps, include_ambiguity=True)

        self.assertEqual(pairs, [])
        self.assertEqual(missing, [2, 3])
        self.assertEqual(ambiguity["dump_target_timestamps"], [202])
        self.assertEqual(ambiguity["tap_target_timestamps"], [])

    def test_unique_timestamps_keep_dump_order_and_existing_shape(self):
        dumps = [
            {"index": 5, "frame": 20, "ts": 303},
            {"index": 1, "frame": 21, "ts": 404},
        ]
        taps = [
            {"pts_ns": 404, "offset": 40, "bytes": 4},
            {"pts_ns": 303, "offset": 30, "bytes": 3},
        ]

        pairs, missing = match(dumps, taps)

        self.assertEqual([index for index, _ in pairs], [5, 1])
        self.assertEqual([row["pts_ns"] for _, row in pairs], [303, 404])
        self.assertEqual(missing, [])

    def test_ambiguous_cell_writes_error_without_attempting_psnr(self):
        with tempfile.TemporaryDirectory() as tmp:
            cell = Path(tmp) / "cell"
            quality_dir = cell / "quality"
            quality_dir.mkdir(parents=True)
            source = quality_dir / "source.y4m"
            source.write_bytes(b"YUV4MPEG2 W2 H2 C420jpeg\n")
            Path(str(source) + ".frames.csv").write_text(
                "dump_index,frame_count,target_timestamp_ns\n0,1,909\n"
            )
            index = cell / "tap-quality.idx"
            payload = cell / "tap-quality.bin"
            index.write_text(
                "# alvr-bitstream-tap v1 codec=pyrowave width=2 height=2\n"
                "pts_ns,offset,bytes,idr\n909,0,4,1\n909,4,4,0\n"
            )
            payload.write_bytes(b"abcdefgh")
            raw_rows = bitstream.read_index(index)
            # This is precisely why validation must precede merging: raw TCP
            # records with a reused PTS collapse to one synthetic row.
            self.assertEqual(len(raw_rows), 2)
            self.assertEqual(len(pyrowave_wave.merge_packets(raw_rows)), 1)
            with patch.object(quality.subprocess, "run") as run:
                result = quality.score_cell(cell)

            self.assertEqual(result["frames"], 0)
            self.assertIn("ambiguous or non-identity target timestamp", result["error"])
            self.assertNotIn("psnr_y", result)
            run.assert_not_called()

    def test_nonpositive_timestamp_is_not_a_quality_identity(self):
        dumps = [{"index": 8, "frame": 21, "ts": 0}]
        taps = [{"pts_ns": 0, "offset": 0, "bytes": 4}]

        pairs, missing, ambiguity = match(dumps, taps, include_ambiguity=True)

        self.assertEqual(pairs, [])
        self.assertEqual(missing, [8])
        self.assertEqual(ambiguity["nonpositive_dump_timestamps"], [0])
        self.assertEqual(ambiguity["nonpositive_tap_timestamps"], [0])

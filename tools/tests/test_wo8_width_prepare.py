import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()

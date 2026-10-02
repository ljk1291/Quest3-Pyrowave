import shutil
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xrbench import hvs_scorer as hs

class HvsScorerTests(unittest.TestCase):
    def test_vertical_formula_and_invalid_inputs(self):
        self.assertAlmostEqual(hs.height_factor(23.6, 3232), 23.6 * 180 / (3232 * __import__('math').pi))
        with self.assertRaises(ValueError): hs.height_factor(float('nan'), 3232)
        with self.assertRaises(ValueError): hs.height_factor(23.6, 0)

    def test_patch_applies_and_reverses_against_exact_base(self):
        fixture=Path(__file__).parent/'fixtures'/'pyrowave-d2997ac-psnr.cpp'
        self.assertEqual(hs.sha256_file(fixture), hs.BASE_PSNR_SHA256)
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';source.mkdir();shutil.copyfile(fixture,source/'psnr.cpp')
            manifest=hs.verify_patch(source)
            self.assertEqual(manifest['upstream']['base_revision'], hs.UPSTREAM_BASE_REVISION)
            self.assertEqual(manifest['upstream']['license'], 'MIT')
            prepared=Path(temp)/'prepared'; hs.prepare_source(source,prepared)
            self.assertEqual(hs.sha256_file(prepared/'psnr.cpp'), hs.PATCHED_PSNR_SHA256)
            self.assertTrue((prepared/'PYROWAVE-HVS-PPD-SCORER.json').is_file())

    def test_prepare_cli_does_not_write_json_to_source_directory(self):
        fixture=Path(__file__).parent/'fixtures'/'pyrowave-d2997ac-psnr.cpp'
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';source.mkdir();shutil.copyfile(fixture,source/'psnr.cpp')
            output=Path(temp)/'prepared'
            self.assertEqual(hs.main(['prepare-source','--source',str(source),'--out',str(output)]),0)
            self.assertTrue((output/'PYROWAVE-HVS-PPD-SCORER.json').is_file())


if __name__ == '__main__': unittest.main()


import shutil
import tempfile
import unittest
from pathlib import Path
import sys
import hashlib
import subprocess
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xrbench import hvs_scorer as hs

class HvsScorerTests(unittest.TestCase):
    def test_vertical_formula_and_invalid_inputs(self):
        self.assertAlmostEqual(hs.height_factor(23.6, 3232), 23.6 * 180 / (3232 * __import__('math').pi))
        with self.assertRaises(ValueError): hs.height_factor(float('nan'), 3232)
        with self.assertRaises(ValueError): hs.height_factor(23.6, 0)

    def test_patch_applies_and_reverses_against_exact_base(self):
        fixture=Path(__file__).parent/'fixtures'/'pyrowave-d2997ac-psnr.cpp'
        # A pre-existing Windows worktree can retain CRLF across a rebase even
        # after the explicit LF attribute lands. Both exact hashes are recorded;
        # the canonical source bytes must still equal the pinned preimage.
        self.assertIn(hs.sha256_file(fixture), (hs.BASE_PSNR_SHA256, hs.WORKTREE_BASE_PSNR_SHA256))
        self.assertEqual(hashlib.sha256(fixture.read_bytes().replace(b'\r\n', b'\n')).hexdigest(), hs.BASE_PSNR_SHA256)
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

    def test_lf_and_crlf_preimages_produce_the_same_canonical_adapter(self):
        fixture=Path(__file__).parent/'fixtures'/'pyrowave-d2997ac-psnr.cpp'
        canonical=fixture.read_bytes().replace(b'\r\n',b'\n')
        with tempfile.TemporaryDirectory() as temp:
            for label,raw in (('lf',canonical),('crlf',canonical.replace(b'\n',b'\r\n'))):
                source=Path(temp)/label;source.mkdir();(source/'psnr.cpp').write_bytes(raw)
                output=Path(temp)/(label+'-prepared'); hs.prepare_source(source,output)
                self.assertEqual(hs.sha256_file(output/'psnr.cpp'),hs.PATCHED_PSNR_SHA256)
                self.assertNotIn(b'\r\n',(output/'psnr.cpp').read_bytes())

    def test_prepared_copy_inside_an_enclosing_git_repo_is_actually_patched(self):
        fixture=Path(__file__).parent/'fixtures'/'pyrowave-d2997ac-psnr.cpp'
        with tempfile.TemporaryDirectory() as temp:
            parent=Path(temp)/'parent'; parent.mkdir()
            subprocess.run(['git','init','-q',str(parent)],check=True,capture_output=True)
            outer=parent/'psnr.cpp'; outer.write_text('owner repository file must stay unchanged\n')
            source=parent/'source'; source.mkdir(); shutil.copyfile(fixture,source/'psnr.cpp')
            output=parent/'prepared'; hs.prepare_source(source,output)
            self.assertEqual(hs.sha256_file(output/'psnr.cpp'),hs.PATCHED_PSNR_SHA256)
            self.assertEqual(outer.read_text(),'owner repository file must stay unchanged\n')
            self.assertFalse((output/'.git').exists())


if __name__ == '__main__': unittest.main()

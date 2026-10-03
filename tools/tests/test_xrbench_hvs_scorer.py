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
            self.assertEqual(hs.sha256_file(prepared/'framebank_hvs.cpp'),manifest['standalone']['generated_source_sha256'])
            self.assertEqual(hs.sha256_file(prepared/'framebank_y4m.hpp'),manifest['standalone']['reader_sha256'])
            self.assertEqual(hs.metric_functions((prepared/'psnr.cpp').read_text()),hs.metric_functions(fixture.read_text()))

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


@unittest.skipUnless(shutil.which('g++'),'finite native reader checks require g++ (CI provides it)')
class NativeY4MTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.folder=Path(cls.temporary.name)
        cpp=cls.folder/'reader.cpp'
        cpp.write_text('''#include "framebank_y4m.hpp"
#include <iostream>
int main(int argc,char **argv) {
  try {
    if(argc!=4) return 2;
    Framebank::RawY4M a(argv[1]),b(argv[2]);
    if(!a.same_format(b)) throw std::runtime_error("mismatch");
    std::vector<uint8_t> x,y;
    auto count=Framebank::positive_integer(argv[3]);
    for(uint32_t i=0;i<count;i++){a.read_frame(x);b.read_frame(y);std::cout << int(x[0]) << ",";}
    if(!a.at_end() || !b.at_end()) throw std::runtime_error("extra data");
    return 0;
  } catch(const std::exception &e) {std::cerr<<e.what();return 1;}
}''')
        cls.binary=cls.folder/'reader'
        subprocess.run(['g++','-std=c++14','-Wall','-Wextra','-Werror',str(cpp),'-I',str(hs.native_path('framebank_y4m.hpp').parent),'-o',str(cls.binary)],check=True,capture_output=True,timeout=15)

    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    def raw(self,name,chroma='C420jpeg',full=True,n=3,header_extra='',truncate=0):
        path=self.folder/name
        header=f'YUV4MPEG2 W4 H4 F90:1 Ip {chroma} XCOLORRANGE={"FULL" if full else "LIMITED"} {header_extra}\n'.encode()
        size=24 if chroma=='C420jpeg' else 48
        data=header+b''.join(b'FRAME\n'+bytes([i+7])*size for i in range(n))
        path.write_bytes(data[:-truncate] if truncate else data)
        return path

    def run_reader(self,a,b,count=3):
        return subprocess.run([str(self.binary),str(a),str(b),str(count)],capture_output=True,text=True,timeout=3)

    def test_first_and_last_native_frame_are_preserved(self):
        for chroma in ('C420jpeg','C444'):
            a=self.raw('a',chroma); b=self.raw('b',chroma)
            result=self.run_reader(a,b)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,'7,8,9,')

    def test_short_extra_and_unsupported_inputs_are_rejected(self):
        good=self.raw('good')
        for bad in (self.raw('short',n=2),self.raw('extra',n=4),self.raw('truncated',truncate=1),
                    self.raw('precision',chroma='C420p10'),self.raw('duplicate',header_extra='W6')):
            self.assertNotEqual(self.run_reader(good,bad).returncode,0)

    def test_range_and_chroma_mismatch_are_rejected(self):
        good=self.raw('good')
        for bad in (self.raw('limited',full=False),self.raw('chroma',chroma='C444')):
            self.assertNotEqual(self.run_reader(good,bad).returncode,0)


if __name__ == '__main__': unittest.main()

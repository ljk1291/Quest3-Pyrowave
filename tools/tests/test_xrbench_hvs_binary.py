"""Exercise the built scorer's raw-input gate without creating a Vulkan device."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('Q3PW_HVS_SCORER_TEST_EXE'),'CI-built scorer required')
class RawScorerBinaryTests(unittest.TestCase):
    def fixture(self,folder,name,*,frames=3,chroma='C420jpeg',full=True,truncate=0):
        header=f'YUV4MPEG2 W4 H4 F90:1 Ip {chroma} XCOLORRANGE={"FULL" if full else "LIMITED"}\n'.encode()
        size=24 if chroma=='C420jpeg' else 48
        data=header+b''.join(b'FRAME\n'+bytes([n+7])*size for n in range(frames))
        path=Path(folder)/name; path.write_bytes(data[:-truncate] if truncate else data)
        return path

    def run_gate(self,a,b,*,frames=3):
        return subprocess.run([os.environ['Q3PW_HVS_SCORER_TEST_EXE'],
            '--reference',str(a),'--distorted',str(b),'--frames',str(frames),
            '--pixels-per-degree','23.564281542','--verify-inputs-only'],
            text=True,capture_output=True,timeout=5)

    def test_raw_frame_count_c420_c444_and_explicit_range(self):
        with tempfile.TemporaryDirectory() as folder:
            for chroma in ('C420jpeg','C444'):
                for full in (False,True):
                    a=self.fixture(folder,'a',chroma=chroma,full=full)
                    b=self.fixture(folder,'b',chroma=chroma,full=full)
                    result=self.run_gate(a,b)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertIn('VerifiedFrames = 3',result.stdout)
                    self.assertNotIn('PSNR-HVS-M-H:',result.stdout+result.stderr)
                    self.assertNotIn('GPU:',result.stdout+result.stderr)

    def test_incomplete_extra_and_mismatched_inputs_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            a=self.fixture(folder,'a')
            for options in ({'frames':2},{'frames':4},{'truncate':1},{'full':False},{'chroma':'C444'}):
                b=self.fixture(folder,'b',**options)
                result=self.run_gate(a,b)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('PSNR-HVS-M-H:',result.stdout+result.stderr)

    def test_ninety_frames_include_first_and_last(self):
        with tempfile.TemporaryDirectory() as folder:
            a=self.fixture(folder,'a',frames=90); b=self.fixture(folder,'b',frames=90)
            result=self.run_gate(a,b,frames=90)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('VerifiedFrames = 90',result.stdout)


if __name__=='__main__': unittest.main()

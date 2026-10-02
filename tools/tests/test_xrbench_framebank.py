import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xrbench import framebank as fb


def tiny_source(tmp_path, *, frames=2, fps=90, chroma="444", color_range="FULL"):
    p = tmp_path / "metro-input.y4m"
    info = fb.Y4MInfo(8, 4, fps, 1, chroma, color_range, fb._frame_bytes(8, 4, chroma), frames)
    full = [np.hstack((np.zeros((4, 4), np.uint8), np.full((4, 4), 255, np.uint8))) for _ in range(3)]
    frame = fb.to_420(full) if chroma == "420" else full
    fb.write_y4m(p, info, [frame for _ in range(frames)])
    return p


def lease(active=True):
    return {"schema": 1, "lease": {"active": active, "deadline_epoch_s": 4_000_000_000},
            "arm": {"active": active},
            "guards": {"restorer": {"ready": active, "alive": active}, "monitor": {"ready": active, "alive": active}},
            "cancellation": {"stop_requested": False, "paused": False, "competing_gpu": [], "monitor_fresh": active}}


class FrameBankTests(unittest.TestCase):
    def tmp(self): return tempfile.TemporaryDirectory()

    def test_tiny_y4m_identity_schema_and_default_matrix(self):
        with self.tmp() as temp:
            source = tiny_source(Path(temp)); plan = fb.build_plan(source, 24.2, projection_evidence="test-projection", display_eye=(4,4), geometries=((4,4),(2,2)))
            self.assertEqual(fb.inspect_y4m(source).frames,2); self.assertEqual(len(plan["cells"]),24)
            self.assertEqual([x["source_frame"] for x in plan["source"]["frame_identity"]],[0,1]); self.assertIs(fb.validate_plan(plan),plan)
            self.assertTrue(all(x["encoded_chroma"] == "444" for x in plan["cells"]))

    def test_cap_math_and_tampering_fail(self):
        self.assertEqual(fb.cap_bytes(500,90),694444); self.assertAlmostEqual(fb.bpp(694444,3072,3232),694444*8/(2*3072*3232))
        with self.tmp() as t:
            p=fb.build_plan(tiny_source(Path(t)),24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),));p["cells"][0]["cap_bytes"]+=1
            with self.assertRaisesRegex(ValueError,"cap math"):fb.validate_plan(p)

    def test_resize_never_crosses_seam_and_native_420_is_preserved(self):
        planes=[np.hstack((np.zeros((4,4),np.uint8),np.full((4,4),255,np.uint8))) for _ in range(3)]
        out=fb.resize_per_eye(planes,7,5);self.assertEqual(out[0].shape,(5,14));self.assertEqual(np.max(out[0][:,:7]),0);self.assertEqual(np.min(out[0][:,7:]),255)
        with self.tmp() as t:
            p=Path(t)/"420jpeg.y4m"; info=fb.Y4MInfo(8,4,90,1,"420","FULL",48,2);fb.write_y4m(p,info,[fb.to_420(planes)] * 2)
            p.write_bytes(p.read_bytes().replace(b"C420 XCOLOR",b"C420jpeg XCOLOR",1))
            native=fb.inspect_y4m(p);self.assertEqual((native.chroma,native.frame_bytes,native.frames,native.fps_num),("420",48,2,90))
            plan=fb.build_plan(p,24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),))
            self.assertEqual(plan["source"]["chroma"],"420");self.assertEqual(plan["cells"][0]["encoded_chroma"],"420")
            cropped=fb.crop_y4m(fb.to_420(planes),fb.Y4MInfo(8,4,90,1,"420","FULL",48,1),{"name":"odd","eye":"left","x":.1,"y":.1,"w":.5,"h":.5})
            self.assertEqual(cropped[0].shape[0] % 2,0);self.assertEqual(cropped[0].shape[1] % 2,0)

    def test_high_bit_depth_truncation_and_bad_crop_fail(self):
        with self.tmp() as t:
            t=Path(t);p=t/"p10.y4m";p.write_bytes(b"YUV4MPEG2 W8 H4 F90:1 C444p10 XCOLORRANGE=FULL\n")
            with self.assertRaisesRegex(ValueError,"high-bit-depth"):fb.inspect_y4m(p)
            short=t/"short.y4m";short.write_bytes(b"YUV4MPEG2 W8 H4 F90:1 C444 XCOLORRANGE=FULL\nFRAME\n"+b"\0"*95)
            with self.assertRaisesRegex(ValueError,"truncated"):fb.inspect_y4m(short)
        with self.assertRaisesRegex(ValueError,"crosses"):fb.validate_crops([{"name":"x","eye":"left","x":.9,"y":0,"w":.2,"h":.2}])

    def test_plan_rejects_geometry_fps_and_reordered_identity(self):
        with self.tmp() as t:
            src=tiny_source(Path(t));
            with self.assertRaisesRegex(ValueError,"presentation input"):fb.build_plan(src,24,projection_evidence="test")
            p=fb.build_plan(src,24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),));p["source"]["frame_identity"][1]["source_frame"]=7
            with self.assertRaisesRegex(ValueError,"ordered"):fb.validate_plan(p)
            self.assertEqual(fb.build_plan(tiny_source(Path(t),fps=72),24,projection_evidence="test",display_eye=(4,4))["source"]["header_fps"],[72,1])
            with self.assertRaisesRegex(ValueError,"F72:1 or F90:1"):fb.build_plan(tiny_source(Path(t),fps=60),24,projection_evidence="test",display_eye=(4,4))
            with self.assertRaisesRegex(ValueError,"height_factor"):fb.build_plan(src,24,projection_evidence="test",display_eye=(4,4),hvs_height_factor=1.05)

    def test_lossless_psnr_infinity_is_valid(self):
        self.assertTrue(fb._valid_metric("psnr_y",math.inf));self.assertFalse(fb._valid_metric("vmaf",math.inf));self.assertFalse(fb._valid_metric("psnr_y",math.nan))

    def test_hvs_requires_actual_upstream_factor(self):
        text="HeightFactor = 1.00 || PSNR-HVS-M-H: (Y) inf dB\nHeightFactor = 1.12 || PSNR-HVS-M-H: (Y) 31.2 dB"
        self.assertEqual(fb.parse_hvs_m_h(text,1.0),math.inf);self.assertEqual(fb.parse_hvs_m_h(text,1.12),31.2)
        with self.assertRaisesRegex(ValueError,"requested"):fb.parse_hvs_m_h(text,1.25)

    def test_guard_uses_status_allow_and_rejects_revocation(self):
        calls=[]
        def fake_run(cmd, **kwargs):
            calls.append(cmd);return type("R",(),{"returncode":0,"stdout":json.dumps(lease()),"stderr":""})()
        with mock.patch("xrbench.framebank.subprocess.run",fake_run):
            fb.WindowGuard(Path("window"),status_command=["status"]).status()
        self.assertIn("--require-allow",calls[0]);self.assertIn("frame_bank_pc",calls[0])
        with mock.patch("xrbench.framebank.subprocess.run",lambda *a,**k:type("R",(),{"returncode":0,"stdout":json.dumps(lease(False)),"stderr":""})()):
            with self.assertRaises(PermissionError):fb.WindowGuard(Path("window"),status_command=["status"]).status()

    def test_guard_polls_and_terminates_when_lease_is_revoked(self):
        class Proc:
            def __init__(self): self.calls=0;self.terminated=False
            def poll(self): self.calls+=1;return None
            def terminate(self): self.terminated=True
            def wait(self,timeout=None): return 0
            def kill(self): pass
            def communicate(self): return "",""
        proc=Proc()
        with mock.patch("xrbench.framebank.subprocess.Popen",return_value=proc),mock.patch.object(fb.WindowGuard,"status",side_effect=[lease(), PermissionError("revoked")]),mock.patch("xrbench.framebank.time.sleep"):
            with self.assertRaises(PermissionError):fb.WindowGuard(Path("window")).run(["fake"],cwd=Path.cwd(),env={},timeout_s=1)
        self.assertTrue(proc.terminated)

    def test_missing_tool_and_private_path_fail_closed(self):
        with self.assertRaisesRegex(FileNotFoundError,"psnr_hvs_m_h"):fb.required_tools({"encode":sys.executable,"decode":sys.executable,"ffmpeg":sys.executable})
        with self.assertRaisesRegex(ValueError,"results/local"):fb._private_path(Path(tempfile.gettempdir())/"raw")

    def test_fake_end_to_end_preserves_native_chroma_and_uses_pinned_cli(self):
        # No codec is launched: fake guard child calls copy files so the test proves
        # frame ordering, geometry and command construction without a GPU.
        with self.tmp() as t:
            t=Path(t); src=tiny_source(t, chroma="420", color_range="LIMITED"); plan=fb.build_plan(src,24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),),wavelets=("haar",),rates_mbps=(300,),crops=({"name":"aligned","eye":"left","x":0,"y":0,"w":.5,"h":.5},)); plan_path=t/"plan.json";plan_path.write_text(json.dumps(plan))
            out=fb._private_root()/"framebank-unit-e2e"
            import shutil
            shutil.rmtree(out,ignore_errors=True); calls=[]
            def fake_status(self): return lease()
            def fake_child(self,argv,**kwargs):
                calls.append(argv)
                if len(argv) == 4: shutil.copyfile(argv[1],argv[2])
                elif len(argv) == 3: shutil.copyfile(argv[1],argv[2])
                return 0,"",""
            def fake_score(*args,**kwargs): return {"psnr_y":math.inf,"psnr_cb":math.inf,"psnr_cr":math.inf,"ssim":1.0,"ssim_all":1.0,"vmaf":100.0,"psnr_hvs_m_h":math.inf}
            tools={"encode":sys.executable,"decode":sys.executable,"ffmpeg":sys.executable,"psnr_hvs_m_h":sys.executable}
            try:
                with mock.patch.object(fb.WindowGuard,"status",fake_status),mock.patch.object(fb.WindowGuard,"run",fake_child):
                    result=fb.run_plan(plan_path,src,out,tools,t/"window",score_fn=fake_score)
                self.assertTrue(result["complete"]);self.assertEqual(result["cells"][0]["identity_count"],2)
                self.assertEqual(plan["source"]["color_range"],"LIMITED");self.assertEqual(plan["cells"][0]["encoded_chroma"],"420")
                self.assertEqual(calls[0][1:], [str(out/"cell-00-haar-300-4x4"/"reference-c420.y4m"),str(out/"cell-00-haar-300-4x4"/"encoded.wave"),str(fb.cap_bytes(300,90))])
                self.assertEqual(calls[1][1:], [str(out/"cell-00-haar-300-4x4"/"encoded.wave"),str(out/"cell-00-haar-300-4x4"/"decoded-c420.y4m")]);self.assertEqual(fb.sanitized_report(result)["cells"][0]["codec_only"]["psnr_y"],math.inf)
            finally: shutil.rmtree(out,ignore_errors=True)

    def test_sanitized_report_omits_private_identity(self):
        public=fb.sanitized_report({"complete":False,"failure_reasons":["cell_failed"],"cells":[{"wavelet":"haar","source_frame_identity":["private"],"error":"cell_failed"}]})
        self.assertNotIn("source_frame_identity",public["cells"][0]);self.assertFalse(public["complete"])

if __name__ == "__main__": unittest.main()

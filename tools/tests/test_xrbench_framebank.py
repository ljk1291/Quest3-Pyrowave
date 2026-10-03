import json
import shutil
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
            source = tiny_source(Path(temp)); plan = fb.build_plan(source, 24.2, projection_evidence="test-projection", display_eye=(4,4), geometries=((4,4),(2,2)), fixture=True)
            self.assertEqual(fb.inspect_y4m(source).frames,2); self.assertEqual(len(plan["cells"]),24)
            self.assertEqual([x["source_frame"] for x in plan["source"]["frame_identity"]],[0,1]); self.assertIs(fb.validate_plan(plan),plan)
            self.assertTrue(all(x["encoded_chroma"] == "444" for x in plan["cells"]))

    def test_cap_math_and_tampering_fail(self):
        self.assertEqual(fb.cap_bytes(500,90),694444); self.assertAlmostEqual(fb.bpp(694444,3072,3232),694444*8/(2*3072*3232))
        with self.tmp() as t:
            p=fb.build_plan(tiny_source(Path(t)),24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),), fixture=True);p["cells"][0]["cap_bytes"]+=1
            with self.assertRaisesRegex(ValueError,"cap math"):fb.validate_plan(p)

    def test_resize_never_crosses_seam_and_native_420_is_preserved(self):
        planes=[np.hstack((np.zeros((4,4),np.uint8),np.full((4,4),255,np.uint8))) for _ in range(3)]
        out=fb.resize_per_eye(planes,7,5);self.assertEqual(out[0].shape,(5,14));self.assertEqual(np.max(out[0][:,:7]),0);self.assertEqual(np.min(out[0][:,7:]),255)
        with self.tmp() as t:
            p=Path(t)/"420jpeg.y4m"; info=fb.Y4MInfo(8,4,90,1,"420","FULL",48,2);fb.write_y4m(p,info,[fb.to_420(planes)] * 2)
            p.write_bytes(p.read_bytes().replace(b"C420 XCOLOR",b"C420jpeg XCOLOR",1))
            native=fb.inspect_y4m(p);self.assertEqual((native.chroma,native.frame_bytes,native.frames,native.fps_num),("420",48,2,90))
            plan=fb.build_plan(p,24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),),crops=({"name":"aligned","eye":"left","x":0,"y":0,"w":.5,"h":.5},), fixture=True)
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
            with self.assertRaisesRegex(ValueError,"presentation input"):fb.build_plan(src,24,projection_evidence="test", fixture=True)
            p=fb.build_plan(src,24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),), fixture=True);p["source"]["frame_identity"][1]["source_frame"]=7
            with self.assertRaisesRegex(ValueError,"ordered"):fb.validate_plan(p)
            self.assertEqual(fb.build_plan(tiny_source(Path(t),fps=72),24,projection_evidence="test",display_eye=(4,4), fixture=True)["source"]["header_fps"],[72,1])
            with self.assertRaisesRegex(ValueError,"F72:1 or F90:1"):fb.build_plan(tiny_source(Path(t)/"bad",fps=60),24,projection_evidence="test",display_eye=(4,4), fixture=True)
            with self.assertRaisesRegex(ValueError,"90 source frames"):fb.build_plan(src,24,projection_evidence="test",crop_evidence="semantic-crops",crops=({"name":"ui","eye":"left","x":0,"y":0,"w":.5,"h":.5},),display_eye=(4,4))

    def test_lossless_psnr_infinity_is_valid(self):
        self.assertTrue(fb._valid_metric("psnr_y",math.inf));self.assertFalse(fb._valid_metric("vmaf",math.inf));self.assertFalse(fb._valid_metric("psnr_y",math.nan))

    def test_libvmaf_null_hvs_preserves_separate_vmaf_without_inventing_values(self):
        from xrbench import rdmatrix
        with self.tmp() as t:
            path=Path(t)/"vmaf.json"
            path.write_text(json.dumps({"pooled_metrics":{"psnr_hvs":{"mean":None},
                            "psnr_hvs_y":{"mean":None},"vmaf":{"mean":97.360949}}}))
            self.assertEqual(rdmatrix.parse_vmaf_log(path),{"vmaf":97.360949})
            path.write_text(json.dumps({"pooled_metrics":{"vmaf":{"mean":None}}}))
            parsed=rdmatrix.parse_vmaf_log(path)
            self.assertFalse(fb._valid_metric("vmaf",parsed.get("vmaf")))

    def test_hvs_requires_emitted_vertical_calibration(self):
        ppd,height=23.6,3232; factor=ppd*180/(height*math.pi)
        text=f"PixelsPerDegree = {ppd:.6f} || HeightFactor = {factor:.8f} || PSNR-HVS-M-H: (Y) inf dB"
        parsed=fb.parse_hvs_m_h(text,ppd,height)
        self.assertEqual(parsed["value"],math.inf);self.assertAlmostEqual(parsed["height_factor"],factor,places=5)
        with self.assertRaisesRegex(ValueError,"vertical calibration"):fb.parse_hvs_m_h(text,24.2,height)

    def test_hvs_density_uses_vertical_axis_and_actual_image_height(self):
        measured=fb.hvs_calibration_for_vertical_ppd(23.6,3232)
        self.assertAlmostEqual(measured["height_factor"],23.6*180/(3232*math.pi))
        self.assertTrue(measured["adapter_required"])

    def test_decoded_range_mismatch_is_rejected(self):
        with self.tmp() as t:
            t=Path(t); ref=tiny_source(t, color_range="FULL"); decoded=t/"decoded.y4m"; decoded.write_bytes(ref.read_bytes().replace(b"XCOLORRANGE=FULL",b"XCOLORRANGE=LIMITED",1))
            with self.assertRaisesRegex(ValueError,"decoded_identity_or_geometry_mismatch"): fb._assert_same_frames(ref,decoded,fb.inspect_y4m(ref))

    def test_production_plan_requires_90_frames_and_records_vertical_hvs_adapter(self):
        with self.tmp() as t:
            t=Path(t); source=tiny_source(t,frames=90); plan=fb.build_plan(source,23.6,horizontal_pixels_per_degree=24.2,projection_evidence="projection-verified",crop_evidence="metro-crop-review",crops=({"name":"rails","eye":"left","x":0,"y":0,"w":.5,"h":.5},),display_eye=(4,4),geometries=((4,4),),wavelets=("haar",),rates_mbps=(300,)); self.assertEqual(plan["projection"]["hvs_axis"],"vertical")
            self.assertAlmostEqual(plan["hvs_calibration"]["display"]["vertical_pixels_per_degree"],23.6)
            self.assertIs(fb.validate_plan(plan),plan)

    def test_production_crops_are_explicit_safe_and_pixel_frozen(self):
        with self.tmp() as t:
            source=tiny_source(Path(t),frames=90,chroma="420")
            crops=[{"name":"rails","eye":"left","x":.11,"y":.11,"w":.51,"h":.51},{"name":"fog-ui","eye":"right","x":.25,"y":.25,"w":.5,"h":.5}]
            with self.assertRaisesRegex(ValueError,"caller-selected"): fb.build_plan(source,23.6,projection_evidence="p",crop_evidence="c",display_eye=(4,4))
            plan=fb.build_plan(source,23.6,projection_evidence="p",crop_evidence="c",crops=crops,display_eye=(4,4),geometries=((4,4),),wavelets=("haar",),rates_mbps=(300,))
            self.assertEqual(plan["crops"][0]["resolved_pixels"],{"eye_x":0,"stereo_x":0,"y":0,"width":2,"height":2,"chroma_aligned":True})
            self.assertEqual(plan["crops"][1]["resolved_pixels"]["stereo_x"],4)
            self.assertIs(fb.validate_plan(plan),plan)
            plan["crops"][0]["resolved_pixels"]["width"]+=2
            with self.assertRaisesRegex(ValueError,"frozen crop pixels"): fb.validate_plan(plan)
        with self.assertRaisesRegex(ValueError,"safe lowercase"): fb.validate_crops([{"name":"Foliage.png","eye":"left","x":0,"y":0,"w":.5,"h":.5}])

    def test_crops_cli_json_and_file_input(self):
        crops=[{"name":"ui","eye":"left","x":0,"y":0,"w":.5,"h":.5}]
        self.assertEqual(fb.parse_crops_argument(json.dumps(crops)),crops)
        with self.tmp() as t:
            path=Path(t)/"crops.json";path.write_text(json.dumps(crops))
            self.assertEqual(fb.parse_crops_argument("@"+str(path)),crops)
        with self.assertRaisesRegex(ValueError,"JSON"): fb.parse_crops_argument("not-json")

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
            def __init__(self): self.calls=0;self.terminated=False;self.pid=123
            def poll(self): self.calls+=1;return None
            def terminate(self): self.terminated=True
            def wait(self,timeout=None): return 0
            def kill(self): pass
            def communicate(self): return "",""
        class Registry:
            def register(self,*args): return {"pid":args[1]}
            def unregister(self,*args): return None
        proc=Proc()
        with mock.patch("xrbench.framebank.subprocess.Popen",return_value=proc),mock.patch.object(fb.WindowGuard,"status",side_effect=[lease(), PermissionError("revoked")]),mock.patch("xrbench.framebank.time.sleep"):
            with self.assertRaises(PermissionError):fb.WindowGuard(Path("window"),job_registry=Registry()).run(["fake"],cwd=Path.cwd(),env={},timeout_s=1)
        self.assertTrue(proc.terminated)

    def test_guard_refuses_unregistered_child_and_terminates_it(self):
        class Proc:
            pid=123
            def poll(self): return None
            def terminate(self): self.terminated=True
            def wait(self,timeout=None): return 0
            def kill(self): pass
        class Registry:
            def register(self,*args): raise PermissionError("identity unproven")
            def unregister(self,*args): raise AssertionError("must not unregister")
        proc=Proc();proc.terminated=False
        with mock.patch("xrbench.framebank.subprocess.Popen",return_value=proc),mock.patch.object(fb.WindowGuard,"status",return_value=lease()):
            with self.assertRaises(PermissionError): fb.WindowGuard(Path("window"),job_registry=Registry()).run(["fake"],cwd=Path.cwd(),env={},timeout_s=1)
        self.assertTrue(proc.terminated)

    def test_guard_uses_disk_backed_output_and_checks_lease_after_exit(self):
        class Proc:
            returncode=0
            pid=123
            def poll(self): return 0
            def communicate(self): return "",""
        class Registry:
            def __init__(self): self.calls=[]
            def register(self,*args): self.calls.append(("register",args)); return {"pid":args[1]}
            def unregister(self,*args): self.calls.append(("unregister",args))
        registry=Registry(); proc=Proc()
        with mock.patch("xrbench.framebank.subprocess.Popen",return_value=proc) as spawned, mock.patch.object(fb.WindowGuard,"status",side_effect=[lease(),lease()]):
            guard=fb.WindowGuard(Path("window"),job_registry=registry);self.assertEqual(guard.run(["fake"],cwd=Path.cwd(),env={},timeout_s=1)[0],0)
        self.assertEqual([x[0] for x in registry.calls],["register","unregister"]);self.assertEqual(len(guard.owned_jobs),1)
        self.assertIsNot(spawned.call_args.kwargs["stdout"],__import__("subprocess").PIPE)
        self.assertIsNot(spawned.call_args.kwargs["stderr"],__import__("subprocess").PIPE)

    def test_missing_tool_and_private_path_fail_closed(self):
        with self.assertRaisesRegex(FileNotFoundError,"psnr_hvs_m_h"):fb.required_tools({"encode":sys.executable,"decode":sys.executable,"ffmpeg":sys.executable})
        with self.assertRaisesRegex(ValueError,"results/local"):fb._private_path(Path(tempfile.gettempdir())/"raw")

    def test_fake_end_to_end_preserves_native_chroma_and_uses_pinned_cli(self):
        # No codec is launched: fake guard child calls copy files so the test proves
        # frame ordering, geometry and command construction without a GPU.
        with self.tmp() as t:
            t=Path(t); src=tiny_source(t, chroma="420", color_range="LIMITED"); plan=fb.build_plan(src,24,projection_evidence="test",display_eye=(4,4),geometries=((4,4),),wavelets=("haar",),rates_mbps=(300,),crops=({"name":"aligned","eye":"left","x":0,"y":0,"w":.5,"h":.5},), fixture=True); plan_path=t/"plan.json";plan_path.write_text(json.dumps(plan))
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
                    result=fb.run_plan(plan_path,src,out,tools,t/"window",allow_fixture=True, score_fn=fake_score)
                    saved=(out/'framebank-private.json').read_bytes()
                    with self.assertRaises(FileExistsError): fb.run_plan(plan_path,src,out,tools,t/'window',allow_fixture=True,score_fn=fake_score)
                    self.assertEqual((out/'framebank-private.json').read_bytes(),saved)
                self.assertTrue(result["complete"]);self.assertEqual(result["cells"][0]["identity_count"],2)
                self.assertEqual(plan["source"]["color_range"],"LIMITED");self.assertEqual(plan["cells"][0]["encoded_chroma"],"420")
                self.assertEqual(calls[0][1:], [str(out/"cell-00-haar-300-4x4"/"reference-c420.y4m"),str(out/"cell-00-haar-300-4x4"/"encoded.wave"),str(fb.cap_bytes(300,90))])
                self.assertEqual(calls[1][1:], [str(out/"cell-00-haar-300-4x4"/"encoded.wave"),str(out/"cell-00-haar-300-4x4"/"decoded-c420.y4m")]);self.assertEqual(fb.sanitized_report(result)["cells"][0]["codec_only"]["psnr_y"],math.inf)
            finally: shutil.rmtree(out,ignore_errors=True)

    def test_pinned_hvs_cli_arguments_and_calibration_contract(self):
        class Guard:
            def __init__(self): self.argv=None
            def run(self,argv,**kwargs):
                self.argv=argv
                return 0, "ScoredFrames = 90 || PixelsPerDegree = 23.600000 || HeightFactor = 0.41837265 || PSNR-HVS-M-H: (Y) 31.2 dB", ""
        guard=Guard()
        score=fb._score_hvs_m_h(Path("pyrowave-psnr-hvs-m"),Path("reference.y4m"),Path("distorted.y4m"),90,23.6,3232,guard,Path.cwd(),{},1)
        self.assertEqual(guard.argv,["pyrowave-psnr-hvs-m","--reference","reference.y4m","--distorted","distorted.y4m","--frames","90","--pixels-per-degree","23.6"])
        self.assertAlmostEqual(score["value"],31.2)

    def test_sanitized_report_omits_private_identity(self):
        public=fb.sanitized_report({"complete":False,"failure_reasons":["cell_failed"],"cells":[{"wavelet":"haar","source_frame_identity":["private"],"error":"cell_failed"}]})
        self.assertNotIn("source_frame_identity",public["cells"][0]);self.assertFalse(public["complete"])

    def test_failed_decoder_stops_the_frozen_matrix(self):
        with self.tmp() as t:
            t=Path(t); src=tiny_source(t)
            plan=fb.build_plan(src,24,projection_evidence="test",display_eye=(4,4),
                               geometries=((4,4),),wavelets=("haar",),rates_mbps=(300,500),fixture=True)
            plan_path=t/"plan.json"; plan_path.write_text(json.dumps(plan))
            fb._private_root().mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=fb._private_root()) as out_name:
                out=Path(out_name)/"new"; calls=[]
                def child(self,argv,**kwargs):
                    calls.append(argv)
                    if len(argv)==4:
                        shutil.copyfile(argv[1],argv[2]); return 0,"",""
                    return 1,"terminal decoder failure",""
                tools={k:sys.executable for k in ("encode","decode","ffmpeg","psnr_hvs_m_h")}
                with mock.patch.object(fb.WindowGuard,"status",return_value=lease()),mock.patch.object(fb.WindowGuard,"run",child):
                    result=fb.run_plan(plan_path,src,out,tools,t/"window",allow_fixture=True)
                self.assertFalse(result["complete"])
                self.assertEqual(result["failure_reasons"],["decode_failed"])
                self.assertEqual(len(result["cells"]),1); self.assertEqual(len(calls),2)
                self.assertFalse((out/"cell-01-haar-500-4x4").exists())

    def test_private_command_log_survives_lease_revocation(self):
        class Proc:
            pid=123
            def __init__(self): self.stopped=False
            def poll(self): return 0 if self.stopped else None
            def terminate(self): self.stopped=True
            def wait(self,timeout=None): return 0
        class Registry:
            def register(self,*args): pass
            def unregister(self,*args): pass
        proc=Proc()
        def spawn(*args,**kwargs):
            kwargs["stdout"].write("decoder diagnostic before revocation\n")
            kwargs["stdout"].flush()
            return proc
        fb._private_root().mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fb._private_root()) as out_name:
            cwd=Path(out_name)
            with mock.patch("xrbench.framebank.subprocess.Popen",side_effect=spawn),mock.patch.object(fb.WindowGuard,"status",side_effect=[lease(),PermissionError("revoked")]):
                with self.assertRaises(PermissionError):
                    fb.WindowGuard(Path("window"),job_registry=Registry()).run(["fake"],cwd=cwd,env={},timeout_s=1)
            self.assertTrue(proc.stopped)
            logs=list(cwd.glob("command-*.log")); self.assertEqual(len(logs),1)
            self.assertIn("diagnostic before revocation",logs[0].read_text())

    def test_codec_environment_clears_inherited_experiments(self):
        env,record=fb.codec_environment({'PATH':'keep','PYROWAVE_FORCE_FRAGMENT':'1',
                'PYROWAVE_FUSED_HAAR':'1','pyrowave_batch_dequant':'1','PYROWAVE_LEGACY_GAINS':'1'},'haar')
        self.assertEqual(env,{'PATH':'keep','PYROWAVE_WAVELET':'haar','PYROWAVE_FORCE_COMPUTE':'1'})
        self.assertEqual(record['set']['PYROWAVE_WAVELET'],'haar')
        with self.assertRaises(ValueError): fb.codec_environment({},'unknown')

    def test_tools_metadata_binds_binary_hashes_and_dependency_revisions(self):
        from xrbench import hvs_scorer as hs
        import hashlib
        root=Path(fb.__file__).resolve().parents[2]
        with self.tmp() as t:
            folder=Path(t); tools={}
            for name,filename in (('encode','pyrowave-encode.exe'),('decode','pyrowave-decode.exe'),
                                  ('psnr_hvs_m_h','pyrowave-psnr-hvs-m.exe')):
                tools[name]=folder/filename; tools[name].write_bytes(name.encode())
            source=folder/'HVS-SCORER-SOURCE.json'; source.write_text(json.dumps(hs.manifest()))
            shader=folder/'psnr_hvs_m.comp'
            shutil.copyfile(Path(__file__).parent/'fixtures/pyrowave-d2997ac-psnr_hvs_m.comp',shader)
            imports=folder/'FRAMEBANK-IMPORTS.json'
            imports.write_text(json.dumps({'schema':1,'kind':'framebank_windows_imports',
                'tools':{p.name:[{'name':'kernel32.dll','provider':'windows_system'}] for p in tools.values()}}))
            lock=json.loads((root/'sources.lock.json').read_text())
            lock_hash=hashlib.sha256((root/'sources.lock.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            fork=json.loads((root/'fork.json').read_text())
            build={'repository_commit':'a'*40,'sources_lock_sha256':lock_hash,'dependency_revisions':lock,
                   'shader_hashes':{'test':'b'*64},'protocol_version':fork['protocol_version'],
                   'client_package_id':fork['client_package_id'],
                   'artifact_sha256':{path.name:fb.sha256_file(path) for path in tools.values()}}
            build['artifact_sha256'].update({p.name:fb.sha256_file(p) for p in (shader,imports)})
            build_path=folder/'BUILD-METADATA.json'; build_path.write_text(json.dumps(build))
            meta={'schema':1,'kind':'pyrowave_framebank_tools_build','source_lock_sha256':lock_hash,
                  'source_psnr_cpp_sha256':hs.PATCHED_PSNR_SHA256,'source_manifest_sha256':fb.sha256_file(source),
                  'imports_manifest_sha256':fb.sha256_file(imports),
                  'tools':{field:fb.sha256_file(tools[name]) for name,field in
                           (('encode','encode_sha256'),('decode','decode_sha256'),('psnr_hvs_m_h','scorer_sha256'))}}
            path=folder/'FRAMEBANK-TOOLS-BUILD-METADATA.json'; path.write_text(json.dumps(meta))
            self.assertEqual(fb.verify_tools_build(tools,path)['repository_commit'],'a'*40)
            # These are deliberately non-executable fixture bytes. Verification
            # must work without launching codec/scorer processes or creating a GPU.
            self.assertEqual(fb.main(['verify-tools','--tools-metadata',str(path)]),0)
            meta['source_lock_sha256']='0'*64; path.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'source provenance'):
                fb.main(['verify-tools','--tools-metadata',str(path)])
            meta['source_lock_sha256']=lock_hash; path.write_text(json.dumps(meta))
            original_shader=shader.read_bytes(); shader.write_bytes(b'changed shader')
            with self.assertRaisesRegex(ValueError,'shader'): fb.verify_tools_build(tools,path)
            shader.write_bytes(original_shader)
            original_imports=imports.read_bytes()
            missing={'schema':1,'kind':'framebank_windows_imports','tools':{
                p.name:[{'name':'missing-codec.dll','provider':'bundle','sha256':'0'*64}] for p in tools.values()}}
            imports.write_text(json.dumps(missing))
            meta['imports_manifest_sha256']=fb.sha256_file(imports)
            build['artifact_sha256'][imports.name]=fb.sha256_file(imports)
            path.write_text(json.dumps(meta)); build_path.write_text(json.dumps(build))
            with self.assertRaisesRegex(ValueError,'dependency missing'): fb.verify_tools_build(tools,path)
            imports.write_bytes(original_imports); meta['imports_manifest_sha256']=fb.sha256_file(imports)
            build['artifact_sha256'][imports.name]=fb.sha256_file(imports)
            path.write_text(json.dumps(meta)); build_path.write_text(json.dumps(build))
            tools['decode'].write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'binary differs'): fb.verify_tools_build(tools,path)
            tools['decode'].write_bytes(b'decode')
            build['dependency_revisions']['pyrowave']['commit']='0'*40; build_path.write_text(json.dumps(build))
            with self.assertRaisesRegex(ValueError,'identity'): fb.verify_tools_build(tools,path)

    def test_hvs_transport_requires_the_exact_scored_frame_count(self):
        class Guard:
            def run(self,*args,**kwargs):
                return 0,'ScoredFrames = 89 || PixelsPerDegree = 23.6 || HeightFactor = 0.41837265 || PSNR-HVS-M-H: (Y) 31.2 dB',''
        with self.assertRaisesRegex(ValueError,'frame count'):
            fb._score_hvs_m_h(Path('scorer'),Path('ref'),Path('dist'),90,23.6,3232,Guard(),Path.cwd(),{},1)

    def test_hvs_gpu_gate_requires_identity_and_known_error_ratio(self):
        def good(tool,reference,distorted,*args):
            return {'value':{'zero':math.inf,'shift32':30.0,'shift64':30.0-20*math.log10(2)}[distorted.stem]}
        with self.tmp() as t,mock.patch.object(fb,'_score_hvs_m_h',side_effect=good):
            report=fb.hvs_gpu_sanity('fake',Path(t)/'sanity',23.6,None,{},1)
            self.assertTrue(report['passed'])
            self.assertEqual(fb.inspect_y4m(Path(t)/'sanity/zero.y4m').frames,3)
        with self.tmp() as t,mock.patch.object(fb,'_score_hvs_m_h',return_value={'value':math.inf}):
            with self.assertRaisesRegex(ValueError,'sanity gate'): fb.hvs_gpu_sanity('fake',Path(t)/'sanity',23.6,None,{},1)

if __name__ == "__main__": unittest.main()

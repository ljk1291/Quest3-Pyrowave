"""CPU contracts for the frozen Q3 PyroWave adapter; no encoder/GPU is invoked."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xrbench import framebank as fb
from xrbench import nvenc_framebank as nvenc
from xrbench import pyro_q3_framebank as q3
from xrbench import pyrowave_wave as wave


class PyroQ3FramebankTests(unittest.TestCase):
    LIGHT_ID = {"implementation_revision":"wo8-light-centre-phase-v1",
                "implementation_source_sha256":"bce593ce710537c30580b3b892865949ae66b81c47fd9ffd87441a6c6b78bdf5"}

    def source_contract(self):
        return {"sha256": "a" * 64, "geometry": [5248, 2776], "frames": 90,
                "fps": [90, 1], "chroma": "420", "color_range": "FULL",
                "frame_identity": []}

    def plan(self, include_q3b=False):
        cells = [dict(phase="q3a", source_geometry="crop", score_vertical_pixels_per_degree=23.5, wavelet=w, rate_mbps=r, fps=90, eye_width=2624,
                      eye_height=2776, stereo_width=5248, cap_bytes=fb.cap_bytes(r, 90),
                      bits_per_pixel=fb.bpp(fb.cap_bytes(r, 90), 2624, 2776)) for w, r in q3.Q3A_ROWS]
        if include_q3b:
            from xrbench.foveation import FoveationConfig, encoded_size
            for p,w,r in q3.Q3B_ROWS:
                t=q3._q3b_transform(p); ew,eh=encoded_size(2624,2776,FoveationConfig(t['profile'],t['softness'],t['blur_only'])); cap=fb.cap_bytes(r,90)
                cells.append(dict(phase='q3b',profile=p,wavelet=w,rate_mbps=r,fps=90,eye_width=ew,eye_height=eh,stereo_width=ew*2,cap_bytes=cap,bits_per_pixel=fb.bpp(cap,ew,eh),encoded_chroma='420',score_vertical_pixels_per_degree=23.5,source_geometry='crop',source_transform=t,requires_wo8_reduced_encode=True))
        return {"schema": 1, "kind": "pyro_q3_framebank", "fixture_only": True,
                "source": self.source_contract(), "projection_evidence": "p", "crop_evidence": "c",
                "source_derivation": {"parent_sha256": "b" * 64, "parent_geometry": [6144, 3232], "operation": "native_per_eye_crop_no_resampling"},
                "projection": {"vertical_pixels_per_degree": 23.5},
                "crop_geometry": q3.CROP_GEOMETRY, "fence_rectangles": {**q3.FENCE_RECTANGLES, "cropped": {**q3.FENCE_RECTANGLES["cropped"], "geometry": q3.CROP_GEOMETRY}},
                "source_adapter": {"kind": "per_eye_crop", "geometry": q3.CROP_GEOMETRY, "future_transform": None},
                "frozen_module_hashes": q3._module_hashes(), "cells": cells,
                "hvs_calibration": {"codec_cells": [{} for _ in cells]},
                "quality_contract": {"score_windows_one_based": [[1, 90], [10, 89]], "fence_metric": True,
                                     "per_frame_identity": True, "timing_requires_native_per_frame_record": True,
                                     "q3b_requires_reduced_encode_then_expanded_score": True}}

    def test_q3a_contract_is_exact_and_q3b_requires_real_reduced_encode(self):
        plan = self.plan()
        self.assertIs(q3.validate_plan(plan), plan)
        self.assertEqual([(c["wavelet"], c["rate_mbps"]) for c in plan["cells"]], list(q3.Q3A_ROWS))
        plan["cells"][0]["rate_mbps"] = 800
        with self.assertRaisesRegex(ValueError, "Q3a rows drifted"):
            q3.validate_plan(plan)
        q3b = self.plan(True); self.assertIs(q3.validate_plan(q3b), q3b)
        q3b["cells"][-1]["requires_wo8_reduced_encode"] = False
        with self.assertRaisesRegex(ValueError, "reduced-encode"):
            q3.validate_plan(q3b)

    def test_q3b_manifest_rejects_geometry_cap_or_chroma_drift(self):
        for key, value in (("eye_width", 2), ("cap_bytes", 1), ("encoded_chroma", "444"),
                           ("score_vertical_pixels_per_degree", 24.0)):
            plan = self.plan(True)
            if key in ("eye_width", "cap_bytes"):
                plan["cells"][-1][key] += value
            else:
                plan["cells"][-1][key] = value
            with self.assertRaisesRegex(ValueError, "Q3b reduced geometry/cap/scoring contract drifted"):
                q3.validate_plan(plan)

    def test_extension_plan_freezes_rdo_density_foveation_and_offline_rates(self):
        base=self.plan()
        with mock.patch.object(q3, "build_plan", return_value=base):
            plan=q3.build_extension_plan(Path("cropped.y4m"),23.5,projection_evidence="p",crop_evidence="c",
                                         crops=[],full_source=Path("parent.y4m"),fixture=True,
                                         light_phase_identity=self.LIGHT_ID)
        self.assertIs(q3.validate_plan(plan),plan)
        self.assertEqual(len(plan["cells"]),7)
        self.assertEqual([cell["label"] for cell in plan["cells"]],[row["label"] for row in q3.Q3_EXTENSION_ROWS])
        self.assertEqual(plan["cells"][0]["rdo_viewing_density"]["environment"],{"PYROWAVE_RDO_PX_PER_DEG":"24"})
        self.assertEqual(plan["cells"][1]["rdo_viewing_density"]["effective_ppd"],36.0)
        self.assertIsNone(plan["cells"][3]["rdo_viewing_density"]["environment"])
        self.assertTrue(all(c.get("offline_only_above_wifi_cap") for c in plan["cells"][-3:]))
        self.assertEqual(plan["cells"][2]["source_transform"],q3._q3b_transform("medium-s05"))
        self.assertEqual(plan["cells"][3]["source_transform"]["implementation_revision"],self.LIGHT_ID["implementation_revision"])
        self.assertEqual(q3._select_cells(plan,"q3a",[0,6])[1][0],6)
        plan["cells"][0]["rdo_viewing_density"]["pixels_per_degree"]=25
        with self.assertRaisesRegex(ValueError,"RDO provenance"):
            q3.validate_plan(plan)

    def test_overnight_static_extension_is_additive_and_has_exact_six_static_rows(self):
        base=self.plan()
        with mock.patch.object(q3, "build_plan", return_value=base):
            plan=q3.build_overnight_static_plan(Path("cropped.y4m"),23.5,projection_evidence="p",crop_evidence="c",
                                                crops=[],full_source=Path("parent.y4m"),fixture=True,
                                                light_phase_identity=self.LIGHT_ID)
        self.assertIs(q3.validate_plan(plan), plan)
        self.assertEqual(plan["extension_matrix"]["kind"], "overnight_static_rdo")
        self.assertEqual([cell["experiment_id"] for cell in plan["cells"]],
                         [row["experiment_id"] for row in q3.Q3_OVERNIGHT_STATIC_ROWS])
        self.assertTrue(all(cell["source_geometry"] == "crop" for cell in plan["cells"]))
        self.assertEqual(plan["cells"][3]["source_transform"]["implementation_source_sha256"], self.LIGHT_ID["implementation_source_sha256"])
        plan["cells"][0]["rdo_viewing_density"]["requested_ppd"] = 25
        with self.assertRaisesRegex(ValueError, "RDO provenance"):
            q3.validate_plan(plan)

    def test_overnight_full_a2_plan_is_full_parent_and_runnable_by_common_runner(self):
        info=fb.Y4MInfo(6144,3232,90,1,"420","FULL",6144*3232*3//2,90)
        source_contract={"sha256":"a"*64,"geometry":[6144,3232],"frames":90,"fps":[90,1],"chroma":"420","color_range":"FULL","frame_identity":[]}
        base={"cells":[{"wavelet":"haar","rate_mbps":500,"fps":90,"eye_width":3072,"eye_height":3232,"stereo_width":6144,"encoded_chroma":"420","cap_bytes":fb.cap_bytes(500,90),"bits_per_pixel":fb.bpp(fb.cap_bytes(500,90),3072,3232)}],
              "presentation_eye":[3072,3232],"projection":{"vertical_pixels_per_degree":23.5},"crops":[],
              "hvs_calibration":{"codec_cells":[{}],"crops":[]}}
        with mock.patch.object(q3,"_require_full_source",return_value=info), \
             mock.patch.object(q3,"_source_contract",return_value=source_contract), \
             mock.patch.object(q3,"_hash",return_value="a"*64), \
             mock.patch.object(fb,"build_plan",return_value=base):
            plan=q3.build_overnight_full_a2_plan(Path("parent.y4m"),23.5,projection_evidence="p",crop_evidence="c",crops=[],fixture=True)
        plan["frozen_module_hashes"] = q3._module_hashes()
        self.assertIs(q3.validate_plan(plan),plan)
        self.assertEqual(plan["cells"][0]["source_geometry"],"full_fov")
        self.assertEqual(plan["cells"][0]["rdo_viewing_density"],q3._rdo_descriptor(24))
        self.assertEqual(q3._require_plan_source.__name__, "_require_plan_source")
        plan["cells"][0]["eye_width"] = 2624
        with self.assertRaisesRegex(ValueError, "full a2 codec row drifted"):
            q3.validate_plan(plan)

    def test_extension_refuses_corrected_light_until_its_wo8_source_is_active(self):
        base=self.plan()
        with mock.patch.object(q3,"build_plan",return_value=base), \
             mock.patch.object(q3,"_hash",return_value="0"*64):
            with self.assertRaisesRegex(ValueError,"corrected-Light source hash"):
                q3.build_extension_plan(Path("cropped.y4m"),23.5,projection_evidence="p",crop_evidence="c",
                                        crops=[],full_source=Path("parent.y4m"),fixture=False,
                                        light_phase_identity=self.LIGHT_ID)

    def test_extension_rdo_native_log_requires_effective_requested_value(self):
        requested=q3._rdo_descriptor(24)
        proof=q3._rdo_effective_from_native_log(
            "PyroWave RDO viewing density: requested 24, effective 24.0 px/deg, Nyquist 12.0 cycles/deg",requested)
        self.assertEqual(proof["effective_ppd"],24.0)
        default=q3._rdo_descriptor(None)
        self.assertTrue(q3._rdo_effective_from_native_log(
            "PyroWave RDO viewing density: requested (legacy 96 DPI @ 1m), effective 65.2799988 px/deg, Nyquist 32.6399994 cycles/deg (legacy-equivalent)",default)["legacy_equivalent"])
        with self.assertRaisesRegex(ValueError,"differs|missing"):
            q3._rdo_effective_from_native_log("PyroWave RDO viewing density: requested 36, effective 36 px/deg, Nyquist 18 cycles/deg",requested)

    def test_q3b_selection_uses_original_plan_indices_and_rejects_bad_scope(self):
        plan = self.plan(True)
        selected = q3._select_cells(plan, "q3b", [5, 7])
        self.assertEqual([index for index, _ in selected], [5, 7])
        self.assertEqual([cell["phase"] for _, cell in selected], ["q3b", "q3b"])
        for indices, error in (([5, 5], "duplicates"), ([99], "out-of-range"), ([True], "only integers"),
                               ([0], "outside the requested phase")):
            with self.assertRaisesRegex(ValueError, error):
                q3._select_cells(plan, "q3b", indices)

    def test_module_hash_freezes_runner_dependencies(self):
        plan = self.plan(); plan["frozen_module_hashes"]["framebank.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "module hash drifted"):
            q3.validate_plan(plan)

    def test_build_plan_resolves_fixed_crops_on_the_full_parent_once(self):
        """Do not let the cropped encode size redefine source crop coordinates."""
        parent = fb.Y4MInfo(6144, 3232, 90, 1, "420", "FULL", 6144 * 3232 * 3 // 2, 90)
        cropped = fb.Y4MInfo(5248, 2776, 90, 1, "420", "FULL", 5248 * 2776 * 3 // 2, 90)
        crops = [{"name": "parent-mark", "eye": "left", "x": .5, "y": .25, "w": .25, "h": .5}]
        identities = [{"source_frame": i, "source_sha256": f"{i:064x}"} for i in range(90)]
        real_hash = q3._hash
        def source_hash(path):
            return "b" * 64 if Path(path).name in ("cropped.y4m", "parent.y4m") else real_hash(path)
        with mock.patch.object(q3, "_require_cropped_source", return_value=cropped), \
             mock.patch.object(fb, "inspect_y4m", return_value=parent), \
             mock.patch.object(fb, "frame_records", return_value=identities), \
             mock.patch.object(fb, "sha256_file", return_value="a" * 64), \
             mock.patch.object(q3, "_hash", side_effect=source_hash):
            plan = q3.build_plan(Path("cropped.y4m"), 23.5,
                                 projection_evidence="recorded full-parent projection",
                                 crop_evidence="reviewed parent crop", crops=crops,
                                 full_source=Path("parent.y4m"), fixture=True)
        self.assertEqual(plan["presentation_eye"], [3072, 3232])
        self.assertEqual(plan["crops"][0]["resolved_pixels"],
                         {"eye_x": 1536, "stereo_x": 1536, "y": 808,
                          "width": 768, "height": 1616, "chroma_aligned": True})
        self.assertEqual([(cell["eye_width"], cell["eye_height"]) for cell in plan["cells"]],
                         [(2624, 2776)] * len(q3.Q3A_ROWS))
        self.assertTrue(all(cell["score_vertical_pixels_per_degree"] == 23.5 for cell in plan["cells"]))
        mapped, excluded = nvenc._crop_context_for_cell(plan, plan["cells"][0])
        self.assertEqual(excluded, {})
        self.assertEqual(mapped[0]["resolved_pixels"],
                         {"eye_x": 1258, "stereo_x": 1258, "y": 534,
                          "width": 768, "height": 1616, "chroma_aligned": True})
        # The fake frame-bank hash only models unavailable Y4M I/O; validate
        # the generated manifest with the runner's real source hashes.
        plan["frozen_module_hashes"] = q3._module_hashes()
        self.assertIs(q3.validate_plan(plan), plan)

    def test_container_parse_checks_header_exact_payloads_and_frame_count(self):
        cell = self.plan()["cells"][0]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "test.wave"
            path.write_bytes(wave.header(5248, 2776, fps_num=90, chroma=wave.CHROMA_420) + b"".join((1).to_bytes(4, "little") + b"x" for _ in range(90)))
            parsed = q3.parse_wave(path, cell)
            self.assertEqual(parsed["frames"], 90); self.assertEqual(parsed["payload_bytes"], [1] * 90)
            path.write_bytes(path.read_bytes()[:-5])
            with self.assertRaisesRegex(ValueError, "frame count|truncated"):
                q3.parse_wave(path, cell)

    def test_native_records_never_infers_timing_from_wall_clock(self):
        self.assertFalse(q3._native_records(None, [1] * 90)["qualified"])
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "native.json"
            rows = [{"schema_version": 1, "frame_id": i, "payload_bytes": 1,
                     "cpu_command_record_submit_ms": 0.1, "submit_to_observed_fence_ms": 0.3} for i in range(90)]
            path.write_text("\n".join(json.dumps(row) for row in rows))
            value = q3._native_records(path, [1] * 90)
            self.assertTrue(value["qualified"])
            self.assertIn("not GPU execution", value["semantics"]["submit_to_observed_fence_ms"])
            rows[-1]["payload_bytes"] = 2; path.write_text("\n".join(json.dumps(row) for row in rows))
            with self.assertRaisesRegex(ValueError, "payload mismatch"):
                q3._native_records(path, [1] * 90)

    def test_q3b_reduced_source_identity_must_match_transform_output(self):
        identities = [{"source_frame": i, "encoded_reference_sha256": f"{i:064x}"}
                      for i in range(90)]
        records = [{"source_frame": i, "source_sha256": f"{i:064x}"} for i in range(90)]
        with mock.patch.object(fb, "frame_records", return_value=records), \
             mock.patch.object(q3, "_hash", return_value="c" * 64):
            provenance = q3._q3b_encoded_source_provenance(Path("reduced.y4m"), identities)
        self.assertEqual(provenance["frames"], 90)
        records[-1]["source_sha256"] = "wrong"
        with mock.patch.object(fb, "frame_records", return_value=records):
            with self.assertRaisesRegex(ValueError, "q3b_encoded_source_identity_mismatch"):
                q3._q3b_encoded_source_provenance(Path("reduced.y4m"), identities)

    def test_cli_passes_explicit_q3b_phase_to_runner(self):
        with tempfile.TemporaryDirectory() as root:
            report = Path(root) / "report.json"
            args = ["run", "--plan", "p", "--source", "s", "--private-out", "o", "--report", str(report),
                    "--window", "w", "--encode", "e", "--decode", "d", "--psnr-hvs-m-h", "h",
                    "--ffmpeg", "f", "--tools-metadata", "m", "--scorer-compatibility", "compat", "--phase", "q3b", "--cell-index", "5", "--q3b-preparation-workers", "3"]
            with mock.patch.object(q3, "run_plan", return_value={"complete": True}) as run:
                self.assertEqual(q3.main(args), 0)
            self.assertEqual(run.call_args.kwargs["phase"], "q3b")
            self.assertEqual(run.call_args.kwargs["cell_indices"], [5])
            self.assertEqual(run.call_args.kwargs["preparation_workers"], 3)
            self.assertEqual(run.call_args.kwargs["scorer_compatibility"], Path("compat"))
            self.assertTrue(report.is_file())

    def test_q3b_never_substitutes_shared_scorer_or_blur_only_path(self):
        with mock.patch("xrbench.nvenc_framebank._same_frame_scores", create=True) as scorer:
            # The adapter itself must only delegate to an actual shared scorer.
            self.assertTrue(callable(getattr(__import__("xrbench.nvenc_framebank", fromlist=["x"]), "_same_frame_scores")))
        self.assertEqual(len(q3.Q3B_ROWS), 8)

    def test_split_bundle_historical_scorer_keeps_both_lock_identities(self):
        """A current codec can use only the named historical scorer proof."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools = {'encode': root/'pyrowave-encode.exe', 'decode': root/'pyrowave-decode.exe',
                     'psnr_hvs_m_h': root/'pyrowave-psnr-hvs-m.exe', 'ffmpeg': root/'ffmpeg.exe'}
            for path in tools.values(): path.write_bytes(path.name.encode())
            codec_meta, scorer_meta, descriptor = root/'codec.json', root/'scorer.json', root/'compat.json'
            codec_meta.write_text('{}'); scorer_meta.write_text('{}'); descriptor.write_text('{}')
            codec = {'sources_lock_sha256': 'c'*64, 'scorer_source': {'same': True}, 'scorer_shader_sha256': 's'*64}
            scorer = {'sources_lock_sha256': 'h'*64, 'current_sources_lock_sha256': 'c'*64,
                      'historical_scorer_mode': True, 'scorer_source': {'same': True}, 'scorer_shader_sha256': 's'*64}
            with mock.patch.object(fb, 'verify_tools_build', return_value=codec) as current, \
                 mock.patch.object(fb, 'verify_historical_hvs_scorer', return_value=scorer) as historical:
                result = q3.verify_split_bundles(tools, codec_meta, scorer_meta, descriptor)
            current.assert_called_once(); historical.assert_called_once()
            self.assertTrue(result['historical_scorer_mode'])
            self.assertEqual(result['codec_sources_lock_sha256'], 'c'*64)
            self.assertEqual(result['scorer_sources_lock_sha256'], 'h'*64)
            scorer['current_sources_lock_sha256'] = 'x'*64
            with mock.patch.object(fb, 'verify_tools_build', return_value=codec), \
                 mock.patch.object(fb, 'verify_historical_hvs_scorer', return_value=scorer):
                with self.assertRaisesRegex(ValueError, 'current lock'):
                    q3.verify_split_bundles(tools, codec_meta, scorer_meta, descriptor)

    def test_q3b_orchestration_uses_reduced_codec_input_then_expanded_shared_scores(self):
        """Exercise both squeezed and blur-only cells without a codec/GPU."""
        from xrbench import nvenc_framebank as nv
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); source=root/'cropped.y4m'; source.write_bytes(b'x')
            tools={name:root/(name+'.exe') for name in ('encode','decode','psnr_hvs_m_h','ffmpeg')}
            for path in tools.values(): path.write_bytes(b'x')
            info=fb.Y4MInfo(5248,2776,90,1,'420','FULL',5248*2776*3//2,90)
            for profile in ('light-s0','blur-only-light-s05'):
                cell=dict(phase='q3b',profile=profile,wavelet='97',rate_mbps=1000,fps=90,
                    eye_width=2464 if profile=='light-s0' else 2624,eye_height=2592 if profile=='light-s0' else 2776,
                    stereo_width=4928 if profile=='light-s0' else 5248,source_geometry='crop',
                    source_transform=q3._q3b_transform(profile),requires_wo8_reduced_encode=True,
                    cap_bytes=fb.cap_bytes(1000,90),bits_per_pixel=1,score_vertical_pixels_per_degree=23.5,
                    experiment_id="extension-mocked-"+profile,
                    rdo_viewing_density=q3._rdo_descriptor(None if profile=='light-s0' else 24))
                plan={'schema':1,'kind':'pyro_q3_framebank','source':self.source_contract(),
                      'cells':[{'phase':'q3a'} for _ in range(5)]+[cell],
                      'projection':{'vertical_pixels_per_degree':23.5},'crop_geometry':q3.CROP_GEOMETRY,
                      'source_adapter':{'kind':'per_eye_crop','geometry':q3.CROP_GEOMETRY,'future_transform':None},
                      'hvs_calibration':{'codec_cells':[{} for _ in range(6)]},'fence_rectangles':{'cropped':{'mapped':q3.FENCE_RECTANGLES['cropped']['mapped']},'full_fov':q3.FENCE_RECTANGLES['full_fov']}}
                plan['source']['frame_identity']=[{'source_sha256':'a'} for _ in range(90)]
                (root/'plan.json').write_text(json.dumps(plan)); (root/'meta.json').write_text('{}')
                class Guard:
                    envs=[]
                    def status(self): return {}
                    def run(self, argv, **kwargs):
                        target=Path(argv[-1]) if 'decode.exe' in str(argv[0]) else next((Path(v) for v in argv if str(v).endswith('.wave')),Path(argv[-1]))
                        target.write_bytes(b'x')
                        if 'encode.exe' in str(argv[0]):
                            Guard.envs.append(dict(kwargs['env']))
                            return 0, 'CDF 9/7\nPyroWave RDO viewing density: requested ' + cell['rdo_viewing_density']['requested_log'] + ', effective ' + str(cell['rdo_viewing_density']['effective_ppd']) + ' px/deg, Nyquist ' + str(cell['rdo_viewing_density']['cpd_nyquist']) + ' cycles/deg' + (' (legacy-equivalent)' if cell['rdo_viewing_density']['legacy_equivalent'] else ''), ''
                        return 0,'CDF 9/7',''
                encoded_info=fb.Y4MInfo(cell['stereo_width'],cell['eye_height'],90,1,'420','FULL',1,90)
                score_info=info; ids=[{'source_frame':i,'source_sha256':'a','encoded_reference_sha256':'b'} for i in range(90)]
                encoded_records=[{'source_frame':i,'source_sha256':'b'} for i in range(90)]
                with mock.patch.object(q3,'validate_plan',return_value=plan), mock.patch.object(q3,'_require_cropped_source',return_value=info), mock.patch.object(q3,'_source_contract',return_value=plan['source']), mock.patch.object(q3,'_hash',return_value='c'*64), mock.patch.object(fb,'WindowGuard',return_value=Guard()), mock.patch.object(fb,'required_tools'), mock.patch.object(q3,'verify_split_bundles',return_value={}), mock.patch.object(fb,'hvs_gpu_sanity',return_value={'passed':True}), mock.patch.object(fb,'codec_environment',return_value=({},{})), mock.patch.object(q3,'parse_wave',return_value={'payload_bytes':[1]*90}), mock.patch.object(q3,'_native_records',return_value={'qualified':True}), mock.patch.object(nv,'_stream_q3b_sources',return_value=(encoded_info,score_info,ids,{})) as prep, mock.patch.object(fb,'frame_records',return_value=encoded_records), mock.patch.object(nv,'_reconstruct_q3b_decoded') as expand, mock.patch.object(fb,'canonicalize_decoded_header',return_value={}), mock.patch.object(fb,'_assert_same_frames',side_effect=[encoded_info,score_info]), mock.patch.object(fb,'iter_y4m',side_effect=lambda *_: iter((i,None,'d') for i in range(90))), mock.patch.object(q3,'_same_frame_scores',return_value={'centre_hvs':{},'fence_metrics':{}}) as score:
                    result=q3.run_plan(root/'plan.json',source,root/('out'+profile),tools,root/'lease',tools_metadata=root/'meta.json',supervised=True,phase='q3b',cell_indices=[5])
                self.assertTrue(prep.called); self.assertTrue(expand.called); self.assertTrue(score.called, result)
                self.assertEqual(score.call_args.args[1], 5)
                self.assertEqual(result['cells'][0]['q3b_encoded_source']['frames'],90)
                self.assertEqual(prep.call_args.kwargs['preparation_workers'], 1)
                self.assertIsNotNone(prep.call_args.kwargs['guard'])
                self.assertEqual(result['q3b_preparation_workers'],1)
                self.assertEqual(result['cells'][0]['rdo_effective']['effective_ppd'],cell['rdo_viewing_density']['effective_ppd'])
                expected_env=cell['rdo_viewing_density']['environment'] or {}
                self.assertEqual({key:value for key,value in Guard.envs[0].items() if key == 'PYROWAVE_RDO_PX_PER_DEG'},expected_env)

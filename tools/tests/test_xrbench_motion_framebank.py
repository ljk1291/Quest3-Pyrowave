"""CPU contracts for the separate synthetic-motion adapter; no codec is invoked."""
from pathlib import Path
import sys
import json
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xrbench import framebank as fb
from xrbench import motion_framebank as motion
from xrbench import pyro_q3_framebank as pyro

class MotionFramebankTests(unittest.TestCase):
    def plan(self):
        cells=[]
        for spec in motion.MOTION_ROWS:
            cell={**spec,"phase":"motion","fps":90,"source_geometry":"moving_crop","encoded_chroma":"420",
                  "cap_bytes":fb.cap_bytes(spec["rate_mbps"],90),"score_vertical_pixels_per_degree":23.5,
                  "tracked_score":"source_space_fence_residual","quality_windows_one_based":[[1,90],[10,89]]}
            if spec["runner"] == "nvenc":
                transform=spec.get("source_transform")
                if transform:
                    from xrbench.foveation import FoveationConfig, encoded_size
                    ew,eh=encoded_size(2624,2776,FoveationConfig(transform["profile"],transform["softness"],transform["blur_only"]))
                else: ew,eh=2624,2776
                cell.update(eye_width=ew,eye_height=eh,stereo_width=ew*2)
                cell["nvenc_profile"] = motion.nvenc.profile(spec["codec"],spec["rate_mbps"],90,preset=spec["preset"],spatial_aq=False)
            else:
                from xrbench.foveation import FoveationConfig, encoded_size
                transform=spec["source_transform"]; ew,eh=encoded_size(2624,2776,FoveationConfig(transform["profile"],transform["softness"],transform["blur_only"]))
                cell.update(eye_width=ew,eye_height=eh,stereo_width=ew*2,bits_per_pixel=fb.bpp(cell["cap_bytes"],ew,eh))
                cell["rdo_viewing_density"] = pyro._rdo_descriptor(spec["rdo_px_per_deg"])
                cell["requires_wo8_reduced_encode"] = True
            cells.append(cell)
        cells.append({"experiment_id":"motion_view_haar_full_parent_500_default_rdo","runner":"reuse_only"})
        return {"schema":1,"kind":"synthetic_motion_framebank","source":{"sha256":"a"*64,"geometry":[5248,2776],"frames":90,"fps":[90,1],"chroma":"420","color_range":"FULL","frame_identity":[]},
                "motion_contract":{"manifest_sha256":"b"*64,"motion_input_sha256":"a"*64,"synthetic_not_actual_vr_tracking":True,"score_windows":{"spatial_one_based":[1,90],"temporal_one_based":[10,89],"temporal_pairs":79}},
                "projection":{"vertical_pixels_per_degree":23.5,"horizontal_pixels_per_degree":24.2},"frozen_module_hashes":motion._module_hashes(),"cells":cells,
                "prohibitions":["no optical or Quest performance claim","no whole-image HVS rank against post-decode full-parent diagnostic","no replacement of pre-encode moving crop by moving-view extraction"]}

    def test_plan_separates_three_encodes_from_reuse_only_diagnostic(self):
        plan=self.plan(); self.assertIs(motion.validate_plan(plan),plan)
        self.assertEqual([c["experiment_id"] for c in plan["cells"][:-1]],[x["experiment_id"] for x in motion.MOTION_ROWS])
        self.assertEqual(plan["cells"][-1]["runner"],"reuse_only")
        plan["cells"][0]["rate_mbps"]=500
        with self.assertRaisesRegex(ValueError,"motion codec row drifted"):
            motion.validate_plan(plan)
        plan=self.plan(); plan["cells"][0]["nvenc_profile"]["preset"]="p4"
        with self.assertRaisesRegex(ValueError,"NVENC profile drifted"):
            motion.validate_plan(plan)

    def test_command_api_pins_stock_profile_and_pyro_cap_without_execution(self):
        stock={"cell":self.plan()["cells"][0],"encode_source":Path("motion.y4m")}
        stock["cell"]["identity_count"] = 90
        cmd=motion.encode_command(stock,{"ffmpeg":"ffmpeg.exe"},Path("out.h264"))
        self.assertIn("h264_nvenc",cmd); self.assertIn("700M",cmd)
        pyro_prepared={"cell":self.plan()["cells"][2],"encode_source":Path("motion.y4m")}
        command=motion.encode_command(pyro_prepared,{"encode":"pyrowave-encode.exe"},Path("out.wave"))
        self.assertEqual(command[-2],"--timing-jsonl")
        self.assertEqual(command[3],str(fb.cap_bytes(1000,90)))
        with self.assertRaisesRegex(ValueError,"no encode command"):
            motion.encode_command({"cell":self.plan()["cells"][-1],"reuse_only":True},{},Path("unused"))

    def test_disk_preflight_is_conservative_and_fail_closed(self):
        cell=self.plan()["cells"][2]; cell.update(eye_width=2112,eye_height=2240,stereo_width=4224)
        usage=type("Usage",(),{"free":1,"total":2,"used":1})()
        with mock.patch.object(motion.shutil,"disk_usage",return_value=usage):
            with self.assertRaisesRegex(RuntimeError,"disk_preflight"):
                motion.disk_preflight(Path("C:/temp/cell"),cell)
        usage.free=100*1024**3
        with mock.patch.object(motion.shutil,"disk_usage",return_value=usage):
            report=motion.disk_preflight(Path("C:/temp/cell"),cell)
        self.assertTrue(report["passes"]); self.assertTrue(report["source_is_reused"])

    def test_manifest_contract_rejects_step_eye_and_fence_drift(self):
        rows=[]
        for index in range(90):
            phase=index%40; d=-160+16*phase if phase <= 20 else 160-16*(phase-20)
            rows.append({"frame_one_based":index+1,"displacement_x_pixels":d,
                         "left_source_window":{"x":278+d,"y":274,"width":2624,"height":2776},
                         "right_source_window":{"x":170+d,"y":274,"width":2624,"height":2776},
                         "tracked_fence_output":{"x":1462-d,"y":1036,"width":240,"height":274},
                         "tracked_fence_source":{"eye":"left","x":1740,"y":1310,"width":240,"height":274}})
        doc={"kind":"synthetic_integer_pixel_pingpong_motion","synthetic_not_actual_vr_tracking":True,
             "motion_header":{"width":5248,"height":2776,"frames":90,"fps":[90,1],"chroma":"420","color_range":"FULL"},
             "score_windows":{"spatial_one_based":[1,90],"temporal_one_based":[10,89],"temporal_pairs":79},"frames":rows}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"manifest.json"; path.write_text(json.dumps(doc))
            self.assertEqual(motion._load_contract(path)["document"]["frames"][0]["frame_one_based"],1)
            doc["frames"][1]["displacement_x_pixels"] = -160; path.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"16-pixel step"):
                motion._load_contract(path)

if __name__ == "__main__": unittest.main()


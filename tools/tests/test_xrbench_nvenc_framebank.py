"""CPU-only contract tests for the offline NVENC frame-bank adapter."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xrbench import framebank as fb
from xrbench import nvenc_framebank as nf


class NvencFramebankTests(unittest.TestCase):
    def source(self, root):
        path = Path(root) / "source.y4m"
        info = fb.Y4MInfo(4, 4, 90, 1, "420", "FULL", 24, 90)
        frame = [np.zeros((4, 4), np.uint8), np.full((2, 2), 128, np.uint8), np.full((2, 2), 128, np.uint8)]
        fb.write_y4m(path, info, [frame] * 90)
        return path

    def test_low_delay_cbr_profile_is_explicit_and_one_frame_vbv(self):
        for codec in nf.CODECS:
            value = nf.profile(codec, 1000)
            self.assertEqual(value["rate_control"], "cbr")
            self.assertEqual(value["b_frames"], 0)
            self.assertEqual(value["lookahead_frames"], 0)
            self.assertEqual(value["vbv_bits"], 12_222_223)
            self.assertEqual(value["preset"], "p4")
            self.assertEqual(value["source_plane_contract"], "C420jpeg_FULL")
            args = value["ffmpeg_arguments"]
            self.assertEqual(args[args.index("-rc") + 1], "cbr")
            self.assertEqual(args[args.index("-bf") + 1], "0")
            self.assertEqual(args[args.index("-bufsize") + 1], "12222223")
            self.assertIn("offline_nvenc_proxy", value["comparison_scope"])
        with self.assertRaises(ValueError): nf.profile("h264", 500)

    def test_frozen_plan_reuses_framebank_geometry_crops_and_calibration(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.source(root)
            crop = {"name":"center","eye":"left","x":0,"y":0,"w":1,"h":1}
            plan = nf.build_plan(source, 23.5, projection_evidence="test projection",
                                 crop_evidence="test crop", crops=[crop], fixture=True,
                                 rates_mbps=(200,), geometries=((2, 4),), codecs=nf.CODECS, display_eye=(2, 4))
            self.assertEqual(plan["kind"], "nvenc_frame_bank")
            self.assertEqual(plan["cells"][0]["codec"], "hevc")
            self.assertEqual(plan["cells"][0]["nvenc_profile"], nf.profile("hevc", 200))
            self.assertEqual(len(plan["cells"]), 2)
            self.assertEqual(len(plan["hvs_calibration"]["codec_cells"]), 2)
            self.assertEqual(plan["hvs_calibration"]["display"]["vertical_pixels_per_degree"], 23.5)
            self.assertEqual(plan["crops"][0]["resolved_pixels"]["width"], 2)
            self.assertIs(nf.validate_plan(plan), plan)
            plan["cells"][0]["nvenc_profile"]["b_frames"] = 1
            with self.assertRaisesRegex(ValueError, "profile drifted"):
                nf.validate_plan(plan)

    def test_default_matrix_calibration_is_codec_major_and_cell_aligned(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.source(root); crop = {"name":"center","eye":"left","x":0,"y":0,"w":1,"h":1}
            plan = nf.build_plan(source, 23.5, projection_evidence="p", crop_evidence="c", fixture=True,
                                 rates_mbps=nf.RATES_MBPS, geometries=((2, 4), (4, 4)), codecs=nf.CODECS,
                                 crops=[crop], display_eye=(2, 4))
            self.assertEqual(len(plan["cells"]), 16)
            self.assertEqual(len(plan["hvs_calibration"]["codec_cells"]), 16)
            self.assertEqual([cell["codec"] for cell in plan["cells"][:8]], ["hevc"] * 8)
            self.assertEqual([cell["codec"] for cell in plan["cells"][8:]], ["av1"] * 8)
            self.assertEqual(plan["hvs_calibration"]["codec_cells"][:8], plan["hvs_calibration"]["codec_cells"][8:])
            nf.validate_plan(plan)

    def test_bitstream_probe_accepts_unknown_metadata_and_rejects_b_frames_or_count_drift(self):
        cell = {"codec":"hevc", "stereo_width":6144, "eye_height":3232, "fps":90}
        valid = {"streams":[{"codec_name":"hevc", "width":6144, "height":3232,
                 "pix_fmt":"yuv420p", "color_range":"unknown", "avg_frame_rate":"0/0",
                 "chroma_location":"left", "color_space":"unknown", "color_primaries":"unknown",
                 "color_transfer":"unknown", "r_frame_rate":"0/0", "nb_read_frames":"90"}],
                 "frames":[{"pict_type":"I", "width":6144, "height":3232, "pix_fmt":"yuv420p"}] +
                 [{"pict_type":"P", "width":6144, "height":3232, "pix_fmt":"yuv420p"}] * 89}
        result = nf.validate_probe(valid, cell, 90)
        self.assertEqual(result["picture_types"], {"I":1, "P":89})
        self.assertEqual(result["ffprobe_observed_metadata"]["avg_frame_rate"], "0/0")
        self.assertFalse(result["bitstream_timing_confirmed"])
        yuvj = json.loads(json.dumps(valid)); yuvj["streams"][0]["pix_fmt"] = "yuvj420p"
        for frame in yuvj["frames"]: frame["pix_fmt"] = "yuvj420p"
        self.assertEqual(nf.validate_probe(yuvj, cell, 90)["pix_fmt"], "yuvj420p")
        ten_bit = json.loads(json.dumps(valid)); ten_bit["streams"][0]["pix_fmt"] = "p010le"
        for frame in ten_bit["frames"]: frame["pix_fmt"] = "p010le"
        with self.assertRaisesRegex(ValueError, "8-bit 4:2:0"):
            nf.validate_probe(ten_bit, cell, 90)
        for mutation, message in ((lambda v: v["streams"][0].update(color_range="tv"), "range contradicts"),
                                  (lambda v: v["frames"].__setitem__(3, {"pict_type":"B", "width":6144, "height":3232, "pix_fmt":"yuv420p"}), "B or unknown"),
                                  (lambda v: v["streams"][0].update(nb_read_frames="89"), "frame count")):
            candidate = json.loads(json.dumps(valid)); mutation(candidate)
            with self.assertRaisesRegex(ValueError, message):
                nf.validate_probe(candidate, cell, 90)

    def test_commands_pin_raw_codec_and_no_implicit_decode_format(self):
        cell = {"codec":"av1", "identity_count":90, "nvenc_profile":nf.profile("av1", 800)}
        encoded = nf.encode_command("ffmpeg", Path("ref.y4m"), Path("out.av1"), cell)
        self.assertEqual(encoded[-2:], ["obu", "out.av1"])
        self.assertEqual(encoded[encoded.index("-frames:v") + 1], "90")
        decoded = nf.decode_command("ffmpeg", Path("out.av1"), Path("decoded.y4m"), 90, "yuv420p")
        self.assertEqual(decoded[decoded.index("-pix_fmt") + 1], "+yuv420p")
        self.assertEqual(decoded[decoded.index("-fps_mode") + 1], "passthrough")
        self.assertEqual(decoded[decoded.index("-f") + 1], "rawvideo")
        decoded_j = nf.decode_command("ffmpeg", Path("out.hevc"), Path("decoded.raw"), 90, "yuvj420p")
        self.assertEqual(decoded_j[decoded_j.index("-pix_fmt") + 1], "+yuvj420p")
        probe = nf.probe_command("ffprobe", Path("out.av1"), Path("probe.json"))
        self.assertEqual(probe[probe.index("-o") + 1], "probe.json")

    def test_y4m_output_must_keep_jpeg_siting_and_full_range(self):
        with tempfile.TemporaryDirectory() as root:
            good = Path(root) / "good.y4m"
            good.write_bytes(b"YUV4MPEG2 W4 H4 F90:1 Ip A1:1 C420jpeg XCOLORRANGE=FULL\n")
            self.assertEqual(nf._require_jpeg_full_y4m(good)["chroma"], "C420jpeg")
            bad = Path(root) / "bad.y4m"
            bad.write_bytes(b"YUV4MPEG2 W4 H4 F90:1 Ip A1:1 C420mpeg2 XCOLORRANGE=FULL\n")
            with self.assertRaisesRegex(ValueError, "chroma_or_range"):
                nf._require_jpeg_full_y4m(bad)
            with self.assertRaisesRegex(ValueError, "chroma_or_range"):
                nf.build_plan(bad, 23.5, projection_evidence="p", crop_evidence="c",
                              fixture=True, rates_mbps=(200,), geometries=((2, 4),),
                              display_eye=(2, 4))

    def test_raw_wrapper_rejects_wrong_byte_count_and_preserves_frame_payloads(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); info = fb.Y4MInfo(4, 4, 90, 1, "420", "FULL", 24, 2)
            raw = root / "decoded.raw"; payload = bytes(range(24)) + bytes(range(24, 48)); raw.write_bytes(payload)
            wrapped = root / "decoded.y4m"; record = nf.wrap_raw_payload(raw, info, wrapped)
            self.assertTrue(record["byte_identical"])
            self.assertEqual(record["frame_payload_sha256"], [
                __import__("hashlib").sha256(payload[:24]).hexdigest(), __import__("hashlib").sha256(payload[24:]).hexdigest()])
            self.assertEqual(fb.inspect_y4m(wrapped).frames, 2)
            raw.write_bytes(payload[:-1])
            with self.assertRaisesRegex(ValueError, "byte_count"):
                nf.wrap_raw_payload(raw, info, root / "bad.y4m")

    def test_mocked_runner_wraps_raw_planes_and_keeps_observed_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); source = self.source(root)
            crop = {"name":"center","eye":"left","x":0,"y":0,"w":1,"h":1}
            plan = nf.build_plan(source, 23.5, projection_evidence="p", crop_evidence="c", fixture=True,
                                 rates_mbps=(200,), geometries=((2, 4),), codecs=("hevc",), crops=[crop], display_eye=(2, 4))
            plan_path = root / "plan.json"; plan_path.write_text(json.dumps(plan))
            output = root / "out"; metadata = root / "FRAMEBANK-TOOLS-BUILD-METADATA.json"; metadata.write_text("{}")
            observed = {"streams":[{"codec_name":"hevc", "width":4, "height":4, "pix_fmt":"yuv420p",
                "color_range":"unknown", "chroma_location":"left", "color_space":"unknown", "color_primaries":"unknown",
                "color_transfer":"unknown", "avg_frame_rate":"0/0", "r_frame_rate":"0/0", "nb_read_frames":"90"}],
                "frames":[{"pict_type":"I", "width":4, "height":4, "pix_fmt":"yuv420p"}] +
                [{"pict_type":"P", "width":4, "height":4, "pix_fmt":"yuv420p"}] * 89}
            class Guard:
                def status(self): return {}
                def run(self, argv, *, cwd, env, timeout_s):
                    target = Path(argv[-1])
                    if "rawvideo" in argv: target.write_bytes(bytes(24 * 90))
                    elif "hevc" in argv: target.write_bytes(b"stream")
                    return 0, "", ""
            def hashes(path):
                return plan["source"]["sha256"] if Path(path) == source else "a" * 64
            with mock.patch.object(fb, "_private_path", side_effect=lambda value: Path(value)), \
                 mock.patch.object(fb, "WindowGuard", return_value=Guard()), \
                 mock.patch.object(fb, "sha256_file", side_effect=hashes), \
                 mock.patch.object(fb, "verify_tools_build", return_value={"qualified": True}), \
                 mock.patch.object(fb, "hvs_gpu_sanity", return_value={"passed": True}), \
                 mock.patch.object(nf, "_run_json", return_value=observed), \
                 mock.patch.object(nf, "lease_telemetry", return_value={"measurement_mode":"quality", "samples":[{}], "cleanup_verified":False}), \
                 mock.patch.object(nf, "_same_frame_scores", return_value={"codec_only":{}, "displayed":{}, "crops":{}}):
                result = nf.run_plan(plan_path, source, output,
                    {"ffmpeg":sys.executable, "ffprobe":sys.executable, "psnr_hvs_m_h":sys.executable},
                    root / "lease", tools_metadata=metadata)
            self.assertTrue(result["complete"])
            row = result["cells"][0]
            self.assertTrue(row["decoded_raw_wrapper"]["byte_identical"])
            self.assertEqual(row["bitstream"]["ffprobe_observed_metadata"]["avg_frame_rate"], "0/0")

    def test_lease_samples_are_private_path_pid_and_attestation_free(self):
        state = {"closed": False, "last_policy":{"mode":"quality", "free_vram_margin_mib":2048,
            "stop_reasons":[], "pid":44}, "gpu_load_samples":[{"epoch_s":11, "free_vram_mib":8000,
            "total_vram_mib":16000, "overall_load_percent":33, "external_max_engine_percent":4,
            "device_error":None, "compute_backend_reasons":[], "stop_reasons":[],
            "timing_invalidation_reasons":[], "pid":9, "path":"private", "attestation":"private"}]}
        with mock.patch("tools.quest3.unattended.json_read", return_value=state):
            report = nf.lease_telemetry(Path("private-window"), 10, 12)
        serialized = json.dumps(report)
        self.assertNotIn("pid", serialized); self.assertNotIn("path", serialized); self.assertNotIn("attestation", serialized)
        self.assertEqual(report["samples"][0]["free_vram_mib"], 8000.0)
        self.assertFalse(report["cleanup_verified"])

    def test_lease_samples_missing_in_interval_fail_closed(self):
        state = {"closed":False, "last_policy":{"mode":"quality", "free_vram_margin_mib":2048, "stop_reasons":[]},
                 "gpu_load_samples":[{"epoch_s":9}]}
        with mock.patch("tools.quest3.unattended.json_read", return_value=state):
            with self.assertRaisesRegex(ValueError, "missing"):
                nf.lease_telemetry(Path("private-window"), 10, 12)

    def test_runner_marks_final_lease_health_failure_incomplete(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); source = self.source(root); crop = {"name":"center","eye":"left","x":0,"y":0,"w":1,"h":1}
            plan = nf.build_plan(source, 23.5, projection_evidence="p", crop_evidence="c", fixture=True,
                                 rates_mbps=(200,), geometries=((2, 4),), codecs=("hevc",), crops=[crop], display_eye=(2, 4))
            plan_path = root / "plan.json"; plan_path.write_text(json.dumps(plan)); metadata = root / "metadata.json"; metadata.write_text("{}")
            observed = {"streams":[{"codec_name":"hevc","width":4,"height":4,"pix_fmt":"yuv420p","color_range":"unknown","chroma_location":"left","color_space":"unknown","color_primaries":"unknown","color_transfer":"unknown","avg_frame_rate":"0/0","r_frame_rate":"0/0","nb_read_frames":"90"}],"frames":[{"pict_type":"I","width":4,"height":4,"pix_fmt":"yuv420p"}]+[{"pict_type":"P","width":4,"height":4,"pix_fmt":"yuv420p"}]*89}
            class Guard:
                calls = 0
                def status(self):
                    self.calls += 1
                    if self.calls >= 2: raise PermissionError("lease lost")
                    return {}
                def run(self, argv, *, cwd, env, timeout_s):
                    target = Path(argv[-1]); target.write_bytes(bytes(24 * 90) if "rawvideo" in argv else b"stream"); return 0, "", ""
            def hashes(path): return plan["source"]["sha256"] if Path(path) == source else "a" * 64
            with mock.patch.object(fb,"_private_path",side_effect=lambda value:Path(value)), mock.patch.object(fb,"WindowGuard",return_value=Guard()), mock.patch.object(fb,"sha256_file",side_effect=hashes), mock.patch.object(fb,"verify_tools_build",return_value={"qualified":True}), mock.patch.object(fb,"hvs_gpu_sanity",return_value={"passed":True}), mock.patch.object(nf,"_run_json",return_value=observed), mock.patch.object(nf,"lease_telemetry",return_value={"measurement_mode":"quality","samples":[{}],"cleanup_verified":False}), mock.patch.object(nf,"_same_frame_scores",return_value={"codec_only":{},"displayed":{},"crops":{}}):
                result=nf.run_plan(plan_path,source,root/"out",{"ffmpeg":sys.executable,"ffprobe":sys.executable,"psnr_hvs_m_h":sys.executable},root/"lease",tools_metadata=metadata)
            self.assertFalse(result["complete"])
            self.assertIn("lease_final_health_failed",result["failure_reasons"])


if __name__ == "__main__":
    unittest.main()

import copy
import json
import unittest
from unittest.mock import patch

from tools.quest3 import budget
from tools.quest3.bench import active_settings, resolution_gate_status, scene_geometry_gate_status
from tools.quest3.control import resolution, restore_resolution
from tools.quest3.resolution import ENCODE_FIELD, RENDER_FIELD, assignments, evidence, profiles, scene_evidence


def absolute(width, height):
    return {"variant": "Absolute", "Scale": 1.0,
            "Absolute": {"width": width, "height": {"set": True, "content": height}}}


def settings(render=(3072, 3216), encode=(2560, 2688)):
    return {
        "codec": "PyroWave",
        "configured_render_view_resolution": absolute(*render),
        "configured_view_resolution": absolute(*encode),
        "openvr": {
            "target_eye_resolution_width": (render[0] + 31) // 32 * 32,
            "target_eye_resolution_height": (render[1] + 31) // 32 * 32,
            "eye_resolution_width": (encode[0] + 31) // 32 * 32,
            "eye_resolution_height": (encode[1] + 31) // 32 * 32,
            "enable_foveated_encoding": False,
        },
    }


class ResolutionTests(unittest.TestCase):
    def test_profile_writes_both_dimensions_and_keeps_unrelated_settings(self):
        current = {"session_settings": {"video": {
            RENDER_FIELD: absolute(2080, 2208), ENCODE_FIELD: absolute(2080, 2208),
            "preferred_fps": 90, "pyrowave": {"wavelet": {"variant": "Haar"}},
        }}}
        original = copy.deepcopy(current)

        def write(values):
            for path, value in values.items():
                node = current
                fields = path.split(".")
                for field in fields[:-1]:
                    node = node[field]
                node[fields[-1]] = value

        with patch("tools.quest3.control.session", side_effect=lambda: copy.deepcopy(current)), \
                patch("tools.quest3.control.set_values", side_effect=write):
            result = resolution(profile="quality-2560")
        video = current["session_settings"]["video"]
        self.assertEqual(video[RENDER_FIELD], absolute(3072, 3216))
        self.assertEqual(video[ENCODE_FIELD], absolute(2560, 2688))
        self.assertEqual(video["preferred_fps"], original["session_settings"]["video"]["preferred_fps"])
        self.assertEqual(result["render_eye_aligned"], [3072, 3232])
        self.assertEqual(result["encode_eye_aligned"], [2560, 2688])

    def test_explicit_one_axis_preserves_the_other(self):
        values = assignments(render_eye=[3072, 3216])
        self.assertTrue(all(RENDER_FIELD in path for path in values))
        values = assignments(encode_eye=[2080, 2208])
        self.assertTrue(all(ENCODE_FIELD in path for path in values))

    def test_invalid_or_ambiguous_geometry_is_rejected_before_io(self):
        for kwargs in ({}, {"render_eye": [3072.5, 3216]}, {"encode_eye": [0, 2208]},
                       {"render_eye": [True, 3216]}, {"profile": "missing"},
                       {"profile": "quality-2560", "encode_eye": [2560, 2688]}):
            with patch("tools.quest3.control.session") as read, \
                    patch("tools.quest3.control.set_values") as write:
                with self.assertRaises(ValueError):
                    resolution(**kwargs)
                read.assert_not_called()
                write.assert_not_called()

    def test_restore_uses_raw_snapshot_and_verifies_readback(self):
        previous_render = {"variant": "Scale", "Scale": 1.25}
        previous_encode = absolute(2080, 2208)
        current = {"session_settings": {"video": {
            RENDER_FIELD: absolute(3072, 3216), ENCODE_FIELD: absolute(2560, 2688)}}}
        snapshot = {"previous_resolution_settings": {
            RENDER_FIELD: previous_render, ENCODE_FIELD: previous_encode}}

        def write(values):
            for path, value in values.items():
                current["session_settings"]["video"][path.rsplit(".", 1)[1]] = value

        with patch("tools.quest3.control.session", side_effect=lambda: copy.deepcopy(current)), \
                patch("tools.quest3.control.set_values", side_effect=write):
            result = restore_resolution(snapshot)
        self.assertTrue(result["settings_restored"])
        self.assertEqual(current["session_settings"]["video"][RENDER_FIELD], previous_render)

    def test_geometry_evidence_requires_decoder_size_and_rejects_mismatch(self):
        evidence_without_decoder = evidence(settings(), expected_profile="quality-2560")
        self.assertEqual(evidence_without_decoder["status"], "unknown")
        valid = evidence(settings(), [{"pyrowave": {"encoded_width": 5120, "encoded_height": 2688}}],
                         expected_profile="quality-2560")
        self.assertEqual(valid["status"], "verified")
        self.assertEqual(valid["aligned_requested_render_eye"], [3072, 3232])
        wrong = evidence(settings(), [{"pyrowave": {"encoded_width": 6144, "encoded_height": 3232}}],
                         expected_profile="quality-2560")
        self.assertEqual(wrong["status"], "mismatch")
        self.assertIn("decoded_frame_differs_from_negotiated_encode", wrong["mismatches"])

    def test_active_settings_retains_raw_requested_render_geometry(self):
        session_document = {"session_settings": {"video": {
            "preferred_codec": {"variant": "PyroWave"}, "bitrate": {"mode": {"variant": "ConstantMbps", "ConstantMbps": 500}},
            "preferred_fps": 90, "pyrowave": {"decode_path": {"variant": "Compute"}, "wavelet": {"variant": "Haar"}, "transport": {"variant": "Tcp"}},
            "transcoding_view_resolution": absolute(2560, 2688),
            "emulated_headset_view_resolution": absolute(3072, 3216),
            "foveated_encoding": {"enabled": False}, "clientside_foveation": {"enabled": False},
            "encoder_config": {}, "enforce_server_frame_pacing": True,
        }, "connection": {"stream_protocol": {"variant": "Tcp"}}},
            "openvr_config": {"target_eye_resolution_width": 3072, "target_eye_resolution_height": 3232,
                              "eye_resolution_width": 2560, "eye_resolution_height": 2688,
                              "enable_foveated_encoding": False}}
        with patch("tools.quest3.control.session", return_value=session_document):
            observed = active_settings()
        self.assertEqual(observed["configured_render_view_resolution"], absolute(3072, 3216))
        self.assertEqual(evidence(observed, [{"pyrowave": {"encoded_width": 5120, "encoded_height": 2688}}],
                                  "quality-2560")["status"], "verified")

    def test_profile_contract_and_bpp_are_explicit(self):
        profile_map = profiles()
        self.assertEqual(profile_map["godlike-3072"]["render_eye"], [3072, 3216])
        self.assertEqual(profile_map["quality-2080"]["encode_eye"], [2080, 2208])
        document = json.loads((budget.Path("presets/resolution-comparison.json")).read_text(encoding="utf-8"))
        rows = {row["name"]: row for row in budget.geometry_profiles(document)}
        self.assertEqual(rows["godlike-3072"]["maximum_payload_bytes_per_frame"], 694_444)
        self.assertAlmostEqual(rows["godlike-3072"]["bits_per_pixel"], 0.27977, places=4)
        self.assertGreater(rows["quality-2080"]["bits_per_pixel"], rows["quality-2560"]["bits_per_pixel"])

    def test_geometry_capture_gate_is_opt_in_and_fail_closed(self):
        self.assertIsNone(resolution_gate_status({"status": "verified"}, True))
        self.assertEqual(resolution_gate_status({"status": "unknown"}, True),
                         "resolution_evidence_incomplete")
        self.assertEqual(resolution_gate_status({"status": "mismatch"}, True), "resolution_mismatch")
        self.assertIsNone(resolution_gate_status({"status": "mismatch"}, False))

    def test_normalized_scene_geometry_must_match_negotiated_render(self):
        geometry = evidence(settings(), [{"pyrowave": {"encoded_width": 5120, "encoded_height": 2688}}])
        scene = scene_evidence({"source_eye_size": [3072, 3232], "normalized_chart": True}, geometry)
        self.assertEqual(scene["status"], "verified")
        mismatch = scene_evidence({"source_eye_size": [2080, 2208], "normalized_chart": True}, geometry)
        self.assertEqual(scene_geometry_gate_status(mismatch, True), "scene_geometry_mismatch")
        missing = scene_evidence(None, geometry)
        self.assertEqual(scene_geometry_gate_status(missing, True), "scene_geometry_evidence_incomplete")


if __name__ == "__main__":
    unittest.main()

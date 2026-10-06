"""WO-11 overlay integrity and fail-closed source wiring. Rust execution is a CI gate."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "patches/dual-stream-h264-phase1.patch"
PATCH = PATCH_PATH.read_text(encoding="utf-8")
FILES = {
    "Cargo.toml", "alvr/client_core/src/connection.rs", "alvr/client_core/src/lib.rs",
    "alvr/client_core/src/stereo_pairing.rs", "alvr/common/src/version.rs",
    "alvr/packets/src/dual_stream.rs", "alvr/packets/src/lib.rs",
    "alvr/server_core/src/connection.rs", "alvr/session/src/beta.rs",
    "alvr/session/src/beta_tests.rs", "alvr/session/src/settings.rs",
}


def section(path):
    marker = f"diff --git a/{path} b/{path}\n"
    start = PATCH.index(marker) + len(marker)
    end = PATCH.find("\ndiff --git ", start)
    return PATCH[start:] if end < 0 else PATCH[start:end]


class DualStreamPhase1ContractTests(unittest.TestCase):
    def test_pin_and_last_overlay_application_are_authoritative(self):
        lock = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf-8"))
        pin = lock["patches"]["dual_stream_h264_phase1"]
        self.assertEqual(pin["path"], "patches/dual-stream-h264-phase1.patch")
        self.assertEqual(pin["sha256"], hashlib.sha256(PATCH_PATH.read_bytes()).hexdigest())
        fetch = (ROOT / "tools/ci/fetch_sources.sh").read_text(encoding="utf-8")
        check = fetch.index("--value dual_stream_h264_phase1_patch_sha256")
        apply = fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/dual-stream-h264-phase1.patch"')
        previous = fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/direct-eye-foveation.patch"')
        self.assertLess(previous, check)
        self.assertLess(check, apply)
        result = subprocess.run([sys.executable, str(ROOT / "tools/ci/source_lock.py"),
            "--value", "dual_stream_h264_phase1_patch_sha256"], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), pin["sha256"])

    def test_lock_loader_rejects_missing_or_malformed_new_pin(self):
        spec = importlib.util.spec_from_file_location("wo11_source_lock", ROOT / "tools/ci/source_lock.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for malformed in [None, {"path": "wrong", "sha256": "0" * 64},
            {"path": "patches/dual-stream-h264-phase1.patch", "sha256": "bad"}]:
            data = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf-8"))
            if malformed is None:
                del data["patches"]["dual_stream_h264_phase1"]
            else:
                data["patches"]["dual_stream_h264_phase1"] = malformed
            with tempfile.TemporaryDirectory() as tmp:
                module.LOCK = Path(tmp) / "sources.lock.json"
                module.LOCK.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaisesRegex(SystemExit, "dual_stream_h264_phase1"):
                    module.load()

    def test_exact_inventory_includes_new_modules_and_leaves_native_live_paths_untouched(self):
        paths = set(re.findall(r"^diff --git a/(\S+) b/\S+$", PATCH, re.MULTILINE))
        self.assertEqual(paths, FILES)
        for path in ["alvr/packets/src/dual_stream.rs", "alvr/client_core/src/stereo_pairing.rs"]:
            self.assertIn("new file mode 100644", section(path))
        self.assertNotIn("alvr_session::settings::", PATCH)
        removed = "\n".join(line for line in PATCH.splitlines() if line.startswith("-") and not line.startswith("---"))
        self.assertNotIn("VideoPacketHeader", removed)

    def test_protocol_authority_and_both_peer_guards(self):
        fork = json.loads((ROOT / "fork.json").read_text(encoding="utf-8"))
        self.assertEqual(fork["protocol_version"], "20.13.0-ljk1291.3")
        self.assertIn('+version = "' + fork["protocol_version"] + '"', section("Cargo.toml"))
        self.assertIn('Version::parse("20.13.0-ljk1291.2")', section("alvr/common/src/version.rs"))
        client = section("alvr/client_core/src/connection.rs")
        self.assertIn("is_version_compatible(&stream_config.server_version)", client)
        self.assertIn("dual_stream_h264_version: Some(alvr_packets::dual_stream::VERSION)", client)
        self.assertIn("dual_stream_h264_build: Some(ALVR_VERSION.to_string())", client)
        self.assertLess(client.index("if dual_requested"), client.index("ctx.uses_multimodal_protocol"))
        server = section("alvr/server_core/src/connection.rs")
        self.assertIn("negotiate(true, streaming_caps.dual_stream_h264_version)", server)
        for side in [client, server]:
            self.assertIn("dual_stream::negotiate_build(", side)
            self.assertIn("[WO11_DUAL_H264]", side)
            self.assertIn("effective=false", side)
            self.assertIn("pipeline_not_implemented", side)

    def test_default_off_and_no_automatic_codec_or_foveation_change(self):
        settings = section("alvr/session/src/settings.rs")
        self.assertIn("+            dual_stream_h264: false,", settings)
        self.assertIn("pub dual_stream_h264: bool", settings)
        server = section("alvr/server_core/src/connection.rs")
        for token in ["clientside_foveation.enabled()", "foveated_encoding.enabled()",
            "adapt_to_framerate.enabled()", "CodecType::H264", "SocketProtocol::Tcp",
            "total_bps", "left_bps", "right_bps"]:
            self.assertIn(token, server)
        self.assertNotRegex(server, r"\+.*initial_settings\.video\.\w+\s*=(?!=)")

    def test_ci_compiles_production_modules_and_full_packages_remain_gates(self):
        harness = (ROOT / "tools/wo11_contract_test.rs").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("alvr/packets/src/dual_stream.rs", harness)
        self.assertIn("alvr/client_core/src/stereo_pairing.rs", harness)
        self.assertIn("rustc --edition=2021 --test tools/wo11_contract_test.rs", workflow)
        for package in ["alvr_packets", "alvr_session", "alvr_common", "alvr_client_core", "alvr_server_core"]:
            self.assertIn(f"cargo test --release -p {package} --lib", workflow)

    def test_reconstructed_constructors_and_legacy_header(self):
        supplied = os.environ.get("Q3PW_WO11_TREE")
        if not supplied:
            self.skipTest("Set Q3PW_WO11_TREE to check the actual reconstructed source")
        tree = Path(supplied)
        packets = (tree / "alvr/packets/src/lib.rs").read_text(encoding="utf-8")
        for name in ["VideoStreamingCapabilities", "NegotiatedStreamingConfig"]:
            # Both definitions and all explicit constructors contain the new field.
            matches = re.findall(rf"(?:pub struct |\b){name} \{{([^{{}}]*)", packets)
            self.assertTrue(matches)
            for body in matches:
                self.assertIn("dual_stream_h264_version", body)
        header = packets.split("pub struct VideoPacketHeader {", 1)[1].split("\n}", 1)[0]
        fields = re.findall(r"pub (\w+):", header)
        self.assertEqual(fields, ["timestamp", "is_idr", "foveation_center"])
        self.assertIn("pub mod stereo_pairing;", (tree / "alvr/client_core/src/lib.rs").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

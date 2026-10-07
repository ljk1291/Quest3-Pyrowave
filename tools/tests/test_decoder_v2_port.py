"""CPU contracts for the opt-in decoder port. Native policy/GLES tests run in CI."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.ci.check_decoder_v2_shaders import verify
from tools.pyroclient.compile_shaders import SHADERS, manifest

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class DecoderV2PortTests(unittest.TestCase):
    def test_locked_patch_bytes_exports_and_application_order(self):
        lock = json.loads(read("sources.lock.json"))
        fetch = read("tools/ci/fetch_sources.sh")
        exported = subprocess.check_output([sys.executable, "tools/ci/source_lock.py", "--github-env"],
                                           cwd=ROOT, text=True)
        for key, previous, tree in (("pyrowave_decoder_v2", "pyrowave-fast53", "pyrowave"),
                                    ("alvr_decoder_v2", "fast-abr", "ALVR-20.13.0")):
            pin = lock["patches"][key]
            self.assertEqual(hashlib.sha256((ROOT / pin["path"]).read_bytes()).hexdigest(), pin["sha256"])
            value = subprocess.check_output([sys.executable, "tools/ci/source_lock.py", "--value",
                                             key + "_patch_sha256"], cwd=ROOT, text=True).strip()
            self.assertEqual(value, pin["sha256"])
            self.assertIn(f"{key.upper()}_PATCH_SHA256={value}", exported)
            self.assertLess(fetch.index(f'apply_patch "$dest/{tree}" "$repo/patches/{previous}.patch"'),
                            fetch.index(f"--value {key}_patch_sha256"))
            self.assertLess(fetch.index(f"--value {key}_patch_sha256"),
                            fetch.index(f'apply_patch "$dest/{tree}" "$repo/{pin["path"]}"'))
            # Git parses every hunk, including new shader files; fetch_sources performs
            # the full pinned-base application in the same CPU CI job.
            subprocess.run(["git", "apply", "--numstat", pin["path"]], cwd=ROOT,
                           check=True, capture_output=True)
        self.assertEqual(lock["pyrowave"]["commit"], "d2997ac172bdc00e29c58e3f2938acb7e94580bf")

    def test_default_off_selection_and_native_policy_gate_are_wired(self):
        client = read("tools/pyroclient/pyroclient.cpp")
        policy = read("tools/pyroclient/decoder_modes.h")
        self.assertIn("value[0] <= '5' && !value[1]", policy)
        self.assertIn('std::strcmp(value, "2") ? 2 : 4', policy)
        for prop in ("haar32", "cdf53v2", "packed_levels"):
            self.assertIn(f'__system_property_get("debug.q3pw.{prop}"', client)
        self.assertIn('fast53.reason = "cdf53v2"', client)
        self.assertIn('disable_present("no_ahb_storage")', client)
        self.assertIn('disable_present("ahb_allocation_or_import")', client)
        self.assertIn("pyroclient_decode_guarded_many", client)
        ci = read(".github/workflows/ci.yml")
        self.assertIn("tools/pyroclient/decoder_modes_test.cpp", ci)
        self.assertIn("tools/pyroclient/headset_csf_test.cpp", ci)

    def test_library_and_encoder_contracts(self):
        patch = read("patches/pyrowave-decoder-v2.patch")
        for token in ("pyrowave_decoder_set_haar32", "pyrowave_decoder_set_cdf53v2",
                      "mode > 5", "MaxPackedLevels = 4", "impl->cdf53v2",
                      "shaders/idwt_haar32.comp", "shaders/idwt_cdf53v2.comp",
                      "shaders.wavelet_quant[headset_csf ? 1 : 0]",
                      'std::strcmp(csf_request, "1")', "float(height_) / 99.0f",
                      "headset_csf && level >= 3", "headset_csf ? 1.6f : 0.6f",
                      "square_error *= registers.rdo_distortion_scale"):
            self.assertIn(token, patch)
        self.assertNotIn("diff --git a/bitstream/", patch)
        self.assertNotIn("diff --git a/shaders/idwt.comp", patch)
        self.assertNotIn("diff --git a/shaders/dwt_common.h", patch)
        alvr = read("patches/alvr-decoder-v2.patch")
        self.assertIn("[Q3PW_HEADSET_CSF]", alvr)
        self.assertIn("height/99_overrides_rdo", alvr)

    def test_presentation_uses_decoded_geometry_and_rgb_dump(self):
        patch = read("patches/alvr-decoder-v2.patch")
        for token in ("self.presentation_geometry.0", "desc.width == 2 * eye.x",
                      "desc.height * 2 == eye.y", "desc.format == 1",
                      "packed_ycbcr_dump_direct_and_staging_match_rgb_for_both_eyes",
                      "q3pw_present_sample", "super::present_ycbcr::bind",
                      "Some((image, true))"):
            self.assertIn(token, patch)
        self.assertNotIn("diff --git a/alvr/client_core/", patch)  # FIFO/lease unchanged.
        self.assertNotIn("diff --git a/alvr/graphics/resources/direct_eye_foveation.glsl", patch)

    def test_standalone_checks_each_wavelet_against_its_own_stock(self):
        source = read("tools/pyrowave_android/main.cpp")
        self.assertIn('"--compare-v2"', source)
        self.assertIn("variant < haar_arm ? 0 : haar_arm", source)
        for family in ("cdf53-v2", "haar32"):
            for mode in range(1, 6):
                self.assertIn(f'"{family}-{mode}"', source)
        self.assertIn("decoder_sample_offset(i, x, y", source)
        self.assertIn("raw_planes[physical].empty()", source)  # Copy shared targets once.
        self.assertIn("maximum <= 1", source)
        self.assertIn("live_vr=unverified", source)

    def test_shader_fold_workflow_covers_both_libraries(self):
        workflow = read(".github/workflows/shaders.yml")
        self.assertLess(workflow.index('apply -R "$GITHUB_WORKSPACE/patches/pyrowave-decoder-v2.patch"'),
                        workflow.index('apply -R "$GITHUB_WORKSPACE/patches/pyrowave-fast53.patch"'))
        self.assertIn("check_fast53_shaders.py", workflow)
        self.assertIn("check_decoder_v2_shaders.py", workflow)
        self.assertIn("compile_shaders.py --check --output-dir out/pyroclient", workflow)
        self.assertIn('compile_shaders.py" --check', read("tools/pyroclient/build.sh"))
        actual = manifest(ROOT / "tools/pyroclient", ROOT / "tools/pyroclient")
        self.assertEqual(set(actual), set(json.loads(read("tools/pyroclient/shader-manifest.json"))))
        # Actual byte equality is the build gate after CI folding, not a source-only claim.

    def test_shader_gate_rejects_changed_defaults_missing_modes_and_barriers(self):
        def header(entries):
            bank, assignments = [], []
            for (name, indices, fp16), extra in entries:
                words = [0x07230203, 0x10300, 0, 20, 0] + extra
                prefix = f'if (resolver("{name}", "FP16") == {fp16})\n{{\n' if fp16 is not None else ""
                suffix = "}" if fp16 is not None else ""
                assignments.append(prefix + f'this->{name}' + ''.join(f'[{i}]' for i in indices) +
                                   f' = device.request_program(spirv_bank + {len(bank)}, {len(words)*4}, &layout);\n' + suffix)
                bank.extend(words)
            return 'static const uint32_t spirv_bank[] = {' + ','.join(hex(w) for w in bank) + '};\n' + '\n'.join(assignments)
        old = [(("idwt", (1, 1), 1), []), (("wavelet_quant", (), None), [])]
        new = [(("idwt", (1, 1), 1), []), (("wavelet_quant", (0,), None), []),
               (("wavelet_quant", (1,), None), [])]
        new += [((name, (precision, dual), fp16), []) for name in ("idwt_haar32", "idwt_cdf53v2")
                for precision in range(3) for dual in range(2) for fp16 in range(2)]
        verify(header(old), header(new))
        with self.assertRaisesRegex(ValueError, "existing shader changed"):
            verify(header(old), header([(new[0][0], [(1 << 16)])] + new[1:]))
        with self.assertRaisesRegex(ValueError, "12 permutations"):
            verify(header(old), header(new[:-1]))
        with self.assertRaisesRegex(ValueError, "barrier"):
            verify(header(old), header(new[:-1] + [(new[-1][0], [(4 << 16) | 224, 1, 1, 1])]))

    def test_client_shader_manifest_is_independent_of_checkout_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source, header, _ in SHADERS:
                for name in (source, header):
                    (root / name).write_bytes(b'first\nsecond\n')
            baseline = manifest(root, root)
            for source, header, _ in SHADERS:
                for name in (source, header):
                    (root / name).write_bytes(b'first\r\nsecond\r\n')
            self.assertEqual(baseline, manifest(root, root))


if __name__ == "__main__":
    unittest.main()

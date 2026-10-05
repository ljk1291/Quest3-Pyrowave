"""Pinned overlay and safe activation checks; GPU pixels are checked by CI GLES."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class StagingCorrectnessContract(unittest.TestCase):
    def test_overlay_is_hash_pinned_after_session_setting_and_preflight(self):
        lock=json.loads((ROOT/'sources.lock.json').read_text(encoding='utf-8'))
        pin=lock['patches']['foveated_staging_correctness']
        self.assertEqual(hashlib.sha256((ROOT/pin['path']).read_bytes()).hexdigest(),pin['sha256'])
        fetch=(ROOT/'tools/ci/fetch_sources.sh').read_text(encoding='utf-8')
        self.assertLess(fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/alvr-pyrowave-rdo-session-setting.patch"'),
                        fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/foveated-staging-correctness.patch"'))

    def test_actual_profile_resolver_and_renderer_are_under_native_tests(self):
        patch=(ROOT/'patches/foveated-staging-correctness.patch').read_text(encoding='utf-8')
        for text in ('fixed_profiles_resolve_stale_fields_without_mutating_the_session',
                     'custom_asymmetric_geometry_is_preserved_exactly',
                     'software_gles_staging_both_eyes_survive_fixed_profile_inverse_and_gl_state',
                     'codec == CodecType::PyroWave &&',
                     'requested && self.wait_for_import_copy',
                     '"debug.q3pw.staging_isolation") == "1"',
                     '.filter(|c| !c.blur_only).map(|c| c.resolved_geometry())'):
            self.assertIn(text,patch)
        workflow=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
        self.assertIn('cargo +"$RUST_TOOLCHAIN" test -p alvr_graphics --lib staging_correctness_tests',workflow)
        self.assertIn("LIBGL_ALWAYS_SOFTWARE: '1'",workflow)

if __name__=='__main__':unittest.main()

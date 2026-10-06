"""Presentation overlay lock and immutable legacy shader contract."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PresentationOverlayTests(unittest.TestCase):
    def test_overlay_pin_and_stack_order(self):
        lock = json.loads((ROOT / 'sources.lock.json').read_text())
        pin = lock['patches']['presentation_filters']
        self.assertEqual(pin['path'], 'patches/presentation-filters.patch')
        self.assertEqual(pin['sha256'], hashlib.sha256((ROOT / pin['path']).read_bytes()).hexdigest())
        fetch = (ROOT / 'tools/ci/fetch_sources.sh').read_text()
        self.assertLess(fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/foveated-staging-correctness.patch"'),
                        fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/presentation-filters.patch"'))
        self.assertIn('--value presentation_filters_patch_sha256', fetch)

    def test_legacy_shader_hashes_and_sources_are_immutable(self):
        files = json.loads((ROOT / 'tools/windows/quality-shaders.json').read_text())['files']
        prefix = 'alvr/server_openvr/cpp/'
        expected = {
            'platform/win32/FrameRenderPS.cso': 'a4737d33fc2784dac4678b175c17d3566f39066b1ed242fc92187919cb7c52f3',
            'platform/win32/rgbtoyuvplanar.cso': '93de53dae81f6311ce1d567217a10b03d879c474162741483b909c44e44f3554',
            'platform/win32/FrameRenderPSArea.cso': 'df1db9b634eb104a7dea5cccaf5eccc56cc27b80c431f524fae2f3f73d7db6d6',
            'alvr_server/shader/FrameRender.fx': '769831180f07b72d98fa7995b5729f1da685ecb492ed9afd20b0c3e479e15f67',
        }
        patch = (ROOT / 'patches/presentation-filters.patch').read_text()
        for path, digest in expected.items():
            self.assertEqual(files[prefix + path], digest)
            self.assertNotIn('diff --git a/' + prefix + path + ' ', patch)


if __name__ == '__main__':
    unittest.main()

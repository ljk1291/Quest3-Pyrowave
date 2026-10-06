"""T1 source/CPU gates; production GLES pixels run in the manual client CI job."""
import hashlib
import json
import re
import unittest
from pathlib import Path

import numpy as np

from tools.quest3 import bench, control
from tools.xrbench import foveation as reference

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'patches/direct-eye-foveation.patch'


def added_file(path):
    section = PATCH.read_text(encoding='utf-8').split(f'diff --git a/{path} b/{path}\n', 1)[1]
    section = section.split('\ndiff --git ', 1)[0]
    return '\n'.join(line[1:] for line in section.splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


def shader_inverse(uv, size, packed, cfg, eye):
    """Evaluate the actual GLSL arithmetic expressions on CPU, with f32 uniforms.

    The uniform reference uses scalar WO-8 derivation, independently of the Rust
    upload. Native CI checks the Rust values and actual four-vec4 GL upload too.
    """
    shader = added_file('alvr/graphics/resources/direct_eye_foveation.glsl')
    c1, c2, bounds, al, bl, ar, br, cr, scale = ([] for _ in range(9))
    for n, enc, shift in zip(size, packed, cfg.center_shift):
        r = cfg.edge_ratio
        center = 1. - np.ceil((n - cfg.center_fraction * n) / (r * 2.)) * r * 2. / n
        # Same server/client lattice quantization before the per-frame coefficients.
        edge = n - center * n
        shift = np.ceil(shift * edge / (r * 2.)) * r * 2. / edge
        ratio, intercept, middle, lo, hi = reference._params(n, enc, cfg.center_fraction, r, shift)
        c1.append(intercept); c2.append(middle); scale.append(ratio)
        bounds.append(((1. - center) * .5 * (shift + 1.), (1. - center) * .5 * (shift - 1.) + 1.))
        al.append(middle * (1. - r) / (r * lo))
        bl.append((intercept + middle * lo) / lo)
        ar.append(middle * (r - 1.) / (r * (1. - hi)))
        br.append((middle - r * intercept - 2. * r * middle + middle * r * (1. - hi) + r) / (r * (1. - hi)))
        cr.append((middle * r - middle) * (intercept - hi + middle * hi) / (r * (1. - hi) ** 2))
    names = dict(zip(('c1', 'ffe_c2', 'a_left', 'b_left', 'a_right', 'b_right', 'c_right'),
                     (np.asarray(v, np.float32) for v in (c1, c2, al, bl, ar, br, cr))))
    names.update(ffe_expanded=np.asarray(size, np.float32),
                 ffe_edge_ratio=np.float32(cfg.edge_ratio), corrected_uv=np.asarray(uv, np.float32).copy())
    if eye == 1:
        names['corrected_uv'][..., 0] = 1. - names['corrected_uv'][..., 0]
    env = {'__builtins__': {}, 'vec2': np.float32, 'floor': np.floor, 'sqrt': np.sqrt}
    for name in ('intercept_px', 'sample_phase_px'):
        expr = re.search(rf'vec2 {name} = (.*);', shader)[1]
        names[name] = eval(expr, env, names)
    expr = re.search(r'corrected_uv -= (.*);', shader)[1]
    names['corrected_uv'] -= eval(expr, env, names)
    for name in ('center', 'left_edge', 'right_edge'):
        expr = re.search(rf'vec2 {name} = (.*);', shader)[1]
        # As in WGSL, unselected quadratic branches can have negative roots.
        with np.errstate(invalid='ignore'):
            names[name] = eval(expr, env, names)
    # Check the actual branch expressions, so a changed selector cannot pass by
    # evaluating an unrelated copy of the GLSL map in this test.
    for axis in ('x', 'y'):
        expected = (f'corrected_uv.{axis} < lo_bound.{axis} ? left_edge.{axis} : '
                    f'(corrected_uv.{axis} > hi_bound.{axis} ? right_edge.{axis} : center.{axis})')
        assert expected in shader
    lo, hi = np.asarray(bounds, np.float32).T
    mapped = np.where(names['corrected_uv'] < lo, names['left_edge'],
                      np.where(names['corrected_uv'] > hi, names['right_edge'], names['center']))
    mapped *= np.asarray(scale, np.float32)
    if eye == 1:
        mapped[..., 0] = 1. - mapped[..., 0]
    half = .5 / np.asarray(packed)
    mapped = np.clip(mapped, half, 1. - half)
    assert np.isfinite(mapped).all()
    return mapped


class DirectEyeFoveationContract(unittest.TestCase):
    def test_overlay_is_pinned_last_and_native_gates_are_dispatched(self):
        lock = json.loads((ROOT / 'sources.lock.json').read_text())
        pin = lock['patches']['direct_eye_foveation']
        self.assertEqual(pin['path'], 'patches/direct-eye-foveation.patch')
        self.assertEqual(pin['sha256'], hashlib.sha256(PATCH.read_bytes()).hexdigest())
        fetch = (ROOT / 'tools/ci/fetch_sources.sh').read_text()
        self.assertLess(fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/foveated-staging-correctness.patch"'),
                        fetch.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/direct-eye-foveation.patch"'))
        self.assertIn('--value direct_eye_foveation_patch_sha256', fetch)
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('test -p alvr_graphics --lib direct_eye_foveation_policy_tests', workflow)
        self.assertIn('test -p alvr_graphics --lib staging_correctness_tests -- --nocapture --test-threads=1', workflow)
        self.assertNotIn('alvr/server_', PATCH.read_text())

    def test_native_activation_and_spatial_gate_are_in_the_production_overlay(self):
        patch = PATCH.read_text()
        for marker in ('[Q3PW_DIRECT_FFE] requested={} effective={} profile={}',
                       '[Q3PW_PRESENTATION] path={path} rendered=true',
                       'direct_eye_copy_required', 'pyrowave_synchronous_import_required',
                       'asynchronous_copy', 'custom_profile', 'blur_only', 'unsupported_format',
                       'missing_inverse_support', 'missing_external_image_essl3',
                       'renderer_support_or_initialization_failed',
                       'software_gles_direct_ffe_matches_production_wgsl_spatial_both_eyes_and_center_update',
                       'shader_constants_match_wgsl_and_independent_wo8_geometry_fixtures',
                       'direct.set_foveation_center(shifts)', 'assert_ne!(stored[0], stored[1])',
                       'render_egl_image_for_test(image)', 'abs() <= 2',
                       'self.config.configured_foveation.as_ref()',
                       '2de8ad13973ed9c3a8e72f4c85a79e1e7e5d085a'):
            self.assertIn(marker, patch)

    def test_property_is_snapshotted_request_only_and_resettable(self):
        prop = 'debug.q3pw.direct_eye_foveation'
        self.assertIn(prop, bench.EXPERIMENT_PROPERTIES)
        self.assertIn(prop, control.EXPERIMENT_PROPERTIES)
        state = {'property:' + name: {'value': '', 'error': None} for name in bench.EXPERIMENT_PROPERTIES}
        self.assertFalse(bench.experiment_effective(state)['enabled']['direct_eye_foveation'])
        state['property:' + prop]['value'] = '1'
        self.assertTrue(bench.experiment_effective(state)['enabled']['direct_eye_foveation'])
        self.assertIn("('debug.q3pw.direct_eye_foveation','')", (ROOT / 'tools/quest3/control.py').read_text())

    def test_actual_glsl_inverse_matches_independent_cpu_reference_both_eyes(self):
        # Dense coordinates, corners, seam sides and both aligned centre joins.
        xy = np.linspace(.0001, .9999, 101)
        uv = np.stack(np.meshgrid(xy, xy), axis=-1).reshape(-1, 2)
        for size in ((176, 160), (2624, 2752), (3072, 3232)):
            for profile in reference.PROFILE_CONSTANTS:
                cfg = reference.FoveationConfig(profile)
                packed = reference.encoded_size(*size, cfg)
                half = .5 / np.asarray(packed)
                for eye in (0, 1):
                    expected_uv = uv.copy()
                    if eye:
                        expected_uv[:, 0] = 1. - expected_uv[:, 0]
                    expected = reference.inverse_map_uv(expected_uv, size, packed, cfg)
                    if eye:
                        expected[:, 0] = 1. - expected[:, 0]
                    expected = np.clip(expected, half, 1. - half)
                    actual = shader_inverse(uv, size, packed, cfg, eye)
                    np.testing.assert_allclose(actual, expected, rtol=0, atol=2e-6,
                                               err_msg=f'{size} {profile} eye={eye}')

    def test_nonzero_per_eye_center_and_repeat_use_the_same_inverse(self):
        uv = np.stack(np.meshgrid(np.linspace(.003, .997, 41),
                                  np.linspace(.003, .997, 43)), axis=-1).reshape(-1, 2)
        size = (176, 160)
        for profile in reference.PROFILE_CONSTANTS:
            for eye, shift in enumerate(((.21, -.17), (-.23, .19))):
                cfg = reference.FoveationConfig(profile, center_shift=shift)
                packed = reference.encoded_size(*size, cfg)
                aligned_shift = []
                for n, value in zip(size, shift):
                    edge = np.ceil((n - cfg.center_fraction * n) / (cfg.edge_ratio * 2.)) * cfg.edge_ratio * 2.
                    aligned_shift.append(np.ceil(value * edge / (cfg.edge_ratio * 2.)) * cfg.edge_ratio * 2. / edge)
                aligned = reference.FoveationConfig(profile, center_shift=tuple(aligned_shift))
                source_uv = uv.copy()
                if eye:
                    source_uv[:, 0] = 1. - source_uv[:, 0]
                expected = reference.inverse_map_uv(source_uv, size, packed, aligned)
                if eye:
                    expected[:, 0] = 1. - expected[:, 0]
                half = .5 / np.asarray(packed)
                expected = np.clip(expected, half, 1. - half)
                actual = shader_inverse(uv, size, packed, cfg, eye)
                np.testing.assert_allclose(actual, expected, rtol=0, atol=2e-6)
                np.testing.assert_array_equal(actual, shader_inverse(uv, size, packed, cfg, eye))
                self.assertGreater(np.max(np.abs(actual - shader_inverse(
                    uv, size, packed, reference.FoveationConfig(profile), eye))), .001)


if __name__ == '__main__':
    unittest.main()

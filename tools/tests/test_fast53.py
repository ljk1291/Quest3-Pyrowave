import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

import unittest

from tools.xrbench.fast53 import apron_tile, fast_tile, blocked_tile, fast_address, gather_coordinates
from tools.ci.check_fast53_shaders import verify, check_local_shader, programs, spirv_sha256

ROOT = Path(__file__).resolve().parents[2]


def check_addresses_match_literal_gathers_including_odd_coarse_mips():
    for size in (1, 2, 3, 7, 16, 41, 43, 82, 86):
        for low in (True, False):
            for base in range(-4, size + 5, 2):
                coords = gather_coordinates((base, base), (size, size), (low, low))
                assert coords == [(fast_address(base + du, size, low), fast_address(base + dv, size, low))
                                  for du, dv in ((0, 0), (1, 0), (0, 1), (1, 1))]


def check_full_2d_apron_parity_and_partial_workgroup_coverage(precision, dc):
    rng = random.Random(0x53)
    for width, height in ((1, 1), (2, 3), (7, 5), (16, 16), (19, 17), (41, 43)):
        bands = [[[rng.uniform(-.4, .4) for _ in range(width)] for _ in range(height)] for _ in range(4)]
        # Also crop an aligned allocation as the final imageStore does.
        for extent in ((2 * width, 2 * height), (max(1, 2 * width - 2), max(1, 2 * height - 2))):
            output = {}
            for gy in range((width + 15) // 16):
                for gx in range((height + 15) // 16):
                    kwargs = dict(group=(gx, gy), precision=precision, dc=dc, extent=extent)
                    ref = apron_tile(bands, **kwargs)
                    fast = fast_tile(bands, **kwargs)
                    assert fast == ref
                    assert not output.keys() & fast.keys()
                    output.update(fast)
            assert len(output) == extent[0] * extent[1]


def check_band_impulses_edges_and_rounding_boundaries():
    for layer in range(4):
        for y, x in ((0, 0), (0, 16), (16, 0), (16, 16), (7, 8)):
            bands = [[[0.] * 17 for _ in range(17)] for _ in range(4)]
            bands[layer][y][x] = .500244140625  # half rounding tie; initial store matters
            for precision in (0, 1, 2):
                for group in ((0, 0), (1, 0), (0, 1), (1, 1)):
                    assert fast_tile(bands, group, precision) == apron_tile(bands, group, precision)


def check_overlay_pin_selection_and_ci_contract():
    pin = json.loads((ROOT / 'sources.lock.json').read_text())['patches']['pyrowave_fast53']
    patch = ROOT / pin['path']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == pin['sha256']
    result = subprocess.run([sys.executable, str(ROOT / 'tools/ci/source_lock.py'), '--value',
                             'pyrowave_fast53_patch_sha256'], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == pin['sha256']
    script = (ROOT / 'tools/ci/fetch_sources.sh').read_text()
    assert script.index('apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-session-setting.patch"') < script.index(
        'apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-fast53.patch"')
    source = patch.read_text()
    assert 'int fast53 = 0;' in source
    assert 'variant < 0 || variant > 3 || (variant && (!impl->legall53 || impl->fragment_path))' in source
    assert 'return set_fast53_variant(enabled ? 1 : 0);' in source
    client = (ROOT / 'tools/pyroclient/pyroclient.cpp').read_text()
    assert 'choose_fast53(fast53_prop, legall53, fragment_path)' in client
    assert '__system_property_get("debug.q3pw.fast53", fast53_prop)' in client
    assert 'tools/pyroclient/fast53_test.cpp' in (ROOT / '.github/workflows/ci.yml').read_text()
    assert "'debug.q3pw.fast53'" in (ROOT / 'tools/quest3/bench.py').read_text()


class Fast53Tests(unittest.TestCase):
    @staticmethod
    def blocked_reference(bands, group=(0, 0), **kwargs):
        out = {}
        for x in (0, 1):
            for y in (0, 1):
                out.update(apron_tile(bands, (2 * group[0] + x, 2 * group[1] + y), **kwargs))
        return out

    def test_phase_aligned_gathers_match_even_origin_mirror(self):
        # Test every lane, including unused gather lanes at odd/tiny boundaries.
        for width, height in ((1, 1), (2, 3), (3, 2), (7, 5), (31, 33), (41, 43), (164, 86)):
            for layer in range(4):
                for u in (0, 4 * ((height - 1) // 4)):
                    for v in (0, 4 * ((width - 1) // 4)):
                        for i in range(3):
                            for j in range(3):
                                origin = (u + 2 * i - layer // 2, v + 2 * j - layer % 2)
                                got = gather_coordinates(origin, (height, width), (layer < 2, layer % 2 == 0))
                                expected = [(fast_address(origin[0] + du, height, layer < 2),
                                             fast_address(origin[1] + dv, width, layer % 2 == 0))
                                            for du, dv in ((0, 0), (1, 0), (0, 1), (1, 1))]
                                self.assertEqual(got, expected, (width, height, layer, origin))

    def test_blocked_variants_parity_and_workgroup_coverage(self):
        rng = random.Random(0x533)
        for width, height in ((1, 1), (2, 3), (7, 5), (16, 16), (19, 17), (31, 33), (65, 67)):
            bands = [[[rng.uniform(-.4, .4) for _ in range(width)] for _ in range(height)] for _ in range(4)]
            for precision in (0, 1, 2):
                for dc in (False, True):
                    extent = (max(1, 2 * width - 1), max(1, 2 * height - 1))
                    args = dict(precision=precision, dc=dc, extent=extent)
                    outputs = {2: {}, 3: {}}
                    for gy in range((width + 31) // 32):
                        for gx in range((height + 31) // 32):
                            ref = self.blocked_reference(bands, (gx, gy), **args)
                            for variant in (2, 3):
                                fast = blocked_tile(bands, (gx, gy), variant=variant, **args)
                                self.assertEqual(fast, ref, (width, height, precision, dc, variant, gx, gy))
                                self.assertFalse(outputs[variant].keys() & fast.keys())
                                outputs[variant].update(fast)
                    for output in outputs.values():
                        self.assertEqual(len(output), extent[0] * extent[1])

    def test_blocked_impulses_and_store_rounding(self):
        for layer in range(4):
            for y, x in ((0, 0), (0, 16), (16, 0), (16, 16), (7, 8)):
                bands = [[[0.] * 17 for _ in range(17)] for _ in range(4)]
                bands[layer][y][x] = .500244140625
                for precision in (0, 1, 2):
                    ref = self.blocked_reference(bands, precision=precision)
                    for variant in (2, 3):
                        self.assertEqual(blocked_tile(bands, precision=precision, variant=variant), ref)

    def test_blocked_texture_instruction_counts(self):
        bands = [[[.1] * 32 for _ in range(32)] for _ in range(4)]
        for variant, instruction, per_invocation in ((2, 'fetch', 121), (3, 'gather', 36)):
            counts = {}
            out = blocked_tile(bands, variant=variant, counts=counts)
            self.assertEqual(len(out), 4096)
            self.assertEqual(counts, {'invocations': 64, instruction: 64 * per_invocation})

    def test_cropped_live_geometry_coarse_mip(self):
        # Five-level stereo 5248x2752 -> 164x86 at input_level=4.
        rng = random.Random(52482752)
        bands = [[[rng.uniform(-2, 2) for _ in range(164)] for _ in range(86)] for _ in range(4)]
        for precision in (0, 1, 2):
            for group in ((0, 0), (2, 5), (5, 10)):
                with self.subTest(precision=precision, group=group):
                    self.assertEqual(fast_tile(bands, group, precision), apron_tile(bands, group, precision))
            for group in ((0, 0), (1, 2), (2, 5)):
                ref = self.blocked_reference(bands, group, precision=precision)
                for variant in (2, 3):
                    self.assertEqual(blocked_tile(bands, group, precision, variant=variant), ref)

    def test_generated_shader_gate(self):
        def header(fast, change_default=False, extra=(), extra_variant=1, count=4):
            bank, assignments = [], []
            for fp16 in range(2):
                for precision in range(3):
                    for variant in range(count if fast else 1):
                        words = [0x07230203, 0x10300, 0, 10 + precision + 3 * fp16, 0]
                        if variant:
                            if variant == extra_variant:
                                words += extra
                        elif change_default:
                            words[3] += 1
                        suffix = f'[{precision}][{variant}]' if fast else f'[{precision}]'
                        assignments.append(f'if (resolver("idwt", "FP16") == {fp16})\n{{\n'
                                           f'this->idwt{suffix} = device.request_program(spirv_bank + '
                                           f'{len(bank)}, {len(words) * 4}, &layout);\n}}')
                        bank.extend(words)
            return ('static const uint32_t spirv_bank[] = {' + ','.join(hex(w) for w in bank) + '};\n' +
                    '\n'.join(assignments))

        baseline, candidate = header(False), header(True)
        frozen = {(indices[0], fp16): spirv_sha256(words)
                  for (name, indices, fp16), words in programs(candidate).items()
                  if name == 'idwt' and indices[1] == 1}

        def check(candidate):
            verify(baseline, candidate, frozen)

        check(candidate)
        with self.assertRaisesRegex(ValueError, 'pre-existing shader changed'):
            check(header(True, change_default=True))
        for variant in (1, 2, 3):
            with self.assertRaisesRegex(ValueError, 'barrier'):
                check(header(True, extra=[(4 << 16) | 224, 1, 1, 1], extra_variant=variant))
            with self.assertRaisesRegex(ValueError, 'workgroup storage'):
                check(header(True, extra=[(4 << 16) | 59, 1, 2, 4], extra_variant=variant))
        with self.assertRaisesRegex(ValueError, 'measured v1 shader changed'):
            check(header(True, extra=[(1 << 16) | 0]))  # OpNop still changes v1 bytes
        with self.assertRaisesRegex(ValueError, 'missing fast53 variant'):
            check(header(True, count=3))
        with self.assertRaisesRegex(ValueError, 'invalid SPIR-V instruction'):
            check_local_shader([0x07230203, 0, 0, 0, 0, 0])

    def test_addresses(self):
        check_addresses_match_literal_gathers_including_odd_coarse_mips()

    def test_full_2d_parity(self):
        for precision in (0, 1, 2):
            for dc in (False, True):
                with self.subTest(precision=precision, dc=dc):
                    check_full_2d_apron_parity_and_partial_workgroup_coverage(precision, dc)

    def test_impulses(self):
        check_band_impulses_edges_and_rounding_boundaries()

    def test_integration(self):
        check_overlay_pin_selection_and_ci_contract()


if __name__ == '__main__':
    unittest.main()

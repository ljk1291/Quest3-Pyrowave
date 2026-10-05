import math
import random
import unittest

from tools.xrbench.wo6_cdf97_model import (f16, fused_idwt97_2d, fused_idwt97_line,
                                            mirror_index, reference_idwt97_2d,
                                            reference_idwt97_line)


def bands(seed: int):
    rng = random.Random(seed)
    return [[[rng.uniform(-8.0, 8.0) for _ in range(8)] for _ in range(8)] for _ in range(4)]


class Cdf97FusedModelTests(unittest.TestCase):
    def test_literal_line_order_matches_pinned_reference_random_and_impulse(self):
        for seed in range(16):
            values = [random.Random(seed).uniform(-32.0, 32.0) for _ in range(16)]
            self.assertEqual(fused_idwt97_line(values), reference_idwt97_line(values))
        impulse = [0.0] * 16
        impulse[7] = 1.0
        self.assertEqual(fused_idwt97_line(impulse), reference_idwt97_line(impulse))

    def test_two_dimensional_layer_orientation_and_f16_writeback_match(self):
        for seed in range(8):
            self.assertEqual(fused_idwt97_2d(*bands(seed)), reference_idwt97_2d(*bands(seed)))
        ll, xh, yh, hh = bands(91)
        xh[3][4] = 64.0
        output = fused_idwt97_2d(ll, xh, yh, hh)
        self.assertTrue(all(math.isfinite(value) for row in output for value in row))
        self.assertTrue(all(value == f16(value) for row in output for value in row))

    def test_documented_near_and_far_endpoint_rules(self):
        # low/even: near whole sample, far half sample; high/odd reverses near convention.
        self.assertEqual(mirror_index(-1, 5, True, False), 1)
        self.assertEqual(mirror_index(-1, 5, False, True), 0)
        self.assertEqual(mirror_index(5, 5, True, False), 4)
        self.assertEqual(mirror_index(5, 5, False, True), 3)
        self.assertEqual(mirror_index(99, 5, True, False), 0)  # candidate clamp after one mirror step

    def test_adversarial_zeros_alternating_and_large_finite_coefficients(self):
        vectors = ([0.0] * 16,
                   [(-1.0) ** index * 12.0 for index in range(16)],
                   [10000.0 if index % 2 else -10000.0 for index in range(16)])
        for values in vectors:
            expected = reference_idwt97_line(values)
            actual = fused_idwt97_line(values)
            self.assertEqual(actual, expected)
            self.assertTrue(all(math.isfinite(value) for value in actual))


if __name__ == "__main__":
    unittest.main()

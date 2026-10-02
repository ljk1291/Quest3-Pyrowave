import math
import unittest

from tools.quest3.quality_reference import axis_weights, area_box, dither_offset, quantize_r8


class QualityReferenceTests(unittest.TestCase):
    def test_fractional_overlap_and_dc_preservation(self):
        self.assertEqual(axis_weights(1.25, 1.5, 0, 3), {0: 1/3, 1: 2/3})
        for centre in (.05, .5, 2.35, 5.9):
            for footprint in (1, 1.2, 1.5, 4):
                self.assertAlmostEqual(sum(axis_weights(centre, footprint, 0, 5).values()), 1)
                self.assertAlmostEqual(area_box([[.37]*6 for _ in range(6)],
                                               (centre, centre), (footprint, footprint), (0,0,5,5)), .37)

    def test_two_dimensional_area_average(self):
        # Integrates precisely four unit texel cells, unlike a single-tap sample.
        self.assertEqual(area_box([[0,0],[0,1]], (1,1), (2,2), (0,0,1,1)), .25)
        self.assertAlmostEqual(area_box([[0,1],[0,1]], (1.25,1), (1.5,2), (0,0,1,1)), 2/3)

    def test_clamped_eye_boundary_never_reads_other_eye(self):
        stereo = [[0]*4 + [1]*4 for _ in range(4)]
        self.assertEqual(area_box(stereo, (3.8,2), (4,2), (0,0,3,3)), 0)
        self.assertEqual(area_box(stereo, (4.2,2), (4,2), (4,0,7,3)), 1)

    def test_dither_is_zero_mean_bounded_and_spatially_periodic(self):
        offsets = [dither_offset(x,y) for y in range(4) for x in range(4)]
        self.assertAlmostEqual(sum(offsets), 0)
        self.assertLess(max(abs(v) for v in offsets), .5/255)
        self.assertEqual(len(set(offsets)), 16)
        self.assertEqual(dither_offset(3,2), dither_offset(7,6))

    def test_quantization_preserves_integer_neutrals_and_range(self):
        for code in (0,16,24,48,128,235,255):
            for y in range(4):
                for x in range(4):
                    self.assertEqual(quantize_r8(code/255, x,y,True), code)
        for value in (-.25,0,.2,.5,.73,1,1.25):
            plain = quantize_r8(value)
            for y in range(4):
                for x in range(4):
                    got = quantize_r8(value,x,y,True)
                    self.assertTrue(0 <= got <= 255)
                    self.assertLessEqual(abs(got-plain), 1)

    def test_fractional_gradient_dither_mean_is_unbiased(self):
        # 16 ordered thresholds allocate the expected fraction to adjacent codes.
        value = 48.25/255
        codes = [quantize_r8(value,x,y,True) for y in range(4) for x in range(4)]
        self.assertEqual(sum(codes)/16, 48.25)

    def test_unsupported_inputs_fail(self):
        for width in (.9,4.1,math.nan):
            with self.assertRaises(ValueError): axis_weights(1,width,0,4)
        with self.assertRaises(ValueError): axis_weights(1,1,4,0)
        with self.assertRaises(ValueError): quantize_r8(math.nan)

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.xrbench import fence_metrics as m
from tools.xrbench import framebank as fb


class FenceMetricsTests(unittest.TestCase):
    def reference(self):
        r = np.full((32, 32), 60, np.uint8)
        r[:, 16:] = 180
        return r

    def run_sequence(self, error):
        acc = m.FenceAccumulator()
        for t in range(1, 91):
            r = self.reference()
            d = (r.astype(np.int16)+error(t)).astype(np.uint8)
            acc.add(t, r, d)
        return acc.report()

    def test_identity_has_infinite_psnr_and_zero_shimmer(self):
        result = self.run_sequence(lambda t: 0)
        self.assertEqual(result['10-89']['temporal_pairs'], 79)
        self.assertEqual(result['1-90']['temporal_pairs'], 89)
        for row in result.values():
            self.assertEqual(row['edge_psnr_y_db'], math.inf)
            self.assertEqual(row['shimmer_mean'], 0)
            self.assertTrue(row['valid'])

    def test_constant_bias_is_spatial_not_temporal_error(self):
        row = self.run_sequence(lambda t: 4)['10-89']
        self.assertAlmostEqual(row['edge_psnr_y_db'], 20*math.log10(255/4))
        self.assertEqual(row['edge_abs_error_p999'], 4)
        self.assertEqual(row['shimmer_p99'], 0)

    def test_alternating_error_has_double_temporal_amplitude(self):
        row = self.run_sequence(lambda t: 3 if t % 2 else -3)['10-89']
        self.assertEqual(row['shimmer_mean'], 6)
        self.assertEqual(row['shimmer_p99'], 6)
        self.assertEqual(row['edge_abs_error_p999'], 3)

    def test_error_change_before_window_does_not_leak_into_temporal_score(self):
        result = self.run_sequence(lambda t: 0 if t < 10 else 10)
        self.assertEqual(result['10-89']['shimmer_mean'], 0)
        self.assertGreater(result['1-90']['shimmer_mean'], 0)

    def test_mask_uses_reference_and_ignores_crop_boundary(self):
        mask, threshold = m.edge_mask(self.reference())
        self.assertTrue(threshold > 0)
        self.assertTrue(mask[1:-1, 15:17].all())
        self.assertFalse(mask[[0, -1]].any())
        self.assertFalse(mask[:, [0, -1]].any())
        self.assertFalse(mask[:, :14].any())

    def test_empty_flat_mask_is_not_a_valid_perfect_result(self):
        acc = m.FenceAccumulator(((1, 2),))
        for t in (1, 2):
            acc.add(t, np.zeros((4, 4), np.uint8), np.zeros((4, 4), np.uint8))
        row = acc.report()['1-2']
        self.assertFalse(row['valid'])
        self.assertIsNone(row['edge_psnr_y_db'])

    def test_percentile_matches_numpy_linear(self):
        values = np.array([0, 1, 2, 2, 4, 255, 510])
        hist = np.bincount(values, minlength=511)
        for percentile in (0, 50, 99, 99.9, 100):
            self.assertAlmostEqual(m.histogram_percentile(hist, percentile),
                                   np.percentile(values, percentile, method='linear'))

    def test_missing_frames_geometry_drift_and_wrong_dtype_rejected(self):
        acc = m.FenceAccumulator()
        r = self.reference()
        with self.assertRaises(ValueError): acc.add(2, r, r)
        acc.add(1, r, r)
        with self.assertRaises(ValueError): acc.report()
        with self.assertRaises(ValueError): acc.add(2, r, r.astype(float))
        with self.assertRaises(ValueError): acc.add(2, r[:20], r[:20])

    def test_y4m_integration_and_length_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'a.y4m', Path(tmp)/'b.y4m'
            y = np.tile(self.reference(), (1, 2))
            planes = [y, np.full((16, 32), 128, np.uint8), np.full((16, 32), 128, np.uint8)]
            info = fb.Y4MInfo(64, 32, 90, 1, '420', 'FULL', 64*32*3//2, 90)
            fb.write_y4m(a, info, [planes]*90)
            fb.write_y4m(b, info, [planes]*90)
            rect = dict(eye='right', x=0, y=0, width=32, height=32)
            result = m.score_y4m(a, b, rect)
            self.assertEqual(len(result['frame_identity']), 90)
            self.assertEqual(result['windows']['10-89']['frames'], 80)
            fb.write_y4m(b, info, [planes]*89)
            with self.assertRaises(ValueError): m.score_y4m(a, b, rect)


class CropGeometryTests(unittest.TestCase):
    tangents = [[-1.3763818740844727, .8390995860099792, -1.4281479120254517, .9656887650489807],
                [-.8390995860099792, 1.3763818740844727, -1.4281479120254517, .9656887650489807]]

    def geometry(self):
        return m.crop_geometry((3072, 3232), (2624, 2776), self.tangents)

    def test_asymmetry_mirror_and_no_density_resampling(self):
        g = self.geometry()
        l, r = g['eyes']
        self.assertEqual(l['x']+r['x']+2624, 3072)
        self.assertEqual(l['y'], r['y'])
        self.assertNotEqual(l['x'], r['x'])
        for eye in g['eyes']:
            self.assertEqual(eye['x'] % 2, 0)
            self.assertEqual(eye['y'] % 2, 0)
            self.assertTrue(all(abs(v) <= 1 for v in eye['alignment_error']))
            old = eye['original_tangents']; new = eye['effective_tangents']
            self.assertAlmostEqual(3072/(old[1]-old[0]), 2624/(new[1]-new[0]))
            self.assertAlmostEqual(3232/(old[3]-old[2]), 2776/(new[3]-new[2]))
            self.assertAlmostEqual(eye['scaled_span_pixels'][1], 2747.2)

    def test_crop_contains_exact_native_luma_chroma_samples_and_stereo_seam(self):
        g = m.crop_geometry((16, 16), (8, 8), [[-2, 1, -1, 1], [-1, 2, -1, 1]], (.5, .5))
        planes = [np.arange(512, dtype=np.uint16).reshape(16, 32).astype(np.uint8),
                  np.arange(128, dtype=np.uint8).reshape(8, 16),
                  np.full((8, 16), 77, np.uint8)]
        out = m.crop_frame(planes, g)
        for idx, f in enumerate((1, 2, 2)):
            for eye_idx, eye in enumerate(g['eyes']):
                x, y = eye['x']//f+eye_idx*16//f, eye['y']//f
                np.testing.assert_array_equal(out[idx][:, eye_idx*8//f:(eye_idx+1)*8//f],
                                              planes[idx][y:y+8//f, x:x+8//f])

    def test_disabled_geometry_is_identity(self):
        g = m.crop_geometry((3072, 3232), (3072, 3232), self.tangents, (1, 1))
        self.assertEqual([(v['x'], v['y']) for v in g['eyes']], [(0, 0), (0, 0)])

    def test_partial_rectangle_is_reported_not_silently_clipped(self):
        g = self.geometry()
        result = m.map_rectangle(dict(eye='left', x=0, y=0, width=500, height=500), g)
        self.assertFalse(result['fully_contained'])
        self.assertIsNone(result['mapped'])
        self.assertTrue(0 < result['retained_area_fraction'] < 1)

    def test_invalid_geometry_rejected(self):
        for target, multipliers in (((2623, 2776), (.85, .85)), ((4000, 3000), (.85, .85)),
                                    ((2624, 2776), (float('nan'), .85))):
            with self.assertRaises(ValueError):
                m.crop_geometry((3072, 3232), target, self.tangents, multipliers)


if __name__ == '__main__': unittest.main()

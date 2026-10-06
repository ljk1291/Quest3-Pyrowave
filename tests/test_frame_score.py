import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from tools.quest3 import frame_score as f, stereo_scene


def dump(root, timestamp, stage, image, index=0, row_order='top_down', fmt='rgba8', color_range='full'):
    root.mkdir(parents=True, exist_ok=True)
    h, w = image.shape
    if fmt == 'rgba8':
        rgba = np.stack([image, image, image, np.full_like(image, 255)], axis=-1)
        raw = rgba.tobytes()
    else:
        raw = image.tobytes() + bytes([128])*(h*w//2)
    base = root/f'{timestamp}-{stage}'
    base.with_suffix('.raw').write_bytes(raw)
    meta = dict(schema=1, timestamp_ns=timestamp, frame_index=index, stage=stage,
                width=w, height=h, format=fmt, range=color_range, matrix='bt709',
                row_order=row_order, bytes=len(raw), complete=True)
    base.with_suffix('.json').write_text(json.dumps(meta))
    return meta, base.with_suffix('.raw')


class FrameScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server, self.client = self.root/'server', self.root/'client'
        self.image = np.tile(np.arange(128, dtype=np.uint8), (64, 1))

    def test_windows_path_right_split_and_limits(self):
        self.assertEqual(f.parse_dump_path(r'C:\captures with spaces:part:128:9000'),
                         (r'C:\captures with spaces:part', 128, 9000))
        self.assertEqual(f.parse_dump_path('dir:'+'0'*5000+'1:1'), ('dir', 1, 1))
        for text in ['', '0', ':1:1', 'a:0:1', 'a:1:0', 'a:129:1', 'a:1:9001',
                     'a:-1:1', 'a:+1:1', 'a:1:1 ', 'a:1', 'a:1:١', 'a:'+'9'*100+':1']:
            with self.subTest(text=text), self.assertRaises(ValueError): f.parse_dump_path(text)

    def test_exact_identity_metrics_and_strict_json(self):
        for timestamp in [1000, 2000]:
            dump(self.server, timestamp, 'encoder_input', self.image)
            dump(self.client, timestamp, 'post_decode', self.image)
        report = f.score_directories(self.server, self.client)
        self.assertEqual(report['aggregate']['pair_count'], 2)
        full = report['pairs'][1]['regions']['full']
        self.assertTrue(full['identical'])
        self.assertIsNone(full['psnr_y_db'])
        self.assertAlmostEqual(full['ssim_y'], 1)
        self.assertEqual(full['temporal']['residual_mean'], 0)
        self.assertEqual(full['detail_energy_ratio'], 1)
        json.dumps(report, allow_nan=False)
        self.assertIn('Pairs: 2', f.markdown(report))

    def test_known_bias_psnr_ssim(self):
        r = np.full((32, 32), 80, np.float32)
        d = r+4
        self.assertAlmostEqual(f.psnr(r, d), 20*math.log10(255/4))
        self.assertLess(f.ssim(r, d), 1)
        self.assertGreater(f.ssim(r, d), .99)

    def test_block_grid_and_source_subtraction(self):
        r = np.full((64, 128), 100, np.float32)
        d = r.copy()
        d[:, 8:16] += 20
        self.assertGreater(f.blockiness(d, 8), f.blockiness(r, 8))
        identity = f.region_score(d, d, (8, 16))
        self.assertEqual(identity['blockiness']['8']['excess'], 0)

    def test_blurred_edges_lose_detail(self):
        r = np.tile(((np.arange(128)//4)%2*200).astype(np.float32), (64, 1))
        d = cv2.GaussianBlur(r, (5, 5), 1)
        result = f.region_score(r, d, (8,))
        self.assertLess(result['detail_energy_ratio'], 1)
        self.assertGreater(result['high_frequency_error_mean'], 0)
        self.assertGreater(result['edge_pixels'], 0)
        self.assertIsNotNone(result['edge_psnr_y_db'])

    def test_flicker_subtracts_motion_and_constant_bias(self):
        r = self.image.astype(np.float32)
        moved = np.roll(r, 1, axis=1)
        self.assertEqual(f.temporal(moved, moved+3, r, r+3)['residual_mean'], 0)
        flicker = f.temporal(r, r+3, r, r-3)
        self.assertEqual(flicker['static_residual_p99'], 6)
        self.assertEqual(flicker['residual_mean'], 6)

    def test_unexpected_black_and_presented_eye(self):
        dump(self.server, 1000, 'encoder_input', self.image)
        dump(self.client, 1000, 'post_decode', np.zeros_like(self.image))
        dump(self.client, 1000, 'presented_left', np.zeros((64, 64), np.uint8))
        report = f.score_directories(self.server, self.client)
        self.assertEqual(report['aggregate']['unexpected_black_pairs'], 1)
        self.assertEqual(report['aggregate']['unexpected_blank_pairs'], 1)
        self.assertEqual(report['aggregate']['presented_black_images'], 1)
        self.assertFalse(f.blank(np.full((32, 32), 100, np.float32))['black'])
        self.assertTrue(f.blank(np.full((32, 32), 100, np.float32))['blank'])

    def test_one_black_eye_does_not_hide_in_stereo_average(self):
        dump(self.server, 1000, 'encoder_input', self.image)
        decoded = self.image.copy()
        decoded[:, :64] = 0
        dump(self.client, 1000, 'post_decode', decoded)
        report = f.score_directories(self.server, self.client)
        self.assertEqual(report['aggregate']['unexpected_black_pairs'], 0)
        self.assertEqual(report['aggregate']['unexpected_black_decoded_eyes'], 1)

    def test_rgb_channel_order_and_full_planar_luma(self):
        meta, raw = dump(self.server, 1, 'encoder_input', self.image)
        rgba = np.zeros((64, 128, 4), np.uint8)
        rgba[..., 0] = 100
        raw.write_bytes(rgba.tobytes())
        np.testing.assert_allclose(f.luma((meta, raw)), 21.26, atol=.0001)
        meta['format'] = 'bgra8'
        np.testing.assert_allclose(f.luma((meta, raw)), 7.22, atol=.0001)
        meta['format'] = 'yuv444p'
        raw.write_bytes(self.image.tobytes()+bytes(64*128*2))
        np.testing.assert_array_equal(f.luma((meta, raw)), self.image)

    def test_blockiness_keeps_full_frame_phase_inside_crop(self):
        image = np.tile(((np.arange(128)//8)%2*20).astype(np.float32), (64, 1))
        crop = image[:, 3:]
        self.assertGreater(f.blockiness(crop, 8, origin=(0, 3)), 0)
        self.assertEqual(f.blockiness(crop, 8), 0)

    def test_matching_is_timestamp_not_index_or_discovery_order(self):
        dump(self.server, 3000, 'encoder_input', self.image, 5)
        dump(self.server, 1000, 'encoder_input', self.image, 9)
        dump(self.client, 3000, 'post_decode', self.image, 100)
        dump(self.client, 2000, 'post_decode', self.image, 5)
        report = f.score_directories(self.server, self.client)
        self.assertEqual(report['unmatched_server'], [1000])
        self.assertEqual(report['unmatched_client'], [2000])
        self.assertEqual(report['pairs'][0]['timestamp_ns'], 3000)
        self.assertIsNone(report['pairs'][0]['regions']['full']['temporal'])

    def test_rejects_duplicate_truncated_unknown_domain_and_wrong_geometry(self):
        record = dump(self.server, 1000, 'encoder_input', self.image)
        meta, raw = record
        raw.write_bytes(raw.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, 'truncated'): f.discover(self.server, f.STAGES)
        dump(self.server, 1000, 'encoder_input', self.image)
        dump(self.server/'other-run', 1000, 'encoder_input', self.image)
        with self.assertRaisesRegex(ValueError, 'duplicate'): f.discover(self.server, f.STAGES)
        dump(self.client, 1000, 'post_decode', np.zeros((64, 64), np.uint8))
        with self.assertRaisesRegex(ValueError, 'geometry'): f.score_directories(self.server/'other-run', self.client)
        meta['matrix'] = 'unknown'
        raw.with_suffix('.json').write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, 'color domain'): f.discover(self.server, f.STAGES)

    def test_planar_limited_luma_and_row_flip(self):
        image = np.tile(np.array([16, 235], np.uint8), (32, 32))
        record = dump(self.server, 1, 'encoder_input', image, fmt='yuv420p', color_range='limited')
        y = f.luma(record)
        self.assertEqual(float(y[:, 0].mean()), 0)
        self.assertEqual(float(y[:, 1].mean()), 255)
        record = dump(self.client, 2, 'post_decode', self.image[::-1], row_order='bottom_up')
        np.testing.assert_allclose(f.luma(record), self.image, atol=.0001)

    def test_fixed_crops_and_chart_geometry(self):
        projections = {'left': [-1, 1, -1, 1], 'right': [-1, 1, -1, 1]}
        boxes = f.fixed_crops(4160, 2208, chart_projections=projections)
        self.assertEqual(boxes['left_chart_lines'], (1130, 399, 411, 361))
        self.assertEqual(boxes['left_chart_stripes'], (430, 834, 1200, 117))
        self.assertEqual(boxes['right_chart_lines'][0], 3210)
        with self.assertRaises(ValueError): f.fixed_crops(128, 64, {'bad': [120, 0, 40, 30]})
        with self.assertRaises(ValueError): stereo_scene.quality_regions(100, 100, [0, 0, 0, 0])
        with self.assertRaises(ValueError): f.fixed_crops(128, 64, {'bad': 3})
        with self.assertRaises(ValueError): f.fixed_crops(128, 64, chart_projections={})

    def test_cli_output_and_pull_argument_vector(self):
        dump(self.server, 1, 'encoder_input', self.image)
        dump(self.client, 1, 'post_decode', self.image)
        out = self.root/'report.json'
        self.assertEqual(f.main(['score', '--server', str(self.server), '--client', str(self.client), '--out', str(out)]), 0)
        self.assertTrue(out.with_suffix('.md').is_file())
        with patch.object(f.subprocess, 'run') as run:
            target = self.root/'pulled'
            f.main(['pull', '--serial', 'test-serial', '--out', str(target)])
            run.assert_called_once_with(['adb', '-s', 'test-serial', 'pull', f.CLIENT_DIR.rstrip('/')+'/.', str(target)], check=True)


if __name__ == '__main__': unittest.main()

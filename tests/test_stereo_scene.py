import importlib.util
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from tools.quest3 import stereo_scene as scene


PROJECTION = (-1.0, 1.0, -1.0, 1.0)
RENDER_DEPS_AVAILABLE = importlib.util.find_spec('cv2') is not None and importlib.util.find_spec('numpy') is not None


@unittest.skipUnless(RENDER_DEPS_AVAILABLE, 'requires tools/quest3/requirements.txt')
class StereoScenePixelTests(unittest.TestCase):
    def test_flat_fields_are_neutral_and_exact(self):
        for code in (16, 24, 48, 128):
            image = scene.flat_field(31, 17, code)
            self.assertEqual(image.shape, (17, 31, 3))
            self.assertEqual(image.dtype.name, 'uint8')
            self.assertEqual(image.min(), code)
            self.assertEqual(image.max(), code)
            self.assertTrue((image[:, :, 0] == image[:, :, 1]).all())
            self.assertTrue((image[:, :, 1] == image[:, :, 2]).all())

    def test_neutral_patch_chart_has_all_source_codes(self):
        image = scene.eye_pattern(2048, 2048, 'LEFT', (32, 32, 200), PROJECTION,
                                  neutral_patches=True)
        for code in scene.NEUTRAL_RGB_CODES:
            self.assertTrue(((image == (code, code, code)).all(axis=2)).any())

    def test_normalized_reference_canvas_is_byte_identical_to_legacy_chart(self):
        width, height = scene.REFERENCE_CANVAS_EYE
        legacy = scene.eye_pattern(width, height, 'LEFT', (32, 32, 200), PROJECTION,
                                   quality=True, neutral_patches=True)
        normalized = scene.normalized_eye_pattern(width, height, 'LEFT', (32, 32, 200), PROJECTION,
                                                   quality=True, neutral_patches=True)
        self.assertTrue((legacy == normalized).all())

    def test_normalized_chart_scales_projected_panel_geometry(self):
        reference = scene.normalized_eye_pattern(*scene.REFERENCE_CANVAS_EYE, 'LEFT', (32, 32, 200), PROJECTION)
        scaled = scene.normalized_eye_pattern(4160, 4416, 'LEFT', (32, 32, 200), PROJECTION)
        reference_panel = (reference == (32, 32, 200)).all(axis=2)
        scaled_panel = (scaled == (32, 32, 200)).all(axis=2)
        ry, rx = reference_panel.nonzero()
        sy, sx = scaled_panel.nonzero()
        self.assertEqual((rx.min(), ry.min(), rx.max(), ry.max()), (590, 854, 1490, 1354))
        self.assertEqual((sx.min(), sy.min(), sx.max(), sy.max()), (1180, 1708, 2980, 2708))

    def test_normalized_eyes_keep_independent_local_boundaries(self):
        # Stereo submission takes two independent per-eye textures. Their panel placements
        # may differ with asymmetric frusta, but neither can spill or be scaled through a seam.
        left_projection = (-1.4, 1.0, -1.1, 1.1)
        right_projection = (-1.0, 1.4, -1.1, 1.1)
        left = scene.normalized_eye_pattern(3072, 3232, 'LEFT', (32, 32, 200), left_projection)
        right = scene.normalized_eye_pattern(3072, 3232, 'RIGHT', (200, 64, 32), right_projection)
        self.assertEqual(left.shape, (3232, 3072, 3))
        self.assertEqual(right.shape, (3232, 3072, 3))
        for image, color in ((left, (32, 32, 200)), (right, (200, 64, 32))):
            panel = (image == color).all(axis=2)
            y, x = panel.nonzero()
            self.assertGreater(x.min(), 0)
            self.assertLess(x.max(), image.shape[1] - 1)
            self.assertGreater(y.min(), 0)
            self.assertLess(y.max(), image.shape[0] - 1)


class StereoSceneCliTests(unittest.TestCase):
    def parser(self):
        return scene.build_parser()

    def assert_parser_exit(self, callback):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            callback()

    def test_flat_cli_metadata_and_chart_modes_are_exclusive(self):
        parser = self.parser()
        args = scene.validate_args(parser, parser.parse_args(['--out', 'out', '--flat', '48']))
        metadata = scene.scene_metadata(args, 3072, 3232, [PROJECTION, PROJECTION])
        self.assertEqual(metadata['flat_rgb_code'], 48)
        self.assertEqual(metadata['source_neutral_rgb_codes'], [48])
        self.assertFalse(metadata['quality_chart'])
        self.assertFalse(metadata['neutral_patch_chart'])
        self.assertFalse(metadata['normalized_chart'])
        self.assertIsNone(metadata['reference_canvas_eye'])
        self.assert_parser_exit(lambda: parser.parse_args(['--out', 'out', '--flat', '48', '--quality']))

    def test_flat_cli_rejects_out_of_range_codes(self):
        parser = self.parser()
        for value in ('-1', '256'):
            args = parser.parse_args(['--out', 'out', '--flat', value])
            self.assert_parser_exit(lambda: scene.validate_args(parser, args))

    def test_flat_cli_rejects_pulse_that_would_break_uniformity(self):
        parser = self.parser()
        args = parser.parse_args(['--out', 'out', '--flat', '24', '--pulse'])
        self.assert_parser_exit(lambda: scene.validate_args(parser, args))

    def test_source_eye_and_flat_normalization_exclusivity(self):
        parser = self.parser()
        for argv in (
            ['--source-eye', '0', '2208'],
            ['--source-eye', '2080', '-1'],
            ['--flat', '24', '--normalized-chart'],
        ):
            args = parser.parse_args(['--out', 'out', *argv])
            self.assert_parser_exit(lambda: scene.validate_args(parser, args))

    def test_normalized_source_eye_metadata(self):
        parser = self.parser()
        args = scene.validate_args(parser, parser.parse_args([
            '--out', 'out', '--normalized-chart', '--source-eye', '3072', '3232']))
        metadata = scene.scene_metadata(args, *args.source_eye, [])
        self.assertEqual(metadata['source_eye_size'], [3072, 3232])
        self.assertTrue(metadata['normalized_chart'])
        self.assertEqual(metadata['reference_canvas_eye'], [2080, 2208])

    def test_neutral_patch_metadata_is_explicit(self):
        parser = self.parser()
        args = scene.validate_args(parser, parser.parse_args(['--out', 'out', '--neutral-patches']))
        self.assertEqual(scene.scene_metadata(args, 10, 20, [])['source_neutral_rgb_codes'],
                         list(scene.NEUTRAL_RGB_CODES))

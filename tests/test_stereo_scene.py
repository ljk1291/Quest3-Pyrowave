import importlib.util
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
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


@unittest.skipUnless(RENDER_DEPS_AVAILABLE, 'requires tools/quest3/requirements.txt')
class StereoSceneStartupRecenterTests(unittest.TestCase):
    """The startup auto-recenter needs a continuous >60 degree mismatch for >2 s, within the first 10 s."""
    SIZE = (384, 416)

    @staticmethod
    def pose(valid, yaw=0.):
        import numpy as np
        from types import SimpleNamespace
        from tools.quest3 import bench_scene as bs
        matrix = bs.offset_matrix({'degrees': [yaw, 0., 0.], 'metres': [0, 0, 0]})
        return SimpleNamespace(bPoseIsValid=valid, mDeviceToAbsoluteTracking=SimpleNamespace(m=np.asarray(matrix[:3])))

    def step(self, bench, t, valid=True, yaw=0.):
        return scene.bench_pose_step(bench, self.pose(valid, yaw), t)

    def test_tracking_loss_restarts_the_pending_yaw_mismatch(self):
        from tools.quest3 import bench_scene as bs
        bench = bs.BenchScene(size=self.SIZE)
        self.assertIsNone(self.step(bench, .5, yaw=0)[1])
        self.assertIsNone(self.step(bench, 1, yaw=70)[1])       # 70 degree mismatch begins at 1 s
        self.assertIsNone(self.step(bench, 2, valid=False))     # tracking lost
        self.assertIsNone(self.step(bench, 3, valid=False))
        self.assertIsNone(self.step(bench, 4, yaw=70)[1])       # recovery: must not recenter at once (4-1 > 2)
        self.assertIsNone(self.step(bench, 5, yaw=70)[1])
        self.assertIsNone(self.step(bench, 6, yaw=70)[1])       # exactly 2 s of the new run is not yet > 2 s
        event = self.step(bench, 6.5, yaw=70)[1]
        self.assertEqual(event['reason'], 'startup_yaw')
        # The recenter re-anchored to the 70 degree heading: it is now the matched pose.
        self.assertIsNone(self.step(bench, 7, yaw=70)[1])

    def test_uninterrupted_mismatch_still_recenters_after_two_seconds(self):
        from tools.quest3 import bench_scene as bs
        bench = bs.BenchScene(size=self.SIZE)
        self.assertIsNone(self.step(bench, 1, yaw=70)[1])
        self.assertIsNone(self.step(bench, 3, yaw=70)[1])
        self.assertEqual(self.step(bench, 3.5, yaw=70)[1]['reason'], 'startup_yaw')

    def test_no_automatic_recenter_after_ten_seconds_even_across_tracking_loss(self):
        from tools.quest3 import bench_scene as bs
        bench = bs.BenchScene(size=self.SIZE)
        self.assertIsNone(self.step(bench, 8, yaw=70)[1])
        self.assertIsNone(self.step(bench, 9, valid=False))
        self.assertIsNone(self.step(bench, 10.5, yaw=70)[1])
        for t in (11, 14, 20, 60):
            self.assertIsNone(self.step(bench, t, yaw=70)[1])
        self.assertIsNone(bench._yaw_mismatch_since)

    def test_live_loop_skips_invalid_poses_and_restarts_the_mismatch_timer(self):
        import json
        import tempfile
        import time
        from types import SimpleNamespace
        import numpy as np
        from unittest import mock
        from tools.quest3 import bench_scene as bs

        # (time, valid, yaw degrees); the first entry is the initial anchoring pose.
        sequence = [(0, True, 0), (.5, True, 0), (1, True, 70), (2, False, 0), (3, False, 0), (4, True, 70),
                    (5, True, 70), (6, True, 70), (6.5, True, 70), (11, True, 0), (12, True, 0), (14, True, 0)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stop = root/'stop'

            class PoseType:
                def __mul__(self, count):
                    return lambda: [SimpleNamespace(bPoseIsValid=True, mDeviceToAbsoluteTracking=SimpleNamespace(m=np.eye(4)[:3]))
                                    for _ in range(count)]

            class Compositor:
                calls = 0
                now = 0.
                def waitGetPoses(self, poses, _):
                    now, valid, yaw = sequence[min(self.calls, len(sequence)-1)]
                    self.calls += 1
                    self.now = now
                    poses[0].bPoseIsValid = valid
                    poses[0].mDeviceToAbsoluteTracking.m = bs.offset_matrix({'degrees': [yaw, 0., 0.], 'metres': [0, 0, 0]})[:3]
                    if self.calls >= len(sequence):
                        stop.touch()
                def submit(self, eye, texture, bounds):
                    pass

            class GL:
                counter = 0
                def __getattr__(self, name):
                    if name.startswith('GL_'): return name
                    return lambda *args: None
                def glGenTextures(self, n):
                    self.counter += 1; return self.counter
                glGenFramebuffers = glGenTextures
                def glCheckFramebufferStatus(self, *args): return 'GL_FRAMEBUFFER_COMPLETE'

            compositor = Compositor()
            vr = SimpleNamespace(Eye_Left=0, Eye_Right=1, TrackedDevicePose_t=PoseType(), k_unMaxTrackedDeviceCount=1,
                                 k_unTrackedDeviceIndex_Hmd=0, Texture_t=SimpleNamespace, VRTextureBounds_t=SimpleNamespace,
                                 TextureType_OpenGL=1, ColorSpace_Gamma=2)
            system = SimpleNamespace(getProjectionRaw=lambda eye: (-1, 1, -1, 1),
                                     getEyeToHeadTransform=lambda eye: SimpleNamespace(m=np.array([[1, 0, 0, .032 if eye else -.032], [0, 1, 0, 0], [0, 0, 1, 0]])))
            clock = SimpleNamespace(monotonic=lambda: compositor.now, time_ns=time.time_ns)
            args = scene.build_parser().parse_args(['--out', str(root), '--bench', '--bench-backdrop', 'none',
                                                    '--bench-motion', 'none', '--stop-file', str(stop), '--seconds', '100'])
            with mock.patch.object(scene, 'time', clock), redirect_stdout(io.StringIO()):
                scene.run_bench(args, root, system, compositor, *self.SIZE, GL(), vr)
            records = [json.loads(line) for line in (root/'frames.ndjson').read_text().splitlines()]

        # Only valid poses are submitted/logged: the two invalid entries (2 s and 3 s) are skipped.
        self.assertEqual(len(records), len(sequence)-1-2)
        events = [(i, r['recenter']['reason']) for i, r in enumerate(records) if 'recenter' in r]
        # Valid poses: 0.5, 1, 4, 5, 6, 6.5 (recenter), 11, 12, 14 -> index 5 only; none after 10 s.
        self.assertEqual(events, [(5, 'startup_yaw')])


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

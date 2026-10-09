import hashlib
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from tools.quest3 import bench_calibration as calibration, bench_colour as colour
from tools.quest3 import bench_registration as reg, bench_scene as scene, stereo_scene


def test_layout_pixels_and_independent_margin_landmarks(tmp_path):
    chart = scene.CalibrationScene(size=(3072, 3232))
    assert chart.calibration == colour.layout(chart.size)
    assert len(chart.calibration) == 300
    patch_mask = np.zeros(chart.size[::-1], bool)
    for patch in chart.calibration:
        x, y, w, h = patch['box']
        x0, y0, x1, y1 = np.ceil(np.array([x, y, x+w, y+h])-.5).astype(int)
        assert np.all(chart.panel[y0:y1, x0:x1] == patch['rgb'])
        patch_mask[y0:y1, x0:x1] = True
    for x, y in chart.landmarks:
        r = int(np.ceil(chart.spot_sigma*4))
        assert not patch_mask[y-r:y+r+1, x-r:x+r+1].any()
    points = np.array(chart.landmarks)
    held = reg.spatial_split(points, chart.size)
    counts, _, _ = np.histogram2d(*points[held].T, bins=4, range=[[0, chart.size[0]], [0, chart.size[1]]])
    assert counts.min() >= 3
    assert scene.decode_barcode(chart.render_frame(987), chart.barcode_box) == 987
    chart.save(tmp_path)
    replay = scene.BenchScene.from_metadata(tmp_path)
    assert replay.layout_hash == chart.layout_hash
    np.testing.assert_array_equal(replay.render_frame(987, 'right'), chart.render_frame(987))
    moved = scene.offset_matrix({'degrees': [20, -15, 5], 'metres': [.3, .1, -.2]})
    assert chart.frame_geometry(987, moved)['eyes'] == chart.frame_geometry(987)['eyes']


def test_mocked_gl_submissions_match_cpu_pixels(tmp_path, capsys):
    class PoseType:
        def __mul__(self, count):
            return lambda: [SimpleNamespace(bPoseIsValid=True, mDeviceToAbsoluteTracking=SimpleNamespace(m=np.eye(4)[:3])) for _ in range(count)]

    class GL:
        counter = 0
        images = {}
        def __getattr__(self, name):
            if name.startswith('GL_'): return name
            if name in ('glBegin', 'glBlitFramebuffer', 'glGenFramebuffers'):
                raise AssertionError('calibration must not transform or resolve the raster')
            return lambda *args: None
        def glGenTextures(self, count):
            self.counter += 1
            return self.counter
        def glBindTexture(self, target, texture): self.texture = texture
        def glTexImage2D(self, *args): self.images[self.texture] = args[-1].copy()
        def glTexSubImage2D(self, target, level, x, y, w, h, fmt, kind, pixels):
            self.images[self.texture][y:y+h, x:x+w] = pixels

    gl = GL()
    stop = tmp_path/'stop'
    chart = scene.CalibrationScene(size=(656, 688))
    class Compositor:
        submissions = 0
        handles = set()
        def waitGetPoses(self, poses, _):
            poses[0].mDeviceToAbsoluteTracking.m = scene.offset_matrix({'degrees': [30, 5, 0], 'metres': [.2, 0, 0]})[:3]
        def submit(self, eye, texture, bounds):
            assert (bounds.uMin, bounds.uMax, bounds.vMin, bounds.vMax) == (0, 1, 1, 0)
            np.testing.assert_array_equal(gl.images[texture.handle], chart.render_frame(self.submissions//2))
            self.handles.add(texture.handle)
            self.submissions += 1
            if self.submissions == 6: stop.touch()

    compositor = Compositor()
    vr = SimpleNamespace(Eye_Left=0, Eye_Right=1, TrackedDevicePose_t=PoseType(), k_unMaxTrackedDeviceCount=1,
                         k_unTrackedDeviceIndex_Hmd=0, Texture_t=SimpleNamespace, VRTextureBounds_t=SimpleNamespace,
                         TextureType_OpenGL=1, ColorSpace_Gamma=2)
    system = SimpleNamespace(getProjectionRaw=lambda eye: (-1, 1, -1, 1),
                             getEyeToHeadTransform=lambda eye: SimpleNamespace(m=np.eye(4)[:3]))
    parser = stereo_scene.build_parser()
    args = stereo_scene.validate_args(parser, parser.parse_args([
        '--out', str(tmp_path), '--bench', '--bench-calibration', scene.CALIBRATION_LAYOUT,
        '--stop-file', str(stop), '--seconds', '100']))
    stereo_scene.run_bench(args, tmp_path, system, compositor, *chart.size, gl, vr)
    assert compositor.submissions == 6 and len(compositor.handles) == 2
    assert '[Q3PW_BENCH_CALIBRATION]' in capsys.readouterr().out
    replay = scene.BenchScene.from_metadata(tmp_path)
    np.testing.assert_array_equal(replay.render_frame(2), chart.render_frame(2))
    with pytest.raises(ValueError, match='no render-pose'):
        replay.render_frame(3)


@pytest.fixture(scope='module')
def synthetic(tmp_path_factory):
    root = tmp_path_factory.mktemp('calibration')
    chart_dir, burst, output = root/'chart', root/'burst', root/'manifest'
    burst.mkdir()
    chart = scene.CalibrationScene(size=(3072, 3232))
    chart.save(chart_dir)
    model = {'gain': [.95, 1.05, .90], 'offset': [.005, .010, .002], 'radial': [[0, 0, 0], [0, 0, 0]]}
    lut = np.rint(colour.apply(np.repeat(np.arange(256)[:, None], 3, axis=1), model, np.full((256, 2), .5))).clip(0, 255).astype(np.uint8)
    eyes, polygons = [], []
    for side in (0, 1):
        lens = reg.Lens((2064, 2208), [.055, .007])
        angle = np.deg2rad(1.3 if side == 0 else -1.1)
        rotate = np.array([[np.cos(angle), -np.sin(angle), .37/lens.scale],
                           [np.sin(angle), np.cos(angle), -.23/lens.scale], [0, 0, 1.]])
        mapping = reg.PlaneMap(lens, rotate @ np.array([[1.8/chart.size[0], 0, -.9], [0, 1.88/chart.size[1], -.94], [0, 0, 1]]))
        polygons.append(calibration.patch_polygons(chart, mapping))
        pixels = chart.render_frame(42)
        pixels = np.stack([lut[pixels[..., c], c] for c in range(3)], axis=-1)
        coords = mapping.grid(lens.size, inverse=True)
        eyes.append(cv2.remap(pixels, coords[..., 0], coords[..., 1], cv2.INTER_LINEAR, borderValue=(0, 0, 0)))
    stereo = np.concatenate(eyes, axis=1)
    assert stereo.dtype == np.uint8 and stereo.shape == (2208, 4128, 3)
    assert cv2.imwrite(str(burst/'shot.png'), stereo[..., ::-1])
    damaged = stereo.copy()
    for side, quads in enumerate(polygons):
        for n, value in ((0, 0), (1, 255)):
            cv2.fillConvexPoly(damaged, np.rint(quads[n]+[side*2064, 0]).astype(np.int32), (value,)*3)
    assert cv2.imwrite(str(burst/'damaged.png'), damaged[..., ::-1])
    assert cv2.imwrite(str(burst/'missing.png'), np.zeros_like(stereo))
    report = calibration.build(chart_dir, burst, output)
    return root, chart, model, report


def test_real_detection_lens_manifest_recovers_colour(synthetic):
    root, chart, expected, report = synthetic
    assert report['scores_available'], json.dumps(report, indent=2)
    assert len([s for s in report['shots'] if s['status'] == 'accepted']) == 4
    assert all('reason' in s for s in report['shots'] if s['status'] == 'excluded')
    fitted, digest = colour.load_burst(root/'manifest')
    assert digest == report['calibration_id']
    rgb = np.array([p['rgb'] for p in chart.calibration])
    uv = np.array([p['uv'] for p in chart.calibration])
    for side in ('left', 'right'):
        actual = colour.apply(rgb, fitted[side][0], uv)
        np.testing.assert_allclose(actual, colour.apply(rgb, expected, uv), atol=.5)
        # Gain and black-offset recovery in output-code units, including black.
        ramp = np.repeat(np.arange(225)[:, None], 3, axis=1)
        positions = np.full((len(ramp), 2), .5)
        np.testing.assert_allclose(colour.apply(ramp, fitted[side][0], positions),
                                   colour.apply(ramp, expected, positions), atol=.5)
        for split in ('training', 'selection', 'held_out'):
            assert report['eyes'][side][split]['rmse_codes'] < .5
            assert report['eyes'][side][split]['p95_codes'] < 1
    manifest = json.loads((root/'manifest/calibration.json').read_text())
    for side in ('left', 'right'):
        shot = manifest['eyes'][side][0]
        assert np.shape(shot['polygons']) == (300, 4, 2)
        assert cv2.imread(str(root/'manifest'/shot['file'])).shape == (2208, 2064, 3)
        damaged = next(s for s in manifest['eyes'][side] if s['source_file'] == 'damaged.png')
        assert [p['patch_index'] for p in damaged['excluded_patches']] == [0, 1]
        assert np.all(np.array(damaged['polygons'])[:2] == -10000)
        coefficients = [s['lens_coefficients'] for s in report['shots'] if s['eye'] == side and s['status'] == 'accepted']
        assert coefficients[0] == coefficients[1]


def test_spatial_holdout_failure_excludes_shots(synthetic, tmp_path, monkeypatch):
    root, _, _, _ = synthetic
    original = calibration.detect_spots
    def damaged_holdout(capture, chart, initial):
        source, target = original(capture, chart, initial)
        held = reg.spatial_split(source, chart.size)
        target[held & (source[:, 0] > chart.size[0]/2), 0] += .6
        return source, target
    monkeypatch.setattr(calibration, 'detect_spots', damaged_holdout)
    scene.write_json(tmp_path/'burst.json', {'shots': [{'file': str(root/'burst/shot.png')}]})
    report = calibration.build(root/'chart', tmp_path, tmp_path/'manifest')
    assert not report['scores_available']
    assert all('spatial-holdout geometry' in s['reason'] for s in report['shots'])
    manifest = json.loads((tmp_path/'manifest/calibration.json').read_text())
    assert manifest['eyes'] == {'left': [], 'right': []}


def test_missing_clipped_and_small_patches_are_excluded():
    image = np.full((40, 40, 3), 64, np.uint8)
    visible = np.ones((40, 40), bool)
    quad = np.array([[5, 5], [30, 5], [30, 30], [5, 30]], float)
    np.testing.assert_array_equal(calibration.sample_patch(image, quad, visible)[0], [64]*3)
    assert calibration.sample_patch(image, quad-10, visible)[1] == 'patch outside capture'
    assert calibration.sample_patch(image, quad*.1, visible)[1] == 'patch has fewer than 16 sample pixels'
    visible[20, 20] = False
    assert calibration.sample_patch(image, quad, visible)[1] == 'patch hidden or missing'
    for value in (0, 255):
        assert calibration.sample_patch(image*0+value, quad, visible | True)[1] == 'patch clipped in colour'


def test_default_scene_frozen_pixels(tmp_path):
    default = scene.BenchScene(seed=17, size=(656, 688), backdrop='none')
    assert hashlib.sha256(default.render_frame(91, 'right').tobytes()).hexdigest() == '66af6d5c2670393fa59a9ac4280f4fd4f777c9bcf07005603e4baaac31ec98d9'
    default.save(tmp_path)
    metadata = default.metadata()
    metadata['renderer_sha256'] = scene.V4_RENDERER
    scene.write_json(tmp_path/'bench.json', metadata)
    replay = scene.BenchScene.from_metadata(tmp_path)
    np.testing.assert_array_equal(replay.render_frame(91, 'right'), default.render_frame(91, 'right'))

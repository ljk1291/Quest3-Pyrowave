import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.quest3 import bench_detail as detail, bench_registration as reg, bench_score as score
from tools.quest3.bench_scene import BenchScene, offset_matrix, panel_anchor, write_json, V3_RENDERER
from tools.quest3.bench_render_analysis import analyze, render_region
from tools.quest3.bench_lens_score import sample_source, capture_visibility
from ws.scripts import bench_offline


def test_detail_block_drop_and_missing_visibility():
    rng = np.random.default_rng(34)
    truth = rng.uniform(20, 180, (128, 128)).astype(np.float32)
    output = truth.copy()
    output[:64, :64] = 90
    mask = np.ones(truth.shape, bool)
    baseline = detail.retention(detail.energy(truth), detail.energy(truth), mask, mask)
    dropped = detail.retention(detail.energy(truth), detail.energy(output), mask, mask)
    assert np.allclose(baseline['retained'], 1)
    samples = [{**data, 'eye': 'left', 'sample_id': str(i)} for i, data in enumerate((baseline, dropped, baseline))]
    result = detail.temporal(samples)
    assert result['detail_toggle_fraction'] == pytest.approx(.25)
    assert result['detail_std_p99'] > .4
    mask[:64, :64] = False
    hidden = detail.retention(detail.energy(truth), detail.energy(output), np.ones_like(mask), mask)
    samples[1].update(hidden)
    assert detail.temporal(samples)['detail_toggle_fraction'] == 0
    # Flat truth is unavailable, not perfect retained detail.
    zero = np.zeros((128, 128), np.float32)
    assert not detail.retention(zero, zero, mask, mask)['ids']


def test_detail_duplicate_samples_not_temporal_and_two_eyes():
    a = {'ids': [1], 'retained': [.2], 'eye': 'left', 'sample_id': 'one'}
    b = {**a, 'retained': [1.], 'eye': 'right'}
    assert detail.temporal([a, a, b])['detail_temporal_blocks'] == 0


def test_lens_hidden_area_is_not_codec_detail_loss():
    capture = np.full((128, 128, 3), 28, np.uint8)
    capture[:, :16] = 0
    capture[48:80, 48:80] = 0
    valid = capture_visibility(capture)
    assert not valid[:, :19].any()
    assert valid[60:70, 60:70].all()  # real interior black remains content


def test_recentering_preserves_planes_and_file_is_consumed(tmp_path):
    scene = BenchScene(size=(384, 416), backdrop='mosaic')
    scene.save(tmp_path/'scene')  # metadata remains at the original anchor
    relative = np.linalg.inv(scene.anchor) @ scene.backdrop.anchor
    pose = offset_matrix({'degrees': [105, 12, -8], 'metres': [.7, 1.6, .4]})
    request = tmp_path/'recenter'
    request.touch()
    event = scene.maybe_recenter(pose, 30, request)
    assert event['reason'] == 'file' and not request.exists()
    np.testing.assert_allclose(scene.anchor, panel_anchor(pose))
    np.testing.assert_allclose(np.linalg.inv(scene.anchor) @ scene.backdrop.anchor, relative, atol=1e-12)
    assert scene.anchor[1, 3] == 1.6
    assert scene.maybe_recenter(pose, 31, request) is None
    scene.live = True
    scene.frame_records[0] = scene.frame_geometry(0, pose)
    record = scene.frame_geometry(31, pose); record['recenter'] = event
    scene.frame_records[31] = record
    (tmp_path/'scene/frames.ndjson').write_text(json.dumps(record)+'\n')
    replay = BenchScene.from_metadata(tmp_path/'scene')
    np.testing.assert_array_equal(replay.render_frame(31), scene.render_frame(31, homography=np.array(record['eyes'][0]['panel_to_eye'])))


def test_startup_yaw_is_continuous_and_wrap_safe():
    scene = BenchScene(size=(384, 416))
    pose = offset_matrix({'degrees': [70, 0, 0], 'metres': [0, 1.6, 0]})
    assert scene.maybe_recenter(pose, 1) is None
    assert scene.maybe_recenter(np.eye(4), 2) is None
    assert scene.maybe_recenter(pose, 3) is None
    assert scene.maybe_recenter(pose, 5) is None
    assert scene.maybe_recenter(pose, 5.01)['reason'] == 'startup_yaw'
    assert scene.maybe_recenter(np.eye(4), 8) is None
    assert scene.maybe_recenter(np.eye(4), 10.1) is None
    # +/-180 degrees are adjacent, not a startup mismatch.
    p = offset_matrix({'degrees': [179, 0, 0], 'metres': [0, 0, 0]})
    scene.recenter(p, 'test')
    p = offset_matrix({'degrees': [-179, 0, 0], 'metres': [0, 0, 0]})
    assert scene.maybe_recenter(p, 1) is None
    assert scene.maybe_recenter(p, 4) is None


def test_v3_replay_only_audited_hash(tmp_path):
    scene = BenchScene(size=(384, 416))
    scene.save(tmp_path)
    meta = scene.metadata(); meta.update(version=3, renderer_sha256=V3_RENDERER)
    meta.pop('backdrop_filter')
    write_json(tmp_path/'bench.json', meta)
    np.testing.assert_array_equal(BenchScene.from_metadata(tmp_path).render_frame(9), scene.render_frame(9))
    meta['renderer_sha256'] = 'not-audited'
    write_json(tmp_path/'bench.json', meta)
    with pytest.raises(ValueError, match='renderer changed'):
        BenchScene.from_metadata(tmp_path)


def test_inverse_lens_roundtrip_and_burst_fit():
    lens = reg.Lens((700, 720), [.23, .08, .01, .002, -.003, .1, -.04])
    yy, xx = np.mgrid[60:660:60, 60:660:60]
    p = np.stack((xx, yy), -1).reshape(-1, 2).astype(float)
    np.testing.assert_allclose(lens.distort(lens.undistort(p)), p, atol=1e-5)
    pairs = []
    for angle in (-.07, .02, .12):
        h = np.array([[.0014, angle*.0014, -.45], [-angle*.0014, .0014, -.5], [.00002, 0, 1]])
        pairs.append((p, reg.PlaneMap(lens, h).forward(p)))
    maps, diagnostics = reg.fit_burst(pairs, lens.size, iterations=80)
    assert max(d['corner_fit_rms_capture_px'] for d in diagnostics) < .02
    assert maps[0].lens is maps[1].lens


@pytest.mark.parametrize('backdrop', ['none', 'metro'])
def test_lens_lossless_barrel_roll_translation(tmp_path, backdrop):
    asset = None
    if backdrop == 'metro':
        asset = tmp_path/'texture.png'
        rng = np.random.default_rng(381)
        pixels = rng.integers(20, 220, (64, 64, 3), dtype=np.uint8)
        cv2.imwrite(str(asset), cv2.resize(pixels, (656, 688), interpolation=cv2.INTER_CUBIC))
    scene = BenchScene(size=(656, 688), motion='tremor', backdrop=backdrop, backdrop_asset=asset)
    lens = reg.Lens((656, 688), [.20, .07, .01, .001, -.002, .04, -.03])
    for index in (0, 5, 10, 15):
        # Radial/tangential lens plus changing roll and subpixel translation.
        angle = np.deg2rad(2+index*.1)
        c, s = np.cos(angle), np.sin(angle)
        matrix = np.array([[.8*c, -.8*s, 52.3+index*.2], [.8*s, .8*c, 42.7-index*.1], [0, 0, 1.]])
        norm = np.array([[1/lens.scale, 0, -lens.centre[0]/lens.scale], [0, 1/lens.scale, -lens.centre[1]/lens.scale], [0, 0, 1.]])
        mapping = reg.PlaneMap(lens, norm @ matrix)
        coords = mapping.grid(lens.size, inverse=True)
        image = scene.render_frame(index)
        capture = cv2.remap(image, coords[..., 0], coords[..., 1], cv2.INTER_LINEAR, borderValue=(28, 28, 28))
        cv2.imwrite(str(tmp_path/f'{index:03}.png'), capture[..., ::-1])
    write_json(tmp_path/'burst.json', {'shots': [{'file': f'{i:03}.png'} for i in (0, 5, 10, 15)]})
    report = score.score_compositor(tmp_path, scene, 'single', registration='lens')
    # Estimated landmarks and the old colour strip no longer validate a
    # lossless fixture merely because its global fit looks plausible.
    assert report['sample_count'] == 0 and report['diagnostic_sample_count'] == 4
    assert len({tuple(s['lens_coefficients']) for s in report['registration_shots']}) == 1
    assert all(not s['colour']['scores_available'] for s in report['registration_shots'])
    assert set(report['registration_controls']) == {'0.25', '0.5'}
    json.dumps(report, allow_nan=False)


def test_offline_four_budget_plan_no_gpu(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bench_offline.WindowGuard, 'status', lambda *a: pytest.fail('GPU called'))
    bench_offline.main(['--out', str(tmp_path/'out'), '--work', str(tmp_path/'work'), '--dry-run',
                       '--mbps-list', '1000', '1500', '2000', '3000', '--size', '384', '416'])
    plan = json.loads(capsys.readouterr().out)
    assert len(plan['jobs']) == 8
    assert len({j['name'] for j in plan['jobs']}) == 8
    for job in plan['jobs']:
        assert job['cap_bytes'] == int(job['mbps']*1e6/8/90)
        assert int(job['encode'][-1]) == job['cap_bytes']
    assert not (tmp_path/'work').exists()


def test_offline_four_budgets_execute_both_profiles_with_fake_codec(tmp_path, monkeypatch):
    pair = tmp_path/'out/fake/windows'
    pair.mkdir(parents=True)
    for name in ('pyrowave-encode.exe', 'pyrowave-decode.exe'):
        (pair/name).write_bytes(b'CPU fake; never executed')
    monkeypatch.setattr(bench_offline, 'ROOT', tmp_path)
    caps = []
    class Guard:
        def __init__(self, *a, **kw): pass
        def status(self): return {}
        def run(self, command, **kw):
            if 'encode.exe' in command[0]: caps.append(int(command[3]))
            Path(command[2]).write_bytes(Path(command[1]).read_bytes())
            return 0, 'CDF 5/3', ''
    monkeypatch.setattr(bench_offline, 'WindowGuard', Guard)
    bench_offline.main(['--pair', 'fake', '--out', str(tmp_path/'result'), '--work', str(tmp_path/'scratch'),
                       '--window', 'fake', '--frames', '2', '--size', '384', '416', '--bench-backdrop', 'none',
                       '--mbps-list', '1000', '1500', '2000', '3000'])
    assert caps == [int(rate*1e6/8/90) for rate in (1000, 1500, 2000, 3000) for _ in range(2)]
    reports = list((tmp_path/'result').glob('*mbps-*/summary.json'))
    assert len(reports) == 8
    assert len(list((tmp_path/'result').glob('*mbps-compare.md'))) == 4
    assert not list((tmp_path/'scratch').iterdir())


def test_exact_lens_residual_not_inverse_blur():
    scene = BenchScene(size=(656, 688), motion='tremor')
    acc = score.ScoreAccumulator(scene, 'compositor')
    for index in (0, 5, 10):
        lens = reg.Lens((656, 688), [.21, .06, .01, .002, -.001, .02, 0])
        transform = np.array([[.8, -.02-index*.001, 50.2+index*.1], [.02+index*.001, .8, 46.8], [0, 0, 1.]])
        norm = np.array([[1/lens.scale, 0, -lens.centre[0]/lens.scale], [0, 1/lens.scale, -lens.centre[1]/lens.scale], [0, 0, 1.]])
        source_map = reg.PlaneMap(lens, norm @ transform)
        coords = source_map.grid(lens.size, inverse=True)
        source = scene.render_frame(index).astype(np.float32)
        capture = cv2.remap(source, coords[..., 0], coords[..., 1], cv2.INTER_LINEAR, borderValue=(28, 28, 28))
        panel_map = reg.PlaneMap(lens, norm @ transform @ scene.homography(index))
        reference, valid = sample_source(source, panel_map, scene.homography(index))
        acc.add(score.rgb_planes(reference), score.rgb_planes(capture), index, score.erode(valid, 2), homography=panel_map)
    report = acc.finish()
    assert max(report['aggregate'][name]['mse_y']['mean'] for name in ('sat', 'mura', 'edge', 'natural')) < .0001
    assert report['aggregate']['edge']['flicker_p99']['mean'] < .001


def test_partial_barcode_requires_unique_logged_packet():
    from types import SimpleNamespace
    from tools.quest3.bench_scene import barcode_bits
    capture = np.repeat(cv2.resize((20+215*barcode_bits(123)).astype(np.uint8), (280, 80), interpolation=cv2.INTER_NEAREST)[..., None], 3, axis=2)
    capture[:, :60] = 0
    scene = SimpleNamespace(barcode_box=(0, 0, 280, 80), frame_records={123: {'render_unix_ns': 101_000_000_000}})
    lens = reg.Lens((280, 80))
    norm = np.array([[1/lens.scale, 0, -lens.centre[0]/lens.scale], [0, 1/lens.scale, -lens.centre[1]/lens.scale], [0, 0, 1.]])
    mapping = reg.PlaneMap(lens, norm)
    index, info = reg.barcode_index(capture, mapping, scene, {'start_s': 100, 'seconds': 2})
    assert index == 123 and info['partial_barcode']
    scene.frame_records = {}
    with pytest.raises(ValueError, match='ambiguous'):
        reg.barcode_index(capture, mapping, scene, {'start_s': 100, 'seconds': 2})


def test_large_map_approximation_visible_error():
    lens = reg.Lens((2064, 2208), [.3, .1, .08, .001, -.002, .1, .01])
    mapping = reg.PlaneMap(lens, np.array([[.001, 0, -1], [0, .001, -.8], [0, 0, 1.]]))
    grid = mapping.grid((2200, 1800))
    yy, xx = np.mgrid[100:1700:113, 100:2100:127]
    exact = mapping.forward(np.stack((xx, yy), -1))
    assert np.max(np.linalg.norm(grid[yy, xx]-exact, axis=-1)) < .02


@pytest.mark.parametrize('mode', ['ss4', 'cubic4'])
def test_truth_analysis_static_and_filter_reference(tmp_path, mode):
    scene = BenchScene(size=(656, 688), motion='none', backdrop='mosaic', panel='off')
    x, y, w, h = scene.backdrop.central_box
    roi = (32*((x+128)//32), 32*((y+128)//32), 256, 192)
    result = analyze(scene, [0, 1], roi)
    for metrics in result['aggregate'].values():
        assert metrics['detail_std_p99'] == 0
        assert metrics['detail_toggle_fraction'] == 0
    scene.backdrop_filter = mode
    rendered = scene.render_frame(0)
    background = render_region(scene, scene.homography(0, 'left', 'backdrop'), [0, 0, *scene.size], mode)
    valid = score.erode(scene.backdrop_visibility(0), 3)
    np.testing.assert_array_equal(rendered[valid], background[valid])



def test_frozen_lens_reduces_thin_column_and_rejects_folds():
    yy, xx = np.mgrid[50:650:40, 50:75:8]
    points = np.stack((xx, yy), -1).reshape(-1, 2).astype(float)
    observed = points+np.random.default_rng(2).normal(0, .2, points.shape)
    maps, diagnostics = reg.fit_burst([(points, observed)], (700, 720))
    assert diagnostics[0]['lens_parameters'] == 0
    assert np.all(maps[0].lens.coefficients == 0)
    folded = reg.Lens((700, 720), [-.5])
    with pytest.raises(ValueError, match='injectivity'):
        folded.distort(folded.undistort(points))


def test_spatial_holdouts_and_local_tail_validation():
    lens = reg.Lens((400, 400))
    mapping = reg.PlaneMap(lens, np.array([[.005, 0, -1], [0, .005, -1], [0, 0, 1.]]))
    yy, xx = np.mgrid[10:400:20, 10:400:20]
    points = np.stack((xx, yy), -1).reshape(-1, 2).astype(float)
    held = reg.spatial_split(points, (400, 400))
    assert held.any() and (~held).any()
    target = mapping.forward(points)
    good = reg.validate_plane(mapping, points[held], target[held], np.ones((400, 400), bool))
    assert good['scores_available']
    json.dumps(good, allow_nan=False)
    target[(points[:, 0] > 300) & (points[:, 1] > 300), 0] += .4
    bad = reg.validate_plane(mapping, points[held], target[held], np.ones((400, 400), bool))
    assert bad['held_out_median_px'] < .1 and not bad['scores_available']
    assert any(row['p95_px'] > .25 for row in bad['local'])
    narrow = reg.validate_plane(mapping, points[held & (points[:, 0] < 100)], target[held & (points[:, 0] < 100)], np.ones((400, 400), bool))
    assert not narrow['scores_available']
    # Interpolation with only three points/cell can understate the pooled p95.
    sparse = np.array([[x+dx, y+20] for y in range(0, 400, 100)
                       for x in range(0, 400, 100) for dx in (10, 30, 50)], float)
    observed = mapping.forward(sparse)
    observed[2::3, 0] += .26
    pooled = reg.validate_plane(mapping, sparse, observed, np.ones((400, 400), bool))
    assert all(c['valid'] for c in pooled['local'])
    assert pooled['held_out_p95_px'] > .25 and not pooled['scores_available']


def test_detail_full_class_filter_support_and_signed_correlation():
    rng = np.random.default_rng(7)
    truth = rng.uniform(20, 180, (192, 192)).astype(np.float32)
    region = np.zeros(truth.shape, bool); region[32:160, 32:160] = True
    truth[region] = 80
    output = truth.copy(); output[~region] = 80
    valid = np.ones_like(region)
    retained = detail.retention(detail.energy(truth), detail.energy(output), region, valid)
    assert retained['ids'] == []  # flat inside; exterior texture cannot meet the floor
    truth = rng.uniform(20, 180, truth.shape).astype(np.float32)
    reverse = 200-truth
    energy = detail.retention(detail.energy(truth), detail.energy(reverse), valid, valid)
    correlated = detail.correlation(truth, reverse, valid, valid)
    np.testing.assert_allclose(energy['retained'], 1, atol=1e-6)
    np.testing.assert_allclose(correlated['retained'], -1, atol=1e-6)


def colour_observations(model):
    from tools.quest3 import bench_colour
    patches = bench_colour.layout((1000, 1000))
    observed = bench_colour.apply(np.array([p['rgb'] for p in patches]), model, np.array([p['uv'] for p in patches]))
    return [{**p, 'observed': value.tolist()} for p, value in zip(patches, observed)]


@pytest.mark.parametrize('radial', [False, True])
def test_full_eye_colour_spatial_selection_and_validation(radial):
    from tools.quest3 import bench_colour
    model = {'domain': 'linear-eye', 'gain': [1.03, .96, 1.07], 'offset': [.001, .002, .001],
             'radial': [[.2, .15, .1], [.05, .03, .02]] if radial else np.zeros((2, 3)).tolist()}
    observations = colour_observations(model)
    fitted, info = bench_colour.fit(observations)
    assert info['scores_available'] and info['radial_selected'] == radial
    assert info['held_out_rmse_codes'] < .001
    np.testing.assert_allclose(fitted['gain'], model['gain'], atol=1e-6)
    # Final validation cells were never used for model selection or fitting.
    for row in observations:
        if (row['cell'][0]+2*row['cell'][1]) % 5 == 0:
            row['observed'] = (np.array(row['observed'])+5).tolist()
    changed, info = bench_colour.fit(observations)
    assert changed == fitted and not info['scores_available']


def test_full_eye_colour_rejects_strip_and_missing_dark_neutrals():
    from tools.quest3 import bench_colour
    observations = colour_observations({'domain': 'linear-eye', 'gain': [1., 1., 1.], 'offset': [0., 0., 0.], 'radial': [[0., 0., 0.]]*2})
    with pytest.raises(ValueError, match='25 spatial cells'):
        bench_colour.fit([o for o in observations if o['cell'][0] == 0])
    with pytest.raises(ValueError, match='dark neutrals'):
        bench_colour.fit([o for o in observations if o['patch'] != 0])


def test_perturbed_lossless_controls_report_noise_not_codec_error():
    from tools.quest3 import bench_noise
    scene = BenchScene(size=(656, 688), motion='static')
    truth = scene.panel_frame(0).astype(np.float32)
    controls = {}
    for step in (.25, .5):
        acc = score.ScoreAccumulator(scene, 'compositor', record_spatial=False)
        for n in range(6):
            acc.add(score.rgb_planes(truth), score.rgb_planes(bench_noise.shift(truth, step if n % 2 else 0)), n, panel=True)
        controls[str(step)] = acc.finish()
    report = controls['0.25']
    bench_noise.annotate(report, controls)
    row = report['aggregate']['sat']['block_rms_p99']
    assert row['registration_noise_floor'] > 0
    assert row['registration_interpretation'] == 'within registration noise'
    assert not bench_noise.qualified(controls['0.5']['aggregate'])


def test_failed_sample_does_not_clear_other_validated_samples(tmp_path, monkeypatch):
    from tools.quest3 import bench_lens_score as lens_score, bench_colour, bench_noise
    scene = BenchScene(size=(384, 416), motion='static')
    shots = [{'file': f'{i}.png'} for i in range(4)]
    monkeypatch.setattr(cv2, 'findTransformECC', lambda *args, **kwargs: pytest.fail('intensity geometry fitting is forbidden'))
    monkeypatch.setattr(lens_score, '_shots', lambda directory: shots)
    monkeypatch.setattr(lens_score, 'read_capture', lambda directory, shot, side: scene.render_frame(int(shot['file'][0])))
    monkeypatch.setattr(reg, 'barcode_index', lambda capture, mapping, scene, shot: (int(shot['file'][0]), {}))
    monkeypatch.setattr(reg, 'validate_plane', lambda *args: {'scores_available': True})
    identity = {'domain': 'linear-srgb', 'matrix': np.vstack((np.eye(3), np.zeros(3))).tolist()}
    monkeypatch.setattr(bench_colour, 'load_burst', lambda path: ({'single': (identity, {'scores_available': True})}, 'same-calibration'))
    checks = iter((True, False, True, True))
    monkeypatch.setattr(bench_colour, 'validate_sample', lambda *args: {'scores_available': next(checks)})
    monkeypatch.setattr(bench_noise, 'qualified', lambda *args: True)
    report = lens_score.score_lens(tmp_path, scene, 'single', calibration='fixture')
    assert report['sample_count'] == 3 and report['diagnostic_sample_count'] == 1
    assert report['registration_controls']['0.25']['sat']['block_rms_p99']['n'] == 3
    assert report['diagnostic_registration_controls']['0.25']['sat']['block_rms_p99']['n'] == 1
    assert {s['sample_id'] for s in report['samples']} == {'0.png', '2.png', '3.png'}
    assert {s['sample_id'] for s in report['compositor_blocks']} == {'0.png', '2.png', '3.png'}
    assert len({tuple(s['lens_coefficients']) for s in report['registration_shots']}) == 1



def test_full_eye_calibration_burst_loader(tmp_path):
    from tools.quest3 import bench_colour
    size = (1000, 1000)
    image = np.full((1000, 1000, 3), 28, np.uint8)
    polygons = []
    for patch in bench_colour.layout(size):
        x, y, w, h = patch['box']
        polygon = np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]])
        cv2.fillConvexPoly(image, np.rint(polygon).astype(np.int32), patch['rgb'])
        polygons.append(polygon.tolist())
    cv2.imwrite(str(tmp_path/'eye.png'), image[..., ::-1])
    write_json(tmp_path/'calibration.json', {'schema': 1, 'layout': 'full-eye-5x5-v1', 'size': list(size),
               'eyes': {'left': [{'file': 'eye.png', 'polygons': polygons}]}})
    models, identity = bench_colour.load_burst(tmp_path)
    assert models['left'][1]['scores_available'] and len(identity) == 64
    again, same = bench_colour.load_burst(tmp_path)
    assert again == models and same == identity

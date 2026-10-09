"""Display-domain modelling and runner protocol tests; codecs are CPU copies."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import struct

import cv2
import numpy as np
import pytest

from tools.quest3 import bench_display as d
from tools.quest3.bench_scene import BenchScene
from tools.quest3.bench_score import crop_eye, iter_y4m, rgb_planes
from ws.scripts import bench_offline as offline


def geometry(size):
    return {'valid': np.ones(size[::-1], bool), 'homographies': {'panel': np.eye(3)},
            'visible': {'panel': np.ones(size[::-1], bool)}}


def score_pair(reference, output, target=None, count=2):
    target = reference if target is None else target
    score = d.DisplayScore()
    for index in range(count):
        for eye in ('left', 'right'):
            score.add(reference, output, target, d.truth_masks(target), geometry(reference.shape[1::-1]), index, eye, (0, 0))
    return score.finish()


def test_identity_zero_residual_and_display_units():
    rgb = np.full((192, 192, 3), [190, 90, 50], np.float32)
    result = score_pair(rgb, rgb)
    all_metrics = result['aggregate']['all']
    for key in ('mse_y', 'mse_cb', 'mse_cr', 'block_rms_p99', 'toggle_fraction',
                'lf8_y_p99', 'lf24_cb_p99', 'lf8_y_temporal_p99', 'flicker_p99'):
        assert all_metrics[key]['mean'] == 0
    assert all_metrics['ssim_y']['mean'] == pytest.approx(1, abs=1e-12)
    assert all_metrics['blocks']['mean'] == 8  # first unavailable, then 16 blocks after warp halo
    assert all_metrics['psnr_y_infinite']['mean'] is True
    assert d.display_planes(rgb).shape == rgb.shape  # no hidden 4:2:0 resampling


@pytest.mark.parametrize('kernel', ['bilinear', 'adaptive', 'lanczos', 'area'])
@pytest.mark.parametrize('transfer', ['srgb', 'linear'])
def test_constant_colour_and_eye_edge_preservation(kernel, transfer):
    rgb = np.full((66, 80, 3), [23, 101, 211], np.float32)
    output = d.preprocess(rgb, (48, 40), kernel, (.39, .4), transfer)
    np.testing.assert_allclose(output, np.broadcast_to(rgb[0, 0], output.shape), atol=8e-5)
    target = d.display_truth(rgb, (37, 35), (.5, -.5), transfer)
    np.testing.assert_allclose(target, np.broadcast_to(rgb[0, 0], target.shape), atol=8e-5)


@pytest.mark.parametrize('kernel', ['bilinear', 'adaptive', 'lanczos', 'area'])
def test_equal_size_filter_is_identity(kernel):
    rgb = np.random.default_rng(6).uniform(1, 254, (32, 48, 3)).astype(np.float32)
    np.testing.assert_allclose(d.preprocess(rgb, (48, 32), kernel, transfer='srgb'), rgb, atol=3e-5)


def test_adaptive_matches_shader_paired_fetch_reference():
    # Resolve relative to the known rebase root, without importing any GPU helper.
    path = Path(__file__).resolve().parents[1]/'ws/worktrees/upstream-rebase/tools/downsample/reference.py'
    spec = importlib.util.spec_from_file_location('downsample_cpu_reference', path)
    ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
    values = np.random.default_rng(4).uniform(0, 255, 77)
    for count in (77, 63, 31, 12):  # includes the shader's >3x scale clamp
        expected = ref.resample(values, count, ref.shader_sample)
        got = d.resize(values[None, :], (count, 1), 'adaptive')[0]
        np.testing.assert_allclose(got, expected, atol=4e-5)


def test_half_pixel_phase_and_centred_chroma_siting():
    ramp = np.tile(np.arange(8, dtype=np.float32), (4, 1))
    np.testing.assert_allclose(d.resize(ramp, (8, 4), phase=(.5, 0))[1, :-1], np.arange(7)+.5)
    y = np.full((4, 8), 128, np.float32)
    cb = np.tile(np.array([112, 120, 128, 136], np.float32), (2, 1))
    planes = y, cb, np.full_like(cb, 128)
    presented = d.display_planes(d.present(planes, (8, 4), transfer='srgb'))
    # JPEG-centred samples at full-res x=.5,2.5,4.5,6.5: endpoints clamp.
    np.testing.assert_allclose(presented[1, :, 1], [112, 114, 118, 122, 126, 130, 134, 136], atol=2e-5)
    assert np.max(np.abs(presented[..., 0]-128)) < 2e-5


@pytest.mark.parametrize('kernel', ['bilinear', 'adaptive', 'lanczos', 'area'])
def test_stereo_seams_stay_independent(tmp_path, kernel):
    class Scene:
        size = (64, 64)
        def metadata(self): return {'fixture': True}
        def frame_geometry(self, index): return {'index': index}
        def render_frame(self, index, eye):
            return np.full((64, 64, 3), 32 if eye == 'left' else 224, np.uint8)
    master = d.generate_master(Scene(), tmp_path/'master', 1)
    planes = next(d.candidate_frames(tmp_path/'master', master, (32, 32), kernel))
    for eye, expected in (('left', 32), ('right', 224)):
        shown = d.present(crop_eye(planes, eye), (40, 40), (.5, -.5), 'srgb')
        np.testing.assert_allclose(shown, expected, atol=3e-5)


def test_blur_wins_codec_only_but_loses_total_detail():
    xx = np.indices((192, 192))[1]
    truth = np.repeat((128+50*np.sin(xx*2*np.pi/8))[..., None], 3, axis=2).astype(np.float32)
    blurred = cv2.GaussianBlur(truth, (13, 13), 2)
    sharp_decoded = truth+1
    sharp_codec = score_pair(truth, sharp_decoded, truth, count=1)
    blur_codec = score_pair(blurred, blurred, truth, count=1)
    blur_total = score_pair(truth, blurred, truth, count=1)
    metric = lambda r, k: r['aggregate']['all'][k]['mean']
    assert metric(blur_codec, 'mse_y') < metric(sharp_codec, 'mse_y')
    assert metric(blur_total, 'mse_y') > 100*metric(sharp_codec, 'mse_y')
    assert metric(blur_total, 'detail_correlated_mean') < .4
    assert metric(sharp_codec, 'detail_correlated_mean') > .99


def test_temporal_correspondence_and_disocclusion_per_plane():
    size = (96, 96)
    field = np.indices(size)[1].astype(np.float32)
    previous = geometry(size)
    previous['visible'] = {'panel': field < 48, 'backdrop': field >= 48}
    previous['homographies']['backdrop'] = np.eye(3)
    current = deepcopy(previous)
    current['homographies']['panel'][0, 2] = 2
    current['homographies']['backdrop'][0, 2] = -3
    got, valid = d.warp_previous(field, previous, current, size)
    assert got[30, 30] == field[30, 28]
    assert got[30, 70] == field[30, 73]
    assert valid[30, 30] and valid[30, 70]
    assert not valid[30, 48]  # object boundary and newly visible pixels excluded


def test_paired_comparison_accepts_size_treatments_rejects_identity_and_frames():
    rgb = np.full((96, 96, 3), 100, np.float32)
    base = {'comparison_identity': {'master_sha256': 'one', 'model_sha256': 'uniform'},
            'treatment': {'encode_size': [64, 64]}, 'domains': {k: score_pair(rgb, rgb, count=4) for k in d.DOMAINS}}
    candidate = deepcopy(base); candidate['treatment']['encode_size'] = [96, 96]
    for domain in d.DOMAINS:
        for sample in candidate['domains'][domain]['samples']:
            sample['metrics']['all']['mse_y'] = 2
    result = d.compare_display([base, candidate], ['a', 'b'], repetitions=30)
    row = result['comparisons'][0]['domains']['total']['all']['mse_y']
    assert row == {'candidate_minus_baseline': 2, 'ci95': [2, 2], 'paired_frames': 4}
    candidate['comparison_identity']['master_sha256'] = 'other'
    with pytest.raises(ValueError, match='identity'):
        d.compare_display([base, candidate], ['a', 'b'])
    candidate['comparison_identity'] = base['comparison_identity']
    candidate['domains']['total']['samples'][0]['index'] = 50
    with pytest.raises(ValueError, match='frames'):
        d.compare_display([base, candidate], ['a', 'b'], repetitions=2)


def cli(tmp_path):
    return ['--out', str(tmp_path/'out'), '--work', str(tmp_path/'scratch'), '--mode', 'offline-display',
            '--tools', str(tmp_path/'tools'), '--encoder-stack', 'rebase', '--render-size', '384', '416',
            '--encode-size', '384', '416', '--display-size', '192', '192', '--frames', '2',
            '--profiles', 'ours-dw1', '--bench-motion', 'none', '--bench-backdrop', 'none']


def test_size_sweep_dry_run_without_tools_or_writes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(offline.WindowGuard, 'status', lambda *a: pytest.fail('GPU/guard called'))
    monkeypatch.setattr(offline.BenchScene, 'render_frame', lambda *a: pytest.fail('rendered during dry run'))
    offline.main(['--mode', 'offline-display', '--tools', str(tmp_path/'missing'), '--encoder-stack', 'rebase',
                  '--render-size', '3072', '3232', '--encode-size', '2624', '2752', '--encode-size', '2208', '2336',
                  '--encode-size', '2080', '2208', '--mbps-list', '1000', '1500', '--frames', '24',
                  '--out', str(tmp_path/'out'), '--work', str(tmp_path/'scratch'), '--dry-run'])
    plan = json.loads(capsys.readouterr().out)
    assert len(plan['jobs']) == 12
    assert plan['render_size'] == [3072, 3232]
    assert plan['stereo_size'] is None  # there is no single encoded raster in a sweep
    assert plan['pair'] is None and plan['tools_directory'].endswith('missing')
    assert plan['display']['display_size'] == [2064, 2208]
    assert {j['cap_bytes'] for j in plan['jobs']} == {1388888, 2083332}
    assert all(j['encoder_processes'] == 1 and j['history_preserved'] for j in plan['jobs'])
    assert all(j['tools']['encode']['sha256'] is None for j in plan['jobs'])
    assert not list(tmp_path.iterdir())


def test_grid_and_adhoc_profiles_strip_inherited_env(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('PYROWAVE_SECRET_EXPERIMENT', 'inherited')
    monkeypatch.setenv('PYROWAVE_LF_BOOST', '0,9000')
    args = cli(tmp_path)
    pos = args.index('--profiles'); args[pos+1] = 'grid'
    offline.main(args+['--profile-env', 'custom:PYROWAVE_LF_BOOST=99,1,PYROWAVE_CHROMA_CSF=1.3', '--dry-run'])
    jobs = json.loads(capsys.readouterr().out)['jobs']
    assert len(jobs) == 17
    assert {j['environment']['PYROWAVE_CHROMA_CSF'] for j in jobs[:16]} == {'0.6', '1.0', '1.3', '1.6'}
    assert {j['environment']['PYROWAVE_LF_BOOST'] for j in jobs[:16]} == {'3,1', '3,2', '3,3', '3,6'}
    assert all(j['environment']['PYROWAVE_DISCARD_WEIGHT'] == '1' for j in jobs[:16])
    assert jobs[-1]['environment']['PYROWAVE_LF_BOOST'] == '99,1'
    assert all('PYROWAVE_SECRET_EXPERIMENT' not in j['environment'] for j in jobs)


@pytest.mark.parametrize('spec', ['../bad:PYROWAVE_A=1', 'x:PATH=bad', 'x:PYROWAVE_A=',
                                'x:PYROWAVE_A=1,PYROWAVE_A=2', 'x:PYROWAVE_A=1,INVALID=2'])
def test_bad_profile_env_rejected(spec):
    with pytest.raises(ValueError):
        offline.profile_overrides([spec])


@pytest.fixture
def fake_codec(tmp_path, monkeypatch):
    tools = tmp_path/'tools'; tools.mkdir()
    for name in ('encode', 'decode'):
        (tools/f'pyrowave-{name}.exe').write_bytes(b'CPU copy fixture, never executed')
    calls = []
    class Guard:
        def __init__(self, *args, **kwargs): pass
        def status(self): return {}
        def run(self, command, **kwargs):
            calls.append((command, kwargs['env'].copy(), len(list(iter_y4m(command[1])))))
            shutil.copyfile(command[1], command[2])
            return 0, 'CDF 5/3 [Q3PW_TEST] bytes=fixture', ''
    monkeypatch.setattr(offline, 'WindowGuard', Guard)
    return calls


def test_fake_codec_multi_frame_budget_env_hashes_and_common_master(tmp_path, monkeypatch, fake_codec):
    original = BenchScene.render_frame
    rendered = []
    def render(self, index, eye='left', **kw):
        rendered.append((index, eye)); return original(self, index, eye, **kw)
    monkeypatch.setattr(BenchScene, 'render_frame', render)
    monkeypatch.setenv('PYROWAVE_UNWANTED', '1')
    budgets = tmp_path/'budgets.json'; budgets.write_text('[1388888, 1388888]')
    offline.main(cli(tmp_path)+['--window', 'fake', '--budgets', str(budgets), '--encode-size', '352', '384',
                               '--profile-env', 'ours-dw1:PYROWAVE_TEST_HISTORY=1'])
    assert len(fake_codec) == 4  # exactly one encode + one decode per size, never per frame
    assert all(count == 2 for _, _, count in fake_codec)
    assert all('PYROWAVE_UNWANTED' not in env for _, env, _ in fake_codec)
    assert all(env['PYROWAVE_TEST_HISTORY'] == '1' for _, env, _ in fake_codec)
    assert len(rendered) == 4  # two eyes x two frames, shared across candidate sizes
    reports = [json.loads(p.read_text()) for p in (tmp_path/'out').glob('*/summary.json')]
    assert len(reports) == 2
    assert reports[0]['comparison_identity'] == reports[1]['comparison_identity']
    for report in reports:
        assert report['domains']['codec']['aggregate']['all']['mse_y']['mean'] == 0
        assert report['codec_evidence']['actual_container_bytes'] > 0
        assert report['treatment']['tools']['encode']['sha256']
    assert not list((tmp_path/'scratch').iterdir())


@pytest.mark.parametrize('change', ['fewer', 'more', 'clock', 'siting'])
def test_mismatched_frame_rejection(tmp_path, change):
    scene = BenchScene(size=(384, 384), motion='none')
    master = d.generate_master(scene, tmp_path/'master', 1)
    source = tmp_path/'source.y4m'; decoded = tmp_path/'decoded.y4m'
    planes = tuple(np.full(shape, 128, np.uint8) for shape in ((384, 768), (192, 384), (192, 384)))
    offline.write_y4m(source, [planes], (768, 384))
    offline.write_y4m(decoded, [planes]*({'fewer': 0, 'more': 2}.get(change, 1)), (768, 384), 72 if change == 'clock' else 90)
    if change == 'siting':
        decoded.write_bytes(decoded.read_bytes().replace(b'C420jpeg', b'C420mpeg2'))
    config = {'display_size': [96, 96], 'phases': [[0, 0]], 'transfer': 'srgb', 'encode_sizes': [[384, 384]]}
    with pytest.raises(ValueError, match='frame|siting'):
        d.score_display(decoded, source, scene, tmp_path/'master', master, config, {'encode_size': [384, 384]})


def test_varying_caps_rejected_before_launch(tmp_path):
    budgets = tmp_path/'budgets.json'; budgets.write_text('[1000, 2000]')
    with pytest.raises(ValueError, match='history'):
        offline.main(cli(tmp_path)+['--budgets', str(budgets), '--dry-run'])


def test_common_support_intersection_and_phase():
    valid = d.common_support((128, 128), [[32, 32], [64, 64]], (64, 64), (.5, -.5))
    assert not valid[0].any() and not valid[:, -1].any()
    assert valid[2:-2, 2:-2].all()
    assert not valid.all()  # clamped viewport edges are reported as excluded coverage


def test_serialized_frame_bytes_and_truncation(tmp_path):
    path = tmp_path/'encoded.wave'
    raw = b'PYROWAVE'+bytes(32)+struct.pack('<I', 8)+bytes(8)+struct.pack('<I', 12)+bytes(12)
    path.write_bytes(raw)
    result = d.serialized_bytes(path, 2, 10)
    assert result['actual_per_frame_bytes'] == [8, 12]
    assert result['packet_cap_exceedances'] == 1
    assert result['container_framing_bytes'] == 48
    assert result['actual_container_bytes'] == 68
    assert result['mean_packet_cap_utilization'] == 1
    with pytest.raises(ValueError, match='count'):
        d.serialized_bytes(path, 3, 10)
    path.write_bytes(raw[:-1])
    with pytest.raises(ValueError, match='truncated'):
        d.serialized_bytes(path, 2, 10)


def test_padding_is_explicitly_rejected(tmp_path):
    with pytest.raises(ValueError, match='padding'):
        offline.main(cli(tmp_path)+['--encode-size', '350', '384', '--dry-run'])


def test_convergence_preserves_fov_and_content_raster(tmp_path):
    scene = BenchScene(size=(384, 384), motion='none')
    master = d.generate_master(scene, tmp_path/'master', 1)
    config = {'display_size': [96, 96], 'phases': [[0, 0]], 'transfer': 'srgb'}
    result = d.check_convergence(scene, tmp_path/'master', master, (416, 416), config)
    assert len(result['samples']) == 2
    assert scene.size == (384, 384)
    assert all(np.isfinite(r['mse_y_cb_cr']).all() for r in result['samples'])

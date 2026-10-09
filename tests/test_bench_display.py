"""Display-domain modelling and runner protocol tests; codecs are CPU copies."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import tempfile

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
                                'x:PYROWAVE_A=1,PYROWAVE_A=2', 'x:PYROWAVE_A=1,INVALID=2',
                                '..:PYROWAVE_A=1', '.:PYROWAVE_A=1', '.hidden:PYROWAVE_A=1', 'a.:PYROWAVE_A=1',
                                'a..b:PYROWAVE_A=1', 'a/b:PYROWAVE_A=1', 'a\\b:PYROWAVE_A=1', 'a.b/..:PYROWAVE_A=1',
                                'a.b c:PYROWAVE_A=1', ':PYROWAVE_A=1', 'no-settings'])
def test_bad_profile_env_rejected(spec):
    with pytest.raises(ValueError):
        offline.profile_overrides([spec])


def test_profile_env_overrides_builtin_grid_names_and_allows_dotted_new_names(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('PYROWAVE_LF_BOOST', '0,9000')
    # Every built-in grid name contains a decimal point.
    for name in offline.GRID_PROFILES:
        assert offline.profile_overrides([f'{name}:PYROWAVE_CPD_NYQUIST=12.5']) == {name: {'PYROWAVE_CPD_NYQUIST': '12.5'}}
    assert offline.profile_overrides(['trial.v1.2:PYROWAVE_LF_BOOST=3,2,PYROWAVE_CHROMA_CSF=1.3']) == {
        'trial.v1.2': {'PYROWAVE_LF_BOOST': '3,2', 'PYROWAVE_CHROMA_CSF': '1.3'}}
    args = cli(tmp_path)
    args[args.index('--profiles')+1] = 'grid'
    offline.main(args+['--profile-env', 'grid-c1.3-lf2-dw1:PYROWAVE_CPD_NYQUIST=12.5',
                       '--profile-env', 'trial.v1.2:PYROWAVE_CPD_NYQUIST=11', '--dry-run'])
    jobs = json.loads(capsys.readouterr().out)['jobs']
    assert len(jobs) == 17  # 16 grid profiles (the override selects no duplicate) + the new dotted name
    by_profile = {j['profile']: j['environment'] for j in jobs}
    assert by_profile['grid-c1.3-lf2-dw1']['PYROWAVE_CPD_NYQUIST'] == '12.5'
    assert by_profile['grid-c1.3-lf2-dw1']['PYROWAVE_LF_BOOST'] == '3,2'  # rest of the named profile survives
    assert by_profile['grid-c1.3-lf3-dw1']['PYROWAVE_CPD_NYQUIST'] == '13.9'  # other names untouched
    assert by_profile['trial.v1.2']['PYROWAVE_CPD_NYQUIST'] == '11'
    assert all(v['PYROWAVE_LF_BOOST'] != '0,9000' for v in by_profile.values())
    assert 'trial.v1.2' in {j['name'].split('-', 1)[1] for j in jobs}  # one plain path component per job


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


def phase_control_scene(**kwargs):
    return BenchScene(size=(384, 416), motion='none', backdrop='mosaic', panel='off', **kwargs)


def test_renderer_strip_barcode_changes_the_source_per_frame():
    # The reason the phase-only control must freeze one image (review 4, finding 2).
    scene = phase_control_scene()
    assert not np.array_equal(scene.render_frame(0, 'left'), scene.render_frame(1, 'left'))


def test_stationary_phase_control_freezes_one_source_image(tmp_path):
    scene = phase_control_scene()
    master = d.generate_master(scene, tmp_path/'master', 3, start=5)
    assert master['frozen_source']['render_index'] == 5
    assert [row['index'] for row in master['frames']] == [5, 6, 7]  # observation indices still advance
    assert {row['render_index'] for row in master['frames']} == {5}
    assert len(list((tmp_path/'master').glob('*.npy'))) == 2  # one image per eye, reused by every row
    for eye in ('left', 'right'):
        images = [d.read_master(tmp_path/'master', row, eye) for row in master['frames']]
        assert all(np.array_equal(images[0], image) for image in images[1:])
        assert len({row['eyes'][eye]['sha256'] for row in master['frames']}) == 1
        assert np.array_equal(images[0], scene.render_frame(5, eye))
    # The frozen master still checks convergence against the same frozen frame.
    config = {'display_size': [96, 96], 'phases': [[0, 0], [.5, 0]], 'transfer': 'srgb'}
    result = d.check_convergence(scene, tmp_path/'master', master, (416, 448), config)
    assert all(np.isfinite(r['mse_y_cb_cr']).all() for r in result['samples'])


@pytest.mark.parametrize('kwargs', [{'motion': 'tremor', 'panel': 'off', 'backdrop': 'mosaic'},
                                    {'motion': 'none', 'panel': 'on', 'backdrop': 'none'}])
def test_other_scenes_keep_rendering_every_frame(tmp_path, kwargs):
    scene = BenchScene(size=(384, 416), **kwargs)
    master = d.generate_master(scene, tmp_path/'master', 2)
    assert 'frozen_source' not in master and all('render_index' not in row for row in master['frames'])
    assert len(list((tmp_path/'master').glob('*.npy'))) == 4
    assert master['frames'][0]['eyes']['left']['sha256'] != master['frames'][1]['eyes']['left']['sha256']


def test_phase_only_control_scores_one_source_with_advancing_phases(tmp_path, fake_codec):
    offline.main(cli(tmp_path)+['--window', 'fake', '--frames', '3', '--bench-backdrop', 'mosaic', '--bench-panel', 'off',
                                '--display-phase', '0', '0', '--display-phase', '.5', '0'])
    plan = json.loads((tmp_path/'out/plan.json').read_text())
    assert plan['frozen_source'] is True
    report = json.loads(next((tmp_path/'out').glob('*/summary.json')).read_text())
    assert report['frozen_source']['render_index'] == 0
    rows = [p for p in report['frame_provenance'] if p['eye'] == 'left']
    assert [p['index'] for p in rows] == [0, 1, 2]
    assert len({p['master_sha256'] for p in rows}) == 1  # one stored source image
    assert len({p['source_sha256'] for p in rows}) == 1  # identical encoder input every frame
    assert [s['phase'] for s in report['domains']['total']['samples'] if s['eye'] == 'left'] == [[0, 0], [.5, 0], [0, 0]]
    # Only the display phase changes the displayed truth: frames 0 and 2 share a phase.
    assert rows[0]['target_sha256'] == rows[2]['target_sha256'] != rows[1]['target_sha256']
    assert [c[2] for c in fake_codec] == [3, 3]  # one encoder process, all three frames


def command_log(kind):
    """A command log far longer than WindowGuard's 8192-character tail."""
    lines = [f'[Q3PW_EARLY_{kind.upper()}] start-up configuration CDF 5/3', 'PYROWAVE_CPD_NYQUIST=13.9']
    lines += [f'filler line {n:05d} nothing to see' for n in range(800)]
    lines.append(f'[Q3PW_LATE_{kind.upper()}] finished')
    return '\n'.join(lines)+'\n'


@pytest.fixture
def long_log_codec(tmp_path, monkeypatch):
    """Fake guard shaped like the real one: complete command-*.log in cwd, 8 KiB tail returned."""
    tools = tmp_path/'tools'; tools.mkdir()
    for name in ('encode', 'decode'):
        (tools/f'pyrowave-{name}.exe').write_bytes(b'CPU copy fixture, never executed')
    state = {'calls': [], 'fail': None}
    class Guard:
        def __init__(self, *args, **kwargs): pass
        def status(self): return {}
        def run(self, command, *, cwd, env, timeout_s):
            kind = 'encode' if 'encode' in Path(command[0]).name else 'decode'
            state['calls'].append(kind)
            full = command_log(kind)
            with tempfile.NamedTemporaryFile(dir=cwd, prefix='command-', suffix='.log', delete=False) as stream:
                stream.write(full.encode())
            if state['fail'] == kind:
                raise TimeoutError('subprocess timeout')
            shutil.copyfile(command[1], command[2])
            return 0, full[-8192:], ''
    monkeypatch.setattr(offline, 'WindowGuard', Guard)
    return state


def test_display_run_keeps_complete_command_logs_and_extracts_markers_from_them(tmp_path, long_log_codec):
    offline.main(cli(tmp_path)+['--window', 'fake'])
    job = tmp_path/'out/384x416-ours-dw1'
    for kind in ('encode', 'decode'):
        full = command_log(kind)
        assert (job/f'{kind}.full.log').read_bytes() == full.encode()
        assert (job/f'{kind}.log').read_text() == full[-8192:]  # the existing tail file is unchanged
        assert f'EARLY_{kind.upper()}' not in (job/f'{kind}.log').read_text()
    evidence = json.loads((job/'summary.json').read_text())['codec_evidence']
    assert evidence['wavelet_marker_seen'] is True  # only in the start-up lines, beyond the tail
    assert any('EARLY_ENCODE' in line for line in evidence['feature_marker_lines'])
    assert any('PYROWAVE_CPD_NYQUIST=13.9' in line for line in evidence['feature_marker_lines'])
    assert evidence['feature_marker_line_count'] == 3  # early marker, PYROWAVE_CPD line, late marker
    assert evidence['full_log_files'] == {'encode': 'encode.full.log', 'decode': 'decode.full.log'}
    assert evidence['marker_log_source'] == 'complete command logs'
    assert not list((tmp_path/'scratch').iterdir())  # default scratch cleanup still happens


def test_failed_command_still_leaves_its_complete_log(tmp_path, long_log_codec):
    long_log_codec['fail'] = 'encode'
    with pytest.raises(TimeoutError):
        offline.main(cli(tmp_path)+['--window', 'fake'])
    job = tmp_path/'out/384x416-ours-dw1'
    assert (job/'encode.full.log').read_bytes() == command_log('encode').encode()
    assert not list((tmp_path/'scratch').iterdir())


def test_legacy_run_keeps_complete_command_logs(tmp_path, long_log_codec):
    offline.main(['--out', str(tmp_path/'out'), '--work', str(tmp_path/'scratch'), '--tools', str(tmp_path/'tools'),
                  '--encoder-stack', 'legacy', '--profiles', 'ours-c9', '--window', 'fake', '--frames', '2',
                  '--size', '384', '416', '--bench-backdrop', 'none', '--bench-motion', 'none'])
    job = tmp_path/'out/ours-c9'
    assert (job/'encode.full.log').read_bytes() == command_log('encode').encode()
    assert (job/'decode.full.log').read_bytes() == command_log('decode').encode()
    assert 'EARLY_ENCODE' not in (job/'encode.log').read_text()
    evidence = json.loads((job/'summary.json').read_text())['codec_evidence'][0]
    assert evidence['wavelet_marker_seen'] is True
    assert evidence['marker_log_source'] == 'complete command logs'
    assert not list((tmp_path/'scratch').iterdir())


def test_run_logged_without_a_captured_command_log_reports_tail_only(tmp_path):
    class Guard:
        def run(self, command, **kwargs): return 0, 'tail text', ''
    directory = tmp_path/'job'; directory.mkdir()
    code, text, full = offline.run_logged(Guard(), ['x'], cwd=tmp_path, env={}, timeout_s=1, directory=directory, label='encode')
    assert (code, text, full) == (0, 'tail text', None)
    assert (directory/'encode.log').read_text() == 'tail text' and not (directory/'encode.full.log').exists()
    assert offline.log_evidence({'encode': None, 'decode': None})['marker_log_source'].startswith('guard tail only')

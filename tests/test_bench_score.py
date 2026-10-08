import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
import pytest

from tools.quest3 import bench_score as score
from tools.quest3.bench_scene import BenchScene, write_json


@pytest.fixture(scope='module')
def scene():
    return BenchScene(size=(656, 688), motion='tremor')


def test_identical_under_motion(scene):
    accumulator = score.ScoreAccumulator(scene, 'offline')
    for n in (0, 1, 2):
        planes = score.rgb_planes(scene.render_frame(n))
        accumulator.add(planes, planes, n)
    report = accumulator.finish()
    for sample in report['samples']:
        for name, metrics in sample['metrics'].items():
            for key, value in metrics.items():
                if key.startswith(('mse_', 'lf')) and not key.endswith('count'):
                    assert value is None or value == 0, (name, key, value)
        assert sample['metrics']['sat']['toggle_fraction'] in (None, 0)
        assert sample['metrics']['edge']['flicker_mean'] in (None, 0)


def test_signed_chroma_flip():
    mask = np.ones((16, 16), bool)
    plus = np.full((16, 16), 10, np.float32)
    minus = -plus
    result = score.block_metrics(plus-minus, np.zeros_like(plus), mask)
    assert result['toggle_fraction'] == 1
    assert result['block_rms_p99'] == pytest.approx(np.sqrt(200))
    assert score.block_metrics(plus-plus, plus-plus, mask)['toggle_fraction'] == 0


def test_signed_chroma_flip_through_scene_masks(scene):
    accumulator = score.ScoreAccumulator(scene, 'offline')
    for n, sign in ((0, 1), (1, -1)):
        truth = score.rgb_planes(scene.render_frame(n))
        output = [p.copy() for p in truth]
        output[1][score.chroma_mask(scene.labels(n) == 1)] += sign*10
        accumulator.add(truth, output, n)
    assert accumulator.samples[-1]['metrics']['sat']['toggle_fraction'] == 1


def test_dark_blotch_static_and_edge_isolation():
    scene = BenchScene(size=(656, 688), motion='static')
    truth = score.rgb_planes(scene.render_frame(0))
    labels = scene.labels(0)
    accumulator = score.ScoreAccumulator(scene, 'offline')
    for n in (0, 1):
        output = [p.copy() for p in truth]
        output[0][labels == 2] += 5
        accumulator.add(truth, output, n)
    metrics = accumulator.finish()['samples'][-1]['metrics']
    assert metrics['mura']['lf8_y_dark_p99'] == pytest.approx(5, abs=.001)
    assert metrics['mura']['lf8_y_dark_temporal_p99'] == pytest.approx(0, abs=.001)
    assert metrics['sat']['toggle_fraction'] == 0
    assert metrics['edge']['flicker_p99'] == 0
    accumulator = score.ScoreAccumulator(scene, 'offline')
    for n, sign in ((0, 1), (1, -1)):
        output = [p.copy() for p in truth]
        output[0][(labels == 3) & (truth[0] > 100)] += 8*sign
        accumulator.add(truth, output, n)
    metrics = accumulator.finish()['samples'][-1]['metrics']
    assert metrics['edge']['flicker_p99'] >= 15
    assert metrics['sat']['toggle_fraction'] == 0
    assert metrics['mura']['lf8_y_p99'] == 0


def test_skipped_and_duplicate_indices_not_temporal(scene):
    accumulator = score.ScoreAccumulator(scene, 'codec')
    for n in (0, 2, 2, 3):
        planes = score.rgb_planes(scene.render_frame(n))
        accumulator.add(planes, planes, n)
    assert [s['consecutive'] for s in accumulator.samples] == [False, False, False, True]


def test_null_masks(scene):
    planes = score.rgb_planes(scene.render_frame(0))
    accumulator = score.ScoreAccumulator(scene, 'compositor')
    accumulator.add(planes, planes, 0, np.zeros_like(planes[0], bool))
    result = accumulator.finish()
    assert result['aggregate']['sat']['toggle_fraction']['mean'] is None
    assert result['aggregate']['edge']['psnr_y_db']['mean'] is None
    json.dumps(result, allow_nan=False)


def synthetic_burst(directory, scene, amplitude, lf=0):
    directory.mkdir()
    h = np.array([[.79, .006, 14.4], [-.005, .80, 19.2], [9e-6, -8e-6, 1]], np.float64)
    luma = np.array([.2126, .7152, .0722])
    matrix = 1.25*np.eye(3)-.25*np.repeat(luma[:, None], 3, axis=1)
    transform = np.vstack((matrix, np.zeros(3)))
    for shot, index in enumerate((0, 5, 10, 15, 20, 25)):
        rgb = scene.render_frame(index).astype(np.float32)
        labels = scene.labels(index)
        # Pure Cb residual in RGB with zero Y/Cr, inside flat saturated tiles.
        delta = amplitude*(1 if shot % 2 else -1)*(labels == 1)
        rgb[..., 2] += 2*(1-score.KB)*delta
        rgb[..., 1] -= 2*score.KB*(1-score.KB)/(1-score.KR-score.KB)*delta
        rgb[labels == 2] += lf
        rgb = score.apply_colour(rgb, transform)
        capture = cv2.warpPerspective(rgb, h, (550, 575), flags=cv2.INTER_LINEAR)
        cv2.imwrite(str(directory/f'{shot:03}.png'), np.rint(np.clip(capture, 0, 255)).astype(np.uint8)[..., ::-1])


def test_compositor_end_to_end_and_ranking(tmp_path, scene):
    good, bad = tmp_path/'good', tmp_path/'bad'
    synthetic_burst(good, scene, .5, 0)
    synthetic_burst(bad, scene, 12, 6)
    reports = [score.score_compositor(p, scene, 'single') for p in (bad, good)]
    assert all(r['sample_count'] == 6 for r in reports), [r['rejected'] for r in reports]
    assert reports[0]['aggregate']['sat']['toggle_fraction']['mean'] > .5
    assert reports[0]['aggregate']['sat']['block_rms_p99']['mean'] > reports[1]['aggregate']['sat']['block_rms_p99']['mean']*3
    assert reports[0]['aggregate']['mura']['lf8_y_p99']['mean'] > 4
    text, verdict = score.compare_reports(reports, ['A', 'B'], repetitions=100)
    assert verdict, text
    assert 'PASS' in text
    score.save_report(reports[0], tmp_path/'report')
    assert (tmp_path/'report/summary.md').exists()
    reports[1]['comparison_identity'] = {'different': True}
    with pytest.raises(ValueError, match='not comparable'):
        score.compare_reports(reports, ['A', 'B'])


def write_dump(directory, timestamp, stage, planes, rgb=False, bottom=False):
    y, cb, cr = planes
    w, h = y.shape[1], y.shape[0]
    if rgb:
        image = np.clip(score.planes_to_rgb(planes), 0, 255).astype(np.uint8)
        image = np.dstack((image[..., ::-1], np.full((h, w), 255, np.uint8)))
        raw = (image[::-1] if bottom else image).tobytes()
        fmt = 'bgra8'
    else:
        raw = b''.join((p[::-1] if bottom else p).astype(np.uint8).tobytes() for p in planes)
        fmt = 'yuv420p'
    path = directory/f'{timestamp}-{stage}.json'
    write_json(path, {'schema': 1, 'complete': True, 'timestamp_ns': timestamp, 'frame_index': 0,
                     'stage': stage, 'width': w, 'height': h, 'format': fmt, 'range': 'full',
                     'matrix': 'bt709', 'row_order': 'bottom_up' if bottom else 'top_down', 'bytes': len(raw)})
    path.with_suffix('.raw').write_bytes(raw)
    return path


def test_timestamp_pairing_presented_and_dump_formats(tmp_path, scene):
    server, client = tmp_path/'server', tmp_path/'client'
    server.mkdir(); client.mkdir()
    for n in (0, 1):
        eye = score.rgb_planes(scene.render_frame(n), quantize=True)
        stereo = tuple(np.concatenate((p, p), axis=1) for p in eye)
        write_dump(server, 100+n, 'encoder_input', stereo)
        write_dump(client, 100+n, 'post_decode', stereo, bottom=True)
        write_dump(client, 100+n, 'presented_right', eye, rgb=True, bottom=True)
    write_dump(client, 999, 'post_decode', stereo)
    codec = score.score_dumps(server, client, scene, eye='both')
    assert codec['sample_count'] == 4
    assert codec['unmatched_client'] == [{'timestamp_ns': 999, 'stage': 'post_decode'}]
    assert codec['aggregate']['sat']['mse_y']['mean'] == 0
    presented = score.score_dumps(server, client, scene, 'presented', 'right')
    assert presented['sample_count'] == 2
    path = write_dump(client, 1111, 'post_decode', stereo)
    path.with_suffix('.raw').write_bytes(b'short')
    with pytest.raises(ValueError, match='truncated'):
        score.read_dump(path)


def offline_module():
    path = Path(__file__).resolve().parents[1]/'ws/scripts/bench_offline.py'
    spec = importlib.util.spec_from_file_location('bench_offline', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_dry_run_does_not_use_gpu(tmp_path, monkeypatch, capsys):
    module = offline_module()
    monkeypatch.setattr(module.WindowGuard, 'status', lambda *a: pytest.fail('GPU guard accessed in dry run'))
    args = ['--out', str(tmp_path/'out'), '--work', str(tmp_path/'work'), '--dry-run']
    assert module.main(args) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['cap_bytes'] == 1388888
    assert plan['jobs'][0]['environment']['PYROWAVE_WAVELET'] == '53'
    assert plan['jobs'][1]['environment']['PYROWAVE_HEADSET_CSF'] == '1'
    assert not (tmp_path/'out').exists()
    assert not (tmp_path/'work').exists()


def test_y4m_stream_roundtrip(tmp_path, scene):
    module = offline_module()
    path = tmp_path/'source.y4m'
    module.write_y4m(path, module.source_frames(scene, 3, 5), (2*scene.size[0], scene.size[1]))
    result = score.score_offline(path, scene, start=5, stereo=True, truth_path=path)
    assert result['sample_count'] == 6
    assert result['observation_count'] == 3
    assert result['aggregate']['sat']['mse_cb']['mean'] == 0
    assert result['aggregate']['sat']['toggle_fraction']['mean'] == 0


def test_server_conversion_coefficients_and_rounding():
    rgb = np.array([[[255, 0, 0], [0, 255, 0]], [[0, 0, 255], [255, 140, 0]]], np.uint8)
    y, cb, cr = score.rgb_planes(rgb, quantize=True)
    expected_cb = np.rint(128+rgb.astype(np.float32) @ np.array([-.1141230, -.3839162, .4980392], np.float32))
    assert cb[0, 0] == np.rint(expected_cb.mean())
    assert y[0, 0] == 54


def test_offline_runner_cleanup_with_fake_codec(tmp_path, monkeypatch):
    module = offline_module()
    pair = tmp_path/'out/fake/windows'
    pair.mkdir(parents=True)
    for name in ('pyrowave-encode.exe', 'pyrowave-decode.exe'):
        (pair/name).write_bytes(b'CPU test double, never executed')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    calls = []
    class FakeGuard:
        def __init__(self, *a, **kw):
            pass
        def status(self):
            return {}
        def run(self, argv, **kw):
            calls.append(argv)
            if Path(argv[0]).name == 'pyrowave-encode.exe':
                Path(argv[2]).write_bytes(Path(argv[1]).read_bytes())
            else:
                Path(argv[2]).write_bytes(Path(argv[1]).read_bytes())
            return 0, 'CDF 5/3 [Q3PW_HEADSET_CSF]', ''
    monkeypatch.setattr(module, 'WindowGuard', FakeGuard)
    assert module.main(['--pair', 'fake', '--out', str(tmp_path/'result'), '--work', str(tmp_path/'scratch'),
                        '--window', 'fake-lease', '--size', '656', '688', '--frames', '2']) == 0
    assert len(calls) == 4
    assert not list((tmp_path/'scratch').iterdir())
    assert (tmp_path/'result/ours-c9/summary.json').exists()
    assert (tmp_path/'result/upstream-like/summary.json').exists()


@pytest.mark.skipif(shutil.which('powershell') is None, reason='PowerShell parser unavailable')
def test_wrapper_parse_and_health_with_no_hardware(tmp_path):
    wrapper = Path(__file__).resolve().parents[1]/'ws/scripts/bench-run.ps1'
    # Only load the health function AST; never evaluate wrapper top-level code.
    # The Python command is replaced by an in-process PowerShell stub, so no
    # import of session25 (whose serial selection uses ADB) occurs in this test.
    program = r'''
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile('__WRAPPER__',[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Read-BenchHealth'},$true)
Invoke-Expression $node.Extent.Text
function Invoke-HealthStub { $global:LASTEXITCODE=0; return $script:response }
$StartC=50; $StopC=55; $py='Invoke-HealthStub'; $session='__TEMP__'; $runTag='cpu-test'
foreach ($case in @(
  @{b=10;t=49.9;s=0;stop=$false}, @{b=40;t=54.9;s=2;stop=$false},
  @{b=9;t=40;s=0;stop=$true}, @{b=40;t=55;s=0;stop=$true},
  @{b=40;t=40;s=3;stop=$true}, @{b=$null;t=40;s=0;stop=$true}
)) {
  $script:response=@{serial='CPU-FAKE';health=@{battery_percent=$case.b;temperature_c=$case.t;thermal_status=$case.s}} | ConvertTo-Json -Compress
  $stopped=$false
  try { $null=Read-BenchHealth } catch { $stopped=$true }
  if ($stopped -ne $case.stop) { throw ('wrong health decision: '+($case | ConvertTo-Json -Compress)) }
}
Write-Output 'CPU health checks passed'
'''.replace('__WRAPPER__', str(wrapper).replace("'", "''")).replace('__TEMP__', str(tmp_path).replace("'", "''"))
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', program],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'CPU health checks passed' in result.stdout

def test_compositor_opposite_sign_pixels_do_not_cancel():
    field = np.tile(np.r_[np.ones(8)*10,-np.ones(8)*10],(16,1)).astype(np.float32)
    samples=[]
    for i,sign in enumerate((1,-1,1,-1)):
        samples.append({'eye':'left','sample_id':str(i),'ids':[0],
                        'cb':score.packed_blocks(sign*field,[0]),'cr':score.packed_blocks(np.zeros_like(field),[0])})
    metrics=score.compositor_blocks(samples)
    assert metrics['block_rms_mean'] == pytest.approx(np.sqrt(50))
    assert metrics['toggle_fraction'] == 1
    assert metrics['block_mean_std_p99'] == 0


def test_moments_admit_new_pixels_order_independent():
    observations=[(np.array([0.,0.]),np.array([1,0],bool)),
                  (np.array([0.,10.]),np.array([1,1],bool)),
                  (np.array([0.,-10.]),np.array([1,1],bool))]
    results=[]
    for order in (observations,observations[::-1]):
        moments=score.Moments(order[0][1])
        for field,mask in order: moments.update(field,mask)
        results.append(moments.std_values())
    np.testing.assert_allclose(results[0],results[1])
    np.testing.assert_allclose(results[0],[0,10])


def test_lf_support_does_not_cross_class_boundary(scene):
    truth=score.rgb_planes(scene.panel_frame(0))
    output=[p.copy() for p in truth]
    output[0][scene.panel_labels != 2] += 100
    accumulator=score.ScoreAccumulator(scene,'compositor')
    accumulator.add(truth,output,0,panel=True)
    row=accumulator.samples[0]['metrics']['mura']
    assert row['lf8_y_count'] > 0
    assert row['lf8_y_p99'] == 0


def test_colour_linear_light_and_held_out_rejection(scene):
    luma=np.array([score.KR,1-score.KR-score.KB,score.KB])
    matrix=1.4*np.eye(3)-.4*np.repeat(luma[:,None],3,axis=1)
    transform={'domain':'linear-srgb','matrix':np.vstack((matrix,[0.,0.,0.])).tolist()}
    image=score.apply_colour(scene.panel_frame(0),transform)
    model,diagnostics=score.fit_colour(image,scene)
    assert model['domain'] == 'linear-srgb'
    assert diagnostics['held_out_rmse_codes'] < .001
    assert diagnostics['scores_available']
    assert diagnostics['colour_amplification_chroma'] > 1.2
    np.testing.assert_allclose(score.apply_colour(scene.panel_frame(0),model),image,atol=.001)
    # Non-modelled local/nonlinear patch response cannot silently become mura.
    for i,p in enumerate(scene.calibration):
        x,y,w,h=p['box']
        image[y:y+h,x:x+w] += 5 if i%2 else -5
    _,diagnostics=score.fit_colour(np.clip(image,0,255),scene)
    assert diagnostics['held_out_rmse_codes'] > .5
    assert not diagnostics['scores_available']


def make_small_report(stage,indices,error=0,stereo=True):
    scene=BenchScene(size=(656,688),motion='mix')
    acc=score.ScoreAccumulator(scene,stage)
    truth=score.rgb_planes(scene.panel_frame(0))
    for index in indices:
        for eye in ('left','right') if stereo else ('left',):
            output=[p.copy() for p in truth]
            output[0][scene.panel_labels==2] += error
            output[0][scene.panel_labels==4] += error
            output[1][score.chroma_mask(scene.panel_labels==1)] += error*(-1 if index%2 else 1)
            acc.add(truth,output,index,eye=eye,sample_id=str(index),panel=True)
    return acc.finish()


@pytest.mark.parametrize('stage',['offline','codec','presented','compositor'])
def test_stereo_clusters_cannot_pass_with_three_captures(stage):
    bad=make_small_report(stage,range(3),10)
    good=make_small_report(stage,range(3),0)
    assert bad['sample_count']==6 and bad['observation_count']==3
    assert bad['aggregate']['mura']['lf8_y_p99']['n']==3
    text,verdict=score.compare_reports([bad,good],['bad','good'],repetitions=25)
    assert not verdict and 'insufficient' in text


def test_compare_requires_shared_motion_phases():
    jitter=make_small_report('offline',range(180,186),10)
    static=make_small_report('offline',range(720,726),0)
    with pytest.raises(ValueError,match='shared trajectory phases'):
        score.compare_reports([jitter,static],['jitter','static'])
    # Same segment, different turn phase must also be refused.
    turn1=make_small_report('offline',range(540,546),10)
    turn2=make_small_report('offline',range(600,606),0)
    with pytest.raises(ValueError,match='shared trajectory phases'):
        score.compare_reports([turn1,turn2],['out','back'])


def test_psnr_infinity_survives_aggregation_and_ranking():
    perfect=make_small_report('offline',range(6),0)
    lossy=make_small_report('offline',range(6),5)
    assert perfect['aggregate']['natural']['psnr_y_db']['infinite']
    text,_=score.compare_reports([lossy,perfect],['lossy','perfect'],repetitions=25)
    assert 'natural / psnr_y_db | perfect < lossy' in text
    assert 'infinity (MSE=0)' in text
    json.dumps(perfect,allow_nan=False)


def test_lossless_capture_scores_zero_modelled_sampling(scene):
    # Exact forward model, varying perspective and camera. Floating capture:
    # residual formation/pullback must be <0.001 codes, including edge and LF.
    acc=score.ScoreAccumulator(scene,'compositor')
    model={'domain':'encoded-rgb','matrix':np.vstack((np.eye(3),np.zeros(3))).tolist()}
    for i in (0,5,10,15):
        source=scene.render_frame(i)
        h=np.array([[.79,.006+i*.0001,14.4],[-.005,.8,19.2],[9e-6,-8e-6,1.]])
        capture=cv2.warpPerspective(source.astype(np.float32),h,(550,575),borderValue=(28,28,28))
        panel_h=h @ scene.homography(i)
        reference,residual,valid=score.capture_residual(capture,source,h,model,panel_h,scene.panel_size)
        acc.add(score.rgb_planes(reference),score.rgb_planes(reference+residual),i,valid,panel=True)
    result=acc.finish()
    assert result['aggregate']['edge']['flicker_p99']['mean'] < .001
    assert result['aggregate']['mura']['lf8_y_p99']['mean'] < .001


def test_lossless_capture_registration_end_to_end(tmp_path,scene):
    synthetic_burst(tmp_path/'lossless',scene,0,0)
    report=score.score_compositor(tmp_path/'lossless',scene,'single')
    assert report['sample_count']==6, (report['rejected'],report['unavailable'])
    # Includes 8-bit rounding, fitted geometry and fitted colour, unlike exact
    # sampler test. These tolerances are below the 1.5-code toggle threshold.
    assert report['aggregate']['edge']['flicker_p99']['mean'] < 1.0
    assert report['aggregate']['mura']['lf8_y_p99']['mean'] < .25

@pytest.mark.skipif(shutil.which('powershell') is None,reason='PowerShell unavailable')
def test_wrapper_restore_normal_exit_retry_failure_and_kick(tmp_path):
    root=Path(__file__).resolve().parents[1]
    wrapper=root/'ws/scripts/bench-run.ps1'
    program=r'''
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile('__WRAPPER__',[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($name in @('Confirm-BenchRestore','Invoke-BenchKick','Read-BenchHealth')) {
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $node.Extent.Text
}
$session='__TEMP__'; $root=$session; $env:Q3PW_STAGE='stage'; $Adapter='fake'; $py='Invoke-RestoreStub'
$script:attempts=0; $script:succeed=2
function Save-Snapshot([bool]$restored) {
  @{restored=$restored;files=@{session=@{path=(Join-Path $session 'stage/session.json')}}} | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $session 'snapshot.jsonl')
}
function Invoke-RestoreStub {
  $script:attempts++
  $ok=$script:attempts -eq $script:succeed
  Save-Snapshot $ok
  $global:LASTEXITCODE=if ($ok) {0} else {1}
}
$launch=(Get-Date).AddMinutes(-1)
Save-Snapshot $false
Confirm-BenchRestore $launch
if ($script:attempts -ne 2) { throw 'did not retry failed normal-exit restore' }
Confirm-BenchRestore $launch
if ($script:attempts -ne 2) { throw 'verified restore was not idempotent' }
Save-Snapshot $false; $script:succeed=99; $script:attempts=0
$failed=$false
try { Confirm-BenchRestore $launch } catch { $failed=$true }
if (-not $failed -or $script:attempts -ne 2) { throw 'remaining restore failure not propagated' }
$script:kicks=0; $script:running=$false; $KickSteamVR=$true
function Get-Process { if ($script:running) { return @{Id=1} } }
function Start-Process { param($FilePath,$WindowStyle); if ($WindowStyle -ne 'Hidden') { throw 'visible helper' }; $script:kicks++ }
function Save-Event([double]$age) {
 @{epoch_s=([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000-$age);kind='steamvr_restart'} | ConvertTo-Json -Compress | Set-Content (Join-Path $session 'events.jsonl')
}
$seen=@{}
Save-Event 5; Invoke-BenchKick $launch $seen
if ($script:kicks) { throw 'kicked too early' }
Save-Event 16; Invoke-BenchKick $launch $seen; Invoke-BenchKick $launch $seen
if ($script:kicks -ne 1) { throw 'restart kick missing or duplicated' }
$script:running=$true; Save-Event 20; Invoke-BenchKick $launch $seen
if ($script:kicks -ne 1) { throw 'kicked running vrserver' }
# Override stop is honoured and logged; no ADB process is invoked.
$StopC=57; $StartC=52; $runTag='override'; $py='Invoke-HealthStub'
function Invoke-HealthStub { $global:LASTEXITCODE=0; return '{"serial":"stub","health":{"battery_percent":20,"temperature_c":56,"thermal_status":0}}' }
$null=Read-BenchHealth
$h=Get-Content (Join-Path $session 'bench-health-override.jsonl') -Raw | ConvertFrom-Json
if ($h.thresholds.stop_c -ne 57 -or $h.thresholds.start_c -ne 52) { throw 'overrides not logged' }
Write-Output 'restore/kick/override CPU checks passed'
'''.replace('__WRAPPER__',str(wrapper).replace("'","''")).replace('__TEMP__',str(tmp_path).replace("'","''"))
    result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',program],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'CPU checks passed' in result.stdout
    # Check normal exit cannot bypass finally's verification (the original P1).
    source=wrapper.read_text()
    assert source.index('try { Confirm-BenchRestore $launchTime }') > source.index('if ($process) {\n            $restoreFailure')


@pytest.mark.skipif(shutil.which('powershell') is None,reason='PowerShell unavailable')
def test_child_forwards_supported_threshold_without_editing_harness(tmp_path):
    child=Path(__file__).resolve().parents[1]/'ws/scripts/bench-child.ps1'
    harness=tmp_path/'fake.ps1'
    original="""param([string]$Pair,[switch]$Wake)
function Stub { Write-Output ($args -join '|') }
Stub --session25 ws\\session25.py cell sample
Write-Output "Pair=$Pair Wake=$Wake"
"""
    harness.write_text(original)
    result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-File',str(child),'-Harness',str(harness),'-StopC','57','-Pair','a pair','-Wake'],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    assert '--temperature-stop-c|57|cell|sample' in result.stdout
    assert 'Pair=a pair Wake=True' in result.stdout
    assert harness.read_text()==original

def test_compositor_uses_recorded_source_raster_after_downscale(tmp_path):
    # Source size deliberately differs from capture/stream size. Reconstructing
    # directly at stream size used to bias registration (review P1 #3).
    scene=BenchScene(size=(820,860),motion='tremor')
    scene.save(tmp_path/'scene')
    replay=BenchScene.from_metadata(tmp_path/'scene')
    captures=tmp_path/'captures'; captures.mkdir()
    known=np.array([[.74,.004,9.2],[-.003,.72,13.5],[4e-6,-5e-6,1.]])
    for index in (0,5):
        source=scene.render_frame(index)
        capture=cv2.warpPerspective(source,known,(656,688),borderValue=(28,28,28))
        cv2.imwrite(str(captures/f'{index}.png'),capture[...,::-1])
    report=score.score_compositor(captures,replay,'single')
    assert report['sample_count']==2,(report['rejected'],report['unavailable'])
    points=np.array([[[200,250],[600,250],[200,600],[600,600]]],np.float32)
    for sample in report['samples']:
        registration=sample['registration']
        assert registration['source_size']==[820,860]
        predicted=cv2.perspectiveTransform(points,np.array(registration['source_to_capture']))
        expected=cv2.perspectiveTransform(points,known)
        assert np.sqrt(np.mean((predicted-expected)**2)) < .1
    assert report['aggregate']['mura']['lf8_y_p99']['mean'] < .25


def test_common_phase_weights_ignore_stereo_duplication():
    a=make_small_report('offline',[360,361,362,363,390,391],1)
    b=make_small_report('offline',[360,361,390,391,392,393],1,stereo=False)
    _,weights,coverage=score.matched_groups([a,b])
    assert coverage==[1.,1.]
    assert weights=={('pan',12):.5,('pan',13):.5}

def test_psnr_partial_perfect_phases_aggregate_in_mse_domain():
    report=make_small_report('offline',[360,361,362,363,390,391,392,393],5)
    for sample in report['samples']:
        if sample['index'] < 390:
            sample['metrics']['natural']['mse_y']=0.
            sample['metrics']['natural']['psnr_y_db']=None
    text,_=score.compare_reports([report,report],['a','b'],repetitions=10)
    line=next(line for line in text.splitlines() if 'natural / psnr_y_db' in line)
    assert 'infinity' not in line
    assert f'{score.psnr(12.5):.5g}' in line

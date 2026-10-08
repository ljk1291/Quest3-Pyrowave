import hashlib
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from tools.quest3 import bench_scene as bs, bench_score as score
from tools.quest3.bench_backdrop import SERVER_MATRIX, dump_rgb, metro_planes, load_proxy, natural_masks
from ws.scripts import bench_offline as offline


@pytest.fixture(scope='module')
def dump(tmp_path_factory):
    path = tmp_path_factory.mktemp('metro')/'1-encoder_input.json'
    rng = np.random.default_rng(43)
    small = rng.integers(10,100,(104,96,1),dtype=np.uint8)
    image = np.repeat(cv2.resize(small,(384,416),interpolation=cv2.INTER_LINEAR)[...,None],3,axis=2)
    image[:100,:100] = np.clip(image[:100,:100].astype(int)+[90,0,-10],0,255)
    image[120:300,:100] = 28 + rng.integers(-2,3,(180,100,1))
    image[320:,:,0] = 110
    stereo = np.concatenate((image,np.roll(image,3,axis=1)),axis=1)
    planes = score.rgb_planes(stereo,quantize=True)
    data = b''.join(p.tobytes() for p in planes)
    path.with_suffix('.raw').write_bytes(data)
    bs.write_json(path,dict(schema=1,complete=True,timestamp_ns=1,stage='encoder_input',format='yuv420p',
                           width=768,height=416,bytes=len(data),range='full',matrix='bt709',row_order='top_down',
                           projection_raw=[-1,1,-1,1]))
    return path


@pytest.fixture(scope='module')
def scene(dump):
    return bs.BenchScene(size=(384,416),motion='none',backdrop='metro',backdrop_asset=dump)


@pytest.fixture(params=['png', 'raw'])
def marker_asset(request, tmp_path):
    # Only the left eye contains a marker. All rows are stored top-down.
    w, h = 384, 416
    image = np.full((h, w, 3), 16, np.uint8)
    image[h//8:h//4, w//8:w//4] = 235
    if request.param == 'png':
        path = tmp_path/'marker.png'
        assert cv2.imwrite(str(path), image[..., ::-1])
    else:
        path = tmp_path/'1-encoder_input.raw'
        y = np.concatenate((image[..., 0], np.full((h, w), 16, np.uint8)), axis=1)
        chroma = np.full((h//2, w), 128, np.uint8)
        data = y.tobytes() + chroma.tobytes()*2
        path.write_bytes(data)
        bs.write_json(path.with_suffix('.json'), dict(
            schema=1, complete=True, timestamp_ns=1, stage='encoder_input', format='yuv420p',
            width=2*w, height=h, bytes=len(data), range='full', matrix='bt709', row_order='top_down'))
    return path


@pytest.mark.parametrize('source_fov,eye_fov', [
    ((-1,1,-1,1), (-1,1,-1,1)),
    ((-1.15,.85,-.9,1.1), (-1.15,.85,-.9,1.1)),
    ((-.923,.923,-.519,.519), (-1,1,-1,1)),
])
def test_top_down_marker_stays_top_left_cpu_and_gl_matrices(marker_asset, source_fov, eye_fov):
    scene = bs.BenchScene(size=(384,416), motion='none', panel='off', backdrop='metro',
                          backdrop_asset=marker_asset, backdrop_fov=source_fov,
                          projections=[bs.projection_raw(eye_fov)]*2)
    b = scene.backdrop
    x,y,w,h = b.central_box
    # The source marker centre and its vertically/horizontally flipped counterparts.
    uv = np.array([[3/16,3/16], [3/16,13/16], [13/16,3/16]])
    texels = [x-.5,y-.5] + uv*[w,h]
    central = b.image[y:y+h,x:x+w]
    assert central[h//6,w//6].min() > 230
    assert central[5*h//6,w//6].max() < 20
    for eye in ('left','right'):
        projected = cv2.perspectiveTransform(texels[None],scene.homography(0,eye,'backdrop'))[0]
        # Independent source rays: negative getProjectionRaw top means +Y/up.
        l,r,t,bottom = source_fov
        rays = np.column_stack((l+uv[:,0]*(r-l), -(t+uv[:,1]*(bottom-t)), -np.ones(3)))
        world = np.column_stack((3*rays+scene.eye_to_head[0,:3,3], np.ones(3)))
        vp = np.array(scene.frame_geometry(0)['eyes'][int(eye == 'right')]['view_projection'])
        clip = world @ vp.T
        expected = np.column_stack(((clip[:,0]/clip[:,3]+1)*scene.size[0]/2-.5,
                                    (1-clip[:,1]/clip[:,3])*scene.size[1]/2-.5))
        np.testing.assert_allclose(projected,expected,atol=1e-10)
        # Same UV -> local vertex convention and VP @ anchor as run_bench's GL quad.
        texture_uv = (texels+.5)/b.size
        local = np.column_stack(((texture_uv[:,0]-.5)*b.metres[0],
                                 (.5-texture_uv[:,1])*b.metres[1], np.zeros(3), np.ones(3)))
        np.testing.assert_allclose(local @ (vp @ b.anchor).T,clip,atol=1e-10)
        assert np.all(projected[0] >= 0) and np.all(projected[0] < np.array(scene.size)/2)
        rendered = scene.render_frame(0,eye)
        samples = np.rint(projected).astype(int)
        assert rendered[samples[0,1],samples[0,0]].min() > 230
        assert rendered[samples[1,1],samples[1,0]].max() < 20
        assert rendered[samples[2,1],samples[2,0]].max() < 20


@pytest.mark.parametrize('source_fov,fractions', [
    ((-.923,.923,-.519,.519), (.479037,.479037)),
    ((-1,1,-1,1), (1.,1.-.064/6)),
])
def test_anchor_source_coverage_excludes_mirrored_padding(dump, source_fov, fractions):
    scene = bs.BenchScene(size=(384,416),motion='none',backdrop='metro',
                          backdrop_asset=dump,backdrop_fov=source_fov)
    x,y,w,h = scene.backdrop.central_box
    edges = np.array([[[x-.5,y-.5],[x+w-.5,y+h-.5]]],np.float64)
    for eye,fraction in zip(('left','right'),fractions):
        projected = cv2.perspectiveTransform(edges,scene.homography(0,eye,'backdrop'))[0]+.5
        extent = np.minimum(projected[1],scene.size)-np.maximum(projected[0],0)
        assert np.prod(extent)/np.prod(scene.size) == pytest.approx(fraction)


@pytest.mark.parametrize('index,eye,digest',[(0,'left','cb682898c718793d1a151e032c6ce06197ac46b6977f2131ff258417d3a99459'),
    (91,'right','66af6d5c2670393fa59a9ac4280f4fd4f777c9bcf07005603e4baaac31ec98d9'),
    (576,'left','2e2db3e383a2b3fa320b629c057c3df332ce05fa42763c3df6df09e67ff71fac')])
def test_none_byte_identical_to_frozen_v2(index,eye,digest):
    scene = bs.BenchScene(seed=17,size=(656,688),backdrop='none')
    assert hashlib.sha256(scene.render_frame(index,eye).tobytes()).hexdigest() == digest


def test_exact_server_matrix_inverse_and_quantized_roundtrip(dump):
    planes,_ = metro_planes(dump)
    rgb = dump_rgb(planes)
    ycc = rgb @ SERVER_MATRIX.T
    np.testing.assert_allclose(ycc[...,0],planes[0],atol=2e-5)
    for i in (1,2):
        np.testing.assert_allclose(score.box2(ycc[...,i])+128,planes[i],atol=2e-5)
    output = score.rgb_planes(np.rint(np.clip(rgb,0,255)).astype(np.uint8),quantize=True)
    for a,b in zip(output,planes):
        assert np.max(np.abs(a.astype(int)-b)) <= 1
    # R8 + 4:2:0 are lossy: arbitrary source RGB is deliberately not claimed recoverable.


def test_backdrop_homography_angular_match_stereo_and_occlusion(scene):
    b = scene.backdrop
    x,y,w,h = b.central_box
    points = np.array([[[x,y],[x+w-1,y+h-1],[x+w/2,y+h/2]]],np.float64)
    left = cv2.perspectiveTransform(points,scene.homography(0,'left','backdrop'))
    np.testing.assert_allclose(left,points-[x,y],atol=1e-10)
    local = np.column_stack(((points[0,:,0]+.5)/b.size[0]*b.metres[0]-b.metres[0]/2,
                            b.metres[1]/2-(points[0,:,1]+.5)/b.size[1]*b.metres[1],np.zeros(3),np.ones(3)))
    geometry = scene.frame_geometry(0)
    for eye in geometry['eyes']:
        clip = local @ b.anchor.T @ np.array(eye['view_projection']).T
        expected = np.column_stack(((clip[:,0]/clip[:,3]+1)*scene.size[0]/2-.5,
                                    (1-clip[:,1]/clip[:,3])*scene.size[1]/2-.5))
        np.testing.assert_allclose(cv2.perspectiveTransform(points,np.array(eye['backdrop_to_eye']))[0],expected,atol=1e-10)
    assert not np.allclose(geometry['eyes'][0]['backdrop_to_eye'],geometry['eyes'][1]['backdrop_to_eye'])
    v2 = bs.BenchScene(size=scene.size,motion='none')
    panel = cv2.warpPerspective(np.ones(scene.panel_labels.shape,np.uint8),scene.homography(0),scene.size).astype(bool)
    interior = score.erode(panel,3)
    np.testing.assert_array_equal(scene.render_frame(0)[interior],v2.render_frame(0)[interior])
    assert np.all(scene.labels(0)[~cv2.dilate(panel.astype(np.uint8),np.ones((7,7),np.uint8)).astype(bool)] == 4)


@pytest.mark.parametrize('angles',[(20,0,0),(-20,0,0),(0,20,0),(0,-20,0)])
def test_mirrored_extension_covers_turns(scene,angles):
    b = scene.backdrop
    geometry = scene.frame_geometry(0,bs.offset_matrix({'degrees':angles,'metres':[0,0,0]}))
    corners = np.array([[[-.5,-.5],[383.49,-.5],[383.49,415.49],[-.5,415.49]]],np.float64)
    for eye in geometry['eyes']:
        uv = cv2.perspectiveTransform(corners,np.linalg.inv(eye['backdrop_to_eye']))[0]
        assert np.all(uv >= -.5) and np.all(uv < np.array(b.size)-.5)
    x,y,w,h = b.central_box
    np.testing.assert_array_equal(b.image[y:y+h,x-8:x],b.image[y:y+h,x:x+8][:,::-1])
    np.testing.assert_array_equal(b.image[y-8:y,x:x+w],b.image[y:y+8,x:x+w][::-1])


def test_load_proxy_ordering_and_near_raw(dump):
    args = SimpleNamespace(bench_seed=1,size=(384,416),bench_assets=None,metro_dump=[dump],bench_backdrop_fov=None)
    report = offline.encoder_load_comparison(args)
    rows = [report[k] for k in ('a_v2_cards','b_mosaic_cards','c_metro_cards','d_raw_metro')]
    fractions = [r['active_32x32_fraction']['2'] for r in rows]
    assert fractions[0] < fractions[1] <= fractions[2], fractions
    assert fractions[1] > fractions[0]+.25, fractions
    assert fractions[0] < fractions[3]*.5
    assert abs(fractions[2]-fractions[3]) < .2, fractions


def test_backdrop_masks_score_and_panel_occlusion(scene):
    truth = score.rgb_planes(scene.render_frame(0))
    output = [p.copy() for p in truth]
    panel = cv2.warpPerspective(np.ones(scene.panel_labels.shape,np.uint8),scene.homography(0),scene.size).astype(bool)
    output[0][panel] += 12
    accumulator = score.ScoreAccumulator(scene,'offline')
    for n in (0,1):
        accumulator.add(truth,output,n)
    report = accumulator.finish()
    assert report['aggregate']['backdrop-natural']['mse_y']['mean'] == 0
    assert report['aggregate']['sat']['mse_y']['mean'] > 0
    assert set(('sat-natural','mura-natural','edge-natural')) <= report['aggregate'].keys()
    assert all(scene.backdrop.masks[k].any() for k in ('sat','mura','edge','natural'))


def test_strip_and_replay(tmp_path,dump):
    scene = bs.BenchScene(size=(656,688),motion='none',backdrop='metro',backdrop_asset=dump,panel='off')
    assert scene.content_anchor[2,3] == pytest.approx(-3)
    top = scene.content_anchor[1,3]+scene.panel_metres[1]/2
    assert np.rad2deg(np.arctan2(-top,3)) > 30
    image = scene.render_frame(5)
    aligned = cv2.warpPerspective(image,np.linalg.inv(scene.homography(5)),scene.panel_size)
    assert bs.decode_barcode(aligned,scene.barcode_box) == 5
    h,_ = score.fit_homography(image,scene,refine=False)
    assert h.shape == (3,3)
    scene.save(tmp_path)
    replay = bs.BenchScene.from_metadata(tmp_path)
    np.testing.assert_array_equal(image,replay.render_frame(5))
    assert scene.backdrop.metadata()['shared_texture'].startswith('left eye')


def test_raw_metro_truth_bytes_and_offline_score(tmp_path,dump,scene):
    source = tmp_path/'truth.y4m'
    offline.write_y4m(source,offline.raw_metro_frames([dump],2),(768,416))
    frames = list(score.iter_y4m(source))
    assert b''.join(p.tobytes() for p in frames[0]) == dump.with_suffix('.raw').read_bytes()
    report = offline.score_metro(source,source,scene)
    assert report['observation_count'] == 2
    assert all(v['mse_y']['mean'] == 0 for v in report['aggregate'].values())


def test_calibration_dry_run_never_gpu(tmp_path,dump,monkeypatch,capsys):
    monkeypatch.setattr(offline.WindowGuard,'status',lambda *a:pytest.fail('GPU guard called'))
    offline.main(['--out',str(tmp_path/'out'),'--work',str(tmp_path/'work'),'--size','384','416',
                  '--metro-dump',str(dump),'--frames','2','--dry-run'])
    plan = json.loads(capsys.readouterr().out)
    assert plan['scene']['backdrop'] == 'metro' and plan['metro_repeat']
    assert not (tmp_path/'out').exists()


def test_bad_backdrop_inputs(dump):
    with pytest.raises(ValueError,match='requires'):
        bs.BenchScene(size=(384,416),backdrop='metro')
    with pytest.raises(ValueError,match='requires'):
        bs.BenchScene(size=(384,416),backdrop='none',panel='off')
    with pytest.raises(ValueError,match='FOV'):
        bs.BenchScene(size=(384,416),backdrop='metro',backdrop_asset=dump,backdrop_fov=[0,0,0,0])


def test_metro_capture_streams_before_game_and_retains_one(tmp_path,dump,monkeypatch):
    from ws.scripts import bench_metro_dump as capture
    import os
    import shutil
    events = []
    active = {'running':True,'cell':'test-metro'}
    def run(argv,**kwargs):
        events.append('game')
        assert any(e == 'stream' for e in events)
        return '1234\n'  # session25.run returns stdout, NOT CompletedProcess
    def health():
        events.append('health')
        if (tmp_path/'server-dumps').exists():
            return
        server = tmp_path/'server-dumps/server-1'; server.mkdir(parents=True)
        for index in (0,9000):
            path = server/f'{index+1}-encoder_input.json'
            meta = json.loads(dump.read_text()); meta['frame_index']=index
            bs.write_json(path,meta)
            shutil.copyfile(dump.with_suffix('.raw'),path.with_suffix('.raw'))
            os.utime(path,(200,200))
    s = SimpleNamespace(OUT=tmp_path,RUNTIME=tmp_path,PYTHON='unused',CLIENT='client',PACKAGE='pkg',
        read=lambda p:active,adopt_active=lambda a:events.append('adopt'),stop_runtime=lambda:[],
        adb=lambda *a:events.append(a) or 'activity',setprop_command=lambda *a:' '.join(a),
        launch=lambda *a:events.append(('launch',os.environ['ALVR_Q3PW_FRAME_DUMP'])),
        wait_session=lambda p,seconds,description:events.append('stream' if 'BEFORE' in description else 'server'),
        write_state=lambda *a:None,run=run,health=health,record=lambda *a,**kw:None)
    monkeypatch.setenv('ALVR_Q3PW_FRAME_DUMP','previous')
    monkeypatch.setattr(capture,'stream_projection',lambda:[[-1,1,-1,1]]*2)
    monkeypatch.setattr(capture.time,'time',lambda:100)
    monkeypatch.setattr(capture.time,'monotonic',lambda:100)
    result = capture.capture_running_cell(s,tmp_path)
    assert result.name == '9001-encoder_input.json'
    assert len(list(result.parent.glob('*.raw'))) == 1
    assert any(isinstance(e,tuple) and e[0]=='launch' and e[1].endswith(':5:4500') for e in events)
    assert json.loads(result.read_text())['projection_raw'] == [[-1,1,-1,1]]*2


def test_metro_restore_retries_and_health_stop_propagates(monkeypatch):
    from ws.scripts import bench_metro_dump as capture
    calls = []
    s = SimpleNamespace(OUT=__import__('pathlib').Path('.'),
        restore=lambda:calls.append('restore') or (0 if len(calls)==3 else 1),
        read=lambda _: {'restored':len(calls)==3})
    capture.restore_verified(s)
    assert len(calls) == 3
    s.health = lambda:(_ for _ in ()).throw(RuntimeError('temperature >=55'))
    with pytest.raises(RuntimeError,match='temperature'):
        capture.monitored_wait(s,lambda _:True,1,'wait')


def test_load_proxy_only_is_cpu(tmp_path,dump,monkeypatch):
    monkeypatch.setattr(offline.WindowGuard,'status',lambda *a:pytest.fail('GPU guard called'))
    offline.main(['--out',str(tmp_path/'out'),'--work',str(tmp_path/'work'),'--size','384','416',
                  '--metro-dump',str(dump),'--load-proxy-only'])
    assert (tmp_path/'out/load-proxy.json').exists()
    assert not (tmp_path/'work').exists()


def test_offline_calibration_encodes_both_sources_with_same_cap(tmp_path,dump,monkeypatch):
    from pathlib import Path
    import shutil
    pair = tmp_path/'out/fake/windows'; pair.mkdir(parents=True)
    for name in ('pyrowave-encode.exe','pyrowave-decode.exe'):
        (pair/name).write_bytes(b'never executed')
    monkeypatch.setattr(offline,'ROOT',tmp_path)
    calls = []
    class Guard:
        def __init__(self,*a,**kw): pass
        def status(self): return {}
        def run(self,argv,**kw):
            calls.append(argv)
            shutil.copyfile(argv[1],argv[2])
            return 0,'CDF 5/3 bytes-needed unavailable (CPU test double)',''
    monkeypatch.setattr(offline,'WindowGuard',Guard)
    offline.main(['--pair','fake','--out',str(tmp_path/'report'),'--work',str(tmp_path/'scratch'),
                  '--window','fake','--size','384','416','--frames','2','--metro-dump',str(dump),
                  '--bench-motion','none'])
    assert len(calls) == 8
    assert {c[-1] for c in calls if Path(c[0]).name == 'pyrowave-encode.exe'} == {'1388888'}
    for profile in ('ours-c9','upstream-like'):
        base = tmp_path/'report'/profile
        calibration = json.loads((base/'calibration.json').read_text())
        assert calibration['metro_repeat']
        assert all(r['metro_dump'] in (None,0) for r in calibration['metrics'])
        assert all(r['metro_dump'] == 0 for r in calibration['metrics'][:3])
        assert (base/'metro-dump/summary.json').exists()
    assert not list((tmp_path/'scratch').iterdir())


def test_two_plane_forward_capture_zero_and_clipping(scene):
    accumulator = score.ScoreAccumulator(scene,'compositor')
    for index in (30,65):
        real = bs.offset_matrix({'degrees':[index/15,1,0],'metres':[.01,0,0]})
        scene.frame_records[index] = scene.frame_geometry(index,real)
        transform = np.array([[.92,.003,12],[-.003,.92,14],[.00001,0,1]])
        rendered = scene.render_frame(index)
        capture = cv2.warpPerspective(rendered.astype(np.float32),transform,scene.size)
        valid = cv2.warpPerspective(np.ones(rendered.shape[:2],np.float32),transform,scene.size) > .999
        planes = score.rgb_planes(capture)
        accumulator.add(planes,planes,index,valid,homography=transform @ scene.homography(index),frame_transform=transform)
    report = accumulator.finish()
    for name in ('sat-natural','mura-natural','edge-natural','backdrop-natural'):
        for key,row in report['aggregate'][name].items():
            if key.startswith(('mse_','lf','flicker')) and not key.endswith('count'):
                assert row['mean'] in (None,0), (name,key,row)
    index = 200
    scene.frame_records[index] = scene.frame_geometry(index,bs.offset_matrix({'degrees':[180,0,0],'metres':[0,0,0]}))
    assert not scene.backdrop_visibility(index).any()
    assert not scene.labels(index).any()
    assert np.all(scene.render_frame(index) == bs.SURROUND)


def test_offline_asymmetric_dump_projection_is_preserved(tmp_path,dump):
    import shutil
    path = tmp_path/dump.name
    shutil.copyfile(dump.with_suffix('.raw'),path.with_suffix('.raw'))
    raw = [[-1.15,.85,-.9,1.1],[-.85,1.15,-.9,1.1]]
    meta = json.loads(dump.read_text()); meta['projection_raw']=raw
    bs.write_json(path,meta)
    args = SimpleNamespace(bench_backdrop_fov=None,metro_dump=[path])
    projections = offline.offline_projections(args)
    scene = bs.BenchScene(size=(384,416),motion='none',backdrop='metro',backdrop_asset=path,projections=projections)
    x,y,w,h = scene.backdrop.central_box
    points = np.array([[[x,y],[x+w-1,y+h-1]]],np.float64)
    np.testing.assert_allclose(cv2.perspectiveTransform(points,scene.homography(0,'left','backdrop')),points-[x,y],atol=1e-10)
    np.testing.assert_allclose(scene.projections[1],bs.projection_raw(raw[1]))

import hashlib
import json

import cv2
import numpy as np
import pytest

from tools.quest3 import bench_scene as bs, stereo_scene
from tools.quest3.bench_score import rgb_planes, planes_to_rgb, fit_homography, fit_colour, apply_colour


@pytest.fixture(scope='module')
def scene():
    return bs.BenchScene(seed=17, size=(656, 688))


def test_determinism_and_labels(scene):
    other = bs.BenchScene(seed=17, size=scene.size)
    different = bs.BenchScene(seed=18, size=scene.size)
    digest = lambda s: hashlib.sha256(s.render_frame(91).tobytes()).hexdigest()
    assert digest(scene) == digest(other)
    assert digest(scene) != digest(different)
    assert set(np.unique(scene.labels(91))) == set(bs.LEGEND)
    assert np.allclose(scene.homography(91), scene.homography(91+bs.PERIOD))
    # Barcode is a unique uint32 submission ID; geometry alone repeats.
    assert not np.array_equal(scene.barcode_patch(91), scene.barcode_patch(91+bs.PERIOD))


def test_trajectory():
    mixed = bs.trajectory(1)
    assert [mixed[i]['segment'] for i in range(0, 900, 180)] == ['tremor', 'jitter', 'pan', 'turn', 'static']
    for mode, target in [('tremor', .035), ('jitter', .2)]:
        t = bs.trajectory(6, mode)
        assert np.std([p['degrees'][0] for p in t]) == pytest.approx(target)
    pan = bs.trajectory(1, 'pan')
    assert (pan[90]['degrees'][0]-pan[0]['degrees'][0]) == pytest.approx(3)
    turn = bs.trajectory(1, 'turn')
    assert turn[36]['degrees'][0] == pytest.approx(12)
    assert turn[72]['degrees'][0] == pytest.approx(0)
    assert all(not any(p['degrees']) and not any(p['metres']) for p in mixed[720:])
    assert bs.trajectory(1, scale=0)[400]['degrees'][0] == 0


@pytest.mark.parametrize('index', [0, 1, 255, 511, 899])
def test_barcode_degradation_and_checksum(scene, index):
    # Start at stream scale and go to compositor's ~2064/2624 scale.
    patch = scene.barcode_patch(index)
    image = np.pad(patch, ((8, 8), (8, 8), (0, 0)), constant_values=28)
    image = planes_to_rgb(rgb_planes(image, quantize=True))
    image = cv2.GaussianBlur(image, (5, 5), .8)
    small = cv2.resize(image, None, fx=.7866, fy=.8023, interpolation=cv2.INTER_LINEAR)
    image = cv2.resize(small, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
    gray = image @ np.array([.2126, .7152, .0722], np.float32)
    image = gray[..., None]+1.4*(image-gray[..., None])
    image += np.random.default_rng(index).normal(0, 2, image.shape)
    assert bs.decode_barcode(image, (8, 8, patch.shape[1], patch.shape[0])) == index
    broken = patch.copy()
    # Flip both halves of a data Manchester bit; contrast remains valid, CRC must fail.
    cw, ch = patch.shape[1]//28, patch.shape[0]//4
    broken[ch:2*ch, :2*cw] = 255-broken[ch:2*ch, :2*cw]
    with pytest.raises(ValueError, match='checksum'):
        bs.decode_barcode(broken, (0, 0, patch.shape[1], patch.shape[0]))


def test_homography_image_fit_below_tenth_pixel(scene):
    image = scene.panel_frame(410)
    h = np.array([[.79, .008, 15.4], [-.009, .80, 20.1], [1.e-5, -1.2e-5, 1]], np.float64)
    capture = cv2.warpPerspective(image, h, (550, 575), flags=cv2.INTER_LINEAR)
    fitted, diagnostics = fit_homography(capture, scene)
    yy, xx = np.mgrid[40:scene.panel_size[1]-40:60, 40:scene.panel_size[0]-40:60]
    points = np.stack((xx, yy), -1).reshape(1, -1, 2).astype(np.float32)
    expected = cv2.perspectiveTransform(points, h)
    actual = cv2.perspectiveTransform(points, fitted)
    rms = np.sqrt(np.mean(np.sum((actual-expected)**2, axis=-1)))
    assert rms < .1, (rms, diagnostics)


def test_colour_fit(scene):
    luma = np.array([.2126, .7152, .0722])
    matrix = 1.28*np.eye(3)+(1-1.28)*np.repeat(luma[:, None], 3, axis=1)
    transform = np.vstack((matrix, [1., -.8, 1.2])).astype(np.float32)
    image = apply_colour(scene.panel_frame(0), transform)
    fitted, diagnostics = fit_colour(image, scene)
    assert np.max(np.abs(np.array(fitted['matrix'])-transform)) < 1e-3
    assert diagnostics['patch_rmse_codes'] < 1e-3
    assert diagnostics['excluded_patches']


def test_manifest_replay_and_tamper(tmp_path, scene):
    assets = tmp_path/'private'; assets.mkdir()
    cv2.imwrite(str(assets/'cover.png'), scene.render_frame(0)[..., ::-1])
    manifest = bs.asset_manifest(assets)
    assert manifest['fallback'] is None
    assert bs.load_asset(manifest['assets'][0]).shape == (*scene.render_frame(0).shape[:2], 3)
    bs.write_json(tmp_path/'assets.json', manifest)
    assert bs.asset_manifest(tmp_path/'assets.json') == manifest
    (assets/'cover.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash changed'):
        bs.asset_manifest(tmp_path/'assets.json')
    with pytest.raises(ValueError, match='hash changed'):
        bs.load_asset(manifest['assets'][0])


def test_save_replay(tmp_path, scene):
    scene.save(tmp_path)
    replay = bs.BenchScene.from_metadata(tmp_path)
    assert np.array_equal(replay.render_frame(87), scene.render_frame(87))
    assert len(json.loads((tmp_path/'trajectory.json').read_text())) == 900
    assert (tmp_path/'labels.png').is_file()
    assert (tmp_path/'panel.png').is_file()


def test_harness_cli_and_legacy_metadata():
    parser = stereo_scene.build_parser()
    args = stereo_scene.validate_args(parser, parser.parse_args(['--out', 'unused', '--quality', '--normalized-chart', '--pulse', '--bench']))
    assert args.bench
    args = parser.parse_args(['--out', 'unused', '--quality', '--normalized-chart', '--pulse', '--jitter', '.3', '--seed', '7'])
    assert stereo_scene.scene_metadata(args, 2624, 2752, []) == {
        'source_eye_size': [2624, 2752], 'quality_chart': True, 'neutral_patch_chart': False,
        'flat_rgb_code': None, 'source_neutral_rgb_codes': [], 'normalized_chart': True,
        'reference_canvas_eye': [2080, 2208], 'pulse': True, 'sway_pixels': 0,
        'jitter_pixels': .3, 'image': None, 'projections': []}

def test_stereo_homography_matches_3d_and_converges():
    raw = [(-1.12, .88, -1.03, 1.07), (-.88, 1.12, -1.03, 1.07)]
    scene = bs.BenchScene(size=(656,688), motion='none', projections=[bs.projection_raw(r) for r in raw])
    geometry = scene.frame_geometry(0)
    points = np.array([[25,30],[100,180],[400,260]], np.float64)
    w,h = scene.panel_size
    plane = np.column_stack(((points[:,0]+.5)/w*bs.PANEL_WIDTH-bs.PANEL_WIDTH/2,
                             bs.PANEL_HEIGHT/2-(points[:,1]+.5)/h*bs.PANEL_HEIGHT, np.zeros(3),np.ones(3)))
    for eye in geometry['eyes']:
        clip = plane @ scene.anchor.T @ np.array(eye['view_projection']).T
        ndc = clip[:,:2]/clip[:,3,None]
        expected = np.column_stack(((ndc[:,0]+1)*scene.size[0]/2-.5,(1-ndc[:,1])*scene.size[1]/2-.5))
        actual = cv2.perspectiveTransform(points[None],np.array(eye['panel_to_eye']))[0]
        np.testing.assert_allclose(actual,expected,atol=1e-10)
    # Rays through the same texture point from each physical eye intersect the panel.
    target = scene.anchor[:3,3]
    for n in (0,1):
        vp = np.array(geometry['eyes'][n]['view_projection'])
        clip = vp @ np.r_[target,1]
        ray = np.linalg.inv(scene.projections[n]) @ [clip[0]/clip[3],clip[1]/clip[3],-1,1]
        ray = ray[:3]/ray[3]
        eye_origin = scene.eye_to_head[n,:3,3]
        hit = eye_origin + ray * (-bs.DISTANCE/ray[2])
        np.testing.assert_allclose(hit,target,atol=1e-10)
    assert not np.allclose(geometry['eyes'][0]['panel_to_eye'],geometry['eyes'][1]['panel_to_eye'])


def test_world_lock_and_real_pose_composition(scene):
    anchor = scene.anchor.copy()
    real = bs.offset_matrix({'degrees':[8.,2.,1.], 'metres':[.04,.02,.01]})
    before = scene.frame_geometry(0)
    after = scene.frame_geometry(0,real)
    np.testing.assert_array_equal(scene.anchor,anchor)
    assert not np.allclose(before['eyes'][0]['panel_to_eye'],after['eyes'][0]['panel_to_eye'])
    virtual = real @ bs.offset_matrix(scene.trajectory[0])
    expected = scene.projections[0] @ np.linalg.inv(virtual @ scene.eye_to_head[0])
    np.testing.assert_allclose(after['eyes'][0]['view_projection'],expected)
    anchored = bs.panel_anchor(real)
    assert anchored[1,3] == pytest.approx(real[1,3])
    np.testing.assert_allclose(anchored[:3,1],[0,1,0])
    assert np.linalg.norm(anchored[:3,3]-real[:3,3]) == pytest.approx(1.5)


def test_layouts_density_and_none():
    for layout in ('cards','metro'):
        scene = bs.BenchScene(size=(656,688),motion='none',layout=layout)
        labels = scene.panel_labels
        assert set(np.unique(labels)) == set(bs.LEGEND)
        assert (labels == 4).sum() > (labels == 1).sum()*3
        center = np.array([[[scene.panel_size[0]/2,scene.panel_size[1]/2],
                            [scene.panel_size[0]/2+1,scene.panel_size[1]/2]]],np.float32)
        projected = cv2.perspectiveTransform(center,scene.homography(0))[0]
        assert 1/np.linalg.norm(projected[1]-projected[0]) == pytest.approx(1.25,abs=.01)
        np.testing.assert_allclose(scene.homography(0),scene.homography(72))
        assert all(not any(t['metres']) and not any(t['degrees']) for t in scene.trajectory)


def test_logged_pose_replay_and_source_geometry(tmp_path,scene):
    scene.save(tmp_path)
    meta = scene.metadata(); meta['live']=True
    bs.write_json(tmp_path/'bench.json',meta)
    real = bs.offset_matrix({'degrees':[3.,1.,0.], 'metres':[.01,0,0]})
    record = scene.frame_geometry(931,real)
    (tmp_path/'frames.ndjson').write_text(json.dumps(record)+'\n')
    replay = bs.BenchScene.from_metadata(tmp_path)
    np.testing.assert_allclose(replay.homography(931),record['eyes'][0]['panel_to_eye'])
    with pytest.raises(ValueError,match='no render-pose'):
        replay.render_frame(31)
    with pytest.raises(ValueError,match='source geometry'):
        bs.BenchScene.from_metadata(tmp_path,(800,800))


def test_barcode_on_projected_panel(scene):
    for eye in ('left','right'):
        frame = scene.render_frame(12031,eye)
        aligned = cv2.warpPerspective(frame,np.linalg.inv(scene.homography(12031,eye)),scene.panel_size)
        assert bs.decode_barcode(aligned,scene.barcode_box) == 12031

def test_projection_raw_asymmetric_frustum_boundaries():
    raw=(-1.1,.9,-.8,1.2)
    projection=bs.projection_raw(raw)
    # Top negative tangent means positive world Y at the top viewport edge.
    corners=np.array([[raw[0],-raw[2],-1,1],[raw[1],-raw[3],-1,1]])
    clip=corners @ projection.T
    np.testing.assert_allclose(clip[:,:2]/clip[:,3,None],[[-1,1],[1,-1]],atol=1e-12)

@pytest.mark.parametrize('backdrop', ['none','mosaic'])
@pytest.mark.parametrize('filter_mode', ['default','cubic4'])
def test_live_loop_mock_uses_current_render_pose_and_distinct_eye_targets(tmp_path,monkeypatch,backdrop,filter_mode):
    from types import SimpleNamespace
    class PoseType:
        def __mul__(self,count):
            return lambda:[SimpleNamespace(bPoseIsValid=True,mDeviceToAbsoluteTracking=SimpleNamespace(m=np.eye(4)[:3])) for _ in range(count)]
    vr=SimpleNamespace(Eye_Left=0,Eye_Right=1,TrackedDevicePose_t=PoseType(),k_unMaxTrackedDeviceCount=1,
                       k_unTrackedDeviceIndex_Hmd=0,Texture_t=SimpleNamespace,VRTextureBounds_t=SimpleNamespace,
                       TextureType_OpenGL=1,ColorSpace_Gamma=2)
    stop=tmp_path/'stop'
    class Compositor:
        waits=0
        submissions=[]
        def waitGetPoses(self,poses,_):
            self.waits+=1
            pose=np.eye(4); pose[0,3]=self.waits*.01
            poses[0].mDeviceToAbsoluteTracking.m=pose[:3]
        def submit(self,eye,texture,bounds):
            self.submissions.append((eye,texture.handle))
            assert (bounds.vMin,bounds.vMax)==(0,1)
            if len(self.submissions)==6: stop.touch()
    compositor=Compositor()
    class GL:
        counter=0
        matrices=[]
        uploads=[]
        level0={}
        quads=[]
        def __getattr__(self,name):
            if name.startswith('GL_'): return name
            return lambda *args:None
        def glGenTextures(self,n):
            self.counter+=1; return self.counter
        glGenFramebuffers=glGenTextures
        def glCheckFramebufferStatus(self,*args): return 'GL_FRAMEBUFFER_COMPLETE'
        def glLoadMatrixf(self,value): self.matrices.append(value.T.copy())
        def glTexSubImage2D(self,*args): self.uploads.append(args[-1].shape)
        def glBindTexture(self,target,texture): self.texture=texture
        def glTexImage2D(self,*args):
            if args[1] == 0 and args[-1] is not None:
                self.level0[self.texture]=args[-1].copy()
        def glBegin(self,*args):
            self.quads.append({'texture':self.texture,'matrix':self.matrices[-1], 'uv':[], 'vertices':[]})
        def glTexCoord2f(self,u,v): self.quads[-1]['uv'].append((u,v))
        def glVertex3f(self,*xyz): self.quads[-1]['vertices'].append(xyz)
    gl=GL()
    system=SimpleNamespace(getProjectionRaw=lambda eye:(-1,1,-1,1),
        getEyeToHeadTransform=lambda eye:SimpleNamespace(m=np.array([[1,0,0,.032 if eye else -.032],[0,1,0,0],[0,0,1,0]])))
    parser=stereo_scene.build_parser()
    from tools.quest3 import bench_filter
    monkeypatch.setattr(bench_filter, 'program', lambda gl, levels: 1000)
    args=parser.parse_args(['--out',str(tmp_path),'--bench','--bench-backdrop',backdrop,'--bench-backdrop-filter',filter_mode,'--bench-motion','none','--stop-file',str(stop),'--seconds','100'])
    original=bs.BenchScene.render_frame
    def only_at_start(self,*a,**kw):
        assert compositor.waits==1,'full CPU image work in live frame loop'
        return original(self,*a,**kw)
    monkeypatch.setattr(bs.BenchScene,'render_frame',only_at_start)
    stereo_scene.run_bench(args,tmp_path,system,compositor,656,688,gl,vr)
    records=[json.loads(line) for line in (tmp_path/'frames.ndjson').read_text().splitlines()]
    assert [r['frame'] for r in records]==[0,1,2]
    assert [r['real_pose'][0][3] for r in records]==[.02,.03,.04]
    metadata=json.loads((tmp_path/'bench.json').read_text())
    assert metadata['anchor'][0][3]==.01
    assert len({handle for _,handle in compositor.submissions})==2
    for i,record in enumerate(records):
        for eye in (0,1):
            stride = 2 if backdrop == 'mosaic' else 1
            offset = stride*(2*i+eye)
            if backdrop == 'mosaic':
                np.testing.assert_allclose(gl.matrices[offset],np.array(record['eyes'][eye]['view_projection']) @ metadata['backdrop']['anchor'],atol=1e-6)
            np.testing.assert_allclose(gl.matrices[offset+stride-1],np.array(record['eyes'][eye]['view_projection']) @ metadata['content_anchor'],atol=1e-6)
    assert len(gl.uploads)==3 and all(shape[1] < metadata['panel_size'][0] for shape in gl.uploads)
    if backdrop == 'mosaic':
        replay=bs.BenchScene.from_metadata(tmp_path)
        b=replay.backdrop
        for n in range(6):
            quad=gl.quads[n*3]  # backdrop, panel, barcode for each eye
            # Top-down pixels are uploaded unchanged; v=0 is the quad's +Y edge.
            np.testing.assert_array_equal(gl.level0[quad['texture']],b.image)
            vertices=np.column_stack((quad['vertices'],np.ones(4)))
            clip=vertices @ quad['matrix'].T
            screen=np.column_stack(((clip[:,0]/clip[:,3]+1)*replay.size[0]/2-.5,
                                    (1-clip[:,1]/clip[:,3])*replay.size[1]/2-.5))
            texels=np.array(quad['uv'],np.float64)*b.size-.5
            h=np.array(records[n//2]['eyes'][n%2]['backdrop_to_eye'])
            np.testing.assert_allclose(screen,cv2.perspectiveTransform(texels[None],h)[0],atol=1e-4)

def test_cpu_replay_clips_panel_behind_camera(scene):
    turned=bs.offset_matrix({'degrees':[180.,0.,0.], 'metres':[0,0,0]})
    record=scene.frame_geometry(0,turned)
    frame=scene.render_frame(0,homography=np.array(record['eyes'][0]['panel_to_eye']))
    assert np.all(frame==bs.SURROUND)

@pytest.mark.parametrize('filter_mode', ['default','ss4'])
def test_cpu_replay_barcode_is_clipped_behind_camera_like_gl(filter_mode):
    # Camera 2.5 m forward: the barcode plane (1.5 m ahead of the start pose) is behind it, so GL
    # draws nothing there. The unclipped warpPerspective mirror image used to paint surround grey
    # over the visible backdrop (5656 wrong pixels at this size).
    scene = bs.BenchScene(seed=3,size=(384,416),motion='none',backdrop='mosaic',backdrop_filter=filter_mode)
    real = bs.offset_matrix({'degrees':[0.,0.,0.],'metres':[0,0,-2.5]})
    scene.frame_records[0] = record = scene.frame_geometry(0,real)
    panel_h = np.array(record['eyes'][0]['panel_to_eye'])
    x,y,w,h = scene.barcode_box
    offset = np.array([[1,0,x],[0,1,y],[0,0,1.]])
    assert not bs.plane_mask((h,w),panel_h @ offset,scene.size).any()
    unclipped = cv2.warpPerspective(np.ones((h,w),np.uint8),panel_h @ offset,scene.size,flags=cv2.INTER_NEAREST).astype(bool)
    assert unclipped.sum() > 1000, 'regression must exercise the mirrored (behind-camera) barcode footprint'
    frame = scene.render_frame(0)
    assert not (frame[unclipped] == bs.SURROUND).all(axis=1).any()
    # Nothing of the barcode is visible: moving it elsewhere on the panel cannot change the frame.
    scene.barcode_box = (0,0,w,h)
    np.testing.assert_array_equal(scene.render_frame(0),frame)

"""Streaming codec / presented / compositor / offline benchmark scoring (CPU only)."""
from __future__ import annotations

import argparse
import base64
import zlib
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.quest3.bench_scene import BenchScene, LEGEND, PERIOD, decode_barcode, write_json, resize_homography, plane_mask
from tools.quest3 import bench_detail, bench_compare

KR, KB = .2126, .0722
DEFINITIONS = {
    'domain': '8-bit full-range BT.709 Y/Cb/Cr; chroma centred at 128, centred 2x2 grid',
    'residual': 'SIGNED output - same-sampling truth in observed grid, then pull residual into fixed panel coordinates',
    'grid': '32x32 panel texels / 16x16 panel chroma; fixed panel origin, not physical encoder tile tracking',
    'sat': 'consecutive: per-pixel signed residual difference RMS pooled per block; compositor: per-pixel population temporal variance, then pool variances per block; extra block-mean std; >1.5-code toggle threshold; >=2 observations/block',
    'mura': 'abs LP residual in panel coordinates, sigmas 8/24 panel texels; explicit Gaussian radius 3*sigma and mask erosion including pullback interpolation support; temporal abs difference or sparse population std',
    'dark': 'truth Y<64 and Sobel magnitude of sigma-2-smoothed truth <4; all chroma footprint pixels eligible',
    'edge': 'edge-class pixels near Sobel magnitude >40, dilated 1px; temporal signed residual difference or compositor std',
    'detail': '32x32 content luma blocks; output/truth energy ratio of Gaussian Laplacian bands sigma .8 and 1.6; >=32 class pixels, truth energy >=0.5 code^2/pixel, full valid block and six-pixel class/support halo; signed truth-correlated detail reported separately; ratios above 1 retained as alias/noise excess; population temporal std; hysteresis toggle if <0.5 and >0.8 occur in either order; sparse captures are not a flicker frequency',
    'psnr': '10log10(255^2/mean clustered MSE); JSON null plus infinite=true for MSE=0, null plus n=0 for unavailable',
    'ssim': 'Y, Gaussian 11x11 sigma1.5, population covariance, C1=6.5025 C2=58.5225; mask eroded 5 pixels',
    'aggregate': 'both eyes clustered by capture/timestamp before any sample count/bootstrap; PSNR derived from MSE including zeros',
    'registration': 'landmark-only frozen per-eye lens with coverage/rank reduction and injectivity check; per-shot homographies; spatial holdouts reserved before fitting, <=0.1 px median and <=0.25 px p95 in every scored footprint cell; forward truth then residual pullback',
    'colour': 'independent full-eye burst: frozen per-channel linear-sRGB gain/offset, optional spatially validated radial gain; held-out RMSE <=1 and p95 <=2 codes; old strip fits are frozen diagnostics only; amplification remains in output-code residuals',
    'compare': 'common eyes, phases and complete-case spatial support; >=4 original captures per contributing block/phase before chronological cluster resampling; worn motion=none refused pending recorded-pose distribution matching',
    'compositor_limit': 'sparse sampled variation, not 90Hz flicker; lens model is landmark-validated, not a calibrated optical truth; actual GL LOD, upstream downsampling and real colour/filter order remain model limits',
}



def box2(plane):
    h, w = plane.shape[:2]
    if h % 2 or w % 2:
        raise ValueError('4:2:0 needs even dimensions')
    return plane.reshape(h//2, 2, w//2, 2, *plane.shape[2:]).mean(axis=(1, 3), dtype=np.float32)


def rgb_planes(rgb, quantize=False):
    """Quantized mode mirrors server R8 4:4:4 -> R8 2x2 box-average 4:2:0."""
    rgb = rgb.astype(np.float32)
    y = rgb @ np.array([KR, 1-KR-KB, KB], np.float32)
    cb, cr = 128+(rgb[..., 2]-y)/(2*(1-KB)), 128+(rgb[..., 0]-y)/(2*(1-KR))
    if quantize:
        # FrameRender.cpp full-range coefficients use +/-127, not +/-127.5.
        cb = 128 + rgb @ np.array([-.1141230, -.3839162, .4980392], np.float32)
        cr = 128 + rgb @ np.array([.4980392, -.4523718, -.0456674], np.float32)
        q = lambda p: np.rint(np.clip(p, 0, 255)).astype(np.uint8)
        return q(y), q(box2(q(cb))), q(box2(q(cr)))
    return y, box2(cb), box2(cr)


def planes_to_rgb(planes):
    y, cb, cr = (p.astype(np.float32) for p in planes)
    cb = cv2.resize(cb, (y.shape[1], y.shape[0]), interpolation=cv2.INTER_LINEAR)-128
    cr = cv2.resize(cr, (y.shape[1], y.shape[0]), interpolation=cv2.INTER_LINEAR)-128
    r, b = y+2*(1-KR)*cr, y+2*(1-KB)*cb
    return np.stack((r, (y-KR*r-KB*b)/(1-KR-KB), b), -1)


def read_dump(path):
    """Local copy of frame_score's schema/domain handling; strict byte counts."""
    path = Path(path)
    m = json.loads(path.read_text(encoding='utf-8-sig'))
    if m.get('schema') != 1 or m.get('complete') is not True:
        raise ValueError(f'incomplete/unsupported dump: {path}')
    if m.get('matrix') != 'bt709' or m.get('range') not in ('full', 'limited') or m.get('row_order') not in ('top_down', 'bottom_up'):
        raise ValueError(f'unknown dump colour domain/row order: {path}')
    w, h = m['width'], m['height']
    if not all(type(v) is int and v > 0 and v % 2 == 0 for v in (w, h)) or w*h > 64*1024*1024:
        raise ValueError('invalid dump geometry')
    fmt = m['format']
    expected = w*h*{'yuv420p': 1.5, 'yuv444p': 3, 'rgba8': 4, 'bgra8': 4}.get(fmt, 0)
    raw = path.with_suffix('.raw')
    if not expected or m['bytes'] != expected or raw.stat().st_size != expected:
        raise ValueError(f'unsupported/truncated dump: {path}')
    data = np.fromfile(raw, np.uint8)
    flip = lambda p: p[::-1] if m['row_order'] == 'bottom_up' else p
    if fmt in ('rgba8', 'bgra8'):
        if m['range'] != 'full':
            raise ValueError('RGB dump must be full range')
        rgb = flip(data.reshape(h, w, 4)[..., :3])
        planes = rgb_planes(rgb[..., ::-1] if fmt == 'bgra8' else rgb)
    else:
        cw, ch = (w//2, h//2) if fmt == 'yuv420p' else (w, h)
        y = flip(data[:w*h].reshape(h, w)).astype(np.float32)
        chroma = [flip(data[o:o+cw*ch].reshape(ch, cw)).astype(np.float32) for o in (w*h, w*h+cw*ch)]
        if m['range'] == 'limited':
            y = np.clip((y-16)*255/219, 0, 255)
            chroma = [np.clip(128+(p-128)*255/224, 0, 255) for p in chroma]
        planes = (y, *(box2(p) if fmt == 'yuv444p' else p for p in chroma))
    return planes, m


def dump_index(directory, stages):
    result = {}
    for path in sorted(Path(directory).rglob('*.json')):
        if not any(path.name.endswith('-'+stage+'.json') for stage in stages):
            continue
        m = json.loads(path.read_text(encoding='utf-8-sig'))
        ts, stage = m.get('timestamp_ns'), m.get('stage')
        if type(ts) is not int or ts < 0 or stage not in stages:
            raise ValueError(f'invalid timestamp/stage: {path}')
        if ts == 0:
            continue  # startup has no transported pose identity
        if (ts, stage) in result:
            raise ValueError('duplicate timestamp/stage; choose one dump run')
        result[ts, stage] = path
    return result


def crop_eye(planes, eye):
    return tuple(p[:, (p.shape[1]//2 if eye == 'right' else 0):
                     (p.shape[1] if eye == 'right' else p.shape[1]//2)] for p in planes)


def iter_y4m(path):
    """No ffmpeg; preserve exact stored 4:2:0 samples. Never load a whole sequence."""
    with Path(path).open('rb') as stream:
        header = stream.readline(4096).decode('ascii').split()
        if not header or header[0] != 'YUV4MPEG2':
            raise ValueError('not y4m')
        fields = {v[0]: v[1:] for v in header[1:] if not v.startswith('X')}
        w, h = int(fields['W']), int(fields['H'])
        if min(w, h) <= 0 or w*h > 64*1024*1024 or w % 2 or h % 2 or fields.get('C') not in ('420', '420jpeg'):
            raise ValueError('only centred 8-bit 4:2:0 supported')
        if 'XCOLORRANGE=FULL' not in header:
            raise ValueError('offline requires full range')
        while True:
            marker = stream.readline(4096)
            if not marker:
                return
            if not (marker == b'FRAME\n' or marker.startswith(b'FRAME ')) or not marker.endswith(b'\n'):
                raise ValueError('invalid y4m frame marker')
            data = stream.read(w*h*3//2)
            if len(data) != w*h*3//2:
                raise ValueError('truncated y4m frame')
            a = np.frombuffer(data, np.uint8)
            yield (a[:w*h].reshape(h, w), a[w*h:w*h*5//4].reshape(h//2, w//2), a[w*h*5//4:].reshape(h//2, w//2))


def fit_homography(capture, scene, refine=True):
    gray = cv2.cvtColor(capture, cv2.COLOR_RGB2GRAY)
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), params)
    corners, ids, _ = detector.detectMarkers(gray)
    known = {f['id']: f['corners'] for f in scene.fiducials}
    pairs = [(known[int(i)], c.reshape(4, 2)) for i, c in zip(ids.ravel() if ids is not None else [], corners) if int(i) in known]
    if len(pairs) < 3:
        raise ValueError('fewer than three benchmark fiducials visible')
    source = np.concatenate([a for a, _ in pairs]).astype(np.float32)
    target = np.concatenate([b for _, b in pairs]).astype(np.float32)
    if not refine:
        # The scoring path reserves cells. The standalone diagnostic helper
        # may use all corners; neither mode fits marker intensity residuals.
        from tools.quest3.bench_registration import spatial_split
        training = ~spatial_split(source, scene.panel_size)
        source, target = source[training], target[training]
    if len(source) < 4:
        raise ValueError('insufficient fiducial training landmarks after spatial holdouts')
    h, inliers = cv2.findHomography(source, target, cv2.RANSAC, 1.5)
    if h is None or inliers.sum() < 4:
        raise ValueError('fiducial homography failed')
    ecc = None
    projected = cv2.perspectiveTransform(source[None], h)[0]
    error = np.linalg.norm(projected-target, axis=1)
    return h, {'markers': len(pairs), 'corner_fit_rms_capture_px': float(np.sqrt(np.mean(error[inliers.ravel() != 0]**2))),
               'ecc': float(ecc) if ecc is not None else None,
               'note': 'corner-fit residual includes corner detector bias; not ground-truth registration error'}


def register_capture(capture, scene):
    h, diagnostics = fit_homography(capture, scene)
    inverse = np.linalg.inv(h)
    aligned = cv2.warpPerspective(capture, inverse, scene.panel_size, flags=cv2.INTER_LINEAR)
    valid = cv2.warpPerspective(np.ones(capture.shape[:2], np.uint8), inverse, scene.panel_size, flags=cv2.INTER_LINEAR) == 1
    valid = erode(valid, 3)
    diagnostics['panel_to_capture'] = h.tolist()
    return aligned, valid, diagnostics


def srgb_decode(rgb):
    x = np.clip(np.asarray(rgb, np.float64)/255, 0, 1)
    return np.where(x <= .04045, x/12.92, ((x+.055)/1.055)**2.4)


def srgb_encode(linear):
    x = np.clip(linear, 0, 1)
    return 255*np.where(x <= .0031308, 12.92*x, 1.055*x**(1/2.4)-.055)


def apply_colour(rgb, transform):
    # Array support for explicit encoded-RGB synthetic fixtures / legacy models.
    if not isinstance(transform, dict):
        return np.clip(rgb.astype(np.float32) @ transform[:3] + transform[3], 0, 255)
    if transform['domain'] == 'linear-eye':
        from tools.quest3 import bench_colour
        yy, xx = np.mgrid[:rgb.shape[0], :rgb.shape[1]]
        uv = np.stack(((xx+.5)/rgb.shape[1], (yy+.5)/rgb.shape[0]), -1)
        return bench_colour.apply(rgb, transform, uv)
    matrix = np.asarray(transform['matrix'])
    if transform['domain'] == 'linear-srgb':
        return srgb_encode(srgb_decode(rgb) @ matrix[:3] + matrix[3]).astype(np.float32)
    return np.clip(np.asarray(rgb, np.float32) @ matrix[:3] + matrix[3], 0, 255).astype(np.float32)


def fit_colour(aligned, scene, valid=None, tolerance=.5):
    source, target, excluded = [], [], []
    for i, patch in enumerate(scene.calibration):
        x,y,w,h = patch['box']
        pad = max(1, min(w,h)//4)
        tile = aligned[y+pad:y+h-pad, x+pad:x+w-pad]
        if not tile.size or (valid is not None and not valid[y+pad:y+h-pad, x+pad:x+w-pad].all()):
            excluded.append(i); continue
        observed = np.median(tile, axis=(0,1))
        if np.any(observed < 3) or np.any(observed > 252):
            excluded.append(i); continue
        source.append(patch['rgb']); target.append(observed)
    source, target = np.asarray(source), np.asarray(target)
    if len(source) < 10:
        raise ValueError('insufficient unclipped calibration patches for held-out validation')
    candidates = []
    for domain in ('linear-srgb', 'encoded-rgb'):
        x = srgb_decode(source) if domain == 'linear-srgb' else source
        y = srgb_decode(target) if domain == 'linear-srgb' else target
        design = np.column_stack((x, np.ones(len(x))))
        if np.linalg.matrix_rank(design) < 4: continue
        errors = []
        # Leave each patch out: no fitted patch validates itself.
        for i in range(len(x)):
            keep = np.arange(len(x)) != i
            matrix = np.linalg.lstsq(design[keep], y[keep], rcond=None)[0]
            predicted = apply_colour(source[i:i+1], {'domain': domain, 'matrix': matrix.tolist()})
            errors.append(predicted[0]-target[i])
        matrix = np.linalg.lstsq(design, y, rcond=None)[0]
        model = {'domain': domain, 'matrix': matrix.tolist()}
        error = float(np.sqrt(np.mean(np.square(errors))))
        candidates.append((error, model))
    error, model = min(candidates, key=lambda item: item[0])
    matrix = np.asarray(model['matrix'])
    # Gain measured in output code space: colour amplification is evidence, not
    # divided away from codec residuals. Use unclipped +/-1-code chroma probes.
    base = np.array([[128.,128.,128.], [160.,100.,70.], [80.,130.,100.]])
    gains = []
    for direction in (np.array([0., -2*KB*(1-KB)/(1-KR-KB), 2*(1-KB)]),
                      np.array([2*(1-KR), -2*KR*(1-KR)/(1-KR-KB), 0.])):
        delta = (apply_colour(base+direction, model)-apply_colour(base-direction, model))/2
        y = delta @ np.array([KR,1-KR-KB,KB])
        gains.extend(np.hypot((delta[:,2]-y)/(2*(1-KB)), (delta[:,0]-y)/(2*(1-KR))).tolist())
    return model, {'domain': model['domain'], 'rgb_matrix': matrix[:3].tolist(), 'rgb_offset': matrix[3].tolist(),
        'patches_used': len(source), 'excluded_patches': excluded,
        'patch_rmse_codes': float(np.sqrt(np.mean((apply_colour(source, model)-target)**2))),
        'held_out_rmse_codes': error, 'measurement_tolerance_codes': tolerance, 'scores_available': error <= tolerance,
        'colour_amplification_chroma': float(np.mean(gains)),
        'singular_values': np.linalg.svd(matrix[:3], compute_uv=False).tolist()}


def erode(mask, radius):
    return cv2.erode(mask.astype(np.uint8), np.ones((2*radius+1, 2*radius+1), np.uint8),
                     borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)


def chroma_mask(mask):
    return box2(mask.astype(np.float32)) == 1


def values_stats(values):
    if not values.size:
        return {'mean': None, 'p99': None, 'count': 0}
    return {'mean': float(values.mean()), 'p99': float(np.percentile(values, 99)), 'count': int(values.size)}


def add_stats(result, prefix, field, mask):
    result.update({prefix+'_'+k: v for k, v in values_stats(np.abs(field[mask])).items()})


def psnr(mse):
    return 10*math.log10(255**2/mse) if mse is not None and mse > 0 else None


def ssim_map(a, b):
    blur = lambda p: cv2.GaussianBlur(p, (11, 11), 1.5)
    ma, mb = blur(a), blur(b)
    va, vb, cov = np.maximum(blur(a*a)-ma*ma, 0), np.maximum(blur(b*b)-mb*mb, 0), blur(a*b)-ma*mb
    return ((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225))


def block_mean(field, block=16):
    h, w = field.shape
    return field[:h//block*block, :w//block*block].reshape(h//block, block, w//block, block).mean(axis=(1, 3))


def block_metrics(cb, cr, eligible):
    rms = np.sqrt(block_mean((cb*cb+cr*cr)*.5))
    valid = block_mean(eligible.astype(np.float32)) == 1
    selected = rms[valid]
    return {'block_rms_mean': float(selected.mean()) if selected.size else None,
            'block_rms_p99': float(np.percentile(selected, 99)) if selected.size else None,
            'toggle_fraction': float((selected > 1.5).mean()) if selected.size else None,
            'blocks': int(selected.size)}


class Moments:
    """Sparse Welford, admitting newly visible pixels with individual counts."""
    def __init__(self, mask):
        self.indices = np.flatnonzero(mask)
        self.n = np.zeros(len(self.indices), np.uint32)
        self.mean = np.zeros(len(self.indices), np.float32)
        self.m2 = np.zeros_like(self.mean)

    def update(self, field, mask):
        current = np.flatnonzero(mask)
        union = np.union1d(self.indices, current)
        if len(union) != len(self.indices):
            positions = np.searchsorted(union, self.indices)
            for key in ('n', 'mean', 'm2'):
                old = getattr(self, key)
                new = np.zeros(len(union), old.dtype)
                new[positions] = old
                setattr(self, key, new)
            self.indices = union
        valid = np.searchsorted(self.indices, current)
        values = field.ravel()[current]
        self.n[valid] += 1
        delta = values-self.mean[valid]
        self.mean[valid] += delta/self.n[valid]
        self.m2[valid] += delta*(values-self.mean[valid])

    def std_values(self):
        valid = self.n >= 2
        return np.sqrt(np.maximum(self.m2[valid]/self.n[valid], 0))


def pullback_support(homography, panel_size):
    """Conservative panel-texel halo for a bilinear observed-grid footprint."""
    w,h = panel_size
    points = np.array([[[x,y] for y in (0,h/2,h-1) for x in (0,w/2,w-1)]],np.float64)
    nonlinear = hasattr(homography, 'forward')
    mapped = homography.forward(points) if nonlinear else cv2.perspectiveTransform(points,homography)
    if nonlinear:
        wcap, hcap = homography.lens.size
        keep = ((mapped[..., 0] >= 2) & (mapped[..., 0] < wcap-2) & (mapped[..., 1] >= 2) & (mapped[..., 1] < hcap-2))
        points, mapped = points[keep], mapped[keep]
        if not len(points):
            raise ValueError('no visible scoring-grid support for lens pullback')
    inverse = None if nonlinear else np.linalg.inv(homography)
    extent = 0.
    for offset in ((2,0),(0,2),(-2,0),(0,-2)):
        back = homography.inverse(mapped+np.asarray(offset)) if nonlinear else cv2.perspectiveTransform(mapped+np.asarray(offset),inverse)
        extent = max(extent,float(np.max(np.linalg.norm(back-points,axis=-1))))
    return max(2,math.ceil(extent)+1)


def content_warp(field, homography, size, chroma=False, nearest=False):
    if hasattr(homography, 'pull'):
        return homography.pull(field, size, chroma, nearest)
    if chroma:
        scale = np.array([[2.,0,.5],[0,2.,.5],[0,0,1.]])
        homography = np.linalg.inv(scale) @ homography @ scale
        size = (size[0]//2, size[1]//2)
    return cv2.warpPerspective(field, homography, size,
        flags=(cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR) | cv2.WARP_INVERSE_MAP)


def packed_blocks(field, ids):
    h,w = field.shape
    blocks = field[:h//16*16,:w//16*16].reshape(h//16,16,w//16,16).transpose(0,2,1,3).reshape(-1,256)
    return base64.b64encode(zlib.compress(blocks[ids].astype('<f4').tobytes(), 1)).decode('ascii')


def unpacked_blocks(value, count):
    return np.frombuffer(zlib.decompress(base64.b64decode(value)), '<f4').reshape(count,256)


def clustered_values(samples, name, metric):
    groups = {}
    for sample in samples:
        value = sample['metrics'][name].get(metric)
        if value is not None:
            groups.setdefault(sample['sample_id'], []).append(value)
    return [float(np.mean(v)) for v in groups.values()]


class _PlaneScore:
    def __init__(self, scene, stage, record_spatial=True):
        self.scene, self.stage = scene, stage
        self.record_spatial = record_spatial
        self.samples, self.previous, self.moments = [], {}, {}
        self.block_samples = []
        self.detail_samples = {name: [] for name in ('sat', 'mura', 'edge', 'natural')}

    def add(self, truth, output, index, valid=None, eye='left', sample_id=None, extra=None, panel=False, homography=None, support_radius=2):
        truth = tuple(p.astype(np.float32) for p in truth)
        output = tuple(p.astype(np.float32) for p in output)
        if any(a.shape != b.shape for a, b in zip(truth, output)):
            raise ValueError('truth/output/scene geometry mismatch; explicit eye crop required')
        if valid is None:
            valid = np.ones(truth[0].shape, bool)
        size = self.scene.panel_size
        affine = np.eye(3) if panel else (homography if homography is not None else self.scene.homography(index, eye))
        if not panel and homography is None and truth[0].shape[::-1] != self.scene.size:
            affine = resize_homography(self.scene.size, truth[0].shape[::-1]) @ affine
        if not panel:
            support_radius = max(support_radius,pullback_support(affine,size))
        residual = tuple(b-a for a,b in zip(truth, output))
        aligned = tuple(content_warp(e, affine, size, n > 0) for n,e in enumerate(residual))
        truth = tuple(content_warp(e, affine, size, n > 0) for n,e in enumerate(truth))
        valid = content_warp(valid.astype(np.float32), affine, size) > .999
        labels = self.scene.panel_labels
        class_masks = getattr(self.scene, 'class_masks', None)
        if class_masks is None:
            class_masks = {name:labels == ident for ident,name in LEGEND.items() if ident}
        support = getattr(self.scene, 'support_mask', None)
        # Residual is formed in the observed sampling grid BEFORE pulling it back.
        residual = aligned
        output = tuple(t+e for t,e in zip(truth, residual))
        sample_id = str(index) if sample_id is None else str(sample_id)
        masks = {}
        metrics = {}
        spatial = {}
        smap = ssim_map(truth[0], output[0])
        detail_truth, detail_output = bench_detail.energy(truth[0]), bench_detail.energy(output[0])
        detail_valid = erode(valid, max(6, support_radius))
        for ident, name in LEGEND.items():
            if not ident:
                continue
            region = class_masks[name]
            mask = erode((region if support is None else support) & valid, max(3,support_radius))
            mask &= region
            cmask = chroma_mask(mask)
            masks[name] = (mask, cmask)
            row = {}
            for channel, e, m in zip(('y', 'cb', 'cr'), residual, (mask, cmask, cmask)):
                mse = float(np.mean(e[m]**2)) if m.any() else None
                row.update({f'mse_{channel}': mse, f'psnr_{channel}_db': psnr(mse), f'pixels_{channel}': int(m.sum())})
            ssim_mask = erode(mask, 5)
            row['ssim_y'] = float(smap[ssim_mask].mean()) if ssim_mask.any() else None
            detail = bench_detail.retention(detail_truth, detail_output, region, detail_valid)
            self.detail_samples[name].append({**detail, 'eye': eye, 'sample_id': sample_id, 'index': index})
            row['detail_retained_mean'] = float(np.mean(detail['retained'])) if detail['retained'] else None
            row['detail_blocks'] = len(detail['ids'])
            correlated = bench_detail.correlation(truth[0], output[0], region, detail_valid)
            row['detail_correlated_mean'] = float(np.mean(correlated['retained'])) if correlated['retained'] else None
            self.detail_samples[name][-1]['correlated'] = correlated['retained']
            spatial[name] = {'mse_y': bench_compare.field(residual[0]**2, mask)} if self.record_spatial else {}
            metrics[name] = row
        del smap
        prior = self.previous.get(eye)
        consecutive = prior is not None and index-prior['index'] == 1
        # Sparse captures deliberately never become a consecutive-frame measurement.
        temporal = consecutive and self.stage != 'compositor'
        diff = tuple(e-p for e, p in zip(aligned, prior['e'])) if temporal else None
        sat_mask = masks['sat'][1]
        metrics['sat'].update(block_metrics(diff[1], diff[2], sat_mask & prior['masks']['sat'][1]) if temporal else
                              {'block_rms_mean': None, 'block_rms_p99': None, 'toggle_fraction': None, 'blocks': 0})
        if temporal and self.record_spatial:
            eligible = block_mean((sat_mask & prior['masks']['sat'][1]).astype(np.float32)) == 1
            rms = np.sqrt(block_mean((diff[1]**2+diff[2]**2)*.5))
            spatial['sat']['block_rms_p99'] = bench_compare.field(rms, eligible)
            spatial['sat']['toggle_fraction'] = bench_compare.field((rms > 1.5).astype(float), eligible)
        if self.stage == 'compositor':
            eligible = block_mean(sat_mask.astype(np.float32)) == 1
            block_ids = np.flatnonzero(eligible)
            self.block_samples.append({'eye': eye, 'sample_id': sample_id, 'index': index, 'ids': block_ids.tolist(),
                'segment': self.scene.trajectory[index % PERIOD]['segment'],
                'cb': packed_blocks(aligned[1], block_ids), 'cr': packed_blocks(aligned[2], block_ids)})
        smooth = cv2.GaussianBlur(truth[0], (0, 0), 2)
        dark = (truth[0] < 64) & (np.hypot(cv2.Sobel(smooth, cv2.CV_32F, 1, 0), cv2.Sobel(smooth, cv2.CV_32F, 0, 1)) < 4)
        current_lp = {}
        for sigma in (8, 24):
            safe = erode((class_masks['mura'] if support is None else support) & valid, 3*sigma+support_radius)
            safe &= class_masks['mura']
            safe_dark = safe & dark
            for channel, n in (('y', 0), ('cb', 1), ('cr', 2)):
                radius = 3*sigma//(2 if n else 1)
                lp = cv2.GaussianBlur(residual[n], (2*radius+1, 2*radius+1), sigma/(2 if n else 1))
                for suffix, mask in (('', safe), ('_dark', safe_dark)):
                    if n:
                        mask = chroma_mask(mask)
                    key = f'lf{sigma}_{channel}{suffix}'
                    add_stats(metrics['mura'], key, lp, mask)
                    if self.record_spatial and key in ('lf8_y', 'lf24_y_dark'):
                        spatial['mura'][key+'_p99'] = bench_compare.field(np.abs(lp), mask)
                    if self.stage == 'compositor':
                        self._moment((eye, 'mura', key+'_temporal'), lp, mask)
                    elif temporal:
                        prev_lp, prev_mask = prior['lp'][key]
                        add_stats(metrics['mura'], key+'_temporal', lp-prev_lp, mask & prev_mask)
                    else:
                        add_stats(metrics['mura'], key+'_temporal', lp, np.zeros_like(mask))
                    # Reuse arrays for normal/dark masks; only previous residual LPs retained.
                    if self.stage != 'compositor':
                        current_lp[key] = (lp, mask)
        grad = np.hypot(cv2.Sobel(truth[0], cv2.CV_32F, 1, 0), cv2.Sobel(truth[0], cv2.CV_32F, 0, 1))
        edge = cv2.dilate((grad > 40).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        edge &= erode((class_masks['edge'] if support is None else support) & valid, max(3,support_radius)) & class_masks['edge']
        edge_mse = float(np.mean(residual[0][edge]**2)) if edge.any() else None
        metrics['edge']['edge_mse_y'] = edge_mse
        metrics['edge']['edge_psnr_y_db'] = psnr(edge_mse)
        metrics['edge']['edge_pixels'] = int(edge.sum())
        if self.stage == 'compositor':
            self._moment((eye, 'edge', 'flicker'), aligned[0], edge)
        else:
            add_stats(metrics['edge'], 'flicker', diff[0] if temporal else aligned[0],
                      edge & prior['edge'] if temporal else np.zeros_like(edge))
        if self.record_spatial:
            spatial['edge']['flicker_p99'] = bench_compare.field(
                aligned[0] if self.stage == 'compositor' else np.abs(diff[0]) if temporal else aligned[0],
                edge if self.stage == 'compositor' else edge & prior['edge'] if temporal else np.zeros_like(edge))
        self.samples.append({'spatial': spatial, 'index': index, 'eye': eye, 'sample_id': sample_id, 'consecutive': temporal,
                             'segment': self.scene.trajectory[index % PERIOD]['segment'], 'metrics': metrics, **(extra or {})})
        if self.stage != 'compositor':
            self.previous[eye] = {'e': aligned, 'masks': masks, 'index': index, 'edge': edge, 'lp': current_lp}

    def _moment(self, key, field, mask):
        if key not in self.moments:
            self.moments[key] = Moments(mask)
        self.moments[key].update(field, mask)

    def finish(self):
        aggregate = {}
        for name in ('sat', 'mura', 'edge', 'natural'):
            keys = {k for s in self.samples for k in s['metrics'][name]}
            aggregate[name] = {k: distribution(clustered_values(self.samples, name, k)) for k in sorted(keys)}
        if self.stage == 'compositor':
            sat = compositor_blocks(self.block_samples)
            for key, value in sat.items():
                aggregate['sat'][key] = {'mean': value, 'std': None, 'n': len({s['sample_id'] for s in self.block_samples}), 'ci95': None}
            # Pool eligible pixel std values across eyes before taking percentiles.
            grouped = {}
            for (_, name, key), moments in self.moments.items():
                grouped.setdefault((name, key), []).append(moments)
            for (name, key), rows in grouped.items():
                statistics = values_stats(np.concatenate([row.std_values() for row in rows]))
                for stat in ('mean', 'p99'):
                    aggregate[name][key+'_'+stat] = {'mean': statistics[stat],
                        'std': None, 'n': len({s['sample_id'] for s in self.samples}), 'pixels': statistics['count'], 'ci95': None}
        for name, fields in aggregate.items():
            for key, value in bench_detail.temporal(self.detail_samples[name]).items():
                fields[key] = {'mean': value, 'std': None, 'n': len({s['sample_id'] for s in self.samples}), 'ci95': None}
            for channel in ('y','cb','cr'):
                mse = fields.get('mse_'+channel, {}).get('mean')
                key = 'psnr_'+channel+'_db'
                fields[key] = {'mean': psnr(mse), 'infinite': mse == 0, 'n': fields.get('mse_'+channel, {}).get('n', 0),
                               'std': None, 'ci95': None}
        edge_mse = aggregate['edge'].get('edge_mse_y', {})
        aggregate['edge']['edge_psnr_y_db'] = {'mean': psnr(edge_mse.get('mean')),
            'infinite': edge_mse.get('mean') == 0, 'n': edge_mse.get('n',0), 'std': None, 'ci95': None}
        meta = self.scene.metadata()
        identity = {k: meta[k] for k in ('version', 'seed', 'motion', 'scale', 'period', 'layout', 'panel_size', 'projections', 'eye_to_head', 'reference_size', 'renderer_sha256', 'numpy', 'opencv', 'assets_manifest', 'panel_mode', 'backdrop')}
        identity['backdrop_renderer_sha256'] = meta['backdrop_renderer_sha256']
        identity['backdrop_filter'] = meta.get('backdrop_filter', 'default')
        identity['filter_shader_sha256'] = meta.get('filter_shader_sha256')
        if identity['backdrop']:
            identity['backdrop'] = {k:v for k,v in identity['backdrop'].items() if k not in ('anchor','fov_source')}
        return {'schema': 1, 'stage': self.stage, 'scene': meta, 'comparison_identity': identity,
                'definitions': DEFINITIONS, 'samples': self.samples, 'aggregate': aggregate,
                'compositor_blocks': self.block_samples, 'sample_count': len(self.samples), 'observation_count': len({s['sample_id'] for s in self.samples}),
                'detail_samples': self.detail_samples,
                'acceptance': 'unverified: requires owner-labelled live A/B and one-time worn check'}


class ScoreAccumulator(_PlaneScore):
    """Score each plane in its own fixed coordinates; retain v2 panel metrics."""
    def __init__(self, scene, stage, record_spatial=True):
        super().__init__(scene,stage,record_spatial)
        self.background = None
        if scene.backdrop:
            from types import SimpleNamespace
            b = scene.backdrop
            view = SimpleNamespace(panel_size=b.size, panel_labels=np.full(b.image.shape[:2],4,np.uint8),
                size=scene.size, class_masks=b.masks, support_mask=b.masks['natural'],
                trajectory=scene.trajectory, metadata=scene.metadata,
                homography=lambda index,eye:scene.homography(index,eye,'backdrop'))
            self.background = _PlaneScore(view,stage,record_spatial)

    def add(self, truth, output, index, valid=None, eye='left', sample_id=None, extra=None,
            panel=False, homography=None, support_radius=2, frame_transform=None):
        if self.background and panel:
            raise ValueError('two-plane scoring needs residuals in the observed grid, not panel-only residuals')
        panel_valid = valid
        if self.background:
            panel_h = homography if homography is not None else resize_homography(self.scene.size,truth[0].shape[::-1]) @ self.scene.homography(index,eye)
            panel_valid = plane_mask(self.scene.panel_labels.shape,panel_h,truth[0].shape[::-1])
            if valid is not None:
                panel_valid &= valid
        super().add(truth,output,index,panel_valid,eye,sample_id,extra,panel,homography,support_radius)
        if self.background:
            scene = self.scene
            transform = frame_transform
            if transform is None:
                transform = (homography @ np.linalg.inv(scene.homography(index,eye)) if homography is not None
                             else resize_homography(scene.size,truth[0].shape[::-1]))
            visible = scene.backdrop_visibility(index,eye,truth[0].shape[::-1],transform)
            if valid is not None:
                visible &= valid
            self.background.add(truth,output,index,visible,eye,sample_id,extra,
                                homography=transform @ scene.homography(index,eye,'backdrop'))

    def finish(self):
        result = super().finish()
        if self.background:
            report = self.background.finish()
            rename = lambda name: name+'-natural' if name != 'natural' else 'backdrop-natural'
            result['aggregate'].update({rename(k):v for k,v in report['aggregate'].items()})
            for sample,background in zip(result['samples'],report['samples']):
                sample['metrics'].update({rename(k):v for k,v in background['metrics'].items()})
                sample['spatial'].update({rename(k):v for k,v in background['spatial'].items()})
            result['backdrop_compositor_blocks'] = report['compositor_blocks']
            result['detail_samples'].update({rename(k): v for k, v in report['detail_samples'].items()})
            result['definitions'] = {**DEFINITIONS, 'backdrop': 'separate fixed plane grid, overlapping automatic natural subclasses; panel silhouette dilated 3 eye pixels before pullback, then normal support erosion; mirrored extension included'}
        return result


def bootstrap_indices(n, rng):
    """Circular moving-block bootstrap avoids treating adjacent frames as independent."""
    length = max(1, round(np.sqrt(n)))
    starts = rng.integers(0, n, (math.ceil(n/length), 1))
    return ((starts+np.arange(length)) % n).ravel()[:n]


def distribution(values):
    a = np.asarray([v for v in values if v is not None], np.float64)
    if not len(a):
        return {'mean': None, 'std': None, 'n': 0, 'ci95': None}
    rng = np.random.default_rng(341)
    ci = np.percentile([a[bootstrap_indices(len(a), rng)].mean() for _ in range(300)], [2.5, 97.5]).tolist() if len(a) >= 3 else None
    return {'mean': float(a.mean()), 'std': float(a.std()), 'n': len(a), 'ci95': ci}


def compositor_blocks(samples):
    fields, block_means = [], []
    for eye in sorted({s['eye'] for s in samples}):
        selected = [s for s in samples if s['eye'] == eye]
        ids = sorted({i for s in selected for i in s['ids']})
        if not ids: continue
        lookup = {ident:n for n,ident in enumerate(ids)}
        count = np.zeros(len(ids), np.int32)
        mean = np.zeros((len(ids),2,256), np.float64)
        m2 = np.zeros_like(mean)
        bm = np.zeros((len(ids),2), np.float64)
        bm2 = np.zeros_like(bm)
        for sample in selected:
            positions = np.array([lookup[i] for i in sample['ids']], np.int64)
            if not len(positions): continue
            values = np.stack([unpacked_blocks(sample[c], len(positions)) for c in ('cb','cr')], axis=1)
            count[positions] += 1
            delta = values-mean[positions]
            mean[positions] += delta/count[positions,None,None]
            m2[positions] += delta*(values-mean[positions])
            block = values.mean(axis=2)
            delta = block-bm[positions]
            bm[positions] += delta/count[positions,None]
            bm2[positions] += delta*(block-bm[positions])
        valid = count >= 2
        fields.extend(np.sqrt((m2[valid]/count[valid,None,None]).mean(axis=(1,2))).tolist())
        block_means.extend(np.sqrt((bm2[valid]/count[valid,None]).mean(axis=1)).tolist())
    a = np.asarray(fields)
    return {'block_rms_mean': float(a.mean()) if a.size else None,
            'block_rms_p99': float(np.percentile(a,99)) if a.size else None,
            'toggle_fraction': float((a > 1.5).mean()) if a.size else None, 'blocks': int(a.size),
            'block_mean_std_p99': float(np.percentile(block_means,99)) if a.size else None}


def refine_source_registration(capture, scene, index, eye, panel_to_capture):
    """Landmark-only homography with a zero (frozen planar) lens."""
    from tools.quest3 import bench_registration as reg
    source = scene.render_frame(index, eye)
    lens = reg.Lens(capture.shape[1::-1])
    norm = np.array([[1/lens.scale, 0, -lens.centre[0]/lens.scale],
                     [0, 1/lens.scale, -lens.centre[1]/lens.scale], [0, 0, 1.]])
    mapping = reg.PlaneMap(lens, norm @ panel_to_capture @ np.linalg.inv(scene.homography(index, eye)))
    a, b = reg.matches(reg.features(source), reg.features(capture), mapping)
    held = reg.spatial_split(a, scene.size)
    mapping, _, _ = reg.refine_plane(mapping, a[~held], b[~held])
    transform = np.linalg.inv(norm) @ mapping.homography
    return source, transform, {'source_to_capture': transform.tolist(), 'source_size': list(scene.size),
                               'geometry': reg.validate_plane(mapping, a[held], b[held], np.ones(source.shape[:2], bool))}


def capture_residual(capture, source, source_to_capture, colour, panel_to_capture, panel_size):
    # Colour acts on the rendered source, then capture sampling. Never compare an
    # inverse-warped capture with a sharper directly rendered panel.
    truth = cv2.warpPerspective(apply_colour(source, colour), source_to_capture,
                                capture.shape[1::-1], flags=cv2.INTER_LINEAR,
                                borderValue=(28,28,28))
    residual = capture.astype(np.float32)-truth
    inverse = np.linalg.inv(panel_to_capture)
    pulled = cv2.warpPerspective(residual, inverse, panel_size, flags=cv2.INTER_LINEAR)
    reference = cv2.warpPerspective(truth, inverse, panel_size, flags=cv2.INTER_LINEAR)
    valid_capture = cv2.warpPerspective(np.ones(source.shape[:2],np.float32), source_to_capture,
                                       capture.shape[1::-1], flags=cv2.INTER_LINEAR) > .999
    valid = cv2.warpPerspective(erode(valid_capture,2).astype(np.float32), inverse,
                                panel_size, flags=cv2.INTER_LINEAR) > .999
    return reference, pulled, erode(valid,2)


def score_compositor(directory, scene, eye='left', registration='auto', calibration=None):
    from tools.quest3.bench_lens_score import score_lens
    requested_mode = registration
    result = score_lens(directory, scene, eye, calibration=calibration, planar=requested_mode != 'lens')
    if requested_mode == 'auto' and not result['sample_count'] and not result.get('diagnostic_sample_count') and result['rejected']:
        return score_lens(directory, scene, eye, calibration=calibration)
    return result


def score_dumps(server, client, scene, stage='codec', eye='left'):
    sources = dump_index(server, ('encoder_input',))
    wanted = ('post_decode',) if stage == 'codec' else ('presented_left', 'presented_right')
    outputs = dump_index(client, wanted)
    score = ScoreAccumulator(scene, stage)
    rejected, unmatched = [], []
    for (ts, output_stage), path in sorted(outputs.items()):
        source = sources.get((ts, 'encoder_input'))
        if source is None:
            unmatched.append({'timestamp_ns': ts, 'stage': output_stage}); continue
        full_truth, _ = read_dump(source)
        full_output, _ = read_dump(path)
        for side in ('left', 'right') if eye == 'both' else (eye,):
            if stage == 'presented' and output_stage != 'presented_'+side:
                continue
            truth = crop_eye(full_truth, side)
            output = crop_eye(full_output, side) if stage == 'codec' else full_output
            try:
                rgb = np.rint(np.clip(planes_to_rgb(truth),0,255)).astype(np.uint8)
                h, _ = fit_homography(rgb, scene, refine=False)
                panel = cv2.warpPerspective(rgb,np.linalg.inv(h),scene.panel_size,flags=cv2.INTER_LINEAR)
                index = decode_barcode(panel, scene.barcode_box)
                # Exact dump residual; geometry only supplies masks/alignment.
                score.add(truth, output, index, eye=side, sample_id=str(ts), homography=h if not scene.live else None)
            except ValueError as exc:
                rejected.append({'timestamp_ns': ts, 'eye': side, 'reason': str(exc)})
    report = score.finish()
    report.update(rejected=rejected, unmatched_client=unmatched,
                  unmatched_server=sorted(ts for ts, _ in sources if not any(t == ts for t, _ in outputs)))
    return report


def score_offline(decoded, scene, start=0, stereo=False, truth_path=None):
    score = ScoreAccumulator(scene, 'offline')
    references = iter_y4m(truth_path) if truth_path else None
    paths = sorted(Path(decoded).glob('*-post_decode.json')) if Path(decoded).is_dir() else None
    if paths is not None:
        paths = sorted(paths, key=lambda p: int(p.name.split('-')[0]))
    frames = (read_dump(p)[0] for p in paths) if paths is not None else iter_y4m(decoded)
    for n, frame in enumerate(frames):
        index = start+n
        full_truth = next(references, None) if references is not None else None
        if references is not None and full_truth is None:
            raise ValueError('decoded contains more frames than truth')
        for eye in ('left','right') if stereo else ('left',):
            truth = (crop_eye(full_truth,eye) if stereo else full_truth) if full_truth is not None else rgb_planes(scene.render_frame(index,eye),quantize=True)
            output = crop_eye(frame,eye) if stereo else frame
            score.add(truth,output,index,eye=eye,sample_id=str(n))
    if references is not None and next(references, None) is not None:
        raise ValueError('decoded contains fewer frames than truth')
    return score.finish()


TABLE_METRICS = [('sat', 'toggle_fraction'), ('sat', 'block_rms_p99'), ('mura', 'lf8_y_p99'),
                 ('mura', 'lf24_y_dark_p99'), ('edge', 'flicker_p99'), ('natural', 'psnr_y_db')]


def summary_markdown(report):
    lines = [f"Stage: **{report['stage']}**; {report['sample_count']} validated eye samples; "
             f"{report.get('diagnostic_sample_count', 0)} diagnostic; {len(report.get('rejected', []))} rejected.", '']
    fmt = lambda v: 'n/a' if v is None else f'{v:.5g}'
    metrics = list(TABLE_METRICS)
    metrics += [('sat-natural','block_rms_p99'), ('mura-natural','lf8_y_p99'),
                ('edge-natural','flicker_p99'), ('backdrop-natural','psnr_y_db')]
    for aggregate_key, title in (('aggregate', 'Validated'), ('diagnostic_aggregate', 'Conditional diagnostics only')):
        aggregate = report.get(aggregate_key)
        if not aggregate:
            continue
        lines += [f'**{title}**', '', '| Class | Metric | Mean | Registration-noise floor | Interpretation |',
                  '|---|---|---:|---:|---|']
        selected = metrics+[(name, metric) for name in aggregate for metric in
                            ('detail_retained_mean', 'detail_correlated_mean', 'detail_std_p99', 'detail_toggle_fraction')]
        for name, metric in selected:
            if name not in aggregate:
                continue
            row = aggregate[name].get(metric, {})
            value = 'infinity' if row.get('infinite') else fmt(row.get('mean'))
            floor = fmt(row.get('registration_noise_floor'))
            if row.get('registration_noise_domain'):
                floor += ' ('+row['registration_noise_domain']+')'
            lines.append(f"| {name} | {metric} | {value} | {floor} | {row.get('registration_interpretation', 'n/a')} |")
        lines.append('')
    lines += [report['acceptance'], '',
              'Sparse compositor samples measure sampled variation, not sustained VR rate or 90 Hz flicker.',
              'Geometry/colour validation, frozen models and per-metric perturbation controls are in summary.json.']
    return '\n'.join(lines)+'\n'


def save_report(report, directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    write_json(directory/'summary.json', report)
    (directory/'summary.md').write_text(summary_markdown(report), encoding='utf-8')


def phase_key(sample):
    segment = sample['segment']
    # Stationary AR(1) segments share exposure statistics. Directional motion
    # uses 1/3-second bins to distinguish outbound/return/holds.
    return (segment, 0 if segment in ('static','none','tremor','jitter') else sample['index'] % PERIOD // 30)


def matched_groups(reports, minimum_coverage=.8):
    return bench_compare.matched_groups(reports, phase_key, minimum_coverage)


def comparison_value(report, groups, name, metric, support=None):
    if support is None:
        rows = bench_compare.observations(report, groups, name, metric)
        support = {eye: set.intersection(*(set(bench_compare.ids(row)) for e, _, row in rows if e == eye))
                   for eye in {e for e, _, _ in rows}}
    unique = list({g[0]['sample_id']: g for g in groups}.values())
    return bench_compare.PreparedMetric(report, unique, name, metric, support)(groups)


def compare_reports(reports, names, margin=.2, repetitions=500):
    if len(reports) < 2 or len(names) != len(reports) or repetitions < 1 or not np.isfinite(margin) or margin < 0:
        raise ValueError('compare requires two runs and a finite nonnegative margin')
    if any(not bench_compare.same_identity(r['comparison_identity'], reports[0]['comparison_identity']) or r['stage'] != reports[0]['stage'] for r in reports[1:]):
        raise ValueError('different assets/scene/stage: runs are not comparable')
    grouped,weights,coverage = matched_groups(reports)
    if reports[0]['stage'] == 'compositor' and any(r.get('colour_calibration_id') != reports[0].get('colour_calibration_id') for r in reports[1:]):
        raise ValueError('not comparable: colour parameters must use the same frozen per-eye calibration')
    supports = {}
    def support(name, metric, key):
        token = (name, metric, key)
        if token not in supports:
            supports[token] = bench_compare.common_support(reports, grouped, key, name, metric)
        return supports[token]
    lines = [f'Shared phase coverage: {coverage}; common phase weights: {weights}.', '',
             '| Class / metric | Ranking (best first) | Values |','|---|---|---|']
    def weighted(values):
        if any(v is None for v in values): return None
        return float(sum(v*w for v,w in zip(values,weights.values())))
    prepared_metrics = {}
    def prepared(report, phases, name, metric, key):
        token = (id(report), name, metric, key)
        if token not in prepared_metrics:
            prepared_metrics[token] = bench_compare.PreparedMetric(report, list(phases[key].values()), name, metric, support(name,metric,key))
        return prepared_metrics[token]
    table_metrics = list(TABLE_METRICS)
    table_metrics += [(name, metric) for name in reports[0]['aggregate']
                      for metric in ('detail_retained_mean', 'detail_correlated_mean', 'detail_std_p99', 'detail_toggle_fraction')]
    if all('backdrop-natural' in r['aggregate'] for r in reports):
        table_metrics += [('sat-natural','block_rms_p99'),('mura-natural','lf8_y_p99'),
                          ('edge-natural','flicker_p99'),('backdrop-natural','psnr_y_db')]
    for name,metric in table_metrics:
        entries = []
        for report,label,phases in zip(reports,names,grouped):
            measured = 'mse_'+metric[5:-3] if metric.startswith('psnr_') else metric
            value = weighted([prepared(report,phases,name,measured,k)(list(phases[k].values())) for k in weights])
            if value is not None:
                if metric.startswith('psnr_'):
                    value = math.inf if value == 0 else psnr(value)
                entries.append((value,label))
        # Energy retention is diagnostic; signed correlation separately detects
        # contrast reversals and replacement noise.
        if metric != 'detail_retained_mean':
            entries.sort(key=lambda item: item[0], reverse=metric.startswith('psnr') or metric == 'detail_correlated_mean')
        if entries:
            best = entries[0][0]
            def fmt(v):
                if math.isinf(v): return 'infinity (MSE=0)'
                if metric.startswith('psnr'): return f'{v:.5g} ({v-best:+.3g} dB)'
                return f'{v:.5g} ({v/best:.3g}x)' if best else f'{v:.5g}'
            ranking = ' < '.join(label for _,label in entries) if metric != 'detail_retained_mean' else ', '.join(label for _,label in entries)+' (energy diagnostic)'
            lines.append(f"| {name} / {metric} | {ranking} | {', '.join(fmt(v) for v,_ in entries)} |")
        else:
            lines.append(f'| {name} / {metric} | unavailable | insufficient common spatial observations; re-score older reports |')
    rng = np.random.default_rng(913)
    checks = []
    for name,metric in (('sat','block_rms_p99'),('mura','lf8_y_p99')):
        draws = []
        for report,phases in zip(reports[:2],grouped[:2]):
            selected = {}
            for key in weights:
                selected[key] = bench_compare.eligible_groups(report, list(phases[key].values()), name, metric)
                if not any(support(name,metric,key).values()):
                    selected[key] = []
            if sum(map(len,selected.values())) < 4 or any(len(v) < 4 for v in selected.values()):
                draws.append(None); continue
            values = []
            for _ in range(repetitions):
                values.append(weighted([prepared(report,phases,name,metric,key)([groups[j] for j in bootstrap_indices(len(groups),rng)]) for key,groups in selected.items()]))
            draws.append(None if any(v is None for v in values) else np.asarray(values))
        if any(a is None for a in draws):
            checks.append(False); lines.append(f'\n{name}: insufficient common spatial support: requires >=4 distinct original capture IDs per contributing block and phase before resampling.'); continue
        lo,hi = np.percentile(draws[0]-(1+margin)*draws[1],[2.5,97.5])
        checks.append(lo > 0)
        lines.append(f'\n{name}: A - {1+margin:g}*B 95% interval [{lo:.4g}, {hi:.4g}] codes ({repetitions} phase-stratified moving-block capture-cluster resamples).')
    verdict = all(checks)
    lines.append(f"\nVerdict: {'PASS' if verdict else 'NOT ESTABLISHED'} ? A={names[0]} worse than B={names[1]} on sat and mura by >{margin:.0%}. Owner live acceptance remains unverified.")
    return '\n'.join(lines)+'\n',verdict


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    score = sub.add_parser('score')
    score.add_argument('--stage', required=True, choices=('codec', 'presented', 'compositor', 'offline'))
    score.add_argument('--scene', required=True, type=Path)
    score.add_argument('--out', required=True, type=Path)
    score.add_argument('--input', type=Path)
    score.add_argument('--server', type=Path)
    score.add_argument('--client', type=Path)
    score.add_argument('--truth', type=Path)
    score.add_argument('--eye', choices=('left', 'right', 'both', 'single'), default='left')
    score.add_argument('--size', type=int, nargs=2, help='scoring stream-eye size; default 2624x2752 for live dumps')
    score.add_argument('--start', type=int, default=0)
    score.add_argument('--stereo', action='store_true')
    score.add_argument('--calibration', type=Path, help='independent full-eye calibration burst; reuse the same burst for A/B')
    score.add_argument('--registration', choices=('auto', 'planar', 'lens'), default='auto')
    compare = sub.add_parser('compare')
    compare.add_argument('runs', nargs='+', type=Path)
    compare.add_argument('--margin', type=float, default=.2)
    args = parser.parse_args(argv)
    if args.command == 'compare':
        reports = [json.loads((p/'summary.json' if p.is_dir() else p).read_text(encoding='utf-8-sig')) for p in args.runs]
        text, _ = compare_reports(reports, [p.name for p in args.runs], args.margin)
        print(text)
        return 0
    size = args.size
    scene = BenchScene.from_metadata(args.scene, size)
    source_metadata = json.loads((args.scene/'bench.json' if args.scene.is_dir() else args.scene).read_text(encoding='utf-8-sig'))
    if args.stage == 'compositor':
        if not args.input:
            parser.error('--input burst directory required')
        report = score_compositor(args.input, scene, args.eye, args.registration, args.calibration)
    elif args.stage == 'offline':
        if not args.input:
            parser.error('--input decoded y4m/raw-dump directory required')
        report = score_offline(args.input, scene, args.start, args.stereo, args.truth)
    else:
        if not args.server or not args.client or args.eye == 'single':
            parser.error('--server and --client required; select left/right/both')
        report = score_dumps(args.server, args.client, scene, args.stage, args.eye)
    report['source_scene'] = source_metadata.get('bench', source_metadata)
    save_report(report, args.out)
    print(summary_markdown(report))
    return 0 if report['sample_count'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

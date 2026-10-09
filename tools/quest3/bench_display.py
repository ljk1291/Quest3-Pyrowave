"""CPU uniform-display experiment model; no hardware or codec process creation.

D = presented decoded YUV, U = presented exact encoder-input YUV, T = common
RGB master integrated over display footprints. All metrics use float 4:4:4.
The ALVR filter equations remain credited to Quest3-Pyrowave/JMS1717 upstream.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

import cv2
import numpy as np

from tools.quest3 import bench_detail
from tools.quest3.bench_backdrop import natural_masks
from tools.quest3.bench_scene import sha256, write_json, resize_homography, plane_mask
from tools.quest3.bench_score import (rgb_planes, planes_to_rgb, srgb_decode, srgb_encode,
    iter_y4m, crop_eye, erode, block_metrics, add_stats, psnr, ssim_map, bootstrap_indices)

SHADER = Path(__file__).resolve().parents[2]/'ws/worktrees/upstream-rebase/ws/sources/ALVR-20.13.0/alvr/server_openvr/cpp/platform/win32/FrameDownsample.hlsl.inc'
DOMAINS = {'codec': 'D-U', 'preprocess': 'U-T', 'total': 'D-T'}
MODEL = {
    'version': 1, 'display_model': 'uniform-bilinear',
    'coordinates': 'pixel centres; phase in display pixels; equal full-eye FOV; eyes sampled separately',
    'client': 'centred C420jpeg bilinear chroma reconstruction, full-range BT.709 inverse, RGB clamp; identity-size float swapchain, then bilinear compositor',
    'truth': 'exact box footprint integration of the stored master, in the selected transfer domain',
    'colour': 'master RGB8 sRGB; display float RGB / full-range BT.709 Y-prime Cb Cr 4:4:4, 0..255 code units',
    'server_filter': 'Catmull-Rom radius 2 or Lanczos-3 radius 3; scale=clamp(source/target,1,3); normalized separable weights; per-eye clamp',
    'bandlimit': 'optional separable normalized Lanczos-windowed sinc, radius ceil(3/(2*cutoff)); cutoff cycles/master texel',
    'metric_units': '32x32 display-pixel chroma/detail blocks; LF Gaussian sigma 8/24 display pixels, radius 3*sigma; SSIM radius 5',
    'temporal': 'signed display residuals and display-filtered LF/detail fields first; previous fields/validity warped to current content separately for panel/backdrop; consecutive frames only',
    'regions': 'centre normalized radius <=.4; transition .4.. .75; periphery >.75 (elliptic eye coordinates)',
    'limits': ['uniform rays, no optical lens calibration/timewarp/FFR/upscaling/sharpening',
               'float CPU taps instead of hardware paired bilinear fetches; no GPU rounding parity claim',
               'explicit sRGB or linear filtering, not inferred SRV/encodingGamma/correctionType',
               'area and bandlimit are experimental CPU controls, not existing server modes',
               'swapchain quantization and device-specific colour transforms are not modelled',
               'master convergence and transfer/phase robustness must be checked before promotion; no live VR rate claim'],
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def array_hash(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


@lru_cache(maxsize=128)
def axis_weights(source, target, kernel, phase=0.):
    """Same texel-centre weights as FrameDownsample.hlsl.inc (unpaired taps)."""
    centre = (np.arange(target, dtype=np.float64)+.5+phase)*source/target
    if kernel == 'bilinear':
        first = np.floor(centre-.5).astype(int)
        indices = first[:, None]+np.arange(2)
        weights = np.maximum(0, 1-np.abs(indices+.5-centre[:, None]))
    elif kernel == 'area':
        width = source/target
        left, right = centre-width/2, centre+width/2
        first = np.floor(left).astype(int)
        indices = first[:, None]+np.arange(int(np.ceil(width))+1)
        weights = np.maximum(0, np.minimum(indices+1, right[:, None])-np.maximum(indices, left[:, None]))
    elif kernel in ('adaptive', 'lanczos'):
        scale = min(3., max(1., source/target))
        radius, max_pairs = (2, 7) if kernel == 'adaptive' else (3, 10)
        first = np.floor(centre-.5-radius*scale).astype(int)
        last = np.floor(centre-.5+radius*scale).astype(int)
        pairs = np.minimum((last-first+2)//2, max_pairs)
        taps = np.arange(int(pairs.max())*2)
        indices = first[:, None]+taps
        x = np.abs((indices+.5-centre[:, None])/scale)
        if kernel == 'adaptive':
            weights = np.where(x < 1, (1.5*x-2.5)*x*x+1,
                               np.where(x < 2, ((-.5*x+2.5)*x-4)*x+2, 0))
        else:
            weights = np.where(x < 3, np.sinc(x)*np.sinc(x/3), 0)
        weights *= taps < 2*pairs[:, None]
    else:
        raise ValueError('unknown resampling kernel')
    weights /= weights.sum(axis=1, keepdims=True)
    return np.clip(indices, 0, source-1), weights.astype(np.float32)


def resize(image, size, kernel='bilinear', phase=(0., 0.)):
    """Separable resampling; call per eye, never on a side-by-side image."""
    out = np.asarray(image, np.float32)
    for axis in (1, 0):
        target = size[1-axis]
        indices, weights = axis_weights(out.shape[axis], target, kernel, float(phase[1-axis]))
        shape = list(out.shape); shape[axis] = target
        result = np.zeros(shape, np.float32)
        broadcast = [1]*out.ndim; broadcast[axis] = target
        for tap in range(indices.shape[1]):
            result += np.take(out, indices[:, tap], axis=axis)*weights[:, tap].reshape(broadcast)
        out = result
    return out


def in_transfer(rgb, transfer):
    return srgb_decode(np.asarray(rgb, np.float32)) if transfer == 'linear' else np.asarray(rgb, np.float32)/255


def from_transfer(value, transfer):
    value = np.clip(value, 0, 1)
    return srgb_encode(value) if transfer == 'linear' else value*255


def preprocess(rgb, size, kernel='adaptive', cutoff=None, transfer='linear'):
    value = in_transfer(rgb, transfer)
    if cutoff:
        kernels = []
        for c in cutoff:
            if not np.isfinite(c) or not 0 < c <= .5:
                raise ValueError('band-limit cutoff must be in (0,.5] cycles/master texel')
            x = np.arange(-int(np.ceil(3/(2*c))), int(np.ceil(3/(2*c)))+1)
            weights = 2*c*np.sinc(2*c*x)*np.sinc(2*c*x/3)
            weights[np.abs(2*c*x) >= 3] = 0
            kernels.append((weights/weights.sum()).astype(np.float32))
        value = cv2.sepFilter2D(value, -1, *kernels, borderType=cv2.BORDER_REPLICATE)
    return from_transfer(resize(value, size, kernel), transfer)


def display_truth(rgb, size, phase=(0., 0.), transfer='linear'):
    return from_transfer(resize(in_transfer(rgb, transfer), size, 'area', phase), transfer)


def present(planes, size, phase=(0., 0.), transfer='linear'):
    # Keep reconstruction into the swapchain separate from compositor sampling.
    swapchain = np.clip(planes_to_rgb(planes), 0, 255)
    return from_transfer(resize(in_transfer(swapchain, transfer), size, 'bilinear', phase), transfer)


def display_planes(rgb):
    """Deliberately no rgb_planes(): that helper subsamples chroma."""
    rgb = np.asarray(rgb, np.float32)
    y = rgb @ np.array([.2126, .7152, .0722], np.float32)
    return np.stack((y, 128+(rgb[..., 2]-y)/1.8556, 128+(rgb[..., 0]-y)/1.5748), -1)


def filter_record(source, target, kernel):
    axes = []
    for s, t in zip(source, target):
        indices, weights = axis_weights(s, t, kernel)
        axes.append({'source': s, 'target': t, 'indices_sha256': array_hash(indices.astype('<i4')),
                     'coefficients_sha256': array_hash(weights.astype('<f4'))})
    return {'kernel': kernel, 'axes': axes, 'equations': MODEL['server_filter']}


def model_record(config):
    record = {**MODEL, **config, 'implementation_sha256': sha256(__file__),
              'metric_helpers_sha256': sha256(Path(__file__).with_name('bench_score.py')),
              'detail_helpers_sha256': sha256(Path(__file__).with_name('bench_detail.py')),
              'server_shader_sha256': sha256(SHADER) if SHADER.is_file() else None,
              'numpy': np.__version__, 'opencv': cv2.__version__}
    return {**record, 'sha256': digest(record)}


def generate_master(scene, directory, count, start=0, fps=90):
    directory = Path(directory); directory.mkdir()
    manifest = {'scene': scene.metadata(), 'size': list(scene.size), 'fps': fps, 'frames': []}
    for index in range(start, start+count):
        row = {'index': index, 'timestamp_ns': round(index*1e9/fps), 'geometry': scene.frame_geometry(index), 'eyes': {}}
        for eye in ('left', 'right'):
            path = directory/f'{index:06d}-{eye}.npy'
            np.save(path, scene.render_frame(index, eye), allow_pickle=False)
            row['eyes'][eye] = {'file': path.name, 'sha256': sha256(path)}
        manifest['frames'].append(row)
    manifest['sha256'] = digest(manifest)
    write_json(directory/'master.json', manifest)
    return manifest


def read_master(directory, row, eye):
    path = Path(directory)/row['eyes'][eye]['file']
    if sha256(path) != row['eyes'][eye]['sha256']:
        raise ValueError('master frame hash mismatch')
    return np.load(path, allow_pickle=False)


def check_convergence(scene, directory, master, larger_size, config):
    from copy import copy
    # Freeze all content rasters, assets, FOVs and anchors; only the raster changes.
    larger = copy(scene)
    larger.size = tuple(larger_size)
    rows = []
    for n in sorted({0, len(master['frames'])//2, len(master['frames'])-1}):
        row = master['frames'][n]
        phase = config['phases'][n % len(config['phases'])]
        for eye in ('left', 'right'):
            a = display_truth(read_master(directory, row, eye), config['display_size'], phase, config['transfer'])
            higher = larger.render_frame(row['index'], eye)
            b = display_truth(higher, config['display_size'], phase, config['transfer'])
            mse = np.mean((display_planes(b)-display_planes(a))**2, axis=(0, 1))
            rows.append({'index': row['index'], 'eye': eye, 'higher_rgb_sha256': array_hash(higher),
                         'mse_y_cb_cr': mse.tolist(), 'psnr_y_cb_cr': [psnr(float(v)) for v in mse]})
    return {'master_size': master['size'], 'larger_size': list(larger_size), 'samples': rows,
            'interpretation': 'reference sensitivity diagnostic; no automatic convergence claim'}


def candidate_frames(directory, master, size, kernel, cutoff=None, transfer='linear'):
    for row in master['frames']:
        eyes = [rgb_planes(preprocess(read_master(directory, row, eye), size, kernel, cutoff, transfer), quantize=True)
                for eye in ('left', 'right')]
        yield tuple(np.concatenate((a, b), axis=1) for a, b in zip(*eyes))


def common_support(render_size, encode_sizes, display_size, phase):
    """Intersection of unclamped centres/footprints, identical for every candidate."""
    axes = []
    for axis, d in enumerate(display_size):
        q = np.arange(d)+.5+phase[axis]
        # T's full box footprint plus candidate bilinear footprint must fit.
        valid = (q >= .5) & (q <= d-.5)
        for size in [render_size, *encode_sizes]:
            p = q*size[axis]/d-.5
            valid &= (p >= 0) & (p <= size[axis]-1)
        axes.append(valid)
    return axes[1][:, None] & axes[0][None, :]


def content_geometry(scene, index, eye, size, phase):
    transform = np.array([[1., 0, -phase[0]], [0, 1., -phase[1]], [0, 0, 1.]]) @ resize_homography(scene.size, size)
    h = {'panel': transform @ scene.homography(index, eye)}
    visible = {'panel': plane_mask(scene.panel_labels.shape, h['panel'], size)}
    if scene.backdrop:
        h['backdrop'] = transform @ scene.homography(index, eye, 'backdrop')
        visible['backdrop'] = plane_mask(scene.backdrop.image.shape[:2], h['backdrop'], size) & ~visible['panel']
    visible['surround'] = ~np.logical_or.reduce(list(visible.values()))
    h['surround'] = np.eye(3)
    return h, visible


def truth_masks(rgb):
    masks = natural_masks(rgb)
    y = display_planes(rgb)[..., 0]
    smooth = cv2.GaussianBlur(y, (0, 0), 2)
    masks['dark'] = masks['mura']
    masks['mura'] = np.hypot(cv2.Sobel(smooth, cv2.CV_32F, 1, 0), cv2.Sobel(smooth, cv2.CV_32F, 0, 1)) < 4
    yy, xx = np.indices(y.shape, np.float32)
    radius = np.hypot((xx+.5)*2/y.shape[1]-1, (yy+.5)*2/y.shape[0]-1)
    masks.update(all=np.ones(y.shape, bool), centre=radius <= .4,
                 transition=(radius > .4) & (radius <= .75), periphery=radius > .75)
    return masks


def warp_previous(field, previous, current, size, radius=1):
    """Warp each physical plane separately; exclude occlusion/interpolation halos."""
    out = np.zeros_like(field)
    valid = np.zeros(field.shape[:2], bool)
    for plane, h in current['homographies'].items():
        transform = h @ np.linalg.inv(previous['homographies'][plane])
        mask = erode(previous['valid'] & previous['visible'][plane], radius)
        support = cv2.warpPerspective(mask.astype(np.float32), transform, size) > .999
        support &= erode(current['valid'] & current['visible'][plane], radius)
        warped = cv2.warpPerspective(field, transform, size)
        out[support] = warped[support]
        valid |= support
    return out, valid


class DisplayScore:
    def __init__(self):
        self.samples, self.previous = [], {}

    def add(self, reference, output, target, masks, geometry, index, eye, phase):
        if reference.shape != output.shape or reference.shape != target.shape:
            raise ValueError('display truth/output geometry mismatch')
        reference, output = map(display_planes, (reference, output))
        residual = output-reference
        size = residual.shape[1::-1]
        previous = self.previous.get(eye)
        consecutive = previous is not None and index == previous['index']+1
        diff, temporal_valid = residual, np.zeros(residual.shape[:2], bool)
        if consecutive:
            aligned, temporal_valid = warp_previous(previous['residual'], previous, geometry, size)
            diff = residual-aligned
        # Avoid cancellation of tiny variances in constant 32-bit float images.
        ssim = ssim_map(reference[..., 0].astype(np.float64), output[..., 0].astype(np.float64))
        # LP fields are always formed on the display grid BEFORE correspondence.
        lp = {s: cv2.GaussianBlur(residual, (6*s+1, 6*s+1), s) for s in (8, 24)}
        lp_diff = {}
        if consecutive:
            for s in lp:
                prior_lp = cv2.GaussianBlur(previous['residual'], (6*s+1, 6*s+1), s)
                aligned, safe = warp_previous(prior_lp, previous, geometry, size, 3*s+1)
                lp_diff[s] = (lp[s]-aligned, safe)
        # Detail is relative to each residual domain's reference; masks stay T-derived.
        ref_energy, out_energy = bench_detail.energy(reference[..., 0]), bench_detail.energy(output[..., 0])
        def bands(y):
            low = cv2.GaussianBlur(y, (5, 5), .8)
            return y-low, low-cv2.GaussianBlur(low, (9, 9), 1.6)
        a, b = bands(reference[..., 0]), bands(output[..., 0])
        correlation = a[0]*b[0]+a[1]*b[1]
        detail_valid = erode(geometry['valid'], 6)
        detail_prior = None
        if consecutive:
            a, av = warp_previous(previous['ref_energy'], previous, geometry, size, 7)
            b, bv = warp_previous(previous['out_energy'], previous, geometry, size, 7)
            detail_prior = a, b, av & bv
        metrics = {}
        for name, region in masks.items():
            valid = geometry['valid'] & region
            row = {'pixels': int(valid.sum()), 'coverage': float(valid.mean())}
            for channel, n in (('y', 0), ('cb', 1), ('cr', 2)):
                mse = float(np.mean(residual[..., n][valid]**2)) if valid.any() else None
                row.update({f'mse_{channel}': mse, f'psnr_{channel}_db': psnr(mse), f'psnr_{channel}_infinite': mse == 0})
            safe = erode(valid, 5)
            row['ssim_y'] = float(ssim[safe].mean()) if safe.any() else None
            row.update(block_metrics(diff[..., 1], diff[..., 2], valid & temporal_valid, block=32))
            add_stats(row, 'flicker', diff[..., 0], valid & temporal_valid)
            for sigma, field in lp.items():
                safe = erode(geometry['valid'], 3*sigma) & region
                for channel, n in (('y', 0), ('cb', 1), ('cr', 2)):
                    add_stats(row, f'lf{sigma}_{channel}', field[..., n], safe)
                    delta, allowed = lp_diff.get(sigma, (field, np.zeros_like(safe)))
                    add_stats(row, f'lf{sigma}_{channel}_temporal', delta[..., n], safe & allowed)
            detail = bench_detail.retention(ref_energy, out_energy, region, detail_valid)
            corr = bench_detail.retention(ref_energy, correlation, region, detail_valid)
            row['detail_retained_mean'] = float(np.mean(detail['retained'])) if detail['retained'] else None
            row['detail_correlated_mean'] = float(np.mean(corr['retained'])) if corr['retained'] else None
            row['detail_temporal_rms'] = None
            if detail_prior:
                a, b, safe = detail_prior
                prior = bench_detail.retention(a, b, region, safe)
                paired = set(detail['ids']) & set(prior['ids'])
                c, p = dict(zip(detail['ids'], detail['retained'])), dict(zip(prior['ids'], prior['retained']))
                if paired:
                    row['detail_temporal_rms'] = float(np.sqrt(np.mean([(c[k]-p[k])**2 for k in paired])))
            metrics[name] = row
        self.samples.append({'index': index, 'eye': eye, 'phase': list(phase), 'metrics': metrics,
                             'support_sha256': array_hash(geometry['valid']),
                             'masks_sha256': digest({k: array_hash(v) for k, v in masks.items()})})
        self.previous[eye] = {**geometry, 'residual': residual, 'index': index,
                              'ref_energy': ref_energy, 'out_energy': out_energy}

    def finish(self):
        aggregate = {}
        for region in self.samples[0]['metrics'] if self.samples else []:
            aggregate[region] = {}
            for metric in self.samples[0]['metrics'][region]:
                values = clustered(self.samples, region, metric)
                aggregate[region][metric] = {'mean': float(np.mean(list(values.values()))) if values else None, 'frames': len(values)}
            for channel in ('y', 'cb', 'cr'):
                mse = aggregate[region][f'mse_{channel}']['mean']
                aggregate[region][f'psnr_{channel}_db']['mean'] = psnr(mse)
                aggregate[region][f'psnr_{channel}_infinite']['mean'] = mse == 0
        return {'samples': self.samples, 'aggregate': aggregate}


def clustered(samples, region, metric):
    frames = {}
    for sample in samples:
        value = sample['metrics'][region].get(metric)
        if value is not None:
            frames.setdefault(sample['index'], []).append(value)
    return {k: float(np.mean(v)) for k, v in frames.items()}


def validate_y4m(path, size, fps):
    with Path(path).open('rb') as stream:
        tokens = stream.readline(4096).decode('ascii').split()
    fields = {t[0]: t[1:] for t in tokens[1:] if not t.startswith('X')}
    if (fields.get('W'), fields.get('H'), fields.get('F'), fields.get('I'), fields.get('C')) not in [
            (str(2*size[0]), str(size[1]), f'{fps}:1', 'p', c) for c in ('420', '420jpeg')]:
        raise ValueError('frame geometry, clock, interlace or chroma siting mismatch')


def serialized_bytes(path, frames, cap):
    """Standalone rebase encode.cpp: 40-byte header, then u32 length + packet/frame."""
    total = Path(path).stat().st_size
    result = {'actual_container_bytes': total, 'actual_per_frame_bytes': None,
              'packet_cap_exceedances': None, 'format': 'unrecognized; container bytes only'}
    with Path(path).open('rb') as stream:
        if stream.read(8) != b'PYROWAVE':
            return result
        if len(stream.read(32)) != 32:
            raise ValueError('truncated PyroWave container header')
        sizes = []
        while stream.tell() < total:
            raw = stream.read(4)
            if len(raw) != 4:
                raise ValueError('truncated PyroWave frame length')
            length, = struct.unpack('<I', raw)
            if not length or stream.tell()+length > total:
                raise ValueError('truncated/empty PyroWave frame packet')
            sizes.append(length)
            stream.seek(length, 1)
        if len(sizes) != frames:
            raise ValueError('PyroWave packet frame count differs from source')
    return {**result, 'actual_per_frame_bytes': sizes, 'packet_cap_exceedances': sum(n > cap for n in sizes),
            'mean_packet_cap_utilization': sum(sizes)/(frames*cap), 'container_framing_bytes': 40+4*frames,
            'format': 'PYROWAVE little-endian CLI container; bytes are serialized packets, excluding file framing'}


def score_display(decoded, source, scene, directory, master, config, treatment):
    size, display_size = treatment['encode_size'], config['display_size']
    for path in (source, decoded):
        validate_y4m(path, size, master['fps'])
    inputs, outputs = iter_y4m(source), iter_y4m(decoded)
    scores = {name: DisplayScore() for name in DOMAINS}
    provenance = []
    try:
        for n, row in enumerate(master['frames']):
            src, dec = next(inputs, None), next(outputs, None)
            if src is None or dec is None:
                raise ValueError('mismatched frame count: fewer frames than master')
            phase = config['phases'][n % len(config['phases'])]
            valid = common_support(master['size'], config['encode_sizes'], display_size, phase)
            for eye in ('left', 'right'):
                rgb = read_master(directory, row, eye)
                target = display_truth(rgb, display_size, phase, config['transfer'])
                u = present(crop_eye(src, eye), display_size, phase, config['transfer'])
                d = present(crop_eye(dec, eye), display_size, phase, config['transfer'])
                masks = truth_masks(target)
                homographies, visible = content_geometry(scene, row['index'], eye, display_size, phase)
                labels = cv2.warpPerspective(scene.panel_labels, homographies['panel'], tuple(display_size), flags=cv2.INTER_NEAREST)
                masks['natural'] &= ((labels == 4) & visible['panel']) | visible.get('backdrop', False)
                geometry = {'valid': valid, 'homographies': homographies, 'visible': visible}
                for name, a, b in (('codec', u, d), ('preprocess', target, u), ('total', target, d)):
                    scores[name].add(a, b, target, masks, geometry, row['index'], eye, phase)
                provenance.append({'index': row['index'], 'eye': eye, 'timestamp_ns': row['timestamp_ns'],
                                   'master_sha256': row['eyes'][eye]['sha256'], 'target_sha256': array_hash(target),
                                   'source_sha256': digest([array_hash(p) for p in crop_eye(src, eye)]),
                                   'decoded_sha256': digest([array_hash(p) for p in crop_eye(dec, eye)])})
        if next(inputs, None) is not None or next(outputs, None) is not None:
            raise ValueError('mismatched frame count: more frames than master')
    finally:
        inputs.close(); outputs.close()
    # Encode sizes define a common support intersection, not a treatment identity.
    model = model_record({k: v for k, v in config.items() if k != 'encode_sizes'})
    identity = {'master_sha256': master['sha256'], 'model_sha256': model['sha256']}
    return {'schema': 1, 'stage': 'offline-display', 'comparison_identity': identity, 'model': model,
            'treatment': treatment, 'frame_provenance': provenance, 'domains': {k: s.finish() for k, s in scores.items()},
            'frame_identity_limit': 'ordinal Y4M frame correspondence; CLI carries no authenticated frame IDs; count/clock/geometry checked, payloads hashed',
            'observation_count': len(master['frames']), 'live_acceptance': 'unverified'}


def compare_display(reports, names, repetitions=500):
    """Paired moving-block bootstrap, both eyes clustered by original frame."""
    if not reports or len(reports) != len(names):
        raise ValueError('reports/names required')
    identity = reports[0]['comparison_identity']
    if any(r['comparison_identity'] != identity for r in reports):
        raise ValueError('incompatible master/display-model identity')
    result = {'baseline': names[0], 'comparisons': [], 'method': 'paired frame clusters (both eyes), circular moving-block bootstrap; 95% CI; no automatic promotion'}
    bootstrap = {}
    for report, name in zip(reports[1:], names[1:]):
        domains = {}
        for domain in DOMAINS:
            baseline = reports[0]['domains'][domain]['samples']
            candidate = report['domains'][domain]['samples']
            keys = lambda samples: [(s['index'], s['eye'], s['phase'], s['support_sha256'], s['masks_sha256']) for s in samples]
            if keys(baseline) != keys(candidate):
                raise ValueError('mismatched frames/phases/common support or truth masks')
            all_frames = sorted({s['index'] for s in baseline})
            rows = {}
            for region in reports[0]['domains'][domain]['aggregate']:
                rows[region] = {}
                for metric in reports[0]['domains'][domain]['aggregate'][region]:
                    if metric.startswith('psnr_') or metric in ('pixels', 'coverage') or metric.endswith('_count'):
                        continue
                    a, b = clustered(baseline, region, metric), clustered(candidate, region, metric)
                    common = sorted(a.keys() & b.keys())
                    # Keep holes on the original clock; do not compress disocclusions
                    # into apparently adjacent observations during block resampling.
                    delta = np.array([b[k]-a[k] if k in a and k in b else np.nan for k in all_frames])
                    ci = None
                    if len(common) >= 4:
                        if len(delta) not in bootstrap:
                            rng = np.random.default_rng(20261009)
                            bootstrap[len(delta)] = np.array([bootstrap_indices(len(delta), rng) for _ in range(repetitions)])
                        draws = delta[bootstrap[len(delta)]]
                        counts = np.isfinite(draws).sum(axis=1)
                        means = np.nansum(draws, axis=1)[counts > 0]/counts[counts > 0]
                        ci = np.percentile(means, [2.5, 97.5]).tolist() if means.size else None
                    rows[region][metric] = {'candidate_minus_baseline': float(np.nanmean(delta)) if common else None,
                                            'ci95': ci, 'paired_frames': len(common)}
            domains[domain] = rows
        result['comparisons'].append({'candidate': name, 'domains': domains})
    return result

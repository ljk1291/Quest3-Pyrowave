"""CPU fence-error metrics and exact, density-preserving stereo crop geometry.

These sequence metrics do not measure optical shimmer or frame timing. Index
windows are one-based inclusive. Temporal pairs stay entirely inside each window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from . import framebank as fb

WINDOWS = ((1, 90), (10, 89))


def crop_geometry(source_eye, target_eye, tangents, multipliers=(.8542, .8500)):
    """Centre fixed pixel extents on the tangent rectangle scaled about zero.

    Coordinates are OpenVR left/right/top/bottom with top-down image rows. No
    resampling: chroma-aligned offsets round to nearest even pixel (ties-to-even).
    Fixed target size can differ from scaled span; effective tangents are recorded.
    """
    sw, sh = source_eye
    tw, th = target_eye
    if any(type(v) is not int or v <= 0 or v % 2 for v in (sw, sh, tw, th)):
        raise ValueError('source/target eye sizes must be positive even integers')
    if tw > sw or th > sh or len(tangents) != 2:
        raise ValueError('crop must fit both eyes')
    mx, my = multipliers
    if not all(math.isfinite(v) and 0 < v <= 1 for v in (mx, my)):
        raise ValueError('multipliers must be finite in (0,1]')
    eyes = []
    for name, bounds in zip(('left', 'right'), tangents):
        l, r, t, b = bounds
        if not all(math.isfinite(v) for v in bounds) or not (l < 0 < r and t < 0 < b):
            raise ValueError('tangents must straddle the optical axis')
        scaled = (l * mx, r * mx, t * my, b * my)
        cx = ((scaled[0] + scaled[1]) / 2 - l) * sw / (r-l)
        cy = ((scaled[2] + scaled[3]) / 2 - t) * sh / (b-t)
        ideal = (cx-tw/2, cy-th/2)
        x, y = (int(round(v/2)*2) for v in ideal)
        if x < 0 or y < 0 or x+tw > sw or y+th > sh:
            raise ValueError('fixed crop falls outside eye; no silent clamping')
        effective = (l+x/sw*(r-l), l+(x+tw)/sw*(r-l),
                     t+y/sh*(b-t), t+(y+th)/sh*(b-t))
        eyes.append(dict(eye=name, x=x, y=y, width=tw, height=th,
                         ideal_offset=list(ideal), alignment_error=[x-ideal[0], y-ideal[1]],
                         original_tangents=list(bounds), scaled_tangents=list(scaled),
                         effective_tangents=list(effective),
                         scaled_span_pixels=[sw*mx, sh*my]))
    return dict(source_eye=list(source_eye), target_eye=list(target_eye),
                tangent_multipliers=list(multipliers), eyes=eyes,
                resampling='none; fixed extents centred on scaled tangent rectangle',
                alignment='nearest even; ties-to-even')


def crop_frame(planes, geometry):
    sw, sh = geometry['source_eye']
    if len(planes) != 3:
        raise ValueError('expected three 4:2:0 planes')
    result = []
    for p, factor in zip(planes, (1, 2, 2)):
        if p.dtype != np.uint8 or p.shape != (sh//factor, 2*sw//factor):
            raise ValueError('expected native 8-bit full stereo C420 planes')
        parts = []
        for idx, eye in enumerate(geometry['eyes']):
            x = (idx*sw+eye['x'])//factor
            y, w, h = (eye[k]//factor for k in ('y', 'width', 'height'))
            parts.append(p[y:y+h, x:x+w])
        result.append(np.concatenate(parts, axis=1))
    return result


def map_rectangle(rect, geometry):
    """Map a full-FOV eye-local rectangle; report excluded portions explicitly."""
    eye = geometry['eyes'][('left', 'right').index(rect['eye'])]
    x, y = rect['x']-eye['x'], rect['y']-eye['y']
    w, h = rect['width'], rect['height']
    left, top = max(0, x), max(0, y)
    right, bottom = min(eye['width'], x+w), min(eye['height'], y+h)
    contained = x >= 0 and y >= 0 and x+w <= eye['width'] and y+h <= eye['height']
    return dict(original=dict(rect), fully_contained=contained,
                mapped=dict(eye=rect['eye'], x=x, y=y, width=w, height=h) if contained else None,
                intersection=dict(eye=rect['eye'], x=left, y=top,
                                  width=max(0, right-left), height=max(0, bottom-top)),
                retained_area_fraction=max(0, right-left)*max(0, bottom-top)/(w*h))


def edge_mask(reference, region_mask=None):
    """Per-frame top-5% Sobel magnitude on valid interior; retain positive ties.

    Excluding the outer pixel avoids crop-border padding edges. Squared magnitude
    gives the same ordering as magnitude. Ties at the 95th percentile are included
    and the actual selected count is reported. Flat regions have no edge mask.
    """
    if reference.dtype != np.uint8 or reference.ndim != 2 or min(reference.shape) < 3:
        raise ValueError('reference must be a uint8 luma region at least 3x3')
    r = reference.astype(np.int32)
    gx = (r[:-2, 2:]+2*r[1:-1, 2:]+r[2:, 2:]
          -r[:-2, :-2]-2*r[1:-1, :-2]-r[2:, :-2])
    gy = (r[2:, :-2]+2*r[2:, 1:-1]+r[2:, 2:]
          -r[:-2, :-2]-2*r[:-2, 1:-1]-r[:-2, 2:])
    mag = gx*gx+gy*gy
    region = np.ones(reference.shape, dtype=bool) if region_mask is None else region_mask
    if region.dtype != np.bool_ or region.shape != reference.shape:
        raise ValueError('region mask must be boolean and match the luma region')
    eligible = region[1:-1, 1:-1]
    threshold = float(np.percentile(mag[eligible], 95, method='linear')) if eligible.any() else None
    mask = np.zeros(reference.shape, dtype=bool)
    if threshold is not None:
        mask[1:-1, 1:-1] = (mag >= threshold) & (mag > 0) & eligible
    return mask, threshold


def histogram_percentile(histogram, percentile):
    """Exact numpy-style linear percentile from nonnegative integer counts."""
    total = int(histogram.sum())
    if total == 0:
        return None
    rank = (total-1)*percentile/100
    lo, hi = math.floor(rank), math.ceil(rank)
    cumulative = histogram.cumsum()
    a = int(np.searchsorted(cumulative, lo+1))
    b = int(np.searchsorted(cumulative, hi+1))
    return a+(b-a)*(rank-lo)


class FenceAccumulator:
    def __init__(self, windows=WINDOWS, *, region_mask=None):
        self.windows = tuple(windows)
        self.region_mask = region_mask
        self.data = {f'{a}-{b}': dict(edge=np.zeros(256, dtype=np.int64),
                                     temporal=np.zeros(511, dtype=np.int64),
                                     frames=0, pairs=0, masked_frames=0,
                                     mask_counts=[], thresholds=[]) for a, b in self.windows}
        self.previous_error = None
        self.last_frame = 0
        self.shape = None

    def add(self, frame_number, reference, decoded, *, mask_reference=None):
        if frame_number != self.last_frame+1:
            raise ValueError('frames must be consecutive and one-based')
        if decoded.dtype != np.uint8 or decoded.shape != reference.shape:
            raise ValueError('decoded luma must match reference shape/dtype')
        if self.shape is not None and reference.shape != self.shape:
            raise ValueError('region geometry changed')
        if mask_reference is not None and mask_reference.shape != reference.shape:
            raise ValueError('mask-reference geometry mismatch')
        mask, threshold = edge_mask(reference if mask_reference is None else mask_reference, self.region_mask)
        error = decoded.astype(np.int16)-reference.astype(np.int16)
        for a, b in self.windows:
            if a <= frame_number <= b:
                d = self.data[f'{a}-{b}']
                d['frames'] += 1
                d['masked_frames'] += int(mask.any())
                d['mask_counts'].append(int(mask.sum()))
                d['thresholds'].append(threshold)
                d['edge'] += np.bincount(np.abs(error[mask]), minlength=256)
                if frame_number > a:
                    # Same current-reference mask for spatial and temporal error.
                    delta = np.abs((error-self.previous_error)[mask])
                    d['temporal'] += np.bincount(delta, minlength=511)
                    d['pairs'] += 1
        self.previous_error = error
        self.last_frame = frame_number
        self.shape = reference.shape

    def report(self):
        out = {}
        for a, b in self.windows:
            d = self.data[f'{a}-{b}']
            if d['frames'] != b-a+1 or d['pairs'] != b-a:
                raise ValueError('incomplete score window')
            count = int(d['edge'].sum())
            tc = int(d['temporal'].sum())
            mse = float(np.dot(np.arange(256, dtype=float)**2, d['edge'])/count) if count else None
            psnr = (math.inf if mse == 0 else 10*math.log10(255**2/mse)) if count else None
            out[f'{a}-{b}'] = dict(frame_window_one_based=[a, b], frames=d['frames'],
                temporal_current_frames_one_based=[a+1, b], temporal_pairs=d['pairs'],
                edge_pixels=count, temporal_pixels=tc, masked_frames=d['masked_frames'],
                edge_psnr_y_db=psnr, edge_abs_error_p999=histogram_percentile(d['edge'], 99.9),
                shimmer_mean=float(np.dot(np.arange(511), d['temporal'])/tc) if tc else None,
                shimmer_p99=histogram_percentile(d['temporal'], 99),
                mask_pixel_counts=d['mask_counts'], sobel_squared_thresholds=d['thresholds'],
                valid=count > 0 and tc > 0)
        return out


def score_y4m(reference, decoded, rect, guard=None, *, region_mask=None, region_descriptor=None,
               mask_reference=None):
    reference, decoded = Path(reference), Path(decoded)
    if guard:
        guard.status()
    ri, di = fb.inspect_y4m(reference), fb.inspect_y4m(decoded)
    if ri != di or ri.frames != 90 or ri.color_range != 'FULL':
        raise ValueError('scoring requires matching complete full-range 90-frame sequences')
    x, y, w, h = (rect[k] for k in ('x', 'y', 'width', 'height'))
    if any(type(v) is not int for v in (x, y, w, h)) or min(x, y) < 0 or min(w, h) < 3:
        raise ValueError('rectangle must be valid integer eye-local coordinates')
    if x+w > ri.width//2 or y+h > ri.height or rect['eye'] not in ('left', 'right'):
        raise ValueError('rectangle falls outside eye')
    if rect['eye'] == 'right':
        x += ri.width//2
    mask_path = Path(mask_reference) if mask_reference is not None else reference
    mi = fb.inspect_y4m(mask_path)
    if mi != ri:
        raise ValueError('mask-reference sequence format/length mismatch')
    if region_mask is not None and (region_mask.dtype != np.bool_ or region_mask.shape != (h,w)):
        raise ValueError('region mask must match the scored rectangle')
    descriptor = json.loads(json.dumps(region_descriptor, allow_nan=False))
    acc = FenceAccumulator(region_mask=region_mask)
    identity = []
    for (i, ref, rh), (j, dec, dh), (k, mr, mh) in zip(fb.iter_y4m(reference, ri), fb.iter_y4m(decoded, di), fb.iter_y4m(mask_path, mi)):
        if i != j or i != k:
            raise ValueError('frame identity mismatch')
        if guard and i % 10 == 0:
            guard.status()
        acc.add(i+1, ref[0][y:y+h, x:x+w], dec[0][y:y+h, x:x+w], mask_reference=mr[0][y:y+h, x:x+w])
        identity.append(dict(frame=i+1, reference_sha256=rh, decoded_sha256=dh, mask_reference_sha256=mh))
    if guard:
        guard.status()
    return dict(schema=1, kind='fence_sequence_error', rectangle=dict(rect),
                reference_sha256=fb.sha256_file(reference), decoded_sha256=fb.sha256_file(decoded),
                frame_identity=identity, windows=acc.report(), mask_reference_sha256=fb.sha256_file(mask_path),
                region_descriptor=descriptor,
                region_mask=None if region_mask is None else dict(shape=list(region_mask.shape),
                    selected_pixels=int(region_mask.sum()), sha256=hashlib.sha256(region_mask.tobytes(order='C')).hexdigest()),
                mask='per-current-reference-frame Sobel top 5%; positive threshold ties included; valid interior',
                temporal='absolute difference of decoded and reference temporal deltas; current-frame mask',
                optical_shimmer_measured=False)


def score_against_references(sharp_reference, decoded, rect, guard=None, *,
                             matching_blur_reference=None, region_mask=None, region_descriptor=None):
    """Compare sharp/blurred references on the SAME sharp-derived edge mask.

    Using blurred edges to choose a new mask would reward hiding the original
    edges. Both comparisons record reference and mask identities independently.
    """
    kwargs = dict(region_mask=region_mask, region_descriptor=region_descriptor, mask_reference=sharp_reference)
    result = {'sharp_reference': score_y4m(sharp_reference, decoded, rect, guard, **kwargs)}
    if matching_blur_reference is not None:
        result['matching_blur_reference'] = score_y4m(matching_blur_reference, decoded, rect, guard, **kwargs)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--decoded', type=Path, required=True)
    p.add_argument('--rectangle', type=Path, required=True)
    p.add_argument('--window', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(argv)
    guard = fb.WindowGuard(a.window, supervised=True)
    report = score_y4m(a.reference, a.decoded, json.loads(a.rectangle.read_text()), guard)
    a.out.write_text(fb.report_json(report), encoding='utf-8')


if __name__ == '__main__':
    main()

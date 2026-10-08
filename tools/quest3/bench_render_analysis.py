"""Truth-only backdrop detail analysis, no codec, OpenVR, GL or network.

Render a fixed content ROI at native eye sampling. The reference is 4x
supersampled Lanczos-4 followed by an area resolve, at the identical pose.
"""
import argparse
import copy
from pathlib import Path
import sys

import cv2
import numpy as np

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.quest3.bench_scene import BenchScene, filtered_warp, resize_homography, trajectory, write_json, plane_mask
from tools.quest3 import bench_detail
from tools.quest3.bench_registration import project
from tools.quest3.bench_score import erode


def render_region(scene, h, box, mode):
    x, y, w, height = box
    factor = 1.5 if mode == 'default' else 4
    # The default FBO uses globally rounded dimensions: its scale is not
    # necessarily exactly 1.5 for an odd subregion. Preserve global centres.
    large = tuple(round(v*factor) for v in scene.size)
    resize = resize_homography(scene.size, large)
    if factor == 1.5:
        x0, y0 = int(np.floor(x*factor))-2, int(np.floor(y*factor))-2
        x1, y1 = int(np.ceil((x+w)*factor))+2, int(np.ceil((y+height)*factor))+2
        shift = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.]])
        raw = np.rint(filtered_warp(scene.backdrop.mips, shift @ resize @ h, (x1-x0, y1-y0))).astype(np.uint8)
        yy, xx = np.mgrid[y:y+height, x:x+w].astype(np.float32)
        coords = project(np.stack((xx, yy), -1), shift @ resize).astype(np.float32)
        return cv2.remap(raw, coords[..., 0], coords[..., 1], cv2.INTER_LINEAR)
    result = np.empty((height, w, 3), np.uint8)
    for start in range(0, height, 32):
        rows = min(32, height-start)
        shift = np.array([[1, 0, -4*x], [0, 1, -4*(y+start)], [0, 0, 1.]])
        transform = shift @ resize @ h
        if mode == 'reference':
            yy, xx = np.mgrid[:rows*4, :w*4].astype(np.float32)
            uv = project(np.stack((xx, yy), -1), np.linalg.inv(transform)).astype(np.float32)
            raw = cv2.remap(scene.backdrop.image, uv[..., 0], uv[..., 1], cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
            result[start:start+rows] = cv2.resize(raw, (w, rows), interpolation=cv2.INTER_AREA)
        else:
            raw = np.rint(np.clip(filtered_warp(scene.backdrop.mips, transform, (w*4, rows*4),
                            interpolation=cv2.INTER_CUBIC if mode == 'cubic4' else cv2.INTER_LINEAR), 0, 255)).astype(np.uint8)
            raw = cv2.resize(raw, (w*2, rows*2), interpolation=cv2.INTER_LINEAR)
            result[start:start+rows] = cv2.resize(raw, (w, rows), interpolation=cv2.INTER_LINEAR)
    return result


def analyze(scene, indices, roi, eye='left'):
    x, y, w, h = roi
    offset = np.array([[1, 0, x], [0, 1, y], [0, 0, 1.]])
    samples = {mode: [] for mode in ('default', 'ss4', 'cubic4')}
    per_frame = []
    for index in indices:
        mapping = scene.homography(index, eye, 'backdrop')
        corners = project(np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]]), mapping)
        lo = np.maximum(0, np.floor(corners.min(axis=0))-8).astype(int)
        hi = np.minimum(scene.size, np.ceil(corners.max(axis=0))+8).astype(int)
        width, height = hi-lo
        if min(width, height) <= 0:
            continue
        box = [*lo, int(width), int(height)]
        shift = np.array([[1, 0, -lo[0]], [0, 1, -lo[1]], [0, 0, 1.]])
        content_h = shift @ mapping @ offset
        visible = plane_mask(scene.backdrop.image.shape[:2], shift @ mapping, (width, height))
        foreground = plane_mask(scene.panel_labels.shape, shift @ scene.homography(index, eye), (width, height))
        visible &= ~cv2.dilate(foreground.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        valid = cv2.warpPerspective(visible.astype(np.float32), content_h, (w, h), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR) > .999
        valid = erode(valid, 8)
        images = {}
        for mode in ('reference', *samples):
            image = render_region(scene, mapping, box, mode).astype(np.float32)
            luma = image @ np.array([.2126, .7152, .0722], np.float32)
            images[mode] = cv2.warpPerspective(luma, content_h, (w, h), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR)
        truth = bench_detail.energy(images['reference'])
        row = {'index': int(index), 'visible_texels': int(valid.sum())}
        for mode in samples:
            detail = bench_detail.retention(truth, bench_detail.energy(images[mode]), np.ones((h, w), bool), valid)
            samples[mode].append({**detail, 'eye': eye, 'sample_id': str(index)})
            row[mode] = {'retained_mean': float(np.mean(detail['retained'])) if detail['retained'] else None,
                         'blocks': len(detail['ids']),
                         'luma_rmse_codes': float(np.sqrt(np.mean((images[mode][valid]-images['reference'][valid])**2))) if valid.any() else None}
        per_frame.append(row)
        print(f'[BENCH_RENDER_ANALYSIS] frame={index} blocks={row["default"]["blocks"]}', flush=True)
    return {'roi_content_texels': list(roi), 'eye': eye, 'frames': per_frame,
            'aggregate': {mode: bench_detail.temporal(values) for mode, values in samples.items()},
            'detail_samples': samples,
            'reference': '4x native eye supersample; Lanczos4 texture resample; area resolve, RGB8; identical pose; fixed content pullback',
            'limits': 'CPU filter model, not measured GL output; finite ROI, native eye pixel density; no codec or compositor; ratios >1 include excess alias/noise energy'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--motions', nargs='+', choices=('recorded', 'none', 'tremor', 'jitter', 'pan', 'turn'), default=['recorded'])
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--frames', type=int, default=24)
    parser.add_argument('--step', type=int, default=1)
    parser.add_argument('--indices', type=int, nargs='+', help='explicit recorded frame IDs (e.g. decoded capture barcodes)')
    parser.add_argument('--roi', type=int, nargs=4, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
    parser.add_argument('--eye', choices=('left', 'right'), default='left')
    args = parser.parse_args(argv)
    if args.frames < 2 or args.step < 1 or args.start < 0:
        parser.error('at least two frames, positive step and nonnegative start required')
    if args.indices and (args.motions != ['recorded'] or len(set(args.indices)) < 2 or args.indices != sorted(set(args.indices)) or min(args.indices) < 0):
        parser.error('--indices requires recorded mode and distinct increasing nonnegative frame IDs')
    scene = BenchScene.from_metadata(args.scene)
    if scene.backdrop is None:
        parser.error('scene has no backdrop')
    bx, by, bw, bh = scene.backdrop.central_box
    roi = args.roi or [32*((bx+bw//2-512)//32), 32*((by+64)//32), 1024, 768]
    x, y, w, h = roi
    if min(x, y) < 0 or min(w, h) < 32 or any(v % 32 for v in roi) or x+w > scene.backdrop.size[0] or y+h > scene.backdrop.size[1]:
        parser.error('ROI must be inside backdrop with 32-aligned origin and dimensions')
    args.out.mkdir(parents=True, exist_ok=True)
    for motion in args.motions:
        current = copy.copy(scene)
        if motion != 'recorded':
            current.live = False
            current.frame_records = {}
            current.trajectory = trajectory(scene.seed, motion, scene.scale)
            # Synthetic offsets around the original yaw anchor, at eye height.
            real = scene.anchor.copy()
            real[:3, 3] += 1.5*scene.anchor[:3, 2]
            for i in range(args.start, args.start+args.frames*args.step, args.step):
                current.frame_records[i] = current.frame_geometry(i, real)
        indices = args.indices or list(range(args.start, args.start+args.frames*args.step, args.step))
        if motion == 'recorded' and any(i not in current.frame_records for i in indices):
            parser.error('requested recorded pose frames are missing')
        result = analyze(current, indices, roi, args.eye)
        result.update(motion=motion, source_scene=str(args.scene), native_eye_size=list(scene.size),
                      step=None if args.indices else args.step, indices=indices)
        write_json(args.out/f'{motion}.json', result)
        print(motion, result['aggregate'], flush=True)


if __name__ == '__main__':
    main()

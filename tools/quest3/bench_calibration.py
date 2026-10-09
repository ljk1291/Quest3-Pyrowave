"""Build an independent full-eye colour manifest from Quest compositor bursts.

Geometry comes only from margin markers/spots. Spatial holdouts and thresholds
are the v5 registration's; failed shots never contribute colour observations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from tools.quest3 import bench_colour as colour, bench_registration as reg
from tools.quest3.bench_lens_score import capture_visibility, read_capture
from tools.quest3.bench_scene import CalibrationScene, CALIBRATION_LAYOUT, write_json


def detect_spots(capture, scene, initial):
    """Intensity centroids of isolated symmetric margin spots, never patches.

    ArUco provides identity/search windows only. Spot targets are measured
    independently of the warp prediction, then split BEFORE the final fit.
    """
    gray = capture.astype(np.float32).mean(axis=2)
    sources, targets = [], []
    points = np.asarray(scene.landmarks, float)
    predicted = initial.forward(points)
    dx = initial.forward(points+[scene.spot_sigma, 0])-predicted
    dy = initial.forward(points+[0, scene.spot_sigma])-predicted
    for source, centre, ax, ay in zip(points, predicted, dx, dy):
        radius = int(np.ceil(4*max(np.linalg.norm(ax), np.linalg.norm(ay))))+2
        if not 3 <= radius <= 40:
            continue
        x, y = np.rint(centre).astype(int)
        x0, y0, x1, y1 = x-radius, y-radius, x+radius+1, y+radius+1
        if x0 < 0 or y0 < 0 or x1 > gray.shape[1] or y1 > gray.shape[0]:
            continue
        patch = gray[y0:y1, x0:x1]
        border = np.r_[patch[0], patch[-1], patch[:, 0], patch[:, -1]]
        background = np.median(border)
        weights = np.maximum(patch-background, 0)
        if weights.max() < 35 or np.max(np.abs(border-background)) > 4:
            continue  # truncated/occluded spot, or another object in its window
        yy, xx = np.mgrid[y0:y1, x0:x1]
        target = np.array([(weights*xx).sum(), (weights*yy).sum()])/weights.sum()
        if np.linalg.norm(target-centre) > radius/3:
            continue
        sources.append(source); targets.append(target)
    if len(sources) < 12:
        raise ValueError('insufficient independent margin spots')
    return np.array(sources), np.array(targets)


def patch_polygons(scene, mapping):
    # The contract's pixel EDGE coordinates become registration's integer
    # pixel CENTRE coordinates here. Preserve TL,TR,BR,BL and all 300 slots.
    boxes = np.array([p['box'] for p in scene.calibration])
    lo, hi = boxes[:, :2]-.5, boxes[:, :2]+boxes[:, 2:]-.5
    points = np.stack((lo, np.c_[hi[:, 0], lo[:, 1]], hi, np.c_[lo[:, 0], hi[:, 1]]), axis=1)
    return mapping.forward(points)


def sample_patch(capture, polygon, visible):
    """Match bench_colour's middle-half median; explicitly reject hidden patches."""
    polygon = np.asarray(polygon, np.float32)
    if not np.isfinite(polygon).all() or np.any(polygon < 0) or np.any(polygon >= capture.shape[1::-1]):
        return None, 'patch outside capture'
    polygon = polygon.mean(axis=0)+(polygon-polygon.mean(axis=0))*.5
    mask = np.zeros(capture.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.rint(polygon).astype(np.int32), 1)
    use = mask != 0
    if use.sum() < 16:
        return None, 'patch has fewer than 16 sample pixels'
    if not visible[use].all():
        return None, 'patch hidden or missing'
    observed = np.median(capture[use], axis=0)
    if np.any(observed < 3) or np.any(observed > 252):
        return None, 'patch clipped in colour'
    return observed, None


def fit_report(observations):
    model, validation = colour.fit(observations)
    error = colour.apply([p['rgb'] for p in observations], model, [p['uv'] for p in observations]) - np.array([p['observed'] for p in observations])
    split = np.array([(p['cell'][0]+2*p['cell'][1]) % 5 for p in observations])
    for name, mask in (('training', split >= 2), ('selection', split == 1), ('held_out', split == 0)):
        validation[name] = {'rmse_codes': float(np.sqrt(np.mean(error[mask]**2))),
                            'p95_codes': float(np.percentile(np.abs(error[mask]), 95)),
                            'patches': int(mask.sum())}
    return {'model': model, **validation}


def build(scene_directory, directory, out):
    scene = CalibrationScene.from_metadata(scene_directory)
    directory, out = Path(directory), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    burst = directory/'burst.json'
    shots = (json.loads(burst.read_text(encoding='utf-8-sig'))['shots'] if burst.exists()
             else [{'file': p.name} for p in sorted(directory.glob('*.png'))])
    manifest = {'schema': 1, 'layout': CALIBRATION_LAYOUT, 'size': list(scene.size),
                'layout_sha256': scene.layout_hash, 'eyes': {'left': [], 'right': []}}
    report = {'schema': 1, 'layout_sha256': scene.layout_hash, 'eyes': {}, 'shots': [],
              'registration': 'frozen per-eye lens; per-shot homographies; independent spatial holdouts',
              'manifest': str((out/'calibration.json').resolve())}
    # All 16 source-eye regions need held-out geometry, including the periphery.
    footprint = np.ones(scene.size[::-1], bool)
    for side in manifest['eyes']:
        rows, marker_pairs = [], []
        for shot in shots:
            info = {'file': shot['file'], 'eye': side, 'status': 'excluded'}
            report['shots'].append(info)
            try:
                capture = read_capture(directory, shot, side)
                if capture.shape[:2] != (2208, 2064):
                    raise ValueError('expected a 4128x2208 side-by-side Quest screencap')
                source, target = reg.detect(capture, scene)
                held = reg.spatial_split(source, scene.size)
                if (~held).sum() < 8:
                    raise ValueError('insufficient training ArUco corners')
                source, target = source[~held], target[~held]
                # Reject false decoded IDs before nonlinear lens initialization.
                # The loose gate tolerates barrel distortion; no held-out spot
                # enters this coarse correspondence check or the final fit.
                _, mask = cv2.findHomography(source, target, cv2.RANSAC, 66.)
                if mask is None or mask.sum() < 8:
                    raise ValueError('insufficient consistent training ArUco corners')
                keep = mask.ravel().astype(bool)
                marker_pairs.append((source[keep], target[keep]))
                rows.append((shot, info))
            except (ValueError, OSError, cv2.error) as exc:
                info['reason'] = str(exc)
        observations, ready, training = [], [], []
        try:
            if rows:
                initial_maps, _ = reg.fit_burst(marker_pairs, (2064, 2208))
                for (shot, info), initial in zip(rows, initial_maps):
                    try:
                        capture = read_capture(directory, shot, side)
                        source, target = detect_spots(capture, scene, initial)
                        held = reg.spatial_split(source, scene.size)
                        if (~held).sum() < 12:
                            raise ValueError('insufficient training spots after spatial holdouts')
                        training.append((source[~held], target[~held]))
                        ready.append((shot, info, source[held], target[held]))
                    except (ValueError, cv2.error) as exc:
                        info['reason'] = str(exc)
                # Final lens uses ONLY the training spots. ArUco corner error
                # is not propagated into the strict subpixel qualification.
                if ready:
                    maps, fits = reg.fit_burst(training, (2064, 2208), initial_maps[0].lens.coefficients)
                    for (shot, info, source, target), mapping, fit in zip(ready, maps, fits):
                        try:
                            info.update(lens_coefficients=mapping.lens.coefficients.tolist(),
                                        homography=mapping.homography.tolist(), fit=fit)
                            geometry = reg.validate_plane(mapping, source, target, footprint)
                            info['geometry'] = geometry
                            if not geometry['scores_available']:
                                raise ValueError('spatial-holdout geometry qualification failed (median <=0.1 px, p95 <=0.25 px, >=3 per 4x4 cell)')
                            capture = read_capture(directory, shot, side)
                            index, barcode = reg.barcode_index(capture, mapping, scene, shot)
                            info.update(index=index, **barcode)
                            polygons = patch_polygons(scene, mapping)
                            visible = capture_visibility(capture)
                            excluded, shot_observations = [], []
                            for n, (patch, polygon) in enumerate(zip(scene.calibration, polygons)):
                                observed, reason = sample_patch(capture, polygon, visible)
                                if reason:
                                    excluded.append({'patch_index': n, 'reason': reason})
                                    # Schema 1 requires 300 finite quads. An off-image
                                    # quad is skipped by the v5 loader, without reindexing.
                                    polygons[n] = -10000
                                else:
                                    shot_observations.append({**patch, 'observed': observed.tolist()})
                            name = f'{side}-{len(manifest["eyes"][side]):04d}.png'
                            if not cv2.imwrite(str(out/name), capture[..., ::-1]):
                                raise OSError('could not write single-eye crop')
                            manifest['eyes'][side].append({'file': name, 'source_file': shot['file'], 'index': index,
                                                          'polygons': polygons.tolist(), 'excluded_patches': excluded})
                            observations.extend(shot_observations)
                            info.update(status='accepted', patches_used=300-len(excluded), excluded_patches=excluded)
                        except (ValueError, OSError, cv2.error) as exc:
                            info['reason'] = str(exc)
        except (ValueError, np.linalg.LinAlgError, cv2.error) as exc:
            for _, info in rows:
                if 'reason' not in info:
                    info['reason'] = str(exc)
        try:
            report['eyes'][side] = fit_report(observations)
        except ValueError as exc:
            report['eyes'][side] = {'scores_available': False, 'reason': str(exc)}
    write_json(out/'calibration.json', manifest)
    report['scores_available'] = all(eye['scores_available'] for eye in report['eyes'].values())
    if report['scores_available']:
        _, report['calibration_id'] = colour.load_burst(out)
    write_json(out/'calibration-report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('build')
    command.add_argument('--scene', type=Path, required=True)
    command.add_argument('--input', type=Path, required=True)
    command.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    report = build(args.scene, args.input, args.out)
    for side, fit in report['eyes'].items():
        metrics = '; '.join(f'{name} RMSE={fit[name]["rmse_codes"]:.4f} p95={fit[name]["p95_codes"]:.4f} codes'
                            for name in ('training', 'selection', 'held_out') if name in fit)
        print(f'[Q3PW_BENCH_CALIBRATION] eye={side} available={int(fit["scores_available"])} {metrics or fit.get("reason", "")}')
    print(f'Calibration manifest: {report["manifest"]}')
    print(f'Qualification report: {args.out / "calibration-report.json"}')
    return 0 if report['scores_available'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

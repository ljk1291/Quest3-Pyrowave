"""Independent full-eye colour calibration; frozen across compared bursts."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from tools.quest3 import bench_score as bs


COLOURS = [[v, v, v] for v in (16, 32, 64, 96, 128, 192, 224)] + [
    [160, 64, 64], [64, 160, 64], [64, 64, 160], [160, 128, 48], [48, 128, 160]]


def layout(size):
    """5x5 repeated 4x3 patch arrays; normalized eye pixel-edge coordinates."""
    patches = []
    for row in range(5):
        for col in range(5):
            for n, rgb in enumerate(COLOURS):
                x = col/5+.02+(n % 4+.1)*.04
                y = row/5+.02+(n//4+.1)*(.16/3)
                box = np.array([x, y, .032, .128/3])*np.tile(size, 2)
                patches.append({'cell': [col, row], 'patch': n, 'rgb': rgb,
                                'box': box.tolist(), 'uv': [x+.016, y+.064/3]})
    return patches


def apply(rgb, model, uv):
    values = bs.srgb_decode(rgb)
    r2 = np.sum((2*np.asarray(uv)-1)**2, axis=-1)/2
    radial = np.asarray(model['radial'])
    gain = 1+r2[..., None]*radial[0]+r2[..., None]**2*radial[1]
    return bs.srgb_encode(values*np.asarray(model['gain'])*gain+model['offset']).astype(np.float32)


def fit(observations):
    """Model selection and final validation use different spatial cells."""
    if not observations:
        raise ValueError('full-eye calibration requires repeated colours in all 25 spatial cells')
    rgb = np.asarray([o['rgb'] for o in observations])
    observed = np.asarray([o['observed'] for o in observations])
    uv = np.asarray([o['uv'] for o in observations])
    cells = np.asarray([o['cell'] for o in observations])
    if not all(np.isfinite(a).all() for a in (rgb, observed, uv, cells)) or np.any((uv < 0) | (uv > 1)):
        raise ValueError('invalid full-eye colour observations')
    split = (cells[:, 0]+2*cells[:, 1]) % 5
    train, select, held = split >= 2, split == 1, split == 0
    if len(set(map(tuple, cells))) < 25 or min(train.sum(), select.sum(), held.sum()) < 36:
        raise ValueError('full-eye calibration requires repeated colours in all 25 spatial cells')
    if any(len({tuple(o['rgb']) for o in observations if tuple(o['cell']) == cell}) < 12 for cell in set(map(tuple, cells))):
        raise ValueError('each full-eye calibration cell requires all twelve colours, including dark neutrals')
    x, y = bs.srgb_decode(rgb), bs.srgb_decode(observed)
    r2 = np.sum((2*uv-1)**2, axis=1)/2
    models = []
    for radial in (False, True):
        try:
            gains, offsets, fields = [], [], []
            for c in range(3):
                columns = [x[:, c], np.ones(len(x))]
                if radial:
                    columns += [x[:, c]*r2, x[:, c]*r2**2]
                design = np.array(columns).T
                if np.linalg.cond(design[train]) > 1e5:
                    raise ValueError('colour calibration is ill-conditioned')
                beta = np.linalg.lstsq(design[train], y[train, c], rcond=None)[0]
                if beta[0] <= 0:
                    raise ValueError('nonpositive colour gain')
                gains.append(beta[0]); offsets.append(beta[1])
                fields.append(beta[2:]/beta[0] if radial else [0., 0.])
            model = {'domain': 'linear-eye', 'gain': gains, 'offset': offsets, 'radial': np.array(fields).T.tolist()}
            # The gain must remain positive across the entire normalized eye.
            radius = np.linspace(0, 1, 257)[:, None]
            if np.min(1+radius*np.array(model['radial'])[0]+radius**2*np.array(model['radial'])[1]) <= 0:
                raise ValueError('nonpositive radial colour gain')
            error = apply(rgb, model, uv)-observed
            models.append((float(np.sqrt(np.mean(error[select]**2))), model, error))
        except ValueError:
            if not radial:
                raise
    chosen = int(len(models) > 1 and models[1][0] < .8*models[0][0] and models[0][0]-models[1][0] > .05)
    _, model, error = models[chosen]
    rmse = float(np.sqrt(np.mean(error[held]**2)))
    p95 = float(np.percentile(np.abs(error[held]), 95))
    local = [float(np.sqrt(np.mean(error[held & np.all(cells == cell, axis=1)]**2)))
             for cell in set(map(tuple, cells[held]))]
    # Measure amplification in output codes, including the transfer function.
    base = np.array([[128., 128., 128.], [160., 100., 70.], [80., 130., 100.]])
    positions = np.full((len(base), 2), .5)
    gains = []
    for direction in (np.array([0., -2*bs.KB*(1-bs.KB)/(1-bs.KR-bs.KB), 2*(1-bs.KB)]),
                      np.array([2*(1-bs.KR), -2*bs.KR*(1-bs.KR)/(1-bs.KR-bs.KB), 0.])):
        delta = (apply(base+direction, model, positions)-apply(base-direction, model, positions))/2
        luma = delta @ np.array([bs.KR, 1-bs.KR-bs.KB, bs.KB])
        gains.extend(np.hypot((delta[:, 2]-luma)/(2*(1-bs.KB)), (delta[:, 0]-luma)/(2*(1-bs.KR))))
    return model, {'scores_available': rmse <= 1 and p95 <= 2 and max(local) <= 1,
                   'held_out_rmse_codes': rmse, 'held_out_p95_codes': p95,
                   'spatial_holdout_rmse_codes': local, 'radial_selected': bool(chosen),
                   'selection_rmse_codes': [m[0] for m in models], 'patches_used': len(rgb),
                   'colour_amplification_chroma': float(np.mean(gains))}


def load_burst(path):
    """Read independent capture patches using explicitly registered polygons.

    Calibration images are single-eye RGB. Each patch polygon is supplied by
    the calibration capture's landmark registration, never inferred from the
    scored codec residual. The middle half is used to avoid edge filtering.
    """
    path = Path(path)
    if path.is_dir():
        path = path/'calibration.json'
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('schema') != 1 or data.get('layout') != 'full-eye-5x5-v1':
        raise ValueError('unsupported full-eye colour calibration layout')
    patches = layout(data['size'])
    result = {}
    digest = hashlib.sha256(path.read_bytes())
    for side, shots in data['eyes'].items():
        observations = []
        for shot in shots:
            image_path = path.parent/shot['file']
            digest.update(image_path.read_bytes())
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError('unreadable calibration capture')
            image = image[..., ::-1]
            for patch, polygon in zip(patches, shot['polygons'], strict=True):
                polygon = np.asarray(polygon, np.float32)
                if polygon.shape != (4, 2) or not np.isfinite(polygon).all():
                    raise ValueError('invalid calibration polygon')
                polygon = polygon.mean(axis=0)+(polygon-polygon.mean(axis=0))*.5
                if np.any(polygon < 0) or np.any(polygon >= image.shape[1::-1]):
                    continue
                mask = np.zeros(image.shape[:2], np.uint8)
                cv2.fillConvexPoly(mask, np.rint(polygon).astype(np.int32), 1)
                values = image[mask != 0]
                if len(values) < 16:
                    continue
                observed = np.median(values, axis=0)
                if np.any(observed < 3) or np.any(observed > 252):
                    continue
                observations.append({**patch, 'observed': observed.tolist()})
        result[side] = fit(observations)
    # Include fitted values in the identity; two compared captures must use
    # exactly the same calibration, including per-eye colour parameters.
    digest.update(json.dumps(result, sort_keys=True).encode())
    return result, digest.hexdigest()



def validate_sample(capture, reference, mapping, scene, valid):
    """Check a frozen model for capture-specific drift; never refit it."""
    observed = mapping.pull(capture, scene.panel_size)
    predicted = mapping.pull(reference, scene.panel_size)
    visible = mapping.pull(valid.astype(np.float32), scene.panel_size) > .999
    errors = []
    for patch in scene.calibration:
        x, y, w, h = patch['box']
        pad = max(1, min(w, h)//4)
        sl = np.s_[y+pad:y+h-pad, x+pad:x+w-pad]
        if not visible[sl].size or not visible[sl].all():
            continue
        a, b = np.median(observed[sl], axis=(0, 1)), np.median(predicted[sl], axis=(0, 1))
        if np.any(a < 3) or np.any(a > 252):
            continue
        errors.append(a-b)
    rmse = float(np.sqrt(np.mean(np.square(errors)))) if errors else None
    p95 = float(np.percentile(np.abs(errors), 95)) if errors else None
    return {'patches': len(errors), 'rmse_codes': rmse, 'p95_codes': p95,
            'scores_available': len(errors) >= 4 and rmse <= 1 and p95 <= 2}

"""Lens-aware compositor scoring; private captures stay local."""
from pathlib import Path
import json

import cv2
import numpy as np

from tools.quest3 import bench_registration as reg
from tools.quest3 import bench_score as bs


def read_capture(directory, shot, side):
    path = directory/shot['file']
    if path.suffix == '.rgba':
        rgb = np.fromfile(path, np.uint8).reshape(shot['height'], shot['width'], 4)[..., :3]
    else:
        bgr = cv2.imread(str(path))
        if bgr is None:
            raise ValueError('unreadable image')
        rgb = bgr[..., ::-1]
    part = rgb if side == 'single' else rgb[:, :rgb.shape[1]//2] if side == 'left' else rgb[:, rgb.shape[1]//2:]
    # Exclude an unmatched last row/column from the centred 4:2:0 lattice.
    return part[:part.shape[0]//2*2, :part.shape[1]//2*2]


def capture_visibility(capture):
    """Exclude the compositor's border-connected black hidden-area mask.

    Interior black content remains eligible. True black touching the lens
    boundary is conservatively unavailable too; it cannot validate a warp.
    """
    black = (np.max(capture, axis=2) <= 1).astype(np.uint8)
    _, components = cv2.connectedComponents(black, connectivity=8)
    border = np.unique(np.r_[components[0], components[-1], components[:, 0], components[:, -1]])
    border = border[border != 0]
    return bs.erode(~np.isin(components, border), 3)


def sample_source(source, mapping, source_h):
    """Forward truth in capture pixels; same sample lattice as output."""
    coords = reg.project(mapping.grid(mapping.lens.size, inverse=True), source_h).astype(np.float32)
    reference = cv2.remap(source, coords[..., 0], coords[..., 1], cv2.INTER_LINEAR, borderValue=(28, 28, 28))
    valid = ((coords[..., 0] >= 1) & (coords[..., 0] < source.shape[1]-2) &
             (coords[..., 1] >= 1) & (coords[..., 1] < source.shape[0]-2))
    return reference, valid


def _shots(directory):
    path = directory/'burst.json'
    return json.loads(path.read_text(encoding='utf-8-sig'))['shots'] if path.exists() else [{'file': p.name} for p in sorted(directory.glob('*.png'))]


def _split_pair(source, target, size):
    held = reg.spatial_split(source, size)
    return (source[~held], target[~held]), (source[held], target[held])


def _configure_roi(score, scene):
    offset = np.eye(3)
    if not scene.backdrop:
        return offset, None
    bx, by, bw, bh = scene.backdrop.central_box
    lo = np.array([bx//32*32, by//32*32])
    hi = np.minimum(scene.backdrop.size, np.ceil(np.array([bx+bw, by+bh])/32)*32).astype(int)
    x, y = lo; w, h = hi-lo
    b = score.background.scene
    b.panel_size = (int(w), int(h))
    b.panel_labels = b.panel_labels[y:y+h, x:x+w]
    central = np.zeros((h, w), bool)
    central[by-y:by-y+bh, bx-x:bx-x+bw] = True
    b.class_masks = {k: v[y:y+h, x:x+w] & central for k, v in b.class_masks.items()}
    b.support_mask = b.support_mask[y:y+h, x:x+w] & central
    offset[:2, 2] = lo
    return offset, [int(x), int(y), int(w), int(h)]


def _add(score, scene, capture, reference, valid, index, side, shot, extra, mapping,
         bg_reference=None, bg_valid=None, bg_map=None):
    bs._PlaneScore.add(score, bs.rgb_planes(reference), bs.rgb_planes(capture), index,
                       valid, side, shot['file'], extra, homography=mapping)
    if scene.backdrop:
        score.background.add(bs.rgb_planes(bg_reference), bs.rgb_planes(capture), index,
                             bg_valid, side, shot['file'], extra, homography=bg_map)


def score_lens(directory, scene, eye, calibration=None, planar=False):
    from tools.quest3 import bench_colour, bench_noise
    directory = Path(directory)
    shots = _shots(directory)
    validated = bs.ScoreAccumulator(scene, 'compositor')
    diagnostic_score = bs.ScoreAccumulator(scene, 'compositor')
    offset, roi = _configure_roi(validated, scene)
    _configure_roi(diagnostic_score, scene)
    noise = {kind: {step: bs.ScoreAccumulator(scene, 'compositor', record_spatial=False) for step in (.25, .5)}
             for kind in ('validated', 'diagnostic')}
    for controls in noise.values():
        for acc in controls.values():
            _configure_roi(acc, scene)
    calibration_models, calibration_id = bench_colour.load_burst(calibration) if calibration else ({}, None)
    diagnostics, rejected, unavailable = [], [], []
    panel_features = reg.features(scene.panel)
    frozen_models = {}
    for side in ('left', 'right') if eye == 'both' else (eye,):
        rows, marker_pairs = [], []
        for shot in shots:
            info = {'file': shot['file'], 'eye': side, 'status': 'rejected'}
            diagnostics.append(info)
            try:
                capture = read_capture(directory, shot, side)
                a, b = reg.detect(capture, scene)
                train, held = _split_pair(a, b, scene.panel_size)
                if len(train[0]) < 4:
                    raise ValueError('insufficient training markers after spatial holdout reservation')
                rows.append({'shot': shot, 'info': info, 'features': reg.features(capture),
                             'markers': (a, b), 'held_markers': held})
                marker_pairs.append(train)
            except ValueError as exc:
                info['reason'] = str(exc); rejected.append(info)
        if not rows:
            continue
        try:
            if planar:
                maps = []
                for row in rows:
                    capture = read_capture(directory, row['shot'], side)
                    # Use the planar API for its failure/fallback diagnostics.
                    h, _ = bs.fit_homography(capture, scene, refine=False)
                    aligned = cv2.warpPerspective(capture, np.linalg.inv(h), scene.panel_size)
                    index = bs.decode_barcode(aligned, scene.barcode_box)
                    _, transform, _ = bs.refine_source_registration(capture, scene, index, side, h)
                    lens = reg.Lens(capture.shape[1::-1])
                    norm = np.array([[1/lens.scale, 0, -lens.centre[0]/lens.scale],
                                     [0, 1/lens.scale, -lens.centre[1]/lens.scale], [0, 0, 1.]])
                    maps.append(reg.PlaneMap(lens, norm @ transform @ scene.homography(index, side)))
            else:
                maps, _ = reg.fit_burst(marker_pairs, capture.shape[1::-1])
        except ValueError as exc:
            for row in rows:
                row['info']['reason'] = str(exc); rejected.append(row['info'])
            continue
        # A clipped marker column may not decode the barcode at all. Spread
        # the initial calibration with static panel landmarks before requiring
        # frame identity; these also reserve the same spatial holdout cells.
        expanded = []
        for row, mapping, marker_pair in zip(rows, maps, marker_pairs):
            a, b = reg.matches(panel_features, row['features'], mapping, radius=120, maximum=400)
            train, held = _split_pair(a, b, scene.panel_size)
            row['panel_train'] = tuple(np.concatenate((m, f)) for m, f in zip(marker_pair, train))
            row['panel_held'] = tuple(np.concatenate((m, f)) for m, f in zip(row['held_markers'], held))
            expanded.append(row['panel_train'])
        try:
            if planar:
                maps, _ = reg._fit_burst(expanded, capture.shape[1::-1], None, 40, 0, 0.)
            else:
                maps, _ = reg.fit_burst(expanded, capture.shape[1::-1], maps[0].lens.coefficients)
        except ValueError as exc:
            for row in rows:
                row['info']['reason'] = str(exc); rejected.append(row['info'])
            continue
        training, ready = [], []
        for row, initial, marker_pair in zip(rows, maps, marker_pairs):
            shot, info = row['shot'], row['info']
            try:
                capture = read_capture(directory, shot, side)
                index, barcode = reg.barcode_index(capture, initial, scene, shot)
                info.update(index=index, **barcode)
                row['panel_slot'] = len(training)
                training.append(row['panel_train'])
                if scene.backdrop:
                    source = scene.render_frame(index, side)
                    source_h = scene.homography(index, side)
                    bg_h = scene.homography(index, side, 'backdrop')
                    source_map = reg.PlaneMap(initial.lens, initial.homography @ np.linalg.inv(source_h))
                    a, b = reg.matches(reg.features(source, maximum=5000), row['features'], source_map, radius=120, maximum=500)
                    positions = np.rint(a).astype(int)
                    visible = scene.backdrop_visibility(index, side)
                    keep = visible[positions[:, 1], positions[:, 0]] if len(a) else np.zeros(0, bool)
                    native = reg.project(a[keep], np.linalg.inv(bg_h))
                    train, held = _split_pair(native, b[keep], scene.backdrop.size)
                    if len(train[0]) < 8:
                        raise ValueError('insufficient backdrop training landmarks after spatial holdouts')
                    row.update(bg_slot=len(training), bg_train=train, bg_held=held)
                    training.append(train)
                ready.append(row)
            except ValueError as exc:
                info['reason'] = str(exc); rejected.append(info)
        if not ready:
            continue
        try:
            # The only final lens fit: all training planes/shots in this eye.
            # Nothing below can alter its coefficients or fit intensities.
            if planar:
                fitted, fits = reg._fit_burst(training, capture.shape[1::-1], None, 40, 0, 0.)
            else:
                fitted, fits = reg.fit_burst(training, capture.shape[1::-1], maps[0].lens.coefficients)
            lens = fitted[0].lens
        except ValueError as exc:
            for row in ready:
                row['info']['reason'] = str(exc); rejected.append(row['info'])
            continue
        # Fit a single legacy strip model per eye for diagnostics only. It
        # never establishes full-eye colour coverage, even on lossless input.
        colour, colour_info = calibration_models.get(side, (None, None))
        if colour is None:
            for row in ready:
                try:
                    capture = read_capture(directory, row['shot'], side)
                    mapping = fitted[row['panel_slot']]
                    aligned = mapping.pull(capture, scene.panel_size)
                    valid = mapping.pull(capture_visibility(capture).astype(np.float32), scene.panel_size) > .999
                    colour, colour_info = bs.fit_colour(aligned, scene, bs.erode(valid, 3))
                    colour_info = {**colour_info, 'scores_available': False, 'calibration_source_sample_id': row['shot']['file'],
                                   'reason': 'full-eye independent calibration burst required; strip is diagnostic-only'}
                    break
                except ValueError:
                    continue
        if colour is None:
            colour = {'domain': 'linear-srgb', 'matrix': np.vstack((np.eye(3), np.zeros(3))).tolist()}
            colour_info = {'scores_available': False, 'held_out_rmse_codes': None, 'colour_amplification_chroma': 1.,
                           'reason': 'no usable colour calibration; identity model for diagnostics only'}
        frozen_models[side] = {'lens': lens.coefficients.tolist(), 'colour': colour, 'colour_validation': colour_info}
        for row in ready:
            shot, info = row['shot'], row['info']
            index = info['index']
            print(f"[BENCH_FROZEN_SCORE] {shot['file']} {side} frame={index}", flush=True)
            try:
                capture = read_capture(directory, shot, side)
                capture_valid = capture_visibility(capture)
                mapping = fitted[row['panel_slot']]
                # Refine only this plane's homography against training landmarks.
                if len(row['panel_train'][0]) >= 8:
                    mapping, _, _ = reg.refine_plane(mapping, *row['panel_train'])
                coords = mapping.grid(lens.size, inverse=True)
                panel_visible = ((coords[..., 0] >= 0) & (coords[..., 0] < scene.panel_size[0]) &
                                 (coords[..., 1] >= 0) & (coords[..., 1] < scene.panel_size[1]))
                footprint = mapping.pull((capture_valid & panel_visible).astype(np.float32), scene.panel_size) > .999
                footprint &= scene.panel_labels > 0
                geometry = {'panel': reg.validate_plane(mapping, *row['panel_held'], footprint)}
                source_h = scene.homography(index, side)
                source = scene.render_frame(index, side)
                # Global transforms act before source filtering as before;
                # a full-eye radial field is evaluated on the source eye grid.
                colour_ok = colour_info['scores_available']
                transformed = bs.apply_colour(source, colour)
                reference, valid = sample_source(transformed, mapping, source_h)
                colour_check = bench_colour.validate_sample(capture, reference, mapping, scene, valid & capture_valid) if colour_ok else None
                if colour_check is not None:
                    colour_ok = colour_check['scores_available']
                    info['frozen_colour_sample_check'] = colour_check
                valid = bs.erode(valid & capture_valid & panel_visible, 3)
                bg_reference = bg_valid = bg_map = None
                if scene.backdrop:
                    bg_fitted = fitted[row['bg_slot']]
                    bg_fitted, _, _ = reg.refine_plane(bg_fitted, *row['bg_train'])
                    bg_map = reg.PlaneMap(lens, bg_fitted.homography @ offset)
                    bg_h = scene.homography(index, side, 'backdrop')
                    bg_reference, bg_valid = sample_source(transformed, bg_map, bg_h @ offset)
                    bg_valid &= capture_valid & ~cv2.dilate(panel_visible.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
                    source_coords = reg.project(bg_map.grid(lens.size, inverse=True), bg_h @ offset).astype(np.float32)
                    bg_valid &= cv2.remap(scene.backdrop_visibility(index, side).astype(np.float32), source_coords[..., 0], source_coords[..., 1], cv2.INTER_LINEAR) > .999
                    bg_valid = bs.erode(bg_valid, 3)
                    bscene = validated.background.scene
                    footprint = bg_map.pull(bg_valid.astype(np.float32), bscene.panel_size) > .999
                    footprint &= bscene.support_mask
                    a, b = row['bg_held']
                    geometry['backdrop'] = reg.validate_plane(bg_map, a-offset[:2, 2], b, footprint)
                geometry_ok = all(g['scores_available'] for g in geometry.values())
                info.update(geometry=geometry, colour=colour_info, lens_coefficients=lens.coefficients.tolist(),
                            lens_fit=fits[row['panel_slot']], panel_to_ideal=mapping.homography.tolist(),
                            source_size=list(scene.size))
                extra = {'registration': info, 'colour': colour_info, 'capture_time': shot.get('start_s', index)}
                # Separate accumulators: an invalid shot never poisons or enters
                # validated temporal statistics from otherwise valid captures.
                accepted = geometry_ok and colour_ok
                if accepted:
                    # Qualify each sample separately; a failed control cannot
                    # remove another capture from validated temporal statistics.
                    control = bs.ScoreAccumulator(scene, 'compositor', record_spatial=False)
                    _configure_roi(control, scene)
                    for n, delta in enumerate((0., .25)):
                        bs._PlaneScore.add(control, bs.rgb_planes(reference), bs.rgb_planes(bench_noise.shift(reference, delta)),
                                           index, valid, side, str(n), homography=mapping)
                        if scene.backdrop:
                            control.background.add(bs.rgb_planes(bg_reference), bs.rgb_planes(bench_noise.shift(bg_reference, delta)),
                                                   index, bg_valid, side, str(n), homography=bg_map)
                    info['registration_control_aggregate'] = control.finish()['aggregate']
                    accepted = bench_noise.qualified(info['registration_control_aggregate'])
                    info['registration_control_available'] = accepted
                target = validated if accepted else diagnostic_score
                _add(target, scene, capture, reference, valid, index, side, shot, extra, mapping, bg_reference, bg_valid, bg_map)
                info['status'] = 'accepted' if accepted else 'diagnostic_only'
                if not accepted:
                    info['reason'] = '; '.join(([] if geometry_ok else ['spatial geometry holdouts exceed 0.1 px median / 0.25 px p95 or lack local coverage']) +
                                              ([] if colour_ok else [colour_info.get('reason', 'independent colour holdouts failed')]) +
                                              (['registration-noise control exceeds metric allowance'] if geometry_ok and colour_ok and not accepted else []))
                    unavailable.append(info)
                # Lossless controls with alternating 0/step capture-pixel shifts,
                # using exactly these maps, class masks and valid footprints.
                for step, acc in noise['validated' if accepted else 'diagnostic'].items():
                    delta = step if len(acc.samples) % 2 else 0.
                    perturbed = bench_noise.shift(reference, delta)
                    bg_perturbed = bench_noise.shift(bg_reference, delta) if scene.backdrop else None
                    bs._PlaneScore.add(acc, bs.rgb_planes(reference), bs.rgb_planes(perturbed), index,
                                       valid, side, shot['file'], homography=mapping)
                    if scene.backdrop:
                        acc.background.add(bs.rgb_planes(bg_reference), bs.rgb_planes(bg_perturbed), index,
                                           bg_valid, side, shot['file'], homography=bg_map)
            except ValueError as exc:
                info.update(status='rejected', reason=str(exc)); rejected.append(info)
                print(f'[BENCH_FROZEN_REJECT] {exc}', flush=True)
    report, conditional = validated.finish(), diagnostic_score.finish()
    for key in ('aggregate', 'samples', 'detail_samples', 'compositor_blocks', 'backdrop_compositor_blocks', 'sample_count', 'observation_count'):
        if key in conditional:
            report['diagnostic_'+key] = conditional[key]
    report.update(registration_model='frozen per-eye burst lens from training landmarks only; per-shot homographies',
                  registration_shots=diagnostics, rejected=rejected, unavailable=unavailable, backdrop_scoring_roi=roi,
                  frozen_models=frozen_models, colour_calibration_id=calibration_id)
    bench_noise.annotate(report, {str(step): acc.finish() for step, acc in noise['validated'].items()},
                         {str(step): acc.finish() for step, acc in noise['diagnostic'].items()})
    if not report['sample_count']:
        report['acceptance'] = 'UNAVAILABLE: no samples meet independent full-footprint geometry, colour and registration-noise qualification; diagnostic fields are not codec attribution.'
    return report

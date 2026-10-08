"""Lens-aware compositor scoring; private captures stay local."""
from pathlib import Path
import json
from types import SimpleNamespace

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
    return rgb if side == 'single' else rgb[:, :rgb.shape[1]//2] if side == 'left' else rgb[:, rgb.shape[1]//2:]


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


def refine_markers(capture, source, panel_map, source_h, scene, detected_corners=None, refine_lens=True, detected_panel=None):
    """Fit neutral marker pixels against forward-sampled recorded truth.

    Only geometric parameters plus neutral gain/offset are fitted. Natural
    content and all scored probes are excluded from this photometric fit.
    """
    mask = np.zeros(capture.shape[:2], np.uint8)
    polygons = (np.asarray(detected_corners).reshape(-1, 4, 2) if detected_corners is not None else
                [panel_map.forward(np.asarray(marker['corners'])) for marker in scene.fiducials])
    for points in polygons:
        if np.max(np.abs(points)) < 1e4:
            cv2.fillConvexPoly(mask, np.rint(points).astype(np.int32), 1)
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    yy, xx = np.nonzero(mask)
    step = max(1, len(xx)//6000)
    points = np.c_[xx[::step], yy[::step]].astype(np.float64)
    target = capture[yy[::step], xx[::step]].astype(float).mean(axis=1)
    gray = source.astype(np.float32).mean(axis=2)
    scale = max(scene.size)
    norm = np.diag([1/scale, 1/scale, 1.])
    inverse = norm @ source_h @ np.linalg.inv(panel_map.homography)
    inverse /= inverse[2, 2]
    quantized = False
    def error(params):
        h = np.r_[params[:8], 1].reshape(3, 3)
        ideal = panel_map.lens.undistort(points, params[8:] if refine_lens else panel_map.lens.coefficients)
        q = reg.project(ideal, h)*scale
        u = np.clip(q[:, 0], 0, gray.shape[1]-1.001)
        v = np.clip(q[:, 1], 0, gray.shape[0]-1.001)
        ix, iy = u.astype(int), v.astype(int)
        fx, fy = u-ix, v-iy
        values = (1-fy)*((1-fx)*gray[iy, ix]+fx*gray[iy, ix+1])+fy*((1-fx)*gray[iy+1, ix]+fx*gray[iy+1, ix+1])
        if quantized:
            values = cv2.remap(gray, u.astype(np.float32)[:, None], v.astype(np.float32)[:, None], cv2.INTER_LINEAR).ravel()
        centered = values-values.mean()
        gain = np.dot(centered, target-target.mean())/max(np.dot(centered, centered), 1e-9)
        return centered*gain+target.mean()-target
    initial = np.r_[inverse.ravel()[:8], panel_map.lens.coefficients] if refine_lens else inverse.ravel()[:8]
    fit = reg.least_squares(error, initial, iterations=60, robust=10.)
    # Finish with the full neutral-marker objective after robust initialization;
    # otherwise high-contrast edges can remain trapped on a Huber plateau.
    fit = reg.least_squares(error, fit, iterations=40)
    if refine_lens and detected_panel is not None and np.mean(error(fit)**2) > 1:
        # Centre/tangential parameters have local minima when all markers lie
        # on a small border. A second centred seed, refitted to the SAME
        # observed corners, resolves that ambiguity without fitting content.
        seed_lens = reg.Lens(panel_map.lens.size, panel_map.lens.coefficients)
        seed_lens.coefficients[3:] = 0
        native = reg.project(detected_panel, source_h)
        seed_h, _ = cv2.findHomography(native, seed_lens.undistort(detected_corners), 0)
        if seed_h is not None:
            seed_inverse = norm @ np.linalg.inv(seed_h)
            seed_inverse /= seed_inverse[2, 2]
            alternate = reg.least_squares(error, np.r_[seed_inverse.ravel()[:8], seed_lens.coefficients], iterations=60, robust=10.)
            alternate = reg.least_squares(error, alternate, iterations=40)
            if np.mean(error(alternate)**2) < np.mean(error(fit)**2):
                fit = alternate
    quantized = True
    best = np.mean(error(fit)**2)
    units = np.r_[np.full(8, 1/scale), np.full(len(fit)-8, 10/scale)]
    for epsilon in (.1, .04, .02):
        for _ in range(6):
            residual = error(fit)
            columns = []
            for n, unit in enumerate(units):
                plus, minus = fit.copy(), fit.copy()
                plus[n] += epsilon*unit; minus[n] -= epsilon*unit
                columns.append((error(plus)-error(minus))/(2*epsilon))
            delta = np.linalg.lstsq(np.stack(columns, axis=1), -residual, rcond=1e-6)[0]
            delta = np.clip(delta, -1, 1)
            improved = False
            for fraction in (1., .5, .25):
                candidate = fit+fraction*units*delta
                cost = np.mean(error(candidate)**2)
                if cost < best:
                    fit, best, improved = candidate, cost, True
                    break
            if not improved:
                break
    for epsilon in (4e-5, 1e-5, 3e-6, 1e-6):
        for _ in range(5):
            changed = False
            for n in range(len(fit)):
                for sign in (-1, 1):
                    candidate = fit.copy(); candidate[n] += sign*epsilon
                    cost = np.mean(error(candidate)**2)
                    if cost < best:
                        fit, best, changed = candidate, cost, True
            if not changed:
                break
    matrix = np.linalg.inv(np.linalg.inv(norm) @ np.r_[fit[:8], 1].reshape(3, 3)) @ source_h
    lens = reg.Lens(panel_map.lens.size, fit[8:]) if refine_lens else panel_map.lens
    return reg.PlaneMap(lens, matrix), float(np.sqrt(np.mean(error(fit)**2)))


def score_lens(directory, scene, eye):
    directory = Path(directory)
    path = directory/'burst.json'
    shots = json.loads(path.read_text(encoding='utf-8-sig'))['shots'] if path.exists() else [{'file': p.name} for p in sorted(directory.glob('*.png'))]
    score = bs.ScoreAccumulator(scene, 'compositor')
    diagnostics, rejected, unavailable = [], [], []
    prepared = []
    panel_features = reg.features(scene.panel)
    for side in ('left', 'right') if eye == 'both' else (eye,):
        rows, pairs = [], []
        for shot in shots:
            diagnostic = {'file': shot['file'], 'eye': side, 'status': 'rejected'}
            diagnostics.append(diagnostic)
            try:
                capture = read_capture(directory, shot, side)
                source, target = reg.detect(capture, scene)
                rows.append((shot, diagnostic, reg.features(capture)))
                pairs.append((source, target))
            except ValueError as exc:
                diagnostic['reason'] = str(exc); rejected.append(diagnostic)
        if not pairs:
            continue
        maps, fits = reg.fit_burst(pairs, capture.shape[1::-1])
        # Interior panel landmarks break the thin-column degeneracy of B2's
        # clipped marker border. Keep marker weight by repeating those pairs.
        expanded = []
        for mapping, pair, row in zip(maps, pairs, rows):
            a, b = reg.matches(panel_features, row[2], mapping, radius=100, maximum=100)
            expanded.append((np.concatenate((pair[0], pair[0], a)), np.concatenate((pair[1], pair[1], b))))
        maps, _ = reg.fit_burst(expanded, capture.shape[1::-1], maps[0].lens.coefficients)
        for mapping, pair, row in zip(maps, pairs, rows):
            shot, diagnostic, observed_features = row
            e = np.linalg.norm(mapping.forward(pair[0])-pair[1], axis=1)
            diagnostic.update(corner_fit_rms_capture_px=float(np.sqrt(np.mean(e*e))), markers=len(pair[0])//4,
                              burst_lens_coefficients=mapping.lens.coefficients.tolist())
            try:
                capture = read_capture(directory, shot, side)
                index, barcode = reg.barcode_index(capture, mapping, scene, shot)
                diagnostic.update(index=index, **barcode)
                if diagnostic['corner_fit_rms_capture_px'] > 1.5:
                    raise ValueError('lens corner RMS exceeds 1.5 capture pixels')
                prepared.append((shot, side, diagnostic, mapping, observed_features, pair))
            except ValueError as exc:
                diagnostic['reason'] = str(exc); rejected.append(diagnostic)
    # Score the original captured Metro image, excluding reflected extension.
    # The fixed source ROI also preserves a common grid across worn A/B poses.
    offset = np.eye(3)
    if scene.backdrop and prepared:
        bx, by, bw, bh = scene.backdrop.central_box
        lo = np.array([bx//32*32, by//32*32])
        hi = np.minimum(scene.backdrop.size, np.ceil(np.array([bx+bw, by+bh])/32)*32).astype(int)
        x, y = lo; w, h = hi-lo
        if min(w, h) <= 0:
            raise ValueError('backdrop not visible in fitted burst')
        b = score.background.scene
        b.panel_size = (int(w), int(h))
        b.panel_labels = b.panel_labels[y:y+h, x:x+w]
        central = np.zeros((h, w), bool)
        central[by-y:by-y+bh, bx-x:bx-x+bw] = True
        b.class_masks = {k: v[y:y+h, x:x+w] & central for k, v in b.class_masks.items()}
        b.support_mask = b.support_mask[y:y+h, x:x+w] & central
        offset[:2, 2] = lo
        backdrop_roi = [int(x), int(y), int(w), int(h)]
        print(f'[BENCH_LENS_ROI] {backdrop_roi}', flush=True)
    else:
        backdrop_roi = None
    colour_by_eye = {}
    for shot, side, diagnostic, mapping, observed_features, corners in prepared:
        print(f"[BENCH_LENS_SCORE] {shot['file']} {side} frame={diagnostic['index']}", flush=True)
        try:
            capture = read_capture(directory, shot, side)
            capture_valid = capture_visibility(capture)
            index = diagnostic['index']
            source_h = scene.homography(index, side)
            source = scene.render_frame(index, side)
            mapping, marker_rmse = refine_markers(capture, source, mapping, source_h, scene, corners[1], detected_panel=corners[0])
            diagnostic['forward_marker_rmse_codes'] = marker_rmse
            diagnostic['refined_lens_coefficients'] = mapping.lens.coefficients.tolist()
            if marker_rmse > 25:
                raise ValueError('forward marker fit exceeds 25 codes; pose/filter/lens mismatch')
            diagnostic['corner_refined_rms_capture_px'] = float(np.sqrt(np.mean((mapping.forward(corners[0])-corners[1])**2)*2))
            # Backdrop registration is independently checked before adding
            # either plane, keeping both score sample lists synchronized.
            if scene.backdrop:
                bg_h = scene.homography(index, side, 'backdrop')
                initial = reg.PlaneMap(mapping.lens, mapping.homography @ np.linalg.inv(source_h))
                ref_features = reg.features(source, maximum=5000)
                a, b = reg.matches(ref_features, observed_features, initial, radius=100, maximum=320)
                panel_region = bs.plane_mask(scene.panel_labels.shape, source_h, scene.size)
                positions = np.rint(a).astype(int)
                on_panel = panel_region[positions[:, 1], positions[:, 0]] if len(a) else np.zeros(0, bool)
                panel_a, panel_b = a[on_panel], b[on_panel]
                labels = scene.backdrop_visibility(index, side)
                positions = np.rint(a).astype(int)
                eligible = labels[positions[:, 1], positions[:, 0]] if len(a) else np.zeros(0, bool)
                a, b = a[eligible], b[eligible]
                if len(a) < 20:
                    raise ValueError(f'backdrop has only {len(a)} feature matches (20 required)')
                # Alternating spatially distributed matches are held out.
                fitted, _, inliers = reg.refine_plane(initial, a[::2], b[::2], threshold=3.)
                # The panel does not constrain the top half of a barrel lens.
                # Refine its per-shot model with training backdrop landmarks,
                # keeping a separate plane homography and held-out check.
                panel_native = reg.project(corners[0], source_h)
                broad, _ = reg.fit_burst([(panel_native, corners[1]), (a[::2], b[::2])],
                                         mapping.lens.size, mapping.lens.coefficients, iterations=35)
                candidate = broad[1]
                # Model selection uses training errors, never held-out pixels.
                old_train = np.linalg.norm(fitted.forward(a[::2])-b[::2], axis=1)
                new_train = np.linalg.norm(candidate.forward(a[::2])-b[::2], axis=1)
                if np.median(new_train) < np.median(old_train):
                    fitted = candidate
                # SIFT centroids are biased by resampling. Do not replace an
                # already subpixel-consistent photometric map just to fit that
                # detector noise with more geometric degrees of freedom.
                initial_train = np.linalg.norm(initial.forward(a[::2])-b[::2], axis=1)
                if np.median(initial_train) <= .75:
                    fitted = initial
                held = np.linalg.norm(fitted.forward(a[1::2])-b[1::2], axis=1)
                trusted = held < 5
                diagnostic.update(backdrop_matches=len(a), backdrop_inliers=int(inliers.sum()),
                    backdrop_held_out_median_px=float(np.median(held)), backdrop_held_out_p90_px=float(np.percentile(held, 90)))
                print(f'[BENCH_LENS_BACKDROP] matches={len(a)} median_px={np.median(held):.3f}', flush=True)
                if trusted.sum() < 8 or np.median(held) > 2.:
                    raise ValueError('backdrop feature validation exceeds 2 pixels or lacks held-out support')
                # A clipped marker column alone can fit while its interior
                # folds. Use the wider lens calibration, then refine only the
                # panel homography; validate on independent rendered features.
                if len(panel_a) >= 8:
                    candidate_panel = reg.PlaneMap(broad[0].lens, broad[0].homography @ source_h)
                    candidate_panel, candidate_rmse = refine_markers(
                        capture, source, candidate_panel, source_h, scene, corners[1], refine_lens=False)
                    old_error = np.linalg.norm(initial.forward(panel_a)-panel_b, axis=1)
                    candidate_source = reg.PlaneMap(candidate_panel.lens, candidate_panel.homography @ np.linalg.inv(source_h))
                    new_error = np.linalg.norm(candidate_source.forward(panel_a)-panel_b, axis=1)
                    if candidate_rmse <= 1.25*marker_rmse+.25 and np.median(new_error) < np.median(old_error):
                        mapping, marker_rmse = candidate_panel, candidate_rmse
                        panel_error = new_error
                    else:
                        panel_error = old_error
                    diagnostic.update(panel_feature_matches=len(panel_a), panel_feature_median_px=float(np.median(panel_error)))
                    if np.median(panel_error) > 2:
                        raise ValueError('panel interior feature validation exceeds 2 pixels (clipped-border extrapolation)')
                elif len(corners[0]) < 24:
                    raise ValueError('clipped panel lacks independent interior feature support')
                diagnostic['backdrop_lens_coefficients'] = fitted.lens.coefficients.tolist()
                bg_map = reg.PlaneMap(fitted.lens, fitted.homography @ bg_h @ offset)
            diagnostic['forward_marker_rmse_codes'] = marker_rmse
            diagnostic['refined_lens_coefficients'] = mapping.lens.coefficients.tolist()
            diagnostic['corner_refined_rms_capture_px'] = float(np.sqrt(np.mean((mapping.forward(corners[0])-corners[1])**2)*2))
            aligned = mapping.pull(capture, scene.panel_size)
            valid_panel = mapping.pull(capture_valid.astype(np.float32), scene.panel_size) > .999
            try:
                colour, colour_diagnostics = bs.fit_colour(aligned, scene, bs.erode(valid_panel, 3))
                colour_by_eye[side] = (colour, colour_diagnostics, shot['file'])
            except ValueError as exc:
                if not str(exc).startswith('insufficient unclipped calibration patches') or side not in colour_by_eye:
                    raise
                # This never validates a shot. A same-eye burst model permits
                # conditional temporal diagnostics when head motion clips the
                # colour strip; keep its provenance and failure explicit.
                colour, baseline, origin = colour_by_eye[side]
                colour_diagnostics = {**baseline, 'scores_available': False, 'held_out_rmse_codes': None,
                    'burst_reference_held_out_rmse_codes': baseline['held_out_rmse_codes'],
                    'calibration_source_sample_id': origin, 'patches_used': 0, 'unavailable_reason': str(exc)}
            diagnostic['colour'] = colour_diagnostics
            print(f"[BENCH_LENS_COLOUR] held_out={colour_diagnostics['held_out_rmse_codes']} marker_rmse={marker_rmse:.3f}", flush=True)
            if not colour_diagnostics['scores_available']:
                diagnostic.update(status='unavailable', reason=colour_diagnostics.get('unavailable_reason', 'held-out colour model error exceeds 0.5 codes'))
            transformed = bs.apply_colour(source, colour)
            reference, valid = sample_source(transformed, mapping, source_h)
            valid &= capture_valid
            panel_coords = mapping.grid(mapping.lens.size, inverse=True)
            panel_visible = ((panel_coords[..., 0] >= 0) & (panel_coords[..., 0] < scene.panel_size[0]) &
                             (panel_coords[..., 1] >= 0) & (panel_coords[..., 1] < scene.panel_size[1]))
            if scene.backdrop:
                bg_reference, bg_valid = sample_source(transformed, bg_map, bg_h @ offset)
                bg_valid &= capture_valid
                # Restrict metrics to landmark-supported capture area. Neither
                # a small panel fit nor reflected features justify extrapolation.
                hull = np.zeros(capture.shape[:2], np.uint8)
                supported = np.linalg.norm(fitted.forward(a)-b, axis=1) < 3
                cv2.fillConvexPoly(hull, cv2.convexHull(np.rint(b[supported]).astype(np.int32)), 1)
                bg_valid &= bs.erode(hull.astype(bool), 8)
                bg_valid &= ~cv2.dilate(panel_visible.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
                bg_source_coords = reg.project(bg_map.grid(bg_map.lens.size, inverse=True), bg_h @ offset).astype(np.float32)
                source_visible = scene.backdrop_visibility(index, side).astype(np.float32)
                bg_valid &= cv2.remap(source_visible, bg_source_coords[..., 0], bg_source_coords[..., 1], cv2.INTER_LINEAR) > .999
            extra = {'registration': diagnostic, 'colour': colour_diagnostics}
            bs._PlaneScore.add(score, bs.rgb_planes(reference), bs.rgb_planes(capture), index,
                               bs.erode(valid & panel_visible, 3), side, shot['file'], extra, homography=mapping)
            if scene.backdrop:
                score.background.add(bs.rgb_planes(bg_reference), bs.rgb_planes(capture), index,
                                     bs.erode(bg_valid, 3), side, shot['file'], extra, homography=bg_map)
            diagnostic.update(status='accepted' if colour_diagnostics['scores_available'] else 'registered_colour_unavailable',
                              panel_to_ideal=mapping.homography.tolist())
            if not colour_diagnostics['scores_available']:
                unavailable.append(diagnostic)
        except ValueError as exc:
            diagnostic.update(status='rejected', reason=str(exc)); rejected.append(diagnostic)
            print(f'[BENCH_LENS_REJECT] {exc}', flush=True)
    report = score.finish()
    report.update(registration_model='inverse Brown k1/k2/k3/p1/p2 plus fitted centre, shared per burst/eye; per-plane homographies',
                  registration_shots=diagnostics, rejected=rejected, unavailable=unavailable, backdrop_scoring_roi=backdrop_roi)
    if scene.backdrop:
        report['definitions']['backdrop'] = ('separate fixed source-image texel grid; original source rectangle only, '
            'excluding mirrored padding, lens hidden area, panel occlusion and unsupported landmark extrapolation; '
            'overlapping automatic natural subclasses; backdrop_scoring_roi gives the 32-aligned crop')
    groups = {}
    for sample in score.samples:
        groups.setdefault(sample['sample_id'], []).append(sample['colour']['colour_amplification_chroma'])
    report['colour_amplification_chroma'] = bs.distribution([float(np.mean(v)) for v in groups.values()])
    # Keep colour-model failure explicit. Useful conditional diagnostics are
    # separate from validated metrics and cannot enter compare's verdict.
    if unavailable and score.samples:
        for key in ('aggregate', 'samples', 'detail_samples', 'compositor_blocks', 'backdrop_compositor_blocks'):
            if key in report:
                report['diagnostic_'+key] = report[key]
        report['diagnostic_sample_count'] = report['sample_count']
        report['diagnostic_observation_count'] = report['observation_count']
        report['aggregate'] = {name: {metric: {**value, 'mean': None, 'std': None, 'n': 0, 'ci95': None, 'infinite': False}
                                      for metric, value in fields.items()} for name, fields in report['aggregate'].items()}
        report.update(samples=[], detail_samples={}, compositor_blocks=[], backdrop_compositor_blocks=[], sample_count=0, observation_count=0,
                      acceptance='UNAVAILABLE: held-out colour calibration exceeds 0.5 codes. diagnostic_* fields are conditional on an unvalidated colour model; do not use for acceptance or codec attribution.')
    return report

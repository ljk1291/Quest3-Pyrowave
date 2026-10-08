"""CPU lens registration. Geometry is fitted to landmarks, never codec residuals.

The inverse Brown model expands capture coordinates to a pinhole image. Its
radial/tangential coefficients are shared by a burst/eye; each plane/shot has
its own homography. Coordinates are normalized for a well-conditioned fit.
"""
from __future__ import annotations

import cv2
import numpy as np


def project(points, matrix):
    p = np.asarray(points, np.float64)
    q = np.c_[p.reshape(-1, 2), np.ones(p.size//2)] @ matrix.T
    return (q[:, :2]/q[:, 2:]).reshape(p.shape)


def least_squares(function, initial, iterations=50, robust=None):
    """Small damped Gauss-Newton fit; no optional SciPy dependency."""
    x = np.asarray(initial, np.float64).copy()
    damping = 1e-4
    for _ in range(iterations):
        r = function(x).ravel()
        weights = np.ones_like(r) if robust is None else np.minimum(1, robust/np.maximum(np.abs(r), 1e-12))
        j = np.empty((r.size, x.size))
        for n in range(x.size):
            step = 1e-5*max(1, abs(x[n]))
            candidate = x.copy(); candidate[n] += step
            j[:, n] = (function(candidate).ravel()-r)/step
        normal = j.T @ (weights[:, None]*j)
        delta = np.linalg.solve(normal + damping*np.diag(np.maximum(np.diag(normal), 1e-8)), -j.T @ (weights*r))
        candidate = x+delta
        if np.sum(weights*function(candidate).ravel()**2) < np.sum(weights*r*r):
            x = candidate
            damping = max(1e-8, damping/3)
            if np.max(np.abs(delta)) < 1e-8:
                break
        else:
            damping *= 10
            if damping > 1e8:
                break
    return x


def detect(capture, scene):
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), params)
    corners, ids, _ = detector.detectMarkers(cv2.cvtColor(capture, cv2.COLOR_RGB2GRAY))
    known = {f['id']: f['corners'] for f in scene.fiducials}
    pairs = [(known[int(i)], c.reshape(4, 2)) for i, c in zip(ids.ravel() if ids is not None else [], corners) if int(i) in known]
    if len(pairs) < 3:
        raise ValueError('lens fit needs at least three visible benchmark markers')
    return np.concatenate([a for a, _ in pairs]), np.concatenate([b for _, b in pairs])


class Lens:
    def __init__(self, size, coefficients=None):
        self.size = tuple(size)
        self.scale = max(size)/2
        self.centre = np.array(size)/2
        self.coefficients = np.zeros(7) if coefficients is None else np.pad(np.array(coefficients), (0, max(0, 7-len(coefficients))))

    def undistort(self, pixels, coefficients=None):
        params = self.coefficients if coefficients is None else coefficients
        shift = params[5:7]
        p = (np.asarray(pixels)-self.centre)/self.scale-shift
        x, y = p[..., 0], p[..., 1]
        k1, k2, k3, p1, p2 = params[:5]
        r2 = x*x+y*y
        radial = 1+r2*(k1+r2*(k2+r2*k3))
        return np.stack((x*radial+2*p1*x*y+p2*(r2+2*x*x),
                         y*radial+p1*(r2+2*y*y)+2*p2*x*y), -1)+shift

    def distort(self, ideal):
        # Newton inversion, analytic Jacobian. Return invalid maps for folds.
        self.check_injective()
        q = np.asarray(ideal, np.float64)
        p = q.copy()
        k1, k2, k3, p1, p2 = self.coefficients[:5]
        for _ in range(18):
            x, y = (p-self.coefficients[5:7])[..., 0], (p-self.coefficients[5:7])[..., 1]
            r = x*x+y*y
            a = 1+r*(k1+r*(k2+r*k3))
            b = k1+r*(2*k2+3*r*k3)
            xx = a+2*x*x*b+2*p1*y+6*p2*x
            yy = a+2*y*y*b+6*p1*y+2*p2*x
            xy = 2*x*y*b+2*p1*x+2*p2*y
            error = self.undistort(p*self.scale+self.centre)-q
            det = xx*yy-xy*xy
            det = np.where(np.abs(det) < 1e-8, 1e-8, det)
            delta = np.stack(((yy*error[..., 0]-xy*error[..., 1])/det,
                              (xx*error[..., 1]-xy*error[..., 0])/det), -1)
            p -= np.clip(delta, -.5, .5)
            if np.max(np.abs(delta)) < 1e-8:
                break
        result = p*self.scale+self.centre
        bad = np.linalg.norm(self.undistort(result)-q, axis=-1) > 1e-5
        result[bad] = -1e4
        return result

    def check_injective(self):
        """Require a positive-definite Brown Jacobian over the capture rectangle.

        The Jacobian is symmetric; uniform positive definiteness implies strict
        monotonicity (and hence injectivity) on this convex domain. A conservative
        derivative bound covers the space between grid points, not just samples.
        """
        key = tuple(self.coefficients)
        if getattr(self, '_checked', None) == key:
            return
        k1, k2, k3, p1, p2, sx, sy = key
        yy, xx = np.mgrid[0:129, 0:129].astype(float)
        x = (xx/128*self.size[0]-self.centre[0])/self.scale-sx
        y = (yy/128*self.size[1]-self.centre[1])/self.scale-sy
        r = x*x+y*y
        a = 1+r*(k1+r*(k2+r*k3)); b = k1+r*(2*k2+3*r*k3)
        jx = a+2*x*x*b+2*p1*y+6*p2*x
        jy = a+2*y*y*b+6*p1*y+2*p2*x
        cross = 2*x*y*b+2*p1*x+2*p2*y
        smallest = (jx+jy-np.hypot(jx-jy, 2*cross))/2
        radius = np.sqrt(r.max())
        # Norm bound for the derivative of the radial/tangential Jacobian.
        derivative = (6*abs(k1)*radius + 20*abs(k2)*radius**3 +
                      42*abs(k3)*radius**5 + 12*(abs(p1)+abs(p2)))
        gap = np.hypot(*self.size)/(256*self.scale)
        if not np.isfinite(smallest).all() or smallest.min()-derivative*gap <= 1e-4:
            raise ValueError('folded or unidentifiable lens: injectivity not established')
        self._checked = key


class PlaneMap:
    def __init__(self, lens, homography):
        self.lens, self.homography = lens, np.array(homography)
        self._grids = {}

    def forward(self, points):
        return self.lens.distort(project(points, self.homography))

    def inverse(self, points):
        return project(self.lens.undistort(points), np.linalg.inv(self.homography))

    def grid(self, size, inverse=False):
        key = (tuple(size), inverse)
        if key in self._grids:
            return self._grids[key]
        if not inverse and max(size) > 1500:
            # Smooth lens geometry: a 4-texel grid avoids Newton-solving tens
            # of millions of invisible backdrop pixels. Verify interpolation
            # at cell centres; fall back to the exact map if >.02 capture px.
            step = 4
            yy, xx = np.mgrid[:size[1]+step:step, :size[0]+step:step].astype(np.float32)
            sparse = self.forward(np.stack((xx, yy), -1)).astype(np.float32)
            check = np.stack((xx[:-1:16, :-1:16]+2, yy[:-1:16, :-1:16]+2), -1)
            exact = self.forward(check)
            approx = (sparse[:-1:16, :-1:16]+sparse[1::16, :-1:16]+sparse[:-1:16, 1::16]+sparse[1::16, 1::16])/4
            visible = ((exact[..., 0] >= 4) & (exact[..., 0] < self.lens.size[0]-4) &
                       (exact[..., 1] >= 4) & (exact[..., 1] < self.lens.size[1]-4))
            error = np.linalg.norm(exact-approx, axis=-1)
            if visible.any() and np.max(error[visible]) <= .02:
                result = cv2.warpAffine(sparse, np.array([[step, 0, 0], [0, step, 0]], np.float64), tuple(size), flags=cv2.INTER_LINEAR)
                self._grids[key] = result
                return result
        yy, xx = np.mgrid[:size[1], :size[0]].astype(np.float32)
        # Row chunks avoid a large temporary Newton working set.
        result = np.empty((*xx.shape, 2), np.float32)
        for start in range(0, size[1], 128):
            points = np.stack((xx[start:start+128], yy[start:start+128]), -1)
            result[start:start+128] = self.inverse(points) if inverse else self.forward(points)
        self._grids[key] = result
        return result

    def pull(self, field, size, chroma=False, nearest=False):
        if chroma:
            size = (size[0]//2, size[1]//2)
            key = (tuple(size), 'chroma')
            if key not in self._grids:
                coords = np.empty((size[1], size[0], 2), np.float32)
                for start in range(0, size[1], 128):
                    yy, xx = np.mgrid[start:min(start+128, size[1]), :size[0]].astype(np.float32)
                    coords[start:start+128] = (self.forward(np.stack((xx*2+.5, yy*2+.5), -1))-.5)/2
                self._grids[key] = coords
            coords = self._grids[key]
        else:
            coords = self.grid(size)
        return cv2.remap(field, coords[..., 0].astype(np.float32), coords[..., 1].astype(np.float32),
                         cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR)


def features(image, maximum=3000):
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    detector = cv2.SIFT_create(nfeatures=maximum, contrastThreshold=.015)
    points, descriptors = detector.detectAndCompute(gray, None)
    return np.array([p.pt for p in points]), descriptors


def matches(reference, observed, mapping, radius=60, maximum=250):
    """Descriptor matches with a geometric gate; no dense brightness fitting."""
    a, da = reference; b, db = observed
    if da is None or db is None:
        return np.empty((0, 2)), np.empty((0, 2))
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    selected = [p for pair in pairs if len(pair) == 2 for p, q in [pair] if p.distance < .72*q.distance]
    if not selected:
        return np.empty((0, 2)), np.empty((0, 2))
    source = a[[p.queryIdx for p in selected]]
    target = b[[p.trainIdx for p in selected]]
    distance = np.linalg.norm(mapping.forward(source)-target, axis=1)
    keep = np.flatnonzero(distance < radius)
    # Spatially spread matches rather than selecting one highly textured tile.
    keep = sorted(keep, key=lambda n: selected[n].distance)
    used, accepted = set(), []
    for n in keep:
        cell = tuple((target[n]//64).astype(int))
        if cell not in used:
            accepted.append(n); used.add(cell)
        if len(accepted) >= maximum:
            break
    return source[accepted], target[accepted]


def refine_plane(mapping, source, target, threshold=2.):
    """Independent per-shot homography with a fixed burst lens."""
    ideal = mapping.lens.undistort(target)
    h, mask = cv2.findHomography(np.asarray(source), ideal, cv2.RANSAC, threshold/mapping.lens.scale)
    if h is None or mask.sum() < 8:
        raise ValueError('insufficient lens-corrected plane feature inliers')
    result = PlaneMap(mapping.lens, h)
    errors = np.linalg.norm(result.forward(source)-target, axis=1)
    return result, errors, mask.ravel().astype(bool)


def fit_burst(pairs, size, initial=None, iterations=50):
    """One lens per eye, an independent homography for every supplied plane."""
    targets = np.concatenate([b for _, b in pairs]).astype(np.float32)
    span = np.ptp(targets, axis=0)/size
    hull = cv2.contourArea(cv2.convexHull(targets))/np.prod(size)
    # A marker column cannot identify radial, tangential and optical-centre
    # terms. Coverage is decided before optimizing, using training landmarks.
    count = 7 if hull >= .12 and min(span) >= .35 else 2 if hull >= .04 and min(span) >= .2 else 0
    while True:
        try:
            return _fit_burst(pairs, size, initial, iterations, count, hull)
        except (ValueError, np.linalg.LinAlgError):
            if count == 0:
                raise
            count = 2 if count == 7 else 0


def _fit_burst(pairs, size, initial, iterations, count, hull):
    lens = Lens(size)
    if initial is not None:
        lens.coefficients[:count] = np.asarray(initial)[:count]
    normalized, matrices, norms = [], [], []
    for source, target in pairs:
        centre = np.mean(source, axis=0)
        scale = max(np.ptp(source, axis=0))/2
        norm = np.array([[1/scale, 0, -centre[0]/scale], [0, 1/scale, -centre[1]/scale], [0, 0, 1.]])
        src = project(source, norm)
        h, _ = cv2.findHomography(src, lens.undistort(target), 0)
        if h is None:
            raise ValueError('degenerate lens landmarks')
        normalized.append((src, target)); matrices.append((h/h[2, 2]).ravel()[:8]); norms.append(norm)
    def errors(params):
        residuals = []
        for n, (source, target) in enumerate(normalized):
            h = np.r_[params[count+n*8:count+(n+1)*8], 1].reshape(3, 3)
            coefficients = np.pad(params[:count], (0, 7-count))
            residuals.append((project(source, h)-lens.undistort(target, coefficients)).ravel())
        return np.concatenate(residuals)*lens.scale
    result = least_squares(errors, np.r_[lens.coefficients[:count], np.concatenate(matrices)], iterations, robust=2.)
    # Remove the homography nuisance directions before testing lens rank.
    r = errors(result)
    jacobian = []
    for n in range(len(result)):
        step = 1e-5*max(1, abs(result[n]))
        candidate = result.copy(); candidate[n] += step
        jacobian.append((errors(candidate)-r)/step)
    j = np.array(jacobian).T
    condition = 1.
    if count:
        residual_j = j[:, :count]-j[:, count:] @ np.linalg.lstsq(j[:, count:], j[:, :count], rcond=None)[0]
        singular = np.linalg.svd(residual_j, compute_uv=False)
        condition = float(singular[0]/max(singular[-1], 1e-15))
        if condition > 1e5 or singular[-1] < .01:
            raise ValueError('lens training landmarks do not identify model')
    lens.coefficients = np.pad(result[:count], (0, 7-count))
    lens.check_injective()
    maps = [PlaneMap(lens, np.r_[result[count+n*8:count+(n+1)*8], 1].reshape(3, 3) @ norm) for n, norm in enumerate(norms)]
    diagnostics = []
    for mapping, (source, target) in zip(maps, pairs):
        e = np.linalg.norm(mapping.forward(source)-target, axis=1)
        diagnostics.append({'corner_fit_rms_capture_px': float(np.sqrt(np.mean(e*e))),
                            'corner_max_capture_px': float(e.max()), 'landmarks': len(e),
                            'lens_parameters': count, 'lens_condition': condition, 'training_hull_fraction': float(hull)})
    return maps, diagnostics


def spatial_split(source, size):
    """Reserve fixed spatial cells before any model fitting or selection."""
    cells = np.floor(np.asarray(source)/np.asarray(size)*12).astype(int)
    return (cells[:, 0]+2*cells[:, 1]) % 3 == 0


def validate_plane(mapping, source, target, footprint):
    """Independent holdouts, including local tails in every scored 4x4 cell."""
    source, target = np.asarray(source), np.asarray(target)
    size = np.array(footprint.shape[::-1])
    inside = np.all((source >= 0) & (source < size-1), axis=1)
    source, target = source[inside], target[inside]
    positions = np.rint(source).astype(int)
    inside = footprint[positions[:, 1], positions[:, 0]]
    source, target = source[inside], target[inside]
    error = np.linalg.norm(mapping.forward(source)-target, axis=1)
    cells = np.clip((np.asarray(source)/size*4).astype(int), 0, 3)
    yy, xx = np.nonzero(footprint)
    required = set(map(tuple, np.c_[xx*4//size[0], yy*4//size[1]]))
    local = []
    for cell in sorted(required):
        values = error[np.all(cells == cell, axis=1)]
        median = float(np.median(values)) if len(values) else None
        p95 = float(np.percentile(values, 95)) if len(values) else None
        local.append({'cell': [int(v) for v in cell], 'n': len(values), 'median_px': median, 'p95_px': p95,
                      'valid': len(values) >= 3 and median <= .1 and p95 <= .25})
    median = float(np.median(error)) if len(error) else None
    p95 = float(np.percentile(error, 95)) if len(error) else None
    return {'held_out_median_px': median, 'held_out_p95_px': p95,
            'local': local, 'scores_available': bool(local) and median is not None and
            median <= .1 and p95 <= .25 and all(c['valid'] for c in local)}


def barcode_index(capture, mapping, scene, shot):
    """Decode visible Manchester pairs, including a uniquely constrained crop.

    A partial barcode must match exactly one pose-log packet within the shot's
    wall-clock interval (+/-2 s for capture/stream latency). It must retain
    at least 8 CRC bits and 28 total bits. Timestamps alone never identify truth.
    """
    from tools.quest3.bench_scene import barcode_bits
    x, y, w, h = scene.barcode_box
    yy, xx = np.mgrid[:4, :28]
    points = np.stack((x+(xx+.5)*w/28, y+(yy+.5)*h/4), -1)
    sampled = []
    for dy, dx in ((0, 0), (-.15, -.15), (.15, -.15), (-.15, .15), (.15, .15)):
        q = mapping.forward(points + [dx*w/28, dy*h/4]).astype(np.float32)
        sampled.append(cv2.remap(capture.astype(np.float32).mean(axis=2), q[..., 0], q[..., 1], cv2.INTER_LINEAR))
    cells = np.median(sampled, axis=0).reshape(56, 2)
    visible = np.abs(cells[:, 0]-cells[:, 1]) >= 35
    bits = cells[:, 0] > cells[:, 1]
    if visible.all():
        import binascii
        packet = np.packbits(bits).tobytes()
        if packet[0] == 0xd3 and binascii.crc_hqx(packet[:5], 0xffff) == int.from_bytes(packet[5:], 'big'):
            index = int.from_bytes(packet[1:5], 'big')
            scene.homography(index)  # require a recorded pose for live scenes
            return index, {'barcode_bits': 56, 'partial_barcode': False}
    if visible.sum() < 28 or visible[40:].sum() < 8 or 'start_s' not in shot:
        raise ValueError(f'barcode clipped/damaged: {visible.sum()}/56 bits, {visible[40:].sum()}/16 CRC bits; frame identity unavailable')
    start = shot['start_s']-2
    end = shot['start_s']+shot.get('seconds', 0)+2
    candidates = []
    for index, record in scene.frame_records.items():
        timestamp = record.get('render_unix_ns', 0)/1e9
        if start <= timestamp <= end:
            expected = barcode_bits(index).reshape(56, 2)[:, 0]
            if np.array_equal(expected[visible], bits[visible]):
                candidates.append(index)
    if len(candidates) != 1:
        raise ValueError(f'partial barcode ambiguous: {len(candidates)} logged candidates, {visible.sum()}/56 bits')
    return candidates[0], {'barcode_bits': int(visible.sum()), 'partial_barcode': True,
                           'barcode_crc_bits': int(visible[40:].sum()), 'timestamp_window_s': [start, end]}

"""Deterministic world-locked planar stereo benchmark, CPU geometry and replay.

OpenVR is right-handed, +Y up, forward -Z. Homographies use top-left image
coordinates with integer pixel centres. See ws/BENCH-SCENE.md for filter limits.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

REFERENCE_SIZE = (2624, 2752)
PERIOD = 900
FPS = 90
LEGEND = {0: 'frame', 1: 'sat', 2: 'mura', 3: 'edge', 4: 'natural'}
MOTIONS = ('none', 'mix', 'static', 'tremor', 'jitter', 'pan', 'turn')
VERSION = 4
# V3's default renderer is preserved byte-for-byte by the default branch.
# Only this audited predecessor is accepted, never an arbitrary hash bypass.
V3_RENDERER = '669fdf30c06f6d1b2df38cd53d8396e4c7cdb0aa41d2264730fbe6c46ff801bb'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def asset_manifest(value=None):
    """Directories discover private images/dumps; manifests freeze selection + crops.

    No implicit access to Steam or captures. Point --bench-assets at their parent,
    or supply {"assets": [{"path": ..., "sha256": ..., "crop": [x,y,w,h]}]}.
    """
    if value is None:
        return {'assets': [], 'fallback': 'seeded-fractal-photo-v1'}
    path = Path(value).resolve()
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        entries = data['assets']
        base = path.parent
    elif path.is_dir():
        candidates = sorted(p for p in path.rglob('*') if p.is_file() and
                            (p.suffix.lower() in ('.png', '.jpg', '.jpeg') or
                             p.name.endswith('-encoder_input.raw')))
        if any(p.name == 'library_600x900.jpg' for p in candidates):
            candidates = [p for p in candidates if p.name == 'library_600x900.jpg' or p.suffix == '.raw']
        # Read one image at a time. Stable saturation ranking, path as tie breaker.
        ranked = []
        for p in candidates:
            if p.suffix == '.raw':
                ranked.append((0., str(p), p))
            else:
                rgb = cv2.imread(str(p))
                if rgb is not None:
                    small = cv2.resize(rgb, (60, 90), interpolation=cv2.INTER_AREA)
                    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
                    ranked.append((-float((hsv[..., 1] * (hsv[..., 2] > 60)).mean()), str(p), p))
        # Include both kinds if present, instead of letting covers exclude dumps.
        covers = [p for _, _, p in sorted(ranked) if p.suffix != '.raw'][:10]
        dumps = [p for _, _, p in sorted(ranked) if p.suffix == '.raw'][:2]
        entries = [{'path': str(p)} for p in covers + dumps]
        base = path
    else:
        raise ValueError(f'asset path does not exist: {path}')
    result = []
    for entry in entries:
        p = (base / entry['path']).resolve()
        digest = sha256(p)
        if entry.get('sha256', digest) != digest:
            raise ValueError(f'asset hash changed: {p}')
        item = {**entry, 'path': str(p), 'sha256': digest}
        if p.suffix == '.raw':
            item['metadata_sha256'] = sha256(p.with_suffix('.json'))
            if entry.get('metadata_sha256', item['metadata_sha256']) != item['metadata_sha256']:
                raise ValueError(f'asset metadata changed: {p}')
        result.append(item)
    return {'assets': result, 'fallback': None if result else 'seeded-fractal-photo-v1'}


def load_asset(entry):
    path = Path(entry['path'])
    if entry.get('sha256') != sha256(path):
        raise ValueError(f'asset hash changed: {path}')
    if path.suffix == '.raw':
        if entry.get('metadata_sha256') != sha256(path.with_suffix('.json')):
            raise ValueError(f'asset metadata changed: {path}')
        # Shared dump reader lives in the shipped scorer, never in a worktree.
        from tools.quest3.bench_score import read_dump, planes_to_rgb
        planes, _ = read_dump(path.with_suffix('.json'))
        rgb = np.clip(planes_to_rgb(planes), 0, 255).astype(np.uint8)
        if 'crop' not in entry:
            rgb = rgb[:, :rgb.shape[1] // 2]  # default Metro left-eye crop
    else:
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError(f'cannot decode asset: {path}')
        rgb = bgr[..., ::-1]
    if 'crop' in entry:
        x, y, w, h = entry['crop']
        if min(x, y) < 0 or min(w, h) <= 0 or x+w > rgb.shape[1] or y+h > rgb.shape[0]:
            raise ValueError(f'asset crop outside image: {path}')
        rgb = rgb[y:y+h, x:x+w]
    return rgb


def trajectory(seed=1, motion='mix', scale=1.0):
    """Local-camera yaw/pitch/roll in degrees and translation in metres."""
    if motion not in MOTIONS or not np.isfinite(scale) or not 0 <= scale <= 1:
        raise ValueError('supported motion and finite scale in [0,1] required')
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((PERIOD, 3))
    ar, state = np.zeros_like(noise), np.zeros(3)
    for i in range(3 * PERIOD):
        state = .9 * state + np.sqrt(1 - .9**2) * noise[i % PERIOD]
        ar[i % PERIOD] = state
    ar /= ar.std(axis=0)
    values = []
    segments = ('tremor', 'jitter', 'pan', 'turn', 'static')
    for i in range(PERIOD):
        segment = segments[i // 180] if motion == 'mix' else motion
        local = i % 180 if motion == 'mix' else i
        angles, translation = np.zeros(3), np.zeros(3)
        if segment in ('tremor', 'jitter'):
            amp = .035 if segment == 'tremor' else .2
            angles = ar[i] * [amp, amp, amp*.2]
            translation = ar[i] * (.00015 if segment == 'tremor' else .0008)
        elif segment == 'pan':
            angles[0] = 3 * (local if motion == 'mix' else min(local, PERIOD-local)) / FPS
            translation[0] = angles[0] * .001
        elif segment == 'turn':
            amount = .5 - .5 * np.cos(np.pi * min(local/36, 2.))
            angles = np.array([12., 1., .3]) * amount
            translation = np.array([.015, .002, .001]) * amount
        values.append({'index': i, 'segment': segment,
                       'degrees': (angles*scale).tolist(), 'metres': (translation*scale).tolist()})
    return values


def barcode_bits(index):
    if not 0 <= index < 2**32:
        raise ValueError('barcode index outside uint32')
    payload = b'\xd3' + int(index).to_bytes(4, 'big')
    packet = payload + binascii.crc_hqx(payload, 0xffff).to_bytes(2, 'big')
    bits = np.unpackbits(np.frombuffer(packet, np.uint8))
    return np.stack((bits, 1-bits), axis=1).reshape(4, 28)


def decode_barcode(rgb, box):
    x, y, w, h = box
    gray = rgb[y:y+h, x:x+w].astype(np.float32).mean(axis=2)
    if gray.shape != (h, w):
        raise ValueError('barcode outside image')
    cells = []
    for row in range(4):
        for col in range(28):
            x0, x1 = round((col+.25)*w/28), round((col+.75)*w/28)
            y0, y1 = round((row+.25)*h/4), round((row+.75)*h/4)
            cells.append(float(np.median(gray[y0:y1, x0:x1])))
    pairs = np.asarray(cells).reshape(-1, 2)
    if np.min(np.abs(pairs[:, 0] - pairs[:, 1])) < 35:
        raise ValueError('barcode low contrast or damaged Manchester pair')
    packet = np.packbits(pairs[:, 0] > pairs[:, 1]).tobytes()
    index = int.from_bytes(packet[1:5], 'big')
    if packet[0] != 0xd3 or binascii.crc_hqx(packet[:5], 0xffff) != int.from_bytes(packet[5:], 'big'):
        raise ValueError('barcode checksum/magic/index mismatch')
    return index


def fractal_photo(rng, width, height):
    image = np.zeros((height, width, 3), np.float32)
    for n, weight in ((3, 95), (8, 55), (24, 28), (64, 14), (160, 7)):
        noise = rng.random((n, n, 3), dtype=np.float32)
        image += weight * cv2.resize(noise, (width, height), interpolation=cv2.INTER_CUBIC)
    return np.clip(image, 0, 255).astype(np.uint8)


# Physical panel and deterministic filtering shared with the OpenGL renderer.
DISTANCE = 1.5
PANEL_WIDTH = 2 * DISTANCE * np.tan(np.deg2rad(65/2))
PANEL_HEIGHT = PANEL_WIDTH * .625
SURROUND = 28
SUPERSAMPLE = 1.5
NEAR, FAR = .05, 100.


def pose_matrix(value):
    matrix = np.eye(4)
    matrix[:3, :4] = np.asarray(value, np.float64).reshape(3, 4)
    return matrix


def offset_matrix(offset):
    yaw, pitch, roll = np.deg2rad(offset['degrees'])
    cy, sy, cp, sp, cr, sr = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch), np.cos(roll), np.sin(roll)
    m = np.eye(4)
    m[:3, :3] = (np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @
                 np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @
                 np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]]))
    m[:3, 3] = offset['metres']
    return m


def panel_anchor(initial_pose):
    # OpenVR: right-handed, +Y up, forward -Z. Discard initial pitch/roll.
    forward = -initial_pose[:3, 2].copy()
    forward[1] = 0
    length = np.linalg.norm(forward)
    if length < 1e-6:
        raise ValueError('initial HMD forward direction is vertical; cannot anchor yaw')
    forward /= length
    anchor = np.eye(4)
    anchor[:3, 0] = np.cross(forward, [0, 1, 0])
    anchor[:3, 2] = -forward
    anchor[:3, 3] = initial_pose[:3, 3] + DISTANCE * forward
    return anchor


def projection_raw(raw):
    left, right, top, bottom = raw  # OpenVR top tangent is negative.
    return np.array([[2/(right-left), 0, (right+left)/(right-left), 0],
                     [0, 2/(bottom-top), -(bottom+top)/(bottom-top), 0],
                     [0, 0, -(FAR+NEAR)/(FAR-NEAR), -2*FAR*NEAR/(FAR-NEAR)],
                     [0, 0, -1, 0]], np.float64)


def resize_homography(source, target):
    sx, sy = np.asarray(target) / source
    return np.array([[sx, 0, (sx-1)/2], [0, sy, (sy-1)/2], [0, 0, 1.]])


def panel_homography(vp, anchor, panel_size, eye_size, metres=(PANEL_WIDTH, PANEL_HEIGHT)):
    # Texture centres -> local plane. Top of texture is positive world Y.
    w, h = panel_size
    width, height = metres
    plane = np.array([[width/w, 0, width*(.5/w-.5)],
                      [0, -height/h, height*(.5-.5/h)],
                      [0, 0, 0], [0, 0, 1.]])
    clip = vp @ anchor @ plane
    ew, eh = eye_size
    viewport = np.array([[ew/2, 0, (ew-1)/2], [0, -eh/2, (eh-1)/2], [0, 0, 1.]])
    result = viewport @ clip[[0, 1, 3]]
    return result  # retain clip-W scale/sign for CPU near/far clipping


def mip_chain(image):
    levels = [image.astype(np.float32)]
    while min(levels[-1].shape[:2]) > 1:
        h, w = levels[-1].shape[:2]
        levels.append(np.rint(cv2.resize(levels[-1], (max(1, w//2), max(1, h//2)), interpolation=cv2.INTER_AREA)))
    return levels


def filtered_warp(levels, homography, size, return_mask=False, interpolation=cv2.INTER_LINEAR):
    """Projective bilinear/trilinear sample, analytic GL-style isotropic LOD.

    Explicit mips are also uploaded to GL. OpenCV fractions are 1/32 pixel;
    hardware derivatives/LOD and final resolve may differ slightly. RGB codes,
    no sRGB framebuffer conversion, matching the live GL_RGBA8 pipeline.
    """
    inverse = np.linalg.inv(homography)
    yy, xx = np.mgrid[:size[1], :size[0]].astype(np.float32)
    den = inverse[2, 0]*xx + inverse[2, 1]*yy + inverse[2, 2]
    u = (inverse[0, 0]*xx + inverse[0, 1]*yy + inverse[0, 2])/den
    v = (inverse[1, 0]*xx + inverse[1, 1]*yy + inverse[1, 2])/den
    dx = np.hypot(inverse[0, 0]-u*inverse[2, 0], inverse[1, 0]-v*inverse[2, 0])/np.abs(den)
    dy = np.hypot(inverse[0, 1]-u*inverse[2, 1], inverse[1, 1]-v*inverse[2, 1])/np.abs(den)
    lod = np.clip(np.log2(np.maximum(np.maximum(dx, dy), 1)), 0, len(levels)-1)
    low = np.floor(lod).astype(np.int16)
    result = np.zeros((*xx.shape, 3), np.float32)
    for n in range(int(low.min()), min(len(levels), int(low.max())+2)):
        weight = np.maximum(1-np.abs(lod-n), 0)
        if not weight.any():
            continue
        level = levels[n]
        sx, sy = level.shape[1]/levels[0].shape[1], level.shape[0]/levels[0].shape[0]
        sample = cv2.remap(level.astype(np.float32, copy=False), ((u+.5)*sx-.5).astype(np.float32), ((v+.5)*sy-.5).astype(np.float32),
                           interpolation, borderMode=cv2.BORDER_REPLICATE)
        result += sample * weight[..., None]
    h, w = levels[0].shape[:2]
    inside = (u >= -.5) & (u < w-.5) & (v >= -.5) & (v < h-.5) & (den >= 1/FAR) & (den <= 1/NEAR)
    result[~inside] = SURROUND
    return (result, inside) if return_mask else result


def plane_mask(shape, homography, size):
    mask = cv2.warpPerspective(np.ones(shape,np.uint8),homography,size,flags=cv2.INTER_NEAREST).astype(bool)
    inverse = np.linalg.inv(homography)
    yy,xx = np.ogrid[:size[1],:size[0]]
    inverse_depth = inverse[2,0]*xx+inverse[2,1]*yy+inverse[2,2]
    return mask & (inverse_depth >= 1/FAR) & (inverse_depth <= 1/NEAR)


class BenchScene:
    def __init__(self, seed=1, size=REFERENCE_SIZE, motion='mix', scale=1., assets=None, manifest=None,
                 layout='cards', panel_size=None, projections=None, eye_to_head=None, anchor=None,
                 backdrop='none', backdrop_asset=None, backdrop_manifest=None, backdrop_fov=None, panel='on', backdrop_filter='default'):
        self.seed, self.size, self.motion, self.scale, self.layout = seed, tuple(size), motion, scale, layout
        if backdrop_filter not in ('default', 'ss4', 'cubic4'):
            raise ValueError('backdrop filter must be default, ss4 or cubic4')
        self.backdrop_filter = backdrop_filter
        if min(self.size) < 384 or any(v % 2 for v in self.size) or layout not in ('cards', 'metro'):
            raise ValueError('even eye dimensions >=384 and cards/metro layout required')
        self.projections = np.array(projections if projections is not None else [projection_raw((-1, 1, -1, 1))]*2)
        self.eye_to_head = np.array(eye_to_head if eye_to_head is not None else [np.eye(4), np.eye(4)])
        if eye_to_head is None:
            self.eye_to_head[:, 0, 3] = [-.032, .032]
        self.anchor = np.array(anchor if anchor is not None else panel_anchor(np.eye(4)))
        # Freeze the panel raster at reference-stream density across 2624/3072 sources.
        # 1.25 texels/native pixel at 2624, about 1.07 at 3072, both in range.
        projected = [min(self.size[n], REFERENCE_SIZE[n])*abs(self.projections[0, n, n])*(PANEL_WIDTH, PANEL_HEIGHT)[n]/(2*DISTANCE) for n in (0, 1)]
        self.panel_size = tuple(panel_size or [max(128, 2*round(v*1.25/2)) for v in projected])
        self.manifest = manifest if manifest is not None else asset_manifest(assets)
        self.trajectory = trajectory(seed, motion, scale)
        from tools.quest3.bench_backdrop import Backdrop, backdrop_manifest as freeze
        self.backdrop_kind = backdrop or ('metro' if backdrop_asset or backdrop_manifest else 'mosaic')
        if self.backdrop_kind not in ('none', 'mosaic', 'metro') or panel not in ('on','off'):
            raise ValueError('invalid backdrop/panel mode')
        if panel == 'off' and self.backdrop_kind == 'none':
            raise ValueError('--bench-panel off requires a backdrop')
        self.panel_mode = panel
        self.backdrop = (Backdrop(self, self.backdrop_kind, backdrop_manifest or (freeze(backdrop_asset) if backdrop_asset else None), backdrop_fov)
                         if self.backdrop_kind != 'none' else None)
        self.content_anchor = self.anchor.copy()
        self.panel_metres = [PANEL_WIDTH, PANEL_HEIGHT]
        if panel == 'on':
            self.panel, self.panel_labels = self._content()
            self.static, self.fiducials, self.calibration, self.barcode_box = self._border()
        else:
            self._backdrop_strip()
        mask = self.static[..., 3] != 0
        self.panel[mask] = self.static[mask, :3]
        self.panel_labels[mask] = 0
        self.mips = mip_chain(self.panel)
        self.frame_records = {}
        self.live = False
        self._yaw_mismatch_since = None

    def recenter(self, real_pose, reason):
        new = panel_anchor(np.asarray(real_pose))
        delta = new @ np.linalg.inv(self.anchor)
        self.content_anchor = delta @ self.content_anchor
        if self.backdrop:
            self.backdrop.anchor = delta @ self.backdrop.anchor
        self.anchor = new
        self._yaw_mismatch_since = None
        return {'reason': reason, 'anchor': new.tolist(), 'content_anchor': self.content_anchor.tolist(),
                'backdrop_anchor': self.backdrop.anchor.tolist() if self.backdrop else None}

    def tracking_lost(self):
        # The automatic startup recenter needs a continuous mismatch; an
        # invalid/skipped pose breaks the run, so the pending timer restarts.
        self._yaw_mismatch_since = None

    def maybe_recenter(self, real_pose, elapsed, request=None):
        # File consumption is edge-triggered: a second touch requests another
        # recenter. Automatic correction is confined to this bench's startup.
        if request is not None and Path(request).is_file():
            event = self.recenter(real_pose, 'file')
            Path(request).unlink()
            return event
        if elapsed >= 10:
            self._yaw_mismatch_since = None
            return None
        forward = -np.asarray(real_pose)[[0, 2], 2]
        length = np.linalg.norm(forward)
        if length < 1e-6:
            self._yaw_mismatch_since = None
            return None
        angle = np.rad2deg(np.arccos(np.clip(np.dot(forward/length, -self.anchor[[0, 2], 2]), -1, 1)))
        if angle <= 60:
            self._yaw_mismatch_since = None
        elif self._yaw_mismatch_since is None:
            self._yaw_mismatch_since = elapsed
        elif elapsed-self._yaw_mismatch_since > 2:
            return self.recenter(real_pose, 'startup_yaw')
        return None

    def _backdrop_strip(self):
        # A narrow reference strip on the same 3 m plane, below -30 degrees.
        # Its own pixel coordinates remain the registration/barcode API.
        b = self.backdrop
        width = 3.2
        top = -3*np.tan(np.deg2rad(32))
        height = .65
        self.content_anchor = self.anchor.copy()
        self.content_anchor[:3,3] += self.anchor[:3,:3] @ [0,top-height/2,-1.5]
        self.panel_metres = [width,height]
        density = b.size[0]/b.metres[0]
        self.panel_size = (max(448,2*round(width*density/2)), max(112,2*round(height*density/2)))
        w,h = self.panel_size
        self.panel = np.full((h,w,3),SURROUND,np.uint8)
        self.panel_labels = np.zeros((h,w),np.uint8)
        self.static = np.full((h,w,4),SURROUND,np.uint8); self.static[...,3] = 255
        self.fiducials, self.calibration = [], []
        side = h//3
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        for ident,(x,y) in enumerate(((side//3,side//3),(w-side*4//3,side//3),
                                     (side//3,h-side*4//3),(w-side*4//3,h-side*4//3))):
            pad = max(3,side//8)
            self.static[y-pad:y+side+pad,x-pad:x+side+pad] = (245,245,245,255)
            self.static[y:y+side,x:x+side,:3] = cv2.aruco.generateImageMarker(dictionary,ident,side)[...,None]
            self.fiducials.append({'id':ident,'corners':[[x-.5,y-.5],[x+side-.5,y-.5],[x+side-.5,y+side-.5],[x-.5,y+side-.5]]})
        cw, ch = (w-4*side)//28, max(3,h//12)
        self.barcode_box = ((w-28*cw)//2,h//10,28*cw,4*ch)
        # Exactly the v2 calibration colours; keep independent held-out patches.
        colours = [(v,v,v) for v in (16,32,64,96,144,192,232)] + [
            (180,95,45),(45,165,80),(70,95,190),(170,70,150),(75,160,175),(180,160,70),
            (130,80,50),(50,125,75),(65,85,140),(125,65,110),(65,120,130),(135,120,65),(230,90,20),(255,140,0)]
        step = (w-4*side)//len(colours)
        for i,colour in enumerate(colours):
            x,y,pw,ph = 2*side+i*step,h*3//5,step-1,h//4
            self.static[y:y+ph,x:x+pw] = (*colour,255)
            self.calibration.append({'rgb':list(colour),'box':[x,y,pw,ph]})

    def _content(self):
        w, h = self.panel_size
        rng = np.random.default_rng(self.seed)
        image = np.full((h, w, 3), SURROUND, np.uint8)
        labels = np.zeros((h, w), np.uint8)
        def box(x0, y0, x1, y1):
            return round(x0*w), round(y0*h), round(x1*w), round(y1*h)
        def photo(i, rect):
            x0, y0, x1, y1 = box(*rect)
            entries = self.manifest['assets']
            asset = load_asset(entries[i % len(entries)]) if entries else fractal_photo(rng, x1-x0, y1-y0)
            image[y0:y1, x0:x1] = cv2.resize(asset, (x1-x0, y1-y0), interpolation=cv2.INTER_AREA)
            labels[y0:y1, x0:x1] = 4
        if self.layout == 'metro':
            photo(0, (.10, .17, .90, .75))
            probe_top = .77
        else:
            for i in range(10):
                x, y = .10 + (i % 5)*.162, .17 + (i//5)*.195
                photo(i, (x, y, x+.15, y+.18))
            probe_top = .58
        bottom = .87
        colors = [(255, 140, 0), (230, 90, 20), (230, 30, 35), (30, 220, 45), (30, 65, 240)]
        for i, color in enumerate(colors):
            x0, y0, x1, y1 = box(.10+i*.044, probe_top, .10+(i+1)*.044, bottom)
            image[y0:y1, x0:x1] = color
            if i % 2:
                image[y0:y1, x0:x1] = np.clip(image[y0:y1, x0:x1].astype(np.int16)+rng.integers(-4, 5, (y1-y0, x1-x0, 1)), 0, 255)
            labels[y0:y1, x0:x1] = 1
        x0, y0, x1, y1 = box(.34, probe_top, .63, bottom)
        yy, xx = np.mgrid[:y1-y0, :x1-x0]
        base = 18+22*xx/max(1, x1-x0)+2*np.sin(xx/16)*np.cos(yy/24)
        image[y0:y1, x0:x1] = np.stack((base*.85, base, base*1.2), -1)
        labels[y0:y1, x0:x1] = 2
        x0, y0, x1, y1 = box(.65, probe_top, .90, bottom)
        labels[y0:y1, x0:x1] = 3
        for i, angle in enumerate((0, 2, 15, 30, 45, 87)):
            x = x0+int((i+.5)*(x1-x0)/6)
            cy = y0+int((y1-y0)*.25)
            length = max(8, (x1-x0)//14)
            dx, dy = int(length*np.cos(np.deg2rad(angle))), int(length*np.sin(np.deg2rad(angle)))
            cv2.line(image, (x-dx, cy-dy), (x+dx, cy+dy), (240, 240, 240), 1+i%2, cv2.LINE_AA)
        for i, text in enumerate(('Library / MENU', '012345 AaBb')):
            cv2.putText(image, text, (x0+3, y0+int((.6+.25*i)*(y1-y0))), cv2.FONT_HERSHEY_SIMPLEX,
                        max(.25, w/2300), (240, 180, 100), 1, cv2.LINE_AA)
        return image, labels

    def _border(self):
        w, h = self.panel_size
        image = np.zeros((h, w, 4), np.uint8)
        bx, by = round(w*.09), round(h*.15)
        image[:by] = image[h-round(h*.11):] = (SURROUND, SURROUND, SURROUND, 255)
        image[:, :bx] = image[:, w-bx:] = (SURROUND, SURROUND, SURROUND, 255)
        side = max(20, round(min(w*.055, h*.10)))
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        fiducials = []
        for ident, (cx, cy) in enumerate(((bx/2, by/2), (w-bx/2, by/2), (w-bx/2, h-by/2), (bx/2, h-by/2),
                                          (bx/2, h*.38), (w-bx/2, h*.38), (bx/2, h*.67), (w-bx/2, h*.67))):
            x, y = round(cx-side/2), round(cy-side/2)
            pad = max(3, side//8)
            image[y-pad:y+side+pad, x-pad:x+side+pad] = (245, 245, 245, 255)
            image[y:y+side, x:x+side, :3] = cv2.aruco.generateImageMarker(dictionary, ident, side)[..., None]
            fiducials.append({'id': ident, 'corners': [[x-.5,y-.5],[x+side-.5,y-.5],[x+side-.5,y+side-.5],[x-.5,y+side-.5]]})
        cw, ch = max(3, int(w*.66/28)), max(3, int(h*.11/4))
        barcode = ((w-28*cw)//2, (by-4*ch)//2, 28*cw, 4*ch)
        colors = [(v, v, v) for v in (16, 32, 64, 96, 144, 192, 232)] + [
            (180,95,45), (45,165,80), (70,95,190), (170,70,150), (75,160,175),
            (180,160,70), (130,80,50), (50,125,75), (65,85,140), (125,65,110),
            (65,120,130), (135,120,65), (230,90,20), (255,140,0)]
        calibration = []
        step = (w-2*bx)//len(colors)
        for i, color in enumerate(colors):
            x, y, pw, ph = bx+i*step+1, h-round(h*.09), step-2, max(8, round(h*.065))
            image[y:y+ph, x:x+pw] = (*color, 255)
            calibration.append({'rgb': list(color), 'box': [x,y,pw,ph]})
        return image, fiducials, calibration, barcode

    def barcode_patch(self, index):
        _, _, w, h = self.barcode_box
        gray = cv2.resize((20+215*barcode_bits(index)).astype(np.uint8), (w,h), interpolation=cv2.INTER_NEAREST)
        return np.repeat(gray[..., None], 3, axis=2)

    def panel_frame(self, index):
        image = self.panel.copy()
        x,y,w,h = self.barcode_box
        image[y:y+h,x:x+w] = self.barcode_patch(index)
        return image

    def frame_geometry(self, index, real_pose=None):
        real = np.eye(4) if real_pose is None else np.asarray(real_pose)
        offset = self.trajectory[index % PERIOD]
        camera = real @ offset_matrix(offset)
        eyes = []
        for projection, eye_pose in zip(self.projections, self.eye_to_head):
            vp = projection @ np.linalg.inv(camera @ eye_pose)
            entry = {'view_projection': vp.tolist(), 'panel_to_eye': panel_homography(vp, self.content_anchor, self.panel_size, self.size, self.panel_metres).tolist()}
            if self.backdrop:
                b = self.backdrop
                entry['backdrop_to_eye'] = panel_homography(vp,b.anchor,b.size,self.size,b.metres).tolist()
            eyes.append(entry)
        return {'frame': index, 'index': index % PERIOD, 'real_pose': real.tolist(),
                'synthetic_offset': offset, 'eyes': eyes}

    def homography(self, index, eye='left', plane='panel'):
        record = self.frame_records.get(index)
        if record is None:
            if self.live:
                raise ValueError(f'no render-pose log for barcode {index}')
            record = self.frame_geometry(index)
        return np.array(record['eyes'][int(eye == 'right')][plane+'_to_eye'])

    def render_frame(self, index, eye='left', homography=None):
        if self.backdrop_filter != 'default':
            return self._render_ss4(index, eye, homography)
        h = self.homography(index, eye) if homography is None else homography
        large = tuple(round(v*SUPERSAMPLE) for v in self.size)
        transform = resize_homography(self.size, large) @ h
        if self.backdrop:
            backdrop_h = self.homography(index,eye,'backdrop')
            if homography is not None:
                backdrop_h = h @ np.linalg.inv(self.homography(index,eye)) @ backdrop_h
            image = filtered_warp(self.backdrop.mips, resize_homography(self.size,large) @ backdrop_h, large)
            foreground, visible = filtered_warp(self.mips, transform, large, return_mask=True)
            image[visible] = foreground[visible]
        else:
            image = filtered_warp(self.mips, transform, large)
        # Non-mipmapped coplanar barcode, drawn with the same perspective.
        x,y,w,bh = self.barcode_box
        offset = np.array([[1,0,x],[0,1,y],[0,0,1.]])
        patch = filtered_warp([self.barcode_patch(index).astype(np.float32)], transform @ offset, large)
        mask = plane_mask((bh,w), transform @ offset, large)  # depth-aware: GL clips a plane behind the camera
        image[mask] = patch[mask]
        # RGBA8 supersampled FBO quantizes before GL_LINEAR resolve.
        return np.rint(cv2.resize(np.rint(image).astype(np.uint8), self.size, interpolation=cv2.INTER_LINEAR)).astype(np.uint8)

    def _render_ss4(self, index, eye, homography=None):
        """4x RGBA8 FBO, two 2:1 linear resolves; tiled CPU working set.

        Both planes share this FBO so silhouettes and occlusion have exactly
        the same filter. The opt-in changes foreground sampling too.
        """
        h = self.homography(index, eye) if homography is None else homography
        large = tuple(v*4 for v in self.size)
        panel_h = resize_homography(self.size, large) @ h
        if self.backdrop:
            back_h = self.homography(index, eye, 'backdrop')
            if homography is not None:
                back_h = h @ np.linalg.inv(self.homography(index, eye)) @ back_h
            back_h = resize_homography(self.size, large) @ back_h
        result = np.empty((self.size[1], self.size[0], 3), np.uint8)
        x, y, w, bh = self.barcode_box
        offset = np.array([[1, 0, x], [0, 1, y], [0, 0, 1.]])
        for start in range(0, self.size[1], 32):
            rows = min(32, self.size[1]-start)
            shift = np.array([[1, 0, 0], [0, 1, -start*4], [0, 0, 1.]])
            size = (large[0], rows*4)
            transform = shift @ panel_h
            foreground, visible = filtered_warp(self.mips, transform, size, return_mask=True)
            image = filtered_warp(self.backdrop.mips, shift @ back_h, size,
                                  interpolation=cv2.INTER_CUBIC if self.backdrop_filter == 'cubic4' else cv2.INTER_LINEAR) if self.backdrop else foreground
            image[visible] = foreground[visible]
            patch = filtered_warp([self.barcode_patch(index).astype(np.float32)], transform @ offset, size)
            mask = plane_mask((bh, w), transform @ offset, size)  # depth-aware, as the panel
            image[mask] = patch[mask]
            image = np.rint(np.clip(image, 0, 255)).astype(np.uint8)
            image = cv2.resize(image, (self.size[0]*2, rows*2), interpolation=cv2.INTER_LINEAR)
            result[start:start+rows] = cv2.resize(image, (self.size[0], rows), interpolation=cv2.INTER_LINEAR)
        return result

    def labels(self, index, eye='left'):
        labels = cv2.warpPerspective(self.panel_labels, self.homography(index, eye), self.size, flags=cv2.INTER_NEAREST)
        if self.backdrop:
            labels[~plane_mask(self.panel_labels.shape,self.homography(index,eye),self.size)] = 0
            visible = self.backdrop_visibility(index,eye)
            labels[visible] = 4
        return labels

    def backdrop_visibility(self, index, eye='left', size=None, transform=None):
        size = tuple(size or self.size)
        transform = resize_homography(self.size,size) if transform is None else transform
        visible = plane_mask(self.backdrop.image.shape[:2],transform @ self.homography(index,eye,'backdrop'),size)
        foreground = plane_mask(self.panel_labels.shape,transform @ self.homography(index,eye),size).astype(np.uint8)
        # Exclude the FBO resolve footprint at the occlusion boundary.
        return visible & ~cv2.dilate(foreground,np.ones((7,7),np.uint8)).astype(bool)

    def metadata(self):
        return {'version': VERSION, 'seed': self.seed, 'motion': self.motion, 'scale': self.scale, 'layout': self.layout,
                'period': PERIOD, 'fps': FPS, 'reference_size': list(REFERENCE_SIZE), 'size': list(self.size),
                'panel_size': list(self.panel_size), 'texels_per_source_pixel_centre': [self.panel_size[n]/(self.size[n]*abs(self.projections[0,n,n])*self.panel_metres[n]/(2*(DISTANCE if self.panel_mode == 'on' else 3))) for n in (0,1)], 'panel_metres': self.panel_metres, 'distance_m': DISTANCE if self.panel_mode == 'on' else 3.,
                'anchor': self.anchor.tolist(), 'projections': self.projections.tolist(), 'eye_to_head': self.eye_to_head.tolist(),
                'panel_mode': self.panel_mode, 'content_anchor': self.content_anchor.tolist(), 'content_metres': self.panel_metres,
                'backdrop': self.backdrop.metadata() if self.backdrop else None,
                'live': self.live, 'backdrop_filter': self.backdrop_filter, 'assets_manifest': self.manifest, 'legend': LEGEND, 'fiducials': self.fiducials,
                'barcode_box': self.barcode_box, 'calibration': self.calibration, 'supersample': SUPERSAMPLE if self.backdrop_filter == 'default' else 4,
                'filter': 'explicit area mip pyramid; trilinear isotropic LOD; 1.5x RGBA8 FBO; bilinear resolve; code-value filtering',
                'filter_override': None if self.backdrop_filter == 'default' else '4x RGBA8 FBO for both planes; two 2:1 bilinear resolves; '+('backdrop cubic A=-0.75 with explicit mip LOD' if self.backdrop_filter == 'cubic4' else 'trilinear textures'),
                'filter_shader_sha256': sha256(Path(__file__).with_name('bench_filter.py')) if self.backdrop_filter == 'cubic4' else None,
                'numpy': np.__version__, 'opencv': cv2.__version__, 'renderer_sha256': sha256(__file__),
                'backdrop_renderer_sha256': sha256(Path(__file__).with_name('bench_backdrop.py')),
                'trajectory_sha256': hashlib.sha256(json.dumps(self.trajectory, sort_keys=True).encode()).hexdigest()}

    def save(self, directory):
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        write_json(directory/'bench.json', self.metadata())
        write_json(directory/'assets.json', self.manifest)
        write_json(directory/'trajectory.json', self.trajectory)
        write_json(directory/'labels.json', LEGEND)
        cv2.imwrite(str(directory/'reference.png'), self.render_frame(0)[..., ::-1])
        cv2.imwrite(str(directory/'panel.png'), self.panel_frame(0)[..., ::-1])
        cv2.imwrite(str(directory/'labels.png'), self.panel_labels)
        if self.backdrop:
            cv2.imwrite(str(directory/'backdrop.png'),self.backdrop.image[...,::-1])

    @classmethod
    def from_metadata(cls, path, size=None):
        path = Path(path)
        if path.is_dir(): path /= 'bench.json'
        meta = json.loads(path.read_text(encoding='utf-8-sig'))
        meta = meta.get('bench', meta)
        compatible_v3 = meta['version'] == 3 and meta['renderer_sha256'] == V3_RENDERER
        if not compatible_v3 and (meta['version'] != VERSION or meta['renderer_sha256'] != sha256(__file__)):
            raise ValueError('renderer changed; replay with the captured version')
        if meta['backdrop_renderer_sha256'] != sha256(Path(__file__).with_name('bench_backdrop.py')):
            raise ValueError('backdrop renderer changed; replay with the captured version')
        if meta.get('backdrop_filter') == 'cubic4' and meta.get('filter_shader_sha256') != sha256(Path(__file__).with_name('bench_filter.py')):
            raise ValueError('backdrop shader changed; replay with the captured version')
        if meta['opencv'] != cv2.__version__ or meta['numpy'] != np.__version__:
            raise ValueError('CPU library versions changed since capture')
        manifest = asset_manifest(path.parent/'assets.json')
        if manifest != meta['assets_manifest']: raise ValueError('asset manifest differs')
        result = cls(meta['seed'], meta['size'], meta['motion'], meta['scale'], manifest=manifest,
                     layout=meta['layout'], panel_size=meta['panel_size'], projections=meta['projections'],
                     eye_to_head=meta['eye_to_head'], anchor=meta['anchor'], panel=meta['panel_mode'],
                     backdrop=meta['backdrop']['kind'] if meta['backdrop'] else 'none',
                     backdrop_manifest=meta['backdrop']['asset'] if meta['backdrop'] else None,
                     backdrop_fov=meta['backdrop']['source_fov'] if meta['backdrop'] else None,
                     backdrop_filter=meta.get('backdrop_filter', 'default'))
        result.live = meta['live']
        logs = path.parent/'frames.ndjson'
        if logs.exists():
            with logs.open(encoding='utf-8') as stream:
                for line in stream:
                    record = json.loads(line)
                    result.frame_records[record['frame']] = record
        # Never rebuild at stream resolution: source geometry/filter history matters.
        if size is not None and tuple(size) != result.size:
            raise ValueError('source geometry is recorded; --size cannot replace it')
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bench-seed', type=int, default=1)
    parser.add_argument('--bench-motion', choices=MOTIONS, default='mix')
    parser.add_argument('--bench-scale', type=float, default=1.)
    parser.add_argument('--bench-layout', choices=('cards','metro'), default='cards')
    parser.add_argument('--bench-assets')
    add_backdrop_arguments(parser)
    parser.add_argument('--size', type=int, nargs=2, default=REFERENCE_SIZE)
    args = parser.parse_args(argv)
    BenchScene(args.bench_seed, args.size, args.bench_motion, args.bench_scale, args.bench_assets, layout=args.bench_layout, **backdrop_arguments(args)).save(args.out)


def add_backdrop_arguments(parser):
    parser.add_argument('--bench-backdrop', choices=('metro','mosaic','none'), default=None,
                        help='default: metro with backdrop asset, otherwise mosaic')
    parser.add_argument('--bench-backdrop-asset', type=Path, help='PNG or encoder_input.json (shared left eye)')
    parser.add_argument('--bench-backdrop-fov', type=float, nargs=4, metavar=('LEFT','RIGHT','TOP','BOTTOM'))
    parser.add_argument('--bench-panel', choices=('on','off'), default='on')
    parser.add_argument('--bench-backdrop-filter', choices=('default', 'ss4', 'cubic4'), default='default')


def backdrop_arguments(args):
    return {'backdrop':args.bench_backdrop, 'backdrop_asset':args.bench_backdrop_asset,
            'backdrop_fov':args.bench_backdrop_fov, 'panel':args.bench_panel,
            'backdrop_filter':getattr(args, 'bench_backdrop_filter', 'default')}


if __name__ == '__main__':
    main()

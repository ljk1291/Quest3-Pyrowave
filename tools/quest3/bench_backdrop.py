"""CPU-only natural backdrop assets, plane geometry and encoder-load diagnostics."""
from pathlib import Path
import json

import cv2
import numpy as np

from tools.quest3.bench_scene import asset_manifest, load_asset, fractal_photo, mip_chain

BACKDROPS = ('metro', 'mosaic', 'none')
SERVER_MATRIX = np.array([[.2126, .7152, .0722],
                          [-.1141230, -.3839162, .4980392],
                          [.4980392, -.4523718, -.0456674]], np.float64)


def dump_rgb(planes):
    """Invert the server's +/-127 matrix, with co-sited 2x2 replication.

    This is the exact linear inverse, not the conventional +/-127.5 inverse.
    Quantization, 4:2:0 and out-of-gamut clipping are irreversible. Replication
    preserves the stored chroma on a forward 2x2 average (linear upsampling does
    not). Callers round/clamp once when making an RGB8 texture.
    """
    y, cb, cr = planes
    up = lambda p: np.repeat(np.repeat(p.astype(np.float32)-128, 2, 0), 2, 1)
    return (np.stack((y, up(cb), up(cr)), -1) @ np.linalg.inv(SERVER_MATRIX).T).astype(np.float32)


def metro_planes(path):
    from tools.quest3.bench_score import read_dump
    planes, meta = read_dump(path)
    if (meta['stage'], meta['format'], meta['range'], meta['matrix'], meta['row_order']) != (
            'encoder_input', 'yuv420p', 'full', 'bt709', 'top_down'):
        raise ValueError('Metro needs full-range BT.709 top-down yuv420p encoder_input')
    if meta['width'] % 4:
        raise ValueError('Metro stereo eye width must be even')
    return tuple(p.astype(np.uint8) for p in planes), meta


def backdrop_manifest(path):
    path = Path(path)
    if path.suffix.lower() == '.json':
        meta = json.loads(path.read_text(encoding='utf-8-sig'))
        if 'assets' in meta:
            result = asset_manifest(path)
            if len(result['assets']) != 1:
                raise ValueError('backdrop manifest must select exactly one uncropped frame')
            return result
        path = path.with_suffix('.raw')
    from tools.quest3.bench_scene import sha256
    entry = {'path': str(path.resolve()), 'sha256': sha256(path)}
    if path.suffix.lower() == '.raw':
        entry['metadata_sha256'] = sha256(path.with_suffix('.json'))
    return {'assets': [entry], 'fallback': None}


def raw_tangents(projection):
    p = np.asarray(projection)
    return np.array([(p[0, 2]-1)/p[0, 0], (p[0, 2]+1)/p[0, 0],
                     (-p[1, 2]-1)/p[1, 1], (-p[1, 2]+1)/p[1, 1]])


def natural_masks(rgb):
    ycc = rgb.astype(np.float32) @ SERVER_MATRIX.astype(np.float32).T
    y = ycc[..., 0]
    smooth = cv2.GaussianBlur(y, (0, 0), 2)
    gradient = lambda a: np.hypot(cv2.Sobel(a, cv2.CV_32F, 1, 0), cv2.Sobel(a, cv2.CV_32F, 0, 1))
    return {'natural': np.ones(y.shape, bool),
            'sat': (np.hypot(ycc[..., 1], ycc[..., 2]) > 30) & (y > 40),
            'mura': (y < 64) & (gradient(smooth) < 4),
            'edge': cv2.dilate((gradient(y) > 40).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)}


def load_proxy(rgb):
    """One-level orthonormal Haar energy/entropy; not a codec bitrate predictor."""
    ycc = rgb.astype(np.float32) @ SERVER_MATRIX.astype(np.float32).T
    h, w = (v//32*32 for v in ycc.shape[:2])
    if not h or not w:
        raise ValueError('load proxy needs at least 32x32 pixels')
    a, b, c, d = (ycc[dy:h:2, dx:w:2] for dy, dx in ((0,0),(0,1),(1,0),(1,1)))
    detail = np.stack(((a+b-c-d)/2, (a-b+c-d)/2, (a-b-c+d)/2), -1)
    energy = np.mean(detail**2, axis=(2,3)).reshape(h//32,16,w//32,16).mean(axis=(1,3))
    q = np.rint(detail).astype(np.int16)
    _, counts = np.unique(q, return_counts=True)
    probabilities = counts/counts.sum()
    entropy = float(-np.sum(probabilities*np.log2(probabilities)))
    return {'size': [w,h], 'haar_detail_rms': float(np.sqrt(np.mean(detail**2))),
            'active_32x32_fraction': {str(t): float(np.mean(energy > t*t)) for t in (1,2,4,8)},
            'detail_entropy_bits_per_coefficient': entropy,
            'detail_entropy_bytes_proxy': entropy*q.size/8,
            'limits': 'single-level pooled Y/Cb/Cr Haar coefficients, rounded to codes; no RDO, prediction, packet overhead or bitrate guarantee'}


class Backdrop:
    def __init__(self, scene, kind, manifest=None, fov=None):
        self.kind, self.manifest = kind, manifest
        metadata = {}
        if kind == 'metro':
            if not manifest or len(manifest['assets']) != 1:
                raise ValueError('metro backdrop requires --bench-backdrop-asset PNG or encoder_input.json')
            entry = manifest['assets'][0]
            if 'crop' in entry:
                raise ValueError('backdrop must be an uncropped eye image; crops change its projection')
            # Validate frozen hashes through the existing asset reader.
            image = load_asset(entry)
            if Path(entry['path']).suffix == '.raw':
                planes, metadata = metro_planes(Path(entry['path']).with_suffix('.json'))
                image = np.rint(np.clip(dump_rgb(tuple(p[:, :p.shape[1]//2] for p in planes)), 0, 255)).astype(np.uint8)
        source_fov = fov if fov is not None else metadata.get('projection_raw', metadata.get('eye_fov'))
        self.fov_source = 'explicit/dump' if source_fov is not None else 'stream left getProjectionRaw (offline: configured projection)'
        if source_fov is not None and np.asarray(source_fov).shape == (2,4):
            source_fov = source_fov[0]
        self.fov = np.asarray(source_fov if source_fov is not None else raw_tangents(scene.projections[0]), np.float64)
        if self.fov.shape != (4,) or not np.isfinite(self.fov).all() or not (self.fov[0] < 0 < self.fov[1] and self.fov[2] < 0 < self.fov[3]):
            raise ValueError('backdrop FOV requires left<0<right, top<0<bottom tangents')
        self.distance = 3.
        l,r,t,b = self.fov
        # Native eye-pixel density; texture size reflects angular span, not source file dimensions.
        stream = raw_tangents(scene.projections[0])
        cw, ch = [max(128, 2*round(scene.size[n]*(r-l if n == 0 else b-t)/(stream[1]-stream[0] if n == 0 else stream[3]-stream[2])/2)) for n in (0,1)]
        if kind == 'mosaic':
            rng = np.random.default_rng(scene.seed+8301)
            image = np.zeros((ch,cw,3), np.uint8)
            entries = scene.manifest['assets']
            for i in range(12):
                x0,x1 = i%4*cw//4, (i%4+1)*cw//4
                y0,y1 = i//4*ch//3, (i//4+1)*ch//3
                photo = load_asset(entries[i%len(entries)]) if entries else fractal_photo(rng,x1-x0,y1-y0)
                image[y0:y1,x0:x1] = cv2.resize(photo,(x1-x0,y1-y0),interpolation=cv2.INTER_AREA)
            # Keep natural structures, plus seeded 2-10-code fine texture even in smooth assets.
            noise_scale = cv2.resize(rng.uniform(4,10,(6,8)).astype(np.float32),(cw,ch),interpolation=cv2.INTER_LINEAR)
            fine = rng.normal(0, 1, (ch,cw,1))*noise_scale[...,None]
            image = np.rint(np.clip(8+image.astype(np.float32)*.24+fine, 0,255)).astype(np.uint8)
        central = cv2.resize(image,(cw,ch),interpolation=cv2.INTER_AREA)
        luma = central.astype(np.float32) @ SERVER_MATRIX[0].astype(np.float32)
        self.statistics = {'median_luma':float(np.median(luma)), 'fraction_luma_below_64':float(np.mean(luma < 64))}
        # Cover source + both asymmetric eye frusta, with 22 degrees each side.
        # 2 degrees reserve covers IPD and small synthetic translations at 3 m.
        frusta = np.array([self.fov, *(raw_tangents(p) for p in scene.projections)])
        angles = np.arctan(frusta)
        lo = angles[:,[0,2]].min(axis=0)-np.deg2rad(22)
        hi = angles[:,[1,3]].max(axis=0)+np.deg2rad(22)
        if max(np.abs(np.r_[lo,hi])) >= np.deg2rad(85):
            raise ValueError('FOV plus 22-degree extension is too wide for a finite plane')
        el,et = np.tan(lo); er,eb = np.tan(hi)
        pads = np.ceil([(l-el)*cw/(r-l), (er-r)*cw/(r-l), (t-et)*ch/(b-t), (eb-b)*ch/(b-t)]).astype(int)
        # Even extents keep the scorer chroma grid well-defined.
        pads += pads % 2
        pl,pr,pt,pb = pads
        self.image = cv2.copyMakeBorder(central,pt,pb,pl,pr,cv2.BORDER_REFLECT)
        self.size = self.image.shape[1::-1]
        if max(self.size) > 16384:
            raise ValueError('extended backdrop exceeds 16384 texels; reduce source eye size/FOV')
        self.central_box = [int(pl),int(pt),cw,ch]
        self.metres = [self.size[0]*self.distance*(r-l)/cw, self.size[1]*self.distance*(b-t)/ch]
        # Left source-eye rays meet this common plane. Right eye sees correct plane parallax.
        local = np.eye(4)
        local[:3,3] = [scene.eye_to_head[0,0,3]+self.distance*(l-pl*(r-l)/cw)+self.metres[0]/2,
                       scene.eye_to_head[0,1,3]-self.distance*(t-pt*(b-t)/ch)-self.metres[1]/2, -1.5]
        self.anchor = scene.anchor @ local
        self.mips = [np.rint(level).astype(np.uint8) for level in mip_chain(self.image)]
        self.masks = natural_masks(self.image)

    def metadata(self):
        return {'kind': self.kind, 'synthetic_mosaic': self.kind == 'mosaic', 'asset': self.manifest,
                'source_fov': self.fov.tolist(), 'fov_source': self.fov_source,
                'shared_texture': 'left eye on one common world plane', 'extension_degrees': 22,
                'extension': 'edge-mirrored (BORDER_REFLECT)', 'size': list(self.size),
                'central_box': self.central_box, 'metres': self.metres, 'anchor': self.anchor.tolist(),
                'distance_m': self.distance, 'central_texels_per_eye_pixel': 1.0,
                'central_statistics':self.statistics,
                'natural_subclasses':{'sat':'chroma magnitude >30 and luma >40',
                                     'mura':'luma <64 and sigma-2-smoothed Sobel <4',
                                     'edge':'Sobel >40, dilated one texel'}}

"""Score exact-timestamp lossless live dumps. CPU only; pull runs ADB only on request.

Direct execution: python tools/quest3/frame_score.py --help
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.quest3 import stereo_scene
from tools.xrbench.fence_metrics import edge_mask
from tools.xrbench.framebank import sha256_file

CLIENT_DIR = '/sdcard/Android/data/io.github.ljk1291.quest3pyrowave/files/q3pw-dumps/'
STAGES = {'encoder_input', 'post_decode', 'presented_left', 'presented_right'}


def parse_dump_path(value):
    """Mirror server's rightmost delimiters, including Windows drive letters."""
    try:
        directory, count, interval = value.rsplit(':', 2)
    except ValueError as exc:
        raise ValueError('expected directory:count:interval') from exc
    if not directory or not count.isascii() or not interval.isascii() or not count.isdigit() or not interval.isdigit():
        raise ValueError('nonempty directory and decimal numbers required')
    count, interval = count.lstrip('0') or '0', interval.lstrip('0') or '0'
    if len(count) > 10 or len(interval) > 10 or not 1 <= int(count) <= 128 or not 1 <= int(interval) <= 9000:
        raise ValueError('capture limit: count 1..128, interval 1..9000')
    return directory, int(count), int(interval)


def discover(directory, allowed_stages):
    records = {}
    for path in sorted(Path(directory).rglob('*.json')):
        meta = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(meta, dict): raise ValueError(f'invalid dump metadata: {path}')
        if meta.get('stage') not in STAGES:
            continue
        if meta.get('stage') not in allowed_stages:
            raise ValueError(f'unexpected stage in {path}')
        if meta.get('schema') != 1 or meta.get('complete') is not True:
            raise ValueError(f'incomplete or unsupported dump: {path}')
        for field in ('timestamp_ns', 'frame_index', 'width', 'height', 'bytes'):
            value = meta.get(field)
            if type(value) is not int or value < (0 if field == 'frame_index' else 1):
                raise ValueError(f'invalid {field}: {path}')
        if meta['bytes'] > 256 * 1024 * 1024 or meta.get('row_order') not in ('top_down', 'bottom_up'):
            raise ValueError(f'invalid size/row order: {path}')
        if meta.get('matrix') != 'bt709' or meta.get('range') not in ('full', 'limited'):
            raise ValueError(f'unknown color domain: {path}')
        remapped = meta.get('legacy_range_remap', False)
        if type(remapped) is not bool or (remapped and (meta['stage'] != 'post_decode' or
                meta.get('format') not in ('rgba8', 'bgra8') or meta['range'] != 'full')):
            raise ValueError(f'invalid legacy_range_remap metadata: {path}')
        raw = path.with_suffix('.raw')
        if not raw.is_file() or raw.stat().st_size != meta['bytes']:
            raise ValueError(f'missing/truncated raw dump: {path}')
        key = (meta['timestamp_ns'], meta['stage'])
        if key in records:
            raise ValueError(f'duplicate timestamp/stage {key}; select one capture run')
        records[key] = (meta, raw)
    return records


def luma(record, *, legacy_range_remap=False):
    """Full-range BT.709 R'G'B' luma, or normalized exact encoder Y plane.

    MediaCodec's EGL external RGB color conversion and PyroWave's RGBA conversion
    are part of the measured path. The explicit legacy remap models the stock
    full-range SDR staging shader, without fitting away error. No gamma transform.
    """
    meta, path = record
    h, w = meta['height'], meta['width']
    pixels = np.fromfile(path, dtype=np.uint8)
    fmt = meta['format']
    if legacy_range_remap and (meta['stage'] != 'post_decode' or
                              fmt not in ('rgba8', 'bgra8') or meta['range'] != 'full'):
        raise ValueError('legacy range remap requires full-range post_decode RGB')
    if legacy_range_remap and meta.get('legacy_range_remap', False):
        raise ValueError('dump already applied legacy range remap')
    if fmt in ('rgba8', 'bgra8'):
        if len(pixels) != h*w*4 or meta['range'] != 'full':
            raise ValueError('invalid RGBA extent/range')
        rgb = pixels.reshape(h, w, 4)[..., :3].astype(np.float32)
        if fmt == 'bgra8': rgb = rgb[..., ::-1]
        if legacy_range_remap: rgb = np.rint(16 + rgb * (219/255))
        y = rgb @ np.array([.2126, .7152, .0722], dtype=np.float32)
    elif fmt in ('yuv420p', 'yuv444p'):
        expected = h*w*3 if fmt == 'yuv444p' else h*w*3//2
        if fmt == 'yuv420p' and (w % 2 or h % 2): raise ValueError('odd 4:2:0 extent')
        if len(pixels) != expected: raise ValueError('invalid planar extent')
        y = pixels[:h*w].reshape(h, w).astype(np.float32)
        if meta['range'] == 'limited': y = (y-16) * (255/219)
    else:
        raise ValueError(f'unsupported pixel format {fmt}')
    if meta['row_order'] == 'bottom_up': y = y[::-1]
    return np.clip(y, 0, 255)


def psnr(reference, decoded, mask=None):
    error = decoded.astype(np.float64)-reference
    if mask is not None:
        if not mask.any(): return None
        error = error[mask]
    mse = float(np.mean(error**2))
    return None if mse == 0 else 10*math.log10(255**2/mse)


def ssim(reference, decoded):
    """11x11 Gaussian (sigma=1.5), population covariance, valid interior, Y only."""
    if min(reference.shape) < 11: raise ValueError('SSIM requires regions at least 11x11')
    r, d = reference.astype(np.float64), decoded.astype(np.float64)
    blur = lambda image: cv2.GaussianBlur(image, (11, 11), 1.5)
    a, b = blur(r), blur(d)
    va, vb, cov = np.maximum(0, blur(r*r)-a*a), np.maximum(0, blur(d*d)-b*b), blur(r*d)-a*b
    result = ((2*a*b+6.5025)*(2*cov+58.5225))/((a*a+b*b+6.5025)*(va+vb+58.5225))
    return float(result[5:-5, 5:-5].mean())


def blockiness(image, grid, origin=(0, 0)):
    """Boundary discontinuity minus neighboring non-boundary gradient (luma codes).

    Report signed source/decoded values and their excess separately, so real scene
    grid lines do not masquerade as compression. Grid anchored at image origin.
    """
    values = []
    for axis in (0, 1):
        gradient = np.abs(np.diff(image.astype(np.float32), axis=axis))
        n = image.shape[axis]
        boundaries = np.arange((grid-1-origin[axis]) % grid, n-2, grid)
        boundaries = boundaries[boundaries > 0]
        if len(boundaries):
            a = np.take(gradient, boundaries, axis=axis).mean()
            b = (np.take(gradient, boundaries-1, axis=axis).mean()+np.take(gradient, boundaries+1, axis=axis).mean())/2
            values.append(float(a-b))
    return float(np.mean(values)) if values else None


def blank(image):
    return {'black': bool(np.mean(image <= 3) >= .995),
            'blank': bool(float(image.std()) <= .5),
            'black_fraction': float(np.mean(image <= 3)),
            'mean_y': float(image.mean()), 'std_y': float(image.std())}


def fixed_crops(width, height, extra=None, chart_projections=None):
    if width % 2: raise ValueError('expected even side-by-side stereo width')
    if extra is not None and not isinstance(extra, dict): raise ValueError('crops must be a JSON object')
    if chart_projections is not None:
        if not isinstance(chart_projections, dict) or set(chart_projections) != {'left', 'right'}:
            raise ValueError('chart projections must contain left and right')
        for projection in chart_projections.values():
            if not isinstance(projection, list) or len(projection) != 4 or any(type(v) not in (int, float) for v in projection):
                raise ValueError('chart projections must contain four numeric tangents per eye')
    ew = width//2
    boxes = {'full': (0, 0, width, height)}
    for eye, offset in [('left', 0), ('right', ew)]:
        boxes[f'{eye}_centre'] = (offset+ew//4, height//4, ew//2, height//2)
        for corner, x, y in [('top_left', 0, 0), ('top_right', 3*ew//4, 0),
                              ('bottom_left', 0, 3*height//4), ('bottom_right', 3*ew//4, 3*height//4)]:
            boxes[f'{eye}_periphery_{corner}'] = (offset+x, y, ew//4, height//4)
        if chart_projections is not None:
            for name, (x, y, w, h) in stereo_scene.quality_regions(ew, height, chart_projections[eye]).items():
                boxes[f'{eye}_{name}'] = (offset+x, y, w, h)
    for name, box in (extra or {}).items():
        if name in boxes: raise ValueError(f'duplicate crop {name}')
        if not isinstance(box, (list, tuple)): raise ValueError(f'invalid crop {name}')
        boxes[name] = tuple(box)
    for name, box in boxes.items():
        if len(box) != 4 or any(type(v) is not int for v in box): raise ValueError(f'invalid crop {name}')
        x, y, w, h = box
        if min(w, h) < 11 or x < 0 or y < 0 or x+w > width or y+h > height:
            raise ValueError(f'crop outside frame or smaller than 11x11: {name}')
    return boxes


def region_score(reference, decoded, grids, origin=(0, 0)):
    mask, _ = edge_mask(np.rint(reference).astype(np.uint8))
    blocks = {}
    for grid in grids:
        r, d = blockiness(reference, grid, origin), blockiness(decoded, grid, origin)
        blocks[str(grid)] = {'source': r, 'decoded': d, 'excess': None if r is None else d-r}
    rg, dg = cv2.Laplacian(reference, cv2.CV_32F), cv2.Laplacian(decoded, cv2.CV_32F)
    detail = float(np.mean(np.abs(rg)))
    return {'psnr_y_db': psnr(reference, decoded), 'identical': bool(np.array_equal(reference, decoded)),
            'ssim_y': ssim(reference, decoded), 'edge_psnr_y_db': psnr(reference, decoded, mask),
            'edge_pixels': int(mask.sum()), 'blockiness': blocks,
            'detail_energy_ratio': float(np.mean(np.abs(dg)))/detail if detail else None,
            'high_frequency_error_mean': float(np.mean(np.abs(dg-rg)))}


def temporal(reference, decoded, previous_reference, previous_decoded):
    source_difference = reference-previous_reference
    decoded_difference = decoded-previous_decoded
    residual = np.abs(decoded_difference-source_difference)
    static = np.abs(source_difference) <= 1
    return {'source_difference_mean': float(np.abs(source_difference).mean()),
            'decoded_difference_mean': float(np.abs(decoded_difference).mean()),
            'residual_mean': float(residual.mean()), 'residual_p99': float(np.percentile(residual, 99)),
            'static_fraction': float(static.mean()),
            'static_residual_mean': float(residual[static].mean()) if static.any() else None,
            'static_residual_p99': float(np.percentile(residual[static], 99)) if static.any() else None}


def score_directories(server_dir, client_dir, *, grids=(8, 16, 32), crops=None,
                      chart_projections=None, decode_range_remap='none'):
    if not grids or any(type(g) is not int or g < 2 or g > 1024 for g in grids): raise ValueError('invalid grids')
    if decode_range_remap not in ('none', 'legacy-full-range'): raise ValueError('invalid decode range remap')
    remap = decode_range_remap == 'legacy-full-range'
    source = discover(server_dir, {'encoder_input'})
    client = discover(client_dir, STAGES-{'encoder_input'})
    source_ids = {ts for ts, _ in source}
    decoded_ids = {ts for ts, stage in client if stage == 'post_decode'}
    matched = sorted(source_ids & decoded_ids)
    report = {'schema': 1, 'method': "Exact transported timestamp; packed encoder input vs external decoded RGB; BT.709 full-range luma; no resizing. null PSNR with identical=true means exact identity.",
              'units': 'spatial PSNR dB; SSIM unitless; blockiness and temporal error in 8-bit full-range luma codes',
              'ssim_method': 'Gaussian 11x11 sigma 1.5, population covariance, valid interior',
              'quality_only': True, 'unmatched_server': sorted(source_ids-decoded_ids),
              'unmatched_client': sorted(decoded_ids-source_ids), 'pairs': [], 'presented': [],
              'psnr_hvs': {'measured': False, 'reason': 'WO-1 calibrated native HVS scorer requires projection/PPD and a qualified external run; no uncalibrated substitute'},
              'warnings': []}
    report['decode_range_remap'] = decode_range_remap
    if remap:
        report['method'] += ' Decoded RGB uses the production legacy SDR remap: round(16 + RGB * 219/255), including RGBA8 readback quantization; no fitted coefficients. Raw full-frame metrics are retained separately.'
        report['warnings'].append('Legacy remap requires verified stock full-range SDR hardware-decoder policy (Q3PW_COLOUR legacy_range_remap=true). Do not use for PyroWave, limited-range, HDR, or already corrected images. Old RGBA8 dumps may clip before the production remap; lost endpoints cannot be recovered. This is an approximation of staging input, not final eye pixels.')
    else:
        report['warnings'].append('post_decode with legacy_range_remap=false (including old sidecars without the field) precedes production range correction. All post_decode dumps precede gamma correction. PSNR alone is not a displayed-colour verdict; see docs/H264-RANGE.md.')
    previous = None
    aggregate = {}
    for ts in matched:
        r_record, d_record = source[(ts, 'encoder_input')], client[(ts, 'post_decode')]
        if remap and (r_record[0]['format'] not in ('rgba8', 'bgra8') or r_record[0]['range'] != 'full'):
            raise ValueError('legacy range remap requires full-range RGB encoder input')
        r, d = luma(r_record), luma(d_record, legacy_range_remap=remap)
        if r.shape != d.shape: raise ValueError(f'geometry mismatch at {ts}: {r.shape} != {d.shape}')
        if previous is not None and previous[1].shape != r.shape: raise ValueError('geometry drift within capture')
        boxes = fixed_crops(r.shape[1], r.shape[0], crops, chart_projections)
        row = {'timestamp_ns': ts, 'server_frame_index': r_record[0]['frame_index'],
               'client_frame_index': d_record[0]['frame_index'],
               'dump_legacy_range_remap': d_record[0].get('legacy_range_remap', False),
               'regions': {}, 'source_blank': blank(r), 'decoded_blank': blank(d),
               'files': {'source_sha256': sha256_file(r_record[1]), 'decoded_sha256': sha256_file(d_record[1])}}
        if remap:
            raw = luma(d_record)
            row['raw_post_decode'] = {'psnr_y_db': psnr(r, raw), 'ssim_y': ssim(r, raw),
                                     'blank': blank(raw)}
            # Luma endpoint counts are useful for neutral ramps. Coloured-channel
            # clipping needs an RGB/device check, not a luma-only verdict.
            row['range_endpoints_luma'] = {
                'source_below_16_pixels': int(np.count_nonzero(r < 16)),
                'source_above_235_pixels': int(np.count_nonzero(r > 235)),
                'low_source_decoded_zero_pixels': int(np.count_nonzero((r < 16) & (raw == 0))),
                'high_source_decoded_255_pixels': int(np.count_nonzero((r > 235) & (raw >= 254.999))),
                'remapped_min': float(d.min()), 'remapped_max': float(d.max())}
        row['unexpected_black'] = row['decoded_blank']['black'] and not row['source_blank']['black']
        row['unexpected_blank'] = row['decoded_blank']['blank'] and not row['source_blank']['blank']
        row['eyes'] = {}
        for eye, left in [('left', 0), ('right', r.shape[1]//2)]:
            rb, db = blank(r[:, left:left+r.shape[1]//2]), blank(d[:, left:left+r.shape[1]//2])
            row['eyes'][eye] = {'source': rb, 'decoded': db, 'unexpected_black': db['black'] and not rb['black'],
                                'unexpected_blank': db['blank'] and not rb['blank']}
        for name, (x, y, w, h) in boxes.items():
            rr, dd = r[y:y+h, x:x+w], d[y:y+h, x:x+w]
            metrics = region_score(rr, dd, grids, origin=(y, x))
            metrics['box'] = [x, y, w, h]
            metrics['temporal'] = None
            if previous is not None:
                pt, pr, pd = previous
                metrics['temporal'] = {'previous_timestamp_ns': pt, 'delta_ns': ts-pt,
                    **temporal(rr, dd, pr[y:y+h, x:x+w], pd[y:y+h, x:x+w])}
            row['regions'][name] = metrics
            values = aggregate.setdefault(name, [])
            values.append(metrics)
        report['pairs'].append(row)
        previous = (ts, r, d)
    for (ts, stage), record in sorted(client.items()):
        if stage.startswith('presented_'):
            image = luma(record)
            report['presented'].append({'timestamp_ns': ts, 'stage': stage, 'width': image.shape[1],
                'height': image.shape[0], 'paired_source': ts in source_ids, **blank(image)})
    def mean(values):
        finite = [v for v in values if v is not None]
        return float(np.mean(finite)) if finite else None
    report['aggregate'] = {'pair_count': len(matched),
        'unexpected_black_pairs': sum(p['unexpected_black'] for p in report['pairs']),
        'unexpected_blank_pairs': sum(p['unexpected_blank'] for p in report['pairs']),
        'unexpected_black_decoded_eyes': sum(e['unexpected_black'] for p in report['pairs'] for e in p['eyes'].values()),
        'presented_black_images': sum(p['black'] for p in report['presented']),
        'regions': {name: {'frames': len(rows), 'identical_frames': sum(m['identical'] for m in rows),
            'psnr_y_db_mean_finite': mean([m['psnr_y_db'] for m in rows]),
            'ssim_y_mean': mean([m['ssim_y'] for m in rows]),
            'edge_psnr_y_db_mean_finite': mean([m['edge_psnr_y_db'] for m in rows]),
            'detail_energy_ratio_mean': mean([m['detail_energy_ratio'] for m in rows]),
            'high_frequency_error_mean': mean([m['high_frequency_error_mean'] for m in rows]),
            'temporal_pairs': sum(m['temporal'] is not None for m in rows),
            'temporal_residual_mean': mean([m['temporal']['residual_mean'] for m in rows if m['temporal']]),
            'temporal_static_p99_mean': mean([m['temporal']['static_residual_p99'] for m in rows if m['temporal']]),
            'blockiness_excess_mean': {str(g): mean([m['blockiness'][str(g)]['excess'] for m in rows]) for g in grids}}
            for name, rows in aggregate.items()}}
    if not matched: report['warnings'].append('No exact timestamp pairs; no quality verdict.')
    if len(matched) < 2: report['warnings'].append('Fewer than two pairs; temporal flicker unavailable.')
    if crops is None and chart_projections is None: report['warnings'].append('Chart line/stripe crops not supplied; centre/periphery only.')
    report['warnings'].append('Presented-eye images are checked for blank/black only: encoder input is packed; final eyes also include FFE, gamma and presentation filtering.')
    return report


def markdown(report):
    a = report['aggregate']
    lines = [f"# Live lossless frame score\n\nPairs: {a['pair_count']}; unmatched server/client: {len(report['unmatched_server'])}/{len(report['unmatched_client'])}.",
        f"Decoded range remap: {report['decode_range_remap']}.",
        f"Unexpected black/blank decoded pairs: {a['unexpected_black_pairs']}/{a['unexpected_blank_pairs']}; black presented eyes: {a['presented_black_images']}.",
        '\n| Region | PSNR-Y finite mean dB | SSIM-Y | Temporal residual mean |\n|---|---:|---:|---:|']
    for name, row in a['regions'].items():
        values = [row[k] for k in ('psnr_y_db_mean_finite', 'ssim_y_mean', 'temporal_residual_mean')]
        lines.append(f"| {name} | " + ' | '.join('n/a' if v is None else f'{v:.4f}' for v in values) + ' |')
    lines.extend(['\nExact identity has null PSNR and `identical=true` in JSON. Capture stalls invalidate live timing claims.\n', *report['warnings']])
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    pull = commands.add_parser('pull', help='Explicit ADB collection; no device settings are changed')
    pull.add_argument('--adb', default='adb')
    pull.add_argument('--serial', required=True)
    pull.add_argument('--out', type=Path, required=True)
    score = commands.add_parser('score', help='CPU-only local scoring')
    score.add_argument('--server', type=Path, required=True)
    score.add_argument('--client', type=Path, required=True)
    score.add_argument('--out', type=Path, required=True, help='JSON path; Markdown uses the same stem')
    score.add_argument('--grids', type=int, nargs='+', default=[8, 16, 32])
    score.add_argument('--crops', type=Path, help='JSON object: crop name -> [x,y,width,height] in packed SBS coordinates')
    score.add_argument('--chart-projections', type=Path, help='JSON left/right tangent arrays; ONLY unwarped normalized chart coordinates')
    score.add_argument('--decode-range-remap', choices=['none', 'legacy-full-range'], default='none',
                       help='Explicit production staging remap for verified full-range SDR stock hardware decoding; retains raw metrics')
    args = parser.parse_args(argv)
    try:
        if args.command == 'pull':
            # Empty destination avoids merging old cells into the timestamp namespace.
            args.out.mkdir(parents=True, exist_ok=False)
            subprocess.run([args.adb, '-s', args.serial, 'pull', CLIENT_DIR.rstrip('/')+'/.', str(args.out)], check=True)
            return 0
        report = score_directories(args.server, args.client, grids=args.grids,
            crops=json.loads(args.crops.read_text()) if args.crops else None,
            chart_projections=json.loads(args.chart_projections.read_text()) if args.chart_projections else None,
            decode_range_remap=args.decode_range_remap)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        args.out.with_suffix('.md').write_text(markdown(report), encoding='utf-8')
        print(f"Scored {report['aggregate']['pair_count']} exact timestamp pairs -> {args.out}")
        return 0 if report['aggregate']['pair_count'] else 2
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f'frame_score: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())

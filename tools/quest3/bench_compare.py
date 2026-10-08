"""Comparison on common eyes and fixed spatial support, before resampling."""
import base64
import zlib

import numpy as np


def pack(values):
    return base64.b64encode(zlib.compress(np.asarray(values, '<f4').tobytes(), 1)).decode('ascii')


def unpack(value):
    return np.frombuffer(zlib.decompress(base64.b64decode(value)), '<f4')


def field(values, mask):
    indices = np.flatnonzero(mask).astype('<u4')
    return {'ids': base64.b64encode(zlib.compress(indices.tobytes(), 1)).decode('ascii'),
            'count': len(indices), 'values': pack(values[mask])}


def ids(row):
    value = row['ids']
    return np.frombuffer(zlib.decompress(base64.b64decode(value)), '<u4') if isinstance(value, str) else np.asarray(value, dtype=np.int64)


def same_identity(a, b):
    """Only rigid eye transforms tolerate floating-point noise; hashes are exact."""
    if {k: v for k, v in a.items() if k != 'eye_to_head'} != {k: v for k, v in b.items() if k != 'eye_to_head'}:
        return False
    if 'eye_to_head' not in a or 'eye_to_head' not in b:
        return a == b
    left, right = np.asarray(a['eye_to_head']), np.asarray(b['eye_to_head'])
    if left.shape != (2, 4, 4) or right.shape != left.shape:
        return False
    if not np.allclose(left[:, :3, 3], right[:, :3, 3], atol=1e-6, rtol=0):
        return False
    if not np.array_equal(left[:, 3], right[:, 3]):
        return False
    # Frobenius chord length is stable even when acos(trace) rounds to zero.
    chord = np.linalg.norm(left[:, :3, :3]-right[:, :3, :3], axis=(1, 2))
    angles = 2*np.arcsin(np.minimum(1, chord/(2*np.sqrt(2))))
    if np.any(angles > 1e-6):
        return False
    # Bound projected displacement over both eyes' full reference frusta at
    # the nearest scored plane (1.5 m), including off-axis rotation effects.
    size = np.asarray(a['reference_size'])
    for i, projection in enumerate(np.asarray(a['projections'])):
        for x in (-1., 0., 1.):
            for y in (-1., 0., 1.):
                ray = np.linalg.inv(projection) @ [x, y, 0, 1]
                ray = ray[:3]/ray[3]
                point = np.r_[ray*(1.5/abs(ray[2])), 1.]
                p = projection @ point
                q = projection @ np.linalg.inv(right[i]) @ left[i] @ point
                if np.linalg.norm((p[:2]/p[3]-q[:2]/q[3])*size/2) > .01:
                    return False
    return True


def matched_groups(reports, phase_key, minimum_coverage=.8):
    # A recorded pose is not a synthetic stationary phase. Until a calibrated
    # motion-distribution matcher is available, explicitly refuse worn none.
    if any(r.get('scene', {}).get('live') and r['comparison_identity'].get('motion') == 'none' for r in reports):
        raise ValueError('not comparable: worn motion=none requires matching recorded pose deltas; synthetic phase none does not establish matched head motion')
    eyes = set.intersection(*({s['eye'] for s in r['samples']} for r in reports))
    if not eyes:
        raise ValueError('not comparable: no common validated eyes/captures')
    grouped = []
    for report in reports:
        phases = {}
        for sample in sorted(report['samples'], key=lambda s: (s.get('capture_time', s['index']), s['index'])):
            if sample['eye'] in eyes:
                phases.setdefault(phase_key(sample), {}).setdefault(sample['sample_id'], []).append(sample)
        # Each cluster must contain every common eye, once. Partial clusters
        # otherwise change eye weights between captures and between runs.
        phases = {k: {i: g for i, g in groups.items() if {s['eye'] for s in g} == eyes}
                  for k, groups in phases.items()}
        grouped.append({k: v for k, v in phases.items() if v})
    common = set.intersection(*(set(g) for g in grouped))
    coverage = [sum(len(g[k]) for k in common)/max(1, len({s['sample_id'] for s in r['samples']}))
                for g, r in zip(grouped, reports)]
    if not common or min(coverage) < minimum_coverage:
        raise ValueError('not comparable: insufficient shared trajectory phases (requires 80% of captures in every run)')
    weights = {k: min(len(g[k]) for g in grouped) for k in sorted(common)}
    total = sum(weights.values())
    return grouped, {k: v/total for k, v in weights.items()}, coverage


def observations(report, groups, name, metric):
    """Retrieve exactly the selected (capture, eye), preserving bootstrap draws."""
    if name in ('sat', 'sat-natural') and metric in ('block_rms_p99', 'toggle_fraction') and report['stage'] == 'compositor':
        rows = report.get('compositor_blocks' if name == 'sat' else 'backdrop_compositor_blocks', [])
        lookup = {(s['sample_id'], s['eye']): s for s in rows}
        return [(s['eye'], s['sample_id'], lookup.get((s['sample_id'], s['eye']), {'ids': []})) for g in groups for s in g]
    if metric.startswith('detail_'):
        lookup = {(s['sample_id'], s['eye']): s for s in report.get('detail_samples', {}).get(name, [])
                  if metric != 'detail_correlated_mean' or 'correlated' in s}
        return [(s['eye'], s['sample_id'], lookup.get((s['sample_id'], s['eye']), {'ids': []})) for g in groups for s in g]
    return [(s['eye'], s['sample_id'], s.get('spatial', {}).get(name, {}).get(metric, {'ids': []})) for g in groups for s in g]


def common_support(reports, grouped, key, name, metric, minimum=4):
    """Conservative complete-case support; original IDs establish eligibility.

    Intersection across all selected captures also fixes pixel weights inside
    a block. Missing observations cannot enter as zeros or bootstrap duplicates.
    """
    common = None
    for report, phases in zip(reports, grouped):
        rows = observations(report, eligible_groups(report, list(phases[key].values()), name, metric), name, metric)
        supported = {}
        for eye in {eye for eye, _, _ in rows}:
            selected = [(ident, row) for e, ident, row in rows if e == eye]
            if len({ident for ident, row in selected if len(ids(row))}) < minimum:
                supported[eye] = set()
            else:
                supported[eye] = set.intersection(*(set(ids(row)) for _, row in selected))
        common = supported if common is None else {e: ids & supported.get(e, set()) for e, ids in common.items()}
    return common or {}


def eligible_groups(report, groups, name, metric):
    return [g for g in groups if all(len(ids(row)) for _, _, row in observations(report, [g], name, metric))]


class PreparedMetric:
    """Decode/restrict once, then resample chronological capture rows cheaply."""
    def __init__(self, report, groups, name, metric, support):
        from tools.quest3 import bench_score as bs
        groups = eligible_groups(report, groups, name, metric)
        self.metric, self.stage = metric, report['stage']
        self.by_id = {group[0]['sample_id']: n for n, group in enumerate(groups)}
        self.values = []
        self.eyes = []
        self.kind = 'scalar'
        for eye, supported in sorted(support.items()):
            if not supported:
                continue
            wanted = np.array(sorted(supported))
            fields = []
            for group in groups:
                rows = [row for e, _, row in observations(report, [group], name, metric) if e == eye]
                if len(rows) != 1:
                    raise ValueError('duplicate capture/eye observations')
                row = rows[0]
                positions = np.searchsorted(ids(row), wanted)
                if 'cb' in row:
                    self.kind = 'chroma'
                    fields.append(np.stack([bs.unpacked_blocks(row[c], len(row['ids']))[positions] for c in ('cb', 'cr')], axis=1))
                elif 'retained' in row:
                    self.kind = 'detail'
                    fields.append(np.asarray(row.get('correlated', []) if metric == 'detail_correlated_mean' else row['retained'])[positions])
                else:
                    field_values = unpack(row['values'])[positions]
                    if metric == 'flicker_p99' and self.stage == 'compositor':
                        self.kind = 'edge'
                        fields.append(field_values)
                    else:
                        fields.append(float(np.mean(field_values)) if metric.startswith('mse_') or metric == 'toggle_fraction' else float(np.percentile(field_values, 99)))
            self.values.append(np.array(fields, dtype=np.float32))
            self.eyes.append(eye)

    def __call__(self, groups):
        if not self.values:
            return None
        indices = [self.by_id[g[0]['sample_id']] for g in groups if g[0]['sample_id'] in self.by_id]
        if not indices:
            return None
        fields = []
        for values in self.values:
            a = values[indices]
            if self.kind == 'chroma':
                fields.extend(np.sqrt(np.var(a, axis=0).mean(axis=(1, 2))))
            elif self.kind == 'edge':
                fields.extend(np.std(a, axis=0))
            elif self.kind == 'detail':
                if self.metric in ('detail_retained_mean', 'detail_correlated_mean'):
                    fields.extend(a.mean(axis=0))
                elif self.metric == 'detail_std_p99':
                    fields.extend(np.std(a, axis=0))
                elif self.metric == 'detail_toggle_fraction':
                    fields.extend((a.min(axis=0) < .5) & (a.max(axis=0) > .8))
            else:
                fields.extend(a)
        if not len(fields):
            return None
        if self.kind == 'chroma' and self.metric == 'toggle_fraction':
            return float(np.mean(np.array(fields) > 1.5))
        return float(np.percentile(fields, 99) if self.kind != 'scalar' and self.metric.endswith('p99') else np.mean(fields))

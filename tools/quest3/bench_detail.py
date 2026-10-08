"""Luma detail retention in fixed 32x32 content blocks (CPU only)."""
import cv2
import numpy as np


def block_sum(field):
    h, w = field.shape
    return field[:h//32*32, :w//32*32].reshape(h//32, 32, w//32, 32).sum(axis=(1, 3))


def energy(luma):
    """Two finest undecimated Laplacian bands, in squared code values."""
    y = np.asarray(luma, np.float32)
    low = cv2.GaussianBlur(y, (5, 5), .8)
    coarse = cv2.GaussianBlur(low, (9, 9), 1.6)
    return (y-low)**2 + (low-coarse)**2


def retention(truth_energy, output_energy, region, valid, floor=.5):
    # Filter support is supplied by the caller. Class edges may occupy only a
    # small part of a block; pool energy only on that class's pixels.
    pixels = block_sum(region.astype(np.float32))
    safe = block_sum(valid.astype(np.float32)) == 1024
    reference = block_sum(truth_energy*region)
    observed = block_sum(output_energy*region)
    eligible = safe & (pixels >= 32) & (reference >= floor*pixels)
    ids = np.flatnonzero(eligible)
    values = observed.ravel()[ids]/reference.ravel()[ids]
    return {'ids': ids.tolist(), 'retained': values.tolist()}


def temporal(samples):
    """Hysteresis transitions; missing blocks never become zero-energy samples.

    Eye/block identities remain distinct. Duplicate capture IDs are clustered
    before temporal statistics, so two eyes are not consecutive observations.
    """
    blocks = {}
    for sample in samples:
        for ident, ratio in zip(sample['ids'], sample['retained']):
            blocks.setdefault((sample['eye'], ident), {}).setdefault(sample['sample_id'], []).append(ratio)
    std, spans, toggles, all_values = [], [], [], []
    for observations in blocks.values():
        values = np.array([np.mean(v) for v in observations.values()])
        all_values.extend(values)
        if len(values) < 2:
            continue
        std.append(float(values.std())); spans.append(float(np.ptp(values)))
        states = [(-1 if v < .5 else 1) for v in values if v < .5 or v > .8]
        toggles.append(any(a != b for a, b in zip(states, states[1:])))
    return {'detail_retained_mean': float(np.mean(all_values)) if all_values else None,
            'detail_std_mean': float(np.mean(std)) if std else None,
            'detail_std_p99': float(np.percentile(std, 99)) if std else None,
            'detail_span_p99': float(np.percentile(spans, 99)) if spans else None,
            'detail_toggle_fraction': float(np.mean(toggles)) if toggles else None,
            'detail_temporal_blocks': len(toggles)}

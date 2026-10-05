"""CPU equivalence model for the CDF 5/3 inverse candidate.

It mirrors `shaders/idwt.comp`'s inverse order: undo update on low/even
samples, then undo predict on high/odd samples.  The candidate computes each
output pair directly from the same clamped one-coefficient neighbourhood.
This is correctness evidence only; it says nothing about GPU performance.
"""
from __future__ import annotations

import struct


def _half(value: float) -> float:
    """GLSL shared FP16 store/load round-trip used between inverse axes."""
    return struct.unpack("e", struct.pack("e", float(value)))[0]


def _at(values: list[float], index: int) -> float:
    """5/3 symmetric endpoint extension: the nearest coefficient repeats."""
    if not values:
        raise ValueError("empty coefficient band")
    return values[min(max(index, 0), len(values) - 1)]


def reference_53(low: list[float], high: list[float], *, fp16_shared: bool = False) -> list[float]:
    """Shared-apron lifting arithmetic expressed as scalar reference code."""
    if len(low) != len(high) or not low:
        raise ValueError("equal nonempty low/high bands required")
    even = [float(value) - .25 * (_at(high, index - 1) + _at(high, index))
            for index, value in enumerate(low)]
    odd = [float(value) + .5 * (_at(even, index) + _at(even, index + 1))
           for index, value in enumerate(high)]
    values = [component for pair in zip(even, odd) for component in pair]
    return [_half(value) for value in values] if fp16_shared else values


def pair_local_53(low: list[float], high: list[float], *, fp16_shared: bool = False) -> list[float]:
    """Candidate per-pair form using only the ±1 high/low neighbourhood."""
    if len(low) != len(high) or not low:
        raise ValueError("equal nonempty low/high bands required")
    out = []
    for index in range(len(low)):
        even = float(low[index]) - .25 * (_at(high, index - 1) + _at(high, index))
        # The next even is independently reconstructed from its ±1 high halo.
        # At the right endpoint the shared-apron path mirrors the reconstructed
        # even sample itself, rather than applying a fictitious extra update.
        next_even = even if index + 1 == len(low) else float(low[index + 1]) - .25 * (high[index] + high[index + 1])
        odd = float(high[index]) + .5 * (even + next_even)
        out.extend((even, odd))
    return [_half(value) for value in out] if fp16_shared else out


def inverse_2d(reference, low_h, high_v, high_d, *, fp16_shared: bool = False):
    """Separable 2-D reference/candidate harness for same-shaped band grids."""
    rows = [reference(row_a, row_b, fp16_shared=fp16_shared) for row_a, row_b in zip(low_h, high_v)]
    # The caller supplies rows with the same 5/3 pairing structure for the
    # second axis; this intentionally tests order and shared rounding without
    # inventing a texture layout or production dispatch.
    return [reference(row_a, row_b, fp16_shared=fp16_shared) for row_a, row_b in zip(rows, high_d)]

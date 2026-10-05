"""Literal CPU model for the proposed CDF 9/7 fused inverse.

This is a correctness aid, not an encoder/decoder implementation.  It models
the 16-sample apron used by ``shaders/idwt.comp`` and
``tools/pyrowave_android/idwt97_fused.comp``: float32 lifting arithmetic with
an f16 shared-memory store between horizontal and vertical passes.  The latter
is deliberate: omitting it can hide a candidate's precision/order difference.
"""
from __future__ import annotations

import struct
import math
from typing import Sequence

ALPHA = -1.586134342059924
BETA = -0.052980118572961
GAMMA = 0.882911075530934
DELTA = 0.443506852043971
K = 1.230174104914001
INV_K = 1.0 / K
LIBRARY_IDWT_LAYERS = {"ll": 0, "x_high": 2, "y_high": 1, "hh": 3}


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def f16(value: float) -> float:
    # GLSL f16 conversion saturates this CPU proof to an IEEE infinity rather
    # than raising Python's packing exception; callers can make overflow a gate.
    if math.isfinite(value) and abs(value) > 65504.0:
        return math.copysign(math.inf, value)
    return struct.unpack("<e", struct.pack("<e", value))[0]


def mirror_index(index: int, size: int, even_band: bool, far_whole_sample: bool) -> int:
    """Resolve the fused shader's documented near/far mirrored coefficient index."""
    if size <= 0:
        raise ValueError("size must be positive")
    if index < 0:
        index = -index if even_band else -index - 1
    if index >= size:
        index = 2 * size - 2 - index if far_whole_sample else 2 * size - 1 - index
    return min(max(index, 0), size - 1)


def mirrored_repeat_texel(index: int, size: int) -> int:
    """The integer texel sequence for normalized MIRRORED_REPEAT gathers."""
    if size <= 0:
        raise ValueError("size must be positive")
    period = 2 * size
    index %= period
    return index if index < size else period - 1 - index


def library_gather_wxzy_coordinates(coord: tuple[int, int], resolution: tuple[int, int],
                                    even_x: bool, even_y: bool) -> list[tuple[int, int]]:
    """Resolve the pinned library's generate_mirror_uv + gather + ``.wxzy``.

    ``generate_mirror_uv`` offsets each axis before transposing UV. GLSL gather
    returns (i0,j1), (i1,j1), (i1,j0), (i0,j0); the shader's ``.wxzy`` makes
    the final source-coordinate order (x,y), (x,y+1), (x+1,y+1), (x+1,y),
    after MIRRORED_REPEAT addressing.
    """
    x, y = coord
    width, height = resolution
    x = x - (1 if even_x and x < 0 else 0) + 1
    y = y - (1 if even_y and y < 0 else 0) + 1
    x += 1 if not even_x and x >= width else 0
    y += 1 if not even_y and y >= height else 0
    return [(mirrored_repeat_texel(x - 1, width), mirrored_repeat_texel(y - 1, height)),
            (mirrored_repeat_texel(x - 1, width), mirrored_repeat_texel(y, height)),
            (mirrored_repeat_texel(x, width), mirrored_repeat_texel(y, height)),
            (mirrored_repeat_texel(x, width), mirrored_repeat_texel(y - 1, height))]


def _scaled(values: Sequence[float]) -> list[float]:
    if len(values) != 16:
        raise ValueError("the idwt 8x2 apron has exactly 16 samples")
    return [f16(f32(value * (K if index % 2 == 0 else INV_K))) for index, value in enumerate(values)]


def reference_idwt97_line(values: Sequence[float]) -> list[float]:
    """Pinned idwt.comp order: Delta, Gamma, Beta, Alpha; return the eight kept values."""
    work = [f32(value) for value in _scaled(values)]
    for index in range(2, 15, 2):
        work[index] = f32(work[index] - f32(DELTA * f32(work[index - 1] + work[index + 1])))
    for index in range(3, 14, 2):
        work[index] = f32(work[index] - f32(GAMMA * f32(work[index - 1] + work[index + 1])))
    for index in range(4, 13, 2):
        work[index] = f32(work[index] - f32(BETA * f32(work[index - 1] + work[index + 1])))
    for index in range(5, 12, 2):
        work[index] = f32(work[index] - f32(ALPHA * f32(work[index - 1] + work[index + 1])))
    return [f16(work[index]) for index in range(4, 12)]


def fused_idwt97_line(values: Sequence[float]) -> list[float]:
    """Literal ``lift16`` candidate order, with its f16 tile writeback."""
    work = [f32(value) for value in _scaled(values)]
    for coefficient, start, stop in ((DELTA, 2, 15), (GAMMA, 3, 14),
                                     (BETA, 4, 13), (ALPHA, 5, 12)):
        for index in range(start, stop, 2):
            work[index] = f32(work[index] - f32(coefficient * f32(work[index - 1] + work[index + 1])))
    return [f16(work[index]) for index in range(4, 12)]


def _interleave(ll: Sequence[Sequence[float]], xh: Sequence[Sequence[float]],
                yh: Sequence[Sequence[float]], hh: Sequence[Sequence[float]]) -> list[list[float]]:
    """Candidate layer mapping: LL, x-high layer 1, y-high layer 2, HH layer 3."""
    bands = (ll, xh, yh, hh)
    if any(len(band) != 8 or any(len(row) != 8 for row in band) for band in bands):
        raise ValueError("the one-level CPU proof accepts four 8x8 coefficient aprons")
    out = [[0.0] * 16 for _ in range(16)]
    for y in range(8):
        for x in range(8):
            out[2 * y][2 * x] = f16(f32(ll[y][x] * K * K))
            out[2 * y][2 * x + 1] = f16(f32(xh[y][x] * INV_K * K))
            out[2 * y + 1][2 * x] = f16(f32(yh[y][x] * K * INV_K))
            out[2 * y + 1][2 * x + 1] = f16(f32(hh[y][x] * INV_K * INV_K))
    return out


def _lift_unscaled_line(values: Sequence[float]) -> list[float]:
    """Same lifting order after the two-axis candidate interleave has already scaled inputs."""
    work = [f32(value) for value in values]
    for coefficient, start, stop in ((DELTA, 2, 15), (GAMMA, 3, 14),
                                     (BETA, 4, 13), (ALPHA, 5, 12)):
        for index in range(start, stop, 2):
            work[index] = f32(work[index] - f32(coefficient * f32(work[index - 1] + work[index + 1])))
    return [f16(work[index]) for index in range(4, 12)]


def reference_idwt97_2d(ll: Sequence[Sequence[float]], xh: Sequence[Sequence[float]],
                         yh: Sequence[Sequence[float]], hh: Sequence[Sequence[float]]) -> list[list[float]]:
    """Two passes with the explicit f16 shared-memory boundary of idwt.comp."""
    source = _interleave(ll, xh, yh, hh)
    horizontal = [_lift_unscaled_line(row) for row in source]
    columns = [_lift_unscaled_line([horizontal[row][column] for row in range(16)]) for column in range(8)]
    return [[columns[column][row] for column in range(8)] for row in range(8)]


def fused_idwt97_2d(ll: Sequence[Sequence[float]], xh: Sequence[Sequence[float]],
                     yh: Sequence[Sequence[float]], hh: Sequence[Sequence[float]]) -> list[list[float]]:
    """Candidate topology expressed independently: row writeback then column writeback."""
    tile = _interleave(ll, xh, yh, hh)
    # The shader only writes the kept x span; every source row remains available for vertical aprons.
    row_store = [[f16(0.0)] * 8 for _ in range(16)]
    for row in range(16):
        row_store[row] = _lift_unscaled_line(tile[row])
    output = [[f16(0.0)] * 8 for _ in range(8)]
    for column in range(8):
        kept = _lift_unscaled_line([row_store[row][column] for row in range(16)])
        for row, value in enumerate(kept):
            output[row][column] = value
    return output

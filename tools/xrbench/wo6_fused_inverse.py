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


def _shared(value: float, fp16_shared: bool) -> float:
    """Match ``store_shared`` followed by ``load_shared`` for the FP16 path."""
    return _half(value) if fp16_shared else float(value)


def _validate_apron(samples: list[float], core_pair_start: int, core_pair_count: int) -> None:
    if len(samples) < 6 or len(samples) % 2:
        raise ValueError("at least three interleaved low/high pairs are required")
    pairs = len(samples) // 2
    if core_pair_start < 1 or core_pair_count < 1 or core_pair_start + core_pair_count >= pairs:
        raise ValueError("core pairs need one complete pair of apron on each side")


def shader_apron_53(
        samples: list[float], core_pair_start: int, core_pair_count: int, *, fp16_shared: bool = False) -> list[float]:
    """Literal scalar form of the CDF 5/3 branch in ``idwt.comp``.

    ``samples`` is the already gathered, interleaved low/high shared-memory
    row, including its apron.  The two loops deliberately retain the shader's
    order: all even samples are updated before any odd sample is predicted.
    That distinction matters at the right edge of every output pair.
    """
    _validate_apron(samples, core_pair_start, core_pair_count)
    values = [_shared(value, fp16_shared) for value in samples]
    for index in range(2, len(values) - 1, 2):
        values[index] -= .25 * (values[index - 1] + values[index + 1])
    for index in range(3, len(values) - 2, 2):
        values[index] += .5 * (values[index - 1] + values[index + 1])
    begin, end = 2 * core_pair_start, 2 * (core_pair_start + core_pair_count)
    return values[begin:end]


def pair_local_apron_53(
        samples: list[float], core_pair_start: int, core_pair_count: int, *, fp16_shared: bool = False) -> list[float]:
    """Candidate calculation with only the current and ±1 pair neighbourhood.

    This is algebraically equivalent to :func:`shader_apron_53` for output
    pairs that have an apron.  It intentionally has no 9/7 mode.
    """
    _validate_apron(samples, core_pair_start, core_pair_count)
    values = [_shared(value, fp16_shared) for value in samples]

    def even(pair: int) -> float:
        index = 2 * pair
        return values[index] - .25 * (values[index - 1] + values[index + 1])

    output: list[float] = []
    for pair in range(core_pair_start, core_pair_start + core_pair_count):
        value_even = even(pair)
        value_odd = values[2 * pair + 1] + .5 * (value_even + even(pair + 1))
        output.extend((value_even, value_odd))
    return output


def _apron_from_clamped_bands(low: list[float], high: list[float]) -> list[float]:
    if len(low) != len(high) or not low:
        raise ValueError("equal nonempty low/high bands required")
    # ``load_image_with_apron`` supplies coefficient pairs outside the active
    # region through its mirror gather.  At a one-dimensional boundary this is
    # the repeated endpoint pair used by the 5/3 lifting rule.
    return [component for pair in ((_at(low, pair), _at(high, pair))
                                   for pair in range(-1, len(low) + 1))
            for component in pair]


def reference_53(low: list[float], high: list[float], *, fp16_shared: bool = False) -> list[float]:
    """Full line reference, including the clamped coefficient-pair apron."""
    return shader_apron_53(_apron_from_clamped_bands(low, high), 1, len(low), fp16_shared=fp16_shared)


def pair_local_53(low: list[float], high: list[float], *, fp16_shared: bool = False) -> list[float]:
    """Full line candidate using the same clamped coefficient-pair apron."""
    return pair_local_apron_53(_apron_from_clamped_bands(low, high), 1, len(low), fp16_shared=fp16_shared)

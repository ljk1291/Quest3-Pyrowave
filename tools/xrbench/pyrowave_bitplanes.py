"""Parse retained PyroWave `.wave` bitplane records without invoking a codec.

The parser mirrors the serialized layout checked by the native encoder's
``validate_bitstream`` routine.  It is intentionally read-only: it examines
container framing, sequence/block headers, controls, bitplane bytes, signs,
and alignment padding, then reports a zero-order entropy bound for actual
bitplane symbols.  It does not run an encoder, decoder, or entropy coder.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Iterable

from .pyrowave_wave import MAGIC

_CONTAINER_HEADER_BYTES = 40
_SEQUENCE_HEADER_BYTES = 8
_BLOCK_HEADER_BYTES = 8


class BitplaneFormatError(ValueError):
    """The container does not satisfy the native serialized-layout contract."""


@dataclass(frozen=True)
class FrameStats:
    payload_bytes: int
    sequence: int
    width: int
    height: int
    codec_code: int
    chroma_resolution: int
    active_blocks: int
    block_header_bytes: int
    control_bytes: int
    plane_bytes: int
    sign_bytes: int
    padding_bytes: int
    plane_counts: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    plane_context_counts: tuple[tuple[tuple[int, int], tuple[tuple[int, int], ...]], ...]


def _need(blob: bytes, offset: int, length: int, where: str) -> None:
    if offset < 0 or length < 0 or offset + length > len(blob):
        raise BitplaneFormatError(f"truncated {where}")


def _u32(blob: bytes, offset: int, where: str) -> int:
    _need(blob, offset, 4, where)
    return struct.unpack_from("<I", blob, offset)[0]


def _entropy_bits(symbols: Iterable[int]) -> tuple[int, float]:
    counts = Counter(symbols)
    total = sum(counts.values())
    if not total:
        return 0, 0.0
    entropy = -sum(count / total * math.log2(count / total) for count in counts.values())
    return total, entropy


def _parse_frame(payload: bytes) -> FrameStats:
    _need(payload, 0, _SEQUENCE_HEADER_BYTES, "sequence header")
    first, second = struct.unpack_from("<II", payload, 0)
    width = (first & 0x3FFF) + 1
    height = ((first >> 14) & 0x3FFF) + 1
    sequence = (first >> 28) & 0x7
    if not ((first >> 31) & 1):
        raise BitplaneFormatError("sequence header has no extended bit")
    total_blocks = second & 0xFFFFFF
    codec_code = (second >> 24) & 0x3
    chroma_resolution = (second >> 26) & 0x1

    pos = _SEQUENCE_HEADER_BYTES
    last_block_index = -1
    block_header_bytes = control_bytes = plane_bytes = sign_bytes = padding_bytes = 0
    plane_counts: dict[int, Counter[int]] = defaultdict(Counter)
    plane_context_counts: dict[tuple[int, int], Counter[int]] = defaultdict(Counter)

    for expected_block in range(total_blocks):
        _need(payload, pos, _BLOCK_HEADER_BYTES, f"block {expected_block} header")
        first, second = struct.unpack_from("<II", payload, pos)
        ballot = first & 0xFFFF
        payload_words = (first >> 16) & 0xFFF
        block_sequence = (first >> 28) & 0x7
        if (first >> 31) & 1:
            raise BitplaneFormatError(f"block {expected_block} unexpectedly has extended bit")
        if block_sequence != sequence:
            raise BitplaneFormatError(f"block {expected_block} sequence does not match frame")
        block_index = (second >> 8) & 0xFFFFFF
        if block_index <= last_block_index:
            raise BitplaneFormatError(f"block indices are not strictly increasing at {block_index}")
        last_block_index = block_index
        block_bytes = payload_words * 4
        if block_bytes < _BLOCK_HEADER_BYTES:
            raise BitplaneFormatError(f"block {block_index} is shorter than its header")
        _need(payload, pos, block_bytes, f"block {block_index}")

        active_8x8 = ballot.bit_count()
        controls_at = pos + _BLOCK_HEADER_BYTES
        controls_bytes = active_8x8 * 3
        data_at = controls_at + controls_bytes
        if data_at > pos + block_bytes:
            raise BitplaneFormatError(f"block {block_index} controls exceed payload")

        plane_at = data_at
        significant_values = 0
        for control_index in range(active_8x8):
            control16 = struct.unpack_from("<H", payload, controls_at + control_index * 2)[0]
            q_bits = payload[controls_at + active_8x8 * 2 + control_index] & 0xF
            for subblock_offset in range(0, 16, 2):
                planes = q_bits + ((control16 >> subblock_offset) & 0x3)
                _need(payload, plane_at, planes, f"block {block_index} planes")
                significance = 0
                values = payload[plane_at : plane_at + planes]
                for plane_index, value in enumerate(values):
                    plane_counts[plane_index][value] += 1
                    plane_context_counts[(q_bits, plane_index)][value] += 1
                    significance |= value
                plane_at += planes
                significant_values += significance.bit_count()

        signs = (significant_values + 7) // 8
        _need(payload, plane_at, signs, f"block {block_index} sign tail")
        used = (plane_at + signs) - pos
        if (used + 3) // 4 != payload_words:
            raise BitplaneFormatError(f"block {block_index} has inconsistent word length")
        padding = block_bytes - used
        if not 0 <= padding <= 3:
            raise BitplaneFormatError(f"block {block_index} has invalid alignment padding")

        block_header_bytes += _BLOCK_HEADER_BYTES
        control_bytes += controls_bytes
        plane_bytes += plane_at - data_at
        sign_bytes += signs
        padding_bytes += padding
        pos += block_bytes

    if pos != len(payload):
        raise BitplaneFormatError(f"frame has {len(payload) - pos} trailing byte(s)")
    return FrameStats(
        payload_bytes=len(payload), sequence=sequence, width=width, height=height,
        codec_code=codec_code, chroma_resolution=chroma_resolution,
        active_blocks=total_blocks, block_header_bytes=block_header_bytes,
        control_bytes=control_bytes, plane_bytes=plane_bytes, sign_bytes=sign_bytes,
        padding_bytes=padding_bytes,
        plane_counts=tuple((plane, tuple(sorted(counts.items()))) for plane, counts in sorted(plane_counts.items())),
        plane_context_counts=tuple((context, tuple(sorted(counts.items())))
                                   for context, counts in sorted(plane_context_counts.items())),
    )


def parse_wave_bytes(blob: bytes) -> tuple[tuple[int, ...], list[FrameStats]]:
    """Parse a complete `.wave` container from bytes."""
    _need(blob, 0, _CONTAINER_HEADER_BYTES, "container header")
    if blob[:8] != MAGIC:
        raise BitplaneFormatError("missing PYROWAVE magic")
    container = struct.unpack_from("<8i", blob, 8)
    if container[0] <= 0 or container[1] <= 0:
        raise BitplaneFormatError("invalid container dimensions")
    pos = _CONTAINER_HEADER_BYTES
    frames: list[FrameStats] = []
    while pos < len(blob):
        size = _u32(blob, pos, "frame length")
        pos += 4
        if size == 0:
            raise BitplaneFormatError("zero-sized frame")
        _need(blob, pos, size, "frame payload")
        frames.append(_parse_frame(blob[pos : pos + size]))
        pos += size
    if pos != len(blob):
        raise BitplaneFormatError("trailing partial frame length")
    if not frames:
        raise BitplaneFormatError("container has no frames")
    return container, frames


def analyze_wave_bytes(blob: bytes) -> dict:
    """Return a JSON-safe, path-free analysis of an actual serialized bitstream."""
    container, frames = parse_wave_bytes(blob)
    first = frames[0]
    invariants = (first.width, first.height, first.codec_code, first.chroma_resolution)
    if any((frame.width, frame.height, frame.codec_code, frame.chroma_resolution) != invariants for frame in frames):
        raise BitplaneFormatError("frame sequence headers disagree on dimensions or codec")

    counts_by_plane: dict[int, Counter[int]] = defaultdict(Counter)
    for frame in frames:
        for plane, pairs in frame.plane_counts:
            counts_by_plane[plane].update(dict(pairs))
    aggregate_counts: Counter[int] = Counter()
    for counts in counts_by_plane.values():
        aggregate_counts.update(counts)
    total_symbols = sum(aggregate_counts.values())
    aggregate_h0 = (0.0 if not total_symbols else -sum(
        count / total_symbols * math.log2(count / total_symbols)
        for count in aggregate_counts.values()))
    by_plane = []
    summed_h0_bits = 0.0
    for plane in sorted(counts_by_plane):
        counts = counts_by_plane[plane]
        count = sum(counts.values())
        h0 = (0.0 if not count else -sum(
            value_count / count * math.log2(value_count / count)
            for value_count in counts.values()))
        summed_h0_bits += count * h0
        by_plane.append({"plane_index": plane, "bytes": count, "h0_bits_per_byte": h0,
                         "h0_bytes": count * h0 / 8.0})
    counts_by_context: dict[tuple[int, int], Counter[int]] = defaultdict(Counter)
    for frame in frames:
        for context, pairs in frame.plane_context_counts:
            counts_by_context[context].update(dict(pairs))
    contextual_h0_bits = 0.0
    for counts in counts_by_context.values():
        count = sum(counts.values())
        if count:
            contextual_h0_bits += -sum(
                value_count * math.log2(value_count / count)
                for value_count in counts.values())

    payload_sizes = [frame.payload_bytes for frame in frames]
    classes = {
        "sequence_header_bytes": len(frames) * _SEQUENCE_HEADER_BYTES,
        "block_header_bytes": sum(frame.block_header_bytes for frame in frames),
        "control_bytes": sum(frame.control_bytes for frame in frames),
        "bitplane_bytes": sum(frame.plane_bytes for frame in frames),
        "sign_bytes": sum(frame.sign_bytes for frame in frames),
        "alignment_padding_bytes": sum(frame.padding_bytes for frame in frames),
    }
    classes["payload_bytes"] = sum(payload_sizes)
    if sum(value for key, value in classes.items() if key != "payload_bytes") != classes["payload_bytes"]:
        raise AssertionError("byte classes do not cover payload")

    return {
        "schema": 1,
        "kind": "pyrowave_actual_bitplane_h0_analysis",
        "analysis_mode": "read_only_parser_no_codec_or_entropy_coder",
        "input_sha256": hashlib.sha256(blob).hexdigest(),
        "container": {"width": container[0], "height": container[1], "format": container[2],
                      "chroma": container[3], "full_range": container[4],
                      "fps_numerator": container[5], "fps_denominator": container[6]},
        "frames": {"count": len(frames), "payload_bytes_min": min(payload_sizes),
                   "payload_bytes_max": max(payload_sizes),
                   "payload_bytes_mean": sum(payload_sizes) / len(payload_sizes),
                   "active_blocks_min": min(frame.active_blocks for frame in frames),
                   "active_blocks_max": max(frame.active_blocks for frame in frames)},
        "sequence": {"width": first.width, "height": first.height, "codec_code": first.codec_code,
                     "chroma_resolution": first.chroma_resolution},
        "payload_byte_classes": classes,
        "bitplane_h0": {"symbols": total_symbols, "aggregate_h0_bits_per_byte": aggregate_h0,
                        "aggregate_h0_bytes": total_symbols * aggregate_h0 / 8.0,
                        "per_plane_h0_bytes_sum": summed_h0_bits / 8.0,
                        "per_q_bits_and_plane_h0_bytes_sum": contextual_h0_bits / 8.0,
                        "per_plane": by_plane,
                        "context": "native q_bits control nibble plus plane ordinal",
                        "interpretation": "zero-order symbol entropy bound only; no entropy coder was run"},
    }


def analyze_wave_path(path: Path) -> dict:
    return analyze_wave_bytes(path.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True, help="retained .wave container")
    parser.add_argument("--out", type=Path, help="write sanitized JSON; contains no input path")
    args = parser.parse_args(argv)
    result = analyze_wave_path(args.input)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

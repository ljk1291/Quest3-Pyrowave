"""Verify that the zero-offset decoder reproduces a retained decoded Y4M corpus.

This tool does no encoding, device I/O, or GPU work.  It is intentionally a
post-decode gate: pass the retained old decoder output and the new decoder's
zero-offset output, and it rejects any header, frame-count, or frame-hash drift.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def _info(path):
    path = Path(path)
    with path.open("rb") as stream:
        header = stream.readline().decode("ascii", "replace").strip()
        if not header.startswith("YUV4MPEG2 "):
            raise ValueError("not_y4m")
        tokens = header.split()[1:]
        def token(prefix, default=None):
            for value in tokens:
                if value.startswith(prefix):
                    return value[len(prefix):]
            if default is not None:
                return default
            raise ValueError("decoded_header_or_geometry_mismatch")
        width, height = int(token("W")), int(token("H"))
        fps_num, fps_den = (int(value) for value in token("F", "0:1").split(":"))
        chroma = token("C", "420jpeg").lower()
        if chroma in ("420", "420jpeg", "420mpeg2", "420paldv", "420p8"):
            chroma, frame_bytes = "420", width * height * 3 // 2
        elif chroma in ("444", "444p8"):
            chroma, frame_bytes = "444", width * height * 3
        else:
            raise ValueError("unsupported_y4m_chroma")
        range_match = re.search(r"\bXCOLORRANGE=(FULL|LIMITED)\b", header)
        if width <= 0 or height <= 0 or width % 2 or height % 2 or fps_num <= 0 or fps_den <= 0 or not range_match:
            raise ValueError("decoded_header_or_geometry_mismatch")
        hashes = []
        while tag := stream.readline():
            if not tag.startswith(b"FRAME"):
                raise ValueError("decoded_frame_tag_mismatch")
            raw = stream.read(frame_bytes)
            if len(raw) != frame_bytes:
                raise ValueError("decoded_frame_truncated")
            hashes.append(hashlib.sha256(raw).hexdigest())
    return {"width": width, "height": height, "frames": len(hashes), "fps_num": fps_num,
            "fps_den": fps_den, "chroma": chroma, "color_range": range_match.group(1),
            "frame_sha256": hashes}


def _frames(path, info):
    return info["frame_sha256"]


def verify(old80, offset_zero, *, expected_frames=90, label="crop97-rdo24-1000"):
    old80 = Path(old80)
    offset_zero = Path(offset_zero)
    old_info = _info(old80)
    new_info = _info(offset_zero)
    old_header = {key: value for key, value in old_info.items() if key != "frame_sha256"}
    new_header = {key: value for key, value in new_info.items() if key != "frame_sha256"}
    if old_header != new_header:
        raise ValueError("decoded_header_or_geometry_mismatch")
    if old_header["frames"] != expected_frames:
        raise ValueError("retained_frame_count_mismatch")
    old_frames = _frames(old80, old_info)
    new_frames = _frames(offset_zero, new_info)
    if len(old_frames) != expected_frames or len(new_frames) != expected_frames:
        raise ValueError("decoded_frame_count_mismatch")
    mismatches = [index for index, pair in enumerate(zip(old_frames, new_frames), start=1)
                  if pair[0] != pair[1]]
    if mismatches:
        raise ValueError("decoded_frame_hash_mismatch:" + ",".join(map(str, mismatches[:8])))
    return {
        "schema": 1,
        "kind": "pyrowave_dequant_zero_offset_decode_parity",
        "label": label,
        "expected_frames": expected_frames,
        "matched_frames": expected_frames,
        "old80_y4m_sha256": hashlib.sha256(old80.read_bytes()).hexdigest(),
        "offset_zero_y4m_sha256": hashlib.sha256(offset_zero.read_bytes()).hexdigest(),
        "decoded_header": old_header,
        "frame_sha256": old_frames,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old80", required=True, type=Path)
    parser.add_argument("--offset-zero", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=90)
    parser.add_argument("--label", default="crop97-rdo24-1000")
    args = parser.parse_args()
    if args.expected_frames != 90:
        raise SystemExit("the retained decoder parity gate requires exactly 90 frames")
    report = verify(args.old80, args.offset_zero, expected_frames=args.expected_frames, label=args.label)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("zero-offset decoded-frame parity verified: 90/90")


if __name__ == "__main__":
    main()

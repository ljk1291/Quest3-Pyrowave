"""Offline, fail-closed quality sweep for lossless ALVR PyroWave frame dumps.

This deliberately has no ADB, SteamVR, or headset control.  ``plan`` only
inspects a lossless Y4M dump and writes a reproducible manifest.  ``run`` is a
PC encode/decode workload and refuses to start without a WO-0-authorized window
that explicitly allows ``frame_bank_pc``.  Raw frames, resized Y4Ms and PNG
grids are private evidence and belong below ``results/local``; the companion
sanitized JSON contains hashes and aggregate scores only.

The bank scores each cell twice: against its encoded-size source (codec-only),
and after per-eye Lanczos upscale to the recorded 3072x3232 presentation size.
No resize ever sees both eyes together, so the stereo seam cannot contribute
samples to either eye.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np
from PIL import Image

from .ratequality import bytes_per_frame

SCHEMA = 1
FPS = 90
WAVELETS = ("haar", "53", "97")
RATES_MBPS = (300, 500, 600, 800)
GEOMETRIES = ((3072, 3232), (2560, 2688), (2080, 2208))
DISPLAY_EYE = (3072, 3232)

# Coordinates are normalized inside one eye. They must remain inside that eye;
# an input plan with a seam-crossing absolute crop is rejected before scoring.
DEFAULT_CROPS = (
    {"name": "text", "eye": "left", "x": 0.08, "y": 0.08, "w": 0.26, "h": 0.18},
    {"name": "foliage", "eye": "left", "x": 0.52, "y": 0.30, "w": 0.34, "h": 0.34},
    {"name": "dark_gradient", "eye": "right", "x": 0.08, "y": 0.58, "w": 0.34, "h": 0.28},
    {"name": "thin_lines", "eye": "right", "x": 0.58, "y": 0.08, "w": 0.28, "h": 0.25},
)


@dataclass(frozen=True)
class Y4MInfo:
    width: int
    height: int
    fps_num: int
    fps_den: int
    chroma: str
    color_range: str
    frame_bytes: int
    frames: int


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _parse_header(line: bytes, path: Path) -> Y4MInfo:
    text = line.decode("ascii", "replace").strip()
    if not text.startswith("YUV4MPEG2 "):
        raise ValueError(f"{path}: not YUV4MPEG2")
    def token(prefix: str, default: str | None = None) -> str:
        for item in text.split()[1:]:
            if item.startswith(prefix):
                return item[len(prefix):]
        if default is not None:
            return default
        raise ValueError(f"{path}: missing {prefix} in Y4M header")
    width, height = int(token("W")), int(token("H"))
    rate = token("F", "0:1").split(":")
    if len(rate) != 2 or int(rate[0]) <= 0 or int(rate[1]) <= 0:
        raise ValueError(f"{path}: invalid frame rate")
    chroma = token("C", "420jpeg")
    if not chroma.startswith("444"):
        raise ValueError(f"{path}: WO-1 requires lossless C444 encoder input, got C{chroma}")
    if "XCOLORRANGE=FULL" not in text:
        raise ValueError(f"{path}: WO-1 requires XCOLORRANGE=FULL")
    if width <= 0 or height <= 0 or width % 2:
        raise ValueError(f"{path}: stereo frame must have positive even width")
    return Y4MInfo(width, height, int(rate[0]), int(rate[1]), chroma, "FULL", width * height * 3, 0)


def inspect_y4m(path: Path) -> Y4MInfo:
    """Validate every frame tag/length and return only public geometry metadata."""
    path = Path(path)
    with path.open("rb") as f:
        base = _parse_header(f.readline(), path)
        frames = 0
        while True:
            tag = f.readline()
            if not tag:
                break
            if not tag.startswith(b"FRAME"):
                raise ValueError(f"{path}: frame {frames} has no FRAME tag")
            data = f.read(base.frame_bytes)
            if len(data) != base.frame_bytes:
                raise ValueError(f"{path}: truncated frame {frames}")
            frames += 1
    if not frames:
        raise ValueError(f"{path}: no frames")
    return Y4MInfo(**{**asdict(base), "frames": frames})


def iter_y4m(path: Path, info: Y4MInfo | None = None) -> Iterator[tuple[int, list[np.ndarray], str]]:
    """Yield (index, [Y,Cb,Cr], SHA-256) while preserving raw source identity."""
    path = Path(path)
    info = info or inspect_y4m(path)
    with path.open("rb") as f:
        _parse_header(f.readline(), path)
        for index in range(info.frames):
            tag = f.readline()
            if not tag.startswith(b"FRAME"):
                raise ValueError(f"{path}: frame {index} tag changed after inspection")
            raw = f.read(info.frame_bytes)
            if len(raw) != info.frame_bytes:
                raise ValueError(f"{path}: frame {index} truncated after inspection")
            planes = [np.frombuffer(raw[offset: offset + info.width * info.height], dtype=np.uint8)
                      .reshape((info.height, info.width)).copy()
                      for offset in range(0, info.frame_bytes, info.width * info.height)]
            yield index, planes, hashlib.sha256(raw).hexdigest()


def write_y4m(path: Path, info: Y4MInfo, frames: Sequence[Sequence[np.ndarray]]) -> list[str]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    hashes: list[str] = []
    with path.open("wb") as f:
        f.write((f"YUV4MPEG2 W{info.width} H{info.height} F{info.fps_num}:{info.fps_den} "
                 f"Ip A1:1 C444 XCOLORRANGE=FULL\n").encode("ascii"))
        for planes in frames:
            if len(planes) != 3 or any(p.shape != (info.height, info.width) for p in planes):
                raise ValueError("frame does not match declared C444 geometry")
            raw = b"".join(np.ascontiguousarray(p).tobytes() for p in planes)
            f.write(b"FRAME\n" + raw)
            hashes.append(hashlib.sha256(raw).hexdigest())
    return hashes


def cap_bytes(mbps: int, fps: int = FPS) -> int:
    """Exact PyroWave per-frame cap; a rate is not an average bitrate target."""
    if mbps <= 0 or fps <= 0:
        raise ValueError("mbps and fps must be positive")
    return bytes_per_frame(mbps, fps)


def bpp(cap: int, eye_width: int, eye_height: int) -> float:
    if min(cap, eye_width, eye_height) <= 0:
        raise ValueError("cap and geometry must be positive")
    return cap * 8 / (2 * eye_width * eye_height)


def _resize_plane(plane: np.ndarray, width: int, height: int) -> np.ndarray:
    return np.asarray(Image.fromarray(plane).resize((width, height), Image.Resampling.LANCZOS)).copy()


def resize_per_eye(planes: Sequence[np.ndarray], eye_width: int, eye_height: int) -> list[np.ndarray]:
    """Resize each eye independently. A seam pixel is never used as a filter input."""
    if len(planes) != 3:
        raise ValueError("expected Y/Cb/Cr")
    source_height, stereo_width = planes[0].shape
    if stereo_width % 2 or any(p.shape != (source_height, stereo_width) for p in planes):
        raise ValueError("planes must be equal-sized side-by-side stereo")
    source_eye = stereo_width // 2
    resized: list[np.ndarray] = []
    for plane in planes:
        left = _resize_plane(plane[:, :source_eye], eye_width, eye_height)
        right = _resize_plane(plane[:, source_eye:], eye_width, eye_height)
        resized.append(np.concatenate((left, right), axis=1))
    return resized


def validate_crops(crops: Sequence[dict]) -> list[dict]:
    clean = []
    names = set()
    for crop in crops:
        if not isinstance(crop, dict) or set(crop) != {"name", "eye", "x", "y", "w", "h"}:
            raise ValueError("crop schema is exactly name, eye, x, y, w, h")
        if crop["name"] in names or crop["eye"] not in ("left", "right"):
            raise ValueError("crop names must be unique and eye must be left or right")
        values = [crop[k] for k in ("x", "y", "w", "h")]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
            raise ValueError("crop coordinates must be finite")
        x, y, w, h = values
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 or y + h > 1:
            raise ValueError("crop crosses its eye boundary or falls outside the eye")
        names.add(crop["name"])
        clean.append(dict(crop))
    if not clean:
        raise ValueError("at least one fixed crop is required")
    return clean


def crop_eye(planes: Sequence[np.ndarray], crop: dict) -> list[np.ndarray]:
    validate_crops([crop])
    h, w2 = planes[0].shape
    w = w2 // 2
    left = 0 if crop["eye"] == "left" else w
    x = left + int(round(crop["x"] * w)); y = int(round(crop["y"] * h))
    cw = max(1, int(round(crop["w"] * w))); ch = max(1, int(round(crop["h"] * h)))
    if x < left or x + cw > left + w or y < 0 or y + ch > h:
        raise ValueError("rounded crop crosses stereo seam")
    return [p[y:y + ch, x:x + cw].copy() for p in planes]


def frame_records(source: Path) -> list[dict]:
    info = inspect_y4m(source)
    return [{"source_frame": index, "source_sha256": digest} for index, _, digest in iter_y4m(source, info)]


def build_plan(source: Path, projection_px_per_deg: float, *, projection_evidence: str,
               fps: int = FPS,
               wavelets: Sequence[str] = WAVELETS, rates_mbps: Sequence[int] = RATES_MBPS,
               geometries: Sequence[Sequence[int]] = GEOMETRIES,
               display_eye: Sequence[int] = DISPLAY_EYE,
               crops: Sequence[dict] = DEFAULT_CROPS) -> dict:
    """Create a freezeable matrix manifest without running codec/scorer processes."""
    if not isinstance(projection_px_per_deg, (int, float)) or not math.isfinite(projection_px_per_deg) or projection_px_per_deg <= 0:
        raise ValueError("projection_px_per_deg must be a finite positive logged value")
    if not isinstance(projection_evidence, str) or not projection_evidence.strip():
        raise ValueError("projection_evidence must name the logged projection measurement")
    info = inspect_y4m(source)
    if (info.fps_num, info.fps_den) != (fps, 1):
        raise ValueError(f"source dump is {info.fps_num}:{info.fps_den}; WO-1 90 Hz sweep requires {fps}:1")
    if (info.width // 2, info.height) != tuple(display_eye):
        raise ValueError("source dump must be the logged 3072x3232-per-eye presentation input")
    clean_crops = validate_crops(crops)
    cells = []
    for wavelet in wavelets:
        if wavelet not in WAVELETS:
            raise ValueError(f"unsupported wavelet {wavelet}")
        for rate in rates_mbps:
            for geometry in geometries:
                ew, eh = map(int, geometry)
                if min(ew, eh) <= 0:
                    raise ValueError("encoded eye geometry must be positive")
                cap = cap_bytes(int(rate), fps)
                cells.append({"wavelet": wavelet, "rate_mbps": int(rate), "fps": fps,
                              "eye_width": ew, "eye_height": eh, "stereo_width": ew * 2,
                              "cap_bytes": cap, "bits_per_pixel": bpp(cap, ew, eh)})
    return {"schema": SCHEMA, "kind": "pyrowave_frame_bank", "source": {
                "sha256": sha256_file(source), "geometry": [info.width, info.height],
                "frames": info.frames, "fps": [info.fps_num, info.fps_den], "chroma": "444",
                "color_range": info.color_range, "frame_identity": frame_records(source)},
            "presentation_eye": list(display_eye), "projection_px_per_deg": float(projection_px_per_deg),
            "projection_evidence": projection_evidence.strip(),
            "resize": {"scope": "per_eye", "filter": "lanczos4", "seam_crossing": False},
            "crops": clean_crops, "cells": cells,
            "required_metrics": ["psnr_y", "psnr_cb", "psnr_cr", "ssim", "vmaf", "psnr_hvs_m_h"]}


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA or plan.get("kind") != "pyrowave_frame_bank":
        raise ValueError("not a frame-bank schema-1 manifest")
    source = plan.get("source", {})
    if source.get("chroma") != "444" or source.get("color_range") != "FULL":
        raise ValueError("only full-range C444 source dumps are valid")
    identities = source.get("frame_identity")
    if not isinstance(identities, list) or len(identities) != source.get("frames") or not identities:
        raise ValueError("source frame identity manifest is incomplete")
    if [entry.get("source_frame") for entry in identities] != list(range(len(identities))):
        raise ValueError("source frame identities must be ordered and contiguous")
    validate_crops(plan.get("crops", []))
    if not isinstance(plan.get("projection_evidence"), str) or not plan["projection_evidence"].strip():
        raise ValueError("projection evidence is missing")
    if not plan.get("cells"):
        raise ValueError("frame bank contains no cells")
    for cell in plan["cells"]:
        if cell.get("cap_bytes") != cap_bytes(cell.get("rate_mbps"), cell.get("fps")):
            raise ValueError("cell cap math does not match its rate and frame rate")
        if cell.get("stereo_width") != cell.get("eye_width", 0) * 2:
            raise ValueError("cell stereo geometry is not two separate eyes")
    return plan


def _window_allowed(path: Path) -> dict:
    """Minimal WO-0 handoff contract; no arm/window file is created or changed here."""
    try:
        window = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PermissionError("a readable, owner-created WO-0 window record is required") from exc
    if window.get("active") is not True or "frame_bank_pc" not in window.get("allow", []):
        raise PermissionError("WO-0 window is not active or does not allow frame_bank_pc")
    return window


def required_tools(tools: dict) -> None:
    missing = []
    for name in ("encode", "decode", "ffmpeg", "psnr_hvs_m_h"):
        value = tools.get(name)
        executable = shlex.split(str(value))[0] if value else ""
        if not executable or (not Path(executable).exists() and shutil.which(executable) is None):
            missing.append(name)
    if missing:
        raise FileNotFoundError("required scorer/codec tool unavailable: " + ", ".join(missing))


def tool_provenance(tools: dict) -> dict:
    """Identify the executable bytes without publishing their machine paths."""
    result = {}
    for name, value in tools.items():
        executable = Path(shlex.split(str(value))[0])
        result[name] = {"sha256": sha256_file(executable) if executable.exists() else None,
                        "command_has_placeholders": "{" in str(value)}
    return result


def parse_hvs_m_h(output: str) -> float:
    match = re.search(r"PSNR[-_ ]HVS[-_ ]M[-_ ]H\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", output, re.I)
    if not match:
        raise ValueError("PSNR-HVS-M-H scorer output has no finite named score")
    value = float(match.group(1))
    if not math.isfinite(value):
        raise ValueError("PSNR-HVS-M-H scorer output is non-finite")
    return value


def _score_hvs_m_h(command: str, reference: Path, distorted: Path, px_per_deg: float, cwd: Path) -> float:
    # The scorer command must name its input contract explicitly via placeholders;
    # guessing a third-party CLI would turn a missing score into a false result.
    required = {"{reference}", "{distorted}", "{pixels_per_degree}"}
    if not required.issubset(set(re.findall(r"\{[^}]+\}", command))):
        raise ValueError("psnr_hvs_m_h command must contain {reference}, {distorted}, {pixels_per_degree}")
    cmd = command.format(reference=str(reference), distorted=str(distorted), pixels_per_degree=f"{px_per_deg:.8g}")
    result = subprocess.run(shlex.split(cmd), cwd=str(cwd), capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError("PSNR-HVS-M-H scorer failed: " + (result.stderr or result.stdout)[-300:])
    return parse_hvs_m_h(result.stdout + result.stderr)


def score_pair(tools: dict, distorted: Path, reference: Path, workdir: Path, px_per_deg: float) -> dict:
    # rdmatrix owns the ffmpeg graph and imports OpenCV for its PNG-source path.
    # Keep planning/schema tests runnable without the optional media environment.
    from . import rdmatrix
    values = rdmatrix.score(tools["ffmpeg"], distorted, reference, workdir)
    expected = ("psnr_y", "psnr_u", "psnr_v", "ssim_y", "ssim_all", "vmaf")
    missing = [key for key in expected if not isinstance(values.get(key), (int, float)) or not math.isfinite(values[key])]
    if missing:
        raise RuntimeError("ffmpeg/libvmaf did not emit required metrics: " + ", ".join(missing))
    return {"psnr_y": values["psnr_y"], "psnr_cb": values["psnr_u"], "psnr_cr": values["psnr_v"],
            "ssim": values["ssim_y"], "ssim_all": values["ssim_all"], "vmaf": values["vmaf"],
            "psnr_hvs": values.get("psnr_hvs"),
            "psnr_hvs_m_h": _score_hvs_m_h(tools["psnr_hvs_m_h"], reference, distorted, px_per_deg, workdir),
            "pixels_per_degree": px_per_deg}


def _decode_frames(path: Path) -> tuple[Y4MInfo, list[list[np.ndarray]], list[str]]:
    info = inspect_y4m(path)
    frames, hashes = [], []
    for _, planes, digest in iter_y4m(path, info):
        frames.append(planes); hashes.append(digest)
    return info, frames, hashes


def _write_crop_y4m(path: Path, planes_by_frame: Sequence[Sequence[np.ndarray]], crop: dict, fps: int) -> None:
    cropped = [crop_eye(planes, crop) for planes in planes_by_frame]
    h, w = cropped[0][0].shape
    write_y4m(path, Y4MInfo(w, h, fps, 1, "444", "FULL", w * h * 3, len(cropped)), cropped)


def _grid_png(path: Path, source: Sequence[np.ndarray], decoded: Sequence[np.ndarray]) -> None:
    """Private visual evidence: Y/CB/CR source and decoded, no claim-producing analysis."""
    tiles = []
    for ref, got in zip(source, decoded):
        tiles.extend([np.repeat(ref[..., None], 3, axis=2), np.repeat(got[..., None], 3, axis=2)])
    row = np.concatenate(tiles, axis=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(row).save(path)


def run_plan(plan_path: Path, source: Path, private_out: Path, tools: dict, window: Path) -> dict:
    """Run a frozen matrix. This is intentionally unavailable without a WO-0 window."""
    plan = validate_plan(json.loads(Path(plan_path).read_text(encoding="utf-8")))
    _window_allowed(window)
    required_tools(tools)
    source = Path(source)
    if sha256_file(source) != plan["source"]["sha256"]:
        raise ValueError("source dump hash differs from frozen plan")
    info = inspect_y4m(source)
    if info.frames != plan["source"]["frames"]:
        raise ValueError("source frame count differs from frozen plan")
    private_out = Path(private_out)
    if "results" not in {part.lower() for part in private_out.parts} or "local" not in {part.lower() for part in private_out.parts}:
        raise ValueError("raw frame-bank evidence must be written under results/local")
    private_out.mkdir(parents=True, exist_ok=True)
    source_frames = [planes for _, planes, _ in iter_y4m(source, info)]
    output = {"schema": SCHEMA, "kind": "pyrowave_frame_bank_result", "plan_sha256": sha256_file(plan_path),
              "source_sha256": plan["source"]["sha256"], "projection_px_per_deg": plan["projection_px_per_deg"],
              "projection_evidence": plan["projection_evidence"], "tool_provenance": tool_provenance(tools),
              "cells": [], "complete": False, "failure_reasons": []}
    for index, cell in enumerate(plan["cells"]):
        cell_dir = private_out / f"cell-{index:02d}-{cell['wavelet']}-{cell['rate_mbps']}-{cell['eye_width']}x{cell['eye_height']}"
        cell_dir.mkdir(parents=True, exist_ok=True)
        ref_frames = [resize_per_eye(frame, cell["eye_width"], cell["eye_height"]) for frame in source_frames]
        ref_info = Y4MInfo(cell["stereo_width"], cell["eye_height"], cell["fps"], 1, "444", "FULL",
                           cell["stereo_width"] * cell["eye_height"] * 3, len(ref_frames))
        reference = cell_dir / "reference-encoded.y4m"; encoded = cell_dir / "encoded.wave"; decoded = cell_dir / "decoded.y4m"
        identities = write_y4m(reference, ref_info, ref_frames)
        env = os.environ.copy(); env["PYROWAVE_WAVELET"] = cell["wavelet"]
        encode = subprocess.run([tools["encode"], str(reference), str(encoded), str(cell["cap_bytes"])], cwd=str(cell_dir), env=env, capture_output=True, text=True, check=False)
        row = {**cell, "source_frame_identity": identities, "actual_container_bytes": encoded.stat().st_size if encoded.exists() else None}
        if encode.returncode or not encoded.exists() or not encoded.stat().st_size:
            row["error"] = "encode_failed"; output["cells"].append(row); output["failure_reasons"].append("encode_failed"); continue
        decode = subprocess.run([tools["decode"], str(encoded), str(decoded)], cwd=str(cell_dir), capture_output=True, text=True, check=False)
        if decode.returncode or not decoded.exists():
            row["error"] = "decode_failed"; output["cells"].append(row); output["failure_reasons"].append("decode_failed"); continue
        decoded_info, decoded_frames, decoded_ids = _decode_frames(decoded)
        if decoded_info.width != ref_info.width or decoded_info.height != ref_info.height or len(decoded_frames) != len(ref_frames):
            row["error"] = "decoded_identity_or_geometry_mismatch"; output["cells"].append(row); output["failure_reasons"].append(row["error"]); continue
        # The codec is lossy. Exact identity means every output is bound to the
        # source frame and encoded reference at the same ordered cell index;
        # requiring equal pixel hashes here would reject every legitimate lossy
        # result and destroy the distinction between identity and quality.
        row["decoded_frame_identity"] = [
            {"cell_frame": i, "source_frame": plan["source"]["frame_identity"][i]["source_frame"],
             "reference_sha256": identities[i], "decoded_sha256": decoded_ids[i]}
            for i in range(len(decoded_frames))]
        row["actual_payload_bytes"] = max(encoded.stat().st_size - 40 - 4 * len(ref_frames), 0)
        try:
            row["codec_only"] = score_pair(tools, decoded, reference, cell_dir, plan["projection_px_per_deg"])
            displayed_frames = [resize_per_eye(frame, *plan["presentation_eye"]) for frame in decoded_frames]
            display_info = Y4MInfo(plan["presentation_eye"][0] * 2, plan["presentation_eye"][1], cell["fps"], 1, "444", "FULL", plan["presentation_eye"][0] * 2 * plan["presentation_eye"][1] * 3, len(displayed_frames))
            displayed = cell_dir / "decoded-display.y4m"; display_reference = cell_dir / "source-display.y4m"
            write_y4m(displayed, display_info, displayed_frames)
            display_refs = [resize_per_eye(frame, *plan["presentation_eye"]) for frame in source_frames]
            write_y4m(display_reference, display_info, display_refs)
            row["displayed"] = score_pair(tools, displayed, display_reference, cell_dir, plan["projection_px_per_deg"])
            row["crops"] = {}
            for crop in plan["crops"]:
                ref_crop, got_crop = cell_dir / f"crop-{crop['name']}-reference.y4m", cell_dir / f"crop-{crop['name']}-decoded.y4m"
                _write_crop_y4m(ref_crop, display_refs, crop, cell["fps"]); _write_crop_y4m(got_crop, displayed_frames, crop, cell["fps"])
                row["crops"][crop["name"]] = score_pair(tools, got_crop, ref_crop, cell_dir, plan["projection_px_per_deg"])
                _grid_png(cell_dir / "grids" / f"PRIVATE-{crop['name']}.png", crop_eye(display_refs[0], crop), crop_eye(displayed_frames[0], crop))
        except Exception as exc:
            row["error"] = "scoring_failed"; row["scoring_detail"] = str(exc)
            output["failure_reasons"].append("scoring_failed")
        output["cells"].append(row)
    output["complete"] = not output["failure_reasons"] and len(output["cells"]) == len(plan["cells"])
    (private_out / "framebank-private.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def sanitized_report(private_result: dict) -> dict:
    """Remove private paths/frame hashes and preserve missing metrics as a failed report."""
    cells = []
    for row in private_result.get("cells", []):
        cells.append({key: row.get(key) for key in ("wavelet", "rate_mbps", "fps", "eye_width", "eye_height", "cap_bytes", "bits_per_pixel", "actual_container_bytes", "actual_payload_bytes", "codec_only", "displayed", "crops", "error")})
    return {"schema": SCHEMA, "kind": "pyrowave_frame_bank_sanitized", "complete": private_result.get("complete") is True,
            "failure_reasons": list(private_result.get("failure_reasons", [])),
            "projection_px_per_deg": private_result.get("projection_px_per_deg"), "cells": cells,
            "optical_latency_ms": None, "display_fps": None}


def _main_plan(args: argparse.Namespace) -> int:
    plan = build_plan(Path(args.source), args.pixels_per_degree, projection_evidence=args.projection_evidence)
    Path(args.out).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"wrote frozen plan with {len(plan['cells'])} cells; no codec/scorer was run")
    return 0


def _main_run(args: argparse.Namespace) -> int:
    tools = {"encode": args.encode, "decode": args.decode, "ffmpeg": args.ffmpeg, "psnr_hvs_m_h": args.psnr_hvs_m_h}
    result = run_plan(Path(args.plan), Path(args.source), Path(args.private_out), tools, Path(args.window))
    report = sanitized_report(result)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote sanitized report: complete={report['complete']}")
    return 0 if report["complete"] else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="inspect lossless source and freeze a matrix; no codec run")
    plan.add_argument("--source", required=True); plan.add_argument("--pixels-per-degree", required=True, type=float); plan.add_argument("--projection-evidence", required=True, help="sanitized ID of the logged projection measurement"); plan.add_argument("--out", required=True)
    run = commands.add_parser("run", help="run frozen PC codec/scorer matrix inside a WO-0 window")
    run.add_argument("--plan", required=True); run.add_argument("--source", required=True); run.add_argument("--private-out", required=True)
    run.add_argument("--report", required=True); run.add_argument("--window", required=True, help="owner-created active WO-0 window record")
    run.add_argument("--encode", required=True); run.add_argument("--decode", required=True); run.add_argument("--ffmpeg", required=True)
    run.add_argument("--psnr-hvs-m-h", required=True, help="command with {reference} {distorted} {pixels_per_degree}")
    args = parser.parse_args(argv)
    return _main_plan(args) if args.command == "plan" else _main_run(args)


if __name__ == "__main__":
    raise SystemExit(main())

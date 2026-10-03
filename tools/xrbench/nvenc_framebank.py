"""Offline NVENC HEVC/AV1 frame-bank adapter.

This is a controlled *ALVR-like encode proxy*, not an ALVR configuration or a
Quest decoder test.  It uses the frozen Metro Y4M, exact frame-bank crops and
HVS calibration, then records the requested low-delay CBR profile and what the
encoded elementary stream actually contains.  It never starts VR software.

The runner must be given an existing owner-supervised ``frame_bank_pc`` lease.
Raw video, commands, and probes stay below ``results/local``; use
``sanitized_report`` for a shareable result.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path

from . import framebank as fb

SCHEMA = 1
CODECS = ("hevc", "av1")
RATES_MBPS = (200, 500, 800, 1000)
GEOMETRIES = ((3072, 3232), (2560, 2688))


def _tool(value):
    path = fb._tool_path(value)
    if path is None:
        raise FileNotFoundError("required NVENC frame-bank tool unavailable")
    return path


def _vbv_bits(rate_mbps: int, fps: int) -> int:
    """ALVR's 1.1-frame low-delay CBR VBV, rounded up to an integer bit."""
    if not isinstance(rate_mbps, int) or rate_mbps <= 0 or not isinstance(fps, int) or fps <= 0:
        raise ValueError("rate and fps must be positive integers")
    return math.ceil(1.1 * rate_mbps * 1_000_000 / fps)


def profile(codec: str, rate_mbps: int, fps: int = fb.FPS) -> dict:
    """Return a pinned low-delay NVENC profile without probing or encoding.

    ``p4`` is a fixed proxy choice from ALVR's selectable P1--P7 range. The
    exact live ALVR encoder settings are not inferred from it; the report
    labels this profile as an offline proxy and retains every argument.
    """
    if codec not in CODECS:
        raise ValueError("codec must be hevc or av1")
    vbv = _vbv_bits(rate_mbps, fps)
    encoder = f"{codec}_nvenc"
    args = [
        "-c:v", encoder, "-preset", "p4", "-tune", "ull", "-rc", "cbr",
        "-b:v", f"{rate_mbps}M", "-minrate", f"{rate_mbps}M",
        "-maxrate", f"{rate_mbps}M", "-bufsize", str(vbv),
        "-bf", "0", "-g", str(fps), "-forced-idr", "1",
        "-rc-lookahead", "0", "-zerolatency", "1", "-delay", "0",
        "-strict_gop", "1", "-multipass", "disabled", "-ldkfs", "1",
        "-pix_fmt", "yuv420p", "-color_range", "pc", "-chroma_sample_location", "center",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "iec61966-2-1",
    ]
    return {
        "codec": codec, "encoder": encoder, "rate_control": "cbr",
        "requested_mbps": rate_mbps, "fps": fps, "gop": fps,
        "b_frames": 0, "lookahead_frames": 0, "preset": "p4", "tune": "ull",
        "vbv_bits": vbv, "vbv_frames_nominal": 1.1, "multipass": "disabled",
        "low_delay": {"zero_latency": True, "delay_frames": 0, "strict_gop": True, "low_delay_key_frame_scale": 1},
        "pixel_format": "yuv420p", "source_plane_contract": "C420jpeg_FULL",
        "color_metadata_proxy_assumption": {"primaries": "bt709", "matrix": "bt709", "transfer": "iec61966-2-1"},
        "backend_padding_policy": "FFmpeg-6.1-NVENC-CBR-backend-dependent; AV1 source enables bitstream padding; actual bytes include any padding",
        "ffmpeg_arguments": args,
        "comparison_scope": "offline_nvenc_proxy_not_live_alvr_configuration",
    }


def build_plan(source: Path, vertical_pixels_per_degree: float, *, projection_evidence: str,
               crop_evidence: str, horizontal_pixels_per_degree: float | None = None,
               rates_mbps=RATES_MBPS, geometries=GEOMETRIES, codecs=CODECS,
               crops=None, fixture: bool = False, display_eye=fb.DISPLAY_EYE) -> dict:
    """Freeze an NVENC matrix while reusing all frame-bank geometry controls."""
    if not codecs or any(codec not in CODECS for codec in codecs):
        raise ValueError("plan requires supported codecs")
    if not rates_mbps or any(not isinstance(x, int) or x <= 0 for x in rates_mbps):
        raise ValueError("plan requires positive integer rates")
    _require_jpeg_full_y4m(source)
    # The base plan remains the authoritative source/crop/calibration validator.
    base = fb.build_plan(source, vertical_pixels_per_degree,
                         horizontal_pixels_per_degree=horizontal_pixels_per_degree,
                         projection_evidence=projection_evidence, crop_evidence=crop_evidence,
                         fixture=fixture, wavelets=("haar",), rates_mbps=tuple(rates_mbps),
                         geometries=tuple(geometries), crops=crops, display_eye=display_eye)
    cells = []
    base_calibration = base["hvs_calibration"]["codec_cells"]
    for codec in codecs:
        for cell in base["cells"]:
            row = dict(cell)
            row.pop("wavelet", None)
            row["codec"] = codec
            row["nvenc_profile"] = profile(codec, row["rate_mbps"], row["fps"])
            cells.append(row)
    # Frame-bank calibration is indexed by cell, so repeat the base geometry
    # mapping in the same codec-major order as the resulting cells.
    base["hvs_calibration"]["codec_cells"] = [copy.deepcopy(item) for _ in codecs for item in base_calibration]
    base.update({"schema": SCHEMA, "kind": "nvenc_frame_bank", "cells": cells,
                 "proxy": {"kind": "offline_nvenc_low_delay_cbr",
                           "live_alvr_configuration_verified": False,
                           "quest_decoder_throughput_verified": False}})
    return base


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA or plan.get("kind") != "nvenc_frame_bank":
        raise ValueError("not an NVENC frame-bank schema-1 manifest")
    normalized = dict(plan)
    normalized["schema"] = fb.SCHEMA
    normalized["kind"] = "pyrowave_frame_bank"
    cells = []
    for cell in plan.get("cells", []):
        if not isinstance(cell, dict):
            raise ValueError("NVENC cell is invalid")
        codec = cell.get("codec")
        if codec not in CODECS:
            raise ValueError("NVENC cell codec is unsupported")
        expected = profile(codec, cell.get("rate_mbps"), cell.get("fps"))
        if cell.get("nvenc_profile") != expected:
            raise ValueError("NVENC profile drifted")
        copied = dict(cell)
        copied.pop("codec", None); copied.pop("nvenc_profile", None)
        copied["wavelet"] = "haar"  # only to invoke the shared manifest validator
        cells.append(copied)
    normalized["cells"] = cells
    fb.validate_plan(normalized)
    if plan.get("proxy") != {"kind": "offline_nvenc_low_delay_cbr",
                             "live_alvr_configuration_verified": False,
                             "quest_decoder_throughput_verified": False}:
        raise ValueError("NVENC proxy scope is missing or drifted")
    return plan


def _ext(codec: str) -> str:
    return "hevc" if codec == "hevc" else "av1"


def _muxer(codec: str) -> str:
    # FFmpeg 6.1 writes raw AV1 OBUs through the ``obu`` muxer, not ``av1``.
    return "hevc" if codec == "hevc" else "obu"


def encode_command(ffmpeg: Path | str, reference: Path, output: Path, cell: dict) -> list[str]:
    p = cell["nvenc_profile"]
    return [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(reference),
            "-map", "0:v:0", "-frames:v", str(cell["identity_count"]), *p["ffmpeg_arguments"],
            "-f", _muxer(cell["codec"]), str(output)]


def decode_command(ffmpeg: Path | str, bitstream: Path, output: Path, frames: int, native_pix_fmt: str) -> list[str]:
    # ``+`` makes FFmpeg reject a conversion instead of selecting a compatible
    # output format. Colour/siting tags are deliberately not forced here.
    if native_pix_fmt not in ("yuv420p", "yuvj420p"):
        raise ValueError("NVENC decoded native 8-bit 4:2:0 format is unsupported")
    return [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(bitstream),
            "-map", "0:v:0", "-frames:v", str(frames), "-pix_fmt", "+" + native_pix_fmt,
            "-fps_mode", "passthrough", "-f", "rawvideo", str(output)]


def probe_command(ffprobe: Path | str, bitstream: Path, output: Path) -> list[str]:
    return [str(ffprobe), "-v", "error", "-count_frames", "-show_streams", "-show_frames",
            "-show_entries", "stream=codec_name,width,height,pix_fmt,color_range,chroma_location,color_space,color_primaries,color_transfer,avg_frame_rate,r_frame_rate,nb_read_frames:frame=pict_type,width,height,pix_fmt",
            "-of", "json", "-o", str(output), str(bitstream)]


def validate_probe(value: dict, cell: dict, frames: int) -> dict:
    """Validate reconstructed planes; preserve elementary-stream metadata as observed.

    Raw HEVC/OBU streams frequently omit VUI timing and chroma location. Unknown
    metadata cannot be upgraded to a claim about presentation; a known conflicting
    range or SDR colour signal is still a hard failure.
    """
    streams = value.get("streams") if isinstance(value, dict) else None
    if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
        raise ValueError("NVENC probe did not report exactly one video stream")
    stream = streams[0]
    expected = {"codec_name": cell["codec"], "width": cell["stereo_width"],
                "height": cell["eye_height"]}
    for key, wanted in expected.items():
        if stream.get(key) != wanted:
            raise ValueError("NVENC bitstream metadata mismatch: " + key)
    native_formats = ("yuv420p", "yuvj420p")  # yuvj420p is FFmpeg's full-range 8-bit alias.
    if stream.get("pix_fmt") not in native_formats:
        raise ValueError("NVENC bitstream native 8-bit 4:2:0 format mismatch")
    if str(stream.get("nb_read_frames")) != str(frames):
        raise ValueError("NVENC bitstream frame count mismatch")
    pictures = value.get("frames")
    if not isinstance(pictures, list) or len(pictures) != frames:
        raise ValueError("NVENC bitstream picture count mismatch")
    types = [row.get("pict_type") for row in pictures if isinstance(row, dict)]
    if len(types) != frames or any(t not in ("I", "P") for t in types):
        raise ValueError("NVENC bitstream contains B or unknown picture type")
    if any(row.get("width") != cell["stereo_width"] or row.get("height") != cell["eye_height"]
           or row.get("pix_fmt") != stream.get("pix_fmt") for row in pictures):
        raise ValueError("NVENC decoded frame format mismatch")
    observed = {key: stream.get(key, "unknown") for key in
                ("color_range", "chroma_location", "color_space", "color_primaries", "color_transfer",
                 "avg_frame_rate", "r_frame_rate")}
    if observed["color_range"] not in (None, "unknown", "pc"):
        raise ValueError("NVENC bitstream range contradicts source plane contract")
    for key, wanted in (("color_space", "bt709"), ("color_primaries", "bt709"),
                        ("color_transfer", "iec61966-2-1")):
        if observed[key] not in (None, "unknown", wanted):
            raise ValueError("NVENC bitstream colour metadata contradicts proxy assumption")
    return {"codec": stream["codec_name"], "geometry": [stream["width"], stream["height"]],
            "pix_fmt": stream["pix_fmt"], "frames": frames, "picture_types": {t: types.count(t) for t in sorted(set(types))},
            "ffprobe_observed_metadata": observed, "external_sequence_rate": f"{cell['fps']}/1",
            "bitstream_timing_confirmed": False}


def _run_json(guard, command, output, directory, timeout):
    code, out, err = guard.run(command, cwd=directory, env=os.environ.copy(), timeout_s=timeout)
    if code:
        raise RuntimeError("ffprobe_failed")
    try:
        return json.loads(Path(output).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("ffprobe did not emit valid JSON") from exc


def _require_jpeg_full_y4m(path: Path) -> dict:
    """Reject a decoder that substituted MPEG-2 siting or lost full-range tags."""
    with Path(path).open("rb") as stream:
        header = stream.readline(4097).decode("ascii", "replace").strip()
    tokens = set(header.split())
    if "C420jpeg" not in tokens or "XCOLORRANGE=FULL" not in tokens:
        raise ValueError("decoded_y4m_chroma_or_range_mismatch")
    return {"header": header, "chroma": "C420jpeg", "color_range": "FULL"}


def wrap_raw_payload(raw: Path, info: fb.Y4MInfo, out: Path) -> dict:
    """Make a Y4M scoring view without changing one decoded sample byte."""
    expected = info.frame_bytes * info.frames
    if Path(raw).stat().st_size != expected:
        raise ValueError("decoded_raw_byte_count_mismatch")
    source_hash = hashlib.sha256(); frame_hashes = []
    with Path(raw).open("rb") as source, fb._open_writer(out, info) as target:
        for _ in range(info.frames):
            payload = source.read(info.frame_bytes)
            if len(payload) != info.frame_bytes:
                raise ValueError("decoded_raw_byte_count_mismatch")
            source_hash.update(payload)
            target.write(b"FRAME\n" + payload)
            frame_hashes.append(hashlib.sha256(payload).hexdigest())
        if source.read(1):
            raise ValueError("decoded_raw_byte_count_mismatch")
    wrapped_hashes = [digest for _, _, digest in fb.iter_y4m(out, info)]
    if wrapped_hashes != frame_hashes:
        raise ValueError("decoded_raw_payload_changed")
    return {"raw_payload_sha256": source_hash.hexdigest(), "frame_payload_sha256": frame_hashes,
            "byte_identical": True, "external_y4m_contract": {"chroma": "C420jpeg", "color_range": "FULL",
            "fps": [info.fps_num, info.fps_den]}}


def _same_frame_scores(plan, cell_index, cell, tools, guard, directory, source, source_info,
                       decoded, decoded_info, reference, ref_info, timeout, keep_artifacts):
    """Use exactly the established display and fixed-crop score path."""
    common = dict(frames=ref_info.frames, guard=guard, env=os.environ.copy(), timeout_s=timeout)
    codec_ppd = plan["hvs_calibration"]["codec_cells"][cell_index]["vertical_pixels_per_degree"]
    row = {"codec_only": fb.score_pair(tools, decoded, reference, directory, codec_ppd,
                                        image_height=ref_info.height, **common)}
    display_ref = directory / "source-display.y4m"; display_dec = directory / "decoded-display.y4m"
    fb._write_display(source, source_info, display_ref, plan["presentation_eye"])
    fb._write_display(decoded, decoded_info, display_dec, plan["presentation_eye"])
    row["displayed"] = fb.score_pair(tools, display_dec, display_ref, directory,
                                      plan["hvs_calibration"]["display"]["vertical_pixels_per_degree"],
                                      image_height=plan["presentation_eye"][1], **common)
    display_info = fb.inspect_y4m(display_ref); decoded_display_info = fb.inspect_y4m(display_dec)
    row["crops"] = {}
    for crop_index, crop in enumerate(plan["crops"]):
        rp = directory / f"crop-{crop['name']}-reference.y4m"; gp = directory / f"crop-{crop['name']}-decoded.y4m"
        riter = fb.iter_y4m(display_ref, display_info); giter = fb.iter_y4m(display_dec, decoded_display_info)
        _, first_ref, _ = next(riter); _, first_dec, _ = next(giter); riter.close(); giter.close()
        c0 = fb.crop_y4m(first_ref, display_info, crop)
        crop_info = fb.Y4MInfo(c0[0].shape[1], c0[0].shape[0], display_info.fps_num,
                               display_info.fps_den, display_info.chroma, display_info.color_range,
                               fb._frame_bytes(c0[0].shape[1], c0[0].shape[0], display_info.chroma), display_info.frames)
        with fb._open_writer(rp, crop_info) as rf, fb._open_writer(gp, crop_info) as gf:
            for (_, rplanes, _), (_, gplanes, _) in zip(fb.iter_y4m(display_ref, display_info),
                                                        fb.iter_y4m(display_dec, decoded_display_info)):
                fb._write_frame(rf, crop_info, fb.crop_y4m(rplanes, display_info, crop))
                fb._write_frame(gf, crop_info, fb.crop_y4m(gplanes, display_info, crop))
        calibration = plan["hvs_calibration"]["crops"][crop_index]
        row["crops"][crop["name"]] = fb.score_pair(tools, gp, rp, directory,
            calibration["vertical_pixels_per_degree"], image_height=crop_info.height, **common)
        fb._grid_png(directory / "grids" / f"PRIVATE-{crop['name']}.png", c0,
                     fb.crop_y4m(first_dec, display_info, crop))
        if not keep_artifacts:
            rp.unlink(); gp.unlink()
    if not keep_artifacts:
        display_ref.unlink(); display_dec.unlink()
    return row


def run_plan(plan_path: Path, source: Path, private_out: Path, tools: dict, window: Path, *,
             command_timeout_s: float = 900, keep_artifacts: bool = False, supervised: bool = True,
             tools_metadata: Path | None = None) -> dict:
    """Run a frozen proxy matrix through an owner-supervised quality lease."""
    raw = Path(plan_path).read_bytes(); plan = validate_plan(json.loads(raw))
    source = Path(source); private_out = fb._private_path(private_out)
    if not supervised:
        raise ValueError("NVENC frame bank requires explicit owner-supervised lease")
    if private_out.exists():
        raise FileExistsError("private output must be fresh")
    needed = {name: _tool(tools.get(name)) for name in ("ffmpeg", "ffprobe", "psnr_hvs_m_h")}
    if tools_metadata is None:
        raise ValueError("qualified frame-bank tools metadata is required")
    metadata = Path(tools_metadata)
    bundle = metadata.resolve().parent
    build_tools = {"encode": bundle / "pyrowave-encode.exe", "decode": bundle / "pyrowave-decode.exe",
                   "psnr_hvs_m_h": bundle / "pyrowave-psnr-hvs-m.exe"}
    build_provenance = fb.verify_tools_build(build_tools, metadata)
    if fb.sha256_file(needed["psnr_hvs_m_h"]) != fb.sha256_file(build_tools["psnr_hvs_m_h"]):
        raise ValueError("selected HVS scorer differs from qualified frame-bank bundle")
    guard = fb.WindowGuard(window, supervised=True); guard.status()
    source_header = _require_jpeg_full_y4m(source)
    source_info = fb.inspect_y4m(source)
    if fb.sha256_file(source) != plan["source"]["sha256"] or source_info.frames != plan["source"]["frames"]:
        raise ValueError("source differs from frozen NVENC plan")
    private_out.mkdir(parents=True)
    result = {"schema": SCHEMA, "kind": "nvenc_frame_bank_result", "complete": False,
              "failure_reasons": [], "frozen_plan_sha256": hashlib.sha256(raw).hexdigest(),
              "source_sha256_start": fb.sha256_file(source), "source_sha256_end": None,
              "tool_provenance_start": {name: {"basename": path.name, "sha256": fb.sha256_file(path)} for name, path in needed.items()},
              "tool_provenance_end": None, "projection": plan["projection"],
              "projection_evidence": plan["projection_evidence"], "crop_definitions": plan["crops"],
              "proxy": plan["proxy"], "source_y4m_header": source_header,
              "tools_build_provenance": build_provenance, "cells": []}
    scoring_tools = {"ffmpeg": needed["ffmpeg"], "psnr_hvs_m_h": needed["psnr_hvs_m_h"]}
    try:
        result["hvs_gpu_sanity"] = fb.hvs_gpu_sanity(needed["psnr_hvs_m_h"], private_out / "scorer-sanity",
            plan["projection"]["vertical_pixels_per_degree"], guard, os.environ.copy(), command_timeout_s)
    except (PermissionError, TimeoutError, ValueError, RuntimeError):
        result["failure_reasons"].append("hvs_gpu_sanity_failed")
    for index, cell in enumerate(plan["cells"] if not result["failure_reasons"] else []):
        directory = private_out / f"cell-{index:02d}-{cell['codec']}-{cell['rate_mbps']}-{cell['eye_width']}x{cell['eye_height']}"
        directory.mkdir(); row = dict(cell); ref = directory / "reference.y4m"; stream = directory / ("encoded." + _ext(cell["codec"])); raw_decoded = directory / "decoded.raw"; decoded = directory / "decoded.y4m"
        try:
            ref_info, identities = fb._stream_reference(source, source_info, cell, ref)
            row["identity_count"] = len(identities)
            if [x["source_sha256"] for x in identities] != [x["source_sha256"] for x in plan["source"]["frame_identity"]]:
                raise ValueError("source_frame_identity_drift")
            code, _, _ = guard.run(encode_command(needed["ffmpeg"], ref, stream, row), cwd=directory,
                                   env=os.environ.copy(), timeout_s=command_timeout_s)
            if code or not stream.is_file() or stream.stat().st_size <= 0:
                raise RuntimeError("nvenc_encode_failed")
            probe_json = directory / "bitstream-probe.json"
            probe = validate_probe(_run_json(guard, probe_command(needed["ffprobe"], stream, probe_json), probe_json, directory, command_timeout_s), row, ref_info.frames)
            row["bitstream"] = {**probe, "actual_elementary_stream_bytes": stream.stat().st_size,
                "actual_mbps_external_f90_normalization": stream.stat().st_size * 8 * cell["fps"] / ref_info.frames / 1_000_000}
            code, _, _ = guard.run(decode_command(needed["ffmpeg"], stream, raw_decoded, ref_info.frames, probe["pix_fmt"]), cwd=directory,
                                   env=os.environ.copy(), timeout_s=command_timeout_s)
            if code or not raw_decoded.is_file():
                raise RuntimeError("nvenc_decode_failed")
            row["decoded_raw_wrapper"] = wrap_raw_payload(raw_decoded, ref_info, decoded)
            decoded_info = fb.inspect_y4m(decoded)
            fb._assert_same_frames(ref, decoded, ref_info)
            row["decoded_frame_identity"] = [{"cell_frame": i, "source_frame": x["source_frame"],
                "reference_sha256": x["reference_sha256"], "decoded_sha256": digest}
                for (i, _, digest), x in zip(fb.iter_y4m(decoded, decoded_info), identities)]
            if len(row["decoded_frame_identity"]) != ref_info.frames:
                raise ValueError("decoded_identity_or_geometry_mismatch")
            row.update(_same_frame_scores(plan, index, cell, scoring_tools, guard, directory, source,
                       source_info, decoded, decoded_info, ref, ref_info, command_timeout_s, keep_artifacts))
        except (PermissionError, TimeoutError, ValueError, RuntimeError) as exc:
            row["error"] = str(exc) if str(exc) in {"nvenc_encode_failed", "nvenc_decode_failed", "decoded_identity_or_geometry_mismatch"} else "cell_failed"
            result["failure_reasons"].append(row["error"])
        result["cells"].append(row)
        (private_out / "nvenc-framebank-progress.json").write_text(fb.report_json(result), encoding="utf-8")
        if not keep_artifacts:
            for path in (ref, stream, raw_decoded, decoded, directory / "bitstream-probe.json"): path.unlink(missing_ok=True)
        if row.get("error"):
            break
    result["source_sha256_end"] = fb.sha256_file(source)
    result["tool_provenance_end"] = {name: {"basename": path.name, "sha256": fb.sha256_file(path)} for name, path in needed.items()}
    if result["source_sha256_end"] != result["source_sha256_start"]: result["failure_reasons"].append("source_changed_during_run")
    if result["tool_provenance_end"] != result["tool_provenance_start"]: result["failure_reasons"].append("tool_changed_during_run")
    try:
        if fb.verify_tools_build(build_tools, metadata) != build_provenance:
            result["failure_reasons"].append("tool_build_provenance_changed_during_run")
    except (OSError, ValueError, KeyError):
        result["failure_reasons"].append("tool_build_provenance_changed_during_run")
    if hashlib.sha256(Path(plan_path).read_bytes()).hexdigest() != result["frozen_plan_sha256"]: result["failure_reasons"].append("plan_changed_during_run")
    result["complete"] = not result["failure_reasons"] and len(result["cells"]) == len(plan["cells"])
    (private_out / "nvenc-framebank-private.json").write_text(fb.report_json(result), encoding="utf-8")
    return result


def sanitized_report(result: dict) -> dict:
    keep = ("codec", "rate_mbps", "fps", "eye_width", "eye_height", "encoded_chroma", "cap_bytes", "bits_per_pixel", "nvenc_profile", "bitstream", "decoded_raw_wrapper", "codec_only", "displayed", "crops", "error")
    return {"schema": SCHEMA, "kind": "nvenc_frame_bank_sanitized", "complete": result.get("complete") is True,
            "failure_reasons": list(result.get("failure_reasons", [])), "frozen_plan_sha256": result.get("frozen_plan_sha256"),
            "source_sha256": result.get("source_sha256_end"), "source_y4m_header": result.get("source_y4m_header"), "tool_provenance": result.get("tool_provenance_end"), "tools_build_provenance": result.get("tools_build_provenance"),
            "hvs_gpu_sanity": result.get("hvs_gpu_sanity"), "projection": result.get("projection"), "crop_definitions": result.get("crop_definitions"), "proxy": result.get("proxy"),
            "cells": [{key: row.get(key) for key in keep} for row in result.get("cells", [])],
            "optical_latency_ms": None, "display_fps": None}


def _crops_argument(value: str):
    return fb.parse_crops_argument(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    for name in ("source", "projection-evidence", "crop-evidence", "out"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--vertical-pixels-per-degree", type=float, required=True)
    p.add_argument("--horizontal-pixels-per-degree", type=float)
    p.add_argument("--crops", required=True)
    r = sub.add_parser("run")
    for name in ("plan", "source", "private-out", "report", "window", "ffmpeg", "ffprobe", "psnr-hvs-m-h", "tools-metadata"):
        r.add_argument("--" + name, required=True)
    r.add_argument("--command-timeout-s", type=float, default=900)
    r.add_argument("--keep-artifacts", action="store_true")
    r.add_argument("--supervised", action="store_true", help="required owner-supervised PC-only lease")
    args = parser.parse_args(argv)
    if args.command == "plan":
        plan = build_plan(Path(args.source), args.vertical_pixels_per_degree,
                          horizontal_pixels_per_degree=args.horizontal_pixels_per_degree,
                          projection_evidence=args.projection_evidence, crop_evidence=args.crop_evidence,
                          crops=_crops_argument(args.crops))
        Path(args.out).write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print("wrote frozen NVENC proxy plan; no codec or scorer ran")
        return 0
    result = run_plan(Path(args.plan), Path(args.source), Path(args.private_out),
                      {"ffmpeg": args.ffmpeg, "ffprobe": args.ffprobe, "psnr_hvs_m_h": args.psnr_hvs_m_h},
                      Path(args.window), command_timeout_s=args.command_timeout_s,
                      keep_artifacts=args.keep_artifacts, supervised=args.supervised,
                      tools_metadata=Path(args.tools_metadata))
    Path(args.report).write_text(fb.report_json(sanitized_report(result)), encoding="utf-8")
    print("wrote sanitized NVENC report: complete=" + str(result["complete"]))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

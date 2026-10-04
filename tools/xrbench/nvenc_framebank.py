"""Offline NVENC frame-bank adapter.

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
import re
import time
from pathlib import Path

import numpy as np

from . import framebank as fb

SCHEMA = 2
CODECS = ("h264", "hevc", "av1")
DEFAULT_CODECS = ("hevc", "av1")
RATES_MBPS = (200, 500, 800, 1000)
GEOMETRIES = ((3072, 3232), (2560, 2688))

# Schema-1 plans remain readable so the earlier, unexecuted Q3 plan is not
# silently rewritten.  New plans pin every requested encoder property here.
_CODEC_DEFAULTS = {
    "h264": {"encoder": "h264_nvenc", "pix_fmt": "yuv420p", "profile": "high"},
    "hevc": {"encoder": "hevc_nvenc", "pix_fmt": "p010le", "profile": "main10"},
    "av1": {"encoder": "av1_nvenc", "pix_fmt": "p010le", "profile": "main"},
}
_LAYOUTS = ("stereo_sbs", "dual_eye")


def foveation_transform_descriptor(*, profile: str, softness: float, blur_only: bool) -> dict:
    """Frozen Q3b source-transform descriptor; WO-8 owns its implementation."""
    if profile not in ("light", "medium", "h264fit"):
        raise ValueError("unknown foveation profile")
    if not isinstance(softness, (int, float)) or not math.isfinite(softness) or not 0 <= softness <= 1:
        raise ValueError("foveation softness must be in [0, 1]")
    if not isinstance(blur_only, bool):
        raise ValueError("foveation blur_only must be boolean")
    return {"kind": "wo8_foveation", "profile": profile, "softness": float(softness),
            "blur_only": blur_only}


def revised_q3a_cells() -> tuple[dict, ...]:
    """The complete 15-cell Q3a contract, shared with the PyroWave runner.

    This adapter executes only the ten NVENC cells.  The five PyroWave rows are
    returned here so the combined report cannot silently omit them or mistake a
    codec-specific runner's scope for the whole Q3a matrix.
    """
    return (
        {"label": "h264-dual-p7-400", "runner": "nvenc", "codec": "h264", "layout": "dual_eye", "mbps": 400, "preset": "p7", "aq": False, "geometry": "crop"},
        {"label": "h264-dual-p7-700", "runner": "nvenc", "codec": "h264", "layout": "dual_eye", "mbps": 700, "preset": "p7", "aq": False, "geometry": "crop"},
        {"label": "h264-dual-p4-700", "runner": "nvenc", "codec": "h264", "layout": "dual_eye", "mbps": 700, "preset": "p4", "aq": False, "geometry": "crop"},
        {"label": "h264-dual-p7-aq-700", "runner": "nvenc", "codec": "h264", "layout": "dual_eye", "mbps": 700, "preset": "p7", "aq": True, "geometry": "crop"},
        {"label": "hevc-main10-p7-200", "runner": "nvenc", "codec": "hevc", "layout": "stereo_sbs", "mbps": 200, "preset": "p7", "aq": False, "geometry": "crop"},
        {"label": "hevc-main10-p4-200", "runner": "nvenc", "codec": "hevc", "layout": "stereo_sbs", "mbps": 200, "preset": "p4", "aq": False, "geometry": "crop"},
        {"label": "av1-main10-p7-200", "runner": "nvenc", "codec": "av1", "layout": "stereo_sbs", "mbps": 200, "preset": "p7", "aq": False, "geometry": "crop"},
        {"label": "av1-main10-p4-200", "runner": "nvenc", "codec": "av1", "layout": "stereo_sbs", "mbps": 200, "preset": "p4", "aq": False, "geometry": "crop"},
        {"label": "pyrowave-haar-1000", "runner": "pyrowave", "codec": "pyrowave", "wavelet": "haar", "mbps": 1000, "geometry": "crop"},
        {"label": "pyrowave-53-800", "runner": "pyrowave", "codec": "pyrowave", "wavelet": "53", "mbps": 800, "geometry": "crop"},
        {"label": "pyrowave-53-1000", "runner": "pyrowave", "codec": "pyrowave", "wavelet": "53", "mbps": 1000, "geometry": "crop"},
        {"label": "pyrowave-97-800", "runner": "pyrowave", "codec": "pyrowave", "wavelet": "97", "mbps": 800, "geometry": "crop"},
        {"label": "pyrowave-97-1000", "runner": "pyrowave", "codec": "pyrowave", "wavelet": "97", "mbps": 1000, "geometry": "crop"},
        {"label": "h264-dual-p7-700-full", "runner": "nvenc", "codec": "h264", "layout": "dual_eye", "mbps": 700, "preset": "p7", "aq": False, "geometry": "full_fov"},
        {"label": "hevc-main10-p7-200-full", "runner": "nvenc", "codec": "hevc", "layout": "stereo_sbs", "mbps": 200, "preset": "p7", "aq": False, "geometry": "full_fov"},
    )


def revised_q3b_cells() -> tuple[dict, ...]:
    """Published ten-cell Q3b matrix; rates are total stream rates."""
    pyro = lambda label, wavelet, profile, softness, blur=False: {
        "label": label, "runner": "pyrowave", "codec": "pyrowave", "wavelet": wavelet,
        "mbps_total": 1000, "profile": profile, "softness": softness, "blur_only": blur}
    return (
        pyro("pyrowave-97-light-s0-1000", "97", "light", 0.0),
        pyro("pyrowave-97-light-s05-1000", "97", "light", 0.5),
        pyro("pyrowave-97-light-s1-1000", "97", "light", 1.0),
        pyro("pyrowave-53-light-s05-1000", "53", "light", 0.5),
        pyro("pyrowave-53-medium-s05-1000", "53", "medium", 0.5),
        pyro("pyrowave-97-medium-s05-1000", "97", "medium", 0.5),
        {"label":"h264-h264fit-s05-700", "runner":"nvenc", "codec":"h264", "layout":"stereo_sbs",
         "mbps_total":700, "preset":"p7", "profile":"h264fit", "softness":.5, "blur_only":False},
        pyro("pyrowave-97-h264fit-s05-1000", "97", "h264fit", 0.5),
        {"label":"h264-dual-blur-light-s05-700", "runner":"nvenc", "codec":"h264", "layout":"dual_eye",
         "mbps_total":700, "preset":"p7", "profile":"light", "softness":.5, "blur_only":True},
        pyro("pyrowave-97-blur-light-s05-1000", "97", "light", .5, True),
    )


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


def profile(codec: str, rate_mbps: int, fps: int = fb.FPS, *, preset: str = "p4",
            spatial_aq: bool = False, layout: str = "stereo_sbs") -> dict:
    """Return a pinned low-delay NVENC profile without probing or encoding.

    The profile is an explicitly pinned offline proxy.  It records process
    completion timing later, never a made-up GPU execution time.
    """
    if codec not in CODECS:
        raise ValueError("codec must be h264, hevc or av1")
    if preset not in ("p4", "p7"):
        raise ValueError("NVENC preset must be p4 or p7")
    if not isinstance(spatial_aq, bool) or layout not in _LAYOUTS:
        raise ValueError("invalid AQ or stream layout")
    if spatial_aq and codec != "h264":
        raise ValueError("only the requested H.264 AQ cell enables spatial AQ")
    vbv = _vbv_bits(rate_mbps, fps)
    defaults = _CODEC_DEFAULTS[codec]
    args = [
        "-c:v", defaults["encoder"], "-preset", preset, "-tune", "ull", "-rc", "cbr",
        "-b:v", f"{rate_mbps}M", "-minrate", f"{rate_mbps}M",
        "-maxrate", f"{rate_mbps}M", "-bufsize", str(vbv),
        "-bf", "0", "-g", str(fps), "-forced-idr", "1",
        "-rc-lookahead", "0", "-zerolatency", "1", "-delay", "0",
        "-strict_gop", "1", "-multipass", "disabled", "-ldkfs", "1",
        "-pix_fmt", defaults["pix_fmt"], "-color_range", "pc", "-chroma_sample_location", "center",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "iec61966-2-1",
    ]
    if codec in ("h264", "hevc"):
        args[2:2] = ["-profile:v", defaults["profile"]]
    if spatial_aq:
        args.extend(("-spatial_aq", "1", "-aq-strength", "8"))
    return {
        "codec": codec, "encoder": defaults["encoder"], "rate_control": "cbr",
        "requested_mbps": rate_mbps, "fps": fps, "gop": fps,
        "b_frames": 0, "lookahead_frames": 0, "preset": preset, "tune": "ull",
        "vbv_bits": vbv, "vbv_frames_nominal": 1.1, "multipass": "disabled",
        "low_delay": {"zero_latency": True, "delay_frames": 0, "strict_gop": True, "low_delay_key_frame_scale": 1},
        "layout": layout, "stream_count": 2 if layout == "dual_eye" else 1,
        "spatial_aq": spatial_aq, "aq_strength": 8 if spatial_aq else None,
        "pixel_format": defaults["pix_fmt"], "native_decode_format": (
            "8bit_420_observed" if defaults["pix_fmt"] == "yuv420p" else "10bit_420_observed"),
        "source_plane_contract": "C420jpeg_FULL",
        "score_pixel_format": "yuv420p",
        # Y4M source samples are 8-bit full range. Make the encoder upload
        # conversion explicit for Main10 rather than accepting FFmpeg's
        # implicit swscale defaults.
        "encode_upconvert_filter": (
            "scale=in_range=full:out_range=full:flags=bilinear+accurate_rnd:sws_dither=none,format=p010le"
            if defaults["pix_fmt"] == "p010le" else None),
        # This single scoring conversion is deliberately full-range to
        # full-range, bilinear, accurately rounded and non-dithered.  It is
        # recorded rather than relying on FFmpeg's implicit 10->8 conversion.
        "score_downconvert_filter": (
            "scale=in_range=full:out_range=full:flags=bilinear+accurate_rnd:sws_dither=none,format=yuv420p"
            if defaults["pix_fmt"] == "p010le" else None),
        "color_metadata_proxy_assumption": {"primaries": "bt709", "matrix": "bt709", "transfer": "iec61966-2-1"},
        "backend_padding_policy": "FFmpeg-6.1-NVENC-CBR-backend-dependent; AV1 source enables bitstream padding; actual bytes include any padding",
        "ffmpeg_arguments": args,
        "comparison_scope": "offline_nvenc_proxy_not_live_alvr_configuration",
    }


def build_plan(source: Path, vertical_pixels_per_degree: float, *, projection_evidence: str,
               crop_evidence: str, horizontal_pixels_per_degree: float | None = None,
               rates_mbps=RATES_MBPS, geometries=GEOMETRIES, codecs=DEFAULT_CODECS,
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
                 "source_adapter": {"kind": "identity", "geometry": None, "future_transform": None},
                 "proxy": {"kind": "offline_nvenc_low_delay_cbr",
                           "live_alvr_configuration_verified": False,
                           "quest_decoder_throughput_verified": False}})
    return base


def _revised_cell(base: dict, *, codec: str, rate_mbps: int, preset: str,
                  layout: str, spatial_aq: bool, label: str,
                  source_geometry: str) -> dict:
    """Create one revision-2026-10-04 NVENC cell from frozen base geometry."""
    if source_geometry not in ("crop", "full_fov"):
        raise ValueError("source geometry must be crop or full_fov")
    row = dict(base)
    row.update({"codec": codec, "rate_mbps": rate_mbps, "label": label,
                "source_geometry": source_geometry,
                "nvenc_profile": profile(codec, rate_mbps, base["fps"], preset=preset,
                                         layout=layout, spatial_aq=spatial_aq)})
    row["cap_bytes"] = fb.cap_bytes(rate_mbps, row["fps"])
    row["bits_per_pixel"] = fb.bpp(row["cap_bytes"], row["eye_width"], row["eye_height"])
    if layout == "dual_eye":
        if rate_mbps % 2:
            raise ValueError("dual-eye total rate must split evenly")
        row["per_stream_mbps"] = rate_mbps // 2
    return row


def _canonical_crop_geometry(value: dict) -> dict:
    """Accept the public geometry record without weakening its fixed pixels.

    ``fence_metrics.crop_geometry`` returns executable geometry without a
    ``kind`` member, while the public Q3 artifact wraps that value under
    ``geometry``.  Add only this schema discriminator after proving the exact
    crop fields exist; coordinates and tangents are copied untouched.
    """
    if not isinstance(value, dict):
        raise ValueError("revised Q3a requires frozen per-eye crop geometry")
    geometry = copy.deepcopy(value)
    if geometry.get("kind") is None:
        required = {"source_eye", "target_eye", "eyes"}
        if not required.issubset(geometry):
            raise ValueError("revised Q3a requires frozen per-eye crop geometry")
        geometry["kind"] = "per_eye_crop"
    return geometry


def build_revised_q3a_plan(source: Path, vertical_pixels_per_degree: float, *,
                           projection_evidence: str, crop_evidence: str,
                           crop_geometry: dict, fence_rectangle: dict, crops, fixture: bool = False,
                           horizontal_pixels_per_degree: float | None = None,
                           full_eye: tuple[int, int] = fb.DISPLAY_EYE) -> dict:
    """Freeze the revised Q3a NVENC subset.

    ``crop_geometry`` is the audited output of ``fence_metrics.crop_geometry``.
    It is deliberately supplied by the geometry owner, rather than guessed
    from resolution multipliers in this codec adapter.  The runtime consumes it
    through :mod:`xrbench.source_adapter`; Q3b can add a transform descriptor
    without changing codec-cell provenance.
    """
    _require_jpeg_full_y4m(source)
    # The public Q3 geometry artifact wraps the executable geometry and fence
    # evidence; accepting it directly keeps the plan bound to that record.
    if isinstance(crop_geometry, dict) and isinstance(crop_geometry.get("geometry"), dict):
        public_record = crop_geometry
        crop_geometry = public_record["geometry"]
        if fence_rectangle is None and isinstance(public_record.get("fence"), dict):
            fence_rectangle = public_record["fence"]
    if isinstance(fence_rectangle, dict) and isinstance(fence_rectangle.get("original"), dict):
        fence_rectangle = fence_rectangle["original"]
    if isinstance(fence_rectangle, dict) and isinstance(fence_rectangle.get("fence"), dict):
        fence_rectangle = fence_rectangle["fence"].get("original")
    crop_geometry = _canonical_crop_geometry(crop_geometry)
    if not isinstance(crop_geometry, dict) or crop_geometry.get("kind") != "per_eye_crop":
        raise ValueError("revised Q3a requires frozen per-eye crop geometry")
    crop_eye = tuple(crop_geometry.get("target_eye", ()))
    if crop_eye != (2624, 2776):
        raise ValueError("revised Q3a crop geometry must be 2624x2776 per eye")
    try:
        from . import fence_metrics
    except ImportError as exc:  # a source-only package error, before a lease opens
        raise ValueError("fence metrics module is unavailable") from exc
    if not isinstance(fence_rectangle, dict):
        raise ValueError("revised Q3a requires the frozen fence rectangle")
    mapped_fence = fence_metrics.map_rectangle(fence_rectangle, crop_geometry)
    if not mapped_fence["fully_contained"]:
        raise ValueError("fence rectangle is not fully contained by frozen crop geometry")
    # Use the normal frame-bank validator to freeze source identity, named
    # fixed crops and calibration.  Codec-cell score calibration is replaced
    # below for each requested source geometry.
    base = fb.build_plan(source, vertical_pixels_per_degree,
        horizontal_pixels_per_degree=horizontal_pixels_per_degree,
        projection_evidence=projection_evidence, crop_evidence=crop_evidence,
        fixture=fixture, wavelets=("haar",), rates_mbps=(200,),
        geometries=(crop_eye,), crops=crops, display_eye=full_eye)
    crop_base = dict(base["cells"][0])
    full_base = dict(crop_base)
    full_base.update({"eye_width": full_eye[0], "eye_height": full_eye[1],
                      "stereo_width": full_eye[0] * 2,
                      "bits_per_pixel": fb.bpp(fb.cap_bytes(200, fb.FPS), *full_eye)})
    definitions = (
        (crop_base, "h264", 400, "p7", "dual_eye", False, "h264-dual-p7-400", "crop"),
        (crop_base, "h264", 700, "p7", "dual_eye", False, "h264-dual-p7-700", "crop"),
        (crop_base, "h264", 700, "p4", "dual_eye", False, "h264-dual-p4-700", "crop"),
        (crop_base, "h264", 700, "p7", "dual_eye", True, "h264-dual-p7-aq-700", "crop"),
        (crop_base, "hevc", 200, "p7", "stereo_sbs", False, "hevc-main10-p7-200", "crop"),
        (crop_base, "hevc", 200, "p4", "stereo_sbs", False, "hevc-main10-p4-200", "crop"),
        (crop_base, "av1", 200, "p7", "stereo_sbs", False, "av1-main10-p7-200", "crop"),
        (crop_base, "av1", 200, "p4", "stereo_sbs", False, "av1-main10-p4-200", "crop"),
        (full_base, "h264", 700, "p7", "dual_eye", False, "h264-dual-p7-700-full", "full_fov"),
        (full_base, "hevc", 200, "p7", "stereo_sbs", False, "hevc-main10-p7-200-full", "full_fov"),
    )
    cells = [_revised_cell(cell, codec=codec, rate_mbps=rate, preset=preset,
                            layout=layout, spatial_aq=aq, label=label,
                            source_geometry=geometry)
             for cell, codec, rate, preset, layout, aq, label, geometry in definitions]
    # Framebank's historical codec calibration models resize-to-full-FOV. The
    # cropped geometry retains pixel density instead, so keep its score PPD
    # explicitly beside the legacy-compatible calibration record.
    for cell in cells:
        if cell["source_geometry"] == "crop":
            cell["score_vertical_pixels_per_degree"] = float(vertical_pixels_per_degree)
    calibration = []
    for cell in cells:
        height = cell["eye_height"]
        calibration.append(fb.hvs_calibration_for_vertical_ppd(
            vertical_pixels_per_degree * height / full_eye[1], height))
    base["hvs_calibration"]["codec_cells"] = calibration
    base.update({"schema": SCHEMA, "kind": "nvenc_frame_bank", "cells": cells,
                 "source_adapter": {"kind": "per_eye_crop", "geometry": copy.deepcopy(crop_geometry),
                                    "future_transform": None},
                 "fence_rectangles": {"full_fov": copy.deepcopy(fence_rectangle),
                                      "cropped": mapped_fence},
                 "q3_revision": "2026-10-04-q3a",
                 "score_windows": {"full_sequence": [1, 90], "temporal_sequence": [10, 89],
                                   "temporal_pair_convention": "t=11..89 (79 pairs)"},
                 "proxy": {"kind": "offline_nvenc_low_delay_cbr",
                           "live_alvr_configuration_verified": False,
                           "quest_decoder_throughput_verified": False}})
    return base


def with_foveation_source(plan: dict, *, profile: str, softness: float, blur_only: bool) -> dict:
    """Reject premature Q3b use until reduced-plane WO-8 scoring lands.

    A full-size forward+inverse warp would only blur/remap at the crop geometry;
    it cannot measure foveation's requested reduced-pixel encoder allocation.
    The later adapter must encode WO-8's reduced planes, reconstruct decoded
    planes, and compare sharp plus matching-blur references by band.
    """
    foveation_transform_descriptor(profile=profile, softness=softness, blur_only=blur_only)
    raise RuntimeError("Q3b reduced-plane adapter and band scoring are not implemented")


def _validate_source_adapter(plan: dict) -> None:
    adapter = plan.get("source_adapter")
    if adapter is None:  # schema-1 compatibility only
        if plan.get("schema") != 1:
            raise ValueError("NVENC source adapter is missing")
        return
    if not isinstance(adapter, dict) or set(adapter) != {"kind", "geometry", "future_transform"}:
        raise ValueError("NVENC source adapter schema drifted")
    if adapter["kind"] == "identity":
        if adapter["geometry"] is not None or adapter["future_transform"] is not None:
            raise ValueError("NVENC identity source adapter drifted")
        return
    if adapter["kind"] != "per_eye_crop":
        raise ValueError("NVENC source adapter is unsupported")
    transform = adapter["future_transform"]
    if transform is not None:
        try:
            if transform != foveation_transform_descriptor(profile=transform.get("profile"),
                                                            softness=transform.get("softness"),
                                                            blur_only=transform.get("blur_only")):
                raise ValueError
        except (AttributeError, ValueError, TypeError) as exc:
            raise ValueError("NVENC foveation transform drifted") from exc
    geometry = adapter["geometry"]
    if not isinstance(geometry, dict) or geometry.get("kind") != "per_eye_crop":
        raise ValueError("NVENC crop geometry is missing")
    eyes = geometry.get("eyes")
    if not isinstance(eyes, list) or len(eyes) != 2 or {x.get("eye") for x in eyes if isinstance(x, dict)} != {"left", "right"}:
        raise ValueError("NVENC crop geometry must freeze both eyes")


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or plan.get("schema") not in (1, SCHEMA) or plan.get("kind") != "nvenc_frame_bank":
        raise ValueError("not an NVENC frame-bank manifest")
    _validate_source_adapter(plan)
    if plan.get("q3_revision") in ("2026-10-04-q3a", "2026-10-04-q3b"):
        fences = plan.get("fence_rectangles")
        if not isinstance(fences, dict) or set(fences) != {"full_fov", "cropped"}:
            raise ValueError("revised Q3 fence rectangles are missing")
        if not isinstance(fences["full_fov"], dict) or not isinstance(fences["cropped"], dict):
            raise ValueError("revised Q3 fence rectangles are invalid")
        if fences["cropped"].get("fully_contained") is not True or not isinstance(fences["cropped"].get("mapped"), dict):
            raise ValueError("cropped fence rectangle must be fully contained")
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
        p = cell.get("nvenc_profile")
        if not isinstance(p, dict):
            raise ValueError("NVENC profile is missing")
        expected = profile(codec, cell.get("rate_mbps"), cell.get("fps"),
                           preset=p.get("preset", "p4"), spatial_aq=p.get("spatial_aq", False),
                           layout=p.get("layout", "stereo_sbs"))
        if cell.get("nvenc_profile") != expected:
            raise ValueError("NVENC profile drifted")
        if p["layout"] == "dual_eye":
            if cell.get("per_stream_mbps") != cell["rate_mbps"] // 2 or cell["rate_mbps"] % 2:
                raise ValueError("dual-eye rate split drifted")
        elif "per_stream_mbps" in cell:
            raise ValueError("single-stream cell must not declare a per-stream rate")
        score_ppd = cell.get("score_vertical_pixels_per_degree")
        if score_ppd is not None and (cell.get("source_geometry") != "crop" or
                                      not isinstance(score_ppd, (int, float)) or not math.isfinite(score_ppd) or score_ppd <= 0):
            raise ValueError("cropped score PPD is invalid")
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
    return {"h264": "h264", "hevc": "hevc", "av1": "av1"}[codec]


def _muxer(codec: str) -> str:
    # FFmpeg 6.1 writes raw AV1 OBUs through the ``obu`` muxer, not ``av1``.
    return {"h264": "h264", "hevc": "hevc", "av1": "obu"}[codec]


def encode_command(ffmpeg: Path | str, reference: Path, output: Path, cell: dict) -> list[str]:
    p = cell["nvenc_profile"]
    conversion = (["-vf", p["encode_upconvert_filter"]]
                  if p.get("encode_upconvert_filter") is not None else [])
    return [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "verbose", "-benchmark_all", "-debug_ts", "-i", str(reference),
            "-map", "0:v:0", "-frames:v", str(cell["identity_count"]), *conversion, *p["ffmpeg_arguments"],
            "-f", _muxer(cell["codec"]), str(output)]


def decode_command(ffmpeg: Path | str, bitstream: Path, output: Path, frames: int, native_pix_fmt: str) -> list[str]:
    # ``+`` makes FFmpeg reject a conversion instead of selecting a compatible
    # output format. Colour/siting tags are deliberately not forced here.
    if native_pix_fmt not in ("yuv420p", "yuvj420p", "p010le", "yuv420p10le"):
        raise ValueError("NVENC decoded native 4:2:0 format is unsupported")
    return [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(bitstream),
            "-map", "0:v:0", "-frames:v", str(frames), "-pix_fmt", "+" + native_pix_fmt,
            "-fps_mode", "passthrough", "-f", "rawvideo", str(output)]


def score_convert_command(ffmpeg: Path | str, native_raw: Path, output: Path, info: fb.Y4MInfo,
                          native_pix_fmt: str, profile_record: dict) -> list[str]:
    """Convert verified native raw 10-bit planes once for the 8-bit scorer."""
    if native_pix_fmt not in ("p010le", "yuv420p10le"):
        raise ValueError("score conversion requires an observed 10-bit 4:2:0 layout")
    return [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo",
            "-pix_fmt", native_pix_fmt, "-video_size", f"{info.width}x{info.height}",
            "-framerate", f"{info.fps_num}/{info.fps_den}", "-i", str(native_raw),
            "-frames:v", str(info.frames), "-vf", profile_record["score_downconvert_filter"],
            "-pix_fmt", "yuv420p", "-color_range", "pc", "-f", "rawvideo", str(output)]


def probe_command(ffprobe: Path | str, bitstream: Path, output: Path) -> list[str]:
    return [str(ffprobe), "-v", "error", "-count_frames", "-show_streams", "-show_frames",
            "-show_entries", "stream=codec_name,profile,width,height,pix_fmt,color_range,chroma_location,color_space,color_primaries,color_transfer,avg_frame_rate,r_frame_rate,nb_read_frames:frame=pict_type,key_frame,width,height,pix_fmt",
            "-of", "json", "-o", str(output), str(bitstream)]


def _annexb_nalus(payload: bytes):
    """Yield Annex-B NAL payloads; elementary stream data remains private."""
    markers = list(re.finditer(b"\x00\x00(?:\x00)?\x01", payload))
    if not markers:
        raise ValueError("elementary stream is not Annex-B")
    for index, marker in enumerate(markers):
        begin = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(payload)
        if end > begin:
            yield payload[begin:end]


def _h264_first_mb_is_zero(nal: bytes) -> bool:
    """Read the first Exp-Golomb ``first_mb_in_slice`` from an H.264 RBSP."""
    rbsp = re.sub(b"\x00\x00\x03", b"\x00\x00", nal[1:])
    bits = "".join(f"{byte:08b}" for byte in rbsp)
    zeroes = len(bits) - len(bits.lstrip("0"))
    if zeroes >= len(bits):
        raise ValueError("H.264 slice header is truncated")
    end = zeroes * 2 + 1
    if end > len(bits):
        raise ValueError("H.264 slice header is truncated")
    return int(bits[:end], 2) - 1 == 0


def validate_initial_idr(bitstream: Path, codec: str, frames: int) -> dict:
    """Prove a sole first IDR for H.264/HEVC without confusing extra slices.

    The VCL first-slice flags, rather than the total NAL count, bind the Annex-B
    proof to FFprobe's decoded-frame count. AV1 deliberately remains a
    ``key_frame`` proxy because it has no IDR NAL type.
    """
    if codec == "av1":
        return {"method": "ffprobe_key_frame_proxy", "frame_starts": frames,
                "initial_idr_proven": None,
                "note": "AV1 has no IDR NAL; exactly-one-initial-key-frame proxy is reported separately"}
    if codec not in ("h264", "hevc"):
        raise ValueError("IDR proof codec is unsupported")
    starts: list[int] = []
    for nal in _annexb_nalus(Path(bitstream).read_bytes()):
        if codec == "h264":
            nal_type = nal[0] & 0x1F
            if nal_type in (1, 5) and _h264_first_mb_is_zero(nal):
                starts.append(nal_type)
        else:
            if len(nal) < 3:
                raise ValueError("HEVC NAL is truncated")
            nal_type = (nal[0] >> 1) & 0x3F
            if nal_type <= 31 and (nal[2] & 0x80):
                starts.append(nal_type)
    idr_types = (5,) if codec == "h264" else (19, 20)
    if len(starts) != frames or starts[0] not in idr_types or any(value in idr_types for value in starts[1:]):
        raise ValueError("Annex-B first-slice evidence does not prove one initial IDR")
    return {"method": "annexb_first_slice_vcl", "frame_starts": len(starts),
            "initial_vcl_nal_type": starts[0], "initial_idr_proven": True,
            "subsequent_idr_vcl_count": sum(value in idr_types for value in starts[1:])}


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
    expected_profiles = {"h264": ("High",), "hevc": ("Main 10",), "av1": ("Main",)}
    if stream.get("profile") not in expected_profiles[cell["codec"]]:
        raise ValueError("NVENC bitstream profile mismatch")
    # Direct probe tests and schema-1 callers did not carry an encoder profile.
    # Production cells always do, so their native precision is fail-closed.
    expected_class = cell.get("nvenc_profile", {}).get("native_decode_format", "8bit_420_observed")
    native_formats = (("yuv420p", "yuvj420p") if expected_class == "8bit_420_observed"
                      else ("p010le", "yuv420p10le"))
    if stream.get("pix_fmt") not in native_formats:
        raise ValueError("NVENC bitstream native 4:2:0 format mismatch")
    if str(stream.get("nb_read_frames")) != str(frames):
        raise ValueError("NVENC bitstream frame count mismatch")
    pictures = value.get("frames")
    if not isinstance(pictures, list) or len(pictures) != frames:
        raise ValueError("NVENC bitstream picture count mismatch")
    types = [row.get("pict_type") for row in pictures if isinstance(row, dict)]
    if len(types) != frames or any(t not in ("I", "P") for t in types):
        raise ValueError("NVENC bitstream contains B or unknown picture type")
    key_frames = [row.get("key_frame") for row in pictures]
    if types[0] != "I" or key_frames != [1] + [0] * (frames - 1):
        raise ValueError("NVENC bitstream must have exactly one initial key frame")
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
            # FFprobe's key_frame flag is intentionally described as a proxy:
            # it cannot distinguish HEVC CRA from IDR, and AV1 has no IDR NAL.
            "initial_key_frame_evidence": "exactly_one_initial_key_frame_proxy_not_codec_idr_proof",
            "ffprobe_observed_metadata": observed, "external_sequence_rate": f"{cell['fps']}/1",
            "bitstream_timing_confirmed": False}


def native_raw_record(raw: Path, info: fb.Y4MInfo, native_pix_fmt: str) -> dict:
    """Prove native decoder payload layout and bounds before score conversion."""
    if native_pix_fmt in ("yuv420p", "yuvj420p"):
        bytes_per_frame, depth, layout, alignment = info.frame_bytes, 8, "planar", "8bit"
    elif native_pix_fmt == "p010le":
        bytes_per_frame, depth, layout, alignment = info.width * info.height * 3, 10, "semiplanar", "msb_aligned_16bit"
    elif native_pix_fmt == "yuv420p10le":
        bytes_per_frame, depth, layout, alignment = info.width * info.height * 3, 10, "planar", "lsb_aligned_16bit"
    else:
        raise ValueError("native decoder format is unsupported")
    if Path(raw).stat().st_size != bytes_per_frame * info.frames:
        raise ValueError("native_decoded_raw_byte_count_mismatch")
    hashes = []
    with Path(raw).open("rb") as stream:
        for _ in range(info.frames):
            payload = stream.read(bytes_per_frame)
            if len(payload) != bytes_per_frame:
                raise ValueError("native_decoded_raw_byte_count_mismatch")
            hashes.append(hashlib.sha256(payload).hexdigest())
        if stream.read(1):
            raise ValueError("native_decoded_raw_byte_count_mismatch")
    return {"observed_pix_fmt": native_pix_fmt, "bit_depth": depth, "plane_layout": layout,
            "sample_alignment": alignment, "bytes_per_frame": bytes_per_frame,
            "frame_payload_sha256": hashes, "frames": info.frames}


def _run_json(guard, command, output, directory, timeout):
    code, out, err = guard.run(command, cwd=directory, env=os.environ.copy(), timeout_s=timeout)
    if code:
        raise RuntimeError("ffprobe_failed")
    try:
        return json.loads(Path(output).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("ffprobe did not emit valid JSON") from exc


def _parse_encode_completion_diagnostics(text: str, frames: int) -> dict:
    """Pair each FFmpeg encoder input PTS with its following encode_video call.

    FFmpeg 6.1 writes benchmark task times in microseconds.  The association is
    an encoder-call wall diagnostic, not a GPU timestamp. Extra encode/flush
    calls remain explicit instead of being averaged into a video frame.
    """
    event = re.compile(r"encoder <- type:video frame_pts:(-?\d+).*?|bench:\s+(\d+) user\s+(\d+) sys\s+(\d+) real\s+(encode_video|flush_video)", re.I)
    pending = None; samples = []; extra_encode = []; flush = []; pts = []
    for match in event.finditer(text):
        if match.group(1) is not None:
            if pending is not None:
                raise ValueError("encoder PTS had no following encode_video call")
            pending = int(match.group(1)); pts.append(pending)
            continue
        record = {"user_us": int(match.group(2)), "system_us": int(match.group(3)),
                  "real_us": int(match.group(4))}
        if match.group(5).lower() == "flush_video":
            flush.append(record)
        elif pending is not None:
            samples.append({"frame_pts": pending, **record}); pending = None
        else:
            extra_encode.append(record)
    if pending is not None or pts != list(range(frames)) or len(samples) != frames:
        raise ValueError("encoder PTS/encode_video association is incomplete or non-contiguous")
    return {"method": "ffmpeg-6.1-benchmark_all-next-encode_video-after-debug_ts-pts",
            "measurement_boundary": "encoder_call_wall_cpu_microseconds",
            "measurement_valid_for_timing_ranking": False,
            "gpu_execution_ms": None, "frame_completion_samples": samples,
            "unassociated_encode_video_calls": extra_encode, "flush_video_calls": flush,
            "frame_count": frames}


def _run_timed(guard, command, directory, timeout, *, encode_frames: int | None = None):
    """Retain full FFmpeg logs and record explicit process/encoder diagnostics."""
    started = time.perf_counter()
    command = [command[0], "-report", *command[1:]]
    log_name = "ffmpeg-report-" + hashlib.sha256("\0".join(map(str, command)).encode()).hexdigest()[:16] + ".log"
    env = os.environ.copy(); env["FFREPORT"] = "file=" + log_name + ":level=48"
    code, out, err = guard.run(command, cwd=directory, env=env, timeout_s=timeout)
    elapsed = (time.perf_counter() - started) * 1000.0
    report_path = Path(directory) / log_name
    retained = report_path.is_file()
    full_log = report_path.read_text(encoding="utf-8", errors="replace") if retained else out + err
    timing = {"process_wall_clock_diagnostic_ms": elapsed, "completion": "subprocess_exit",
              "full_private_ffmpeg_report_retained": retained,
                            "gpu_execution_ms": None,
                            "measurement_valid_for_timing_ranking": False,
                            "gpu_execution_note": "not available from FFmpeg process completion; never divide this by frames"}
    if encode_frames is not None and code == 0:
        if not retained:
            raise RuntimeError("full_ffmpeg_encode_report_missing")
        timing["encoder_completion_diagnostic"] = _parse_encode_completion_diagnostics(full_log, encode_frames)
    return code, out, err, timing


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


def _split_stereo_y4m(source: Path, info: fb.Y4MInfo, left: Path, right: Path) -> tuple[fb.Y4MInfo, fb.Y4MInfo]:
    """Split a stereo frame exactly per plane for the two-stream H.264 proxy."""
    if info.width % 2:
        raise ValueError("stereo source width must be even")
    eye = fb.Y4MInfo(info.width // 2, info.height, info.fps_num, info.fps_den, info.chroma,
                      info.color_range, info.frame_bytes // 2, info.frames)
    with fb._open_writer(left, eye) as lf, fb._open_writer(right, eye) as rf:
        for _, planes, _ in fb.iter_y4m(source, info):
            lplanes = [p[:, :p.shape[1] // 2].copy() for p in planes]
            rplanes = [p[:, p.shape[1] // 2:].copy() for p in planes]
            fb._write_frame(lf, eye, lplanes)
            fb._write_frame(rf, eye, rplanes)
    return eye, eye


def _join_stereo_raw(left: Path, right: Path, eye: fb.Y4MInfo, output: Path) -> None:
    """Join two byte-identical eye decodes into a side-by-side raw payload."""
    stereo = fb.Y4MInfo(eye.width * 2, eye.height, eye.fps_num, eye.fps_den, eye.chroma,
                         eye.color_range, eye.frame_bytes * 2, eye.frames)
    with Path(left).open("rb") as lf, Path(right).open("rb") as rf, Path(output).open("xb") as out:
        shapes = fb._plane_shapes(eye)
        for _ in range(eye.frames):
            lraw = lf.read(eye.frame_bytes); rraw = rf.read(eye.frame_bytes)
            if len(lraw) != eye.frame_bytes or len(rraw) != eye.frame_bytes:
                raise ValueError("dual_eye_decoded_raw_byte_count_mismatch")
            lp = []; rp = []; offset = 0
            for h, w in shapes:
                size = h * w
                lp.append(lraw[offset:offset + size]); rp.append(rraw[offset:offset + size]); offset += size
            out.write(b"".join(np.concatenate((np.frombuffer(a, dtype=np.uint8).reshape((h, w)),
                                                  np.frombuffer(b, dtype=np.uint8).reshape((h, w))), axis=1).tobytes()
                               for a, b, (h, w) in zip(lp, rp, shapes)))
        if lf.read(1) or rf.read(1):
            raise ValueError("dual_eye_decoded_raw_byte_count_mismatch")
    if Path(output).stat().st_size != stereo.frame_bytes * stereo.frames:
        raise ValueError("dual_eye_decoded_raw_byte_count_mismatch")


def _stream_reference_for_cell(plan: dict, source: Path, source_info: fb.Y4MInfo, cell: dict,
                               path: Path) -> tuple[fb.Y4MInfo, list[dict]]:
    """Materialize either full-FOV or frozen per-eye-cropped source frames."""
    if cell.get("source_geometry", "full_fov") == "full_fov":
        return fb._stream_reference(source, source_info, cell, path)
    adapter = plan.get("source_adapter", {})
    if adapter.get("kind") != "per_eye_crop":
        raise ValueError("requested source adapter is unavailable")
    try:
        from . import fence_metrics
    except ImportError as exc:
        raise ValueError("frozen crop adapter is unavailable") from exc
    geometry = adapter["geometry"]
    target = tuple(geometry["target_eye"])
    if target != (cell["eye_width"], cell["eye_height"]):
        raise ValueError("crop geometry and encoded geometry differ")
    info = fb.Y4MInfo(target[0] * 2, target[1], source_info.fps_num, source_info.fps_den,
                      source_info.chroma, source_info.color_range,
                      fb._frame_bytes(target[0] * 2, target[1], source_info.chroma), source_info.frames)
    identities = []
    with fb._open_writer(path, info) as out:
        for index, planes, digest in fb.iter_y4m(source, source_info):
            cropped = fence_metrics.crop_frame(planes, geometry)
            transform = adapter.get("future_transform")
            if transform is not None:
                try:
                    from .foveation import FoveationConfig, transform_planes
                except ImportError as exc:
                    raise ValueError("WO-8 frame-bank transform is unavailable") from exc
                cropped = transform_planes(cropped, FoveationConfig(profile=transform["profile"],
                                                                      softness=transform["softness"],
                                                                      blur_only=transform["blur_only"]))
            reference_hash = fb._write_frame(out, info, cropped)
            identities.append({"source_frame": index, "source_sha256": digest,
                               "reference_sha256": reference_hash})
    return info, identities


def _q3b_config(transform: dict):
    """Construct the frozen WO-8 transform; no default transform is implied."""
    if not isinstance(transform, dict) or transform.get("kind") != "wo8_foveation":
        raise ValueError("Q3b cell requires an explicit WO-8 transform")
    try:
        from .foveation import FoveationConfig
        return FoveationConfig(profile=transform["profile"], softness=transform["softness"],
                               blur_only=transform["blur_only"])
    except (ImportError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Q3b WO-8 transform is unavailable or invalid") from exc


def _stream_q3b_sources(source: Path, source_info: fb.Y4MInfo, geometry: dict, transform: dict,
                        encoded_path: Path, sharp_path: Path, blur_path: Path):
    """Encode reduced WO-8 planes, while retaining full crop score references.

    The encoded path is the *only* input to the codec.  The sharp and matching
    blur paths remain expanded cropped space for post-decode quality scoring.
    """
    try:
        from . import fence_metrics
        from .foveation import encode_planes, blur_reference
    except ImportError as exc:
        raise ValueError("Q3b source modules are unavailable") from exc
    config = _q3b_config(transform)
    expanded = tuple(geometry["target_eye"])
    first = None
    identities = []
    for index, planes, digest in fb.iter_y4m(source, source_info):
        cropped = fence_metrics.crop_frame(planes, geometry)
        encoded = encode_planes(cropped, config)
        if encoded.expanded_eye != expanded or encoded.chroma420 is not True:
            raise ValueError("Q3b WO-8 expanded geometry/chroma drifted")
        if first is None:
            first = encoded
            small = encoded.encoded_eye
            encoded_info = fb.Y4MInfo(small[0] * 2, small[1], source_info.fps_num, source_info.fps_den,
                source_info.chroma, source_info.color_range,
                fb._frame_bytes(small[0] * 2, small[1], source_info.chroma), source_info.frames)
            score_info = fb.Y4MInfo(expanded[0] * 2, expanded[1], source_info.fps_num, source_info.fps_den,
                source_info.chroma, source_info.color_range,
                fb._frame_bytes(expanded[0] * 2, expanded[1], source_info.chroma), source_info.frames)
            encoded_out = fb._open_writer(encoded_path, encoded_info)
            sharp_out = fb._open_writer(sharp_path, score_info)
            blur_out = fb._open_writer(blur_path, score_info)
        elif encoded.encoded_eye != first.encoded_eye:
            raise ValueError("Q3b WO-8 encoded geometry changed by frame")
        encoded_hash = fb._write_frame(encoded_out, encoded_info, encoded.planes)
        sharp_hash = fb._write_frame(sharp_out, score_info, cropped)
        blur_hash = fb._write_frame(blur_out, score_info, blur_reference(cropped, config))
        identities.append({"source_frame": index, "source_sha256": digest,
                           "encoded_reference_sha256": encoded_hash,
                           "sharp_reference_sha256": sharp_hash, "blur_reference_sha256": blur_hash})
    if first is None:
        raise ValueError("Q3b source has no frames")
    encoded_out.close(); sharp_out.close(); blur_out.close()
    return encoded_info, score_info, identities, {"transform": copy.deepcopy(transform),
        "expanded_eye": list(first.expanded_eye), "encoded_eye": list(first.encoded_eye),
        "encoded_stereo": [first.encoded_eye[0] * 2, first.encoded_eye[1]],
        "encoded_chroma": "420"}


def _reconstruct_q3b_decoded(decoded_small: Path, encoded_info: fb.Y4MInfo, score_path: Path,
                              score_info: fb.Y4MInfo, transform: dict) -> None:
    """Expand a decoded reduced WO-8 frame only after the codec stage."""
    try:
        from .foveation import EncodedPlanes, reconstruct_planes
    except ImportError as exc:
        raise ValueError("Q3b reconstruction module is unavailable") from exc
    config = _q3b_config(transform)
    template = EncodedPlanes((np.empty((0, 0), np.uint8),) * 3,
        (score_info.width // 2, score_info.height), (encoded_info.width // 2, encoded_info.height), True, config)
    with fb._open_writer(score_path, score_info) as out:
        for _, planes, _ in fb.iter_y4m(decoded_small, encoded_info):
            fb._write_frame(out, score_info, reconstruct_planes(planes, template))


def _q3b_periphery_mask(cell: dict, info: fb.Y4MInfo, rect: dict):
    """Frozen source-space band classification for a Q3b fence rectangle."""
    try:
        from .foveation import encoded_size, softness_ramp
    except ImportError as exc:
        raise ValueError("Q3b band classifier is unavailable") from exc
    config = _q3b_config(cell["source_transform"])
    eye_w, eye_h = info.width // 2, info.height
    x = (np.arange(rect["width"]) + rect["x"] + .5) / eye_w
    y = (np.arange(rect["height"]) + rect["y"] + .5) / eye_h
    xx, yy = np.meshgrid(x, y)
    ramp = softness_ramp(np.stack((xx, yy), axis=-1), (eye_w, eye_h),
                         encoded_size(eye_w, eye_h, config), config)
    mask = ramp > 0
    return mask, {"kind": "wo8_source_space_periphery", "profile": config.profile,
                  "softness": config.softness, "blur_only": config.blur_only,
                  "criterion": "softness_ramp>0", "selected_pixels": int(mask.sum()),
                  "total_pixels": int(mask.size)}


def _crop_context_for_cell(plan: dict, cell: dict) -> tuple[list[dict], dict[str, dict]]:
    """Map fixed full-FOV crops into a cropped source without inventing pixels.

    A crop that is only partly inside the encoded field is reported as excluded.
    It is not intersected or rescaled, because either would change the fixed-crop
    question.  The caller retains the original full-FOV crop definitions in the
    public plan for cross-cell provenance.
    """
    if cell.get("source_geometry", "full_fov") != "crop":
        return plan["crops"], {}
    geometry = plan["source_adapter"]["geometry"]
    by_eye = {row["eye"]: row for row in geometry["eyes"]}
    usable, excluded = [], {}
    for original in plan["crops"]:
        resolved = original["resolved_pixels"]
        geo = by_eye[original["eye"]]
        x, y, width, height = (resolved[key] for key in ("eye_x", "y", "width", "height"))
        gx, gy, gw, gh = (geo[key] for key in ("x", "y", "width", "height"))
        ix0, iy0 = max(x, gx), max(y, gy)
        ix1, iy1 = min(x + width, gx + gw), min(y + height, gy + gh)
        overlap = max(0, ix1 - ix0) * max(0, iy1 - iy0)
        coverage = overlap / (width * height)
        if x < gx or y < gy or x + width > gx + gw or y + height > gy + gh:
            excluded[original["name"]] = {"status": "excluded_from_cropped_score",
                                          "reason": "fixed_crop_not_fully_contained",
                                          "coverage_fraction": coverage,
                                          "original_resolved_pixels": resolved}
            continue
        mapped = {"name": original["name"], "eye": original["eye"],
                  "x": (x - gx) / gw, "y": (y - gy) / gh,
                  "w": width / gw, "h": height / gh}
        mapped["resolved_pixels"] = fb.resolve_crop_pixels(mapped, gw, gh, "420")
        usable.append(mapped)
    return usable, excluded


_STOP_REASONS = frozenset(("gpu_driver_or_device_error", "free_vram_below_margin", "stop_requested",
                           "comfy_queue_active_or_unknown", "compute_backend_active_or_unknown"))
_TIMING_REASONS = frozenset(("comfy_queue_active_or_unknown", "compute_backend_active_or_unknown",
                             "timing_activity_unknown", "sustained_external_gpu_load"))


def lease_telemetry(window: Path, start_epoch_s: float, end_epoch_s: float) -> dict:
    """Return only sanitized, in-run quality-monitor evidence from a private lease."""
    from tools.quest3 import unattended as u
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (start_epoch_s, end_epoch_s)) or end_epoch_s < start_epoch_s:
        raise ValueError("invalid run interval")
    state = u.json_read(Path(window) / "state.json")
    policy = state.get("last_policy")
    if not isinstance(policy, dict) or policy.get("mode") != "quality":
        raise ValueError("lease quality policy missing")
    margin = policy.get("free_vram_margin_mib")
    if not isinstance(margin, (int, float)) or not math.isfinite(margin) or margin <= 0:
        raise ValueError("lease VRAM margin missing")
    def enum_list(value, allowed, label):
        if not isinstance(value, list) or any(not isinstance(x, str) or x not in allowed for x in value):
            raise ValueError("lease " + label + " invalid")
        return list(value)
    samples = []
    for raw in state.get("gpu_load_samples", []):
        if not isinstance(raw, dict):
            continue
        epoch = raw.get("epoch_s")
        if not isinstance(epoch, (int, float)) or not math.isfinite(epoch) or not start_epoch_s <= epoch <= end_epoch_s:
            continue
        numeric = {}
        for key, lower, upper in (("free_vram_mib", 0, float("inf")), ("total_vram_mib", 1, float("inf")),
                                  ("overall_load_percent", 0, 100), ("external_max_engine_percent", 0, 100)):
            value = raw.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError("lease sample numeric field invalid")
            numeric[key] = float(value)
        if numeric["free_vram_mib"] > numeric["total_vram_mib"]:
            raise ValueError("lease sample VRAM invalid")
        device = raw.get("device_error")
        if device is not None and device not in ("gpu_driver_query_unavailable", "gpu_driver_query_failed"):
            raise ValueError("lease device status invalid")
        samples.append({"epoch_s": float(epoch), **numeric, "device_error": device,
                        "compute_backend_reasons": enum_list(raw.get("compute_backend_reasons"), _STOP_REASONS, "compute reasons"),
                        "stop_reasons": enum_list(raw.get("stop_reasons"), _STOP_REASONS, "stop reasons"),
                        "timing_invalidation_reasons": enum_list(raw.get("timing_invalidation_reasons"), _TIMING_REASONS, "timing reasons")})
    if not samples:
        raise ValueError("lease telemetry missing for run interval")
    return {"measurement_mode": "quality", "free_vram_margin_mib": float(margin),
            "policy_stop_reasons": enum_list(policy.get("stop_reasons"), _STOP_REASONS, "policy stop reasons"),
            "run_start_epoch_s": float(start_epoch_s), "run_end_epoch_s": float(end_epoch_s),
            "samples": samples, "lease_closed_observed": state.get("closed") is True,
            "cleanup_verified": False}


def _window_y4m(source: Path, info: fb.Y4MInfo, output: Path, start_one_based: int, end_one_based: int) -> fb.Y4MInfo:
    """Write an exact inclusive source-frame window without timing duplication."""
    if not 1 <= start_one_based <= end_one_based <= info.frames:
        raise ValueError("invalid score frame window")
    window = fb.Y4MInfo(info.width, info.height, info.fps_num, info.fps_den, info.chroma,
                        info.color_range, info.frame_bytes, end_one_based - start_one_based + 1)
    with fb._open_writer(output, window) as target:
        for index, planes, _ in fb.iter_y4m(source, info):
            if start_one_based - 1 <= index < end_one_based:
                fb._write_frame(target, window, planes)
    return window


def _score_pair_windows(tools, distorted: Path, reference: Path, info: fb.Y4MInfo, workdir: Path,
                        vertical_ppd: float, guard, timeout: float, *, all_score: dict | None = None) -> dict:
    """All primary metrics for both required Q3 frame windows."""
    Path(workdir).mkdir(parents=True, exist_ok=True)
    common = dict(guard=guard, env=os.environ.copy(), timeout_s=timeout)
    if all_score is None:
        all_score = fb.score_pair(tools, distorted, reference, workdir, vertical_ppd,
                                  frames=info.frames, image_height=info.height, **common)
    dist_trim, ref_trim = workdir / "trim-decoded.y4m", workdir / "trim-reference.y4m"
    trim_info = _window_y4m(distorted, info, dist_trim, 10, 89)
    _window_y4m(reference, info, ref_trim, 10, 89)
    try:
        trim_score = fb.score_pair(tools, dist_trim, ref_trim, workdir, vertical_ppd,
                                   frames=trim_info.frames, image_height=trim_info.height, **common)
    finally:
        dist_trim.unlink(missing_ok=True); ref_trim.unlink(missing_ok=True)
    return {"1-90": all_score, "10-89": trim_score,
            "windows_one_based": {"1-90": [1, 90], "10-89": [10, 89]}}


def _same_frame_scores(plan, cell_index, cell, tools, guard, directory, source, source_info,
                       decoded, decoded_info, reference, ref_info, timeout, keep_artifacts,
                       *, matching_blur_reference=None):
    """Use exactly the established display and fixed-crop score path."""
    common = dict(frames=ref_info.frames, guard=guard, env=os.environ.copy(), timeout_s=timeout)
    codec_ppd = cell.get("score_vertical_pixels_per_degree",
                         plan["hvs_calibration"]["codec_cells"][cell_index]["vertical_pixels_per_degree"])
    row = {"codec_only": fb.score_pair(tools, decoded, reference, directory, codec_ppd,
                                        image_height=ref_info.height, **common)}
    row["codec_only_windows"] = _score_pair_windows(tools, decoded, reference, ref_info,
        directory / "codec-windows", codec_ppd, guard, timeout, all_score=row["codec_only"])
    if "fence_rectangles" in plan:
        from . import fence_metrics
        fence_rect = (plan["fence_rectangles"]["cropped"]["mapped"] if cell.get("source_geometry") == "crop"
                      else plan["fence_rectangles"]["full_fov"])
        if matching_blur_reference is None:
            row["fence_metrics"] = fence_metrics.score_y4m(reference, decoded, fence_rect, guard)
        else:
            mask, descriptor = _q3b_periphery_mask(cell, ref_info, fence_rect)
            row["fence_metrics"] = fence_metrics.score_against_references(
                reference, decoded, fence_rect, guard, matching_blur_reference=matching_blur_reference,
                region_mask=mask, region_descriptor=descriptor)
    display_ref = directory / "source-display.y4m"; display_dec = directory / "decoded-display.y4m"
    is_crop = cell.get("source_geometry", "full_fov") == "crop"
    presentation_eye = (cell["eye_width"], cell["eye_height"]) if is_crop else plan["presentation_eye"]
    # Crop rows score reconstructed cropped space against their cropped
    # reference. Full-FOV rows retain the established source-vs-decoded path.
    fb._write_display(reference if is_crop else source, ref_info if is_crop else source_info,
                      display_ref, presentation_eye)
    fb._write_display(decoded, decoded_info, display_dec, presentation_eye)
    display_info = fb.inspect_y4m(display_ref); decoded_display_info = fb.inspect_y4m(display_dec)
    display_ppd = codec_ppd if is_crop else plan["hvs_calibration"]["display"]["vertical_pixels_per_degree"]
    row["displayed"] = fb.score_pair(tools, display_dec, display_ref, directory,
                                      display_ppd, image_height=presentation_eye[1], **common)
    row["displayed_windows"] = _score_pair_windows(tools, display_dec, display_ref, display_info,
        directory / "display-windows", display_ppd, guard, timeout, all_score=row["displayed"])
    row["crops"] = {}
    row["crop_windows"] = {}
    score_crops, excluded = _crop_context_for_cell(plan, cell)
    row["crops"].update(excluded)
    calibration_by_name = {crop["name"]: calibration for crop, calibration in zip(
        plan["crops"], plan["hvs_calibration"]["crops"])}
    for crop in score_crops:
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
        calibration = calibration_by_name[crop["name"]]
        row["crops"][crop["name"]] = fb.score_pair(tools, gp, rp, directory,
            calibration["vertical_pixels_per_degree"], image_height=crop_info.height, **common)
        row["crop_windows"][crop["name"]] = _score_pair_windows(
            tools, gp, rp, crop_info, directory / f"crop-{crop['name']}-windows",
            calibration["vertical_pixels_per_degree"], guard, timeout,
            all_score=row["crops"][crop["name"]])
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
    guard = fb.WindowGuard(window, supervised=True); guard.status(); run_start_epoch_s = time.time()
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
              "q3_revision": plan.get("q3_revision"), "source_adapter": plan.get("source_adapter"),
              "fence_rectangles": plan.get("fence_rectangles"), "score_windows": plan.get("score_windows"),
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
            q3b_transform = cell.get("source_transform")
            score_ref = ref; score_blur = None; score_ref_info = None
            if q3b_transform is None:
                ref_info, identities = _stream_reference_for_cell(plan, source, source_info, cell, ref)
            else:
                score_ref = directory / "score-sharp-reference.y4m"
                score_blur = directory / "score-blur-reference.y4m"
                ref_info, score_ref_info, identities, q3b_provenance = _stream_q3b_sources(
                    source, source_info, plan["source_adapter"]["geometry"], q3b_transform,
                    ref, score_ref, score_blur)
                row["q3b_transform"] = q3b_provenance
            row["identity_count"] = len(identities)
            if [x["source_sha256"] for x in identities] != [x["source_sha256"] for x in plan["source"]["frame_identity"]]:
                raise ValueError("source_frame_identity_drift")
            if row["nvenc_profile"]["layout"] == "dual_eye":
                left_ref, right_ref = directory / "reference-left.y4m", directory / "reference-right.y4m"
                left_info, right_info = _split_stereo_y4m(ref, ref_info, left_ref, right_ref)
                streams = []
                raw_eyes = []
                for eye_name, eye_ref, eye_info in (("left", left_ref, left_info), ("right", right_ref, right_info)):
                    eye_stream = directory / f"encoded-{eye_name}.{_ext(cell['codec'])}"
                    eye_native_raw = directory / f"decoded-{eye_name}-native.raw"
                    eye_score_raw = directory / f"decoded-{eye_name}-score.raw"
                    stream_cell = dict(row)
                    stream_cell["nvenc_profile"] = profile(cell["codec"], cell["per_stream_mbps"], cell["fps"],
                                                              preset=row["nvenc_profile"]["preset"], spatial_aq=row["nvenc_profile"]["spatial_aq"],
                                                              layout="dual_eye")
                    code, _, _, timing = _run_timed(guard, encode_command(needed["ffmpeg"], eye_ref, eye_stream, stream_cell), directory, command_timeout_s, encode_frames=eye_info.frames)
                    if code or not eye_stream.is_file() or eye_stream.stat().st_size <= 0:
                        raise RuntimeError("nvenc_encode_failed")
                    idr_evidence = validate_initial_idr(eye_stream, cell["codec"], eye_info.frames)
                    eye_probe_path = directory / f"bitstream-probe-{eye_name}.json"
                    eye_cell = dict(stream_cell); eye_cell["stereo_width"] = eye_info.width; eye_cell["eye_height"] = eye_info.height
                    probe = validate_probe(_run_json(guard, probe_command(needed["ffprobe"], eye_stream, eye_probe_path), eye_probe_path, directory, command_timeout_s), eye_cell, eye_info.frames)
                    code, _, _, decode_timing = _run_timed(guard, decode_command(needed["ffmpeg"], eye_stream, eye_native_raw, eye_info.frames, probe["pix_fmt"]), directory, command_timeout_s)
                    if code or not eye_native_raw.is_file():
                        raise RuntimeError("nvenc_decode_failed")
                    native_record = native_raw_record(eye_native_raw, eye_info, probe["pix_fmt"])
                    if native_record["bit_depth"] == 10:
                        code, _, _, score_timing = _run_timed(guard, score_convert_command(needed["ffmpeg"], eye_native_raw, eye_score_raw, eye_info, probe["pix_fmt"], stream_cell["nvenc_profile"]), directory, command_timeout_s)
                        if code or not eye_score_raw.is_file():
                            raise RuntimeError("nvenc_score_conversion_failed")
                    else:
                        eye_score_raw, score_timing = eye_native_raw, None
                    streams.append({"eye": eye_name, "profile": stream_cell["nvenc_profile"], "bitstream": {**probe,
                        "initial_idr_evidence": idr_evidence,
                        "actual_elementary_stream_bytes": eye_stream.stat().st_size,
                        "actual_elementary_stream_sha256": fb.sha256_file(eye_stream),
                        "actual_mbps_external_f90_normalization": eye_stream.stat().st_size * 8 * cell["fps"] / eye_info.frames / 1_000_000},
                        "native_decoded_raw": native_record,
                        "encode_process_completion_diagnostic": timing,
                        "decode_process_completion_diagnostic": decode_timing,
                        "score_conversion_process_completion_diagnostic": score_timing})
                    raw_eyes.append(eye_score_raw)
                _join_stereo_raw(raw_eyes[0], raw_eyes[1], left_info, raw_decoded)
                row["streams"] = streams
                row["bitstream"] = {"layout": "dual_eye", "stream_count": 2,
                    "actual_elementary_stream_bytes": sum(x["bitstream"]["actual_elementary_stream_bytes"] for x in streams),
                    "actual_elementary_stream_sha256_by_eye": {
                        x["eye"]: x["bitstream"]["actual_elementary_stream_sha256"] for x in streams},
                    "actual_mbps_external_f90_normalization": sum(x["bitstream"]["actual_mbps_external_f90_normalization"] for x in streams),
                    "per_stream_mbps_requested": cell["per_stream_mbps"]}
            else:
                code, _, _, timing = _run_timed(guard, encode_command(needed["ffmpeg"], ref, stream, row), directory, command_timeout_s, encode_frames=ref_info.frames)
                if code or not stream.is_file() or stream.stat().st_size <= 0:
                    raise RuntimeError("nvenc_encode_failed")
                idr_evidence = validate_initial_idr(stream, cell["codec"], ref_info.frames)
                probe_json = directory / "bitstream-probe.json"
                probe = validate_probe(_run_json(guard, probe_command(needed["ffprobe"], stream, probe_json), probe_json, directory, command_timeout_s), row, ref_info.frames)
                row["bitstream"] = {**probe, "initial_idr_evidence": idr_evidence,
                    "actual_elementary_stream_bytes": stream.stat().st_size,
                    "actual_elementary_stream_sha256": fb.sha256_file(stream),
                    "actual_mbps_external_f90_normalization": stream.stat().st_size * 8 * cell["fps"] / ref_info.frames / 1_000_000}
                native_raw = directory / "decoded-native.raw"
                code, _, _, decode_timing = _run_timed(guard, decode_command(needed["ffmpeg"], stream, native_raw, ref_info.frames, probe["pix_fmt"]), directory, command_timeout_s)
                if code or not native_raw.is_file():
                    raise RuntimeError("nvenc_decode_failed")
                native_record = native_raw_record(native_raw, ref_info, probe["pix_fmt"])
                if native_record["bit_depth"] == 10:
                    code, _, _, score_timing = _run_timed(guard, score_convert_command(needed["ffmpeg"], native_raw, raw_decoded, ref_info, probe["pix_fmt"], row["nvenc_profile"]), directory, command_timeout_s)
                    if code or not raw_decoded.is_file():
                        raise RuntimeError("nvenc_score_conversion_failed")
                else:
                    raw_decoded, score_timing = native_raw, None
                row["encode_process_completion_diagnostic"] = timing
                row["decode_process_completion_diagnostic"] = decode_timing
                row["score_conversion_process_completion_diagnostic"] = score_timing
                row["native_decoded_raw"] = native_record
            row["decoded_raw_wrapper"] = wrap_raw_payload(raw_decoded, ref_info, decoded)
            decoded_info = fb.inspect_y4m(decoded)
            fb._assert_same_frames(ref, decoded, ref_info)
            score_decoded = decoded; score_decoded_info = decoded_info
            if q3b_transform is not None:
                score_decoded = directory / "score-reconstructed-decoded.y4m"
                _reconstruct_q3b_decoded(decoded, decoded_info, score_decoded, score_ref_info, q3b_transform)
                score_decoded_info = fb.inspect_y4m(score_decoded)
                fb._assert_same_frames(score_ref, score_decoded, score_ref_info)
            row["decoded_frame_identity"] = [{"cell_frame": i, "source_frame": x["source_frame"],
                "reference_sha256": x.get("encoded_reference_sha256", x.get("reference_sha256")), "decoded_sha256": digest}
                for (i, _, digest), x in zip(fb.iter_y4m(decoded, decoded_info), identities)]
            if len(row["decoded_frame_identity"]) != ref_info.frames:
                raise ValueError("decoded_identity_or_geometry_mismatch")
            row.update(_same_frame_scores(plan, index, cell, scoring_tools, guard, directory, source,
                source_info, score_decoded, score_decoded_info, score_ref, score_ref_info or ref_info,
                command_timeout_s, keep_artifacts, matching_blur_reference=score_blur))
        except (PermissionError, TimeoutError, ValueError, RuntimeError) as exc:
            row["error"] = str(exc) if str(exc) in {"nvenc_encode_failed", "nvenc_decode_failed", "decoded_identity_or_geometry_mismatch"} else "cell_failed"
            result["failure_reasons"].append(row["error"])
        result["cells"].append(row)
        (private_out / "nvenc-framebank-progress.json").write_text(fb.report_json(result), encoding="utf-8")
        if not keep_artifacts and not row.get("error"):
            # Raw 90-frame C420 and native Main10 payloads are large. Their
            # hashes/scores/probes have already been persisted. Keep the small
            # elementary stream plus its hash for decoder-only rechecks; a
            # failed scoring cell remains resumable without re-encoding.
            for path in directory.iterdir():
                if path.is_file() and path.suffix.lower() in (".y4m", ".raw"):
                    path.unlink()
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
    run_end_epoch_s = time.time()
    try:
        guard.status()
        result["lease_final_health"] = "active"
    except PermissionError:
        result["failure_reasons"].append("lease_final_health_failed")
        result["lease_final_health"] = "failed"
    try:
        result["lease_telemetry"] = lease_telemetry(window, run_start_epoch_s, run_end_epoch_s)
    except (OSError, ValueError, KeyError):
        result["failure_reasons"].append("lease_telemetry_missing_or_invalid")
    result["complete"] = not result["failure_reasons"] and len(result["cells"]) == len(plan["cells"])
    (private_out / "nvenc-framebank-private.json").write_text(fb.report_json(result), encoding="utf-8")
    return result


def sanitized_report(result: dict) -> dict:
    keep = ("label", "codec", "rate_mbps", "fps", "eye_width", "eye_height", "encoded_chroma", "cap_bytes", "bits_per_pixel", "source_geometry", "nvenc_profile", "streams", "bitstream", "encode_process_completion_diagnostic", "decode_process_completion_diagnostic", "score_conversion_process_completion_diagnostic", "decoded_raw_wrapper", "codec_only", "codec_only_windows", "displayed", "displayed_windows", "fence_metrics", "crops", "crop_windows", "error")
    def native_public(record):
        if not isinstance(record, dict):
            return None
        return {key: record.get(key) for key in ("observed_pix_fmt", "bit_depth", "plane_layout",
                "sample_alignment", "bytes_per_frame", "frames")}
    def cell_public(row):
        item = {key: row.get(key) for key in keep if key not in ("streams", "decoded_raw_wrapper")}
        item["native_decoded_raw"] = native_public(row.get("native_decoded_raw"))
        item["decoded_raw_wrapper"] = ({key: row.get("decoded_raw_wrapper", {}).get(key)
                                        for key in ("raw_payload_sha256", "byte_identical", "external_y4m_contract")}
                                       if isinstance(row.get("decoded_raw_wrapper"), dict) else None)
        if isinstance(row.get("streams"), list):
            item["streams"] = [{"eye": stream.get("eye"), "profile": stream.get("profile"),
                                "bitstream": stream.get("bitstream"),
                                "native_decoded_raw": native_public(stream.get("native_decoded_raw")),
                                "encode_process_completion_diagnostic": stream.get("encode_process_completion_diagnostic"),
                                "decode_process_completion_diagnostic": stream.get("decode_process_completion_diagnostic"),
                                "score_conversion_process_completion_diagnostic": stream.get("score_conversion_process_completion_diagnostic")}
                               for stream in row["streams"]]
        return item
    return {"schema": SCHEMA, "kind": "nvenc_frame_bank_sanitized", "complete": result.get("complete") is True,
            "failure_reasons": list(result.get("failure_reasons", [])), "frozen_plan_sha256": result.get("frozen_plan_sha256"),
            "source_sha256": result.get("source_sha256_end"), "source_y4m_header": result.get("source_y4m_header"), "tool_provenance": result.get("tool_provenance_end"), "tools_build_provenance": result.get("tools_build_provenance"),
            "hvs_gpu_sanity": result.get("hvs_gpu_sanity"), "projection": result.get("projection"), "crop_definitions": result.get("crop_definitions"), "q3_revision": result.get("q3_revision"), "source_adapter": result.get("source_adapter"), "fence_rectangles": result.get("fence_rectangles"), "score_windows": result.get("score_windows"), "proxy": result.get("proxy"),
            "lease_final_health": result.get("lease_final_health"), "lease_telemetry": result.get("lease_telemetry"),
            "cells": [cell_public(row) for row in result.get("cells", [])],
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
    p.add_argument("--revised-q3a", action="store_true", help="freeze only the revised NVENC Q3a subset")
    p.add_argument("--crop-geometry", help="JSON from fence_metrics.crop_geometry (required with --revised-q3a)")
    p.add_argument("--fence-rectangle", help="frozen Q3 fence rectangle JSON (required with --revised-q3a)")
    r = sub.add_parser("run")
    for name in ("plan", "source", "private-out", "report", "window", "ffmpeg", "ffprobe", "psnr-hvs-m-h", "tools-metadata"):
        r.add_argument("--" + name, required=True)
    r.add_argument("--command-timeout-s", type=float, default=900)
    r.add_argument("--keep-artifacts", action="store_true")
    r.add_argument("--supervised", action="store_true", help="required owner-supervised PC-only lease")
    args = parser.parse_args(argv)
    if args.command == "plan":
        if args.revised_q3a:
            if not args.crop_geometry or not args.fence_rectangle:
                parser.error("--revised-q3a requires --crop-geometry and --fence-rectangle")
            plan = build_revised_q3a_plan(Path(args.source), args.vertical_pixels_per_degree,
                horizontal_pixels_per_degree=args.horizontal_pixels_per_degree,
                projection_evidence=args.projection_evidence, crop_evidence=args.crop_evidence,
                crop_geometry=json.loads(Path(args.crop_geometry).read_text(encoding="utf-8")),
                fence_rectangle=json.loads(Path(args.fence_rectangle).read_text(encoding="utf-8")),
                crops=_crops_argument(args.crops))
        else:
            if args.crop_geometry or args.fence_rectangle:
                parser.error("crop geometry and fence rectangle require --revised-q3a")
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

"""Frozen cropped-source PyroWave runner for Q3a, with fail-closed Q3b hooks.

This is an offline PC codec/quality experiment.  It never starts ALVR, SteamVR,
or a headset application.  A caller supplies an existing owner-supervised
``frame_bank_pc`` WindowGuard lease.  Native timing is retained only when an
encoder-provided per-frame record is supplied; wall-clock encode duration is
deliberately not converted into a per-frame timing claim.
"""
from __future__ import annotations

import copy
import argparse
import hashlib
import json
import math
import os
import shutil
import time
from pathlib import Path

from . import framebank as fb
from . import pyrowave_wave as wave

SCHEMA = 1
Q3A_ROWS = (("haar", 1000), ("53", 800), ("53", 1000), ("97", 800), ("97", 1000))
Q3B_ROWS = (
    ("light-s0", "97", 1000), ("light-s05", "97", 1000),
    ("light-s1", "97", 1000), ("light-s05", "53", 1000),
    ("medium-s05", "53", 1000), ("medium-s05", "97", 1000),
    ("h264fit-s05", "97", 1000), ("blur-only-light-s05", "97", 1000),
)
# Owner-selected post-Q3b quality extensions.  ``profile`` is absent for a
# full native crop; present profiles use WO-8 reduced-plane encode/reconstruct.
# Default RDO deliberately leaves the environment knob unset, preserving the
# build's historical constant.  Rates above the Wi-Fi target are offline-only.
Q3_EXTENSION_ROWS = (
    {"experiment_id":"q3a_rdo_pyro_97_1000_rdo24", "phase":"q3a", "label":"pyrowave-97-crop-rdo24-1000", "wavelet":"97", "rate_mbps":1000, "rdo_px_per_deg":24},
    {"experiment_id":"q3a_rdo_pyro_97_1000_rdo36", "phase":"q3a", "label":"pyrowave-97-crop-rdo36-1000", "wavelet":"97", "rate_mbps":1000, "rdo_px_per_deg":36},
    {"experiment_id":"q3b_rdo_pyro_97_medium_s05_rdo24", "phase":"q3b", "label":"pyrowave-97-medium-s05-rdo24-1000", "wavelet":"97", "rate_mbps":1000, "profile":"medium-s05", "rdo_px_per_deg":24},
    {"experiment_id":"q3b_phase_pyro_97_light_s05_default_rdo", "phase":"q3b", "label":"pyrowave-97-light-s05-default-rdo-1000", "wavelet":"97", "rate_mbps":1000, "profile":"light-s05", "rdo_px_per_deg":None},
    {"experiment_id":"q3a_highrate_pyro_97_1500_default_rdo", "phase":"q3a", "label":"pyrowave-97-crop-default-rdo-1500", "wavelet":"97", "rate_mbps":1500, "rdo_px_per_deg":None, "offline_only_above_wifi_cap":True},
    {"experiment_id":"q3a_highrate_pyro_97_2000_default_rdo", "phase":"q3a", "label":"pyrowave-97-crop-default-rdo-2000", "wavelet":"97", "rate_mbps":2000, "rdo_px_per_deg":None, "offline_only_above_wifi_cap":True},
    {"experiment_id":"q3a_highrate_pyro_haar_2000_default_rdo", "phase":"q3a", "label":"pyrowave-haar-crop-default-rdo-2000", "wavelet":"haar", "rate_mbps":2000, "rdo_px_per_deg":None, "offline_only_above_wifi_cap":True},
)
# This is a new, additive overnight matrix.  It must never be folded into the
# historical extension above: those rows already have retained evidence and a
# different experiment identity.
Q3_OVERNIGHT_STATIC_ROWS = (
    {"experiment_id":"q3a_overnight_pyro_haar_crop_1000_rdo24", "phase":"q3a", "label":"pyrowave-haar-crop-rdo24-1000", "wavelet":"haar", "rate_mbps":1000, "rdo_px_per_deg":24},
    {"experiment_id":"q3b_overnight_pyro_haar_medium_s05_1000_rdo24", "phase":"q3b", "label":"pyrowave-haar-medium-s05-rdo24-1000", "wavelet":"haar", "rate_mbps":1000, "profile":"medium-s05", "rdo_px_per_deg":24},
    {"experiment_id":"q3b_overnight_pyro_53_medium_s05_1000_rdo24", "phase":"q3b", "label":"pyrowave-53-medium-s05-rdo24-1000", "wavelet":"53", "rate_mbps":1000, "profile":"medium-s05", "rdo_px_per_deg":24},
    {"experiment_id":"q3b_overnight_pyro_97_light_s05_phase_rdo24", "phase":"q3b", "label":"pyrowave-97-light-s05-phase-rdo24-1000", "wavelet":"97", "rate_mbps":1000, "profile":"light-s05", "rdo_px_per_deg":24, "requires_light_phase_identity":True},
    {"experiment_id":"q3a_overnight_pyro_97_crop_1000_rdo16", "phase":"q3a", "label":"pyrowave-97-crop-rdo16-1000", "wavelet":"97", "rate_mbps":1000, "rdo_px_per_deg":16},
    {"experiment_id":"q3a_overnight_pyro_97_crop_1000_rdo20", "phase":"q3a", "label":"pyrowave-97-crop-rdo20-1000", "wavelet":"97", "rate_mbps":1000, "rdo_px_per_deg":20},
)
WAVELET_LABEL = {"haar": "Haar", "53": "CDF 5/3", "97": "CDF 9/7"}
CROPPED_SOURCE_SHA256 = "4c833e175610488ffa05a8037e52c166424db8308a67a2bfed4ed48861fad2e5"
FENCE_RECTANGLES = {"full_fov": {"eye": "left", "x": 1740, "y": 1310, "width": 240, "height": 274},
                    "cropped": {"mapped": {"eye": "left", "x": 1462, "y": 1036, "width": 240, "height": 274},
                                "source": {"eye": "left", "x": 1740, "y": 1310, "width": 240, "height": 274}}}
CROP_GEOMETRY = {
    "kind": "per_eye_crop", "source_eye": [3072, 3232], "target_eye": [2624, 2776],
    "tangent_multipliers": [.8542, .85],
    "eyes": [
        {"eye": "left", "x": 278, "y": 274, "width": 2624, "height": 2776,
         "ideal_offset": [278.310417777275, 274.82863217055296],
         "alignment_error": [-.3104177772750063, -.8286321705529645],
         "original_tangents": [-1.3763818740844727, .8390995860099792, -1.4281479120254517, .9656887650489807],
         "scaled_tangents": [-1.1757053968429565, .7167588663697242, -1.2139257252216338, .8208354502916336],
         "effective_tangents": [-1.1758923409118627, .7164980729188151, -1.225205074921988, .8308873185058041],
         "scaled_span_pixels": [2624.1023999999998, 2747.2]},
        {"eye": "right", "x": 170, "y": 274, "width": 2624, "height": 2776,
         "ideal_offset": [169.689582222725, 274.82863217055296],
         "alignment_error": [.3104177772750063, -.8286321705529645],
         "original_tangents": [-.8390995860099792, 1.3763818740844727, -1.4281479120254517, .9656887650489807],
         "scaled_tangents": [-.7167588663697242, 1.1757053968429565, -1.2139257252216338, .8208354502916336],
         "effective_tangents": [-.716498072918815, 1.175892340911863, -1.225205074921988, .8308873185058041],
         "scaled_span_pixels": [2624.1023999999998, 2747.2]}],
    "resampling": "none; fixed extents centred on scaled tangent rectangle",
    "alignment": "nearest even; ties-to-even"}


def _hash(path):
    return fb.sha256_file(Path(path))


def _module_hashes():
    root = Path(__file__).resolve().parent
    # The Q3 scorer is imported lazily so the adapter remains source-only until
    # a run starts, but its implementation is still part of a frozen plan.
    return {name: _hash(root / name) for name in ("pyro_q3_framebank.py", "framebank.py", "nvenc_framebank.py", "fence_metrics.py", "foveation.py", "pyrowave_wave.py")}


def _require_cropped_source(source: Path) -> fb.Y4MInfo:
    info = fb.inspect_y4m(source)
    if (info.width, info.height, info.frames, info.chroma, info.color_range, info.fps_num, info.fps_den) != (5248, 2776, 90, "420", "FULL", 90, 1):
        raise ValueError("Q3 cropped source must be 5248x2776, C420, full-range, 90 frames at 90 Hz")
    return info


def _require_full_source(source: Path) -> fb.Y4MInfo:
    info = fb.inspect_y4m(source)
    if (info.width, info.height, info.frames, info.chroma, info.color_range, info.fps_num, info.fps_den) != (6144, 3232, 90, "420", "FULL", 90, 1):
        raise ValueError("Q3 full source must be 6144x3232, C420, full-range, 90 frames at 90 Hz")
    return info


def _require_plan_source(source: Path, plan: dict) -> fb.Y4MInfo:
    geometry = plan.get("source", {}).get("geometry")
    if geometry == [5248, 2776]:
        return _require_cropped_source(source)
    if geometry == [6144, 3232]:
        return _require_full_source(source)
    raise ValueError("plan source geometry is unsupported")


def _source_contract(source: Path, info: fb.Y4MInfo) -> dict:
    return {"sha256": _hash(source), "geometry": [info.width, info.height],
            "frames": info.frames, "fps": [info.fps_num, info.fps_den],
            "chroma": info.chroma, "color_range": info.color_range,
            "frame_identity": fb.frame_records(source)}


def _q3b_transform(profile: str) -> dict:
    """Frozen cell-level WO-8 contract; the implementation remains unavailable here."""
    blur_only = profile.startswith("blur-only-")
    if "s0" in profile and "s05" not in profile:
        softness = 0.0
    elif "s1" in profile and "s05" not in profile:
        softness = 1.0
    else:
        softness = .5
    base = profile.removeprefix("blur-only-").rsplit("-s", 1)[0]
    return {"kind": "wo8_foveation", "profile": base, "softness": softness, "blur_only": blur_only}


def _light_phase_identity(value: dict | None) -> dict:
    if not isinstance(value, dict) or set(value) != {"implementation_revision", "implementation_source_sha256"}:
        raise ValueError("corrected-Light phase identity must be explicitly supplied")
    revision=value["implementation_revision"]; digest=value["implementation_source_sha256"]
    if (not isinstance(revision,str) or not revision or not isinstance(digest,str) or len(digest)!=64 or
            any(ch not in "0123456789abcdef" for ch in digest)):
        raise ValueError("corrected-Light phase identity is invalid")
    return {"implementation_revision":revision,"implementation_source_sha256":digest}


def _extension_transform(spec: dict, light_phase_identity: dict | None) -> dict | None:
    profile=spec.get("profile")
    if profile is None:
        return None
    transform=_q3b_transform(profile)
    if spec["experiment_id"] == "q3b_phase_pyro_97_light_s05_default_rdo" or spec.get("requires_light_phase_identity"):
        transform.update(_light_phase_identity(light_phase_identity))
    return transform


def _extension_matrix(rows: tuple[dict, ...], light_phase_identity: dict | None, *, kind: str) -> dict:
    """Exact, schema-visible identity for an additive extension matrix."""
    # Historical extension plans and their retained result records use this
    # exact object.  Do not add a generic kind or static-source label here.
    if rows is Q3_EXTENSION_ROWS:
        return {"runner":"pyrowave", "historical_q3b_dropped":["h264-dual-blur-light-s05-700"],
                "light_phase_identity":_light_phase_identity(light_phase_identity), "quality_windows_one_based":[[1,90],[10,89]], "fence_and_hvs_required":True,
                "offline_only_above_wifi_cap_mbps":[1500,2000]}
    common = {"runner": "pyrowave", "kind": kind,
              "quality_windows_one_based": [[1, 90], [10, 89]],
              "fence_and_hvs_required": True,
              "static_source_only": True}
    if any(row.get("requires_light_phase_identity") or
           row["experiment_id"] == "q3b_phase_pyro_97_light_s05_default_rdo" for row in rows):
        common["light_phase_identity"] = _light_phase_identity(light_phase_identity)
    return common


def build_plan(source: Path, vertical_pixels_per_degree: float, *, projection_evidence: str,
               crop_evidence: str, crops, full_source: Path, horizontal_pixels_per_degree: float | None = None,
               fixture: bool = False, include_q3b: bool = False) -> dict:
    """Freeze Q3a's five cropped rows. Q3b remains non-runnable until WO-8."""
    source = Path(source); info = _require_cropped_source(source)
    if _hash(source) != CROPPED_SOURCE_SHA256 and not fixture:
        raise ValueError("source does not match the reviewed Q3 cropped-source hash")
    if not projection_evidence.strip() or not crop_evidence.strip():
        raise ValueError("projection and crop evidence are required")
    if not isinstance(crops, list) or not crops:
        raise ValueError("frozen Q3 crop score definitions are required")
    # Reuse the only calibrated scorer-plan builder, then select the exact
    # experiment rows rather than recreating its projection/crop math here.
    full_source = Path(full_source)
    full_info = fb.inspect_y4m(full_source)
    if (full_info.width, full_info.height, full_info.frames, full_info.chroma, full_info.color_range) != (6144, 3232, 90, "420", "FULL"):
        raise ValueError("Q3 full source must be the reviewed 6144x3232 C420 90-frame parent")
    base = fb.build_plan(full_source, vertical_pixels_per_degree,
                         horizontal_pixels_per_degree=horizontal_pixels_per_degree,
                         projection_evidence=projection_evidence, crop_evidence=crop_evidence,
                         fixture=fixture, fps=90, wavelets=("haar", "53", "97"),
                         rates_mbps=(800, 1000), geometries=((2624, 2776),),
                         # The parent is the logged full presentation input.
                         # Resolve its fixed crops in that coordinate space once;
                         # cells below identify the native 2624x2776 crop that
                         # is actually encoded and scored.
                         display_eye=(3072, 3232), crops=crops)
    selected = {(w, r) for w, r in Q3A_ROWS}
    pairs = [(i, c) for i, c in enumerate(base["cells"])
             if (c["wavelet"], c["rate_mbps"]) in selected]
    cells = [dict(phase="q3a", source_geometry="crop", score_vertical_pixels_per_degree=float(vertical_pixels_per_degree), **c) for _, c in pairs]
    if include_q3b:
        from .foveation import FoveationConfig, encoded_size
        for p, w, r in Q3B_ROWS:
            transform = _q3b_transform(p); ew, eh = encoded_size(2624, 2776,
                FoveationConfig(transform["profile"], transform["softness"], transform["blur_only"]))
            cells.append(dict(phase="q3b", profile=p, source_geometry="crop", source_transform=transform,
                              wavelet=w, rate_mbps=r, fps=90, eye_width=ew, eye_height=eh,
                              stereo_width=ew*2, cap_bytes=fb.cap_bytes(r,90),
                              bits_per_pixel=fb.bpp(fb.cap_bytes(r,90),ew,eh),
                              encoded_chroma="420",
                              score_vertical_pixels_per_degree=float(vertical_pixels_per_degree),
                              requires_wo8_reduced_encode=True))
    calibration_cells = [base["hvs_calibration"]["codec_cells"][i] for i, _ in pairs]
    if include_q3b:
        calibration_cells.extend(fb.hvs_calibration_for_vertical_ppd(vertical_pixels_per_degree, 2776)
                                 for _ in Q3B_ROWS)
    return {"schema": SCHEMA, "kind": "pyro_q3_framebank", "fixture_only": bool(fixture),
            "source": _source_contract(source, info), "source_derivation": {"parent_sha256": _hash(full_source), "parent_geometry": [full_info.width, full_info.height], "operation": "native_per_eye_crop_no_resampling"}, "projection_evidence": projection_evidence.strip(),
            "crop_evidence": crop_evidence.strip(), "crop_geometry": copy.deepcopy(CROP_GEOMETRY),
            "frozen_module_hashes": _module_hashes(), "cells": cells,
            "presentation_eye": base["presentation_eye"], "projection": base["projection"],
            "crops": base["crops"], "hvs_calibration": {**base["hvs_calibration"], "codec_cells": calibration_cells},
            "source_adapter": {"kind": "per_eye_crop", "geometry": copy.deepcopy(CROP_GEOMETRY),
                               "future_transform": None},
            "fence_rectangles": {**copy.deepcopy(FENCE_RECTANGLES), "cropped": {**copy.deepcopy(FENCE_RECTANGLES["cropped"]), "geometry": copy.deepcopy(CROP_GEOMETRY)}},
            "quality_contract": {"score_windows_one_based": [[1, 90], [10, 89]], "fence_metric": True,
                                 "per_frame_identity": True, "timing_requires_native_per_frame_record": True,
                                 "q3b_requires_reduced_encode_then_expanded_score": True}}


def _rdo_descriptor(value):
    """Freeze WO-7 PPD request, float32 Nyquist scale and native-log proof."""
    import numpy as np
    if value is None:
        cpd=float(np.float32(.34) * np.float32(96.0) * np.float32(1.0))
        return {"mode":"build_default", "environment":None, "requested_ppd":None,
                "requested_log":"(legacy 96 DPI @ 1m)", "effective_ppd":float(np.float32(cpd * 2.0)),
                "cpd_nyquist":cpd, "legacy_equivalent":True, "native_log_required":True}
    if type(value) is not int or not 0 < value <= 10000:
        raise ValueError("Q3 extension RDO density must be an integer in (0, 10000] or default")
    return {"mode":"px_per_deg", "environment":{"PYROWAVE_RDO_PX_PER_DEG":str(value)},
            "requested_ppd":float(value), "requested_log":str(value), "effective_ppd":float(value),
            "cpd_nyquist":float(value) / 2.0, "legacy_equivalent":False, "native_log_required":True}


def _rdo_effective_from_native_log(text: str, requested: dict) -> dict:
    """Require consistent native PPD/Nyquist logs, allowing only print rounding."""
    import math
    import re
    matches=list(re.finditer(r"PyroWave RDO viewing density: requested (?P<requested>[^,]+), effective (?P<ppd>[0-9]+(?:\.[0-9]+)?) px/deg, Nyquist (?P<cpd>[0-9]+(?:\.[0-9]+)?) cycles/deg(?P<legacy> \(legacy-equivalent\))?", text))
    if not matches:
        raise ValueError("native RDO viewing-density log is missing")
    parsed=[]
    for match in matches:
        ppd=float(match.group("ppd")); cpd=float(match.group("cpd")); legacy=bool(match.group("legacy"))
        if (match.group("requested") != requested["requested_log"] or
                not math.isclose(ppd,requested["effective_ppd"],rel_tol=0.0,abs_tol=5e-6) or
                not math.isclose(cpd,requested["cpd_nyquist"],rel_tol=0.0,abs_tol=5e-6) or
                legacy != requested["legacy_equivalent"]):
            raise ValueError("native RDO viewing-density log differs from frozen request")
        parsed.append((match.group("requested"),ppd,cpd,legacy))
    if len(set(parsed)) != 1:
        raise ValueError("native RDO viewing-density logs are inconsistent")
    raw,ppd,cpd,legacy=parsed[0]
    return {"requested_log":raw, "requested_ppd":requested["requested_ppd"],
            "effective_ppd":ppd, "cpd_nyquist":cpd, "legacy_equivalent":legacy,
            "source":"native_encoder_log", "decimal_abs_tolerance":5e-6}

def build_extension_plan(source: Path, vertical_pixels_per_degree: float, *, projection_evidence: str,
                         crop_evidence: str, crops, full_source: Path,
                         horizontal_pixels_per_degree: float | None = None, fixture: bool = False,
                         light_phase_identity: dict | None = None,
                         _rows: tuple[dict, ...] = Q3_EXTENSION_ROWS,
                         _matrix_kind: str = "owner_quality_extension") -> dict:
    """Freeze the seven owner-selected PyroWave quality-extension rows.

    Historical Q3a/Q3b evidence is not included or rewritten.  This separate
    manifest makes all new RDO and above-Wi-Fi-cap conditions reviewable.
    """
    base=build_plan(source, vertical_pixels_per_degree, projection_evidence=projection_evidence,
                    crop_evidence=crop_evidence, crops=crops, full_source=full_source,
                    horizontal_pixels_per_degree=horizontal_pixels_per_degree, fixture=fixture)
    cells=[]
    for spec in _rows:
        row=dict(source_geometry="crop", fps=90, encoded_chroma="420",
                 score_vertical_pixels_per_degree=float(vertical_pixels_per_degree),
                 requires_wo8_reduced_encode=False, **copy.deepcopy(spec))
        transform=_extension_transform(spec, light_phase_identity)
        if transform is not None:
            if (not fixture and (spec["experiment_id"] == "q3b_phase_pyro_97_light_s05_default_rdo" or spec.get("requires_light_phase_identity")) and
                    _hash(Path(__file__).resolve().parent / "foveation.py") != transform["implementation_source_sha256"]):
                raise ValueError("WO-8 corrected-Light source hash is not active; do not freeze this rescore")
            from .foveation import FoveationConfig, encoded_size
            ew,eh=encoded_size(2624,2776,FoveationConfig(transform["profile"],transform["softness"],transform["blur_only"]))
            row.update(source_transform=transform, requires_wo8_reduced_encode=True)
        else:
            ew,eh=2624,2776
        cap=fb.cap_bytes(row["rate_mbps"],90)
        row.update(eye_width=ew,eye_height=eh,stereo_width=ew*2,cap_bytes=cap,
                   bits_per_pixel=fb.bpp(cap,ew,eh), rdo_viewing_density=_rdo_descriptor(row.pop("rdo_px_per_deg")))
        cells.append(row)
    base.update(cells=cells, extension_matrix=_extension_matrix(_rows, light_phase_identity, kind=_matrix_kind),
                hvs_calibration={**base["hvs_calibration"], "codec_cells":[fb.hvs_calibration_for_vertical_ppd(
                    vertical_pixels_per_degree,2776) for _ in cells]})
    validate_plan(base)
    return base


def build_overnight_static_plan(source: Path, vertical_pixels_per_degree: float, *, projection_evidence: str,
                                crop_evidence: str, crops, full_source: Path,
                                horizontal_pixels_per_degree: float | None = None, fixture: bool = False,
                                light_phase_identity: dict | None = None) -> dict:
    """Freeze the six new static-crop native PyroWave cells.

    This deliberately accepts only the reviewed static crop source. Synthetic
    motion uses a separate runner and may never be substituted here.
    """
    return build_extension_plan(source, vertical_pixels_per_degree,
                                projection_evidence=projection_evidence, crop_evidence=crop_evidence,
                                crops=crops, full_source=full_source,
                                horizontal_pixels_per_degree=horizontal_pixels_per_degree,
                                fixture=fixture, light_phase_identity=light_phase_identity,
                                _rows=Q3_OVERNIGHT_STATIC_ROWS,
                                _matrix_kind="overnight_static_rdo")


def build_overnight_full_a2_plan(source: Path, vertical_pixels_per_degree: float, *, projection_evidence: str,
                                 crop_evidence: str, crops, horizontal_pixels_per_degree: float | None = None,
                                 fixture: bool = False) -> dict:
    """Freeze static full-parent Haar/500/RDO24 (the a2 control).

    It is deliberately a separate plan because it encodes the full parent,
    whereas the six overnight native cells encode the reviewed static crop.
    """
    source = Path(source); info = _require_full_source(source)
    base = fb.build_plan(source, vertical_pixels_per_degree,
                         horizontal_pixels_per_degree=horizontal_pixels_per_degree,
                         projection_evidence=projection_evidence, crop_evidence=crop_evidence,
                         fixture=fixture, fps=90, wavelets=("haar",), rates_mbps=(500,),
                         geometries=((3072, 3232),), display_eye=(3072, 3232), crops=crops)
    cell = dict(base["cells"][0], experiment_id="q3a_overnight_pyro_haar_full_500_rdo24",
                phase="q3a", source_geometry="full_fov",
                score_vertical_pixels_per_degree=float(vertical_pixels_per_degree),
                rdo_viewing_density=_rdo_descriptor(24), requires_wo8_reduced_encode=False)
    plan = {"schema": SCHEMA, "kind": "pyro_q3_framebank", "fixture_only": bool(fixture),
            "source": _source_contract(source, info),
            "source_derivation": {"operation": "full_parent_no_resampling"},
            "projection_evidence": projection_evidence.strip(), "crop_evidence": crop_evidence.strip(),
            "frozen_module_hashes": _module_hashes(), "cells": [cell],
            "presentation_eye": base["presentation_eye"], "projection": base["projection"],
            "crops": base["crops"],
            "hvs_calibration": {**base["hvs_calibration"], "codec_cells": [base["hvs_calibration"]["codec_cells"][0]]},
            "source_adapter": {"kind": "full_parent", "resampling": "none"},
            "fence_rectangles": {"full_fov": copy.deepcopy(FENCE_RECTANGLES["full_fov"])},
            "quality_contract": {"score_windows_one_based": [[1, 90], [10, 89]], "fence_metric": True,
                                 "per_frame_identity": True, "timing_requires_native_per_frame_record": True},
            "extension_matrix": {"runner": "pyrowave", "kind": "overnight_full_a2_rdo",
                                 "static_source_only": True, "quality_windows_one_based": [[1, 90], [10, 89]],
                                 "fence_and_hvs_required": True}}
    validate_plan(plan)
    return plan


def _extension_rows_for_matrix(extension: dict) -> tuple[dict, ...]:
    if not isinstance(extension, dict):
        raise ValueError("Q3 extension matrix is invalid")
    if "kind" not in extension:
        return Q3_EXTENSION_ROWS
    if extension.get("kind") == "overnight_static_rdo":
        return Q3_OVERNIGHT_STATIC_ROWS
    raise ValueError("unrecognized Q3 extension matrix kind")


def _validate_overnight_full_a2(plan: dict) -> dict:
    source = plan.get("source", {})
    if (source.get("geometry"), source.get("frames"), source.get("fps"), source.get("chroma"), source.get("color_range")) != ([6144, 3232], 90, [90, 1], "420", "FULL"):
        raise ValueError("overnight full a2 source contract drifted")
    if plan.get("source_derivation") != {"operation": "full_parent_no_resampling"}:
        raise ValueError("overnight full a2 derivation drifted")
    if plan.get("frozen_module_hashes") != _module_hashes():
        raise ValueError("runner module hash drifted; freeze a new plan")
    if plan.get("source_adapter") != {"kind": "full_parent", "resampling": "none"}:
        raise ValueError("overnight full a2 source adapter drifted")
    if plan.get("fence_rectangles") != {"full_fov": FENCE_RECTANGLES["full_fov"]}:
        raise ValueError("overnight full a2 fence rectangle drifted")
    expected_matrix = {"runner": "pyrowave", "kind": "overnight_full_a2_rdo", "static_source_only": True,
                       "quality_windows_one_based": [[1, 90], [10, 89]], "fence_and_hvs_required": True}
    if plan.get("extension_matrix") != expected_matrix:
        raise ValueError("overnight full a2 matrix provenance drifted")
    cells = plan.get("cells")
    if not isinstance(cells, list) or len(cells) != 1:
        raise ValueError("overnight full a2 requires exactly one cell")
    cell = cells[0]; cap = fb.cap_bytes(500, 90)
    expected = {"experiment_id": "q3a_overnight_pyro_haar_full_500_rdo24", "phase": "q3a",
                "source_geometry": "full_fov", "wavelet": "haar", "rate_mbps": 500, "fps": 90,
                "eye_width": 3072, "eye_height": 3232, "stereo_width": 6144, "encoded_chroma": "420",
                "cap_bytes": cap, "bits_per_pixel": fb.bpp(cap, 3072, 3232),
                "score_vertical_pixels_per_degree": plan.get("projection", {}).get("vertical_pixels_per_degree"),
                "rdo_viewing_density": _rdo_descriptor(24), "requires_wo8_reduced_encode": False}
    if any(cell.get(key) != value for key, value in expected.items()) or cell.get("source_transform") is not None:
        raise ValueError("overnight full a2 codec row drifted")
    calibration = plan.get("hvs_calibration", {})
    if not isinstance(calibration, dict) or len(calibration.get("codec_cells", [])) != 1:
        raise ValueError("overnight full a2 calibrated scoring contract drifted")
    return plan


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA or plan.get("kind") != "pyro_q3_framebank":
        raise ValueError("not a Pyro Q3 frame-bank manifest")
    if plan.get("extension_matrix", {}).get("kind") == "overnight_full_a2_rdo":
        return _validate_overnight_full_a2(plan)
    source = plan.get("source", {})
    if source.get("geometry") != [5248, 2776] or source.get("frames") != 90 or source.get("fps") != [90, 1] or source.get("chroma") != "420" or source.get("color_range") != "FULL":
        raise ValueError("Q3 source contract drifted")
    derivation = plan.get("source_derivation", {})
    if (derivation.get("parent_geometry") != [6144, 3232] or derivation.get("operation") != "native_per_eye_crop_no_resampling" or
            not isinstance(derivation.get("parent_sha256"), str) or len(derivation["parent_sha256"]) != 64):
        raise ValueError("Q3 cropped-source derivation drifted")
    if plan.get("frozen_module_hashes") != _module_hashes():
        raise ValueError("runner module hash drifted; freeze a new plan")
    actual_a = [c for c in plan.get("cells", []) if c.get("phase") == "q3a"]
    extension = plan.get("extension_matrix")
    if extension is None and ([(c.get("wavelet"), c.get("rate_mbps")) for c in actual_a] != list(Q3A_ROWS) or any(
            c.get("eye_width") != 2624 or c.get("eye_height") != 2776 or c.get("stereo_width") != 5248 or
            c.get("cap_bytes") != fb.cap_bytes(c["rate_mbps"], 90) or c.get("source_geometry") != "crop" or
            c.get("score_vertical_pixels_per_degree") != plan.get("projection", {}).get("vertical_pixels_per_degree") for c in actual_a)):
        raise ValueError("Q3a rows drifted")
    if plan.get("fence_rectangles", {}).get("cropped", {}).get("mapped") != FENCE_RECTANGLES["cropped"]["mapped"]:
        raise ValueError("Q3 cropped fence rectangle drifted")
    adapter = plan.get("source_adapter", {})
    if adapter.get("kind") != "per_eye_crop" or adapter.get("geometry") != CROP_GEOMETRY:
        raise ValueError("Q3 source adapter geometry drifted")
    actual_b = [c for c in plan.get("cells", []) if c.get("phase") == "q3b"]
    calibration = plan.get("hvs_calibration", {})
    if not isinstance(calibration, dict) or len(calibration.get("codec_cells", [])) != len(actual_a) + len(actual_b):
        raise ValueError("Q3 calibrated scoring contract drifted")
    if extension is None and actual_b and [(c.get("profile"), c.get("wavelet"), c.get("rate_mbps")) for c in actual_b] != list(Q3B_ROWS):
        raise ValueError("Q3b rows drifted")
    extension_rows = _extension_rows_for_matrix(extension) if extension is not None else None
    for cell in actual_b:
        expected_transform = (_extension_transform(next(row for row in extension_rows
                                                        if row["label"] == cell.get("label")),
                                                  extension.get("light_phase_identity"))
                              if extension is not None else _q3b_transform(cell["profile"]))
        if not cell.get("requires_wo8_reduced_encode") or cell.get("source_transform") != expected_transform:
            raise ValueError("Q3b row lacks reduced-encode requirement")
        from .foveation import FoveationConfig, encoded_size
        ew, eh = encoded_size(2624,2776,FoveationConfig(cell["source_transform"]["profile"],cell["source_transform"]["softness"],cell["source_transform"]["blur_only"]))
        cap=fb.cap_bytes(cell["rate_mbps"],90)
        if (cell.get("eye_width"),cell.get("eye_height"),cell.get("stereo_width")) != (ew,eh,ew*2) or cell.get("cap_bytes") != cap or cell.get("bits_per_pixel") != fb.bpp(cap,ew,eh) or cell.get("encoded_chroma") != "420" or cell.get("score_vertical_pixels_per_degree") != plan["projection"]["vertical_pixels_per_degree"]:
            raise ValueError("Q3b reduced geometry/cap/scoring contract drifted")
    if extension is not None:
        actual_extension = [cell for cell in plan.get("cells", []) if cell.get("phase") in ("q3a", "q3b")]
        if ([cell.get("label") for cell in actual_extension] != [row["label"] for row in extension_rows] or
                any(cell.get("phase") not in ("q3a","q3b") or cell.get("fps") != 90 or
                    cell.get("source_geometry") != "crop" for cell in actual_extension) or
                len(actual_extension) != len(plan.get("cells", []))):
            raise ValueError("Q3 extension rows drifted")
        if extension != _extension_matrix(extension_rows, extension.get("light_phase_identity"),
                                           kind=extension.get("kind")):
            raise ValueError("Q3 extension matrix provenance drifted")
        for cell, spec in zip(actual_extension, extension_rows):
            transform = _extension_transform(spec, extension.get("light_phase_identity"))
            if (cell.get("experiment_id") != spec["experiment_id"] or cell.get("phase") != spec["phase"] or
                    cell.get("wavelet") != spec["wavelet"] or cell.get("rate_mbps") != spec["rate_mbps"] or
                    cell.get("source_transform") != transform):
                raise ValueError("Q3 extension codec row drifted")
            if cell.get("rdo_viewing_density") != _rdo_descriptor(spec.get("rdo_px_per_deg")):
                raise ValueError("Q3 extension RDO provenance drifted")
            if bool(cell.get("offline_only_above_wifi_cap",False)) != bool(spec.get("offline_only_above_wifi_cap",False)):
                raise ValueError("Q3 extension offline-only label drifted")
            if transform:
                from .foveation import FoveationConfig, encoded_size
                ew,eh=encoded_size(2624,2776,FoveationConfig(transform["profile"],transform["softness"],transform["blur_only"]))
            else:
                ew,eh=2624,2776
            cap=fb.cap_bytes(spec["rate_mbps"],90)
            if (cell.get("eye_width"),cell.get("eye_height"),cell.get("stereo_width"),cell.get("cap_bytes")) != (ew,eh,ew*2,cap):
                raise ValueError("Q3 extension encoded geometry/cap drifted")
            if cell.get("bits_per_pixel") != fb.bpp(cap,ew,eh) or cell.get("encoded_chroma") != "420" or cell.get("score_vertical_pixels_per_degree") != plan["projection"]["vertical_pixels_per_degree"]:
                raise ValueError("Q3 extension quality contract drifted")
    return plan


def parse_wave(path: Path, cell: dict) -> dict:
    """Validate the private container as 90 exact payload records, without decoding it."""
    data = Path(path).read_bytes()
    expected_header = wave.header(cell["stereo_width"], cell["eye_height"], fps_num=90, chroma=wave.CHROMA_420, full_range=True)
    if not data.startswith(expected_header):
        raise ValueError("PyroWave container header mismatch")
    cursor, sizes = len(expected_header), []
    while cursor < len(data):
        if cursor + 4 > len(data): raise ValueError("truncated PyroWave frame length")
        size = int.from_bytes(data[cursor:cursor + 4], "little"); cursor += 4
        if size <= 0 or cursor + size > len(data): raise ValueError("truncated PyroWave payload")
        sizes.append(size); cursor += size
    if cursor != len(data) or len(sizes) != 90: raise ValueError("PyroWave container frame count mismatch")
    if any(size > cell["cap_bytes"] for size in sizes): raise ValueError("PyroWave frame payload exceeds frozen cap")
    return {"container_sha256": hashlib.sha256(data).hexdigest(), "container_bytes": len(data),
            "payload_bytes": sizes, "frames": len(sizes), "header_bytes": len(expected_header),
            "payload_bytes_total": sum(sizes), "actual_mbps_payload_f90": sum(sizes)*8*90/len(sizes)/1_000_000}


def _native_records(path: Path, payloads: list[int]) -> dict:
    """Accept only the native encoder's forthcoming per-frame evidence schema."""
    if path is None or not Path(path).is_file():
        return {"qualified": False, "reason": "native_per_frame_telemetry_missing"}
    try:
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise ValueError("native telemetry JSONL is invalid") from exc
    if len(rows) != 90 or not all(isinstance(row, dict) for row in rows): raise ValueError("native telemetry does not contain 90 frames")
    required = ("schema_version", "frame_id", "payload_bytes", "cpu_command_record_submit_ms", "submit_to_observed_fence_ms")
    if [r.get("frame_id") for r in rows] != list(range(90)) or any(any(k not in r for k in required) for r in rows):
        raise ValueError("native telemetry schema mismatch")
    if any(r["schema_version"] != 1 or not isinstance(r["payload_bytes"], int) or r["payload_bytes"] <= 0 or
           any(not isinstance(r[key], (int, float)) or not math.isfinite(r[key]) or r[key] < 0
               for key in ("cpu_command_record_submit_ms", "submit_to_observed_fence_ms")) for r in rows):
        raise ValueError("native telemetry values invalid")
    if [r["payload_bytes"] for r in rows] != payloads: raise ValueError("native telemetry payload mismatch")
    return {"qualified": True, "frames": rows, "semantics": {"submit_to_observed_fence_ms": "completion latency, not GPU execution"}}


def _q3b_encoded_source_provenance(path: Path, identities: list[dict]) -> dict:
    """Bind the generated reduced Y4M to the hashes written by the transform."""
    records = fb.frame_records(path)
    expected = [{"source_frame": item["source_frame"],
                 "source_sha256": item["encoded_reference_sha256"]}
                for item in identities]
    if records != expected:
        raise ValueError("q3b_encoded_source_identity_mismatch")
    return {"sha256": _hash(path), "frames": len(records),
            "frame_identity_sha256": hashlib.sha256(
                fb.report_json(records).encode("utf-8")).hexdigest()}


def _same_frame_scores(plan, index, cell, tools, guard, directory, source, source_info, decoded, decoded_info, timeout, keep_artifacts, *, reference=None, reference_info=None, matching_blur_reference=None):
    """Use Q3's shared scorer after its revision is merged; never silently downgrade it."""
    from . import nvenc_framebank as nvenc
    scorer = getattr(nvenc, "_same_frame_scores", None)
    if scorer is None: raise RuntimeError("shared_q3_scorer_unavailable")
    reference = source if reference is None else reference; reference_info = source_info if reference_info is None else reference_info
    return scorer(plan, index, cell, tools, guard, directory, source, source_info, decoded, decoded_info,
                  reference, reference_info, timeout, keep_artifacts, matching_blur_reference=matching_blur_reference)


def _result_base(raw_plan: bytes, source: Path, tools: dict, tool_build: dict | None) -> dict:
    return {"schema": SCHEMA, "kind": "pyro_q3_framebank_result", "frozen_plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
            "source_sha256_start": _hash(source), "source_sha256_end": None,
            "tool_provenance_start": {k: _hash(v) for k, v in tools.items()}, "tool_provenance_end": None,
            "tools_build_provenance": tool_build, "module_hashes": _module_hashes(), "cells": [],
            "complete": False, "failure_reasons": []}


def verify_split_bundles(tools: dict, codec_metadata: Path, scorer_metadata: Path | None = None,
                         scorer_compatibility: Path | None = None) -> dict:
    """Verify codec and scorer bundles separately before mixing their binaries.

    A telemetry rebuild may replace encode/decode while comparisons deliberately
    retain the earlier qualified HVS scorer.  Each package is verified using its
    own three binaries; only after equal HVS implementation evidence is checked
    may the new codec pair and old scorer be used in one Q3 result.
    """
    codec_metadata = Path(codec_metadata); codec_bundle = codec_metadata.parent
    codec_tools = {"encode": codec_bundle / "pyrowave-encode.exe", "decode": codec_bundle / "pyrowave-decode.exe",
                   "psnr_hvs_m_h": codec_bundle / "pyrowave-psnr-hvs-m.exe"}
    codec = fb.verify_tools_build(codec_tools, codec_metadata)
    if _hash(tools["encode"]) != _hash(codec_tools["encode"]) or _hash(tools["decode"]) != _hash(codec_tools["decode"]):
        raise ValueError("codec binaries differ from codec bundle metadata")
    scorer_metadata = codec_metadata if scorer_metadata is None else Path(scorer_metadata)
    scorer_bundle = scorer_metadata.parent
    scorer_tools = {"encode": scorer_bundle / "pyrowave-encode.exe", "decode": scorer_bundle / "pyrowave-decode.exe",
                    "psnr_hvs_m_h": scorer_bundle / "pyrowave-psnr-hvs-m.exe"}
    if scorer_compatibility is None:
        scorer = fb.verify_tools_build(scorer_tools, scorer_metadata)
    else:
        scorer = fb.verify_historical_hvs_scorer(scorer_tools, scorer_metadata, scorer_compatibility)
    if _hash(tools["psnr_hvs_m_h"]) != _hash(scorer_tools["psnr_hvs_m_h"]):
        raise ValueError("HVS scorer differs from scorer bundle metadata")
    for key in ("scorer_source", "scorer_shader_sha256"):
        if codec.get(key) != scorer.get(key):
            raise ValueError("codec/scorer bundles do not prove the same HVS implementation")
    if scorer.get('historical_scorer_mode'):
        if codec.get('sources_lock_sha256') != scorer.get('current_sources_lock_sha256'):
            raise ValueError('codec bundle does not use the current lock required by historical scorer proof')
    elif codec.get('sources_lock_sha256') != scorer.get('sources_lock_sha256'):
        raise ValueError("codec/scorer bundles do not prove the same source-lock record")
    return {"codec_bundle": codec, "scorer_bundle": scorer,
            "separate_scorer_bundle": scorer_metadata != codec_metadata,
            "hvs_implementation_unchanged": True,
            "historical_scorer_mode": scorer.get('historical_scorer_mode') is True,
            "codec_sources_lock_sha256": codec.get('sources_lock_sha256'),
            "scorer_sources_lock_sha256": scorer.get('sources_lock_sha256')}


def _select_cells(plan: dict, phase: str | None, cell_indices: list[int] | tuple[int, ...] | None) -> list[tuple[int, dict]]:
    """Select original manifest indices before opening the GPU scoring gate."""
    if phase is not None and phase not in ("q3a", "q3b"):
        raise ValueError("phase must be q3a or q3b")
    cells = plan["cells"]
    if cell_indices is None:
        indices = list(range(len(cells)))
    else:
        if not isinstance(cell_indices, (list, tuple)):
            raise ValueError("cell_indices must be a list of original plan indices")
        if any(type(index) is not int for index in cell_indices):
            raise ValueError("cell_indices must contain only integers")
        if len(set(cell_indices)) != len(cell_indices):
            raise ValueError("cell_indices must not contain duplicates")
        if any(index < 0 or index >= len(cells) for index in cell_indices):
            raise ValueError("cell_indices contains an out-of-range plan index")
        indices = list(cell_indices)
    selected = [(index, cells[index]) for index in indices if phase is None or cells[index].get("phase") == phase]
    if len(selected) != len(indices):
        raise ValueError("cell_indices includes a cell outside the requested phase")
    if not selected:
        raise ValueError("requested selection has no cells")
    return selected


def run_plan(plan_path: Path, source: Path, private_out: Path, tools: dict, window: Path, *, tools_metadata: Path,
             scorer_tools_metadata: Path | None = None, command_timeout_s: float = 900,
             keep_artifacts: bool = False, supervised: bool = False, resume: bool = False, phase: str | None = None,
             cell_indices: list[int] | tuple[int, ...] | None = None, preparation_workers: int = 1,
             scorer_compatibility: Path | None = None) -> dict:
    """Run only frozen Q3a rows; Q3b fails closed until a real WO-8 adapter exists."""
    from . import nvenc_framebank as nvenc
    raw_plan = Path(plan_path).read_bytes(); plan = validate_plan(json.loads(raw_plan)); source = Path(source)
    preparation_workers = nvenc._q3b_preparation_workers(preparation_workers)
    info = _require_plan_source(source, plan); guard = fb.WindowGuard(Path(window), supervised=supervised)
    if _source_contract(source, info) != plan["source"]: raise ValueError("source contract differs from frozen plan")
    required = {"encode", "decode", "psnr_hvs_m_h", "ffmpeg"}
    if set(tools) != required: raise ValueError("Pyro Q3 runner requires exactly encode/decode/psnr_hvs_m_h tools")
    fb.required_tools(tools); guard.status(); build = verify_split_bundles(
        tools, Path(tools_metadata), scorer_tools_metadata, scorer_compatibility)
    selected = _select_cells(plan, phase, cell_indices)
    requested_indices = [index for index, _ in selected]
    out = Path(private_out)
    if out.exists():
        if not resume: raise FileExistsError("private output exists; explicit resume required")
        prior = json.loads((out / "framebank-private.json").read_text(encoding="utf-8"))
        if prior.get("frozen_plan_sha256") != hashlib.sha256(raw_plan).hexdigest() or prior.get("source_sha256_start") != _hash(source) or prior.get("tool_provenance_start") != {k: _hash(v) for k, v in tools.items()}:
            raise ValueError("resume provenance mismatch")
        if prior.get("failure_reasons"):
            # An interrupted row may have a partial elementary stream. Never encode it again automatically.
            raise RuntimeError("interrupted run preserved; manual review required before any cell replay")
        if not isinstance(prior.get("cells"), list) or any(type(row.get("plan_index")) is not int for row in prior["cells"]):
            raise ValueError("resume result lacks original plan-index evidence")
        completed = [row["plan_index"] for row in prior["cells"]]
        if len(set(completed)) != len(completed):
            raise ValueError("resume result repeats a plan index")
        selected = [(index, cell) for index, cell in selected if index not in set(completed)]
        result = prior
        if not selected:
            # All requested cells are already evidenced. Do not reopen the GPU
            # sanity gate or regenerate any codec artifact on a resume.
            result["requested_phase"] = phase; result["requested_cell_indices"] = cell_indices
            result["selected_plan_indices"] = requested_indices
            result.setdefault("run_scopes", []).append({"phase": phase, "requested_cell_indices": cell_indices,
                                                         "selected_plan_indices": requested_indices})
            result["complete"] = not result["failure_reasons"] and all(
                index in set(completed) for index in requested_indices)
            (out / "framebank-private.json").write_text(fb.report_json(result), encoding="utf-8")
            return result
    else:
        out.mkdir(parents=True); result = _result_base(raw_plan, source, tools, build)
    result["q3b_preparation_workers"] = preparation_workers
    try:
        env, _ = fb.codec_environment(os.environ, "haar")
        result["hvs_gpu_sanity"] = fb.hvs_gpu_sanity(tools["psnr_hvs_m_h"], out / "scorer-sanity",
                                                      plan["projection"]["vertical_pixels_per_degree"], guard, env, command_timeout_s)
        if not result["hvs_gpu_sanity"].get("passed"): raise RuntimeError("hvs_gpu_sanity_failed")
        result["requested_phase"] = phase; result["requested_cell_indices"] = cell_indices
        result["selected_plan_indices"] = requested_indices
        result.setdefault("run_scopes", []).append({"phase": phase, "requested_cell_indices": cell_indices,
                                                     "selected_plan_indices": requested_indices})
        for index, cell in selected:
            directory = out / f"cell-{index:02d}-{cell['wavelet']}-{cell['rate_mbps']}"; directory.mkdir()
            encoded, decoded = directory / "encoded.wave", directory / "decoded.y4m"; row = {**copy.deepcopy(cell), "plan_index": index}
            try:
                env, row["codec_environment"] = fb.codec_environment(os.environ, cell["wavelet"])
                rdo = cell.get("rdo_viewing_density")
                if rdo is not None:
                    env.update(rdo.get("environment") or {})
                    row["codec_environment"]["rdo_viewing_density"] = copy.deepcopy(rdo)
                encode_source, encode_info = source, info
                score_ref, score_blur, score_info = source, None, info
                if cell.get("source_transform") is not None:
                    encode_source = directory / "reduced-encoded-source.y4m"
                    score_ref, score_blur = directory / "score-sharp-reference.y4m", directory / "score-blur-reference.y4m"
                    encode_info, score_info, identities, transform = nvenc._stream_q3b_sources(
                        source, info, plan["crop_geometry"], cell["source_transform"], encode_source, score_ref, score_blur,
                        preparation_workers=preparation_workers, guard=guard)
                    row["q3b_encoded_source"] = _q3b_encoded_source_provenance(encode_source, identities)
                    transform_identity={key: transform[key] for key in ("implementation_revision", "implementation_source_sha256") if key in transform}
                    if transform_identity:
                        row["q3b_encoded_source"]["source_transform_identity"] = transform_identity
                    row["q3b_transform"] = transform
                timing = directory / "pyrowave-encode-timing.jsonl"
                start = time.time(); code, stdout, stderr = guard.run([str(tools["encode"]), str(encode_source), str(encoded), str(cell["cap_bytes"]), "--timing-jsonl", str(timing)], cwd=directory, env=env, timeout_s=command_timeout_s); end = time.time()
                if code or not encoded.is_file(): raise RuntimeError("encode_failed")
                if WAVELET_LABEL[cell["wavelet"]] not in stdout + stderr and not plan["fixture_only"]: raise RuntimeError("encoder_wavelet_not_confirmed")
                if cell.get("rdo_viewing_density") is not None:
                    row["rdo_effective"] = _rdo_effective_from_native_log(stdout + "\n" + stderr,
                                                                           cell["rdo_viewing_density"])
                row["encode_wall_interval_s"] = [start, end]; row["bitstream"] = parse_wave(encoded, cell)
                row["native_encoder_telemetry"] = _native_records(timing, row["bitstream"]["payload_bytes"])
                if not row["native_encoder_telemetry"]["qualified"]: raise RuntimeError("native_per_frame_telemetry_missing")
                code, stdout, stderr = guard.run([str(tools["decode"]), str(encoded), str(decoded)], cwd=directory, env=env, timeout_s=command_timeout_s)
                if code or not decoded.is_file(): raise RuntimeError("decode_failed")
                if WAVELET_LABEL[cell["wavelet"]] not in stdout + stderr and not plan["fixture_only"]: raise RuntimeError("decoder_wavelet_not_confirmed")
                row["decoded_y4m_header"] = fb.canonicalize_decoded_header(decoded); decoded_info = fb._assert_same_frames(encode_source, decoded, encode_info)
                score_decoded, score_decoded_info = decoded, decoded_info
                if cell.get("source_transform") is not None:
                    score_decoded = directory / "score-reconstructed-decoded.y4m"
                    nvenc._reconstruct_q3b_decoded(decoded, decoded_info, score_decoded, score_info, cell["source_transform"])
                    score_decoded_info = fb._assert_same_frames(score_ref, score_decoded, score_info)
                row["decoded_frame_identity"] = [{"frame": i, "source_sha256": src["source_sha256"], "decoded_small_sha256": got} for (i, _, got), src in zip(fb.iter_y4m(decoded, decoded_info), plan["source"]["frame_identity"])]
                if len(row["decoded_frame_identity"]) != 90: raise ValueError("decoded_identity_or_geometry_mismatch")
                if cell.get("source_transform") is not None:
                    rebuilt = [digest for _, _, digest in fb.iter_y4m(score_decoded, score_decoded_info)]
                    if len(identities) != 90 or len(rebuilt) != 90: raise ValueError("q3b_transformed_identity_mismatch")
                    transform_identity={key: cell["source_transform"][key] for key in ("implementation_revision", "implementation_source_sha256") if key in cell["source_transform"]}
                    row["q3b_frame_identity"] = [{**identities[i], "decoded_small_sha256": row["decoded_frame_identity"][i]["decoded_small_sha256"], "reconstructed_sha256": rebuilt[i], **({"source_transform_identity":transform_identity} if transform_identity else {})} for i in range(90)]
                row.update(_same_frame_scores(plan, index, cell, tools, guard, directory, source, info, score_decoded, score_decoded_info, command_timeout_s, keep_artifacts, reference=score_ref, reference_info=score_info, matching_blur_reference=score_blur))
            except (PermissionError, TimeoutError, ValueError, RuntimeError) as exc:
                row["error"] = str(exc); result["failure_reasons"].append(row["error"])
            result["cells"].append(row); (out / "framebank-progress.json").write_text(fb.report_json(result), encoding="utf-8")
            if row.get("error"): break
            if not keep_artifacts:
                # Keep the compressed elementary stream for decoder-only audit.
                decoded.unlink(missing_ok=True)
        result["source_sha256_end"] = _hash(source); result["tool_provenance_end"] = {k: _hash(v) for k, v in tools.items()}
        if result["source_sha256_end"] != result["source_sha256_start"]: result["failure_reasons"].append("source_changed_during_run")
        if result["tool_provenance_end"] != result["tool_provenance_start"]: result["failure_reasons"].append("tool_changed_during_run")
        completed = {row.get("plan_index") for row in result["cells"]}
        result["complete"] = not result["failure_reasons"] and all(index in completed for index in requested_indices)
    finally:
        (out / "framebank-private.json").write_text(fb.report_json(result), encoding="utf-8")
    return result


def sanitized_report(result: dict) -> dict:
    keep = ("plan_index", "experiment_id", "phase", "profile", "source_geometry", "wavelet", "rate_mbps", "fps", "eye_width", "eye_height", "stereo_width", "cap_bytes", "bits_per_pixel", "encoded_chroma", "bitstream", "native_encoder_telemetry", "codec_only", "codec_only_domain", "displayed", "crops", "codec_only_windows", "displayed_windows", "displayed_reused_from_codec_only", "crop_windows", "centre_hvs", "fence_metrics", "q3b_transform", "q3b_encoded_source", "rdo_viewing_density", "rdo_effective", "offline_only_above_wifi_cap", "error")
    return {"schema": SCHEMA, "kind": "pyro_q3_framebank_sanitized", "complete": result.get("complete") is True,
            "failure_reasons": list(result.get("failure_reasons", [])), "frozen_plan_sha256": result.get("frozen_plan_sha256"),
            "source_sha256": result.get("source_sha256_end"), "tool_provenance": result.get("tool_provenance_end"),
            "tools_build_provenance": result.get("tools_build_provenance"), "module_hashes": result.get("module_hashes"),
            "hvs_gpu_sanity": result.get("hvs_gpu_sanity"), "source": result.get("source_sha256_start"), "q3b_preparation_workers": result.get("q3b_preparation_workers"), "requested_phase": result.get("requested_phase"), "requested_cell_indices": result.get("requested_cell_indices"), "selected_plan_indices": result.get("selected_plan_indices"), "run_scopes": result.get("run_scopes"), "cells": [{k: r.get(k) for k in keep} for r in result.get("cells", [])],
            "optical_latency_ms": None, "display_fps": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="freeze the five Q3a cropped PyroWave rows")
    for name in ("source", "full-source", "projection-evidence", "crop-evidence", "crops", "out"):
        plan.add_argument("--" + name, required=True)
    plan.add_argument("--vertical-pixels-per-degree", required=True, type=float)
    plan.add_argument("--horizontal-pixels-per-degree", type=float)
    plan.add_argument("--include-q3b-hooks", action="store_true")
    overnight = sub.add_parser("overnight-static-plan", help="freeze six new static-crop RDO rows")
    for name in ("source", "full-source", "projection-evidence", "crop-evidence", "crops", "out", "light-phase-identity"):
        overnight.add_argument("--" + name, required=True)
    overnight.add_argument("--vertical-pixels-per-degree", required=True, type=float)
    overnight.add_argument("--horizontal-pixels-per-degree", type=float)
    a2 = sub.add_parser("overnight-full-a2-plan", help="freeze static full-parent Haar/500/RDO24")
    for name in ("source", "projection-evidence", "crop-evidence", "crops", "out"):
        a2.add_argument("--" + name, required=True)
    a2.add_argument("--vertical-pixels-per-degree", required=True, type=float)
    a2.add_argument("--horizontal-pixels-per-degree", type=float)
    run = sub.add_parser("run", help="run a frozen Q3a plan under an owner-supervised lease")
    for name in ("plan", "source", "private-out", "report", "window", "encode", "decode", "psnr-hvs-m-h", "ffmpeg", "tools-metadata"):
        run.add_argument("--" + name, required=True)
    run.add_argument("--scorer-tools-metadata", help="separate verified bundle for the HVS scorer")
    run.add_argument("--scorer-compatibility", help="tracked historical-HVS compatibility descriptor; scorer-only")
    run.add_argument("--command-timeout-s", type=float, default=900)
    run.add_argument("--keep-artifacts", action="store_true")
    run.add_argument("--phase", choices=("q3a", "q3b"))
    run.add_argument("--cell-index", action="append", type=int, dest="cell_indices",
                     help="original frozen-plan index; repeat to select a finite subset")
    run.add_argument("--supervised", action="store_true", help="require owner-attested frame_bank_pc lease")
    run.add_argument("--resume", action="store_true", help="inspect matching completed output only")
    run.add_argument("--q3b-preparation-workers", type=int, default=1, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    if args.command == "plan":
        crops = json.loads(Path(args.crops[1:]).read_text(encoding="utf-8") if args.crops.startswith("@") else args.crops)
        frozen = build_plan(Path(args.source), args.vertical_pixels_per_degree,
                            horizontal_pixels_per_degree=args.horizontal_pixels_per_degree,
                            projection_evidence=args.projection_evidence, crop_evidence=args.crop_evidence,
                            crops=crops, full_source=Path(args.full_source), include_q3b=args.include_q3b_hooks)
        Path(args.out).write_text(fb.report_json(frozen), encoding="utf-8")
        print("wrote frozen Q3 PyroWave plan with", len(frozen["cells"]), "cells")
        return 0
    if args.command == "overnight-static-plan":
        crops = json.loads(Path(args.crops[1:]).read_text(encoding="utf-8") if args.crops.startswith("@") else args.crops)
        phase_identity = json.loads(Path(args.light_phase_identity[1:]).read_text(encoding="utf-8")
                                    if args.light_phase_identity.startswith("@") else args.light_phase_identity)
        frozen = build_overnight_static_plan(Path(args.source), args.vertical_pixels_per_degree,
            horizontal_pixels_per_degree=args.horizontal_pixels_per_degree,
            projection_evidence=args.projection_evidence, crop_evidence=args.crop_evidence,
            crops=crops, full_source=Path(args.full_source), light_phase_identity=phase_identity)
        Path(args.out).write_text(fb.report_json(frozen), encoding="utf-8")
        print("wrote frozen overnight static PyroWave plan with", len(frozen["cells"]), "cells")
        return 0
    if args.command == "overnight-full-a2-plan":
        crops = json.loads(Path(args.crops[1:]).read_text(encoding="utf-8") if args.crops.startswith("@") else args.crops)
        frozen = build_overnight_full_a2_plan(Path(args.source), args.vertical_pixels_per_degree,
            horizontal_pixels_per_degree=args.horizontal_pixels_per_degree,
            projection_evidence=args.projection_evidence, crop_evidence=args.crop_evidence, crops=crops)
        Path(args.out).write_text(fb.report_json(frozen), encoding="utf-8")
        print("wrote frozen overnight full a2 PyroWave plan")
        return 0
    result = run_plan(Path(args.plan), Path(args.source), Path(args.private_out),
                      {"encode": args.encode, "decode": args.decode, "psnr_hvs_m_h": args.psnr_hvs_m_h, "ffmpeg": args.ffmpeg}, Path(args.window),
                      tools_metadata=Path(args.tools_metadata),
                      scorer_tools_metadata=Path(args.scorer_tools_metadata) if args.scorer_tools_metadata else None,
                      scorer_compatibility=Path(args.scorer_compatibility) if args.scorer_compatibility else None,
                      command_timeout_s=args.command_timeout_s, keep_artifacts=args.keep_artifacts,
                      supervised=args.supervised, resume=args.resume, phase=args.phase,
                      cell_indices=args.cell_indices, preparation_workers=args.q3b_preparation_workers)
    report = sanitized_report(result); Path(args.report).write_text(fb.report_json(report), encoding="utf-8")
    print("wrote sanitized report: complete=" + str(report["complete"]))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

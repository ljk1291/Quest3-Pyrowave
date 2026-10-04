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
WAVELET_LABEL = {"haar": "Haar", "53": "CDF 5/3", "97": "CDF 9/7"}
CROPPED_SOURCE_SHA256 = "4c833e175610488ffa05a8037e52c166424db8308a67a2bfed4ed48861fad2e5"
FENCE_RECTANGLES = {"full_fov": {"eye": "left", "x": 1740, "y": 1310, "width": 240, "height": 274},
                    "cropped": {"mapped": {"eye": "left", "x": 1462, "y": 1036, "width": 240, "height": 274},
                                "source": {"eye": "left", "x": 1740, "y": 1310, "width": 240, "height": 274}}}
CROP_GEOMETRY = {"kind": "per_eye_crop", "source_eye": [3072, 3232], "target_eye": [2624, 2776],
                 "tangent_multipliers": [.8542, .85],
                 "eyes": [{"eye": "left", "x": 278, "y": 274, "width": 2624, "height": 2776},
                          {"eye": "right", "x": 170, "y": 274, "width": 2624, "height": 2776}],
                 "resampling": "none"}


def _hash(path):
    return fb.sha256_file(Path(path))


def _module_hashes():
    root = Path(__file__).resolve().parent
    return {name: _hash(root / name) for name in ("pyro_q3_framebank.py", "framebank.py", "fence_metrics.py")}


def _require_cropped_source(source: Path) -> fb.Y4MInfo:
    info = fb.inspect_y4m(source)
    if (info.width, info.height, info.frames, info.chroma, info.color_range, info.fps_num, info.fps_den) != (5248, 2776, 90, "420", "FULL", 90, 1):
        raise ValueError("Q3 cropped source must be 5248x2776, C420, full-range, 90 frames at 90 Hz")
    return info


def _source_contract(source: Path, info: fb.Y4MInfo) -> dict:
    return {"sha256": _hash(source), "geometry": [info.width, info.height],
            "frames": info.frames, "fps": [info.fps_num, info.fps_den],
            "chroma": info.chroma, "color_range": info.color_range,
            "frame_identity": fb.frame_records(source)}


def build_plan(source: Path, vertical_pixels_per_degree: float, *, projection_evidence: str,
               crop_evidence: str, crops, horizontal_pixels_per_degree: float | None = None,
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
    base = fb.build_plan(source, vertical_pixels_per_degree,
                         horizontal_pixels_per_degree=horizontal_pixels_per_degree,
                         projection_evidence=projection_evidence, crop_evidence=crop_evidence,
                         fixture=fixture, fps=90, wavelets=("haar", "53", "97"),
                         rates_mbps=(800, 1000), geometries=((2624, 2776),),
                         display_eye=(2624, 2776), crops=crops)
    selected = {(w, r) for w, r in Q3A_ROWS}
    pairs = [(i, c) for i, c in enumerate(base["cells"])
             if (c["wavelet"], c["rate_mbps"]) in selected]
    cells = [dict(phase="q3a", source_geometry="crop", **c) for _, c in pairs]
    if include_q3b:
        cells += [dict(phase="q3b", profile=p, wavelet=w, rate_mbps=r, fps=90,
                       eye_width=2624, eye_height=2776, stereo_width=5248,
                       requires_wo8_reduced_encode=True)
                  for p, w, r in Q3B_ROWS]
    return {"schema": SCHEMA, "kind": "pyro_q3_framebank", "fixture_only": bool(fixture),
            "source": _source_contract(source, info), "projection_evidence": projection_evidence.strip(),
            "crop_evidence": crop_evidence.strip(), "crop_geometry": copy.deepcopy(CROP_GEOMETRY),
            "frozen_module_hashes": _module_hashes(), "cells": cells,
            "presentation_eye": base["presentation_eye"], "projection": base["projection"],
            "crops": base["crops"], "hvs_calibration": {**base["hvs_calibration"],
                "codec_cells": [base["hvs_calibration"]["codec_cells"][i] for i, _ in pairs]},
            "source_adapter": {"kind": "per_eye_crop", "geometry": copy.deepcopy(CROP_GEOMETRY),
                               "future_transform": None},
            "fence_rectangles": {**copy.deepcopy(FENCE_RECTANGLES), "cropped": {**copy.deepcopy(FENCE_RECTANGLES["cropped"]), "geometry": copy.deepcopy(CROP_GEOMETRY)}},
            "quality_contract": {"score_windows_one_based": [[1, 90], [10, 89]], "fence_metric": True,
                                 "per_frame_identity": True, "timing_requires_native_per_frame_record": True,
                                 "q3b_requires_reduced_encode_then_expanded_score": True}}


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA or plan.get("kind") != "pyro_q3_framebank":
        raise ValueError("not a Pyro Q3 frame-bank manifest")
    source = plan.get("source", {})
    if source.get("geometry") != [5248, 2776] or source.get("frames") != 90 or source.get("fps") != [90, 1] or source.get("chroma") != "420" or source.get("color_range") != "FULL":
        raise ValueError("Q3 source contract drifted")
    if plan.get("frozen_module_hashes") != _module_hashes():
        raise ValueError("runner module hash drifted; freeze a new plan")
    actual_a = [c for c in plan.get("cells", []) if c.get("phase") == "q3a"]
    if [(c.get("wavelet"), c.get("rate_mbps")) for c in actual_a] != list(Q3A_ROWS) or any(
            c.get("eye_width") != 2624 or c.get("eye_height") != 2776 or c.get("stereo_width") != 5248 or
            c.get("cap_bytes") != fb.cap_bytes(c["rate_mbps"], 90) or c.get("source_geometry") != "crop" for c in actual_a):
        raise ValueError("Q3a rows drifted")
    calibration = plan.get("hvs_calibration", {})
    if not isinstance(calibration, dict) or len(calibration.get("codec_cells", [])) != len(actual_a):
        raise ValueError("Q3 calibrated scoring contract drifted")
    if plan.get("fence_rectangles", {}).get("cropped", {}).get("mapped") != FENCE_RECTANGLES["cropped"]["mapped"]:
        raise ValueError("Q3 cropped fence rectangle drifted")
    adapter = plan.get("source_adapter", {})
    if adapter.get("kind") != "per_eye_crop" or adapter.get("geometry") != CROP_GEOMETRY:
        raise ValueError("Q3 source adapter geometry drifted")
    actual_b = [c for c in plan.get("cells", []) if c.get("phase") == "q3b"]
    if actual_b and [(c.get("profile"), c.get("wavelet"), c.get("rate_mbps")) for c in actual_b] != list(Q3B_ROWS):
        raise ValueError("Q3b rows drifted")
    for cell in actual_b:
        if not cell.get("requires_wo8_reduced_encode"):
            raise ValueError("Q3b row lacks reduced-encode requirement")
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
    return {"container_sha256": hashlib.sha256(data).hexdigest(), "container_bytes": len(data),
            "payload_bytes": sizes, "frames": len(sizes), "header_bytes": len(expected_header)}


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


def _same_frame_scores(plan, index, cell, tools, guard, directory, source, source_info, decoded, decoded_info, timeout, keep_artifacts):
    """Use Q3's shared scorer after its revision is merged; never silently downgrade it."""
    from . import nvenc_framebank as nvenc
    scorer = getattr(nvenc, "_same_frame_scores", None)
    if scorer is None: raise RuntimeError("shared_q3_scorer_unavailable")
    return scorer(plan, index, cell, tools, guard, directory, source, source_info, decoded, decoded_info,
                  source, source_info, timeout, keep_artifacts)


def _result_base(raw_plan: bytes, source: Path, tools: dict, tool_build: dict | None) -> dict:
    return {"schema": SCHEMA, "kind": "pyro_q3_framebank_result", "frozen_plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
            "source_sha256_start": _hash(source), "source_sha256_end": None,
            "tool_provenance_start": {k: _hash(v) for k, v in tools.items()}, "tool_provenance_end": None,
            "tools_build_provenance": tool_build, "module_hashes": _module_hashes(), "cells": [],
            "complete": False, "failure_reasons": []}


def verify_split_bundles(tools: dict, codec_metadata: Path, scorer_metadata: Path | None = None) -> dict:
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
    scorer = fb.verify_tools_build(scorer_tools, scorer_metadata)
    if _hash(tools["psnr_hvs_m_h"]) != _hash(scorer_tools["psnr_hvs_m_h"]):
        raise ValueError("HVS scorer differs from scorer bundle metadata")
    for key in ("scorer_source", "scorer_shader_sha256", "sources_lock_sha256"):
        if codec.get(key) != scorer.get(key):
            raise ValueError("codec/scorer bundles do not prove the same HVS implementation")
    return {"codec_bundle": codec, "scorer_bundle": scorer,
            "separate_scorer_bundle": scorer_metadata != codec_metadata,
            "hvs_implementation_unchanged": True}


def run_plan(plan_path: Path, source: Path, private_out: Path, tools: dict, window: Path, *, tools_metadata: Path,
             scorer_tools_metadata: Path | None = None, command_timeout_s: float = 900,
             keep_artifacts: bool = False, supervised: bool = False, resume: bool = False) -> dict:
    """Run only frozen Q3a rows; Q3b fails closed until a real WO-8 adapter exists."""
    raw_plan = Path(plan_path).read_bytes(); plan = validate_plan(json.loads(raw_plan)); source = Path(source)
    info = _require_cropped_source(source); guard = fb.WindowGuard(Path(window), supervised=supervised)
    if _source_contract(source, info) != plan["source"]: raise ValueError("source contract differs from frozen plan")
    required = {"encode", "decode", "psnr_hvs_m_h"}
    if set(tools) != required: raise ValueError("Pyro Q3 runner requires exactly encode/decode/psnr_hvs_m_h tools")
    fb.required_tools(tools); guard.status(); build = verify_split_bundles(tools, Path(tools_metadata), scorer_tools_metadata)
    out = Path(private_out)
    if out.exists():
        if not resume: raise FileExistsError("private output exists; explicit resume required")
        prior = json.loads((out / "framebank-private.json").read_text(encoding="utf-8"))
        if prior.get("frozen_plan_sha256") != hashlib.sha256(raw_plan).hexdigest() or prior.get("source_sha256_start") != _hash(source) or prior.get("tool_provenance_start") != {k: _hash(v) for k, v in tools.items()}:
            raise ValueError("resume provenance mismatch")
        if prior.get("complete"): return prior
        # An interrupted row may have a partial elementary stream. Never encode it again automatically.
        raise RuntimeError("interrupted run preserved; manual review required before any cell replay")
    out.mkdir(parents=True); result = _result_base(raw_plan, source, tools, build)
    try:
        env, _ = fb.codec_environment(os.environ, "haar")
        result["hvs_gpu_sanity"] = fb.hvs_gpu_sanity(tools["psnr_hvs_m_h"], out / "scorer-sanity",
                                                      plan["projection"]["vertical_pixels_per_degree"], guard, env, command_timeout_s)
        if not result["hvs_gpu_sanity"].get("passed"): raise RuntimeError("hvs_gpu_sanity_failed")
        for index, cell in enumerate(plan["cells"]):
            if cell["phase"] == "q3b": raise RuntimeError("q3b_reduced_encode_adapter_unavailable")
            directory = out / f"cell-{index:02d}-{cell['wavelet']}-{cell['rate_mbps']}"; directory.mkdir()
            encoded, decoded = directory / "encoded.wave", directory / "decoded.y4m"; row = copy.deepcopy(cell)
            try:
                env, row["codec_environment"] = fb.codec_environment(os.environ, cell["wavelet"])
                timing = directory / "pyrowave-encode-timing.jsonl"
                start = time.time(); code, stdout, stderr = guard.run([str(tools["encode"]), str(source), str(encoded), str(cell["cap_bytes"]), "--timing-jsonl", str(timing)], cwd=directory, env=env, timeout_s=command_timeout_s); end = time.time()
                if code or not encoded.is_file(): raise RuntimeError("encode_failed")
                if WAVELET_LABEL[cell["wavelet"]] not in stdout + stderr and not plan["fixture_only"]: raise RuntimeError("encoder_wavelet_not_confirmed")
                row["encode_wall_interval_s"] = [start, end]; row["bitstream"] = parse_wave(encoded, cell)
                row["native_encoder_telemetry"] = _native_records(timing, row["bitstream"]["payload_bytes"])
                if not row["native_encoder_telemetry"]["qualified"]: raise RuntimeError("native_per_frame_telemetry_missing")
                code, stdout, stderr = guard.run([str(tools["decode"]), str(encoded), str(decoded)], cwd=directory, env=env, timeout_s=command_timeout_s)
                if code or not decoded.is_file(): raise RuntimeError("decode_failed")
                if WAVELET_LABEL[cell["wavelet"]] not in stdout + stderr and not plan["fixture_only"]: raise RuntimeError("decoder_wavelet_not_confirmed")
                row["decoded_y4m_header"] = fb.canonicalize_decoded_header(decoded); decoded_info = fb._assert_same_frames(source, decoded, info)
                row["decoded_frame_identity"] = [{"frame": i, "source_sha256": src["source_sha256"], "decoded_sha256": got} for (i, _, got), src in zip(fb.iter_y4m(decoded, decoded_info), plan["source"]["frame_identity"])]
                if len(row["decoded_frame_identity"]) != 90: raise ValueError("decoded_identity_or_geometry_mismatch")
                row.update(_same_frame_scores(plan, index, cell, tools, guard, directory, source, info, decoded, decoded_info, command_timeout_s, keep_artifacts))
            except (PermissionError, TimeoutError, ValueError, RuntimeError) as exc:
                row["error"] = str(exc); result["failure_reasons"].append(row["error"])
            result["cells"].append(row); (out / "framebank-progress.json").write_text(fb.report_json(result), encoding="utf-8")
            if row.get("error"): break
            if not keep_artifacts:
                encoded.unlink(missing_ok=True); decoded.unlink(missing_ok=True)
        result["source_sha256_end"] = _hash(source); result["tool_provenance_end"] = {k: _hash(v) for k, v in tools.items()}
        if result["source_sha256_end"] != result["source_sha256_start"]: result["failure_reasons"].append("source_changed_during_run")
        if result["tool_provenance_end"] != result["tool_provenance_start"]: result["failure_reasons"].append("tool_changed_during_run")
        result["complete"] = not result["failure_reasons"] and len(result["cells"]) == len(plan["cells"])
    finally:
        (out / "framebank-private.json").write_text(fb.report_json(result), encoding="utf-8")
    return result


def sanitized_report(result: dict) -> dict:
    keep = ("phase", "profile", "wavelet", "rate_mbps", "fps", "eye_width", "eye_height", "stereo_width", "cap_bytes", "bits_per_pixel", "bitstream", "native_encoder_telemetry", "codec_only", "displayed", "crops", "codec_only_windows", "displayed_windows", "crop_windows", "error")
    return {"schema": SCHEMA, "kind": "pyro_q3_framebank_sanitized", "complete": result.get("complete") is True,
            "failure_reasons": list(result.get("failure_reasons", [])), "frozen_plan_sha256": result.get("frozen_plan_sha256"),
            "source_sha256": result.get("source_sha256_end"), "tool_provenance": result.get("tool_provenance_end"),
            "tools_build_provenance": result.get("tools_build_provenance"), "module_hashes": result.get("module_hashes"),
            "hvs_gpu_sanity": result.get("hvs_gpu_sanity"), "cells": [{k: r.get(k) for k in keep} for r in result.get("cells", [])],
            "optical_latency_ms": None, "display_fps": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="freeze the five Q3a cropped PyroWave rows")
    for name in ("source", "projection-evidence", "crop-evidence", "crops", "out"):
        plan.add_argument("--" + name, required=True)
    plan.add_argument("--vertical-pixels-per-degree", required=True, type=float)
    plan.add_argument("--horizontal-pixels-per-degree", type=float)
    plan.add_argument("--include-q3b-hooks", action="store_true")
    run = sub.add_parser("run", help="run a frozen Q3a plan under an owner-supervised lease")
    for name in ("plan", "source", "private-out", "report", "window", "encode", "decode", "psnr-hvs-m-h", "tools-metadata"):
        run.add_argument("--" + name, required=True)
    run.add_argument("--scorer-tools-metadata", help="separate verified bundle for the HVS scorer")
    run.add_argument("--command-timeout-s", type=float, default=900)
    run.add_argument("--keep-artifacts", action="store_true")
    run.add_argument("--supervised", action="store_true", help="require owner-attested frame_bank_pc lease")
    run.add_argument("--resume", action="store_true", help="inspect matching completed output only")
    args = parser.parse_args(argv)
    if args.command == "plan":
        crops = json.loads(Path(args.crops[1:]).read_text(encoding="utf-8") if args.crops.startswith("@") else args.crops)
        frozen = build_plan(Path(args.source), args.vertical_pixels_per_degree,
                            horizontal_pixels_per_degree=args.horizontal_pixels_per_degree,
                            projection_evidence=args.projection_evidence, crop_evidence=args.crop_evidence,
                            crops=crops, include_q3b=args.include_q3b_hooks)
        Path(args.out).write_text(fb.report_json(frozen), encoding="utf-8")
        print("wrote frozen Q3 PyroWave plan with", len(frozen["cells"]), "cells")
        return 0
    result = run_plan(Path(args.plan), Path(args.source), Path(args.private_out),
                      {"encode": args.encode, "decode": args.decode, "psnr_hvs_m_h": args.psnr_hvs_m_h}, Path(args.window),
                      tools_metadata=Path(args.tools_metadata),
                      scorer_tools_metadata=Path(args.scorer_tools_metadata) if args.scorer_tools_metadata else None,
                      command_timeout_s=args.command_timeout_s, keep_artifacts=args.keep_artifacts,
                      supervised=args.supervised, resume=args.resume)
    report = sanitized_report(result); Path(args.report).write_text(fb.report_json(report), encoding="utf-8")
    print("wrote sanitized report: complete=" + str(report["complete"]))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Stable, replayable Quest 3 Wi-Fi baseline plans and fail-closed acceptance."""
from __future__ import annotations

from copy import deepcopy

SCHEMA_VERSION = 1
DEFAULT_EXPERIMENT = {
    "codec": "PyroWave", "transport": "Tcp", "chroma": "420",
    "decode_path": "Compute", "wavelet": "Cdf97", "dynamic_bitrate": False,
    "foveated_encoding": False, "clientside_foveation": False,
    "hdr": False,
}

def dimensions(width, height):
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("Dimensions must be positive integer per-eye pixels")
    return {"width": width, "height": height}

def experiment(render, encoded, hz, mbps, phase, seconds, **overrides):
    item = deepcopy(DEFAULT_EXPERIMENT)
    item.update({"render_resolution": dimensions(**render), "encoded_resolution": dimensions(**encoded),
                 "requested_hz": hz, "mbps": mbps, "phase": phase, "seconds": seconds})
    item.update(overrides)
    return item

def baseline_plan(render, encoded, repeats=3):
    """Create the bounded Wi-Fi 5 GHz/80 MHz Metro Awakening plan.

    Dimensions must be recorded from Virtual Desktop rather than guessed. 2080x2208
    is an earlier diagnostic size and is intentionally never labelled target-passable.
    """
    render, encoded = dimensions(**render), dimensions(**encoded)
    diagnostic = dimensions(2080, 2208)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "quest3_pyrowave_stable_baseline",
        "environment": {"game": "Metro Awakening", "network": "Wi-Fi 6 5 GHz 80 MHz",
                        "pc_link": "Ethernet", "target": "VD Godlike dimensions supplied by owner"},
        "target": {"render_resolution": render, "encoded_resolution": encoded, "requested_hz": 90},
        "defaults": deepcopy(DEFAULT_EXPERIMENT),
        "acceptance": {"minimum_duration_s": 1800, "rate_tolerance": 0.02,
                       "requires_manual_confirmation": True,
                       "requires_fresh_runtime_evidence": True,
                       "render_resolution": render, "encoded_resolution": encoded,
                       "requested_hz": 90, "allowed_target_mbps": [300,400,600,800]},
        "cells": [
            experiment(render, encoded, 90, 0, "vd-reference", 300, codec="VirtualDesktop",
                       label="VD Godlike 90 Hz reference; record its current AV1/HEVC choice", acceptance_eligible=False),
            experiment(render, encoded, 90, 200, "alvr-hevc-control", 300, codec="Hevc",
                       label="ALVR HEVC 200 Mbps control at target dimensions", acceptance_eligible=False),
            experiment(diagnostic, diagnostic, 72, 400, "diagnostic", 60,
                       label="PyroWave small-resolution qualification", acceptance_eligible=False),
            experiment(render, encoded, 72, 300, "target-screen", 60),
            experiment(render, encoded, 72, 400, "target-screen", 60),
            experiment(render, encoded, 72, 600, "target-screen", 60),
            experiment(render, encoded, 90, 300, "target-screen", 60),
            experiment(render, encoded, 90, 400, "target-screen", 60),
            experiment(render, encoded, 90, 600, "target-screen", 60),
        ],
        "gated": [experiment(render, encoded, 90, 800, "target-screen", 60,
                             gate="Only after all 300/400/600 Mbps target screens pass")],
        "endurance": {"replicates": repeats, "screen_seconds": 300, "final_seconds": 1810,
                      "minimum_observed_submission_window_s": 1800},
        "notes": ["Use TCP 4:2:0 Compute CDF 9/7 SDR with fixed bitrate.",
                  "Do not treat diagnostic 2080x2208 results as Godlike acceptance.",
                  "Record Quest OS, GPU driver, SteamVR version and actual VD dimensions before testing."],
    }

def _same_dimensions(value, expected):
    return (isinstance(value, dict) and isinstance(expected, dict)
            and value.get("width") == expected.get("width") and value.get("height") == expected.get("height"))

def acceptance(report, expected, selected_target_mbps=None):
    """Return an explicit acceptance result. Missing evidence always fails closed."""
    # Accept the durable baseline plan directly, as well as its compact acceptance
    # object, so a later reviewer replays the exact dimensions originally approved.
    if "acceptance" in expected and "target" in expected:
        expected = dict(expected["acceptance"], **expected.get("defaults", {}))
    if selected_target_mbps is not None: expected=dict(expected, selected_target_mbps=selected_target_mbps)
    reasons = []
    requested = expected.get("requested_hz")
    if report.get("status") != "measured": reasons.append("capture_not_measured")
    if not report.get("frames"): reasons.append("no_fresh_stream_frames")
    if report.get("duplicate_frame_events", 0): reasons.append("duplicate_frame_events")
    observed=report.get("submission_rate_window_s")
    if not isinstance(observed,(int,float)) or isinstance(observed,bool) or observed < expected.get("minimum_duration_s", 1800): reasons.append("capture_too_short")
    if requested != 90: reasons.append("target_acceptance_requires_90hz")
    if report.get("settings_start") != report.get("settings_end"): reasons.append("settings_changed_during_capture")
    settings = report.get("settings_start") or {}
    for key in ("render_resolution", "encoded_resolution"):
        if not _same_dimensions(settings.get(key), expected.get(key, {})): reasons.append("%s_mismatch" % key)
        if not _same_dimensions(settings.get("negotiated_" + key), expected.get(key, {})):
            reasons.append("negotiated_%s_mismatch" % key)
    if settings.get("requested_hz") != requested or settings.get("negotiated_hz") != requested:
        reasons.append("runtime_rate_mismatch")
    for key in ("codec","transport","chroma","decode_path","wavelet"):
        if key in expected and settings.get(key) != expected[key]: reasons.append("%s_mismatch" % key)
    if settings.get("hdr_enabled") is not False or settings.get("hdr_server_override") is not True:
        reasons.append("hdr_settings_unverified")
    if (settings.get('bitrate_mode') != 'ConstantMbps' or not isinstance(settings.get('target_mbps'),(int,float))
            or settings.get('enforce_server_frame_pacing') is not True): reasons.append('fixed_bitrate_or_pacing_unverified')
    selected=expected.get('selected_target_mbps', expected.get('mbps'))
    if not isinstance(selected,(int,float)) or isinstance(selected,bool): reasons.append('selected_target_bitrate_missing')
    elif ('allowed_target_mbps' in expected and selected not in expected['allowed_target_mbps']): reasons.append('selected_target_bitrate_not_allowed')
    elif settings.get('target_mbps') != selected: reasons.append('target_bitrate_mismatch')
    if settings.get('foveated_encoding_enabled') is not False or settings.get('clientside_foveation_enabled') is not False:
        reasons.append('foveation_settings_unverified')
    effective=settings.get('effective_pyrowave') or {}
    if effective.get('enabled') is not True: reasons.append('effective_pyrowave_unverified')
    for key in ('transport','chroma','wavelet','decode_path'):
        if key in expected and effective.get(key) != expected[key]: reasons.append('effective_%s_mismatch' % key)
    if effective.get('foveated_encoding') is not False: reasons.append('effective_foveation_unverified')
    if not report.get("fresh_runtime_evidence"): reasons.append("missing_fresh_runtime_evidence")
    if not report.get("build_identity") or not report.get("build_identity_verified"):
        reasons.append("build_identity_unverified")
    if report.get("telemetry_complete") is not True: reasons.append("telemetry_incomplete")
    if report.get("thermal_ok") is not True: reasons.append("thermal_state_unverified")
    if report.get("stream_errors") is None: reasons.append("stream_error_status_missing")
    elif report.get("stream_errors"): reasons.append("stream_errors_reported")
    counters=report.get("pyrowave_counter_window", {}).get("counter_deltas", {})
    if counters.get('complete') is None or counters.get('complete') <= 0: reasons.append('fresh_frame_counter_missing')
    if counters.get("decode_failures") is None: reasons.append("decoder_failure_counter_missing")
    elif counters.get("decode_failures") != 0: reasons.append("decoder_failures_reported")
    if report.get("controllers_ok") is not True: reasons.append("controller_status_unverified")
    if report.get("audio_ok") is not True: reasons.append("audio_status_unverified")
    if report.get("tracking_ok") is not True: reasons.append("tracking_status_unverified")
    if report.get("image_ok") is not True: reasons.append("image_validation_unverified")
    if report.get("metro_clarity_ok") is not True: reasons.append("metro_clarity_unverified")
    if report.get("metro_motion_ok") is not True: reasons.append("metro_motion_unverified")
    if report.get("manual_confirmation") is not True: reasons.append("manual_confirmation_missing")
    if not report.get("sustained_requested_fps"): reasons.append("fresh_submission_rate_failed")
    experiments_start=report.get('experiment_options_start',{})
    experiments_end=report.get('experiment_options_end',{})
    if experiments_start != experiments_end: reasons.append('experiment_options_changed_during_capture')
    if (not experiments_start.get('verified') or not experiments_end.get('verified')
            or any(experiments_start.get('enabled',{}).values()) or any(experiments_end.get('enabled',{}).values())):
        reasons.append('experiment_options_unverified_or_enabled')
    if report.get("rate_stability", {}).get("status") != "stable": reasons.append("endurance_rate_stability_unverified")
    if expected.get("diagnostic_only") or (expected.get("encoded_resolution") == {"width":2080,"height":2208}):
        reasons.append("diagnostic_resolution_cannot_pass_target")
    return {"schema_version": SCHEMA_VERSION, "accepted": not reasons,
            "failure_reasons": reasons, "requested_hz": requested,
            "expected": expected}

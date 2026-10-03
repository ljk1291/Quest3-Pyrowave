"""Independent per-eye render, encode, and captured-geometry contracts for ALVR.

This module makes no hardware calls. ``control`` owns session writes; ``bench``
uses :func:`evidence` to fail a geometry comparison closed when the server or
decoder did not report the expected sizes.
"""
import json
from pathlib import Path


RENDER_FIELD = "emulated_headset_view_resolution"
ENCODE_FIELD = "transcoding_view_resolution"
PROFILE_FILE = Path(__file__).resolve().parents[2] / "presets" / "resolution-comparison.json"


def profiles():
    document = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or not isinstance(document.get("profiles"), dict):
        raise ValueError("Unsupported resolution-profile document")
    return document["profiles"]


def validate_eye(size):
    if (not isinstance(size, (list, tuple)) or len(size) != 2 or
            any(type(value) is not int or not 32 <= value <= 8192 for value in size)):
        raise ValueError("Per-eye width and height must be integers from 32 to 8192")
    return list(size)


def aligned_eye(size):
    return [(value + 31) // 32 * 32 for value in validate_eye(size)] if size is not None else None


def assignments(render_eye=None, encode_eye=None):
    """Return only explicitly requested ALVR settings; omit means preserve."""
    values = {}
    for field, size in ((RENDER_FIELD, render_eye), (ENCODE_FIELD, encode_eye)):
        if size is None:
            continue
        width, height = validate_eye(size)
        base = f"session_settings.video.{field}"
        values.update({
            base + ".variant": "Absolute",
            base + ".Absolute.width": width,
            base + ".Absolute.height.set": True,
            base + ".Absolute.height.content": height,
        })
    if not values:
        raise ValueError("Specify render geometry, encode geometry, or a profile")
    return values


def absolute_eye(setting):
    """Return an aligned Absolute setting, without inventing a Scale value."""
    if not isinstance(setting, dict) or setting.get("variant") != "Absolute":
        return None
    absolute = setting.get("Absolute", {})
    height = absolute.get("height", {})
    if not isinstance(height, dict) or not height.get("set"):
        return None
    value = [absolute.get("width"), height.get("content")]
    if any(type(component) is not int or component <= 0 for component in value):
        return None
    return aligned_eye(value)


def _known(size):
    return (isinstance(size, list) and len(size) == 2 and
            all(type(component) is int and component > 0 for component in size))


def _decoded_stereo_sizes(telemetry):
    """Read additive decoder geometry telemetry without assuming an old wire shape."""
    sizes = []
    for item in telemetry:
        if not isinstance(item, dict):
            continue
        candidates = [item]
        pyrowave = item.get("pyrowave")
        if isinstance(pyrowave, dict):
            candidates.append(pyrowave)
        for candidate in candidates:
            for width_key, height_key in (("encoded_width", "encoded_height"),
                                          ("decoded_width", "decoded_height")):
                size = [candidate.get(width_key), candidate.get(height_key)]
                if _known(size) and size not in sizes:
                    sizes.append(size)
    return sizes


def evidence(settings, telemetry=(), expected_profile=None):
    """Record requested, negotiated and decoder-reported geometry.

    A verified result proves only the dimensions carried through these
    interfaces. It is intentionally not evidence of game texture size, image
    quality, compositor display rate, or sustained performance.
    """
    openvr = settings.get("openvr", {}) if isinstance(settings, dict) else {}
    requested_render = absolute_eye(settings.get("configured_render_view_resolution"))
    requested_encode = absolute_eye(settings.get("configured_view_resolution"))
    negotiated_render = [openvr.get("target_eye_resolution_width"),
                         openvr.get("target_eye_resolution_height")]
    negotiated_encode = [openvr.get("eye_resolution_width"),
                         openvr.get("eye_resolution_height")]
    decoded = _decoded_stereo_sizes(telemetry)
    mismatches = []

    for name, requested, negotiated in (("render", requested_render, negotiated_render),
                                        ("encode", requested_encode, negotiated_encode)):
        if requested is not None and _known(negotiated) and requested != negotiated:
            mismatches.append(f"{name}_size_pending_restart_or_negotiation")

    if _known(negotiated_encode):
        expected_stereo = [negotiated_encode[0] * 2, negotiated_encode[1]]
        if decoded and any(size != expected_stereo for size in decoded):
            mismatches.append("decoded_frame_differs_from_negotiated_encode")

    profile_name = None
    if expected_profile is not None:
        selected = profiles().get(expected_profile)
        if selected is None:
            raise ValueError(f"Unknown resolution profile: {expected_profile}")
        profile_name = expected_profile
        expected_render = aligned_eye(selected["render_eye"])
        expected_encode = aligned_eye(selected["encode_eye"])
        if requested_render != expected_render:
            mismatches.append("requested_render_differs_from_profile")
        if requested_encode != expected_encode:
            mismatches.append("requested_encode_differs_from_profile")

    complete = (settings.get("codec") == "PyroWave" and
                requested_render is not None and requested_encode is not None and
                _known(negotiated_render) and _known(negotiated_encode) and
                bool(decoded) and openvr.get("enable_foveated_encoding") is False)
    return {
        "status": "mismatch" if mismatches else "verified" if complete else "unknown",
        "mismatches": mismatches,
        "expected_profile": profile_name,
        "aligned_requested_render_eye": requested_render,
        "aligned_requested_encode_eye": requested_encode,
        "negotiated_render_eye": negotiated_render,
        "negotiated_encode_eye": negotiated_encode,
        "observed_decoded_stereo_frames": decoded,
        "pc_source_pixel_ratio": (negotiated_render[0] * negotiated_render[1] /
                                  (negotiated_encode[0] * negotiated_encode[1]))
            if _known(negotiated_render) and _known(negotiated_encode) else None,
        "scope": ("Geometry only; a SteamVR recommendation is not proof of game texture "
                  "size, image quality, optical presentation, or sustained performance."),
    }


def scene_evidence(scene, geometry):
    """Bind an opt-in normalized chart record to negotiated render geometry."""
    if not isinstance(scene, dict):
        return {"status": "unknown", "reason": "scene_metadata_missing"}
    source = scene.get("source_eye_size")
    negotiated = geometry.get("negotiated_render_eye") if isinstance(geometry, dict) else None
    normalized = scene.get("normalized_chart")
    if not _known(source) or not _known(negotiated) or normalized is not True:
        return {"status": "unknown", "source_eye_size": source,
                "normalized_chart": normalized, "negotiated_render_eye": negotiated}
    if source != negotiated:
        return {"status": "mismatch", "source_eye_size": source,
                "normalized_chart": normalized, "negotiated_render_eye": negotiated,
                "reason": "scene_source_differs_from_negotiated_render"}
    return {"status": "verified", "source_eye_size": source,
            "normalized_chart": normalized, "negotiated_render_eye": negotiated}

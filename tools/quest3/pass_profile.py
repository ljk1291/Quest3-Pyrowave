"""Parse offline Quest PyroWave Granite pass-profile logs.

This command deliberately accepts a saved log only.  Granite emits means for
completed frame-context windows; the values are not timestamps for an exact
frame, p95 frame timings, display FPS, or optical latency.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SCOPE = "granite_frame_context_mean"
KNOWN_PHASES = frozenset(("Dequant", "iDWT", "iDWT fragment"))
ACTIVATION = re.compile(
    r"\[Q3PW_GPU_PASS\]\s+enabled=1\s+cadence_completed_frames=(\d+)\s+scope=(\S+)"
)
SAMPLE = re.compile(
    r"\[Q3PW_GPU_PASS\]\s+completed_frames=(\d+)\s+wall_ms=(\d+)\s+phase=(.+?)\s+avg_ms=([^\s]+)\s+scope=(\S+)"
)
NO_VALID = re.compile(r"\[Q3PW_GPU_PASS\]\s+no valid Granite timestamp labels\b")


def finite_positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def summarize(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {"windows": len(ordered), "mean_avg_ms": sum(ordered) / len(ordered),
            "p50_avg_ms": percentile(.5), "min_avg_ms": ordered[0], "max_avg_ms": ordered[-1]}


def parse(text: str) -> dict[str, Any]:
    """Return conservative profile evidence from ``[Q3PW_GPU_PASS]`` records."""
    activation_records = []
    invalid_activation_records = 0
    phase_values: dict[str, list[float]] = defaultdict(list)
    warnings: list[str] = []
    invalid_samples = 0
    sample_lines = 0
    lines = list(enumerate(text.splitlines(), start=1))
    # Establish the first valid activation before accepting any timing data. A
    # later property enable must not bless an earlier, unscoped diagnostic.
    first_valid_activation_line: int | None = None
    for number, line in lines:
        if "[Q3PW_GPU_PASS]" not in line or "enabled=" not in line:
            continue
        enabled = ACTIVATION.search(line)
        if enabled:
            cadence, scope = int(enabled.group(1)), enabled.group(2)
            record = {"line": number, "cadence_completed_frames": cadence, "scope": scope}
            activation_records.append(record)
            if cadence == 90 and scope == SCOPE and first_valid_activation_line is None:
                first_valid_activation_line = number
        else:
            invalid_activation_records += 1
            warnings.append("invalid_gpu_pass_activation")

    for number, line in lines:
        if "[Q3PW_GPU_PASS]" not in line:
            continue
        if "enabled=" in line:
            continue
        if NO_VALID.search(line):
            warnings.append("native_no_valid_timestamp_labels")
            continue
        match = SAMPLE.search(line)
        if not match:
            invalid_samples += 1
            warnings.append("unrecognized_gpu_pass_record")
            continue
        sample_lines += 1
        completed, wall, phase, average_text, scope = match.groups()
        try:
            average = float(average_text)
        except ValueError:
            average = float("nan")
        completed_frames, wall_ms = int(completed), int(wall)
        if (completed_frames != 90 or not finite_positive(wall_ms) or not finite_positive(average)
                or scope != SCOPE or phase.strip() not in KNOWN_PHASES):
            invalid_samples += 1
            warnings.append("invalid_gpu_pass_sample")
            continue
        if first_valid_activation_line is None or number < first_valid_activation_line:
            invalid_samples += 1
            warnings.append("sample_before_valid_activation")
            continue
        phase_values[phase.strip()].append(average)

    activation_ok = first_valid_activation_line is not None and invalid_activation_records == 0
    valid_samples = sum(len(values) for values in phase_values.values())
    failures = []
    if not activation_ok:
        failures.append("activation_missing_or_invalid")
    if invalid_activation_records:
        failures.append("invalid_gpu_pass_activation")
    if valid_samples == 0:
        failures.append("no_valid_phase_samples")
    if invalid_samples:
        failures.append("invalid_gpu_pass_samples")
    if "native_no_valid_timestamp_labels" in warnings:
        failures.append("native_no_valid_timestamp_labels")
    return {
        "schema_version": 1,
        "kind": "q3pw_gpu_pass_profile",
        "activation": {"present": bool(activation_records), "valid": activation_ok,
                       "records": activation_records},
        "samples": {"records": sample_lines, "valid": valid_samples, "invalid": invalid_samples},
        "phase_window_means_ms": {phase: summarize(values) for phase, values in sorted(phase_values.items())},
        "warnings": sorted(set(warnings)),
        "healthy_profiling_claim": not failures,
        "failure_reasons": failures,
        "limitations": "Each value is a Granite completed-frame-context window mean. It is not exact-frame latency, a p95 frame time, display FPS, or optical latency.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True, help="Fresh saved diagnostic logcat text; never invokes ADB.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = parse(args.log.read_text(encoding="utf-8", errors="replace"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0 if result["healthy_profiling_claim"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

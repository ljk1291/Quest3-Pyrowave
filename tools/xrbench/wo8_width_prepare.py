"""Prepare the finite WO-8 width-only reference bank without invoking a codec.

This is the CPU stage only: it validates a frozen one-cell plan and duplicate
ledger, creates the reduced 4096x2784 SBS input plus sharp/blur score
references, and records 90 ordered source/reference identities.  It never
opens an NVENC lease, runs an encoder/decoder/scorer, queries a GPU, or starts
VR software.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from . import framebank as fb
from . import nvenc_framebank as nvenc

_MODULES = ("framebank.py", "fence_metrics.py", "foveation.py", "nvenc_framebank.py")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate(plan: dict, source_sha256: str) -> dict:
    cell = plan["cells"][0]
    return {"experiment_id": cell["experiment_id"], "source_sha256": source_sha256,
            "source_transform": cell["source_transform"], "codec": cell["codec"],
            "rate_mbps": cell["rate_mbps"], "encoded_eye": [cell["eye_width"], cell["eye_height"]]}


def _rows(value):
    if isinstance(value, list):
        yield from value
    elif isinstance(value, dict):
        for key in ("rows", "cells", "results", "ranked_fence_review"):
            if isinstance(value.get(key), list):
                yield from value[key]


def _assert_unique(candidate: dict, ledgers: list[Path]) -> list[dict]:
    """Reject an exact completed candidate already represented in supplied ledgers."""
    checked = []
    for path in ledgers:
        raw = path.read_bytes()
        payload = json.loads(raw)
        checked.append({"sha256": hashlib.sha256(raw).hexdigest()})
        for row in _rows(payload):
            if not isinstance(row, dict):
                continue
            same = all(row.get(key) == candidate[key] for key in
                       ("experiment_id", "source_sha256", "source_transform", "codec", "rate_mbps"))
            if same and row.get("complete") is True:
                raise ValueError("exact completed duplicate found in supplied ledger")
    return checked


def prepare(plan_path: Path, source: Path, private_out: Path, ledgers: list[Path], *, workers: int = 3) -> dict:
    """Materialize finite CPU-only WO-8 references and an auditable receipt."""
    raw_plan = plan_path.read_bytes()
    plan = nvenc.validate_plan(json.loads(raw_plan))
    if len(plan.get("cells", [])) != 1:
        raise ValueError("WO-8 preparation requires exactly one frozen cell")
    cell = plan["cells"][0]
    transform = cell.get("source_transform", {})
    if cell.get("experiment_id") != "wo8_width_only_h264_p7_700" or transform.get("profile") != "h264width":
        raise ValueError("not the frozen WO-8 width-only H264 cell")
    if (cell.get("eye_width"), cell.get("eye_height"), cell.get("stereo_width")) != (2048, 2784, 4096):
        raise ValueError("WO-8 encoded geometry drifted")
    if transform.get("softness") != .5 or transform.get("blur_only") is not False:
        raise ValueError("WO-8 transform drifted")
    expected_transform_hash = transform.get("implementation_source_sha256")
    source_root = Path(__file__).resolve().parent
    module_hashes_start = {name: _sha(source_root / name) for name in _MODULES}
    if expected_transform_hash != module_hashes_start["foveation.py"]:
        raise ValueError("WO-8 foveation implementation identity drifted")
    if not ledgers:
        raise ValueError("WO-8 preparation requires at least one duplicate ledger")
    if private_out.exists():
        raise FileExistsError("private preparation output must be fresh")
    source_info = nvenc._require_jpeg_full_y4m(source)
    source_hash_start = fb.sha256_file(source)
    if source_hash_start != plan["source"]["sha256"]:
        raise ValueError("source differs from frozen plan")
    candidate = _candidate(plan, source_hash_start)
    duplicate_ledgers = _assert_unique(candidate, ledgers)
    private_out.mkdir(parents=True)
    try:
        encoded = private_out / "encoded-reference.y4m"
        sharp = private_out / "sharp-reference.y4m"
        blur = private_out / "blur-reference.y4m"
        encoded_info, score_info, identities, transform_provenance = nvenc._stream_q3b_sources(
            source, fb.inspect_y4m(source), plan["source_adapter"]["geometry"], transform,
            encoded, sharp, blur, preparation_workers=workers)
        if len(identities) != 90 or [row["source_sha256"] for row in identities] != [
                row["source_sha256"] for row in plan["source"]["frame_identity"]]:
            raise ValueError("WO-8 requires exactly the frozen 90-frame identity sequence")
        cropped_fence = plan.get("fence_rectangles", {}).get("cropped")
        if not isinstance(cropped_fence, dict):
            raise ValueError("WO-8 plan lacks frozen cropped fence region")
        _, periphery = nvenc._q3b_periphery_mask(cell, score_info, cropped_fence)
        receipt = {"schema": 1, "kind": "wo8_width_only_cpu_preparation", "complete": True,
                   "codec_or_scorer_ran": False, "frozen_plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
                   "candidate": candidate, "duplicate_preflight": {"status": "no_exact_completed_duplicate",
                   "ledgers": duplicate_ledgers}, "source_sha256_start": source_hash_start,
                   "source_sha256_end": fb.sha256_file(source), "source_y4m_header": source_info,
                   "module_hashes_start": module_hashes_start,
                   "module_hashes_end": {name: _sha(source_root / name) for name in _MODULES},
                   "transform": transform_provenance, "quality_regions": {"cropped_fence": cropped_fence,
                   "periphery": periphery, "centre": nvenc._q3b_centre_rect(cell, score_info)},
                   "identity_count": len(identities), "frame_identity": identities}
        if receipt["source_sha256_end"] != source_hash_start or receipt["module_hashes_end"] != module_hashes_start:
            raise ValueError("source or CPU transform changed during preparation")
        (private_out / "width-only-preparation.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return receipt
    except BaseException:
        # Keep a failed private directory for diagnosis; it cannot be mistaken for a receipt.
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--duplicate-ledger", type=Path, action="append", required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args(argv)
    result = prepare(args.plan, args.source, args.private_out, args.duplicate_ledger, workers=args.workers)
    print(f"prepared {result['identity_count']} CPU-only WO-8 frames; no codec or scorer ran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

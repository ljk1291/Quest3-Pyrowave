"""Fail-closed synthetic-motion preparation, command, and tracked-score API.

This module is deliberately separate from the static Q3 frame-bank manifests.
It prepares only the three pre-encode synthetic-motion rows; the retained
full-Haar row is a post-decode moving-view diagnostic and has no encode command.
No function in this module starts a codec unless a caller explicitly executes
the returned command through an owner-supervised WindowGuard.
"""
from __future__ import annotations
import copy
import hashlib
import json
import shutil
from pathlib import Path

from . import fence_metrics
from . import framebank as fb
from . import nvenc_framebank as nvenc
from . import pyro_q3_framebank as pyro

SCHEMA = 1
MOTION_GEOMETRY = [5248, 2776]
MOTION_PHASE = {"implementation_revision": "wo8-light-centre-phase-v1",
                "implementation_source_sha256": "2658166c77699c71e55a21d29f1b75e50d3f47746322f9f91de3798c6d5aec3b"}
MOTION_ROWS = (
    {"experiment_id": "motion_h264fit_p7_700", "runner": "nvenc", "codec": "h264", "rate_mbps": 700,
     "preset": "p7", "spatial_aq": False, "source_transform": {"kind":"wo8_foveation","profile":"h264fit","softness":.5,"blur_only":False}},
    {"experiment_id": "motion_av1_main10_p4_200", "runner": "nvenc", "codec": "av1", "rate_mbps": 200,
     "preset": "p4", "spatial_aq": False},
    {"experiment_id": "motion_medium_97_rdo24_1000", "runner": "pyrowave", "wavelet": "97", "rate_mbps": 1000,
     "rdo_px_per_deg": 24, "source_transform": {"kind":"wo8_foveation","profile":"medium","softness":.5,"blur_only":False}},
)


def _hash(path: Path) -> str:
    return fb.sha256_file(Path(path))


def _module_hashes() -> dict:
    root = Path(__file__).resolve().parent
    return {name: _hash(root / name) for name in ("motion_framebank.py", "framebank.py", "nvenc_framebank.py", "pyro_q3_framebank.py", "fence_metrics.py", "foveation.py")}


def _load_contract(manifest: Path) -> dict:
    raw = Path(manifest).read_bytes(); doc = json.loads(raw)
    header = doc.get("motion_header", {})
    if (doc.get("kind"), doc.get("synthetic_not_actual_vr_tracking"),
        [header.get(k) for k in ("width", "height", "frames", "fps", "chroma", "color_range")]) != (
            "synthetic_integer_pixel_pingpong_motion", True, [5248, 2776, 90, [90, 1], "420", "FULL"]):
        raise ValueError("synthetic motion manifest contract drifted")
    frames = doc.get("frames")
    if not isinstance(frames, list) or len(frames) != 90:
        raise ValueError("synthetic motion manifest must retain 90 layouts")
    if [row.get("frame_one_based") for row in frames] != list(range(1, 91)):
        raise ValueError("synthetic motion frame numbering drifted")
    offsets = [row.get("displacement_x_pixels") for row in frames]
    if (any(type(value) is not int for value in offsets) or
            any(abs(offsets[index] - offsets[index - 1]) != 16 for index in range(1, 90))):
        raise ValueError("synthetic motion 16-pixel step drifted")
    source_fence = None
    for row in frames:
        left, right = row.get("left_source_window", {}), row.get("right_source_window", {})
        rect = row.get("tracked_fence_output", {})
        if (left.get("width"), left.get("height"), right.get("width"), right.get("height")) != (2624, 2776, 2624, 2776):
            raise ValueError("synthetic motion eye geometry drifted")
        if left.get("y") != right.get("y") or left.get("x") - right.get("x") != 108:
            raise ValueError("synthetic motion eye offsets are inconsistent")
        if not (0 <= left.get("x", -1) <= 448 and 0 <= right.get("x", -1) <= 448 and
                0 <= rect.get("x", -1) and rect.get("x", 0) + rect.get("width", 0) <= 2624 and
                rect.get("y") == 1036 and rect.get("width") == 240 and rect.get("height") == 274):
            raise ValueError("synthetic motion crop or tracked fence leaves bounds")
        if source_fence is None:
            source_fence = row.get("tracked_fence_source")
        elif row.get("tracked_fence_source") != source_fence:
            raise ValueError("synthetic motion source fence drifted")
    if doc.get("score_windows") != {"spatial_one_based":[1,90], "temporal_one_based":[10,89], "temporal_pairs":79}:
        raise ValueError("synthetic motion windows drifted")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "document": doc}


def build_plan(source: Path, manifest: Path, *, vertical_pixels_per_degree: float,
               horizontal_pixels_per_degree: float) -> dict:
    """Freeze the three actual pre-encode motion cells and one reuse-only diagnostic."""
    source = Path(source); info = fb.inspect_y4m(source); contract = _load_contract(Path(manifest))
    if (info.width, info.height, info.frames, info.fps_num, info.fps_den, info.chroma, info.color_range) != (5248,2776,90,90,1,"420","FULL"):
        raise ValueError("synthetic motion source geometry drifted")
    if _hash(source) != contract["document"].get("motion_y4m_sha256"):
        raise ValueError("synthetic motion source hash differs from manifest")
    if not all(isinstance(value, (int,float)) and value > 0 for value in (vertical_pixels_per_degree, horizontal_pixels_per_degree)):
        raise ValueError("motion projection PPD must be positive")
    cells=[]
    for spec in MOTION_ROWS:
        cell=copy.deepcopy(spec); cell.update({"phase":"motion", "fps":90, "source_geometry":"moving_crop",
                    "encoded_chroma":"420", "cap_bytes":fb.cap_bytes(spec["rate_mbps"],90),
                    "score_vertical_pixels_per_degree":float(vertical_pixels_per_degree),
                    "tracked_score":"source_space_fence_residual", "quality_windows_one_based":[[1,90],[10,89]]})
        if spec["runner"] == "nvenc":
            transform=cell.get("source_transform")
            if transform:
                from .foveation import FoveationConfig, encoded_size
                ew,eh=encoded_size(2624,2776,FoveationConfig(transform["profile"],transform["softness"],transform["blur_only"]))
            else: ew,eh=2624,2776
            cell.update(eye_width=ew, eye_height=eh, stereo_width=ew*2,
                        nvenc_profile=nvenc.profile(cell["codec"], cell["rate_mbps"], 90, preset=cell["preset"], spatial_aq=False))
        else:
            from .foveation import FoveationConfig, encoded_size
            transform=cell["source_transform"]; ew,eh=encoded_size(2624,2776,FoveationConfig(transform["profile"],transform["softness"],transform["blur_only"]))
            cell.update(eye_width=ew, eye_height=eh, stereo_width=ew*2,
                        bits_per_pixel=fb.bpp(cell["cap_bytes"],ew,eh),
                        rdo_viewing_density=pyro._rdo_descriptor(cell.pop("rdo_px_per_deg")),
                        requires_wo8_reduced_encode=True)
        cells.append(cell)
    cells.append({"experiment_id":"motion_view_haar_full_parent_500_default_rdo", "phase":"motion", "runner":"reuse_only", "wavelet":"haar", "rate_mbps":500,
                  "source_geometry":"full_parent_postdecode_moving_view", "tracked_score":"source_space_fence_residual",
                  "classification":"post-decode moving-view diagnostic; not pre-encode motion stress or interframe compression evidence"})
    return {"schema":SCHEMA,"kind":"synthetic_motion_framebank","source":{"sha256":_hash(source),"geometry":MOTION_GEOMETRY,"frames":90,"fps":[90,1],"chroma":"420","color_range":"FULL","frame_identity":fb.frame_records(source)},
            "motion_contract":{"manifest_sha256":contract["sha256"],"motion_input_sha256":contract["document"]["motion_y4m_sha256"],"synthetic_not_actual_vr_tracking":True,"score_windows":contract["document"]["score_windows"]},
            "projection":{"vertical_pixels_per_degree":float(vertical_pixels_per_degree),"horizontal_pixels_per_degree":float(horizontal_pixels_per_degree),"hvs_axis":"vertical"},
            "frozen_module_hashes":_module_hashes(),"cells":cells,
            "prohibitions":["no optical or Quest performance claim","no whole-image HVS rank against post-decode full-parent diagnostic","no replacement of pre-encode moving crop by moving-view extraction"]}


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan,dict) or plan.get("schema") != SCHEMA or plan.get("kind") != "synthetic_motion_framebank":
        raise ValueError("not a synthetic motion frame-bank plan")
    source=plan.get("source",{})
    if [source.get("geometry"),source.get("frames"),source.get("fps"),source.get("chroma"),source.get("color_range")] != [MOTION_GEOMETRY,90,[90,1],"420","FULL"]:
        raise ValueError("motion source contract drifted")
    if plan.get("frozen_module_hashes") != _module_hashes():
        raise ValueError("motion runner module hash drifted")
    contract=plan.get("motion_contract",{})
    if (not isinstance(contract.get("manifest_sha256"),str) or len(contract["manifest_sha256"]) != 64 or
        contract.get("motion_input_sha256") != source.get("sha256") or contract.get("synthetic_not_actual_vr_tracking") is not True or
        contract.get("score_windows") != {"spatial_one_based":[1,90], "temporal_one_based":[10,89], "temporal_pairs":79}):
        raise ValueError("motion provenance or window contract drifted")
    cells=plan.get("cells",[])
    if [c.get("experiment_id") for c in cells] != [c["experiment_id"] for c in MOTION_ROWS] + ["motion_view_haar_full_parent_500_default_rdo"]:
        raise ValueError("motion cells drifted")
    for cell,spec in zip(cells,MOTION_ROWS):
        immutable={k:v for k,v in spec.items() if k != "rdo_px_per_deg"}
        if (any(cell.get(k) != v for k,v in immutable.items()) or
            cell.get("cap_bytes") != fb.cap_bytes(spec["rate_mbps"],90) or
            (spec["runner"] == "pyrowave" and cell.get("rdo_viewing_density") != pyro._rdo_descriptor(spec["rdo_px_per_deg"]))):
            raise ValueError("motion codec row drifted")
        transform=spec.get("source_transform")
        if transform:
            from .foveation import FoveationConfig, encoded_size
            expected_geometry=encoded_size(2624,2776,FoveationConfig(transform["profile"],transform["softness"],transform["blur_only"]))
        else:
            expected_geometry=(2624,2776)
        if (cell.get("eye_width"),cell.get("eye_height"),cell.get("stereo_width"),cell.get("fps"),cell.get("encoded_chroma")) != (*expected_geometry,expected_geometry[0]*2,90,"420"):
            raise ValueError("motion encoded geometry or format drifted")
        if spec["runner"] == "nvenc":
            expected_profile=nvenc.profile(spec["codec"],spec["rate_mbps"],90,preset=spec["preset"],spatial_aq=False)
            if cell.get("nvenc_profile") != expected_profile:
                raise ValueError("motion NVENC profile drifted")
        elif (cell.get("bits_per_pixel") != fb.bpp(cell["cap_bytes"],*expected_geometry) or
              cell.get("requires_wo8_reduced_encode") is not True):
            raise ValueError("motion PyroWave geometry or reduced-encode contract drifted")
    if cells[-1].get("runner") != "reuse_only": raise ValueError("motion diagnostic must never encode")
    return plan


def verify_inputs(plan: dict, source: Path, manifest: Path) -> tuple[fb.Y4MInfo, dict]:
    validate_plan(plan); source=Path(source); info=fb.inspect_y4m(source); contract=_load_contract(Path(manifest))
    if _hash(source) != plan["source"]["sha256"] or contract["sha256"] != plan["motion_contract"]["manifest_sha256"]:
        raise ValueError("motion source or manifest provenance differs from frozen plan")
    if plan["source"]["frame_identity"] != fb.frame_records(source): raise ValueError("motion frame identity differs from frozen plan")
    return info,contract["document"]


def disk_preflight(directory: Path, cell: dict, *, safety_margin_bytes: int = 2 * 1024**3) -> dict:
    """Fail closed before creating motion derivatives on an undersized volume.

    The source itself is immutable and is never copied.  The estimate covers
    only concurrent derived Y4M/raw files plus the capped elementary stream,
    then adds a fixed safety margin for scorer intermediates.  It is a lower
    bound, not a reservation.
    """
    directory=Path(directory); usage=shutil.disk_usage(directory.parent if directory.parent.exists() else directory.anchor)
    frame=lambda w,h: w*h*3//2 + 6
    full=frame(5248,2776)*90
    encoded_cap=fb.cap_bytes(cell["rate_mbps"],90)*90
    if cell.get("source_transform"):
        # reduced input + sharp/blur references + reconstructed score output;
        # decoded reduced file is conservatively bounded by the largest of
        # reduced/full payloads.
        reduced=frame(cell["stereo_width"],cell["eye_height"])*90
        required=reduced + full*3 + max(reduced,full) + encoded_cap + safety_margin_bytes
    else:
        # reference is the immutable source; decoded raw/score representation
        # and elementary stream are new output only.
        required=full*2 + encoded_cap + safety_margin_bytes
    result={"free_bytes":usage.free,"required_bytes_lower_bound":required,"safety_margin_bytes":safety_margin_bytes,
            "source_is_reused":True,"passes":usage.free >= required}
    if not result["passes"]: raise RuntimeError("motion_disk_preflight_insufficient")
    return result


def prepare_cell(plan: dict, source: Path, manifest: Path, cell_index: int, directory: Path, guard, *, preparation_workers: int=1) -> dict:
    """Prepare exact encode/reference inputs. The caller alone runs returned commands."""
    info,doc=verify_inputs(plan,source,manifest); cells=plan["cells"]
    if type(cell_index) is not int or not 0 <= cell_index < len(cells): raise ValueError("motion cell index out of range")
    cell=copy.deepcopy(cells[cell_index]); cell["identity_count"] = 90
    if cell["runner"] == "reuse_only": return {"cell":cell,"reuse_only":True,"motion_manifest_sha256":hashlib.sha256(Path(manifest).read_bytes()).hexdigest()}
    directory=Path(directory); disk=disk_preflight(directory,cell); directory.mkdir(parents=True,exist_ok=False)
    encode_source=Path(source); score_reference=Path(source); matching_blur=None; encode_info=info; score_info=info
    if cell.get("source_transform"):
        encode_source=directory/"reduced-encoded-source.y4m"; score_reference=directory/"score-sharp-reference.y4m"; matching_blur=directory/"score-blur-reference.y4m"
        encode_info,score_info,identities,transform=nvenc._stream_q3b_sources(Path(source),info,pyro.CROP_GEOMETRY,cell["source_transform"],encode_source,score_reference,matching_blur,preparation_workers=preparation_workers,guard=guard)
        cell["transform_provenance"]=transform
        cell["encoded_source"]=pyro._q3b_encoded_source_provenance(encode_source,identities)
    return {"cell":cell,"encode_source":encode_source,"encode_info":encode_info,"score_reference":score_reference,"score_info":score_info,"matching_blur_reference":matching_blur,"motion_manifest_sha256":hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),"disk_preflight":disk}


def encode_command(prepared: dict, tools: dict, output: Path) -> list[str]:
    """Return one exact encode command; no command is executed here."""
    cell=prepared["cell"]
    if prepared.get("reuse_only"): raise ValueError("full Haar moving-view diagnostic has no encode command")
    if cell["runner"] == "nvenc": return nvenc.encode_command(Path(tools["ffmpeg"]),prepared["encode_source"],Path(output),cell)
    if cell["runner"] == "pyrowave": return [str(tools["encode"]),str(prepared["encode_source"]),str(output),str(cell["cap_bytes"]),"--timing-jsonl",str(Path(output).with_suffix(".timing.jsonl"))]
    raise ValueError("unknown motion runner")


def score_tracked(reference: Path, decoded: Path, manifest: Path) -> dict:
    """Score a per-frame output fence that maps to one fixed source-space ROI."""
    reference=Path(reference); decoded=Path(decoded); contract=_load_contract(Path(manifest)); info=fb.inspect_y4m(reference)
    expected=(5248,2776,90,90,1,"420","FULL")
    if (info.width,info.height,info.frames,info.fps_num,info.fps_den,info.chroma,info.color_range) != expected:
        raise ValueError("tracked score reference geometry differs")
    if _hash(reference) != contract["document"].get("motion_y4m_sha256"):
        raise ValueError("tracked score reference differs from motion manifest")
    doc=contract["document"]
    decoded_info=fb.inspect_y4m(decoded)
    if decoded_info != info: raise ValueError("tracked score decoded geometry differs")
    acc=fence_metrics.FenceAccumulator(); identities=[]
    for (i,ref,rh),(j,got,gh) in zip(fb.iter_y4m(reference,info),fb.iter_y4m(decoded,decoded_info)):
        if i != j: raise ValueError("tracked score frame order differs")
        rect=doc["frames"][i]["tracked_fence_output"]; x,y,w,h=(rect[k] for k in ("x","y","width","height"))
        acc.add(i+1,ref[0][y:y+h,x:x+w],got[0][y:y+h,x:x+w])
        identities.append({"frame_one_based":i+1,"reference_sha256":rh,"decoded_sha256":gh,"source_fence":doc["frames"][i]["tracked_fence_source"]})
    return {"kind":"tracked_source_space_fence_residual","synthetic_motion":True,"windows":acc.report(),"frame_identity":identities,"temporal":"decoded-reference residual variation, not raw motion or optical shimmer"}

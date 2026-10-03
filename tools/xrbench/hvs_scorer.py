"""Reproducible, scorer-only adapter for PyroWave PSNR-HVS-M-H calibration.

This never changes PyroWave's encoder, decoder, runtime library, or dependency pin.
It validates and applies one opt-in patch to a caller-owned clean d2997ac source
copy, then records the exact inputs for a raw-Y4M scorer using its unchanged
metric functions and shader. The legacy calibrated source is retained separately.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, shutil, subprocess, tempfile
from pathlib import Path

UPSTREAM_REPOSITORY = "https://github.com/Themaister/pyrowave"
UPSTREAM_BASE_REVISION = "d2997ac172bdc00e29c58e3f2938acb7e94580bf"
LICENSE = "MIT"
BASE_PSNR_SHA256 = "663a77a183a1f2f4d96928e89a9e34568c1468b6d882a7b833f4f8b6a162d709"
WORKTREE_BASE_PSNR_SHA256 = "436b042a5c631c061565b023ca3317ff22a3a714cf965a5f1aeaa2bf2c41599e"
PATCHED_PSNR_SHA256 = "bf2ed4c7cd2e962e97e468c2fa6b9f0d6068ee7faa441b0f3f001a93b3f3e184"
PATCH_NAME = "pyrowave-psnr-hvs-ppd-scorer.patch"
SCORER_SHADER_SHA256 = "87fd53541193fd2543be754ecb8a6a38f810894993d1c8963e1d86bd8edc30bf"
BUILD_TARGET = "pyrowave-framebank-hvs"
SCORER_OVERLAY = '''\n# Isolated same-input Y4M transport; no video decoder or predictive-frame discard.
add_granite_offline_tool(pyrowave-framebank-hvs framebank_hvs.cpp)
target_link_libraries(pyrowave-framebank-hvs PRIVATE granite-vulkan)
'''

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def height_factor(pixels_per_degree: float, image_height: int) -> float:
    if not isinstance(pixels_per_degree,(int,float)) or not math.isfinite(pixels_per_degree) or pixels_per_degree<=0:
        raise ValueError("pixels_per_degree must be finite and positive")
    if not isinstance(image_height,int) or image_height<=0: raise ValueError("image_height must be positive")
    return float(pixels_per_degree)*180.0/(image_height*math.pi)

def patch_path() -> Path:
    return Path(__file__).resolve().parents[2]/"patches"/PATCH_NAME

def native_path(name: str) -> Path:
    return Path(__file__).resolve().parent/'native'/name

def metric_functions(source: str) -> str:
    """Exact pinned upstream CSF and shader dispatch; transport is separate."""
    csf=source[source.index('static float contrast_sensitivity_function'):source.index('static void roundtrip_pyrowave')]
    dispatch=source[source.index('struct Sync\n'):source.index('static void print_help')]
    return csf+dispatch

def standalone_source(source: str) -> str:
    prefix='''// Copyright (c) 2025-2026 Hans-Kristian Arntzen
// SPDX-License-Identifier: MIT
// Metric functions below are extracted unchanged from pinned upstream psnr.cpp.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "context.hpp"
#include "device.hpp"
#include "os_filesystem.hpp"
#include "global_managers_init.hpp"
#include "math.hpp"
#include "muglm/muglm_impl.hpp"
#include "thread_group.hpp"
#include "path_utils.hpp"
using namespace Vulkan;
using namespace Granite;
using namespace Util;
'''
    return prefix+metric_functions(source)+'\n#include "framebank_hvs_main.cpp"\n'

def manifest() -> dict:
    patch=patch_path()
    fixture=Path(__file__).resolve().parents[1]/'tests/fixtures/pyrowave-d2997ac-psnr.cpp'
    base=fixture.read_bytes().replace(b'\r\n',b'\n').decode('utf-8')
    return {"schema":1,"kind":"pyrowave_psnr_hvs_ppd_scorer","upstream":{"repository":UPSTREAM_REPOSITORY,"base_revision":UPSTREAM_BASE_REVISION,"license":LICENSE},"patch":{"path":f"patches/{PATCH_NAME}","sha256":sha256_file(patch),"base_psnr_cpp_sha256":BASE_PSNR_SHA256,"accepted_windows_worktree_psnr_cpp_sha256":WORKTREE_BASE_PSNR_SHA256,"preimage_normalization":"LF after exact preimage hash validation","patched_psnr_cpp_sha256":PATCHED_PSNR_SHA256},"standalone":{"transport":"strict_native_y4m_no_frame_discard","metric_functions_sha256":hashlib.sha256(metric_functions(base).encode()).hexdigest(),"generated_source_sha256":hashlib.sha256(standalone_source(base).encode()).hexdigest(),"main_sha256":sha256_file(native_path('framebank_hvs_main.cpp')),"reader_sha256":sha256_file(native_path('framebank_y4m.hpp')),"shader_sha256":SCORER_SHADER_SHA256,"cmake_overlay_sha256":hashlib.sha256(SCORER_OVERLAY.encode()).hexdigest()},"build":{"target":BUILD_TARGET,"cmake_options":["-DPYROWAVE_UTILS=OFF","-DPYROWAVE_DEVEL=ON"],"runtime_defaults_changed":False}}

def _git_apply(source:Path, reverse:bool=False, check:bool=True) -> subprocess.CompletedProcess:
    args=["git","-c","core.autocrlf=false","-C",str(source),"apply"]
    if check: args.append("--check")
    if reverse: args.append("--reverse")
    args.append(str(patch_path()))
    # Prepared sources intentionally have no .git directory. Git must not find
    # the enclosing fork and silently skip psnr.cpp as outside its cwd prefix.
    env=os.environ.copy()
    for name in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_COMMON_DIR','GIT_PREFIX'):
        env.pop(name,None)
    env['GIT_CEILING_DIRECTORIES']=str(source.resolve().parent)
    return subprocess.run(args,text=True,capture_output=True,check=False,env=env)

def verify_patch(source:Path) -> dict:
    """Forward- and reverse-check the patch in a private temporary copy."""
    source=Path(source); psnr=source/"psnr.cpp"
    if sha256_file(psnr) not in (BASE_PSNR_SHA256, WORKTREE_BASE_PSNR_SHA256): raise ValueError("source psnr.cpp does not match pinned PyroWave d2997ac base")
    with tempfile.TemporaryDirectory() as temporary:
        # Patch validation needs only its declared preimage. Do not copy the
        # Granite tree just to test a one-file scorer patch.
        staged=Path(temporary)/"source"; staged.mkdir()
        # Canonical LF bytes make the adapter output hash independent of the
        # caller's Git configuration and an existing Windows CRLF checkout.
        (staged/"psnr.cpp").write_bytes(psnr.read_bytes().replace(b'\r\n', b'\n'))
        forward=_git_apply(staged,check=True)
        if forward.returncode: raise ValueError("scorer patch does not apply cleanly")
        applied=_git_apply(staged,check=False)
        if applied.returncode or sha256_file(staged/"psnr.cpp")!=PATCHED_PSNR_SHA256: raise ValueError("scorer patch result hash mismatch")
        reverse=_git_apply(staged,reverse=True,check=True)
        if reverse.returncode: raise ValueError("scorer patch cannot be reversed cleanly")
    return manifest()

def prepare_source(source:Path, output:Path) -> dict:
    """Copy a clean source tree, apply the isolated scorer patch, and write provenance."""
    source,output=Path(source),Path(output)
    if output.exists(): raise FileExistsError("output scorer source already exists")
    verify_patch(source)
    shutil.copytree(source,output,ignore=shutil.ignore_patterns(".git","build*"))
    (output/"psnr.cpp").write_bytes((output/"psnr.cpp").read_bytes().replace(b'\r\n', b'\n'))
    applied=_git_apply(output,check=False)
    if applied.returncode or sha256_file(output/"psnr.cpp")!=PATCHED_PSNR_SHA256: raise RuntimeError("failed to prepare scorer source")
    record=manifest()
    generated=standalone_source((output/'psnr.cpp').read_text(encoding='utf-8'))
    if hashlib.sha256(generated.encode()).hexdigest()!=record['standalone']['generated_source_sha256']:
        raise RuntimeError('metric functions differ from pinned upstream')
    (output/'framebank_hvs.cpp').write_text(generated,encoding='utf-8',newline='\n')
    for name in ('framebank_hvs_main.cpp','framebank_y4m.hpp'): shutil.copyfile(native_path(name),output/name)
    cmake=output/'CMakeLists.txt'
    # Patch-only CPU fixtures intentionally do not contain the complete build tree.
    if cmake.is_file():
        cmake.write_text(cmake.read_text(encoding='utf-8')+SCORER_OVERLAY,encoding='utf-8',newline='\n')
    shader=output/'shaders/psnr_hvs_m.comp'
    if shader.is_file() and sha256_file(shader)!=SCORER_SHADER_SHA256: raise RuntimeError('HVS shader differs from pinned upstream')
    (output/"PYROWAVE-HVS-PPD-SCORER.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest="command",required=True)
    verify=sub.add_parser("verify-patch"); verify.add_argument("--source",required=True); verify.add_argument("--out")
    prepare=sub.add_parser("prepare-source"); prepare.add_argument("--source",required=True); prepare.add_argument("--out",required=True); prepare.add_argument("--manifest-out")
    args=parser.parse_args(argv)
    if args.command=="verify-patch":
        record=verify_patch(Path(args.source)); output=args.out
    else:
        record=prepare_source(Path(args.source),Path(args.out)); output=args.manifest_out
    payload=json.dumps(record,indent=2)+"\n"
    if output: Path(output).write_text(payload,encoding="utf-8")
    else: print(payload,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())

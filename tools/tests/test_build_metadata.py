import json
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools/ci/build_metadata.py"


def load_metadata_tool():
    spec = importlib.util.spec_from_file_location("build_metadata", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_pyrowave(root):
    shader_dir = root / "pyrowave/shaders"
    shader_dir.mkdir(parents=True, exist_ok=True)
    files = ("wavelet_quant.comp", "wavelet_dequant.comp", "dwt_quant_scale.h", "constants.h", "idwt.comp", "idwt_haar_fused.comp",
             "dwt.comp", "dwt_common.h", "dwt_swizzle.h", "slangmosh.json", "slangmosh.hpp")
    hashes = {}
    for name in files:
        content = ("shader:" + name).encode()
        (shader_dir / name).write_bytes(content)
        hashes["shaders/" + name] = hashlib.sha256(content).hexdigest()
    (shader_dir / "quest3-manifest.json").write_text(json.dumps(hashes))
    return root / "pyrowave"


def write_metadata(root, platform):
    root.mkdir(parents=True, exist_ok=True)
    out = root / platform
    out.mkdir()
    native = root / (platform + ".dll")
    native.write_bytes(b"native")
    (out / "artifact.bin").write_bytes(platform.encode())
    command = [sys.executable, str(TOOL), "write", "--platform", platform, "--output", str(out),
               "--pyrowave", str(make_pyrowave(root)), "--required-native", str(native)]
    if platform == "android":
        command += ["--certificate-sha256", "a" * 64, "--require-signing-certificate", "--signing-kind", "development"]
    subprocess.run(command,
                   cwd=REPO, check=True)
    return out / "BUILD-METADATA.json"


def test_metadata_records_inputs_and_artifacts(tmp_path):
    path = write_metadata(tmp_path, "android")
    metadata = json.loads(path.read_text())
    fork = json.loads((REPO / "fork.json").read_text())
    assert metadata["client_package_id"] == "io.github.ljk1291.quest3pyrowave"
    assert metadata["protocol_version"] == fork["protocol_version"]
    assert metadata["application_version"].startswith(fork["protocol_version"] + "+")
    assert metadata["native_library_sha256"]
    assert metadata["artifact_sha256"]["artifact.bin"]


def test_source_lock_fingerprint_is_independent_of_checkout_line_endings(tmp_path):
    tool = load_metadata_tool()
    lf = tmp_path / "sources-lf.lock"
    crlf = tmp_path / "sources-crlf.lock"
    lf.write_bytes(b'{\n  "pin": "value"\n}\n')
    crlf.write_bytes(b'{\r\n  "pin": "value"\r\n}\r\n')
    assert tool.source_lock_sha256(lf) == tool.source_lock_sha256(crlf)


def test_matching_pair_requires_identical_build_inputs(tmp_path):
    left = write_metadata(tmp_path / "left", "android")
    right = write_metadata(tmp_path / "right", "windows")
    subprocess.run([sys.executable, str(TOOL), "verify-pair", str(left), str(right)], check=True)
    metadata = json.loads(right.read_text())
    metadata["protocol_version"] = "mismatch"
    right.write_text(json.dumps(metadata))
    failed = subprocess.run([sys.executable, str(TOOL), "verify-pair", str(left), str(right)],
                            capture_output=True, text=True)
    assert failed.returncode != 0
    assert "protocol_version" in failed.stderr


def test_missing_native_library_prevents_metadata(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    failed = subprocess.run([sys.executable, str(TOOL), "write", "--platform", "android", "--output", str(out),
                             "--pyrowave", str(make_pyrowave(tmp_path)), "--required-native", str(tmp_path / "no.so")],
                            cwd=REPO, capture_output=True, text=True)
    assert failed.returncode != 0
    assert "missing" in failed.stderr


def test_pair_rejects_empty_metadata_and_corrupt_packaged_artifact(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    failed = subprocess.run([sys.executable, str(TOOL), "verify-pair", str(empty), str(empty)],
                            capture_output=True, text=True)
    assert failed.returncode != 0
    left = write_metadata(tmp_path / "left", "android")
    right = write_metadata(tmp_path / "right", "windows")
    (left.parent / "artifact.bin").write_bytes(b"corrupted")
    failed = subprocess.run([sys.executable, str(TOOL), "verify-pair", str(left), str(right)],
                            capture_output=True, text=True)
    assert failed.returncode != 0
    assert "checksum" in failed.stderr


def test_stable_signing_rejects_a_different_certificate(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    native = tmp_path / "native.dll"
    native.write_bytes(b"native")
    failed = subprocess.run([
        sys.executable, str(TOOL), "write", "--platform", "android", "--output", str(out),
        "--pyrowave", str(make_pyrowave(tmp_path)), "--required-native", str(native),
        "--certificate-sha256", "b" * 64, "--require-signing-certificate", "--signing-kind", "stable",
    ], cwd=REPO, capture_output=True, text=True)
    assert failed.returncode != 0
    assert "does not match" in failed.stderr

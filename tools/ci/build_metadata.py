#!/usr/bin/env python3
"""Write and verify the auditable identity of a packaged build.

The output deliberately distinguishes build inputs from artifact checksums.  A
matching Android/Windows pair must agree on the former; the latter are expected
to differ because each artifact contains platform-specific binaries.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CI_TOOLS = Path(__file__).resolve().parent
if str(CI_TOOLS) not in sys.path:
    sys.path.insert(0, str(CI_TOOLS))
from source_lock import load as load_source_lock

IDENTITY_KEYS = ("protocol_version", "client_package_id", "application_version", "server_version", "repository_commit",
                 "sources_lock_sha256", "dependency_revisions", "shader_hashes")
SCHEMA_VERSION = 1


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_lock_sha256(path):
    """Fingerprint lockfile contents independently of Git's checkout EOL policy."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git_commit():
    value = os.environ.get("GITHUB_SHA")
    if value:
        return value
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


def native_files(values):
    result = {}
    for value in values:
        path = Path(value)
        if not path.is_file():
            raise SystemExit(f"required native library is missing: {path}")
        result[path.name] = sha256(path)
    return result


def shaders(root):
    root = Path(root)
    subprocess.run([sys.executable, str(REPO / "tools/ci/check_shader_manifest.py"), str(root)], check=True)
    manifest = root / "shaders" / "quest3-manifest.json"
    if not manifest.is_file():
        raise SystemExit(f"shader manifest is missing: {manifest}")
    return json.loads(manifest.read_text(encoding="utf-8"))


def create(args):
    output = Path(args.output)
    lock = REPO / "sources.lock.json"
    fork = load_fork_identity()
    lock_data = load_source_lock()
    artifacts = {}
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name not in ("BUILD-METADATA.json", "SHA256SUMS.txt"):
            artifacts[path.name] = sha256(path)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "platform": args.platform,
        "repository_commit": git_commit(),
        "application_version": application_version(fork),
        "server_version": application_version(fork),
        "protocol_version": fork["protocol_version"],
        "client_package_id": fork["client_package_id"],
        "sources_lock_sha256": source_lock_sha256(lock),
        "dependency_revisions": lock_data,
        "shader_hashes": shaders(args.pyrowave),
        "native_library_sha256": native_files(args.required_native),
        "artifact_sha256": artifacts,
        "signing_certificate_sha256": certificate(args),
        "signing_kind": args.signing_kind,
    }
    if args.require_signing_certificate and not metadata["signing_certificate_sha256"]:
        raise SystemExit("a signing certificate SHA-256 is required for this artifact")
    if args.signing_kind == "stable":
        expected = fork.get("stable_signing_certificate_sha256")
        if not expected or metadata["signing_certificate_sha256"] != expected:
            raise SystemExit("stable APK signing certificate does not match fork.json")
    (output / "BUILD-METADATA.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                                                  encoding="utf-8")


def application_version(fork):
    return f"{fork['protocol_version']}+{git_commit()[:12]}"


def load_fork_identity():
    fork = json.loads((REPO / "fork.json").read_text(encoding="utf-8"))
    protocol = fork.get("protocol_version")
    package = fork.get("client_package_id")
    if not isinstance(protocol, str) or not re.fullmatch(r"\d+\.\d+\.\d+-[A-Za-z0-9][A-Za-z0-9.-]*", protocol):
        raise SystemExit("fork.json: protocol_version is invalid")
    if not isinstance(package, str) or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", package):
        raise SystemExit("fork.json: client_package_id is invalid")
    return fork


def certificate(args):
    if args.certificate_sha256:
        return args.certificate_sha256
    if not args.certificate_file:
        return None
    contents = Path(args.certificate_file).read_text(encoding="utf-8")
    match = re.search(r"SHA-256[^:]*:\s*([0-9A-Fa-f:]{64,})", contents)
    if not match:
        raise SystemExit("could not find signing certificate SHA-256 in " + args.certificate_file)
    return match.group(1).replace(":", "").lower()


def validate_metadata(metadata, expected_platform):
    if not isinstance(metadata, dict) or metadata.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit("unsupported or missing build metadata schema")
    if metadata.get("platform") != expected_platform:
        raise SystemExit(f"metadata platform must be {expected_platform}")
    missing = [key for key in IDENTITY_KEYS if not metadata.get(key)]
    if missing:
        raise SystemExit("metadata has missing identity fields: " + ", ".join(missing))
    if not isinstance(metadata["dependency_revisions"], dict) or not isinstance(metadata["shader_hashes"], dict):
        raise SystemExit("metadata dependency or shader hashes are malformed")
    if not metadata["shader_hashes"]:
        raise SystemExit("metadata shader hashes are empty")
    artifacts = metadata.get("artifact_sha256")
    if not isinstance(artifacts, dict) or not artifacts:
        raise SystemExit("metadata artifact hashes are missing or empty")
    if not isinstance(metadata.get("native_library_sha256"), dict) or not metadata["native_library_sha256"]:
        raise SystemExit("metadata native library hashes are missing or empty")
    if expected_platform == "android" and metadata.get("signing_kind") not in ("stable", "development"):
        raise SystemExit("Android metadata has no valid signing kind")


def verify_artifacts(metadata, directory):
    expected = metadata["artifact_sha256"]
    actual = {path.name: sha256(path) for path in directory.iterdir()
              if path.is_file() and path.name not in ("BUILD-METADATA.json", "SHA256SUMS.txt")}
    if set(actual) != set(expected):
        raise SystemExit("packaged artifact file list does not match BUILD-METADATA.json")
    corrupt = [name for name, digest in expected.items() if actual[name] != digest]
    if corrupt:
        raise SystemExit("packaged artifact checksum mismatch: " + ", ".join(corrupt))


def verify_pair(args):
    left = json.loads(Path(args.left).read_text(encoding="utf-8"))
    right = json.loads(Path(args.right).read_text(encoding="utf-8"))
    validate_metadata(left, "android")
    validate_metadata(right, "windows")
    verify_artifacts(left, Path(args.left).parent)
    verify_artifacts(right, Path(args.right).parent)
    if not left.get("signing_certificate_sha256"):
        raise SystemExit("Android build metadata has no signing certificate fingerprint")
    failures = [key for key in IDENTITY_KEYS if left.get(key) != right.get(key)]
    if failures:
        raise SystemExit("build identities do not match: " + ", ".join(failures))
    print("matching build identities verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write")
    write.add_argument("--output", required=True)
    write.add_argument("--platform", required=True, choices=("android", "windows"))
    write.add_argument("--pyrowave", required=True)
    write.add_argument("--required-native", nargs="+", required=True)
    write.add_argument("--certificate-sha256")
    write.add_argument("--certificate-file")
    write.add_argument("--require-signing-certificate", action="store_true")
    write.add_argument("--signing-kind", choices=("stable", "development"))
    pair = commands.add_parser("verify-pair")
    pair.add_argument("left")
    pair.add_argument("right")
    args = parser.parse_args()
    if args.command == "write":
        create(args)
    else:
        verify_pair(args)


if __name__ == "__main__":
    main()

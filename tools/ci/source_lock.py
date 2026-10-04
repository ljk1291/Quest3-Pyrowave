#!/usr/bin/env python3
"""Read the one authoritative source lock without accepting environment overrides."""
import argparse
import json
import re
import shlex
from pathlib import Path

LOCK = Path(__file__).resolve().parents[2] / "sources.lock.json"
COMMIT_KEYS = ("integration", "alvr", "pyrowave", "granite", "cargo_apk")
APPLICATION_IDENTITY_KEYS = ("fork", "protocol_version", "client_package_id", "application_version", "server_version")


def load():
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    duplicated_identity = [key for key in APPLICATION_IDENTITY_KEYS if key in data]
    if duplicated_identity:
        raise SystemExit("sources.lock.json must not contain application identity; fork.json is authoritative: "
                         + ", ".join(duplicated_identity))
    for key in COMMIT_KEYS:
        commit = data[key]["commit"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise SystemExit(f"sources.lock.json: {key}.commit is not a full SHA-1")
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", data[key]["url"]):
            raise SystemExit(f"sources.lock.json: {key}.url is not an allowed GitHub repository URL")
    if not re.fullmatch(r"\d+\.\d+\.\d+", data["rust"]):
        raise SystemExit("sources.lock.json: rust is not a release version")
    if not re.fullmatch(r"\d+\.\d+\.\d+", data["android_ndk"]):
        raise SystemExit("sources.lock.json: android_ndk is not a release version")
    loader = data["openxr_loader"]
    if not (isinstance(loader, dict) and re.fullmatch(r"release-\d+\.\d+\.\d+", loader.get("release", ""))
            and re.fullmatch(r"[A-Za-z0-9_.-]+\.aar", loader.get("android_aar", ""))
            and re.fullmatch(r"[0-9a-f]{64}", loader.get("sha256", ""))):
        raise SystemExit("sources.lock.json: openxr_loader must include a release and SHA-256")
    patch = data.get("patches", {}).get("pyrowave_rdo_density", {})
    if (not isinstance(patch, dict) or patch.get("path") != "patches/pyrowave-rdo-density.patch"
            or not re.fullmatch(r"[0-9a-f]{64}", patch.get("sha256", ""))):
        raise SystemExit("sources.lock.json: patches.pyrowave_rdo_density must pin the additive patch SHA-256")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-env", action="store_true")
    parser.add_argument("--value", choices=("rust", "android_ndk", "pyrowave_rdo_density_patch_sha256"))
    args = parser.parse_args()
    data = load()
    if args.value:
        if args.value == "pyrowave_rdo_density_patch_sha256":
            print(data["patches"]["pyrowave_rdo_density"]["sha256"])
        else:
            print(data[args.value])
        return
    values = {
        "ALVR_URL": data["alvr"]["url"],
        "PYROWAVE_URL": data["pyrowave"]["url"],
        "GRANITE_URL": data["granite"]["url"],
        "ALVR_BASE": data["alvr"]["commit"],
        "PYROWAVE_BASE": data["pyrowave"]["commit"],
        "GRANITE_COMMIT": data["granite"]["commit"],
        "CARGO_APK_COMMIT": data["cargo_apk"]["commit"],
        "RUST_TOOLCHAIN": data["rust"],
        "NDK_VERSION": data["android_ndk"],
        "OPENXR_LOADER_RELEASE": data["openxr_loader"]["release"],
        "OPENXR_LOADER_AAR": data["openxr_loader"]["android_aar"],
        "OPENXR_LOADER_SHA256": data["openxr_loader"]["sha256"],
        "PYROWAVE_RDO_DENSITY_PATCH_SHA256": data["patches"]["pyrowave_rdo_density"]["sha256"],
    }
    for key, value in values.items():
        print(f"{key}={value}" if args.github_env else f"{key}={shlex.quote(value)}")


if __name__ == "__main__":
    main()

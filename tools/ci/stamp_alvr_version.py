#!/usr/bin/env python3
"""Stamp reconstructed ALVR Cargo packages with an installable build identity."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def default_version():
    fork = json.loads((REPO / "fork.json").read_text(encoding="utf-8"))
    commit = os.environ.get("GITHUB_SHA") or subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    return f"{fork['protocol_version']}+{commit[:12]}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alvr", type=Path)
    parser.add_argument("--version", default=default_version())
    args = parser.parse_args()
    base = json.loads((REPO / "fork.json").read_text(encoding="utf-8"))["protocol_version"]
    pattern = re.compile(rf'(?m)^(version\s*=\s*)"{re.escape(base)}"$')
    changed = 0
    for path in args.alvr.rglob("Cargo.toml"):
        text = path.read_text(encoding="utf-8")
        updated, count = pattern.subn(rf'\g<1>"{args.version}"', text)
        if count:
            path.write_text(updated, encoding="utf-8")
            changed += count
    if changed == 0:
        stamped = f'version = "{args.version}"'
        if not any(stamped in path.read_text(encoding="utf-8") for path in args.alvr.rglob("Cargo.toml")):
            raise SystemExit(f"no ALVR Cargo package used expected fork version {base}")
    print(args.version)


if __name__ == "__main__":
    main()

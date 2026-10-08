#!/usr/bin/env python3
"""SHA-256 pins for the fork's additive overlay patches, kept in sources.lock.json "overlays".

tools/ci/fetch_sources.sh applies upstream's patch stack and then our overlays, in the order of
its `overlay <tree> patches/<name>.patch` lines. That script is the one ordered list; this lock
holds one pin per overlay. Every applied overlay must be pinned and every pin must be applied.

  python3 tools/ci/source_lock.py                          check pins, files and the fetch script
  python3 tools/ci/source_lock.py verify patches/<p>.patch one overlay, as fetch_sources.sh does
  python3 tools/ci/source_lock.py pin patches/<p>.patch    record a new or regenerated overlay
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCK = REPO / "sources.lock.json"
FETCH = REPO / "tools" / "ci" / "fetch_sources.sh"
OVERLAY_LINE = re.compile(r'^overlay[ \t]+"\$dest/[^"]+"[ \t]+(patches/[A-Za-z0-9_.-]+\.patch)[ \t]*(?:#.*)?$', re.M)
# fetch_sources.sh's base pins must agree with the lock that documents them.
BASE_PINS = {"ALVR_BASE": "alvr", "PYROWAVE_BASE": "pyrowave", "GRANITE_COMMIT": "granite"}


def load():
    return json.loads(LOCK.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlays(data=None):
    pins = (data or load()).get("overlays", {})
    if not isinstance(pins, dict):
        raise SystemExit("sources.lock.json: overlays must map patches/<name>.patch to a SHA-256")
    return pins


def applied():
    """Overlay paths that fetch_sources.sh applies, in order (commented lines excluded)."""
    return OVERLAY_LINE.findall(FETCH.read_text(encoding="utf-8"))


def verify(path):
    pin = overlays().get(path)
    if not pin:
        raise SystemExit(f"{path} is not pinned in sources.lock.json overlays")
    actual = sha256(REPO / path)
    if actual != pin:
        raise SystemExit(f"{path}: SHA-256 {actual} does not match its pin {pin} in sources.lock.json")


def problems():
    data = load()
    pins = overlays(data)
    found = []
    for path, pin in pins.items():
        if not re.fullmatch(r"patches/[A-Za-z0-9_.-]+\.patch", path):
            found.append(f"{path}: not a patches/<name>.patch path")
        elif not isinstance(pin, str) or not re.fullmatch(r"[0-9a-f]{64}", pin):
            found.append(f"{path}: pin is not a SHA-256")
        elif not (REPO / path).is_file():
            found.append(f"{path}: pinned but missing")
        else:
            body = (REPO / path).read_bytes()
            if hashlib.sha256(body).hexdigest() != pin:
                found.append(f"{path}: SHA-256 differs from its pin")
            if b"\r" in body or body.startswith(b"\xef\xbb\xbf"):
                found.append(f"{path}: must be LF without a BOM")
    order = applied()
    if len(order) != len(set(order)):
        found.append("fetch_sources.sh applies an overlay twice")
    for path in sorted(set(order) - set(pins)):
        found.append(f"{path}: applied by fetch_sources.sh but not pinned")
    for path in sorted(set(pins) - set(order)):
        found.append(f"{path}: pinned but not applied by fetch_sources.sh")
    script = FETCH.read_text(encoding="utf-8")
    for variable, key in BASE_PINS.items():
        if f': "${{{variable}:={data[key]["commit"]}}}"' not in script:
            found.append(f"fetch_sources.sh {variable} differs from sources.lock.json {key}.commit")
    return found


def pin(paths):
    data = load()
    pins = overlays(data)
    for path in paths:
        if not (REPO / path).is_file():
            raise SystemExit(f"{path} does not exist")
        pins[path] = sha256(REPO / path)
    block = "".join(f'    "{path}": "{pins[path]}",\n' for path in sorted(pins)).rstrip(",\n") + "\n"
    text = LOCK.read_text(encoding="utf-8")
    # Rewrite only the overlays block, so upstream's pins keep their lines.
    updated, count = re.subn(r'(?s)("overlays": \{\n).*?(\n?  \})', lambda m: m.group(1) + block + "  }",
                             text, count=1)
    if count != 1:
        raise SystemExit('sources.lock.json has no "overlays": { ... } block to update')
    with open(LOCK, "w", encoding="utf-8", newline="\n") as lock:
        lock.write(updated)
    if overlays() != pins:
        raise SystemExit("sources.lock.json overlays were not written as expected")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="check", choices=("check", "verify", "pin"))
    parser.add_argument("patches", nargs="*")
    args = parser.parse_args()
    if args.command == "verify":
        if len(args.patches) != 1:
            parser.error("verify takes one patches/<name>.patch")
        verify(args.patches[0])
    elif args.command == "pin":
        if not args.patches:
            parser.error("pin takes one or more patches/<name>.patch")
        pin(args.patches)
    else:
        found = problems()
        for problem in found:
            print(problem, file=sys.stderr)
        if found:
            raise SystemExit(1)
        print("overlay pins verified: " + (", ".join(applied()) or "none applied"))


if __name__ == "__main__":
    main()

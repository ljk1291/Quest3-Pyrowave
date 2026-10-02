#!/bin/sh
# Checks out the upstream sources the beta is built from and applies our patches, into <dest>.
# sources.lock.json is authoritative: environment variables cannot replace its pins.
#   <dest>/pyrowave      Themaister/pyrowave at PYROWAVE_BASE + patches/pyrowave-cdf53-haar-experiments2-3.patch,
#                        with Granite (and its submodules) at GRANITE_COMMIT
# Both patches are cumulative: base + one patch reproduces the measured clone exactly.
# Usage: tools/ci/fetch_sources.sh <dest>
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
if python3 -c 'import sys' >/dev/null 2>&1; then python_cmd=python3; else python_cmd=python; fi
eval "$("$python_cmd" "$repo/tools/ci/source_lock.py")"
dest=${1:?usage: fetch_sources.sh <dest>}
[ ! -e "$dest/ALVR-20.13.0" ] && [ ! -e "$dest/pyrowave" ] || { echo "Destination already contains sources; use a new directory to preserve local work." >&2; exit 1; }
mkdir -p "$dest"

checkout() {  # <url> <dir> <commit>
    git init -q "$2"
    git -C "$2" config core.autocrlf false
    git -C "$2" config core.longpaths true   # Granite's SPIRV-Cross test files pass 260 chars
    git -C "$2" fetch -q --depth 1 "$1" "$3"
    git -C "$2" checkout -q FETCH_HEAD
    [ "$(git -C "$2" rev-parse HEAD)" = "$3" ] || {
        echo "checkout did not resolve pinned revision $3" >&2; exit 1; }
}

apply_patch() {  # <tree> <patch>; check first so a failed stack never leaves a partial tree
    git -C "$1" apply --check --binary --whitespace=nowarn "$2"
    git -C "$1" apply --binary --whitespace=nowarn "$2"
}

checkout "$ALVR_URL" "$dest/ALVR-20.13.0" "$ALVR_BASE"
git -C "$dest/ALVR-20.13.0" submodule update -q --init --recursive --depth 1   # openvr headers
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/alvr-20.13.0-server-instrumentation.patch"
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/quest3-alvr.patch"
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/stable-baseline-alvr.patch"
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/fork-identity-alvr.patch"

checkout "$PYROWAVE_URL" "$dest/pyrowave" "$PYROWAVE_BASE"
# pyrowave's checkout_granite.sh pins a newer Granite (9d44761), which spiked encoder p99 to 14 ms;
# the measurements used 842d9d5, cloned here with all of its submodules.
checkout "$GRANITE_URL" "$dest/pyrowave/Granite" "$GRANITE_COMMIT"
git -C "$dest/pyrowave/Granite" submodule update -q --init --recursive --depth 1
[ "$(git -C "$dest/pyrowave/Granite" rev-parse HEAD)" = "$GRANITE_COMMIT" ] \
    || { echo "Granite is not at $GRANITE_COMMIT"; exit 1; }
apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-cdf53-haar-experiments2-3.patch"
apply_patch "$dest/pyrowave" "$repo/patches/quest3-pyrowave.patch"

echo "sources ready in $dest: ALVR ${ALVR_BASE%${ALVR_BASE#???????}}, pyrowave ${PYROWAVE_BASE%${PYROWAVE_BASE#???????}}, Granite ${GRANITE_COMMIT%${GRANITE_COMMIT#???????}}"

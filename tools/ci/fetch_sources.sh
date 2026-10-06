#!/bin/sh
# Checks out the upstream sources the beta is built from and applies our patches, into <dest>.
# sources.lock.json is authoritative: environment variables cannot replace its pins.
#   <dest>/pyrowave      Themaister/pyrowave at PYROWAVE_BASE + the cumulative research/Quest
#                        overlays and the additive WO-7 RDO-density overlay,
#                        with Granite (and its submodules) at GRANITE_COMMIT
# The ALVR stack is applied in explicit order; the Light phase overlay depends on WO-8.
# The PyroWave research/Quest patches are cumulative; WO-7 applies after both and changes the encoder only.
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
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/wo8-foveation.patch"
expected_wo8_phase_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value wo8_light_centre_phase_patch_sha256)
actual_wo8_phase_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/wo8-light-centre-phase.patch")
[ "$actual_wo8_phase_patch" = "$expected_wo8_phase_patch" ] || { echo "WO-8 Light phase patch hash does not match sources.lock.json" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/wo8-light-centre-phase.patch"
expected_nvenc_dimension_preflight_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value nvenc_dimension_preflight_patch_sha256)
actual_nvenc_dimension_preflight_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/nvenc-dimension-preflight.patch")
[ "$actual_nvenc_dimension_preflight_patch" = "$expected_nvenc_dimension_preflight_patch" ] || { echo "NVENC dimension-preflight patch hash does not match sources.lock.json" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/nvenc-dimension-preflight.patch"
expected_alvr_rdo_live_readback_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value alvr_pyrowave_rdo_live_readback_patch_sha256)
actual_alvr_rdo_live_readback_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/alvr-pyrowave-rdo-live-readback.patch")
[ "$actual_alvr_rdo_live_readback_patch" = "$expected_alvr_rdo_live_readback_patch" ] || { echo "ALVR PyroWave RDO live-readback patch hash does not match sources.lock.json" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/alvr-pyrowave-rdo-live-readback.patch"
expected_alvr_rdo_session_setting_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value alvr_pyrowave_rdo_session_setting_patch_sha256)
actual_alvr_rdo_session_setting_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/alvr-pyrowave-rdo-session-setting.patch")
[ "$actual_alvr_rdo_session_setting_patch" = "$expected_alvr_rdo_session_setting_patch" ] || { echo "ALVR PyroWave RDO session-setting patch hash does not match sources.lock.json" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/alvr-pyrowave-rdo-session-setting.patch"

expected_staging_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value foveated_staging_correctness_patch_sha256)
actual_staging_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/foveated-staging-correctness.patch")
[ "$actual_staging_patch" = "$expected_staging_patch" ] || { echo "Foveated staging correctness patch hash differs" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/foveated-staging-correctness.patch"

# T2 presentation overlay stacks after the complete baseline; shader defaults are immutable.
expected_presentation_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value presentation_filters_patch_sha256)
actual_presentation_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/presentation-filters.patch")
[ "$actual_presentation_patch" = "$expected_presentation_patch" ] || { echo "Presentation filter patch hash differs" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/presentation-filters.patch"

# T1 direct-eye foveation overlay touches files disjoint from T2's overlay.
expected_direct_ffe_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value direct_eye_foveation_patch_sha256)
actual_direct_ffe_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/direct-eye-foveation.patch")
[ "$actual_direct_ffe_patch" = "$expected_direct_ffe_patch" ] || { echo "Direct eye foveation patch hash differs" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/direct-eye-foveation.patch"

# Pure FFR bug fix: match the embedded fullscreen vertex shader's UV register.
expected_ffe_linkage_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value foveation_shader_linkage_patch_sha256)
actual_ffe_linkage_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/foveation-shader-linkage.patch")
[ "$actual_ffe_linkage_patch" = "$expected_ffe_linkage_patch" ] || { echo "Foveation shader linkage patch hash differs" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/foveation-shader-linkage.patch"

# Default-off frame-loss accounting and source-key statistics experiment.
expected_frame_loss_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value frame_loss_diagnostics_patch_sha256)
actual_frame_loss_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/frame-loss-diagnostics.patch")
[ "$actual_frame_loss_patch" = "$expected_frame_loss_patch" ] || { echo "Frame loss diagnostics patch hash differs" >&2; exit 1; }
apply_patch "$dest/ALVR-20.13.0" "$repo/patches/frame-loss-diagnostics.patch"

checkout "$PYROWAVE_URL" "$dest/pyrowave" "$PYROWAVE_BASE"
# pyrowave's checkout_granite.sh pins a newer Granite (9d44761), which spiked encoder p99 to 14 ms;
# the measurements used 842d9d5, cloned here with all of its submodules.
checkout "$GRANITE_URL" "$dest/pyrowave/Granite" "$GRANITE_COMMIT"
git -C "$dest/pyrowave/Granite" submodule update -q --init --recursive --depth 1
[ "$(git -C "$dest/pyrowave/Granite" rev-parse HEAD)" = "$GRANITE_COMMIT" ] \
    || { echo "Granite is not at $GRANITE_COMMIT"; exit 1; }
apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-cdf53-haar-experiments2-3.patch"
apply_patch "$dest/pyrowave" "$repo/patches/quest3-pyrowave.patch"
expected_rdo_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value pyrowave_rdo_density_patch_sha256)
actual_rdo_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/pyrowave-rdo-density.patch")
[ "$actual_rdo_patch" = "$expected_rdo_patch" ] || { echo "WO-7 PyroWave RDO patch hash does not match sources.lock.json" >&2; exit 1; }
apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-density.patch"
expected_rdo_live_readback_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value pyrowave_rdo_live_readback_patch_sha256)
actual_rdo_live_readback_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/pyrowave-rdo-live-readback.patch")
[ "$actual_rdo_live_readback_patch" = "$expected_rdo_live_readback_patch" ] || { echo "PyroWave RDO live-readback patch hash does not match sources.lock.json" >&2; exit 1; }
apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-live-readback.patch"
expected_rdo_session_setting_patch=$($python_cmd "$repo/tools/ci/source_lock.py" --value pyrowave_rdo_session_setting_patch_sha256)
actual_rdo_session_setting_patch=$($python_cmd -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$repo/patches/pyrowave-rdo-session-setting.patch")
[ "$actual_rdo_session_setting_patch" = "$expected_rdo_session_setting_patch" ] || { echo "PyroWave RDO session-setting patch hash does not match sources.lock.json" >&2; exit 1; }
apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-session-setting.patch"

echo "sources ready in $dest: ALVR ${ALVR_BASE%${ALVR_BASE#???????}}, pyrowave ${PYROWAVE_BASE%${PYROWAVE_BASE#???????}}, Granite ${GRANITE_COMMIT%${GRANITE_COMMIT#???????}}"

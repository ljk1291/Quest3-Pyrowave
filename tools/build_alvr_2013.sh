#!/bin/sh
# Builds the Quest 3 client APK from the patched ALVR 20.13.0 clone (package
# io.github.ljk1291.quest3pyrowave). The clone is an external input and lives beside this repo, not in it --
# see README "Building from source". Pass --print-dir to resolve the clone path
# without building.
set -eu
workspace_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$workspace_dir/tools/lib/xrwired_env.sh"
pyrowave_dir="$inputs_dir/research/pyrowave"
if python3 -c 'import sys' >/dev/null 2>&1; then python_cmd=python3; else python_cmd=python; fi
rust_toolchain=$("$python_cmd" "$workspace_dir/tools/ci/source_lock.py" --value rust)
[ -n "$rust_toolchain" ] || { echo "could not read Rust toolchain from sources.lock.json" >&2; exit 1; }
alvr_dir="$inputs_dir/research/ALVR-20.13.0"

if [ "${1:-}" = "--print-dir" ]; then printf '%s\n' "$alvr_dir"; exit 0; fi

"$python_cmd" "$workspace_dir/tools/ci/stamp_alvr_version.py" "$alvr_dir" >/dev/null

# The PyroWave decoder rides into the APK as two prebuilt .so files in cargo-apk's runtime_libs
# dir (which is gitignored in the clone): our libpyroclient.so and PyroWave's own library.
# client_core/build.rs links against the same dir.
"$workspace_dir/tools/pyroclient/build.sh" >/dev/null
cp "$workspace_dir/tools/pyroclient/libpyroclient.so" "$pyrowave_dir/build-android/libpyrowave-shared.so" \
    "$alvr_dir/deps/android_openxr/arm64-v8a/"

cd "$alvr_dir"
env -u ANDROID_SDK_ROOT ANDROID_HOME="$android_sdk" \
    ANDROID_NDK_HOME="$android_ndk" ANDROID_NDK_ROOT="$android_ndk" \
    JAVA_HOME="$java_home" cargo +"$rust_toolchain" xtask build-client --release

[ -s "$alvr_dir/build/alvr_client_android/alvr_client_android.apk" ] || {
    echo "ALVR client APK was not produced" >&2; exit 1; }

printf '%s\n' "$alvr_dir/build/alvr_client_android/alvr_client_android.apk"

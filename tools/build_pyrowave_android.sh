#!/bin/sh
# Builds PyroWave for the headset: libpyrowave-shared.so in <pyrowave>/build-android, which
# pyroclient/build.sh, pyrowave_android/build.sh and the ALVR client link against. Settings are the
# ones the Mac's build-android was configured with (its CMakeCache): arm64-v8a,
# android-30, Release, -DPYROWAVE_DEVEL=OFF, -DPYROWAVE_FP32_MATH=ON, Ninja.
set -eu
workspace_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$workspace_dir/tools/lib/xrwired_env.sh"
pyrowave_dir="$inputs_dir/research/pyrowave"
if python3 -c 'import sys' >/dev/null 2>&1; then python_cmd=python3; else python_cmd=python; fi
[ "$("$python_cmd" "$workspace_dir/tools/ci/source_lock.py" | sed -n "s/^NDK_VERSION='\(.*\)'$/\1/p")" = "${android_ndk##*/}" ] || {
    echo "Android NDK does not match sources.lock.json" >&2; exit 1; }
[ -f "$pyrowave_dir/pyrowave.h" ] || { echo "no pyrowave.h under $pyrowave_dir"; exit 1; }
[ -f "$android_ndk/build/cmake/android.toolchain.cmake" ] || { echo "no NDK at $android_ndk"; exit 1; }
"$python_cmd" "$workspace_dir/tools/ci/check_shader_manifest.py" "$pyrowave_dir"
build="$pyrowave_dir/build-android"
cmake -S "$pyrowave_dir" -B "$build" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$android_ndk/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-30 \
    -DCMAKE_BUILD_TYPE=Release -DPYROWAVE_DEVEL=OFF -DPYROWAVE_FP32_MATH=ON
cmake --build "$build" --target pyrowave-shared
[ -s "$build/libpyrowave-shared.so" ] || { echo "PyroWave Android library was not produced" >&2; exit 1; }
echo "BUILD_OK -> $build/libpyrowave-shared.so"

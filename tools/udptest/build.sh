#!/bin/bash
# Builds the UDP and TCP transport probes for the headset (NDK) and, on a POSIX host,
# natively for a loopback smoke test.
set -e
workspace_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$workspace_dir/tools/lib/xrwired_env.sh"
HERE=$(xrw_native "$(dirname -- "$0")")
[ -n "$ndk_bin" ] || { echo "no NDK host toolchain under $android_ndk"; exit 1; }
"$ndk_bin/clang" --target=aarch64-linux-android29 -O2 -Wall -Wextra "$HERE/udprecv.c" -o "$HERE/udprecv-android"
"$ndk_bin/clang" --target=aarch64-linux-android29 -O2 -Wall -Wextra "$HERE/tcpframerecv.c" -o "$HERE/tcpframerecv-android"
# The host build is a loopback smoke test for a POSIX machine; udprecv.c uses BSD sockets only.
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) echo "BUILD_OK -> $HERE/udprecv-android $HERE/tcpframerecv-android (host build skipped on Windows)" ;;
    *) cc -O2 -Wall -Wextra "$HERE/udprecv.c" -o "$HERE/udprecv-host"
       cc -O2 -Wall -Wextra "$HERE/tcpframerecv.c" -o "$HERE/tcpframerecv-host"
       echo "BUILD_OK -> $HERE/udprecv-android $HERE/tcpframerecv-android $HERE/udprecv-host $HERE/tcpframerecv-host" ;;
esac

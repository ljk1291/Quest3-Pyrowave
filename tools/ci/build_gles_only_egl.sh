#!/bin/sh
set -eu
# CI-local software-test fixture. Never packages or edits the system library.
dest=/tmp/q3pw-gles-only
mkdir -p "$dest"
real=$(readlink -f /usr/lib/x86_64-linux-gnu/libEGL.so.1)
test -f "$real"
cp "$real" "$dest/libq3pw_real_egl.so.1"
patchelf --set-soname libq3pw_real_egl.so.1 "$dest/libq3pw_real_egl.so.1"
cc -std=c11 -Wall -Wextra -Werror -shared -fPIC tools/ci/gles_only_egl.c \
  -L"$dest" -Wl,--no-as-needed -l:libq3pw_real_egl.so.1 -ldl -o "$dest/libEGL.so.1"
ln -sf libEGL.so.1 "$dest/libEGL.so"
cc -std=c11 -Wall -Wextra -Werror tools/ci/gles_only_egl_probe.c -ldl -o "$dest/probe"
LD_LIBRARY_PATH="$dest${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$dest/probe"

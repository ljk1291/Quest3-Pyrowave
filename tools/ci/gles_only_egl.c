/* SPDX-License-Identifier: MIT
 * CI-only EGL API restriction, never linked into either installable build.
 * wgpu 24 prefers desktop GL when EGL advertises both APIs. The Quest import
 * path requires GLES external textures. Keep Mesa's real implementation and
 * advertise only its supported GLES API; do not fake features or pixel output.
 * Link with --no-as-needed -lEGL so every other entry point is the real library.
 */
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <dlfcn.h>
#include <string.h>

EGLAPI const char *EGLAPIENTRY eglQueryString(EGLDisplay display, EGLint name)
{
    typedef const char *(*Query)(EGLDisplay, EGLint);
    Query real = (Query)dlsym(RTLD_NEXT, "eglQueryString");
    const char *value = real ? real(display, name) : NULL;
    if (name == EGL_CLIENT_APIS && value && strstr(value, "OpenGL_ES"))
        return "OpenGL_ES";
    return value;
}

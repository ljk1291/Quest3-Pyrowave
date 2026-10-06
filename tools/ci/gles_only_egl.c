/* SPDX-License-Identifier: MIT
 * CI-only EGL API restriction, never linked into either installable build.
 * wgpu 24 prefers desktop GL when EGL advertises both APIs. The Quest import
 * path requires GLES external textures. Keep Mesa's real implementation and
 * advertise only its supported GLES API; do not fake features or pixel output.
 * Link to the CI-local, SONAME-renamed copy of the system EGL library so the
 * libEGL.so.1 wrapper cannot resolve its own dependency recursively. The copy's
 * executable code is untouched; every other entry point is the real library.
 */
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <dlfcn.h>
#include <string.h>

EGLAPI const char *EGLAPIENTRY eglQueryString(EGLDisplay display, EGLint name)
{
    typedef const char *(*Query)(EGLDisplay, EGLint);
    void *library = dlopen("libq3pw_real_egl.so.1", RTLD_NOW | RTLD_LOCAL);
    Query real = library ? (Query)dlsym(library, "eglQueryString") : NULL;
    const char *value = real ? real(display, name) : NULL;
    if (name == EGL_CLIENT_APIS && value && strstr(value, "OpenGL_ES"))
        return "OpenGL_ES";
    return value;
}

/* SPDX-License-Identifier: MIT
 * Verify the same dynamic filename used by khronos-egl 6.0 before native tests.
 * Real Mesa context and entry points; no fake extensions, errors or pixels.
 */
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define REQUIRE(condition) do { if (!(condition)) { \
    fprintf(stderr, "EGL probe failed at line %d: %s\n", __LINE__, #condition); \
    exit(1); } } while (0)
#define LOAD(name) __typeof__(&name) name##_fn = (__typeof__(&name))dlsym(library, #name); REQUIRE(name##_fn)

int main(void)
{
    void *library = dlopen("libEGL.so.1", RTLD_NOW | RTLD_LOCAL);
    REQUIRE(library);
    LOAD(eglGetDisplay); LOAD(eglInitialize); LOAD(eglQueryString);
    LOAD(eglBindAPI); LOAD(eglChooseConfig); LOAD(eglCreateContext);
    LOAD(eglCreatePbufferSurface); LOAD(eglMakeCurrent); LOAD(eglGetProcAddress);
    LOAD(eglDestroyContext); LOAD(eglDestroySurface); LOAD(eglTerminate);
    Dl_info origin;
    REQUIRE(dladdr((void *)eglQueryString_fn, &origin));
    REQUIRE(strstr(origin.dli_fname, "/q3pw-gles-only/libEGL.so.1"));
    EGLDisplay display = eglGetDisplay_fn(EGL_DEFAULT_DISPLAY);
    EGLint major = 0, minor = 0;
    REQUIRE(display != EGL_NO_DISPLAY && eglInitialize_fn(display, &major, &minor));
    const char *apis = eglQueryString_fn(display, EGL_CLIENT_APIS);
    REQUIRE(apis && strcmp(apis, "OpenGL_ES") == 0);
    void *real = dlopen("libq3pw_real_egl.so.1", RTLD_NOW | RTLD_LOCAL);
    REQUIRE(real);
    __typeof__(&eglQueryString) original = (__typeof__(&eglQueryString))dlsym(real, "eglQueryString");
    REQUIRE(original);
    const char *original_apis = original(display, EGL_CLIENT_APIS);
    REQUIRE(original_apis && strstr(original_apis, "OpenGL_ES"));
    REQUIRE(eglBindAPI_fn(EGL_OPENGL_ES_API));
    const EGLint config_attributes[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE};
    EGLConfig config;
    EGLint count = 0;
    REQUIRE(eglChooseConfig_fn(display, config_attributes, &config, 1, &count) && count == 1);
    const EGLint context_attributes[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
    EGLContext context = eglCreateContext_fn(display, config, EGL_NO_CONTEXT, context_attributes);
    REQUIRE(context != EGL_NO_CONTEXT);
    const EGLint surface_attributes[] = {EGL_WIDTH, 8, EGL_HEIGHT, 8, EGL_NONE};
    EGLSurface surface = eglCreatePbufferSurface_fn(display, config, surface_attributes);
    REQUIRE(surface != EGL_NO_SURFACE);
    REQUIRE(eglMakeCurrent_fn(display, surface, surface, context));
    __typeof__(&glGetString) get_string = (__typeof__(&glGetString))eglGetProcAddress_fn("glGetString");
    REQUIRE(get_string);
    const char *version = (const char *)get_string(GL_VERSION);
    const char *renderer = (const char *)get_string(GL_RENDERER);
    REQUIRE(version && strncmp(version, "OpenGL ES", 9) == 0);
    REQUIRE(renderer && strstr(renderer, "llvmpipe"));
    printf("EGL loader: %s; real APIs: %s; restricted APIs: %s; GL: %s; renderer: %s\n",
        origin.dli_fname, original_apis, apis, version, renderer);
    REQUIRE(eglMakeCurrent_fn(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT));
    REQUIRE(eglDestroySurface_fn(display, surface));
    REQUIRE(eglDestroyContext_fn(display, context));
    REQUIRE(eglTerminate_fn(display));
    dlclose(real); dlclose(library);
    return 0;
}

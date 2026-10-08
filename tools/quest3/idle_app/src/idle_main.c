/*
 * Q3PW Idle: minimal Quest 3 OpenXR "idle" app.
 *
 * Shows plain black (zero composition layers), requests 72 Hz and the lowest
 * CPU/GPU performance levels, and otherwise does nothing. See README.md.
 */
#include <android/log.h>
#include <android_native_app_glue.h>
#include <EGL/egl.h>
#include <jni.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#ifndef XR_USE_PLATFORM_ANDROID
#define XR_USE_PLATFORM_ANDROID
#endif
#ifndef XR_USE_GRAPHICS_API_OPENGL_ES
#define XR_USE_GRAPHICS_API_OPENGL_ES
#endif
#include <openxr/openxr.h>
#include <openxr/openxr_platform.h>

#ifndef EGL_OPENGL_ES3_BIT
#define EGL_OPENGL_ES3_BIT 0x00000040
#endif

#define TAG "Q3PW_IDLE"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

#define TARGET_REFRESH_HZ 72.0f

typedef struct App {
    struct android_app *app;
    bool resumed;
    bool init_attempted;
    bool finish_called;

    /* EGL */
    EGLDisplay dpy;
    EGLConfig cfg;
    EGLContext ctx;
    EGLSurface surf;

    /* OpenXR */
    XrInstance instance;
    XrSystemId system_id;
    XrSession session;
    XrSessionState state;
    bool session_running;
    bool marker_logged;

    bool ext_gles;
    bool ext_android_create;
    bool ext_refresh;
    bool ext_perf;

    PFN_xrGetOpenGLESGraphicsRequirementsKHR pfnGetGLESReq;
    PFN_xrRequestDisplayRefreshRateFB pfnRequestRefresh;
    PFN_xrGetDisplayRefreshRateFB pfnGetRefresh;
    PFN_xrEnumerateDisplayRefreshRatesFB pfnEnumRefresh;
    PFN_xrPerfSettingsSetPerformanceLevelEXT pfnPerfSet;

    /* what actually succeeded, for the marker line */
    bool refresh_ok;
    bool perf_cpu_ok;
    bool perf_gpu_ok;
    unsigned frame_failures;
} App;

/* ---------------------------------------------------------------- logging */

static unsigned g_fail_count;

static bool xr_ok(App *a, XrResult r, const char *what)
{
    if (XR_SUCCEEDED(r)) {
        return true;
    }
    /* log every failure, but thin out a persistent failure so logcat is not flooded */
    g_fail_count++;
    if (g_fail_count <= 64 || (g_fail_count % 500) == 0) {
        char buf[XR_MAX_RESULT_STRING_SIZE];
        buf[0] = 0;
        if (a == NULL || a->instance == XR_NULL_HANDLE ||
            XR_FAILED(xrResultToString(a->instance, r, buf))) {
            snprintf(buf, sizeof(buf), "XrResult(%d)", (int)r);
        }
        LOGE("[Q3PW_IDLE] XR failure: %s -> %s (%d) [count=%u]", what, buf, (int)r, g_fail_count);
    }
    return false;
}

static void sleep_ms(long ms)
{
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
}

/* -------------------------------------------------------------------- EGL */

static bool init_egl(App *a)
{
    a->dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (a->dpy == EGL_NO_DISPLAY) {
        LOGE("[Q3PW_IDLE] eglGetDisplay failed (0x%x)", eglGetError());
        return false;
    }
    EGLint major = 0, minor = 0;
    if (!eglInitialize(a->dpy, &major, &minor)) {
        LOGE("[Q3PW_IDLE] eglInitialize failed (0x%x)", eglGetError());
        return false;
    }
    const EGLint cfg_attr[] = {
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8,
        EGL_DEPTH_SIZE, 0, EGL_STENCIL_SIZE, 0,
        EGL_NONE};
    EGLint n = 0;
    if (!eglChooseConfig(a->dpy, cfg_attr, &a->cfg, 1, &n) || n < 1) {
        LOGE("[Q3PW_IDLE] eglChooseConfig failed (0x%x, n=%d)", eglGetError(), (int)n);
        return false;
    }
    const EGLint ctx_attr[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
    a->ctx = eglCreateContext(a->dpy, a->cfg, EGL_NO_CONTEXT, ctx_attr);
    if (a->ctx == EGL_NO_CONTEXT) {
        LOGE("[Q3PW_IDLE] eglCreateContext failed (0x%x)", eglGetError());
        return false;
    }
    const EGLint pb_attr[] = {EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE};
    a->surf = eglCreatePbufferSurface(a->dpy, a->cfg, pb_attr);
    if (a->surf == EGL_NO_SURFACE) {
        LOGE("[Q3PW_IDLE] eglCreatePbufferSurface failed (0x%x)", eglGetError());
        return false;
    }
    if (!eglMakeCurrent(a->dpy, a->surf, a->surf, a->ctx)) {
        LOGE("[Q3PW_IDLE] eglMakeCurrent failed (0x%x)", eglGetError());
        return false;
    }
    LOGI("[Q3PW_IDLE] EGL %d.%d pbuffer 16x16 GLES3 context ready", (int)major, (int)minor);
    return true;
}

static void shutdown_egl(App *a)
{
    if (a->dpy != EGL_NO_DISPLAY) {
        eglMakeCurrent(a->dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (a->surf != EGL_NO_SURFACE) {
            eglDestroySurface(a->dpy, a->surf);
        }
        if (a->ctx != EGL_NO_CONTEXT) {
            eglDestroyContext(a->dpy, a->ctx);
        }
        eglTerminate(a->dpy);
    }
    a->dpy = EGL_NO_DISPLAY;
    a->ctx = EGL_NO_CONTEXT;
    a->surf = EGL_NO_SURFACE;
}

/* --------------------------------------------------------------- OpenXR */

static void request_finish(App *a)
{
    if (!a->finish_called) {
        a->finish_called = true;
        LOGI("[Q3PW_IDLE] finishing activity");
        ANativeActivity_finish(a->app->activity);
    }
}

static void teardown_xr(App *a)
{
    if (a->session != XR_NULL_HANDLE) {
        xr_ok(a, xrDestroySession(a->session), "xrDestroySession");
        a->session = XR_NULL_HANDLE;
    }
    a->session_running = false;
    if (a->instance != XR_NULL_HANDLE) {
        xr_ok(a, xrDestroyInstance(a->instance), "xrDestroyInstance");
        a->instance = XR_NULL_HANDLE;
    }
    a->state = XR_SESSION_STATE_UNKNOWN;
}

static bool has_ext(const XrExtensionProperties *p, uint32_t n, const char *name)
{
    for (uint32_t i = 0; i < n; i++) {
        if (strcmp(p[i].extensionName, name) == 0) {
            return true;
        }
    }
    return false;
}

#define GET_PROC(a, fn, name)                                                          \
    xr_ok((a), xrGetInstanceProcAddr((a)->instance, name, (PFN_xrVoidFunction *)&(fn)), \
          "xrGetInstanceProcAddr(" name ")")

static bool init_xr(App *a)
{
    struct android_app *app = a->app;

    /* 1. loader init (XR_KHR_loader_init_android) */
    PFN_xrInitializeLoaderKHR pfnInitLoader = NULL;
    if (!xr_ok(a,
               xrGetInstanceProcAddr(XR_NULL_HANDLE, "xrInitializeLoaderKHR",
                                     (PFN_xrVoidFunction *)&pfnInitLoader),
               "xrGetInstanceProcAddr(xrInitializeLoaderKHR)") ||
        pfnInitLoader == NULL) {
        return false;
    }
    XrLoaderInitInfoAndroidKHR loader_info = {XR_TYPE_LOADER_INIT_INFO_ANDROID_KHR};
    loader_info.applicationVM = app->activity->vm;
    loader_info.applicationContext = app->activity->clazz;
    if (!xr_ok(a, pfnInitLoader((const XrLoaderInitInfoBaseHeaderKHR *)&loader_info),
               "xrInitializeLoaderKHR")) {
        return false;
    }

    /* 2. extensions */
    uint32_t ext_count = 0;
    if (!xr_ok(a, xrEnumerateInstanceExtensionProperties(NULL, 0, &ext_count, NULL),
               "xrEnumerateInstanceExtensionProperties(count)")) {
        return false;
    }
    XrExtensionProperties props[256];
    if (ext_count > 256) {
        ext_count = 256;
    }
    for (uint32_t i = 0; i < ext_count; i++) {
        props[i].type = XR_TYPE_EXTENSION_PROPERTIES;
        props[i].next = NULL;
    }
    if (!xr_ok(a, xrEnumerateInstanceExtensionProperties(NULL, ext_count, &ext_count, props),
               "xrEnumerateInstanceExtensionProperties")) {
        return false;
    }
    a->ext_gles = has_ext(props, ext_count, XR_KHR_OPENGL_ES_ENABLE_EXTENSION_NAME);
    a->ext_android_create = has_ext(props, ext_count, XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME);
    a->ext_refresh = has_ext(props, ext_count, XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME);
    a->ext_perf = has_ext(props, ext_count, XR_EXT_PERFORMANCE_SETTINGS_EXTENSION_NAME);
    LOGI("[Q3PW_IDLE] extensions: %u total, opengl_es=%d android_create=%d display_refresh=%d perf_settings=%d",
         ext_count, a->ext_gles, a->ext_android_create, a->ext_refresh, a->ext_perf);
    if (!a->ext_gles) {
        LOGE("[Q3PW_IDLE] " XR_KHR_OPENGL_ES_ENABLE_EXTENSION_NAME " not available");
        return false;
    }

    const char *enabled[4];
    uint32_t enabled_count = 0;
    enabled[enabled_count++] = XR_KHR_OPENGL_ES_ENABLE_EXTENSION_NAME;
    if (a->ext_android_create) {
        enabled[enabled_count++] = XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME;
    }
    if (a->ext_refresh) {
        enabled[enabled_count++] = XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME;
    }
    if (a->ext_perf) {
        enabled[enabled_count++] = XR_EXT_PERFORMANCE_SETTINGS_EXTENSION_NAME;
    }

    /* 3. instance */
    XrInstanceCreateInfoAndroidKHR android_info = {XR_TYPE_INSTANCE_CREATE_INFO_ANDROID_KHR};
    android_info.applicationVM = app->activity->vm;
    android_info.applicationActivity = app->activity->clazz;

    XrInstanceCreateInfo ici = {XR_TYPE_INSTANCE_CREATE_INFO};
    ici.next = a->ext_android_create ? (const void *)&android_info : NULL;
    strncpy(ici.applicationInfo.applicationName, "Q3PW Idle", XR_MAX_APPLICATION_NAME_SIZE - 1);
    ici.applicationInfo.applicationVersion = 1;
    strncpy(ici.applicationInfo.engineName, "none", XR_MAX_ENGINE_NAME_SIZE - 1);
    ici.applicationInfo.engineVersion = 1;
    ici.applicationInfo.apiVersion = XR_API_VERSION_1_0;
    ici.enabledExtensionCount = enabled_count;
    ici.enabledExtensionNames = enabled;
    if (!xr_ok(a, xrCreateInstance(&ici, &a->instance), "xrCreateInstance")) {
        a->instance = XR_NULL_HANDLE;
        return false;
    }

    /* extension entry points */
    if (!GET_PROC(a, a->pfnGetGLESReq, "xrGetOpenGLESGraphicsRequirementsKHR") ||
        a->pfnGetGLESReq == NULL) {
        return false;
    }
    if (a->ext_refresh) {
        GET_PROC(a, a->pfnRequestRefresh, "xrRequestDisplayRefreshRateFB");
        GET_PROC(a, a->pfnGetRefresh, "xrGetDisplayRefreshRateFB");
        GET_PROC(a, a->pfnEnumRefresh, "xrEnumerateDisplayRefreshRatesFB");
    }
    if (a->ext_perf) {
        GET_PROC(a, a->pfnPerfSet, "xrPerfSettingsSetPerformanceLevelEXT");
    }

    /* 4. system */
    XrSystemGetInfo sgi = {XR_TYPE_SYSTEM_GET_INFO};
    sgi.formFactor = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;
    if (!xr_ok(a, xrGetSystem(a->instance, &sgi, &a->system_id), "xrGetSystem")) {
        return false;
    }
    XrSystemProperties sp = {XR_TYPE_SYSTEM_PROPERTIES};
    if (xr_ok(a, xrGetSystemProperties(a->instance, a->system_id, &sp), "xrGetSystemProperties")) {
        LOGI("[Q3PW_IDLE] system: %s", sp.systemName);
    }

    /* 5. GLES requirements + EGL + session */
    XrGraphicsRequirementsOpenGLESKHR req = {XR_TYPE_GRAPHICS_REQUIREMENTS_OPENGL_ES_KHR};
    if (!xr_ok(a, a->pfnGetGLESReq(a->instance, a->system_id, &req),
               "xrGetOpenGLESGraphicsRequirementsKHR")) {
        return false;
    }
    if (!init_egl(a)) {
        return false;
    }
    XrGraphicsBindingOpenGLESAndroidKHR gb = {XR_TYPE_GRAPHICS_BINDING_OPENGL_ES_ANDROID_KHR};
    gb.display = a->dpy;
    gb.config = a->cfg;
    gb.context = a->ctx;
    XrSessionCreateInfo sci = {XR_TYPE_SESSION_CREATE_INFO};
    sci.next = &gb;
    sci.systemId = a->system_id;
    if (!xr_ok(a, xrCreateSession(a->instance, &sci, &a->session), "xrCreateSession")) {
        a->session = XR_NULL_HANDLE;
        return false;
    }
    LOGI("[Q3PW_IDLE] session created, waiting for READY");
    return true;
}

static void apply_perf_levels(App *a)
{
    if (a->ext_perf && a->pfnPerfSet != NULL) {
        a->perf_cpu_ok = xr_ok(a,
            a->pfnPerfSet(a->session, XR_PERF_SETTINGS_DOMAIN_CPU_EXT,
                          XR_PERF_SETTINGS_LEVEL_POWER_SAVINGS_EXT),
            "xrPerfSettingsSetPerformanceLevelEXT(CPU)");
        a->perf_gpu_ok = xr_ok(a,
            a->pfnPerfSet(a->session, XR_PERF_SETTINGS_DOMAIN_GPU_EXT,
                          XR_PERF_SETTINGS_LEVEL_POWER_SAVINGS_EXT),
            "xrPerfSettingsSetPerformanceLevelEXT(GPU)");
    }
}

static void begin_session(App *a)
{
    XrSessionBeginInfo sbi = {XR_TYPE_SESSION_BEGIN_INFO};
    sbi.primaryViewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
    if (!xr_ok(a, xrBeginSession(a->session, &sbi), "xrBeginSession")) {
        return;
    }
    a->session_running = true;

    float cur = 0.0f;
    if (a->ext_refresh && a->pfnRequestRefresh != NULL) {
        if (a->pfnEnumRefresh != NULL) {
            uint32_t n = 0;
            float rates[16];
            if (xr_ok(a, a->pfnEnumRefresh(a->session, 0, &n, NULL), "xrEnumerateDisplayRefreshRatesFB(count)") &&
                n > 0) {
                if (n > 16) {
                    n = 16;
                }
                if (xr_ok(a, a->pfnEnumRefresh(a->session, n, &n, rates), "xrEnumerateDisplayRefreshRatesFB")) {
                    char line[160];
                    int len = snprintf(line, sizeof(line), "[Q3PW_IDLE] supported refresh rates:");
                    for (uint32_t i = 0; i < n && len < (int)sizeof(line) - 12; i++) {
                        len += snprintf(line + len, sizeof(line) - (size_t)len, " %.0f", rates[i]);
                    }
                    LOGI("%s", line);
                }
            }
        }
        a->refresh_ok = xr_ok(a, a->pfnRequestRefresh(a->session, TARGET_REFRESH_HZ),
                              "xrRequestDisplayRefreshRateFB(72)");
        if (a->pfnGetRefresh != NULL) {
            xr_ok(a, a->pfnGetRefresh(a->session, &cur), "xrGetDisplayRefreshRateFB");
        }
    }
    apply_perf_levels(a);

    if (!a->marker_logged) {
        a->marker_logged = true;
        LOGI("[Q3PW_IDLE] session running refresh=%s perf_cpu=%s perf_gpu=%s ext_refresh=%d ext_perf=%d refresh_cur=%.0f",
             a->refresh_ok ? "72" : (a->ext_refresh ? "fail" : "na"),
             a->perf_cpu_ok ? "power_savings" : (a->ext_perf ? "fail" : "na"),
             a->perf_gpu_ok ? "power_savings" : (a->ext_perf ? "fail" : "na"),
             a->ext_refresh ? 1 : 0, a->ext_perf ? 1 : 0, (double)cur);
    } else {
        LOGI("[Q3PW_IDLE] session running again (re-begin)");
    }
}

static void end_session(App *a)
{
    if (a->session_running) {
        xr_ok(a, xrEndSession(a->session), "xrEndSession");
        a->session_running = false;
        LOGI("[Q3PW_IDLE] session ended");
    }
}

static void poll_xr_events(App *a)
{
    while (a->instance != XR_NULL_HANDLE) {
        XrEventDataBuffer ev = {XR_TYPE_EVENT_DATA_BUFFER};
        XrResult r = xrPollEvent(a->instance, &ev);
        if (r == XR_EVENT_UNAVAILABLE) {
            break;
        }
        if (!xr_ok(a, r, "xrPollEvent")) {
            break;
        }
        switch (ev.type) {
        case XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED: {
            const XrEventDataSessionStateChanged *e = (const XrEventDataSessionStateChanged *)&ev;
            a->state = e->state;
            LOGI("[Q3PW_IDLE] session state -> %d", (int)e->state);
            switch (e->state) {
            case XR_SESSION_STATE_READY:
                if (!a->session_running && a->resumed) {
                    begin_session(a);
                }
                break;
            case XR_SESSION_STATE_FOCUSED:
                apply_perf_levels(a); /* cheap re-assert */
                break;
            case XR_SESSION_STATE_STOPPING:
                end_session(a);
                break;
            case XR_SESSION_STATE_EXITING:
            case XR_SESSION_STATE_LOSS_PENDING:
                teardown_xr(a);
                request_finish(a);
                return;
            default:
                break;
            }
            break;
        }
        case XR_TYPE_EVENT_DATA_INSTANCE_LOSS_PENDING:
            LOGE("[Q3PW_IDLE] instance loss pending");
            teardown_xr(a);
            request_finish(a);
            return;
        case XR_TYPE_EVENT_DATA_DISPLAY_REFRESH_RATE_CHANGED_FB: {
            const XrEventDataDisplayRefreshRateChangedFB *e =
                (const XrEventDataDisplayRefreshRateChangedFB *)&ev;
            LOGI("[Q3PW_IDLE] display refresh rate %.0f -> %.0f", (double)e->fromDisplayRefreshRate,
                 (double)e->toDisplayRefreshRate);
            break;
        }
        default:
            break;
        }
    }
}

/* One empty frame: wait, begin, end with zero layers (compositor shows black). */
static void run_frame(App *a)
{
    XrFrameWaitInfo wi = {XR_TYPE_FRAME_WAIT_INFO};
    XrFrameState fs = {XR_TYPE_FRAME_STATE};
    XrFrameBeginInfo bi = {XR_TYPE_FRAME_BEGIN_INFO};
    XrFrameEndInfo ei = {XR_TYPE_FRAME_END_INFO};
    bool ok = xr_ok(a, xrWaitFrame(a->session, &wi, &fs), "xrWaitFrame");
    if (ok) {
        ok = xr_ok(a, xrBeginFrame(a->session, &bi), "xrBeginFrame");
    }
    if (ok) {
        ei.displayTime = fs.predictedDisplayTime;
        ei.environmentBlendMode = XR_ENVIRONMENT_BLEND_MODE_OPAQUE;
        ei.layerCount = 0;
        ei.layers = NULL;
        ok = xr_ok(a, xrEndFrame(a->session, &ei), "xrEndFrame");
    }
    if (ok) {
        a->frame_failures = 0;
    } else {
        /* never spin if the runtime keeps rejecting frames */
        a->frame_failures++;
        sleep_ms(a->frame_failures < 8 ? 2 : 20);
    }
}

/* ------------------------------------------------------- android glue */

static void on_app_cmd(struct android_app *app, int32_t cmd)
{
    App *a = (App *)app->userData;
    switch (cmd) {
    case APP_CMD_RESUME:
        a->resumed = true;
        LOGI("[Q3PW_IDLE] APP_CMD_RESUME");
        if (!a->init_attempted) {
            a->init_attempted = true;
            if (!init_xr(a)) {
                LOGE("[Q3PW_IDLE] OpenXR init failed; exiting");
                teardown_xr(a);
                request_finish(a);
            }
        }
        break;
    case APP_CMD_PAUSE:
        a->resumed = false;
        LOGI("[Q3PW_IDLE] APP_CMD_PAUSE");
        break;
    case APP_CMD_DESTROY:
        LOGI("[Q3PW_IDLE] APP_CMD_DESTROY");
        break;
    default:
        break;
    }
}

static int poll_timeout_ms(const App *a)
{
    if (a->app->destroyRequested || a->session_running) {
        return 0; /* running: xrWaitFrame paces the loop */
    }
    if (a->session != XR_NULL_HANDLE && a->resumed) {
        return 100; /* waiting for READY: XR events do not wake the looper */
    }
    return -1; /* nothing to do: block until a lifecycle command arrives */
}

void android_main(struct android_app *app)
{
    App a;
    memset(&a, 0, sizeof(a));
    a.app = app;
    a.dpy = EGL_NO_DISPLAY;
    a.ctx = EGL_NO_CONTEXT;
    a.surf = EGL_NO_SURFACE;
    app->userData = &a;
    app->onAppCmd = on_app_cmd;
    LOGI("[Q3PW_IDLE] android_main start");

    while (!app->destroyRequested) {
        int timeout = poll_timeout_ms(&a);
        int events = 0;
        struct android_poll_source *source = NULL;
        while (ALooper_pollOnce(timeout, NULL, &events, (void **)&source) >= 0) {
            if (source != NULL) {
                source->process(app, source);
            }
            source = NULL;
            if (app->destroyRequested) {
                break;
            }
            timeout = 0; /* drain whatever else is pending */
        }
        if (app->destroyRequested) {
            break;
        }
        if (a.instance != XR_NULL_HANDLE) {
            poll_xr_events(&a);
            if (a.session_running) {
                run_frame(&a);
            } else if (a.session != XR_NULL_HANDLE && a.state == XR_SESSION_STATE_READY && a.resumed) {
                begin_session(&a); /* READY arrived while paused; begin now that we resumed */
            }
        }
    }

    teardown_xr(&a);
    shutdown_egl(&a);
    request_finish(&a);
    LOGI("[Q3PW_IDLE] android_main exit");
}

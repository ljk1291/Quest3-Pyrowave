# Q3PW Idle (Quest 3 idle app)

Tiny immersive OpenXR app that shows plain black (zero composition layers, no
swapchains, no passthrough), requests 72 Hz and the lowest CPU/GPU performance
levels. Park it in front between automated tests so the headset stays cool and
low-power, and so a crashed Meta Home does not leave it in hot passthrough.

- Package `io.github.ljk1291.q3pwidle`, activity `android.app.NativeActivity`, arm64-v8a, hasCode=false
- Flow: `xrInitializeLoaderKHR` -> instance (GLES enable, optional android_create /
  FB display refresh / EXT performance settings) -> 16x16 pbuffer EGL ES3 context ->
  session -> on READY: begin, request 72 Hz, CPU+GPU `POWER_SAVINGS` -> empty frame loop
  (xrWaitFrame/BeginFrame/EndFrame, 0 layers). STOPPING ends the session;
  EXITING / LOSS_PENDING destroy it and finish the activity. The looper blocks
  (no busy-spin) whenever the session is not running.
- Marker (logcat tag `Q3PW_IDLE`):
  `[Q3PW_IDLE] session running refresh=72 perf_cpu=power_savings perf_gpu=power_savings ext_refresh=1 ext_perf=1 refresh_cur=NN`
  (`fail` / `na` replace a value that failed / whose extension is missing). Every XrResult failure is logged as `XR failure: ...`.

## Build (offline)

    powershell -NoProfile -ExecutionPolicy Bypass -File tools\quest3\idle_app\build.ps1

Output: `out\idle-app\q3pw-idle.apk` (intermediates in `out\idle-app\obj`). Uses
NDK 27.2.12479018 clang, aapt2, zipalign -p 4, apksigner from `C:\q3pw\fast\toolchain`,
JDK 17 from `JAVA_HOME`, and the prebuilt `openxr\libopenxr_loader.so`. The debug keystore
is created once at `results\local\signing\q3pw-idle-debug.keystore` (password in
`q3pw-idle-debug-password.txt` next to it; gitignored). Re-running is safe.

`include/openxr/` holds Khronos OpenXR headers (SPDX Apache-2.0 OR MIT, license headers kept).

## Device use

    adb install -r out\idle-app\q3pw-idle.apk
    adb shell am start -n io.github.ljk1291.q3pwidle/android.app.NativeActivity
    adb shell am force-stop io.github.ljk1291.q3pwidle
    adb logcat -d -s Q3PW_IDLE

Not yet verified on a device.

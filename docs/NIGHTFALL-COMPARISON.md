# Nightfall comparison — 2026-10-02

Reviewed [tB0nE/nightfall at `e111b5c0825ad27be28d6584007c60cac2b017ea`](https://github.com/tB0nE/nightfall/tree/e111b5c0825ad27be28d6584007c60cac2b017ea).
This is a source review, not a Nightfall build, installation or benchmark.
Our comparison uses the matching `f2e9df5704cc` APK/server pair and Session 05.

The wider 2026-10-02 source review rechecked Nightfall's HEAD: it remains
`e111b5c0825ad27be28d6584007c60cac2b017ea`. There is no new code delta or
equivalent Quest Godlike result to supersede this comparison. The
[combined research shortlist](DECODER-RESEARCH-2026-10-02.md) places its
asynchronous ring beside WiVRn/PyroFling, and its conversion path beside
Nova/libplacebo, with separate ownership and image-correctness experiments.

## What differs

Nightfall streams GameStream desktop/game video into an OpenXR virtual screen,
including optional stereoscopic content. Its native renderer submits quad or
cylinder layers at a configurable screen pose. That is a different product from
ALVR's head/controller-tracked PCVR transport for Metro Awakening. OpenXR use on
the headset does not itself provide a PC game's VR driver/pose return path.
See its [README](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/README.md#L7-L10)
and [layer submission](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/extensions/nightfall-xr/src/fast_xr_renderer_android.cpp#L1897-L1966).

| Area | Nightfall at reviewed commit | Our tested candidate / implication |
| --- | --- | --- |
| Decode engine | PyroWave on Vulkan; no MediaCodec PyroWave decoder | Same; no dedicated-video-engine shortcut |
| Output path | Internal R8 Y/Cb/Cr → fragment conversion → RGBA AHardwareBuffer → EGL/GLES | We already avoid the GPU→CPU→GPU pixel round trip |
| Allocation | Three AHB slots using sampled/framebuffer flags; attachment-only Vulkan output | Same minimal output concept; our additional driver-recommended usage experiment produced the measured gain |
| Scheduling | Asynchronous ready/release SYNC_FD handoff, persistent EGLImage imports, newest pending image replaces an older unconsumed image | Our measured control uses synchronous completion; a new leased-buffer design is a separate candidate |
| Wavelet path | Uses the device's fragment-path recommendation for GPU output | Our measured Haar reconstruction uses Compute; colour conversion is fragment in both |
| Precision | Requests `PYROWAVE_PRECISION=0` by default; converter has `mediump` qualifiers | Our default is precision 1, with an existing precision override. Decoder precision and converter precision must be tested separately |
| Failure behavior | CPU-readback fallback at setup; several unbounded GPU fence waits | Retain our bounded waits, fatal-decoder policy and explicit experiment activation gates |

Implementation references: [decoder initialization and precision](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/addons/nightfall-stream/src/video/pyrowave_decoder.cpp#L33-L128),
[AHB allocation](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/addons/nightfall-stream/src/video/pyrowave_gpu_pipeline.cpp#L306-L378),
[GPU submission](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/addons/nightfall-stream/src/video/pyrowave_gpu_pipeline.cpp#L625-L778),
[EGL slot ownership](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/addons/nightfall-stream/src/video/texture_uploader.cpp#L1715-L1835),
[conversion shader](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/addons/nightfall-stream/src/video/shaders/pyrowave_yuv_to_rgba.frag).

Its earlier CPU-output path still performs GPU decode followed by CPU readback
and GLES upload. The source label `SW-CPU` does not establish CPU-only wavelet
reconstruction. Its newer path's logged decode-thread cost measures CPU
recording/submission, not completed GPU work or displayed frames.

## What its evidence establishes

The [zero-copy status](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/docs/plans/active/pyrowave-zero-copy-gpu.md#L1-L16)
says implementation is complete but live stream validation is pending. It reports
a golden-frame check of eight colour patches and successful device startup.
That is useful correctness evidence, not sustained streaming performance.

Its [standalone timing](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/docs/plans/active/pyrowave-codec.md#L115-L131)
is approximately 9.9 ms for one 3840×2160 source. Our two 3072×3232 eyes total
19,857,408 pixels/frame versus 8,294,400: **2.39× as many source pixels**.
The 2560×1440 AHB probe is smaller again. Different resolution, wavelet,
precision, timing boundaries and presentation prevent inferring a comparative
speedup. The ~7% precision benefit and 0.66-vs-1.26-ms converter comparison are
source comments, not a reproduced same-profile result on this system.

Nightfall vendors PyroWave `89f7e47…` / Granite `1b2d180…`, versus our
`d2997ac…` / `842d9d5…` plus overlays. The
[PyroWave revision diff](https://github.com/Themaister/pyrowave/compare/d2997ac172bdc00e29c58e3f2938acb7e94580bf...89f7e47d4abbf650c91fae766728af866c5e32a0)
adds encoder crop/scale interop and an optional device-priority API; it does not
change decoder/wavelet implementation or packet format. Nightfall's app-owned
device path does not call that new priority API. A dependency update would still
need overlay rebasing and matching-build validation; it is not a demonstrated
decoder optimization.

## Changes to our investigation

1. Keep our measured recommended-AHB candidate as the next control. The
   off/on/off/on sequence produced **56.00 / 82.69 / 55.25 / 82.02 fresh outputs/s**,
   with enabled conversion near 1.3 ms and remaining GPU decode near 9 ms.
2. Profile dequant and individual inverse-wavelet levels; pursue final-luma
   reconstruction/conversion fusion only with exact-frame readback equivalence.
3. Add a small **converter-only relaxed-precision** experiment, preserving our
   full/limited-range behavior. This is distinct from setting all wavelet math
   to FP16. Require pixel/reference checks before a paired performance screen.
4. Keep whole-decoder FP16 opt-in: prior quality gates were not met. Nightfall's
   default/comment is insufficient reason to promote it for Haar at our size.
5. Retain a future bounded asynchronous AHB ring as a design task. Define slot
   leases, release-fence ownership, latest-frame selection, counters, timeout,
   device-loss and teardown behavior before implementation. Do not copy its
   unbounded waits or mistake submission speed for completed fresh-frame delivery.

No Nightfall code or binary is incorporated into this fork. The app's GPL-3.0
implementation is referenced for architectural comparison. Stable 90 Hz, Metro,
endurance, recovery and numerical image-quality acceptance remain incomplete.

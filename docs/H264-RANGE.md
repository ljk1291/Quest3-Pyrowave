# Stock H.264 range audit (2026-10-06)

The reported affine error is **not evidence that the owner sees the same global
contrast expansion in the headset**. The production full-range SDR hardware path
already applies its inverse before staging. The original `post_decode` dump skips
that inverse and writes expanded RGB straight into RGBA8. Thus the reported raw
27-34 dB PSNR and darker means compare different points in the colour pipeline.

There is a remaining endpoint question: if Qualcomm clamps RGB during external
sampling, production cannot recover those tails either. If sampling preserves
out-of-range floats, production corrects them before the first RGBA8 write, while
the old dump loses them. The supplied interior luma fits cannot distinguish these
cases. We have established a capture/scoring mismatch, **not established a live
crushed-black/clipped-highlight defect or proved that none exists**. No speculative
server VUI or client range override is warranted by this evidence.

## Evidence scope and source coordinates

Audit base: fork worktree `codex/h264-range`, starting at `c24a9fe`, including
`patches/frame-dump.patch`. The supplied reconstructed tree was read-only:

```text
R = C:/Users/ljk12/Documents/ChatGPT/VDXR/Quest3-Pyrowave/ws/worktrees/foveation-flash/ws/alvr
```

Below, paths beginning `alvr/` are relative to R. Its files precede frame-dump;
line numbers for server/client production evidence refer to those exact files.
Dump references use this repository's patch line numbers, so they remain available
without a dependency checkout. The owner supplied the live fit/PSNR numbers; no
private captures, live negotiated configuration, SPS, raw YUV planes, decoder
output colour metadata or in-headset observations were independently inspected.

## Server: RGB input, explicitly signalled range

| Evidence | Behaviour |
|---|---|
| `alvr/server_openvr/cpp/platform/win32/VideoEncoderNVENC.cpp:26` | SDR 8-bit input is `NV_ENC_BUFFER_FORMAT_ABGR`, not ARGB or planar YUV. HDR chooses NV12; the 10-bit branch chooses ABGR10/P010. |
| `alvr/server_openvr/cpp/platform/win32/NvEncoderD3D11.cpp:23` | ABGR maps to `DXGI_FORMAT_R8G8B8A8_UNORM` (memory RGBA); ARGB would map to B8G8R8A8. This is byte layout, not a range transform. |
| `alvr/server_openvr/cpp/platform/win32/NvEncoderD3D11.cpp:74` | Allocates those D3D textures and registers their actual pixel format with NVENC. |
| `alvr/server_openvr/cpp/platform/win32/VideoEncoderNVENC.cpp:134` | `CopyResource` copies the rendered input to NVENC's registered RGB texture; `EncodeFrame` follows. No explicit RGB-to-YUV conversion here. |
| `alvr/server_openvr/cpp/platform/win32/VideoEncoderNVENC.cpp:297` | H.264 VUI signal-type-present=1, video-format=unspecified, `videoFullRangeFlag = m_useFullRangeEncoding ? 1 : 0`, colour-description-present=1. |
| `alvr/server_openvr/cpp/platform/win32/VideoEncoderNVENC.cpp:308` | SDR VUI primaries=BT.709, transfer=sRGB, matrix=BT.709. HDR branch uses BT.2020/NCL with sRGB transfer. P7 does not change these fields. |
| `alvr/server_openvr/cpp/alvr_server/nvEncodeAPI.h:1581` | Header describes the range flag as output luma/chroma sample range and the colour matrix as deriving Y/C from RGB. |
| `alvr/server_core/src/connection.rs:773`, `:894` | Negotiated range comes from the server override or client preference and is passed to OpenVR settings. |
| `alvr/session/src/settings.rs:1971`, `alvr/client_openxr/src/lib.rs:449` | Baseline defaults override to full range; client also prefers full range. |

Consequently **the default bitstream is configured to say full range**, not limited
range. A session override can change that; confirm the cell's
`[Q3PW_COLOUR] codec=H264 full_range=true hdr=false legacy_range_remap=true`
and actual SPS before making a statement about that particular bitstream.
The source specifies signalled BT.709/sRGB; it does not expose NVENC's proprietary
RGB conversion arithmetic. Full-range RGB input alone does not prove the coded
YUV sample range or matrix. NVIDIA documents RGB inputs and internal conversion
in its [NVENC programming guide](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvenc-video-encoder-api-prog-guide/index.html).
A full-to-limited RGB/YUV conversion followed by a correct limited-to-full decode would
cancel, rather than produce the owner's extra expansion. The observed fit is
consistent with an extra expansion somewhere between the RGB input and external
RGB view; it cannot isolate encoder conversion, decoder metadata or EGL handling.

`FrameRender.cpp:121` creates the SDR composition texture as R8G8B8A8_UNORM_SRGB.
Optional colour correction (`:452`) and FFE packing operate in RGB. The YUV pass
is created/run only for HDR (`:505`, `:1119`); the planar pass is explicitly
`PyroWaveEnabled() && !m_enableHdr` (`:606`, `:1123`). Stock SDR H.264 therefore
has **no application RGB-to-YUV range/matrix pass before NVENC**. Its dump occurs
immediately before `Transmit` ([frame-dump.patch:551](../patches/frame-dump.patch#L551)).

## Client: same external conversion, different shader after sampling

| Evidence | Behaviour |
|---|---|
| `alvr/client_core/src/video_decoder/android.rs:185` | MediaCodec is configured to the ImageReader's native window. |
| `alvr/client_core/src/video_decoder/android.rs:259` | MediaFormat supplies MIME, dimensions and CSD. The options loop (`:273`) can set arbitrary configured properties, but there is no hardcoded `color-range`/`color-standard` override. |
| `alvr/client_core/src/video_decoder/android.rs:405` | PRIVATE ImageReader output with GPU_SAMPLED_IMAGE usage, not CPU-visible planar YUV. |
| `alvr/client_core/src/video_decoder/android.rs:120` | Selected Image's `hardware_buffer()` yields the leased AHardwareBuffer pointer passed to graphics. |
| `alvr/graphics/src/lib.rs:253` | WGPU backend is GL; H.264 does not use Vulkan sampler YCbCr conversion. |
| `alvr/graphics/src/lib.rs:34`, `:406` | AHB -> native client buffer -> EGL_NATIVE_BUFFER_ANDROID EGLImage -> GL_TEXTURE_EXTERNAL_OES. Attributes are null by default or only EGL_IMAGE_PRESERVED_KHR=true. |
| `alvr/graphics/src/staging.rs:129`, `:164` | Production binds the external image and copies its two eyes with the staging shader. |
| `alvr/graphics/resources/staging_fragment.glsl:17` | Samples `samplerExternalOES`, then, when FIX_LIMITED_RANGE is enabled, computes `16/255 + (219/255)*color`. The earlier "limited to full" comment is misleading: the arithmetic is a contraction, the inverse of the measured expansion. |
| `alvr/client_openxr/src/stream.rs:59`, `:135`, `:229` | Enables that remap for hardware codecs when negotiated full-range and SDR; excludes PyroWave. Logs the effective policy and passes it to StreamRenderer. |
| `alvr/graphics/src/stream.rs:319` | Passes the same remap boolean to StagingRenderer. |
| [frame-dump.patch:51](../patches/frame-dump.patch#L51), [:279](../patches/frame-dump.patch#L279), [:308](../patches/frame-dump.patch#L308) | Old dump also uses samplerExternalOES and EGL_NATIVE_BUFFER_ANDROID, with preservation=true; it uses nearest native-texel sampling into RGBA8 and **no inverse range remap**. |

Neither import sets EGL_YUV_COLOR_SPACE_HINT_EXT or EGL_SAMPLE_RANGE_HINT_EXT.
These are Linux dma-buf import attributes, not a portable Android AHB range fix:
[EGL_ANDROID_image_native_buffer](https://registry.khronos.org/EGL/extensions/ANDROID/EGL_ANDROID_image_native_buffer.txt)
ignores attributes other than image preservation for this target;
[EGL_EXT_image_dma_buf_import](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_image_dma_buf_import.txt)
defines those hints for its separate target. No H.264 `VkSamplerYcbcrConversion`,
`ycbcrRange` or `ycbcrModel` exists in the audited client path. PyroWave's separate
Vulkan decoder is not the stock H.264 conversion path.

The external YUV-to-RGB conversion mechanism is shared. Its parameters come from the
EGLImage/implementation, per [OES_EGL_image_external](https://registry.khronos.org/OpenGL/extensions/OES/OES_EGL_image_external.txt).
The dump's preservation flag changes content-lifetime semantics, not an explicit
range setting. Production and dump are **not the same complete colour pipeline**:
production remaps before storing; dump stores before remapping. Different filtering
and eye reconstruction also prevent interpreting a native packed dump as final eyes.

## Compensation and clipping order

For an unclipped channel x, let external sampling produce
`e = (x - 16) * 255 / 219`. Production's inverse gives
`16 + e * 219/255 = x`. This directly explains why the fitted 1.14-1.166 slope
and -16.9 to -19.1 intercept in raw dumps do not establish displayed contrast error.

Old RGBA8 readback instead stores `clamp(e, 0, 255)` (rounded). Applying the inverse
afterward limits recoverable channels to 16-235. It cannot recover source values
below 16 or above 235. **This can be dump-only clipping**: production performs
its arithmetic while the sampled value is still floating point. The API and CPU
source audit do not establish whether this device's external sampler preserves
those excursions or already clips them. If it already clips, production has a
real tail-information loss, generally raised black/lowered white endpoints after
the inverse rather than the entire raw expanded image reaching the eyes.

Later stages do not add another range inverse. `stream.wgsl:149` applies piecewise
sRGB-to-linear conversion; `:156` applies negotiated encoding gamma. Default
encoding gamma is 1 (`client_openxr/src/lib.rs:450`, `session/src/settings.rs:1973`).
These are transfer functions, not restoration of clipped samples. FFE/upscaling
sample spatially. Layer filtering is passed to the OpenXR projection layer
(`client_openxr/src/stream.rs:716`); sharpen/supersample flags affect presentation,
not coded range and cannot reconstruct lost endpoint distinctions. Server colour
correction precedes the encoder-input dump (`FrameRender.cpp:1111`), so it cannot
explain an additional post-dump affine error.

## Implemented capture/scorer correction

`patches/frame-dump-range.patch` is an additive overlay immediately after
`frame-dump.patch`, SHA-256 pinned in `sources.lock.json` and checked by the fetcher.
It changes capture only; normal rendering, encoder flags, defaults, protocol and
upstream credits remain as before. Capture itself remains default-off.

The renderer's existing `fix_limited_range` boolean is passed into the dump shader.
The shader applies **the production inverse before the RGBA8 target clips or
quantizes**. The init marker is:

```text
[Q3PW_FRAME_DUMP_RANGE] legacy_range_remap=true before_rgba8=true
```

The sidecar adds boolean `legacy_range_remap`: true for remapped `post_decode`,
false for unremapped decoder output and presented-eye records. Missing fields in
old sidecars mean false. The new dump is still packed and before gamma/FFE
reconstruction, but has the production range correction. PyroWave retains its
unremapped full-range RGB capture. No generic range guessing or fitted correction
is added to scoring; newly remapped captures are scored as stored, and attempting
to remap them again fails.

For **old** stock full-range SDR captures whose Q3PW_COLOUR marker confirms the
legacy policy, an explicit CPU approximation is available:

```powershell
python tools/quest3/frame_score.py score --server <source-run> --client <client-run> --decode-range-remap legacy-full-range --out results/local/range-score.json
```

This applies per-channel `round(16 + RGB*219/255)` before luma, retains raw full-frame
PSNR/SSIM/blank diagnostics in `raw_post_decode`, and reports luma endpoint counts
in `range_endpoints_luma`. It approximates an RGBA8 readback after correction;
it cannot undo the old dump's earlier quantization/clipping and is not a final-eye
score. Production can use sRGB staging (graphics/src/lib.rs:101); its transfer
and quantization are not modelled by this CPU option. Endpoint counts are evidence
for neutral ramps, not a colour-channel clipping verdict. Use neither this option nor a fitted affine normalization for PyroWave,
limited-range, HDR or already corrected captures. Raw scoring remains the default.

## Validation and next evidence

Local results: **20 scorer tests and 14 source-lock checks passed**:

```text
benchmark-env/Scripts/python.exe -m unittest tests.test_frame_score -q
validation-env/Scripts/python.exe -m pytest tools/tests/test_ci_pins.py -q
git diff --check
```

Local CPU checks cover inverse cancellation on 16-235, unrecoverable clipping on
a 0-255 ramp, per-channel rounding, invalid domain/metadata rejection, prevention
of double remapping, raw-metric retention and CLI/report compatibility. Source-lock
checks cover the overlay hash, placement and renderer-policy wiring. The overlay
applies forward to the post-frame-dump generation base and reverse-checks against
its result; all three changed source files match the generation tree byte-for-byte.
No shader binary needs regeneration: these GLES shaders compile at runtime.
The existing Actions software-GLES capture/state-restoration test is extended with
remap-on/off cases; native execution and the Android build remain unrun locally.

To close the live endpoint question, use a separately authorized chart cell with
known neutral/RGB ramps through both tails, record negotiated Q3PW_COLOUR and the
actual SPS range/matrix, then compare encoder input with the new remapped packed
dump and the gamma-adjusted presented eyes. An offline decode of the exact bitstream
with explicit full/limited interpretations would isolate coded YUV from Android
external conversion. The owner must judge the ramp in-headset before claiming a
visible fix. Do not change VUI from full to "full" again or add ignored EGL hints.

No hardware, settings changes, installation, live benchmarks or heavy local builds
were performed. Runtime rate acceptance, standalone decode-budget compliance and
sustained live-VR rate are **all unverified by this audit**. No commits were made.

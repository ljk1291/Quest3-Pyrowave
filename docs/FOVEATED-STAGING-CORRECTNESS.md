# Foveated presentation correctness investigation

The installed `0f07f05` pair produced black/flashing with cropped Medium CDF
9/7 at 1000 Mbps. Session 22 contained stale raw client geometry. Session 23
corrected the raw fields and **still failed**. Its retained native log confirms
4224×2208 decoded RGBA, Compute CDF 9/7, the faster AHardwareBuffer allocation
and minimal fragment conversion usage. No image-quality or stable-rate pass
follows from that log. The source sends foveated frames through staging;
requesting direct eye copy does not activate it for these frames.

This additive overlay is stacked after `552ffbb` (corrected RDO pair plus opt-in
NVENC dimension preflight). It retains ALVR `7eda092dbf0002281410a4222683ec228700cffb`,
PyroWave `d2997ac172bdc00e29c58e3f2938acb7e94580bf`, Granite revisions, protocol,
signing identity and baseline defaults. No install is performed.

## Confirmed fixes

- `alvr/session/src/settings.rs`: one shared `resolved_geometry()` for fixed
  Light, Medium and H264Fit profiles. Server native configuration and OpenXR
  inverse mapping call it. Persisted raw Custom fields stay unchanged.
- `alvr/client_openxr/src/stream.rs`: blur-only filtering does not run an inverse
  squeeze on a full-size bitstream. Blur-only remains excluded from our test plan.
- `alvr/graphics/resources/staging_fragment.glsl`: declare float/external-sampler
  precision explicitly. Strict GLSL ES compilation rejected the inherited shader
  before any pixel check. This is a portability fix, not proof of the Quest cause.
- Matching-build provenance pins this exact ALVR-only overlay. Historical HVS
  compatibility names its restricted role; scorer and PyroWave source remain unchanged.

## Candidate requiring a Quest check

`debug.q3pw.staging_init=1` opts PyroWave into a once-per-renderer WGPU-tracked
partial texture write, submission and completion **before** the first external
copy. Raw GLES writes do not update WGPU's initialization tracker. Its first
sampling can clear an apparently uninitialized texture after that raw copy.
The software test previously returned black at its first pixel; the new control
checks the staging pixel before and after sampling to establish that mechanism.
It separately checks the next changing frame and the initialization-on first
frame. The native marker is `[Q3PW_STAGING_INIT] requested/effective/initialized`.
It is default-off and independent of state isolation. No per-frame CPU image
upload is added. The pinned WGPU source is
[texture memory initialization](https://github.com/gfx-rs/wgpu/blob/v24.0.0/wgpu-core/src/command/memory_init.rs).
Even a confirmed software first-frame clear cannot explain persistent Quest
flashing by itself. The new regression and signed pair must pass before use.

`debug.q3pw.staging_isolation=1` enables a PyroWave-only copy with its own VAO,
explicit depth/blend/cull/raster-discard/mask/sampler state and a framebuffer
completeness check. The existing import, synchronous completion and decoder
buffer lease are retained. It logs `[Q3PW_STAGING]` with effective state and
copy dimensions. It is **default-off**. Foreign GL state is a hypothesis,
not a proven cause of session 23's failure. WGPU 24's GLES queue explicitly
resets several states before submission, so a general WGPU cache-corruption
claim is unsupported by the source review.

## Regression and morning gate

The Linux software test uses real Mesa GLES with a CPU adapter, the actual
Rust staging draw, actual WGSL
inverse mapping and actual projection transform. An owned GL texture becomes
an EGLImage source. It checks every output pixel for both eyes for all three
fixed profiles and both output formats, with initialization and isolation off
and on across two changing frames. Initialization-off's first black frame is
an explicit bug-reproduction control, **not a correctness pass**; its next frame
and initialization-on's first and second frames must match the source colours.
The isolation-on case injects hostile blend,
cull and color-mask state. It does not exercise Android AHB import, Qualcomm's
driver or OpenXR presentation. Its adapter/API identity is logged; a CPU renderer
and an actual OpenGL ES version string are mandatory. wgpu24 prefers desktop GL
if EGL advertises both APIs, so a CI-only EGL wrapper advertises just Mesa's
supported GLES API. All other entry points, errors and pixels remain real Mesa;
the wrapper is neither linked into nor shipped with either installable build.
It is not a Qualcomm GLES performance result. Native Rust
tests also preserve Custom geometry
and reproduce the stale raw fields from the failed session.

Before Metro or timing: independently verify a matching pair, obtain installation
authorization, then run a finite supervised chart at a conservative diagnostic
rate (500 Mbps or lower). The stationary Q4 continuation does not qualify nominal
1000 Mbps. Compare initialization off/on first, then isolate GL state as a
separate change, with native markers and decoded/staging
dimensions; ask the owner about labels, orientation, colours, moving content
and corruption. Stop immediately on black/flashing. No optimization is promoted
until this gate passes, followed by controlled timing and quality checks.

ALVR's upstream MIT attribution is retained. The new resolver, tests and
experimental state-isolation code are this fork's changes.

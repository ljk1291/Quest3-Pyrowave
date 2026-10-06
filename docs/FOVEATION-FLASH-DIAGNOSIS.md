# Session 25 foveated-encoding flashing diagnosis

2026-10-06; branch `codex/foveation-flash`, baseline `c7513be`. Source and
offline investigation only. ALVR, PyroWave and JMS1717 upstream credits remain.

## Finding and confidence

**Confirmed server defect: WO-8 changed the compression pixel shader to the
wrong vertex/pixel interface.** Its embedded DXBC consumes `TEXCOORD0` from
register 1; the production fullscreen vertex shader exports it in register 0.
All three flashing cells execute this pair, before either encoder. Clean
non-foveated cells bypass it. The overlay in this change restores the matching
interface and regenerates the embedded DXBC.

This is the leading explanation for the black flashes, supported by the live
bisect, almost constant/tiny encoded payloads, and an offline reproduction of
incorrect sampling. **The precise temporal black-flash symptom is not yet
reproduced or verified fixed on the owner's GPU/headset.** Software WARP
reproduces wrong-eye sampling, not black flashes. Do not treat the patch as a
live acceptance result or assume a particular flash period from these logs.

## Source evidence

Paths below beginning `alvr/` refer to the reconstructed locked ALVR tree,
including all overlays through `direct-eye-foveation.patch`, before this fix.
The local working reconstruction is `ws/alvr/`; the earlier read-only T1 tree
has identical fullscreen VS and compression PS binaries. Line references for
unmodified files also apply to the final reconstruction.

* `patches/wo8-foveation.patch:211` introduces `FoveationPixelInput`, ordered
  `SV_POSITION`, `TEXCOORD0`, `VIEW`. The comment incorrectly identifies the
  layer-compositor interface as this pass's interface. The later Light phase
  patch recompiles that same incorrect interface.
* `alvr/server_openvr/cpp/platform/win32/FFR.cpp:145` loads
  `QUAD_SHADER_CSO_PTR`; line 163 passes that vertex shader and
  `CompressAxisAlignedPixelShader.cso` to `RenderPipeline::Initialize`.
  This is **not** `FrameRender`'s layer vertex shader.
* `alvr/server_openvr/cpp/platform/win32/d3d-render-utils/QuadVertexShader.hlsl:1`
  declares `TEXCOORD0` first, then `SV_Position`. Its comment explicitly says
  UV must be first when the pixel shader does not declare position.
* `alvr/server_openvr/cpp/platform/win32/d3d-render-utils/RenderPipeline.cpp:100`
  sets a viewport covering the output texture; lines 114–118 bind the pair and
  draw one four-vertex fullscreen strip. Both eyes are in this one draw.
* `alvr/server_openvr/cpp/platform/win32/FrameRender.cpp:500` initializes FFR;
  line 502 selects its output for subsequent processing; line 1116 runs it.
  Both NVENC and the PyroWave planar conversion consume this result.

Disassembly of the **embedded binaries**, using the recorded SDK FXC
`/dumpbin`, confirms this is not merely a source annotation mismatch:

| Binary | Semantic | Register | Instruction |
|---|---|---|---|
| Production `QuadVertexShader.cso` output | TEXCOORD0 | 0 | `dcl_output o0.xy` |
| Production `QuadVertexShader.cso` output | SV_Position | 1 | `dcl_output_siv o1.xyzw, position` |
| Before-fix compression PS input | TEXCOORD0 | 1 | `dcl_input_ps linear v1.xy` |
| Fixed compression PS input | TEXCOORD0 | 0 | `dcl_input_ps linear v0.xy` |

The compression arithmetic needs normalized stereo UVs. Invalid linkage can
instead feed the wrong coordinate data to eye selection, mapping, derivatives
and the source-pixel box. Clamping source samples cannot repair the wrong
coordinate system. There is no justified driver-independent prediction of the
resulting temporal behavior.

The old software gate concealed this: at baseline,
`tools/ci/quality_shaders_test.cpp:48` synthesizes a layer-style vertex shader
with position first and UV second, matching the broken pixel shader. Its
foveation tests additionally drew eyes separately, unlike production FFR.
The gate now loads the actual embedded `QuadVertexShader.cso` and draws a full
stereo output, checking every pixel including aligned padding and the seam.

## Session evidence and timing

Evidence remains read-only in the main checkout's
`results/local/session-25/`. Nothing here copies private captures or session
configuration into version control. Log references use original 1-based lines;
timestamps below are the logcat epoch-second values.

The owner's bisect is decisive about the shared *feature*: full-FOV Haar and
crop-only Haar were clean; Medium CDF 9/7 direct-eye FFE flashed with and
without crop; H264Fit using the stock hardware decoder/client expansion also
flashed. The first-connect restart occurred in clean cells too.

Actual activation is visible after reconnect:

* `t1-on-black-flash-logcat.txt:27097`, `1791309895.235`:
  `[Q3PW_DIRECT_FFE] requested=true effective=true profile=Medium
  packed_eye=2112x2208 expanded_eye=2624x2752 reason=eligible`.
  Line 27152, `1791309895.525`: `path=direct_eye_ffe rendered=true`.
* `diag-fov-only-black-flash-logcat.txt:25965`, `1791310897.673`:
  the same effective Medium path, `packed_eye=2464x2592`,
  `expanded_eye=3072x3232`. Line 26027, `1791310897.978`:
  `path=direct_eye_ffe rendered=true`.

Those sizes agree with server/client alignment math: cropped Medium stereo
4224x2208; uncropped Medium 4928x2592; cropped H264Fit 3968x2080.
The harness's `decoded_stereo` field hardcodes cropped Medium even for
`diag-fov-only`; the actual uncropped marker is authoritative. This metadata
mistake does not set the shader geometry (`ws/session25.py:profile`).

Per-cell `report.json` and all `GraphStatistics` records in the corresponding
`events.jsonl` show an unusually small, almost invariant encoder output:

| Capture directory prefix / cell | Frames | Median video Mbps | Packet bytes (all observed records) |
|---|---:|---:|---|
| `1791309913582798100-t1-on-capture` | 1555 | 18.390 | **25352 for all 1555** |
| `1791310910811080400-diag-fov-only-capture` | 1142 | 25.773 | **35508 for all 1142** |
| `1791310626791843800-h264-chart-capture` | 2383 | 23.510 | 13 (1095), 68524 (955), 68533 (171), 32249 (162) |
| `1791309614406424900-sanity-capture` | 2312 | 504.136 | clean owner judgement |
| `1791310761253762600-diag-crop-only-capture` | 1701 | 504.053 | clean owner judgement |

For example, T1 capture `events.jsonl:1` has `video_packet_bytes:25352`
and `requested_bitrate_bps:500000000.0`; uncropped capture line 1 has 35508.
Identical intra-frame PyroWave sizes across moving chart frames suggest
constant/low-information encoder input, rather than solely a bad client inverse.
Packet lengths alone do not prove black pixel values; no encoded-pixel capture
was supplied for these cells.

Timing scan: T1 `[1791309900,1791309993)`, H.264
`[1791310618,1791310681)`, uncropped `[1791310902,1791310948)`.

* `[Q3PW_EFFECTIVE] requested=Some(90.0) runtime_hz=Ok(90.0)` repeats
  92/40/46 times, median intervals 1.002/1.006/1.013 seconds. Although logged
  at `E`, this is a status marker, not a recurring decoder failure. Examples:
  T1 line 27383, H.264 line 23037, uncropped line 26363.
* H.264 alone emits 3201 `Video playback content time jumped` warnings and
  2711 `Rendered frame is earlier` warnings, median intervals 13/15 ms.
  `h264-chart-black-flash-logcat.txt:22876` at `1791310639.514` reports an
  11091-ms content jump; the preceding rendered-frame record is at
  `1791310639.498`, line 22875. These are not 11-second wall-clock stalls.
  `alvr/client_core/src/video_decoder/android.rs:67–70` explicitly puts
  nanoseconds into MediaCodec's microsecond field to preserve timestamp
  identity, explaining the roughly 1000x content-time scale. This is a
  separate telemetry quirk, absent from both flashing PyroWave cells.
* Runtime `VrApi` summaries repeat about once per second and contain stale
  frames (T1 line 27358: 78/90, Stale=12; uncropped line 26361: 57/90,
  Stale=33). They show missed freshness, not which pixels were black.
* Tracking `Images too dark` repeats about every 3.07 seconds in the PyroWave
  dumps (T1 line 27374; uncropped line 26414). Camera/tracking warnings and
  shell `MessageExecutionMonitor` warnings are not ALVR encoder errors.
* The post-start ALVR-tagged records contain rate/capability markers, without
  repeating decoder failure or presentation-path toggles. No per-flash owner
  timestamps or per-frame pixel measurements exist in these dumps, so none of
  these periodic messages can be positively correlated with a flash cadence.

`C:/Program Files (x86)/Steam/logs/vrserver.txt` had already rolled into later
20:31/20:32 runs while this read-only investigation was underway. It cannot
establish the D3D debug messages or applied constants for the earlier flashing
cells. Absence of an error there is not exculpatory evidence.

## Alternatives checked

* **Buffer layout/softness NaN:** the compiled reflection places target size at
  byte 0, eye ratio 16, center size 24, shifts 32/40, edge ratio 48, softness
  56, blur-only 60. `FFR.cpp:14–40` matches and is 64 bytes. Softness 0.5 is
  finite and validated in `connection.rs:158`; the fixed profiles' zero shifts
  and nonempty edges avoid singular joins. No mismatch was found for the
  tested profiles. Arbitrary Custom singularities are outside this diagnosis.
* **Unwritten output/partial viewport:** the output is allocated without initial
  pixels (`FFR.cpp:149`) and relies on a valid full-coverage draw. The viewport
  and strip are correct; invalid shader linkage is a concrete defect in that
  draw. Adding a clear would conceal bad pixels without restoring the image.
* **Render/copy race:** the FFR draw precedes planar conversion and context
  flush (`FrameRender.cpp:1116–1133`). NVENC copies on that same context before
  encoding (`VideoEncoderNVENC.cpp:138–145`). PyroWave explicitly signals,
  flushes and waits for a render fence (`VideoEncoderPyroWave.cpp:467–491`).
  No foveation-specific missing synchronization was identified; adding waits
  is not supported by current evidence.
* **Restart/configuration mismatch:** named profiles resolve fixed geometry on
  server (`connection.rs:143`) and client (`client_openxr/src/stream.rs:76–79`).
  Negotiation gates the inverse; blur-only suppresses it. The observed packed
  dimensions agree with the corresponding server math. Fixed profiles disable
  gaze (`session/src/settings.rs:595`), and the current effective server policy
  also disables it. A periodically changing center is not indicated.
* **Client sampling/staging:** stock WGSL and T1 share the inverse constants
  (`graphics/src/stream.rs:710`), but have distinct presentation paths. The
  direct-eye markers above defeat a staging-only explanation. The focused
  CPU mapping/seam/phase tests pass; no client edit is warranted by this evidence.

## Fix and validation

`patches/foveation-shader-linkage.patch` is an additive, server-only overlay
after the existing stack. It changes only the compression PS input declaration
and its compiled binary. FFR remains opt-in/default-off. Mapping, softness,
client code, codec settings and protocol are unchanged. This is a pure bug fix,
so there is no additional runtime switch or activation marker.

Embedded compression PS SHA-256:

* Before: `2e04b750e610969072a08918f231eaf0c3c2be6113e370e8e03715ecfc74c200`
* Fixed: `3c2b03c4defd53b5854b9c94b3fdf3911c169341c4c3ca40f59d2b76329bae08`

Validation performed locally:

1. Reconstructed upstream `7eda092` from local Git objects, applied every
   locked ALVR overlay in CI order, and regenerated the patch with
   `git diff --binary --full-index` against an index holding the prior stack.
   Reverse/forward application checks pass; the patch includes the CSO.
2. Recorded SDK `10.0.26100.0` FXC (`/nologo /O3 /T ps_5_0 /E main`)
   regenerates the fixed binary exactly. Existing composition shader hashes
   and legacy defaults pass `check_quality_shaders.py` unchanged.
3. `check_foveation_linkage.py` rejects the original real DXBC pair and accepts
   the fixed pair without a device or SDK. It now runs in the CPU CI job and
   before the Windows shader/readback gate.
4. A tiny local ctypes D3D11 probe explicitly selected **WARP**, never a hardware
   adapter. Production VS + old/new PS, reduced Medium geometry (512x256 input,
   448x224 output), left 0.25/right 0.75, and sentinel-cleared output:
   before **75264/100352** pixels belong to the correct eye; fixed
   **100352/100352**. Neither version produced black in this software test.
   Temporary harness: ignored `ws/warp_probe.py`. The committed C++ WARP gate
   now uses this production pair and full-stereo assertion too.
5. 12 pin/CI-contract tests pass (`tools/tests/test_ci_pins.py`); 24 focused
   foveation/reference and T1 contract tests pass. `git diff --check` passes.

The updated C++ WARP fixture and full native pair build still need GitHub
Actions (no local C++ toolchain; no workflow dispatch or commit here). Runtime
90 Hz was accepted in the historical logs. Standalone decode-budget acceptance
is not measured here. Sustained live 90 Hz and a flashing-free image with this
fix are unverified.

Changed files (all left uncommitted):

* `docs/FOVEATION-FLASH-DIAGNOSIS.md`
* `patches/foveation-shader-linkage.patch`
* `patches/README.md`
* `sources.lock.json`
* `.github/workflows/ci.yml`
* `tools/ci/check_foveation_linkage.py`
* `tools/ci/check_quality_shaders.py`
* `tools/ci/fetch_sources.sh`
* `tools/ci/quality_shaders_test.cpp`
* `tools/ci/source_lock.py`
* `tools/tests/test_ci_pins.py`
* `tools/windows/check_quality_shaders.cmd`

## Remaining short hardware cells (not run)

First replay the original T1 and H264Fit chart profiles on the rebuilt pair,
with a clean crop-only reference. If flashing remains, use these three
settings-only diagnostic cells, 10–15 seconds each on the same chart, with
an owner timestamp for each flash. They can derive from `profile('t1-on')` in
the existing harness. Keep codec, crop, RDO, bitrate and client properties fixed.
Update both `session_settings.video.foveated_encoding.content.*` and matching
`openvr_config.foveation_*` readbacks, as that harness does.

| Cell | Changes from T1 | Discriminates |
|---|---|---|
| Medium, zero softness | `peripheral_softness=0` (both configs) | Softness multiplier versus base warp/area pass; zero still runs the area prefilter. |
| Medium, blur-only | `blur_only=true` (both configs) | Keeps server shader/filter but bypasses packing and client inverse. Use PyroWave, with full cropped stereo 5248x2752; do not use this width for H.264. T1 FFE is expected ineligible. |
| Light | profile `Light`, center sizes 0.8, edge ratios 1.5, shifts 0; softness 0.5, blur-only false | Ratio/profile-dependent mapping and packing versus a profile-independent pass defect. Cropped stereo 4928x2592. |

Adjust expected packed geometry in the harness for each cell. A fully upstream
ALVR compression shader is **not** selectable through these settings: that
comparison requires a separately rebuilt shader overlay. These cells are
experiments, not approved defaults or evidence of live performance.

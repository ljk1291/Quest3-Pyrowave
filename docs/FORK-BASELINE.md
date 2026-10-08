# Fork baseline keepers on upstream .65

Port base: Quest3-Pyrowave `18d43ce` (upstream `.65`), reconstructed ALVR `26aa7c0`
(tag `upstream-18d43ce`, ALVR `7eda092` plus upstream patches/copied helpers).
This port carries only the audited baseline keepers. It does not change selection policy,
queue depth, decode kernels, transport, foveation, downsample filters, or encoder timeouts.

## Fresh-output telemetry

The existing fork harness names are restored:

- `HeadsetTelemetry.selected_output_submissions`: cumulative `u64`, reset on decoder creation.
- `HeadsetTelemetry.selected_output_submission_source`:
  `selected_nonnull_post_render_release_v1`.
- The fork bench derives `fresh_selected_output_rate_fps` from counter deltas divided by
  telemetry capture elapsed time. Reject windows spanning a reset or missing coverage.

`VideoDecoderSource::get_frame()` gives each successful source dequeue a strictly increasing
`SelectedFrame.selection_id`. Tracking timestamps and AHardwareBuffer addresses may repeat;
neither is used as identity. The wrapper covers MediaCodec, main PyroWave and legacy PyroWaveUdp.
A held/pre-wait frame carries that same identity into `StreamContext::render`. Count once only
after a non-null source was passed to the renderer and both OpenXR eye images were successfully
released. Empty polls, repeats, forced redraws from a retained image, rejected ready-FD waits,
and selected frames discarded before rendering do not count. Decoder replacement clears the
pending frame before resetting identities/counters. The C API still returns timestamp/buffer
with the same ABI; it does not report OpenXR post-release submissions itself.

This is the original **submission proxy**, not GPU-completion, successful `xrEndFrame`, optical
scanout, or proof of distinct pixel content. Renderer errors/internal fallbacks are not a new
pixel-validity acknowledgement. `completed_eye_copies` remains a separate upstream metric.

**Can `[Q3PW_FRESH] taken=` replace it? Not under the same contract.** `FrameSlot::take()`
increments `taken` immediately when leasing a pending or eligible held frame, before ready-FD
validation, rendering, and eye release. Consequently, pre-wait selections can enter an earlier
window; selections later rejected or discarded still count there. With ordinary successful
one-dequeue/one-render operation and aligned windows the totals should agree apart from boundary
skew. Neither proves physical display. The probe resets its interval counters when read and logs
about once per second only with `debug.q3pw.fresh_probe=1` on Quest 3. It is exposed through
`SourceInner::PyroWave` (including `.65` server-sliced UDP using the main decoder), not through
MediaCodec or the legacy `SourceInner::PyroWaveUdp`. The restored counter is always available
without that property and covers all three source variants through the OpenXR loop.

Upstream references: [FRESHNESS.md](FRESHNESS.md), [FRAME-TRACE.md](FRAME-TRACE.md),
`video_decoder/mod.rs` (`FrameSlot::take`, frame hold), `ready_frames.rs` (FD ownership), and
`client_openxr/src/latest_wait.rs` (bounded selection wait). No changes to those scheduling/FD
helpers. A later FIFO overlay must preserve `SelectedFrame` through pre-wait and keep the
post-release hook; never count enqueue, repeat, or rejection as output submission.

## PyroWave colour range

The `d1c3b3d` presentation fix is ON by default for the effective PyroWave encoder.
Set **`ALVR_Q3PW_PYROWAVE_FULL_RANGE=0` in the streamer/vrserver environment before launch**
to opt out. Only exact `0` disables it; unset, empty, `1`, and other values keep it on.
Restart the streamer/SteamVR and reconnect for an A/B arm; this is not a live environment control.
`beta::pyrowave_full_range` uses upstream's effective encoder selection, including
`ALVR_PYROWAVE`, and the server negotiates the resulting `pyrowave_full_range` boolean.
Hardware codecs always negotiate false and preserve their old SDR/HDR policy.

At successful PyroWave encoder creation, `VideoEncoderPyroWave::Initialize` logs one line via
`Warn` (ALVR warning and SteamVR driver log): **`[Q3PW_RANGE] full_range=1`** or
**`[Q3PW_RANGE] full_range=0`**. This describes the display fix, not coded YCbCr range.
The client logs `[Q3PW_COLOUR] pyrowave_full_range=... full_range=... hdr=...
legacy_range_remap=...` at `error!` so the connected-client log filter retains it.
Here `full_range` is the pre-existing negotiated coded-range value; the other boolean is the fix.

The exact affected rendering path is the `fix_limited_range` argument to `StreamRenderer::new`:

- With the effective bypass true, it is false. Otherwise retain `use_full_range && !enable_hdr`.
- `alvr/graphics/resources/staging_fragment.glsl`: `FIX_LIMITED_RANGE` is no longer defined
  for fixed PyroWave, bypassing `16/255 + (235/255 - 16/255) * color`.
- `alvr/graphics/resources/direct_eye_fragment.glsl`: the `fix_limited_range` uniform is zero,
  bypassing `16/255 + 219/255 * color` for both ordinary RGBA and packed-YCbCr programs.

No shader source/constants, `.cso`, native convert SPIR-V, PC `RgbToYuvPlanar` coefficients,
BT.709 matrix, sRGB/gamma policy, encoded-range setting, or decoder-config byte 9 changes.
`tools/pyroclient/convert.frag` already expands limited coded YCbCr to full RGB;
`present_ycbcr.glsl` already returns full RGB for supported packed frames. Applying the extra
client remap lifts black and compresses white. The opt-out restores upstream's condition; it
does not force a remap when coded range/HDR already made that condition false.

**A matching client APK is required**: it receives the negotiated flag and disables the remap.
No client property or native decoder modification is required. Missing negotiated flags default
to bypass for a saved PyroWave codec and legacy policy for hardware codecs; malformed flags
reject setup. See [PRESENT-YCBCR.md](PRESENT-YCBCR.md) and [CHROMA.md](CHROMA.md).

## FOV crop

Ported from `a667c70`, including `dcb4d66` fail-closed parsing and `c6f02d3` visibility coverage.
Default OFF, both multipliers `1.0`. Harness/session names are unchanged (relative to
`session_settings`):

| Setting | Values |
| --- | --- |
| `video.fov_crop.enabled` | false by default; true enables crop |
| `video.fov_crop.content.horizontal_tangent_multiplier` | finite 0.5-1.0; candidate 0.854 |
| `video.fov_crop.content.vertical_tangent_multiplier` | finite 0.5-1.0; candidate 0.850 |

There is **no Android property** for FOV crop. Typed settings use `Switch<FovCropConfig>` with
`horizontal_tangent_multiplier` / `vertical_tangent_multiplier`. Negotiation uses
`fov_tangent_multipliers.horizontal` / `.vertical` (`FovTangentMultipliers`).

For each eye and side, client tracking sends `atan(tan(runtime_angle) * axis_multiplier)`.
Eye poses/asymmetry are preserved. `send_view_params` caches those exact cropped FOVs;
`report_compositor_start` supplies them for rendering and OpenXR projection-layer submission.
Identity returns the original angles bit-for-bit. Only newly located runtime views are cropped;
reused views are not cropped a second time.

The server independently resolves upstream's full-FOV render and stream requests, applies the
same factors to each, and pads each axis up to 32 pixels. It writes separate OpenVR target/render
fields and negotiates the stream size. Examples at h=0.854/v=0.850:

| Full-FOV aligned size, per eye | Cropped size, per eye |
| --- | --- |
| 3072x3232 render or stream | 2624x2752 |
| 2080x2208 stream | 1792x1888 |

Thus a 3072x3216 render request first aligns to 3072x3232; a separately configured 2080x2208
stream remains separate after crop. Do not supply already cropped dimensions to these settings
unless a second reduction is intentional. Upstream's Bilinear/Adaptive/Lanczos filter choice is
untouched; it operates on the resulting source/stream sizes. Alignment can slightly change the
ratio. The offline 2624x2776 fixture is not a runtime override.

Missing negotiated crop fields mean identity for older servers. Present invalid/incomplete
values fail setup, as do enabled out-of-range/non-finite server multipliers. Shipped streaming
profiles reset crop off and both values to 1.0; the harness must apply its crop after a profile.
The `steamvr-restart` schema flag and `.65` stream-start comparison include `video.fov_crop`:
changes cause the normal debounced reconnect, and changed driver geometry triggers a restart.
`[FOV-CROP]` logs effective factors and sizes (server `info!`, client `error!`).

References: [RENDER-ENCODE-RESOLUTION.md](RENDER-ENCODE-RESOLUTION.md),
[SETTINGS-APPLY.md](SETTINGS-APPLY.md).

## Shutdown and NVENC

`shutdown_driver` now takes the `ServerCoreContext` out of the lock and drops it in a separate
statement, after the write guard has expired. Worker joins in its destructor can therefore
call back through `SERVER_CORE_CONTEXT`. No shutdown timeout or terminal-encoder changes.

The optional NVENC dimension preflight applied unchanged after normalizing the reference patch
to LF. Exact **`ALVR_NVENC_DIMENSION_PREFLIGHT=1`** queries WIDTH_MAX/HEIGHT_MAX using the actual
codec GUID after `FillEncodeConfig`, before `CreateEncoder`. Unknown codec, invalid dimensions,
failed/nonpositive caps, or dimensions above caps fail with `NVENC dimension preflight failed:`.
Success logs `NVENC dimension preflight passed:` through `Warn`. Requested/cap dimensions are
included. Other env values disable it. No dimensions, presets, or encoder fallback policy change;
this runs only when NVENC is attempted, never in the PyroWave encoder.

## Validation and integration gates

Local validation was source-only for Rust/C++: this task has no toolchains or hardware access.
All 183 existing Python tests passed with `python -m unittest discover -s tests -q`.
`python -m pytest -q tests` could not start because pytest is absent. Whitespace, LF/no-BOM,
reverse patch application, unchanged NVENC reference, and the old harness's counter parser were
checked. These checks do not execute the new Rust/C++ code.

Before accepting the integrated build, CI must prove:

1. The generated overlay reconstructs on `26aa7c0`, includes the new `NvencDimensionPolicy.h`,
   and builds matching Windows streamer/dashboard and Android OpenXR APK. Do not omit untracked
   files when extracting the diff. No modified helper is overwritten by upstream's copy step.
2. Unit tests in `alvr_client_core`, `alvr_client_openxr`, `alvr_packets`, `alvr_session`,
   `alvr_server_core`, and `alvr_dashboard` pass; compile/test `alvr_server_openvr` on Windows.
   Run the required Python suite with pytest in CI. Added/ported cases cover deduplication/reset,
   telemetry round-trip, crop identity/asymmetry/alignment/invalid negotiation, profile reset,
   crop reconnect detection, and effective-encoder/default/opt-out range policy.
3. Windows NVENC compilation validates the caps API, const methods, header inclusion and C++17
   aggregate initialization. Exercise its policy with equal caps, over-width/height, failed and
   nonpositive queries, unknown codec, and invalid dimensions.
4. Matching-client render validation covers RGBA and packed YCbCr, direct and staging paths,
   fix ON/OFF, unchanged hardware-codec SDR/HDR, and black/white endpoints. Exercise pre-wait,
   repeats, ready-FD rejection and decoder replacement with the restored counter. The later FIFO
   must carry identities and preserve this same post-release definition.

The telemetry fields extend a bincode control packet: JSON negotiation's missing-field defaults
do **not** establish mixed-version binary compatibility. Use a matching pair and let the planner
handle protocol/version integration. The fork's bench parser must also be carried forward
separately; upstream `.65`'s bench does not compute `fresh_selected_output_rate_fps` by itself.
Live FOV/frustum agreement, crop reconnect, colour correctness, shutdown, performance and optical
claims remain unverified on this port. None of the explicitly excluded experimental groups was included.

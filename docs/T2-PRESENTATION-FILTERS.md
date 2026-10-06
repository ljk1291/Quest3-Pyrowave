# T2 presentation candidates, 2026-10-06

Source/software work only, based on fork `6ee1ba5` (PR #58 head). No defaults,
dependency revisions, signing, protocol, installations, arm files or device/system
settings were changed. Neither candidate has a fork-specific headset acceptance.

The new overlay pin changes the current source-lock identity. The immutable
historical HVS compatibility proof deliberately does not admit this new lock;
offline scoring with that historical tool bundle requires separate qualification.
Only its unit-test fixture was isolated to the lock named by the recorded proof,
with an added newer-lock rejection check. No production scorer, descriptor,
historical evidence or protected frame-bank algorithm changed.

The token vocabulary, Adaptive selector/kernel and CPU reference/tests are adapted
from JMS1717/Quest3-Pyrowave **`2de8ad13973ed9c3a8e72f4c85a79e1e7e5d085a`**:
`patches/quest3-alvr.patch`, `tools/downsample/frame_downsample.hlsl`,
`tools/downsample/reference.py`, `tests/test_downsample.py`. Existing ALVR and
upstream attribution remain. Area is this fork's existing WO-5 implementation.
Adaptive is compiled by FXC and embedded as a separate DXBC, rather than compiling
upstream's HLSL string at runtime. It shares WO-5's 48-byte b0 constant buffer and
uses a separate linear/clamp sampler in s0. The canonical and embedded HLSL must
match byte-for-byte. All legacy HLSL and DXBC hashes remain unchanged.

## Owner's next supervised session

Use a new matching CI-built pair; retain the existing profile and snapshot before
the owner performs changes. This document authorizes no installation or test.

`debug.q3pw.layer_filter` is still init-only and Quest-3-only. Unset/`0` retain
baseline flags; `1` = supersample (`0x1`), `2` = supersample_hq (`0x2`),
`3` = normal supersample + auto (`0x21`). It also accepts trimmed,
case-sensitive `+`-separated `sharpen` (`0x4`), `sharpen_hq` (`0x8`),
`supersample`, `supersample_hq`, `auto` (`0x20`). For example:

| Property request | Expected active flags | Required advertised extensions |
| --- | --- | --- |
| `sharpen_hq` | `0x8` | FB composition-layer settings |
| `sharpen_hq+supersample_hq` | `0xa` | FB composition-layer settings |
| `sharpen+auto` | `0x24` | FB composition-layer settings and META automatic-layer filter |

Restart the Quest client after changing the property. Verify the native
`[Q3PW_LAYER_FILTER] request="..." requested=... active_flags=0x...`
startup record and enabled-extension fields. Missing extensions reject the entire
request without a settings chain. Unknown/empty tokens, mixed numeric/token input
and auto-only requests also yield `active_flags=none`. Numeric `3` retains its
historical normal-supersample companion; textual `auto` alone is invalid. Duplicate
tokens are idempotent. Normal + HQ in either category is valid: normal takes
precedence, as specified by
[XR_FB_composition_layer_settings](https://raw.githubusercontent.com/KhronosGroup/OpenXR-Docs/main/specification/sources/chapters/extensions/fb/fb_composition_layer_settings.adoc).
Auto requires a candidate pool per
[XR_META_automatic_layer_filter](https://raw.githubusercontent.com/KhronosGroup/OpenXR-Docs/main/specification/sources/chapters/extensions/meta/meta_automatic_layer_filter.adoc).
Only the stream projection layer gets the heap-owned chain; lobby/passthrough/local
quad behavior remains unchanged. Flags express submitted hints, not proof the
runtime used a particular algorithm on every frame.

The session setting is **`video.pyrowave.render_downsample_filter`** (under
`session_settings` in saved JSON), with choice JSON `{"variant":"Adaptive"}`,
`{"variant":"Area"}` or `{"variant":"Bilinear"}`. Dashboard: Video → PyroWave →
**Game render downsample filter (all codecs)**. The same setting is used before
PyroWave, stock H.264, HEVC and AV1; it has no codec-enable gate. Completely restart
SteamVR/vrserver after changing it; reconnect the stream. A game caching render
targets may also need restarting. These changes must be owner supervised.

- **Bilinear**, default and missing-session/native-field fallback: identical old
  shader, sampler and 16-byte cbuffer. Historical `ALVR_Q3PW_DOWNSCALE=area`
  remains honored only in this mode, with its original unfoveated SDR PyroWave
  gate and `source=legacy_environment` marker. Restore/clear that process override
  for a pure Bilinear control.
- **Adaptive**, experimental: footprint-widened Catmull-Rom with same-sign tap
  pairing; 3x maximum per source axis (larger footprints are under-filtered).
  Texel-center identity at equal size, bicubic reconstruction when magnifying,
  eye-bound clamping and nonnegative light before the existing transfer conversion.
- **Area**, experimental: existing WO-5 exact box integration, now explicitly
  selectable for every codec, including foveated/HDR composition. Max 4x per
  axis; oversized/invalid eye crops fail the frame explicitly. Same clamped linear
  fallback when equal size/magnifying. This avoids environment inheritance for
  both filters and gives a useful comparison without introducing another shader.
  The independent dither option retains all its original restrictions.

Explicit Adaptive/Area selections ignore the legacy downscale environment, including
invalid values; dither environment validation remains independent. Invalid native
selector values, shader creation or sampler failures fail initialization, never
silently fall back. Verify **`[Q3PW_DOWNSAMPLE] requested=Adaptive effective=Adaptive
source=session ... composition_ready=true`** (or Area/Bilinear) in `vrserver.txt`.
`[FrameRender] game render ... per eye recommendation -> stream ... per eye ...
downsample` describes the recommendation. Opt-in per-layer/per-eye
`[Q3PW_DOWNSAMPLE] submitted_texture=... crop=... source_extent=... stream=...
footprint=...` records actual submitted sizes at first use and each geometry change.
It does not prove a game's internal resolution, especially if it uses dynamic
resolution, and footprint metadata from bounds is not a per-pixel derivative measurement.

## Independent geometry

No resolution-protocol change was needed. Dashboard Video now exposes both existing
exact controls: **Game render resolution per eye**
(`video.emulated_headset_view_resolution`) and **Stream resolution per eye**
(`video.transcoding_view_resolution`). Choose Absolute, set width and enable/set
height independently. The existing preset is now labelled **Render and stream size
preset (sets both)**; selecting it or a streaming profile still sets both sizes,
preserving their old assignments and defaults. Apply profiles first, then set exact
geometry; independent controls avoid importing upstream's unrelated profile defaults.

For example, keep stream 3072x3232/eye and request game render 3840x4032/eye
(1.25x/axis, candidate). Saved paths are:

```text
session_settings.video.transcoding_view_resolution.variant = Absolute
session_settings.video.transcoding_view_resolution.Absolute.width = 3072
session_settings.video.transcoding_view_resolution.Absolute.height.set = true
session_settings.video.transcoding_view_resolution.Absolute.height.content = 3232
session_settings.video.emulated_headset_view_resolution.variant = Absolute
session_settings.video.emulated_headset_view_resolution.Absolute.width = 3840
session_settings.video.emulated_headset_view_resolution.Absolute.height.set = true
session_settings.video.emulated_headset_view_resolution.Absolute.height.content = 4032
```

ALVR keeps its 32-pixel upward alignment. FOV cropping, if enabled, applies to both
configured sizes; fixed foveation changes encoded dimensions later. Use SteamVR
custom 100% to follow the recommendation, or keep an independently recorded SteamVR
scale for a comparison. Verify recommendation, actual texture/crop and final encoded/
decoded dimensions separately. A larger render adds PC work while stream pixels stay
fixed; it cannot transmit all that extra source detail.

## Validation and pending gates

[Sanitized source/software evidence](../results/T2-PRESENTATION-FILTERS-2026-10-06.json)
records local checks. Clean apply of the complete predecessor stack followed by
the new overlay reproduced all 16 modified ALVR files byte-for-byte; reverse check
passed and all eight existing shader-source/bytecode manifest entries matched.
FXC SDK 10.0.26100.0 rebuilt every experimental shader and matched the embedded
hashes. Tiny D3D11 **WARP** readbacks passed Adaptive direct-reference checks, DC,
identity, fractional/anisotropic scale, 3x cap, eye seams/flips and transfer/gamma,
alongside existing Area, dither and foveation regressions. WARP linear-sampler
subtexel rounding has a bounded 0.003 tolerance for the random-pattern/gamma cases;
flat fields/seams/identity retain tight tolerances. No hardware timing was measured.
FXC still emits the unchanged Area/transfer warnings documented in WO-5.

Native Rust execution was unavailable locally (`rustc` absent). CI runs six pure
layer-policy tests in `tests` and `client`, session missing-field migration and
all-codec choice retention in `streamer`, and server-core tests that verify the
setting reaches OpenvrConfig for each codec. Full native builds remain pending.
After the owner makes this local commit available remotely, dispatch
**`.github/workflows/ci.yml` / Quest3-Pyrowave**, branch
`codex/t2-presentation-filters`, **`cpu_only=false`**. Required jobs: **tests,
client, streamer, matching-pair**. `streamer` recompiles/hash-checks Adaptive with
FXC and executes WARP. No workflow was dispatched, no push or PR was made here.

Local Python results: 118 unittest cases (5 skipped), 50 focused frame-bank/pin/
metadata tests, and 861 tools tests (15 skipped, 16 subtests). Four excluded stale
README/link tests fail identically on a complete `6ee1ba5` archive; they are recorded
in the evidence rather than rewriting preserved upstream documentation. No new
relative links are broken. Git staging was refused because the linked-worktree
index is outside the writable sandbox root; **all changes are uncommitted**.

Risks: Catmull-Rom ringing/halos, softened fine text, under-filtering beyond 3x,
extra PC sampling work, compositor sharpening accentuating codec artifacts, and
added compositor GPU cost. HDR, arbitrary projection/layer bounds, overlays,
stock-codec live presentation, foveation interactions and headset tail pacing need
the supervised gate. Upstream's `results/LAYER-FILTER-AB-2026-10-04.json` and
`docs/PR-9-REVIEW.md` are historical upstream evidence only; Adaptive's weaker tail
pacing is one reason Bilinear stays default. Runtime rate acceptance, standalone
11.1 ms decode budget and sustained live 90 Hz are all **unverified for this pair**.

## Exact change inventory

Tracked repository changes: `.github/workflows/ci.yml`, `sources.lock.json`,
`patches/presentation-filters.patch`, `patches/README.md`,
`tools/ci/check_quality_shaders.py`, `tools/ci/fetch_sources.sh`,
`tools/ci/quality_shaders_test.cpp`, `tools/ci/source_lock.py`,
`tools/windows/check_quality_shaders.cmd`, `tools/windows/quality-shaders.json`,
`tools/downsample/frame_downsample.hlsl`, `tools/downsample/reference.py`,
`tests/test_downsample.py`, `tests/test_presentation_overlay.py`,
`tools/tests/test_xrbench_framebank.py`,
`docs/LAYER-FILTER.md`, `docs/PC-QUALITY-FILTERS.md`,
`docs/T2-PRESENTATION-FILTERS.md`, `docs/ARTIFACT-QUALITY-STATUS.md`,
`results/T2-PRESENTATION-FILTERS-2026-10-06.json`.

The additive overlay changes these reconstructed paths (not vendored trees):

```text
alvr/client_openxr/src/layer_filter.rs
alvr/client_openxr/src/lib.rs
alvr/dashboard/src/dashboard/components/settings_controls/presets/builtin_schema.rs
alvr/server_core/src/connection.rs
alvr/server_openvr/cpp/alvr_server/Settings.cpp
alvr/server_openvr/cpp/alvr_server/Settings.h
alvr/server_openvr/cpp/alvr_server/alvr_server.cpp
alvr/server_openvr/cpp/alvr_server/bindings.h
alvr/server_openvr/cpp/alvr_server/shader/FrameRenderPSAdaptive.hlsl
alvr/server_openvr/cpp/platform/win32/FrameRender.cpp
alvr/server_openvr/cpp/platform/win32/FrameRender.h
alvr/server_openvr/cpp/platform/win32/FrameRenderPSAdaptive.cso
alvr/server_openvr/src/graphics.rs
alvr/session/src/beta_tests.rs
alvr/session/src/lib.rs
alvr/session/src/settings.rs
```

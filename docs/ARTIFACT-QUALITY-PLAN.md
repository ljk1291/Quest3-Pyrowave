# Compression-artifact plan: mura-like texture and line aliasing

Status: diagnosis and Codex work orders, 2026-10-02. No source, default, pin or
installed build was changed while writing this. Evidence tags follow the
experiment reports: **MEASURED** (recorded in this repo or upstream), **DERIVED**
(arithmetic on measured values), **ESTIMATED** (model or extrapolation).
Hardware steps run either in owner-supervised sessions or inside armed unattended
windows under [UNATTENDED.md](UNATTENDED.md) and [AGENTS.md](../AGENTS.md). Live
progress and the queue are in [ARTIFACT-QUALITY-STATUS.md](ARTIFACT-QUALITY-STATUS.md);
long-running execution follows [CODEX-GOAL.md](CODEX-GOAL.md).

## Summary

The owner's symptoms after the colour fix — mura-like texture in Metro and the
SteamVR library, blocky thumbnail edges, and line aliasing — are most likely
explained by **bit starvation combined with the Haar wavelet**, not by a decoder
defect.
The Godlike geometry gives PyroWave about **0.28 bits per pixel** at 500 Mbps.
Upstream's well-received manual recipe ran at about **0.91 bpp**. At that low
rate, Haar's piecewise-constant reconstruction turns discarded detail into
2×2/4×4 blocks and staircase edges. Two presentation-side contributors add line
shimmer: the game is rendered at exactly the encode size (no supersampling), and
the Quest compositor gets a single-mip 3072×3232 projection layer with no
filtering flags.

The decoder speed plan (P0–P5) cannot fix this. Even a perfect 90 Hz decoder at
Godlike/500 Mbps/Haar would show the same image. Spending fewer encoded pixels
per frame (render/encode decoupling, then peripheral encoding) improves quality
**and** decode time together, so it comes first.

## Diagnosis

### 1. Bits per pixel are far below where PyroWave is designed to run (primary)

| Configuration | Stereo px/frame | 300 Mbps | 500 Mbps | 600 Mbps | 800 Mbps |
| --- | ---: | ---: | ---: | ---: | ---: |
| Godlike encode 3072×3232/eye, 90 Hz (current) | 19.86 M | 0.168 | **0.280** | 0.336 | 0.448 |
| 2560×2688/eye, 90 Hz | 13.76 M | 0.242 | 0.404 | 0.484 | 0.646 |
| 2080×2208/eye, 90 Hz | 9.19 M | 0.363 | 0.605 | 0.726 | 0.968 |
| Upstream manual recipe: 2080×2208, 120 Hz, 1000 Mbps USB | 9.19 M | | | | **0.907** at 1000 |
| HEVC 200 Mbps at Godlike, 90 Hz (for scale only) | 19.86 M | | | | 0.112 at 200 |

DERIVED: bits/frame = Mbps / 90 (or 120), divided by stereo luma pixels. This is
the same cap math as [BITRATE.md](BITRATE.md).

- PyroWave's README targets "~200+ mbit/s" for **1080p–4K at 60 fps** on a
  monitor. Its trivial entropy coding "is responsible for a large increase in
  bit-rate, especially at higher compression ratios"
  ([upstream README](https://github.com/Themaister/pyrowave)).
- The OpenVR projections logged in session 07 give **24.2 × 23.6 px/deg at the
  centre** of a 3072×3232 eye (MEASURED projection; DERIVED density). That is
  roughly a 1440p monitor viewed from one screen-height away, the closest
  distance PyroWave's author evaluated. In his published CDF 9/7 sweep
  (`eval-results/psnr-sweep-output-2.csv`, 2560×1440, H = 1.0), **0.28 bpp scores
  about 23 dB PSNR-HVS-M-H**. His "good quality" curve (~35 dB) needs **about
  2.2 bpp** there (DERIVED from upstream data). This is monitor-calibrated: lens
  blur and the oversampled periphery make a headset more forgiving. Treat it as a
  direction only: the current point is deep in the codec's low-quality regime.
- Bitrate did not change decode time: Haar GPU decode stayed about 9.2 ms from
  300 to 600 Mbps ([bitrate screen](../results/bitrate-screen-2026-10-02.json),
  MEASURED). More bits, when Wi-Fi allows, cost the decoder nothing measurable.

### 2. Haar roughly halves the effective bitrate on natural content and shapes the artifacts

Real-codec RD data already in this repo
([exp3 rd/](../captures/decoder-experiments/exp3-fused-haar/rd), MEASURED: PC
encode/decode, 2560/eye stereo; Kodak upscaled):

| Content at ≈0.275 bpp (≈ Godlike 500 Mbps) | PSNR-Y 9/7 → Haar | VMAF 9/7 → Haar |
| --- | --- | --- |
| kodim04 | 30.75 → 28.90 | 76.9 → 57.1 |
| kodim07 | 29.64 → 27.25 | 73.6 → 52.6 |
| kodim19 | 26.99 → 25.81 | 73.3 → 57.1 |
| synthetic panel (UI-like) | 52.78 → 51.49 | 97.1 → 96.9 |

- At matched PSNR-Y, Haar needs **+103 % bytes** on Kodak and +10.5 % on the
  panel (exp3); +19 % median on worn SteamVR Home at a much higher bpp (exp5).
  At matched VMAF, CDF 9/7 needs only about **45–55 % of Haar's bytes** on Kodak
  at this operating point (DERIVED from the same CSVs).
- Charts and UI hide Haar's cost; Metro's textured, foggy natural content
  exposes it. This explains why chart screens looked acceptable while Metro failed.
- Haar's synthesis basis is a box. When the rate control strips fine bands,
  reconstruction becomes piecewise-constant: blocks in gradients (the
  "mura-like" mottling) and stair-stepped diagonals (perceived as aliasing). The
  session-07 compositor capture of the Lone Echo thumbnail shows blocky,
  stair-stepped letter and hand edges, consistent with this (qualitative: the
  capture also includes compositor warping).
- CDF 5/3 needs **+17.9 %** bytes versus 9/7 at matched PSNR-Y (exp2,
  MEASURED). Its synthesis basis is a tent: dropped detail becomes linear blur
  instead of blocks.
- The cost: at Godlike, live CDF 9/7 GPU decode was **24.3 ms** versus Haar's
  **10.5 ms** p50
  ([godlike90-screen](../results/godlike90-screen-2026-10-02.json), MEASURED,
  protocol .1). Live Haar uses the pair-local fast kernel (`inverse_haar_pairs`
  in `shaders/idwt.comp`); 9/7 and 5/3 use the shared-memory apron path. This
  most likely explains why exp2/exp3's standalone "transform only costs ~2 %"
  result (measured before the pair-local kernel, on the apron path) does not
  transfer. CDF 9/7 is not viable at Godlike/90 Hz on this decoder. At
  2080×2208 it is ESTIMATED at about 11 ms, still borderline.

### 3. No supersampling on the PC side

Render and encode are both 3072×3232, so the game's own aliasing goes straight
into the codec. ALVR already separates `emulated_headset_view_resolution`
(SteamVR's recommended render size) from `transcoding_view_resolution`
(stream/decode size). Upstream verified this on the same ALVR pin and exposed it
in `eeb0041`. The PC composition sampler is anisotropic, but the game SRV has
one mip (`platform/win32/FrameRender.cpp`). A 1.2–1.5× downscale is therefore
close to single-tap bilinear: better than nothing, but not a proper filter.

### 4. Compositor sampling of the eye buffer (line shimmer)

The client creates 3072×3232 projection swapchains with `mip_count: 1`
(`alvr/client_openxr/src/graphics.rs`). It chains no
`XR_FB_composition_layer_settings`. The panel is about 1:1 at the centre and
increasingly oversampled toward the edges. Meta documents normal and quality
super-sampling flags as reducing "flicker for high contrast edges", and they
apply to projection layers
([Meta: layer filtering](https://developers.meta.com/horizon/documentation/native/android/mobile-openxr-composition-layer-filtering/),
[Meta: Super Resolution on projection layers](https://developers.meta.com/vr/blog/vr-image-quality-meta-quest-super-resolution/);
also [XR_META_automatic_layer_filter](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_META_automatic_layer_filter.html)).
They cost compositor GPU time on the same GPU as the decoder, so this must be
measured.

### 5. Chart "mura" in flat areas is probably not the codec

The diagnostic chart's background and patches are perfectly flat. A wavelet
codec produces zero detail coefficients there, and 0.28 bpp is ample for that
content (panel row above: 97 VMAF). Codec damage concentrates at text, stripes
and edges. Mottling seen across flat dark-grey fields is more likely the LCD
panel's own non-uniformity or compositor behaviour. Confirm with the same
flat-field chart over HEVC before attributing it to PyroWave.

### 6. Minor contributors

- **8-bit planes, no dither**: `RgbToYuvPlanar.hlsl` writes R8 Y/Cb/Cr straight
  from an 8-bit sRGB composition texture. Metro's dark fog gradients can band and
  mottle. Upstream PyroWave added a scaled-encode path with R16 intermediates or
  dithering after our pin (`pyrowave_encoder_encode_gpu_scaled_synchronous`,
  Sept 23).
- **Monitor-tuned RDO weights**: `get_quant_rdo_distortion_scale` assumes 96 dpi
  at 1 m (Nyquist ≈ 32.6 cycles/degree, about 65 px/deg). The headset centre is
  about 24 px/deg, so the finest bands are discounted as if they were invisible.
  The effect on perceived quality is unknown: it is an offline experiment, not a
  fix.
- **Intra-only temporal instability**: per-frame block decisions flip under head
  motion, so low-rate artifacts crawl. More bits per pixel is the cure.
- **Game content**: film grain or noise, if the game exposes them, are the most
  expensive content for an intra wavelet codec.

## What the owner can try now (settings only, supervised)

1. Keep the SteamVR render recommendation at 3072×3232. Set the stream/encode
   size to **2560×2688** in a first A/B, then 2080×2208, with Haar at 500 Mbps
   and the same Metro checkpoint. Expected: visibly less mottling and
   stair-stepping, slightly softer centre (20.2 or 16.4 px/deg vs 24.2), and
   decode time dropping to ESTIMATED ~6.4 ms or ~4.3 ms GPU (upstream measured
   ~4.5 ms at 2080×2208 Haar).
2. If the network stays clean, try 600 Mbps (already measured clean) at the
   better-looking geometry.
3. Show the flat-field chart once over HEVC and once over PyroWave at the same
   geometry to separate panel mura from codec damage.

Use WO-2's tooling for the recorded version of these steps so settings
restoration stays exact.

## Codex work orders

Each work order is one branch/PR under `codex/`. Every new runtime behaviour is
an opt-in toggle, default off, with an activation log line and CPU/CI tests.
Hardware steps (ADB, installs, SteamVR, headset properties, live or GPU benchmarks)
run only inside an armed window that passes every rule in
[UNATTENDED.md](UNATTENDED.md), or in an owner-supervised session. Otherwise Codex
writes the runbook, queues the step in the status file and moves on. Metro gameplay
and in-headset judgements are always owner tasks. Build through GitHub Actions.
Never commit `results/local/` captures.

### WO-0 — Unattended supervisor (prerequisite for every unattended hardware step)

- New `tools/quest3/unattended.py` implementing [UNATTENDED.md](UNATTENDED.md):
  - `arm`, for the owner to run: writes or validates `results/local/unattended/arm.json`.
  - `check`: evaluates every precondition and writes the before-snapshot.
  - `start`: spawns the detached deadline restorer and the thermal/battery monitor,
    then returns a window id.
  - `status`, `stop` (writes the stop marker) and `restore` (runs the restorer now).
- Reuse `tools/quest3/awake.py` (proximity override with its independent restore
  worker), `preflight.py`, `control.py` readback/restore and the baseline
  restoration records. Pin every ADB call to the armed serial. The restorer stops this
  fork's client before restoring properties. Late agent cleanup must not overwrite it.
- Windows specifics:
  - keep-awake through `SetThreadExecutionState` for the window only;
  - idle detection through `GetLastInputInfo`;
  - detached processes that survive the agent exiting.
- CPU tests with fakes for ADB, PowerShell, clocks and process spawn cover:
  - arm validity, including nightly windows across midnight and expiry;
  - every precondition failure path;
  - restorer ordering and idempotence;
  - thermal pause and resume thresholds;
  - refusal when the arm file is missing.
- The first live use is a `check` plus `start`/`restore` dry run inside an armed
  window, with no other device changes. Its restoration report must match the
  snapshot before any test cell runs.

### WO-1 — Offline frame-bank quality harness (highest value, no headset)

Goal: answer "what does the codec do to real Metro frames at each candidate
setting?" offline, with exact source/decoded-frame identity by construction.
This closes the plan's "immutable source/decoded-frame image controls" gate.
Quest decode matches PC decode within one code value (exp1/exp3 correctness
tables), so PC decoding stands in for the headset's reconstruction.

- Input: lossless encoder-input y4m dumps from `ALVR_PYROWAVE_DUMP` /
  `_DUMP_COUNT` / `_DUMP_EVERY` / `_DUMP_TRIGGER`
  (`VideoEncoderPyroWave.cpp`, around lines 179–208).
- New `tools/xrbench/framebank.py`, reusing `exp5.py`, `rdmatrix.py` and
  `pyrowave_wave.py`. Sweep wavelet {haar, 53, 97} via `PYROWAVE_WAVELET`, rate
  {300, 500, 600, 800} Mbps at 90 Hz with the exact cap math in BITRATE.md, and
  per-eye encode geometry {3072×3232, 2560×2688, 2080×2208}. Downscale per eye
  with a stated filter and no seam crossing.
- Score two ways: at encode size (codec-only), and upscaled back to 3072×3232
  (what reaches the eye). Report PSNR-Y/Cb/Cr, SSIM, VMAF, and
  `pyrowave-psnr-hvs-m` with the viewing factor computed from the logged
  projection (about 24 px/deg). Emit fixed-position crops (text, foliage, dark
  gradient, thin lines) as PNG grids, labelled private and written only under
  `results/local/`.
- CI: unit tests on a tiny synthetic y4m (cap math, geometry, seam handling, CSV
  schema). No GPU in CI.
- Owner step (supervised, separate from rate captures): one 90-frame Metro dump
  at the fixed checkpoint. Codex then runs the harness on the PC's GPU inside an
  armed window while the owner is idle (`allow: frame_bank_pc`).
- Done when: a sanitized `results/framebank-<date>.json` summary and a short doc
  section give a Haar/5/3/9/7 × rate × geometry table for Metro frames.

### WO-2 — Render/encode decoupling controls and candidate profiles

- Port upstream `eeb0041` (`tools/quest3/resolution.py`, `control.py
  resolution` command, `presets/resolution-comparison.json`, `tests/test_resolution.py`,
  bench `resolution_evidence`) and `2f6f087` (pinned scene geometry). Adapt
  profiles to this fork's 90 Hz Wi-Fi target: render 3072×3216→3232 with encode
  3072×3232 / 2560×2688 / 2080×2208.
- Extend `tools/quest3/budget.py` to print bits per pixel next to bytes/frame.
- Unattended cells: chart-scene A/B/A per geometry inside an armed window, with Haar,
  500 Mbps and recommended-AHB allocation on, recording decode timings, the fresh rate
  and restoration. Owner runbook: the same A/B/A at a fixed Metro checkpoint, with
  subjective notes. Captures must record requested, negotiated and decoded geometry,
  and fail closed on mismatch, as upstream does.
- Done when: CPU tests pass, profiles apply and restore via readback, and the
  runbook is in `docs/`.

### WO-3 — Panel-mura vs codec control

- Add full-field flat modes to `tools/quest3/stereo_scene.py` (e.g. `--flat 16`,
  `24`, `48`, `128`) and commit the neutral-patch chart variant used in session 07
  (it emitted `source_neutral_rgb_codes`) if it is not already tracked.
- Runbook: identical flat field over PyroWave and the fork's HEVC control at the
  same geometry and refresh. Mottling present in both is not a codec result.

### WO-4 — Opt-in compositor layer filtering

- In `alvr/client_openxr` (via `patches/quest3-alvr.patch` /
  `stable-baseline-alvr.patch` per the patch rules), enable
  `XR_FB_composition_layer_settings` and, when present,
  `XR_META_automatic_layer_filter`. Chain `XrCompositionLayerSettingsFB` to the
  stream projection layer.
- Toggle: `debug.q3pw.layer_filter` = 0 off (default) / 1 normal super-sampling
  / 2 quality super-sampling / 3 auto. Log the requested and active flags once.
  Fall back to no chain if an extension is missing. If the pinned `openxr` crate
  lacks typed support, chain the raw `sys` struct.
- Unattended cells: off/on/off chart screens measuring the fresh rate, decode
  completion and compositor cost proxies at the chosen geometry. Owner step: judge
  line shimmer in the headset.

### WO-5 — PC downscale quality and optional dither

- When render size ≠ stream size, offer a proper downscale (separable
  bicubic/Lanczos, or box-filtered mips) in the Windows composition/planar path
  instead of single-tap anisotropic sampling. Optionally add ordered/blue-noise
  dither before R8 quantization in `RgbToYuvPlanar.hlsl`.
- Both are server options, default off. Regenerate `.cso` files with the
  recorded fxc flags, and add a CPU reference test for filter weights and output
  range. Note: upstream PyroWave's newer `pyrowave_encoder_encode_gpu_scaled_synchronous`
  provides sinc scaling and dithering. Adopting it means moving the PyroWave and
  Granite pins, and Granite `9d44761` previously spiked encoder p99. Evaluate
  separately; do not bundle.

### WO-6 — Fast CDF 5/3 inverse kernel (gated on WO-1)

Start only if WO-1 shows 5/3 materially better than Haar on Metro frames at the
chosen geometry and rate.

- Add an opt-in neighbourhood-local 5/3 inverse in `shaders/idwt.comp` (or a
  sibling), modelled on `inverse_haar_pairs`: texelFetch the small LL/HL/LH/HH
  neighbourhood (5/3 needs ±1 coefficients per axis), with no shared-memory apron
  tile or workgroup barriers. Toggle `PYROWAVE_FAST53` / `debug.q3pw.fast53`.
- Gates: ≤1 code value versus the existing 5/3 path on GPU readback for
  identical bitstreams, edge geometry and both 4:2:0 planes. Regenerate the
  shader manifest and hashes. Device timing comes from the standalone harness,
  run in an armed window. The target is within about 1.3× of Haar's GPU decode.
- Rationale: about 1.7× fewer bytes than Haar for equal PSNR-Y on natural
  content (DERIVED: Haar +103 % vs 5/3 +17.9 % over 9/7), and a tent-shaped
  reconstruction without blocks or staircases.

### WO-7 — Encoder RDO viewing-density knob (offline evaluation only)

- Replace the hard-coded `dpi`/`viewing_distance` in
  `Encoder::Impl::get_quant_rdo_distortion_scale` with an env/config value
  (`PYROWAVE_RDO_PX_PER_DEG`). The default must reproduce today's constant
  exactly (unit test). This is encoder-only and bitstream-compatible.
- Evaluate only through WO-1, with PSNR-HVS-M-H at the matching viewing factor
  plus crops. Do not change the default without an offline and subjective win.

### WO-8 — Light peripheral encoding (keeps Godlike centre density)

- Port upstream `061dc0b` and `2b87fc7` onto this fork's patch stack (they edit
  `patches/quest3-alvr.patch`; rebase over `stable-baseline-alvr.patch`). Keep it
  default off. Add a stronger candidate (for example, a smaller centre and a 2×
  edge ratio) as a separate profile, computed with `tools/quest3/foveation.py`.
- Peripheral px/deg is already above the panel's because of the tangent
  projection, so this is the route to the Godlike centre with fewer encoded pixels.

### WO-9 — Plan update

- Add a "Quality track" to [DECODER-OPTIMIZATION-PLAN.md](DECODER-OPTIMIZATION-PLAN.md)
  that links here. State that encode geometry and bits per pixel are chosen
  before P0–P5, because every decode budget scales with encoded pixels. Keep all
  existing evidence text unchanged.

## Order

1. WO-0 first: no unattended hardware without it. In parallel with it: WO-1, WO-2,
   WO-3 and WO-9 (source and CPU tests only).
2. First armed window: WO-0 dry run, flat-field HEVC control, chart geometry A/B/A.
   Owner: the Metro frame dump.
3. Then WO-4 and WO-5, measured off/on/off at the chosen geometry in armed windows.
4. Gated on WO-1 data: WO-6, WO-7, WO-8.

[ARTIFACT-QUALITY-STATUS.md](ARTIFACT-QUALITY-STATUS.md) holds the live queue and
overrides this order when they differ.

No step promotes a default. Promotion rules in the decoder plan still apply.

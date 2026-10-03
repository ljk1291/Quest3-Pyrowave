# Decoder optimization plan

## Current evidence — 2026-10-02

### Research reconciliation and next work

The [source-pinned research shortlist](DECODER-RESEARCH-2026-10-02.md) compares
WiVRn, upstream PyroWave/PyroFling, FFmpeg, Meta IGL, libplacebo, Nova/Polaris,
NX Warp and Nightfall with the actual fork. It supplies source locations,
licences, activation requirements, effort/risks and isolated correctness gates.
The next-work order below takes priority over unfinished historical experiments:

- [x] Reconcile the references with current code and earlier rejected experiments.
- [x] Install the verified signed colour-fix pair and confirm fresh colour-policy
  and recommended-allocation activation. Chart colours now look normal to the
  owner; this is not a precise range or overall image-quality pass.
- [ ] Before further hardware comparisons, finish an unobscured neutral-patch
  check and immutable source/decoded-frame image controls. Persistent texture
  and line aliasing remain unexplained; compositor PNGs are qualitative.
- [ ] Investigate the terminal PC encoder timeout during Metro startup and
  preserve control/shutdown access after encoder failure. Keep the one-second
  safety bound and pending-resource retirement. Generalize the verified offline
  rollback fallback; require sampled idle competing workloads throughout future
  timing windows. A later active ComfyUI job does not establish timeout causation.
- [ ] **P0:** add per-component/level dequant/iDWT profiling on the faster
  recommended-AHB configuration; verify actual payload/shader activation and
  measure profiler overhead separately. The older 3.75/5.00-ms split is not a
  new profile of the ~82–83 fresh-submission/s candidate.
- [ ] Extend the standalone first-frame replay probe into a bounded, immutable
  multi-frame packet benchmark; preserve legacy fields while identifying exact
  CPU/GPU/completion timing boundaries. Complete range/colour reference gates.
- [ ] **P1:** investigate final-luma Haar reconstruction inside the existing
  fragment conversion, preserving recommended AHB usage. This is not a retry
  of whole-Haar fusion or compute RGBA conversion.
- [ ] **P2:** prove direct three-plane Vulkan sampling into a final RGB target
  offscreen; then separately assess sampler YCbCr conversion and a minimal
  Vulkan OpenXR RGB session. Do not assume YUV swapchains or full asynchrony.
- [ ] **P3/P4:** only with measured justification, test new fragment Haar or a
  single dequant payload/store/branch hypothesis. Keep prior batching/FP16
  regressions closed without a materially new hypothesis.
- [ ] **P5:** consider a new bounded output-lease/scheduling design only if
  profiling attributes a remaining bottleneck to completion/selection/handoff.

No baseline or dependency pin was changed by the source-review step. The
subsequent Session 07 installed the colour-fix candidate separately; no
optimization or stable profile was promoted.
Every hardware experiment still needs explicit session scope/readiness, finite
limits and exact settings restoration. Source review and a standalone win
cannot promote a stable 90-Hz profile.

### First Metro subjective-quality observation

The first supervised Metro Awakening observation on the verified
`f2e9df5704cc` protocol `.2` pair is a **subjective quality fail**. The active
profile was 3072×3232 per eye at runtime-confirmed 90 Hz, producing a 6144×3232 stereo
encoder image: PyroWave Haar/Compute, TCP, fixed 500 Mbps, 4:2:0 SDR, direct
eye copy and the recommended AHardwareBuffer allocation (`0x10000300`). The
owner reported dull colours, mura-like compression and aliasing. This was the
first Metro observation, so allocation-related regression is unknown. The
saved UE 100% scale is not proof of the game's internal render dimensions.

The telemetry capture and screenshots were taken after Metro had closed. They
are excluded from this gameplay observation and supply no Metro performance or
image-quality evidence. No source-frame/decoded-frame match or numerical
quality score exists. Do not label a bitrate, Haar, 4:2:0, allocation setting
or decoder stage as the cause.

The session negotiated full range, but a legacy downstream full-RGBA to
limited-range remap remains a candidate for the dull-colour symptom. A
codec-specific bypass is implemented in source and is not part of this tested build.
Its signed `d1c3b3d4edb3` pair passed cloud builds/tests and matching-pair
verification. The subsequent matching-pair Session 07 verified local artifacts,
installation and fresh activation: the owner reports normal chart colours but
persistent mura-like texture and SteamVR line aliasing. The neutral patches
were partly covered by the dashboard in the retained capture. Metro startup
hit a terminal PC encoder fence timeout, before a gameplay checkpoint or image
capture qualified. Exact settings restoration required recovery after the
failed API; all saved values and VD configuration hashes were verified restored.
See [the follow-up result](../results/colour-quality-check-2026-10-02.json).
Finish unobscured grayscale/range and same-input controls, then replay the same Metro
checkpoint with allocation off/on at fixed 500-Mbps Haar settings. Compare Haar
with CDF 9/7 at the same profile; use HEVC and a Virtual Desktop reference only
as separately recorded controls. Preserve external and internal geometry and
require exact source/decode frame identity before any numerical quality claim.
See [the sanitized observation](../results/metro-quality-feedback-2026-10-02.json).

Session 05 identified a substantial output-allocation improvement on the verified
`f2e9df5704cc` pair. With `fragment_min_usage=1` held constant, requesting the
driver's recommended AHardwareBuffer usage raised fresh selected outputs from
**56.00 to 82.69/s**; reverting the request returned them to **55.25/s**.
Conversion medians were **4.91 / 1.31 / 5.09 ms**, and decode-to-fence medians
were **17.47 / 11.54 / 17.62 ms**. Actual allocation flags changed
`0x300 → 0x10000300 → 0x300` for all three output slots with no fallback.
An independent enabled repeat reached **82.02/s**, with **1.36 ms** conversion
and **11.63 ms** decode-to-fence medians. All seven 50-second rate captures had
matching builds, unchanged non-factor settings, covered runtime/counter evidence,
idle sampled ComfyUI queues and passing thermal gates. Profiler and image
capture were disabled during the rate windows. Saved system/headset settings
and VDXR registration were restored and verified after the separate image runs.
This is an unqualified candidate: the 90 Hz rate and low-rate screens still fail.
The earlier minimal Vulkan image-usage experiment alone was flat at
**56.08 / 55.80 / 56.00/s**. See the [allocation control](../results/allocation-screen-2026-10-02.json)
and [recommended-AHB comparison](../results/optimal-ahb-screen-2026-10-02.json).

The requested 300/400/600/300 Mbps sequence is complete on the verified
`d4735d88985a` protocol `.2` pair. Strict fresh-submission rates were
**52.95 / 54.12 / 53.42 / 55.41 per second**. Reported video bitrate rose to
301.5 / 402.4 / 606.2 / 301.8 Mbps, but GPU decode remained about 9.2 ms and
conversion about 5.1 ms. Higher bitrate did not establish a performance gain;
the repeated 300-Mbps control was fastest. These are short AFK screens, not
optical FPS or a 90 Hz pass. See [the sanitized results](../results/bitrate-screen-2026-10-02.json).

Six screenshots and three short recordings were retained privately in separate
QA runs. The session-03 rate screens had dashboard/performance-HUD uncertainty.
A later clean session-04 compositor capture had no observed SteamVR/HUD
occlusion, retained LEFT/RIGHT labels and a changing chart counter, but showed
softened/fringed fine chroma edges and text. It is qualitative only: compositor
and recording transforms prevent a codec-isolated or numerical pixel-quality
claim. Repeat a clean control before promotion, using exact settings restoration.

HEVC/H.264 use the Quest's hardware video-decoding path through MediaCodec.
PyroWave instead uploads compressed data, reconstructs wavelet planes on the
general GPU, converts them into RGBA hardware buffers, then synchronizes Vulkan,
GLES and OpenXR eye rendering. Codec algorithm simplicity is not equivalent to
the efficiency of a dedicated video-decoding circuit. The chip documents
AVC/HEVC decode support ([Qualcomm XR2 Gen 2 specifications](https://docs.qualcomm.com/doc/87-73689-1/87-73689-1_REV_A_Snapdragon_XR2_Gen_2_Platform_Product_Brief.pdf));
Android exposes hardware decoder identity through
[MediaCodecInfo](https://developer.android.com/media/optimize/performance/codec).

### Hardware decoder, CPU and hybrid options

The XR2 Gen 2 video engine supports AVC/H.264, HEVC, VP9 and AV1 bitstreams;
there is no exposed PyroWave hardware-decoder path. Feeding PyroWave packets to
MediaCodec cannot reuse that engine. Transcoding to HEVC/AV1 would instead be a
different codec pipeline, with another encode/decode step if done after PyroWave.
The direct HEVC path remains our hardware-decoder control.

There is no CPU reconstruction implementation in our pinned PyroWave source.
`pyrowave_decoder_decode_cpu_buffer_synchronous()` calls GPU decode, copies the
three GPU planes to host buffers, waits for a fence, then performs CPU copies;
it is a GPU-readback API, not a CPU decoder. See the
[pinned implementation](https://github.com/Themaister/pyrowave/blob/d2997ac172bdc00e29c58e3f2938acb7e94580bf/pyrowave_c.cpp).

A new CPU decoder with ARM NEON is technically possible, but its performance is
unmeasured. At 3072×3232 per eye and 90 Hz, the workload is 1.787 billion pixels/s;
one RGBA8 output write is 7.15 GB/s, before wavelet intermediates, input reads,
cache maintenance and presentation. These are derived byte counts, not measured
DRAM bandwidth. A CPU-only implementation is therefore a low-priority hypothesis,
not an assumed speedup. It must include output allocation and GPU presentation
in its end-to-end benchmark.

CPU packet ingestion/preparation and GPU reconstruction already perform different
parts of the job. A new hybrid could move coefficient unpacking/dequantization
to a NEON worker while leaving inverse wavelets and conversion on the GPU.
The Quest uses shared memory, so this need not require a discrete-GPU-style PCIe
copy; it still needs suitable buffers, cache visibility and producer/consumer
synchronization. Expanding coefficients on the CPU may increase shared-memory
traffic enough to cancel the gain. CPU/GPU transform splitting or overlapping
successive frames must preserve bounded buffer ownership and latency.

- [ ] If GPU allocation/fusion work is insufficient, prototype NEON coefficient
  unpack/dequant on exact captured packets, with GPU-readback equivalence checks.
- [ ] Measure CPU preparation, GPU wait, memory/cache cost, thermal behavior and
  end-to-end fresh delivery in CPU/GPU off/on/off tests. Never count the current
  `cpu_buffer_synchronous` API as a CPU-only benchmark.
- [ ] Consider a full CPU reconstruction prototype only if the partial prototype
  shows plausible throughput; do not assume more workers increase performance.

### Latest GPU profile

On the session-04 `f2e9df5704cc` protocol `.2` pair, opt-in
`debug.q3pw.pass_profile=1` emitted valid Granite Dequant/iDWT completed-context
means after 90 fenced completions. `debug.q3pw.hide_performance_overlay=1`
provided a clean AFK compositor capture. Both remain diagnostic options, default
off, require client restart, and are recorded/restored by the control tools.
The phase samples span 32.043 seconds inside a 51.907-second chart, including
setup/teardown around a separate 25-second telemetry window. They report
delayed window means rather than exact-frame timing.
Profiling runs do not count as acceptance runs. See [the sanitized profile
evidence](../results/decoder-profile-2026-10-02.json).

The profile measured mean windows of **3.75 ms Dequant** and **5.00 ms iDWT**;
the telemetry conversion median was **4.92 ms**, with **17.31 ms** median
decode-to-fence time against the 11.11 ms interval for 90 Hz. These are different
measurement scopes and must not be summed into an invented total. Session 05
completed the allocation screen described above. Profile the remaining wavelet
levels on that faster allocation before selecting a final-level fusion implementation.
Dequantization remains substantial enough to profile its memory traffic too.

## Objective and guardrails

The objective is a reproducible PyroWave candidate for **3072 x 3232 per eye,
90 Hz, TCP, 4:2:0, SDR** on Quest 3. The target is not met by the current
one-minute chart screens. An earlier protocol `.1` Haar/synchronous-direct
300-Mbps diagnostic recorded 50.42 selected-submission events/s and a 44.99
client-FPS 1% low, with median GPU decode, native conversion and
decode-to-fence timings of 10.51, 5.12 and 19.59 ms. It is historical work
selection evidence only, not the fastest current cell or strict fresh-output
evidence. See [the sanitized screen evidence](../results/godlike90-screen-2026-10-02.json).

Those measurements select work; they do not establish optical FPS, optical
motion-to-photon latency, Metro quality, or a 90 Hz pass. GPU decode and native
conversion are consecutive Vulkan timestamp intervals (`t[1]-t[0]` and
`t[2]-t[1]` in `tools/pyroclient/pyroclient.cpp`); do not add their medians to
CPU wait, OpenXR or eye-copy wall times. The latter overlap the GPU work.

The protocol `.2` matched-pair build and live selected-output counter verification
are complete for session 03. This does not supply retrospective evidence for the
earlier `.1` captures.

All short cells start from this fixed profile unless the one named factor is the
experiment:

| Field | Fixed value |
| --- | --- |
| Geometry | 3072 x 3232 per eye for source, render and encode |
| Runtime | confirmed 90 Hz; SteamVR scale and display/debug properties read back |
| Codec | PyroWave, Haar, Compute wavelet reconstruction, fragment color conversion |
| Transport | TCP, fixed bitrate, 4:2:0, SDR, no foveation |
| Presentation | direct eye copy, synchronous; one decoder worker |
| Other experiments | async copy, handoff, frame/pre-wait, raw sRGB, cache, fused Haar, batch dequant and compute conversion off |
| Workload | same chart/Metro checkpoint, graphics settings, warm-up and comparable thermal state |

`Compute` above describes the wavelet decoder. With
`debug.q3pw.convert_compute=0`, color conversion is the capability-gated
**fragment** path. Consequently `fragment_min_usage` and `optimal_ahb_usage`
are applicable allocation experiments; they are not decoder-wavelet toggles.

## Evidence required for every cell

- [ ] Use a matched APK/server pair and preserve requested, negotiated and
  effective settings at the start and end.
- [ ] Verify direct/staging counters, source dimensions, refresh evidence,
  chart coverage and image correctness (eyes, orientation, range and changing
  content). A property request without an activation readback is not a result.
- [ ] Run automatic pixel/readback QA and screenshot/video QA as **separate
  finite AFK runs** from rate captures. Compare eye assignment, orientation,
  range, color patches and changing counter frames against the deterministic
  source; retain the artifacts and checksums with the cell.
- [ ] Make exact source-frame identity a prerequisite for codec quality scoring.
  Do not pair encoder dumps and taps by target timestamp alone: that timestamp
  is reusable, and an ambiguous duplicate must yield no PSNR/SSIM/VMAF result.
- [ ] Record ALVR-reported `video_mbps` separately from requested bitrate and
  observed network bytes/throughput. `video_mbps` is ALVR's reported video metric, not
  independently verified raw TCP payload; the target is a cap, not a promise
  of bytes.
- [ ] Collect GPU decode, conversion, record, wait, fence, eye acquire/render/
  release distributions without adding overlapping intervals.
- [ ] Record host workload/VRAM, thermal state and clock observations. Reject a
  cell with a competing workload, decoder/stream error, corruption, tracking,
  controller or audio fault.
- [ ] Use the protocol `.2` selected-output counter for acceptance evidence.
  It is a monotonic post-render/release **source identity** counter, not a
  tracking timestamp, GPU completion or optical presentation. Do not promote a
  result without it.

The older public `godlike90-screen` chart data pre-dates that counter. It
remains useful as a diagnostic baseline, but cannot satisfy strict fresh-output
acceptance. The session-03 bitrate screen is protocol `.2` and records the
counter, but is still a short chart diagnostic rather than acceptance evidence.
The legacy target-timestamp field is deliberately reusable by different game
frames; timestamp duplication is diagnostic only.

Previous supervised diagnostics already verified functional world-grid tracking,
both controllers and audio. Finite AFK captures can preserve that functional
evidence and automate image checks, but cannot establish comfort, motion clarity
or gameplay quality; those remain manual Metro-review gates.

## Ordered work

### 0. Establish a clean control

- [x] Remove the unused duplicate fork identity from `sources.lock.json` and enforce
  `fork.json` as the sole application-identity input in new packaging. Contract
  tests reject a lock containing application identity. This metadata-only cleanup
  is not part of the already-built `f2e9df5704cc` test pair.
  Historical `.2` artifact records retain a raw lock snapshot containing stale `.1`
  fork metadata; actual protocol/version writers use `fork.json`. Keep old hashes
  intact and do not reinterpret that redundant value as the installed protocol.
- [x] Validate the completed protocol `.2` matched pair's selected-output
  counter in a short direct/Haar control before comparing optimizations.
- [ ] Repeat CDF staging versus CDF direct with *all* refresh/display properties
  equal. The existing direct comparison is confounded: its direct cells report
  `debug.oculus.refreshRate=90` while the staging cell reports it unset.
- [x] Repeat the fixed Haar/direct 300-Mbps control at least twice. Retain it as
  the before/after reference for every later one-variable screen.
- [ ] Run an HEVC 200-Mbps control at the same dimensions/90 Hz and workload.
  It is a runtime/PC/compositor control, not equal-quality or equal-bitrate
  proof. The existing HEVC screen met the short chart rate proxy (89.68 events/s,
  89.95 1% low), whereas no PyroWave screen did.

### 1. Bitrate is a controlled network screen, not a decode fix

- [x] Complete the 300/400/600/300 sequence with strict fresh-output counters.
- [ ] Repeat a short control with SteamVR dashboard visibility explicitly
  recorded and the QA overlays absent before quality/gameplay promotion.

Run the following sequence only after the clean 300-Mbps control streams
continuously without a connection, decode or image fault. It may remain
decode-limited; a 90-Hz pass is not required to make the bitrate comparison.
Keep encoding, source, runtime and all experiment properties fixed; re-check
the direct counter after every reconnect.

| Order | Target Mbps | Advance only when | Interpretation |
| ---: | ---: | --- | --- |
| 1 | 300 | continuous clean control is repeatable | Establish decode/presentation baseline |
| 2 | 400 | no 300-Mbps network or image fault | Compare payload, loss/retransmits and decode pressure |
| 3 | 600 | 400 remains continuously clean | Test Wi-Fi headroom at the same image workload |
| 4 | 300 | 600 is complete | Detect thermal/clock/order drift |
| 5 | 800 | 300/400/600 show network headroom and clean pacing | Optional; stop on retransmits, increased tail latency or delivery regression |

- [ ] For each rate, compare requested Mbps, median/p95 `video_mbps`, encoded
  bytes/frame and TCP/network counters. Do not infer payload from Wi-Fi PHY.
- [ ] Treat a higher rate with unchanged reported `video_mbps` as a
  codec-content or cap observation, not transport capacity.
- [ ] Do not raise bitrate to compensate for a decode-to-fence result exceeding
  11.11 ms. The current Haar/direct 300-Mbps data has no drops or stale packets
  and reports about 302.5 Mbps through ALVR's `video_mbps` metric, so it points
  first to Quest-side work.
- [ ] Make 80-versus-160-MHz a separate matched network diagnostic once a
  clean continuous profile exists; it does not require an 800-Mbps pass. USB is
  a diagnostic transport reference, never Wi-Fi proof.

### 2. Profile the actual boundary before restructuring it

The direct route is `StreamRenderer::render` in
`alvr/graphics/src/stream.rs`: it is used only for a valid source, no
passthrough and identity reprojection rotations. Otherwise it falls back to
staging. `DirectEyeRenderer::render` in `alvr/graphics/src/direct_eye.rs`
samples the external AHardwareBuffer into two acquired OpenXR eye FBOs and, in
the stable mode, calls `gl.finish()` before the producer lease can be released.

- [x] Add diagnostic-only top-level Granite Dequant and iDWT completed-context
  means. The session-04 profile is a valid delayed-window diagnostic, not
  exact-frame timing or a display-performance result.
- [ ] Add distinct timestamp labels for upload/recording, each wavelet level,
  final inverse transform and color conversion. Keep those GPU intervals
  separate from CPU/wall timing for EGL image import/bind,
  `samplerExternalOES` eye draws, `gl.finish()`, and OpenXR acquire/wait/release.
  Keep all diagnostics outside the default execution path when disabled.
- [ ] Emit whether every selected frame used direct or staging and whether a
  repeat/null redraw occurred. Instrumentation must not manufacture a fresh
  source identity.
- [ ] Compare those phase distributions with Vulkan timestamps, not summed
  totals. Prioritize the largest repeatable phase and publish the boundaries.

### 3. Allocation and import experiments

The existing fragment conversion allocation path is the first low-risk
Quest-side candidate: `debug.q3pw.fragment_min_usage=1` narrows the output image
usage, and `debug.q3pw.optimal_ahb_usage=1` additionally asks the driver for
recommended Android-hardware-buffer usage. The latter requires the former.
The earlier native allocation screen observed about 0.67 ms conversion in one
live sequence, but lower delivery and different clocks; it is a hypothesis, not
a promotion. The fixed fixture was effectively flat. See
[DECODE-PIPELINE.md](DECODE-PIPELINE.md#experimental-fragment-output-usage-19).

- [x] Run allocation off/on/off: `fragment_min_usage=0/1/0` at the fixed
  baseline, with actual usage/allocation flags and fragment activation logged.
  Session 05 found no meaningful rate or conversion gain from this flag alone.
- [x] Run `fragment_min_usage=1` plus `optimal_ahb_usage=0/1/0` with fresh
  native initialization evidence. Session 05 showed a reversible improvement.
- [ ] Complete exact-frame source/decoded-buffer image equivalence checks before
  promotion. The separate compositor screenshots are qualitative only.
- [ ] Reject any allocation fallback, changed color/range/eye mapping, source
  lease fault or rate/tail regression. A requested vendor recommendation is not
  evidence it was used.

The next comparison control keeps **both** `debug.q3pw.fragment_min_usage=1`
and `debug.q3pw.optimal_ahb_usage=1`, with the fixed profile above at 300 Mbps.
These are initialization options and require a client/decoder restart. Verify
`[Q3PW_FRAGMENT_USAGE]` reports fragment conversion and all three minimal slots;
`[Q3PW_AHB_USAGE]` must report requested/active 1, a nonzero recommendation and
three matching allocations without fallback/retry. Record the actual flags;
do not hard-code the recommendation for other drivers. The observed extra bit
does not establish a particular compression/tiling mechanism.

GPU decode remained about 9 ms. In the first faster cell, native recording was
0.57 ms median and native fence wait 10.94 ms median; wait is an overlapping
blocked-host interval, not CPU compute work. Prioritize dequant/iDWT subpass
profiling and final-luma materialization over CPU offload or speculative import
caching. Keep profiler captures separate from rate and screenshot captures.

- [ ] Add per-level inverse-wavelet timing with bounded completed-context
  reporting; measure the final luma level on the recommended-AHB candidate.
- [ ] Investigate the remaining ~45 client-FPS 1% low separately from the
  ~82 fresh-output mean. A near-90 median does not establish smooth 90 Hz.
- [ ] Repeat 300/400/600 Mbps only after the decoder meets its frame budget,
  or for an explicit image-quality question; the old bitrate screen found no
  speed gain and cannot explain this isolated allocation improvement.

`debug.q3pw.image_cache=1` caches at most eight retained AHB/EGL-image/external
texture imports in `DirectEyeRenderer::cached_source_texture`. It can remove the
per-frame create/bind/destroy work in
`GraphicsContext::render_ahardwarebuffer_using_texture`, but cannot remove the
Vulkan reconstruction or synchronous finish.

- [ ] Run cache off/on/off only if phase profiling shows import overhead, or
  after the allocation sequence is inconclusive. Check bounded slot logs and
  cache fallback; do not evict an image held by the external producer.
- [ ] Existing native off/on/off delivery (112.19/112.16/112.93) showed no
  gain. A Godlike retest is justified only as a controlled, instrumented check.

### 4. Decoder/shader candidates, one at a time

- [ ] Keep pair-local Haar as the performance control. It has the best current
  Godlike diagnostic rate but requires objective image-quality comparison with
  CDF 9/7 before any quality claim.
- [ ] Test final-level Haar specialization only after a readback/reference
  equivalence gate, then one fixed-profile off/on/off screen.
- [ ] Test color-conversion fusion only with pixel/range validation. It must
  preserve 4:2:0 chroma siting, limited/full range and sRGB behavior.
- [ ] Test converter-only relaxed precision as an independent shader variant,
  inspired by the [Nightfall source comparison](NIGHTFALL-COMPARISON.md), with
  exact-frame full/limited-range and chroma-edge readback checks. This does not
  enable FP16 throughout the wavelet decoder or establish Nightfall performance.
- [ ] Test shader workgroup shape, memory layout and barriers one change per
  matching generated-shader pair. Record dispatch count, shader hash and
  Vulkan timestamp deltas; do not use a CPU-only timing improvement as proof.
- [ ] Test `convert_compute=1` only as an explicit fragment-conversion control,
  with the same allocation usage and quality gate. It is independent of
  wavelet Compute and is not a default candidate.

The focused fusion candidate is **final luma Haar level + fragment conversion**,
not the existing whole-transform `haar_fused` experiment. At 4:2:0, Cb/Cr finish
at level 1; level 0 materializes only full-resolution luma before conversion
reads it again. An opt-in PyroWave mode could leave levels 4→1 intact, expose
the final luma coefficient view, and reconstruct those four Haar bands inside
the RGBA fragment pass. This removes the final luma image write/read and compute
dispatch while retaining chroma reconstruction, output allocation and safe fences.

- [ ] Add the mode and compute-write→fragment-sampled visibility inside PyroWave;
  the bridge cannot safely supply that dependency for an image it does not own.
- [ ] Use a separate fragment pipeline; gate on Haar + 4:2:0 + compute wavelets
  + active fragment conversion. Unsupported combinations retain the baseline.
- [ ] Match baseline R8 luma quantization, exact Haar parity, chroma filtering,
  range and transfer behavior before claiming equivalence. Avoid silently
  changing precision just because the intermediate luma image disappeared.
- [ ] Compare GPU-readback RGBA for the same encoded frames, including asymmetric
  eye charts, full/limited range and edge geometry. Start with ≤1 channel-value
  error and ≤0.05 dB source-PSNR loss as investigation gates, not a substitute
  for motion/image review.
- [ ] Regenerate/check shader headers and hashes, build a new matching signed
  pair, then measure off/on/off. Additional fragment fetches/register pressure
  could erase the removed memory traffic; fewer passes are not proof of a win.

The following are known regressions or unqualified diagnostics. Keep them off
in the stable profile; revisit only to answer a new profiling hypothesis:

| Option | Prior observation | Rule |
| --- | --- | --- |
| async eye copy | 88.33 vs synchronous 106.47/106.40 fresh submissions/s; 402 deferrals | Do not retest without a new multi-buffer lease design |
| two workers | More contention and a prior delivery regression | Diagnostic only after single-worker bottleneck is proven CPU-side |
| fused Haar | Native live result regressed despite fewer passes | Readback gate and clean control required |
| batched dequant | Off/on/off live screens did not improve delivery | Keep off |
| FP16 math | Missed the PSNR-loss gate | Keep default precision |
| raw sRGB copy | No established gain; requested activation was not proven | Keep off until activation and image QA are available |

### 5. Long-term presentation redesign

- [ ] Do not simply re-enable the existing asynchronous fence path. It holds
  the sole producer lease while the copy is pending and repeats the old layer.
- [ ] If profiling proves the synchronous finish dominant, design explicit
  GL/EGL-to-Vulkan synchronization plus bounded independently leased output
  buffers. It must define failure, teardown and reconnect behavior before
  allowing parallel decode/copy.
- [ ] Investigate a Vulkan/OpenXR-native eye path or supported multiview/layered
  rendering only after the above. The present code owns two separate OpenXR FBO
  writes, per-eye mapping, flip, range and sRGB handling; removing a draw needs
  runtime-extension and pixel-validation evidence.

## Promotion and stop rules

A short screen can reject a regression; it cannot pass the goal. Promote only a
candidate that has repeated fixed-profile screens, a clean bitrate comparison,
strict selected-output rate and 1% low within the 2% tolerance, correct image
review and no sustained deterioration. Then run three five-minute windows,
followed by a 30-minute **Metro Awakening** session at the same dimensions and
settings. Complete reconnect, sleep/resume, controller reconnect and temporary
network-interruption recovery tests before labelling the profile stable.

Stop the current cell immediately for decoder/device failure, stream disconnect,
visible corruption, tracking/controller/audio fault, severe thermal condition,
unexpected settings drift, missing telemetry or source-identity discontinuity.
Save the report and operator observation, restore the last known-good profile,
then return to the prior Virtual Desktop registration/settings using the
[stable baseline return procedure](STABLE-BASELINE.md#return-to-virtual-desktop).
Do not turn a lower resolution, lower refresh or a chart-only result into a
Godlike/90-Hz success.

## Quality track — artifact-quality goal (2026-10-02)

The owner’s [artifact-quality work orders](ARTIFACT-QUALITY-PLAN.md) and
[checkpoint queue](ARTIFACT-QUALITY-STATUS.md) now govern this investigation.
Choose render/encode geometry and bits per pixel before running P0–P5, because
every decoder budget depends on encoded pixels. Preserve the historical
measurements above: the ~82–83 fresh submissions/s comparison belongs to the
`f2` pair, while the colour check belongs to `d1`; neither is a stable 90-Hz pass.

The quality diagnosis is a hypothesis to test on this owner’s exact inputs.
Haar, bitrate starvation, source sampling and compositor filtering remain
distinct factors. Compare an immutable Metro frame bank across wavelet, bitrate
and per-eye encode geometry, scoring both codec reconstruction and the image
resampled to the same eye size. Require exact source/decoded identity, fixed
crops, PSNR/SSIM, VMAF and PSNR-HVS-M-H at the logged viewing density. Compositor
screenshots and prior Kodak results cannot establish a Metro crop-quality win.

WO-0 is the prerequisite for unattended device or GPU work. WO-1–3 prepare the
frame bank, reversible geometry controls and flat-field HEVC/PyroWave comparison
without opening a hardware window. Only an owner-created valid arm file can
authorize unattended work; the independent restorer and monitors must be ready
before any change. Metro acquisition and in-headset judgement remain supervised.
See [UNATTENDED.md](UNATTENDED.md) for the complete contract.

The artifact-quality goal selects a candidate only after all fixed Metro crops
beat the current Godlike-encode/Haar/500-Mbps baseline on both named perceptual
metrics, an unattended chart screen preserves at least the baseline fresh rate
without encoder/decoder faults, and settings restoration verifies the VD hashes.
The status file must then supply that profile’s owner sign-off checklist and
rollback steps. Reduced encode size must be labelled explicitly; retaining a
Godlike render recommendation does not make it a Godlike encoded-resolution pass.
This goal does not change stable defaults or replace the stable-90-Hz acceptance
and promotion rules above.

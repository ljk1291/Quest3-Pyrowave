# Decoder optimization plan

## Current evidence — 2026-10-02

The requested 300/400/600/300 Mbps sequence is complete on the verified
`d4735d88985a` protocol `.2` pair. Strict fresh-submission rates were
**52.95 / 54.12 / 53.42 / 55.41 per second**. Reported video bitrate rose to
301.5 / 402.4 / 606.2 / 301.8 Mbps, but GPU decode remained about 9.2 ms and
conversion about 5.1 ms. Higher bitrate did not establish a performance gain;
the repeated 300-Mbps control was fastest. These are short AFK screens, not
optical FPS or a 90 Hz pass. See [the sanitized results](../results/bitrate-screen-2026-10-02.json).

Six screenshots and three short recordings were retained privately in separate
QA runs. SteamVR's dashboard and the performance HUD obstruct part of the chart;
they do not support a full-chart quality pass or numerical pixel score.
Dashboard visibility was not independently logged during the rate captures.
Repeat a clean control before promotion, using exact settings restoration.

HEVC/H.264 use the Quest's hardware video-decoding path through MediaCodec.
PyroWave instead uploads compressed data, reconstructs wavelet planes on the
general GPU, converts them into RGBA hardware buffers, then synchronizes Vulkan,
GLES and OpenXR eye rendering. Codec algorithm simplicity is not equivalent to
the efficiency of a dedicated video-decoding circuit. The chip documents
AVC/HEVC decode support ([Qualcomm XR2 Gen 2 specifications](https://docs.qualcomm.com/doc/87-73689-1/87-73689-1_REV_A_Snapdragon_XR2_Gen_2_Platform_Product_Brief.pdf));
Android exposes hardware decoder identity through
[MediaCodecInfo](https://developer.android.com/media/optimize/performance/codec).

Next build candidates (not present in the tested pair): opt-in
`debug.q3pw.pass_profile=1` reports existing Granite Dequant/iDWT means after
90 fenced completions; `debug.q3pw.hide_performance_overlay=1` initializes the
HUD hidden for AFK image capture. Both default off, require client restart,
and are recorded/restored by the control tools. Native validation and
on-headset verification are separate pending gates. Profiling runs do not
count as acceptance runs.

## Objective and guardrails

The objective is a reproducible PyroWave candidate for **3072 x 3232 per eye,
90 Hz, TCP, 4:2:0, SDR** on Quest 3. The target is not met by the current
one-minute chart screens. The fastest observed cell, Haar plus synchronous
direct eye copy at 300 Mbps, delivered 50.42 selected-submission events/s and
a 44.99 client-FPS 1% low. Its median GPU decode, native conversion and
decode-to-fence timings were 10.51, 5.12 and 19.59 ms respectively. See
[the sanitized screen evidence](../results/godlike90-screen-2026-10-02.json).

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

The current public chart data pre-dates that counter. It remains useful as a
diagnostic baseline, but cannot satisfy strict fresh-output acceptance. The
legacy target-timestamp field is deliberately reusable by different game frames;
timestamp duplication is diagnostic only.

Previous supervised diagnostics already verified functional world-grid tracking,
both controllers and audio. Finite AFK captures can preserve that functional
evidence and automate image checks, but cannot establish comfort, motion clarity
or gameplay quality; those remain manual Metro-review gates.

## Ordered work

### 0. Establish a clean control

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

- [ ] Add diagnostic-only GPU timing for upload/recording, dequantization,
  each wavelet level, final inverse transform and color conversion, followed by
  separate CPU/wall timing for EGL image import/bind, `samplerExternalOES` eye
  draws, `gl.finish()`, and OpenXR acquire/wait/release. Keep it outside the
  default execution path when disabled.
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

- [ ] Run allocation off/on/off: `fragment_min_usage=0/1/0` at the fixed
  baseline, with actual usage/allocation flags and fragment activation logged.
- [ ] If that is correct and non-regressing, run `fragment_min_usage=1` plus
  `optimal_ahb_usage=0/1/0`; retain both source and GPU readback image checks.
- [ ] Reject any allocation fallback, changed color/range/eye mapping, source
  lease fault or rate/tail regression. A requested vendor recommendation is not
  evidence it was used.

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
- [ ] Test shader workgroup shape, memory layout and barriers one change per
  matching generated-shader pair. Record dispatch count, shader hash and
  Vulkan timestamp deltas; do not use a CPU-only timing improvement as proof.
- [ ] Test `convert_compute=1` only as an explicit fragment-conversion control,
  with the same allocation usage and quality gate. It is independent of
  wavelet Compute and is not a default candidate.

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

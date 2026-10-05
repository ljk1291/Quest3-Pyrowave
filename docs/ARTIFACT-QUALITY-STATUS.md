# Artifact-quality status and queue

The shared channel between the owner, the planning agent (Claude) and the implementing
agent (Codex). Codex reads it at every checkpoint and appends to **Log**. The owner or
Claude may reorder **Queue** or add **Notes for Codex** between checkpoints. Keep
entries short and link to evidence.

## Morning offline checkpoint — 2026-10-05 07:14 CEST

The finite PC-only overnight queue is stopped for owner review. The
[combined Markdown report](../results/metro-overnight-quality-2026-10-05.md) and
[JSON evidence](../results/metro-overnight-quality-2026-10-05.json) publish
19 qualified new quality rows, plus hash-bound retained Q3 controls. Fence
metrics use frames 10–89 and HVS uses all 90. Temporal p99 is a luma-code
reconstruction residual, not milliseconds or optical shimmer. Exact qualified
duplicates were reused rather than repeated; failed attempts remain unranked.
The final Light row and Medium 5/3 row passed their own ordered 90-frame,
source/tool/protected-hash and clean closed-lease gates. No owned jobs or cleanup
errors remain in their completed leases. Quality GPU load samples are retained;
they do not qualify timing.

The original motion request has one explicit gap: no pre-encode full-FOV
Haar/500 head-turn stress row was run. Its retained moving-window pack extracts
after decoding and remains diagnostic only. H264Fit and Medium 9/7 have actual
90-frame synthetic pre-encode moving-crop comparisons. AV1 motion was withdrawn;
the private review pack retains only previously completed native AV1 evidence.
The private pack includes standardized full-range BT.709 fence panels and
lossless 90-frame looping clips; it is not committed or a headset judgement.

H264Fit/700/P7 remains the strongest fence result; width-only H.264 recovers
whole-crop and peripheral HVS while trading fence accuracy. Retained stock
AV1 Main10/200/P4 has stronger whole-crop HVS than those reduced H.264 profiles.
Medium 9/7/RDO24 remains the selected PyroWave Medium quality candidate.
Position-aware RDO, lower uniform densities and reconstruction offsets have
trade-offs and are not promoted. Both specified 8-bit residual temporal models
failed quality against intra; entropy and receive-overlap results remain bounded
CPU/design studies.

[7 separate source branches passed manual CPU-only CI](../results/overnight-source-ci-2026-10-05.json).
The optional WO-6 work proves CPU model arithmetic/mapping only; shader activation,
retained decoder parity and speed remain open. The local publication, reference
reuse, private clip identity and closed-output compression checks pass.
[The corrected matching signed pair](../results/quality-candidate-build-rdo-session-2026-10-05.json),
source `0f07f05b4df88f8fa08ea034f794cda4be9eaf38`, is verified and staged,
not installed. Original 80a1635 and d1c3 rollback artifacts remain intact.
RDO selection has an explicit opt-in session-setting route and native getter;
future live activation still needs its marker. Position/width/offset/stock-logging
and inactive NVENC preflight branches are excluded from that pair.

No headset/ADB, VR/VD, network test, settings, arm-file or installation work
occurred. There were no changed runtime settings to restore; this is not a fresh
runtime-restoration readback. Live decode cost, fresh rate, pipeline latency and
optical fields remain unset. Historical approximately 82–83 fresh submissions/s
is still not stable 90 Hz. The [headset checklist](Q3-HEADSET-CHECKLIST.md)
retains Q4 then a/a2/b/c/d and f–h, with an owner judgement for every in-headset
leg. Stop here until the owner reviews the table and confirms a new session.

## Morning ranking — finite offline evidence only

The fewest-artifact PyroWave path remains the already staged **Medium CDF 9/7,
RDO-24, fixed 1000-Mbps** candidate, subject to its separate matching-build,
Q4 transport, runtime geometry, native RDO marker, decoder, freshness and
owner-image gates. Its retained tight fence (frames 10–89) is 42.412796 dB with
p99 9 luma codes and its all-90 HVS is 37.356360 dB. These are offline quality
metrics, not a decoder-cost, submission-rate, latency, or 90-Hz result. The
historical roughly 82–83 fresh submissions/s is still not a stable 90/s pass.

Do not add either position-RDO branch to that runnable candidate. Both used the
same fixed 1000-Mbps / 1,388,888-byte frame cap and are encoder-only offline
experiments. Mode 1's tight fence is 40.893292 dB / p99 11 and all-90 HVS
42.533568 dB; against the retained uniform-RDO24 regional receipt it improves
the centre by +0.478609 dB PSNR-Y and +0.590397 HVS, while reducing peripheral
corners by −1.093858 dB and −1.298166 HVS. Mode 2 is the measured
effective-density-divisor hypothesis, not eye tracking or a peripheral-acuity
model: its tight fence falls to 40.007427 dB / p99 12 while its all-90 HVS is
43.012701 dB. Its centre is only +0.068186 dB PSNR-Y / +0.088406 HVS against
uniform, while corners are −0.111039 dB / −0.112266 HVS. Its fence improves by
0.074199 dB and whole-crop HVS by 0.003885 dB versus uniform 24; these small,
unreplicated aggregate gains come with the recorded peripheral loss. The fixed regional
rectangles and mirrored-right Session-07 geometry assumption limit these
comparisons; neither mode establishes an overall quality improvement or a live candidate.

Closed-loop temporal work is evidence against promoting a temporal optimization
today. The completed native-previous-decoded and synthetic pose-shift models
both retain 90 decoded frames, but their tight fences are only 30.558714 and
30.515085 dB respectively, both with p99 49; all-90 HVS is 35.683889 and
35.293644 dB. The first-frame proof establishes decoded-pixel equality despite
noncanonical unused sign-padding bits; it does not establish a live interframe protocol, transport or speedup.

Prioritize individual dequantization and inverse-wavelet pass profiling on the
faster AHardwareBuffer allocation configuration. Then evaluate final-stage fusion
and direct YUV presentation against reference pixels, colour behaviour, image
transitions and resource lifetime. Their speed gains are unmeasured; the existing
CPU inverse proof is only a starting gate.

Entropy coding follows those decoder investigations and is not a deployment
candidate: its restricted serialized-bitplane model is
an upper bound of 11,499,003 bytes over 90 frames (13.74% of bitplanes, 9.20%
of full payload). It has no emitted stream, decoder implementation, or decode
cost. Keep the CDF 9/7 fused-inverse work behind its CPU mapping and retained
image-parity gates. Its CPU proof does not establish a decoder speedup. No
additional artifact, bitrate increase, or runtime default follows from either
study.

### Ranked next PyroWave investigations

The gain column separates measured quality changes from unmeasured speed gains.
Keep the baseline and matching installed pair unchanged until controlled timing,
image checks and owner approval support a promotion.

| Priority | Investigation | Gain supported so far / estimate limit | Cost and next gate |
|---:|---|---|---|
| 1 | Profile each dequant/iDWT pass on the faster AHardwareBuffer allocation baseline | No new speed estimate. Retained GPU execution, fence completion and decode wall time have different boundaries; they cannot be subtracted into a reliable per-pass model. | Low source effort, supervised finite headset profiling later; retain matching builds and native activation markers. |
| 2 | Final-level inverse-wavelet fusion, optionally including colour conversion | Speed gain unmeasured. The mechanism removes intermediate writes/reads and a dispatch; the CPU 5/3 and 9/7 models are a correctness starting point only. | Medium/high shader effort; prove boundaries, chroma siting, range/transfer and all retained planes before timing. See [WO-6 CPU proof](WO6-FUSED-INVERSE-CPU-RESULT.md). |
| 3 | Direct YUV sampling/presentation with pooled Vulkan images | Speed gain unmeasured. It may remove the RGBA intermediate and some hand-off work; the external references still include completion waits. | High integration/resource-lifetime risk; separate image transitions, ownership, completion and compositor scheduling. |
| 4 | Keep uniform RDO-24 as the image-quality comparison | Full-FOV Haar/500 improves the fence by 3.656 dB and HVS by 1.532 dB versus the retained legacy density. This is a quality gain, not a decoder-speed gain. | Low encoder effort; explicit session readback is prepared in the uninstalled corrected pair. Position variants and lower uniform densities have trade-offs and are not promoted. |
| 5 | Reconstruction-offset sweep | Completed: +0.125 gives +0.053 dB on the fence but −0.058 dB HVS versus zero. No tested offset improves both metrics; no speed gain is established. | Low decoder change; retain zero-default all-90 parity and keep the legacy reconstruction point. |
| 6 | Receive-overlapped progressive work | Current full-frame API offers zero usable overlap. Ideal serialized coarse-band arrival bounds are 0.179/0.455 ms at 1 Gbps; matched arrival/pass timing is missing. | High packet/API and synchronization effort; obtain matched timing before estimating latency savings. |
| 7 | Context-modelled entropy coding | Restricted-model upper bound: 9.20% of total payload, not an implemented coder or a universal limit. Decode-time cost is unknown and could increase. | High parallel GPU decoding risk; prototype only after the existing reconstruction bottleneck is measured. |

The tested 8-bit residual closed-loop prediction models are rejected for this
corpus: both lose more than 9 dB of fence PSNR and have temporal p99 49. A new
prediction experiment needs a changed residual precision/clipping hypothesis;
neither that rejection nor the successful intra rows establishes a live 90 Hz pass.

## Current headset preparation checkpoint — 2026-10-04 21:34 CEST

The owner requested the verified 80a1635 pair, Q4, then **a, a2, b, c, d** and
**f–h** on the winning runnable cell, with an owner judgement for every
in-headset comparison. Preparation is complete enough to identify one source
blocker; **owner confirmation to begin has not been received**. The APK/server
checksums, stable certificate and archive members were reverified. The new server
is staged separately; the d1c3 artifacts and server remain intact for rollback.
No ADB, GPU query, install, VR launch, network test, settings/registration or
arm-file operation has occurred during preparation. Private per-key guard/adapter
and controller entry points have 32 passing CPU tests, including restart role
reuse, dashboard availability during restoration and retained-handle completion.
Fresh state snapshots and live worker/device readbacks remain open gates before
invocation.

**Native RDO readback on 80a1635 is blocked.** The release PyroWave C API sets
`NullLogger` before encoder initialization and suppresses the WO-7 density log.
There is no initialized-density getter or ALVR log bridge in this pair. Thus
a/a2/d cannot meet the requested native proof by reading the launch environment.
The offline direct-Encoder logs remain valid; no Q3 score is retracted. A minimal
read-only getter/log bridge is prepared on local `codex/wo7-live-readback` for review,
with no deployment or automatic substitution for the pinned pair. See the
[checklist correction](Q3-HEADSET-CHECKLIST.md#preparation-finding-native-rdo-proof-is-blocked-on-80a1635).
Its source/lock/wiring checks pass, including the expanded 141-test CPU command;
the standalone C++ default/report-parity test also compiles and passes. Native
DLL export, full matching build and live log activation remain unverified.

a2 is identical to a except RDO 24 px/deg (12 cycles/deg), and follows it
immediately. Q4 retains the 600/800/1000/1200-Mbps stationary sequence and moving
qualification: nominal 1000-Mbps live cells require a passing 1200-Mbps moving
leg to satisfy the 15% headroom rule. The H264Fit 3968x2080 capability probe is
compiled and fixture-tested, but has not queried the GPU. All live measurements
remain unset, including GPU decode execution, completion latency, fresh rate and
estimated pipeline latency. Settings will be snapshotted before changes and
restored with exact readbacks; the owner performs the VD comparison afterward.

## Prior owner-review checkpoint — 2026-10-04 20:52 CEST

**The revised Q3 request is complete; stop for owner review.** The
[combined 32-row report](../results/metro-q3-combined-2026-10-04.md) and
[machine-readable evidence](../results/metro-q3-combined-2026-10-04.json)
retain 23 previous rows plus nine authorized measurements. Thirty cropped rows
are ranked by trimmed fence metrics then HVS; two historical full-FOV references
remain separate. All nine new measurements completed their 90-frame corpus with
clean finite supervised quality leases, zero owned jobs left, no cleanup errors
and unchanged protected harness hashes. GPU-load samples are retained. No headset,
VR, VD, network/settings, arm-file or installed-pair operation occurred.

| Candidate / control | Fence edge PSNR-Y dB | Temporal p99, luma codes | Whole-crop HVS dB |
|---|---:|---:|---:|
| Single H.264 H264Fit / 700 / P7 / softness 0.5 | 47.837276 | 4 | 36.976144 |
| Cropped AV1 Main10 / 200 / P4 / AQ off (retained) | 42.997587 | 9 | 43.346668 |
| Cropped AV1 Main10 / 200 / P1 / spatial AQ | 42.619633 | 9 | 43.103077 |
| Medium 9/7 / 1000 / softness 0.5 / RDO 24 | 42.412796 | 9 | 37.356360 |
| Cropped 9/7 / 1000 / RDO 24 | 39.933228 | 12 | 43.008816 |
| Cropped 9/7 / 2000 / default RDO — offline-only | 39.503112 | 13 | 45.043698 |
| Corrected Light 9/7 / 1000 / softness 0.5 / default RDO | 36.525299 | 17 | 38.710948 |

Fence metrics use frames **10–89**; HVS above uses all **90** frames. Temporal
p99 is an 8-bit luma reconstruction residual, not milliseconds or optical shimmer.
The source contains 89 distinct payloads and irregular capture timestamps. F90
normalizes the bitrate budget; it does not establish fresh rate or display FPS.
H264Fit leads the fence but has a substantial whole-crop/peripheral tradeoff.
Medium/RDO24 is the selected **offline-quality preparation candidate** among the
tested Medium rows, not a new baseline or a stable 90 Hz result.

At unchanged default density, 9/7 gains **3.749361 dB** from 1000 to 2000 Mbps.
The four-point 800/1000/1500/2000 fit gives **3.895236 dB per doubling** and
extrapolates to **7628.7 Mbps** for the retained dual-H.264/700/P4 fence target
(47.032668 dB). Alternative intervals give **7426.6–8045.7 Mbps**, a model
sensitivity range, not a confidence interval or a feasible transport/decode rate.
All 1500/2000-Mbps rows remain **offline-only, above measured Wi-Fi capacity**.

WO-7 ([PR #43](https://github.com/ljk1291/Quest3-Pyrowave/pull/43)) preserves
the legacy default arithmetic bit-for-bit and adds explicit RDO density; 96 dpi
at 1 m corresponds to **65.28 px/deg**, not 96 px/deg. The Light fix
([PR #42](https://github.com/ljk1291/Quest3-Pyrowave/pull/42)) improves its fence
from 30.832637 to 36.525299 dB and p99 from 32 to 17, with Medium/H264Fit parity
preserved. The extension/provenance adapter is
[PR #44](https://github.com/ljk1291/Quest3-Pyrowave/pull/44). Separate branch
tests and required CI passed before integration. The dropped blur-only Light /
dual-H.264 row was not run: the Pyro blur-only control gave no meaningful fence
gain and stock ALVR lacks live dual-eye H.264 transport.

The matching stable-signed pair at `80a16353ca127508fec745dec53dc790ceb77fb2`
passed [full CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37217852222).
[Verification receipt](../results/quality-candidate-build-80a1635-2026-10-04.json)
pins both artifacts, native payloads, shader/source identities and stable certificate.
It includes WO-10, WO-8 with Light correction, WO-13 and WO-7, and is **not installed**.
The [source audit](STOCK-H264-FOVEATION-AUDIT.md) confirms single-stream stock
H.264 H264Fit forward/inverse support, with live dimension/decoder/quality/timing
gates still open; the offline P1/AQ-strength-8 control is not an exact live AQ match.

Next action is owner review of the report and
[headset checklist](Q3-HEADSET-CHECKLIST.md). Its first cells are baseline,
AV1 Main10/200/P4/AQ-off, conditional H264Fit/700/P7, and Medium 9/7/RDO24/1000.
It pins recommended AHB allocation, exact settings/environment restoration and
separate GPU execution, fence completion, fresh submissions and estimated pipeline
latency fields. Those live measurements remain unset. The historical approximately
82–83 fresh submissions/s is still distinct from a stable 90 Hz pass. No automatic
headset, network test, installation or optimization promotion follows this checkpoint.

## Owner objective (revised 2026-10-04)

Fewest artifacts at Godlike density, fresh submissions at least today's (~82–83/s,
target 90/s), and no pipeline-latency regression; PyroWave is optional. Fence edge
PSNR and temporal shimmer lead ranking, then calibrated HVS, then VMAF. Owner
decoder-cap estimates (HEVC/AV1 ~200 Mbps, H.264 ~700, PyroWave ~1000 network-limited)
require verification on our stack. VMAF saturation and optimistic Lanczos reduction
limit prior rankings. The [active plan](ARTIFACT-QUALITY-PLAN.md) incorporates the
complete 2026-10-03 22:45 planner revision, replacing every earlier note and Q3 plan.

**Ethernet readback, 2026-10-04:** Up, **2.5 Gbps**, Realtek Gaming 2.5GbE Family
Controller. Driver rt640x64.sys **10.73.813.2024**, date **2024-08-15**, NDIS 6.40.
Read with Get-NetAdapter; no network changes. Negotiated link speed is not goodput.

## Current state (baseline retained; updated 2026-10-03)

- **Installed candidate:** signed `d1c3b3d4edb3` pair; colour remap fixed.
- **Profile:** 3072×3232/eye, 90 Hz, Haar, 4:2:0, TCP Wi-Fi, 500 Mbps, recommended-AHB
  allocation.
- **Rate:** about 82 fresh submissions/s (f2 pair). This is not a 90 Hz pass.
- **Quality:** fails. The owner sees mura-like texture and line aliasing. The diagnosis is
  in [ARTIFACT-QUALITY-PLAN.md](ARTIFACT-QUALITY-PLAN.md).
- **Open fault:** a terminal PC encoder fence timeout at Metro startup in session 07.
  The cause is unknown.
- **Offline quality screen:** Q1/Q2 are complete. CDF 9/7, 1000 Mbps,
  3072×3232/eye leads the 18-row comparison at 39.342 HVS dB / 99.163 VMAF.
  This is a quality candidate; the installed baseline and rate acceptance are unchanged.
  [Combined table and crop gates](../results/metro-q1q2-combined-2026-10-03.md).

## Queue (current owner goal)

### Owner headset request, 2026-10-04 — prepare and wait

The latest owner message authorizes preparing the supervised headset sequence,
then explicitly requires waiting for confirmation to begin. VD/Streamer closed,
ComfyUI idle and Quest USB power are owner attestations; fresh safety and state
readbacks remain required at the start. Do not touch the unattended arm file.

1. Retain d1c3 rollback artifacts; install only the requested verified 80a1635
   pair after confirmation. Resolve the native RDO-proof/pinned-pair conflict
   identified above before claiming that gate passed.
2. Q4 network qualification, then a, **a2**, b, c, d; a2 differs from a only by
   RDO 24 px/deg and requires native activation proof.
3. Owner chooses the winning runnable cell using quality and live telemetry;
   run f–h only within verified transport/decoder limits. Ask for every headset
   judgement. No unattended inference from earlier tracking/image checks.
4. Restore every changed setting/property/process environment value exactly;
   verify VD, driver registration and OpenXR state. Report restoration complete
   only after readbacks pass; the owner does their own VD comparison.

### Prior owner revision, 2026-10-04 17:36 CEST

The owner's latest message supersedes the two-cell remainder and the 25-row
publication gate below. ComfyUI is owner-confirmed idle; read-only preflight at
15:36 UTC observed 0 running/0 pending and 12799 MiB free VRAM. Authorization
is finite supervised offline frame-bank work on this PC only, with every safety
stop retained. No headset, VR apps, VD, network, settings, arm or installation work.

1. Finish **H264Fit / single H.264 / 700 Mbps / P7 / softness 0.5**. Drop the
   unrun blur-only Light / dual H.264 cell: PyroWave blur-only showed no meaningful
   fence gain, and dual-eye H.264 is not implemented in stock ALVR. This is a
   scope decision, not a measured H.264 blur-only failure. Preserve the old plan
   and stopped attempts; freeze a replacement with only the authorized row.
2. WO-7 on its own branch: encoder-only `PYROWAVE_RDO_PX_PER_DEG`, default exactly
   preserving 96 dpi / 1 m arithmetic and output, with CPU unit proof and CI.
   Add cropped 9/7 / 1000 at 24 and 36 px/deg, plus Medium / 9/7 / 1000 /
   softness 0.5 at 24 px/deg. Compare with the retained default-density rows.
3. On a separate branch, fix Light's 1:1 centre texel phase in live and CPU paths;
   require parity tests and CI, then score Light / 9/7 / 1000 / softness 0.5 once.
   Retain the old Light rows as historical comparisons, not corrected outputs.
4. Add cropped AV1 Main10 / 200 / P1 / spatial AQ as the requested stock-default
   control; verify its relationship to actual stock settings in the source audit.
5. Add default-density cropped 9/7 / 1500 and 2000, and Haar / 2000. These are
   **offline-only, above measured Wi-Fi capacity**. Report fence edge PSNR,
   temporal p99 and HVS, dB per bitrate doubling, and a qualified extrapolation
   of 9/7's bitrate to the retained dual H.264 / 700 / P4 fence score.
6. Report-only source audit: verify the actual stock-H.264 h264fit live path,
   including inverse reconstruction and dimensional limits; identify missing code.
7. Publish **32 measured rows** (23 retained + one H.264 + eight new), with the
   dropped row explicit and historical full-FOV references separate. Rank fence
   metrics then HVS; preserve source/build and requested/effective RDO identity.
   Build and verify a stable-signed matching pair including WO-10, WO-8 plus
   the Light fix, and WO-13, without installing it. Write the exact checklist,
   putting baseline, cropped AV1 10-bit/200/P4/AQ-off, conditionally supported
   H.264 h264fit/700, then best Medium Pyro/1000 first. Record GPU decode ms,
   fresh submissions/s and estimated pipeline latency separately for each;
   unavailable measurements stay unset. Retain Q4 and exact rollback, then stop.

All source branches require CPU tests and green CI before integration. No protected
harness change may be merged while a cell using those modules is in flight.
The 08:37 UTC blocker and older queue below are retained historical evidence.

**Checkpoint, 2026-10-04:** All ten revised Q3a NVENC rows are complete. The
resumed quality lease closed with zero owned jobs, no cleanup errors, and unchanged
source/tool/module provenance. The first row reused its verified retained encode
and decode; no completed encode was repeated. Full-FOV scoring normalizes the
Y4M container header: all 90 frame and mask-reference hashes still match the
parent source exactly. Original combined-report SHA256:
`3afdc310ab2e4120b4b0e00683533ab6200f39040b70c94367505dbe7e927a35`.
WO-10, WO-8 and WO-13 are merged; WO-12's audit and WO-11's design are merged.
The Q3b CPU preflight caught stale per-stream bitrate and encoded calibration
metadata. [PR #38](https://github.com/ljk1291/Quest3-Pyrowave/pull/38) corrected them
as `9d55e32` after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37169330331)
and independent review; actual expanded-space scoring calibration is unchanged.
All five cropped Pyro Q3a rows are now complete with clean lease closure. CDF 9/7
at 1000 Mbps leads them (trimmed fence edge PSNR 35.754 dB, temporal residual p99
19 luma codes); cropped AV1/200 remains ahead (43.747 dB, p99 8). No timing pass.
The completed 15-row [Q3a report](../results/metro-q3a-quality-2026-10-04.md)
and [JSON](../results/metro-q3a-quality-2026-10-04.json) retain both score windows,
crop metrics and provenance. Q3b and the final combined 25-row report remain pending.
The first Q3b cell was deliberately stopped during CPU reference preparation,
before any codec encode: the area-filter helper rebuilt a full-plane summed-area
table for every tile. Its lease closed with zero jobs/errors; partial references
are retained for byte-identity checks. [PR #39](https://github.com/ljk1291/Quest3-Pyrowave/pull/39)
merged the exact-output CPU cache as `3512b19` after 53 focused CPU tests,
independent review and [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37171100761).
The rebuilt first retained Metro frame is bit-identical. The second attempt also
stopped during CPU preparation, before encoding, after finding a duplicate forward
transform for the matching blur reference. Its lease closed cleanly with zero jobs.
[PR #40](https://github.com/ljk1291/Quest3-Pyrowave/pull/40) removes that duplicate
and adds explicitly selected CPU preparation workers (default one, maximum three).
It merged as `7302a25` after 55 focused tests, independent review and
[CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37172014888).
The reduced and matching-blur first-frame hashes match both retained attempts.
The finite r5 controller ran Q3b with three preparation workers and fresh
r3 Pyro attempt paths. Its three Light / 9/7 / 1000 Mbps softness cells (0, 0.5,
1), Light / 5/3 / 1000 Mbps / softness 0.5, both Medium / 5/3 and 9/7 /
1000 Mbps / softness 0.5, H264Fit / 9/7 / 1000 Mbps / softness 0.5 and
blur-only Light / 9/7 / 1000 Mbps / softness 0.5 are complete with clean lease
closure. All eight PyroWave Q3b rows are retained; two NVENC H.264 cells remain.
**Current stop, 08:37 UTC:** H264Fit / single H.264 / 700 Mbps / P7 / softness 0.5
is unfinished. After an earlier ComfyUI-startup/unknown-queue stop, two read-only
checks showed an empty queue. The new guarded attempt then found a fresh active
ComfyUI job and only 599 MiB free VRAM, below the retained 2048 MiB margin.
It stopped before any codec job began and closed with zero owned jobs/errors.
Both NVENC rows remain; all 23 completed Q3 cells are preserved. The owner has
been asked to finish/pause compute work and free GPU memory before resumption.
[Sanitized stop evidence](../results/q3b-resume-blocked-2026-10-04.json).
Do not repeat completed cells. The first result is worse
than cropped 9/7 without foveation on the primary fence: 30.832 versus 35.754 dB
edge PSNR, temporal residual p99 32 versus 19 luma codes (both frames 10–89).
No image filter, runtime decoder or baseline default changed during execution.
Combined publication and the final stable pair remain outstanding; all 15 Q3a
rows are retained.
The earlier [preflight stop](../results/q3a-preflight-blocked-2026-10-04.json) remains
historical evidence; no arm, headset, installed-pair or settings changes occurred.

1. Fence metrics and three-cell backfill are complete: [ranked report](../results/fence-backfill-2026-10-04.md).
   Tight left-eye rectangle (1740,1310,240,274); all 270 regenerated decode hashes
   match retained evidence. Keep both 1–90 and 10–89 windows and reference-only masks.
2. WO-10 merged as `5659c55` after [full CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37164210397):
   opt-in tangent FOV crop (default 1/1), client reports/projection, server
   density-preserving dimensions, logs and both-eye/asymmetry/alignment tests.
3. In parallel, revised Q3a adapter and 15 offline cells (13 cropped + two full-FOV
   references), WO-13 TCP/frame-size telemetry, WO-12 stock-codec report and WO-11
   dual-stream design only. See active plan for exact rates/presets/formats.
4. WO-8 on WO-10: upstream light, medium/h264fit, area prefilter, smooth peripheral
   softness and blur-only; shared live/frame-bank mapping and filter with CPU parity
   checks. Every runtime feature default-off; own codex branch and green CI per WO.
   Merged as `55bb65b` after [full CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37167562493)
   on resolved source `e61621d`, including actual WARP/software-GLES checks.
5. Merge WO-8, then Q3b's ten offline cells; report both frame windows, centre and
   periphery, sharp/matching-blur comparisons and crop bands. Publish JSON + Markdown
   ranked by fence metrics then HVS. Preserve exact build/source/tool provenance.
6. When Q3a/Q3b and WO-10/8/13 are complete, build a stable-signed matching pair per
   BUILD.md, verify without installing; write Q4 and cells a–h exact settings and
   rollback checklist, then stop for the owner. WO-6 stays deferred unless CDF wins
   and crop/foveation later misses the live 11.1-ms budget.

## Active notes for Codex (2026-10-04)

- Current-session owner authorization covers supervised offline PC leases only for
  fence metrics, Q3a and Q3b. Keep ComfyUI idle and all existing quality safety stops;
  do not touch arm, headset, VR apps, VD, router/network, settings or installed pair.
- Earlier Q3 16-cell plan is obsolete. Drop HEVC/AV1 above 200 Mbps; include H.264
  per-eye and 10-bit HEVC/AV1 plus the exact crop/foveation candidates in the plan.
- Owner's FOV claim is an input requiring later headset confirmation. Record crop
  offsets and excluded fixed regions, preserve Godlike density, and mirror eyes.
- The fence dominates: single-frame averages do not establish temporal stability.
  Preserve measured GPU execution/completion, fresh submissions and optical FPS as
  separate quantities; prior ~82–83/s is not a 90-Hz pass.
- Q1/Q2: full-size Haar/1000 trails 5/3/500 by 0.43 HVS dB and 9/7/500 by 0.98;
  reduced-size Haar's gain includes optimistic Lanczos smoothing. No defaults promoted.
- An owner-dependent blocker must be written here and work stopped for the owner.

## Previous queue (historical)

Take the first unblocked item. Items marked ∥ are independent.

1. **WO-0** unattended supervisor: prerequisite for every unattended hardware step.
2. ∥ **WO-1** offline frame-bank harness: code and CPU tests. Running it needs the owner's
   Metro dump (owner task 3).
3. ∥ **WO-2** render/encode geometry controls, profiles and runbook.
4. ∥ **WO-3** flat-field charts and the HEVC panel-mura control.
5. ∥ **WO-9** decoder-plan quality-track section, committing these docs.
6. **Hardware, first armed window:**
   - WO-3 flat-field PyroWave-vs-HEVC cells;
   - WO-2 chart geometry A/B/A (3072 / 2560 / 2080 encode, Haar, 500 Mbps);
   - an encoder-timeout reproduction attempt with log and workload capture.
7. **WO-4** compositor layer filter, then an unattended off/on/off.
8. **WO-5** PC downscale and dither, then an unattended off/on/off.
9. **Gated on WO-1 results:** WO-6 (fast 5/3), WO-7 (RDO viewing density) and WO-8
   (light peripheral encoding).

## Owner tasks

1. **Before the first window:**
   - Put the Quest on a stable surface on USB power, with the lenses shielded from
     direct sunlight. Sunlight through the lenses can damage the displays.
   - Leave the PC on, Codex open, SteamVR and ALVR installed, and ComfyUI idle.
2. **Arm windows** (section 1 of [UNATTENDED.md](UNATTENDED.md)), once WO-0 has landed.
   A nightly schedule means you arm once.
3. **Metro frame dump** (supervised, about 5 minutes), once WO-1 has landed. Play to the
   fixed checkpoint with the dump trigger armed, so the harness gets real game frames.
4. **Final sign-off** session for the profile the goal selects.

## Notes for Codex

- 2026-10-02 (Claude): start with WO-0, WO-1, WO-2, WO-3 and WO-9. Do not open a hardware
  window until WO-0's restorer and monitor are merged and dry-run tested. Keep each work
  order to one reviewable PR.

- Historical note, superseded by the current Q1–Q4 queue; it grants no standing lease.

- 2026-10-03 09:40 (Claude, relaying the owner): **owner-supervised session now.**
  The owner is present, has confirmed Virtual Desktop is disconnected, and asked for
  testing to start without an arm window. This is AGENTS.md rule (a), a supervised
  session, not an unattended window. Do not create or edit the arm file. Priority is
  the first real Metro frame-bank numbers.
  1. Add a small supervised lease (for example `unattended.py supervise --owner-attested
     "<owner quote + time>" --allow frame_bank_pc --hours 4`) that `WindowGuard`
     accepts. Keep the competing-GPU monitor, the stop marker and job registration.
     Skip the arm, owner-idle, headset battery/ADB and VD gates: none of them protect
     a PC-only encode/decode job. This is a Python-only tools change: local CPU tests
     plus the CPU CI job are enough. Do not wait for a new signed Android/Windows pair.
  2. Run the HVS GPU sanity gate. Then run the frozen matrix in two passes:
     - Pass 1: 500 Mbps × {haar, 53, 97} × {3072, 2560, 2080} on all 90 frames.
       Post its table here before continuing.
     - Pass 2: the remaining 27 cells.
  3. Run no headset cells while the frame bank uses the GPU. Afterwards, with the owner
     present, run the flat-field PyroWave-vs-HEVC control and the chart geometry A/B/A
     with the existing control tools. The unattended chart controller does not exist yet.
  4. Later, not now: scope preconditions by `allow`. Replace the VD log heuristic: an
     unknown state currently counts as connected, and the substring "connected" also
     matches unrelated lines. Use video-encode engine activity plus exact log patterns.
  5. Keep ceremony proportional: one evidence record per real measurement, with no
     checkpoint-only records.

## Log

- 2026-10-05 05:14 UTC, final overnight PC-only quality publication: 19 new qualified
  rows, selected retained controls, regional comparisons, temporal negatives,
  CPU source/latency/entropy studies and 7 CPU CI receipts are published in
  [the combined report](../results/metro-overnight-quality-2026-10-05.md).
  The final Light and Medium 5/3 leases closed cleanly; no timing qualification,
  headset/installation/settings/arm action or default promotion. Full-FOV
  pre-encode motion stress remains unrun and is explicitly separate from the
  post-decode private preview. Corrected 0f07f05 pair staged; rollback intact.
  Checklist updated; stopped for owner review.


- 2026-10-04 19:34 UTC, supervised headset preparation only: reverified and
  separately staged 80a1635, preserved d1c3 rollback, added a2 and exact owner
  judgement phases, and passed eight private guard CPU tests. No hardware,
  install, settings or arm operation occurred; begin confirmation is pending.
  Source review found the release C API suppresses the live RDO marker; a/a2/d
  native-proof gates are blocked on this pair. Offline direct-Encoder logs and
  Q3 scores remain valid. A separate read-only observability proposal is being
  prepared; no automatic pair substitution. See the current checkpoint and
  [checklist](Q3-HEADSET-CHECKLIST.md).

- 2026-10-04 08:37 UTC, Q3b NVENC resume safety stop: the earlier first H.264
  attempt stopped during CPU preparation at 63/90 frames when a newly started
  ComfyUI process had an unavailable queue endpoint. No encoded bitstream was
  produced; its lease closed with zero jobs/errors. Two subsequent read-only
  queue checks showed known idle (0 running, 0 pending), so the original finite
  owner-supervised authorization was used for a fresh attempt. Its preflight
  instead observed **known active ComfyUI (1 running, 0 pending)** and **599 MiB
  free VRAM**, below the 2048 MiB margin. This is a compute/VRAM safety stop,
  not an inference from overall GPU utilization or desktop/browser activity.
  No codec job began; the lease closed with zero owned jobs and no cleanup errors.
  Source, protected modules, controller and frozen plan identities are retained;
  partial failed attempts remain private and excluded from scores.
  [Sanitized evidence](../results/q3b-resume-blocked-2026-10-04.json).
  All 15 Q3a and eight Pyro Q3b cells remain complete; their eight-row Q3b
  publication preflight also passed provenance, both-window and privacy checks.
  Only H264Fit/single-H.264 and blur-only-Light/dual-H.264 remain. Owner action
  is required to idle ComfyUI and release GPU memory before a new guarded attempt.
  Combined 25-row publication, final stable-signed pair and final headset checklist
  remain outstanding. No headset, VR apps, settings, network, arm-file or installed
  pair changes occurred. No profile or 90-Hz result is promoted.

<!-- Codex appends entries here: date, checkpoint, verified (links), remaining, blocked? -->

- 2026-10-04 08:15 UTC, blur-only Light / CDF 9/7 / 1000 Mbps / softness
  0.5 completed. All 90 ordered decoded/Q3b identity records, both score
  windows, source/corpus/projection/scorer provenance and clean lease closures
  pass publisher validation. It retains 2624×2776 encoded pixels per eye;
  it is a full-dimension quality diagnostic, not the reduced Light geometry.

  | CDF 9/7 / 1000 Mbps profile | Encoded pixels / eye | Fence edge PSNR-Y, 10–89 | Temporal mean | Temporal p99 | Whole-image HVS, all-90 |
  |---|---|---:|---:|---:|---:|
  | Cropped, no foveation | 2624×2776 | 35.753751 dB | 3.300473 | 19 | 39.904984 dB |
  | Reduced Light, softness 0.5 | 2464×2592 | 30.832637 dB | 5.327900 | 32 | 37.741237 dB |
  | Blur-only Light, softness 0.5 | 2624×2776 | 35.741924 dB | 3.293609 | 19 | 39.640497 dB |

  These fence and expanded whole-image comparisons have common score domains.
  Blur-only gains 4.909286 dB fence PSNR and 1.899260 dB whole-image HVS
  all-90 versus reduced Light, but versus unfoveated cropped 9/7 it changes
  fence PSNR by −0.011828 dB and leaves temporal p99 at 19. Whole-image HVS
  falls by 0.264488 dB all-90 / 0.270312 dB trimmed versus unfoveated 9/7.
  Fixed-crop trimmed HVS changes versus reduced Light / unfoveated 9/7:
  UI +1.184458 / +0.147972 dB, tunnel +1.359837 / +0.107470 dB, rail
  +1.580445 / −0.030542 dB. This does not establish reduced Light equivalence,
  a decoder-workload reduction, or a live timing/90-Hz result. No promotion.

  Blur-only centre ROI (188,200,2248×2376) and peripheral mask (1,938,480
  pixels, blur_only true) differ from reduced Light (264,280,2112×2218;
  2,595,584 pixels). Treat these as separate diagnostics: blur-only centre
  sharp/matching-blur HVS is 39.637470 / 39.641516 dB in 10–89; peripheral
  sharp edge PSNR/temporal mean/p99 is 35.653516 / 2.923335 / 19, and
  matching-blur is 39.678003 / 1.956875 / 12. Temporal metrics are file-order
  luma residuals, not optical shimmer. Private controller report SHA256:
  `db0b88e475656d594f6e40c34c16b169f3d3207437b7078542647d7e7d7c1c63`.
  All eight PyroWave Q3b rows and 23 of 25 Q3 rows are complete. The existing
  controller has started H264Fit / single H.264 / 700 / P7 / softness 0.5;
  the dual H.264 blur-only row follows. Both retain finite quality leases.
  Combined publication, verified stable pair and owner checklist remain.
  No owner blocker or headset/settings/arm/installed-pair change.

- 2026-10-04 07:38 UTC, H264Fit / PyroWave CDF 9/7 / 1000 Mbps / softness
  0.5 completed. H264Fit names the transform profile here; this is not an H.264
  codec result. All 90 ordered decoded/Q3b identity records, both score windows,
  source/corpus/projection/scorer provenance and clean lease closures pass
  publisher validation. Encoded geometry is 1984×2112/eye; expanded scoring
  remains 2624×2776/eye. Its reduced input intentionally differs from Medium.

  | CDF 9/7 / 1000 Mbps profile | Fence edge PSNR-Y, 10–89 | Temporal mean | Temporal p99 | Whole-image HVS, all-90 |
  |---|---:|---:|---:|---:|
  | Cropped, no foveation | 35.753751 dB | 3.300473 | 19 | 39.904984 dB |
  | Medium, softness 0.5 | 37.543370 dB | 2.605163 | 15.32 | 36.261744 dB |
  | H264Fit, softness 0.5 | 38.367520 dB | 2.371167 | 14 | 35.755413 dB |

  In the same fence domain, H264Fit gains 0.824150 dB versus Medium and
  2.613769 dB versus unfoveated cropped 9/7, while whole-image all-90 HVS
  falls by 0.506331 / 4.149572 dB respectively. Trimmed whole-image HVS is
  35.568106 dB. Fixed-crop trimmed HVS: UI 43.181572, tunnel 42.476398,
  rail 35.617941 dB. Versus Medium these change by +1.577465, +1.316449,
  −0.667202 dB; versus unfoveated 9/7, +5.533141, +4.447747, −4.206740 dB.
  This remains a fence/detail tradeoff, not an overall promotion or timing pass.

  H264Fit's centre ROI (660,700,1322×1408) and peripheral mask (5,418,794
  pixels) differ from Medium's (528,560,1582×1678; 4,624,784 pixels). Their
  diagnostics therefore are not matched-domain cross-profile gains. Separately,
  H264Fit centre sharp/matching-blur HVS is 42.877135 / 42.978041 dB in
  10–89; peripheral sharp edge PSNR/temporal mean/p99 is 30.808949 /
  5.211691 / 33, and matching-blur is 42.954350 / 1.397708 / 8. Temporal
  metrics remain file-order luma residuals, not optical shimmer.
  Private controller report SHA256:
  `30b2115c30536a50ca0d15941d349d26a15279ab7f69655374a6b91630e429c9`.
  Twenty-two of 25 Q3 rows are complete. The existing controller advanced to
  blur-only Light / 9/7 / 1000 / softness 0.5; that cell and two NVENC H.264
  rows remain before combined publication, the verified stable pair and final
  owner checklist. No owner blocker or headset/settings/arm/installed-pair change.

- 2026-10-04 07:05 UTC, Medium wavelet comparison completed: the 5/3 and 9/7
  cells use identical reduced input, all 90 source/encoded-reference/sharp/blur
  frame identities, transform, fence, centre ROI, peripheral descriptor and
  corpus/projection/scorer provenance. Both score windows and clean lease
  closures pass the private publisher's validation. Encoded geometry is
  2112×2240/eye; expanded scoring remains 2624×2776/eye.

  | Medium / 1000 Mbps / softness 0.5 | CDF 5/3 | CDF 9/7 |
  |---|---:|---:|
  | Fence edge PSNR-Y, 10–89 | 36.150850 dB | 37.543370 dB |
  | Fence temporal mean / p99 | 2.889889 / 18 | 2.605163 / 15.32 |
  | Whole-image HVS, all-90 | 36.013034 dB | 36.261744 dB |
  | Whole-image HVS, 10–89 | 35.824581 dB | 36.078479 dB |
  | Peripheral sharp edge PSNR-Y, 10–89 | 30.657437 dB | 30.854177 dB |
  | Peripheral sharp temporal mean / p99 | 5.413821 / 34 | 5.288778 / 33 |
  | Peripheral matching-blur edge PSNR-Y, 10–89 | 40.388626 dB | 41.683527 dB |
  | Peripheral matching-blur temporal mean / p99 | 1.814631 / 11 | 1.621190 / 10 |
  | Centre sharp HVS, 10–89 | 40.736892 dB | 41.498037 dB |
  | Centre matching-blur HVS, 10–89 | 40.786983 dB | 41.554029 dB |

  CDF 9/7 improves the matched fence by 1.392520 dB and whole-image HVS by
  0.248710 dB all-90 / 0.253898 dB trimmed. Temporal values are luma residual
  codes; the fractional p99 is retained rather than rounded to an integer.
  Compared with Light 9/7, Medium 9/7 gains 6.710732 dB on the same fence but
  loses 1.479493 dB whole-image HVS (all-90). Versus unfoveated cropped 9/7,
  it gains 1.789618 dB fence PSNR but loses 3.643241 dB whole-image HVS.
  Fixed-crop trimmed HVS changes versus Light / unfoveated 9/7 respectively:
  UI +4.992162 / +3.955675 dB, tunnel +4.383665 / +3.131298 dB, rail
  −1.928551 / −3.539538 dB. These cross-profile comparisons have common
  fence, expanded whole-image and fixed-crop domains; centre/peripheral domains
  differ across profiles and must not be treated as matched gains.
  This favors 9/7 within Medium on the measured quality metrics, but does not
  promote Medium overall or establish any Quest decoder-speed or 90-Hz claim.
  Private controller report SHA256:
  `ea7dbf1145bbd6c1ba9cce66d8884444a29ed0eac90210077bfd703fefe95e5f`.
  Twenty-one of 25 Q3 rows are complete. The existing controller has advanced
  to H264Fit / 9/7 / 1000 / softness 0.5. Four Q3b cells, combined publication,
  verified stable pair and owner checklist remain. No owner blocker or headset,
  settings, arm-file or installed-pair change.

- 2026-10-04 06:26 UTC, first Medium result completed: CDF 5/3 / 1000 Mbps /
  softness 0.5 at 2112×2240 encoded pixels per eye, reconstructed to the same
  2624×2776/eye score domain. All 90 decoded and Q3b frame identities, both
  score windows, source/corpus/projection/scorer provenance and clean lease
  closure pass validation. Its reduced input differs intentionally from Light.

  | CDF 5/3 / 1000 Mbps profile | Fence edge PSNR-Y, 10–89 | Temporal mean | Temporal p99 | Whole-image HVS, all-90 |
  |---|---:|---:|---:|---:|
  | Cropped, no foveation | 34.288280 dB | 3.702805 | 22 | 39.166110 dB |
  | Light, softness 0.5 | 30.451866 dB | 5.615133 | 33 | 37.285790 dB |
  | Medium, softness 0.5 | 36.150850 dB | 2.889889 | 18 | 36.013034 dB |

  These primary-fence and expanded whole-image comparisons share source region,
  projection/calibration and windows. Medium improves fence edge PSNR by
  5.698983 dB versus Light and 1.862569 dB versus unfoveated cropped 5/3, but
  loses 1.272757 / 3.153077 dB whole-image HVS respectively (all-90). Fixed-crop
  HVS in 10–89, Medium versus Light: UI 40.916910 / 36.049553, tunnel
  40.264840 / 36.176446, rail 35.881996 / 37.460108 dB. This is a quality
  tradeoff, not an overall promotion or a Quest timing result.
  Medium's centre ROI (528,560,1582×1678) and peripheral mask (4,624,784 pixels)
  differ from Light's (264,280,2112×2218; 2,595,584 pixels). Do not interpret
  cross-profile centre/peripheral scores as matched-domain gains. Separately,
  Medium centre sharp/matching-blur HVS is 40.736892 / 40.786983 dB in 10–89;
  its peripheral sharp edge PSNR/temporal mean/p99 is 30.657437 / 5.413821 / 34,
  and matching-blur is 40.388626 / 1.814631 / 11. The private publisher now
  explicitly states this domain qualification; metric calculations, ranking,
  provenance gates and the live harness are unchanged. Python compilation passes.
  Private controller report SHA256:
  `dcb23cce8f8dd228e77bde956d7b6a258ad61d9a768a1c2c8ebcdc56b28cca6f`.
  Twenty of 25 Q3 rows are complete. Medium / CDF 9/7 is running; five Q3b
  cells, combined publication, verified stable pair and owner checklist remain.
  No owner blocker or headset/settings/installed-pair change.

- 2026-10-04, CPU-only mapping preflight for the pending Q3b geometries:
  at source revision `e61621ddd4f4e8b38c392e481f22e677446f8d54`, the allocation
  and mapping algebra in `tools/xrbench/foveation.py:48–85` puts the entire
  primary left-eye fence (1462,1036,240,274) inside the aligned central band
  for both Medium and H264Fit. Medium's source bands are X [526,2098] and
  Y [556,2220]; H264Fit's are X [656,1968] and Y [694,2082]. Representative
  encoded pixel centres (1319.5,895.5) for Medium and (1254.5,826.5) for
  H264Fit map to source (1582.5,1173.5). Both predict texel-centred sampling,
  local squeeze 1, zero softness ramp and a 1×1 footprint on this fence.
  Blur-only Light uses the identity map and likewise predicts no geometric
  filtering within this ROI. These float64 calculations have roundoff of
  approximately 2.3e-13 pixels; they are not GPU pixel measurements.
  This differs from the reduced Light path's central horizontal half-sample
  phase. Do not transfer its measured loss to these pending profiles or infer
  a winner from algebra. No frames were transformed/scored, no GPU work was
  added and the frozen matrix is unchanged. Private calculation SHA256:
  `1f08355d1122ba0da7aa9716a1512488cd4af8ebaeb7249ea5e04e42022ffb89`.

- 2026-10-04 05:48 UTC, Light wavelet comparison completed: CDF 5/3 and CDF 9/7
  at 1000 Mbps / softness 0.5 use identical transformed inputs, reference frame
  identities, geometry, projection, corpus and scorer. The reduced-source SHA256
  is `d1196cdc356f6c36f3816405f0aeb0ab950a28b2c1c6db35e96404f6f591514c`;
  both contain 90 frames with identity SHA256
  `677bba9eb8bf9c6ada570fa07eb87c656d4d75f8f0a2b0f9732bb2c87eabe5ab`.
  Both score windows and clean lease closures pass publication checks; decoded
  payloads differ as expected for the wavelet change.

  | Light / 1000 Mbps / softness 0.5 | CDF 9/7 | CDF 5/3 |
  |---|---:|---:|
  | Fence edge PSNR-Y, 10–89 | 30.832637 dB | 30.451866 dB |
  | Fence temporal mean / p99 | 5.327900 / 32 | 5.615133 / 33 |
  | Peripheral sharp edge PSNR-Y | 32.620879 dB | 32.274144 dB |
  | Peripheral sharp temporal mean / p99 | 4.424289 / 26 | 4.619353 / 27 |
  | Peripheral matching-blur edge PSNR-Y | 41.495943 dB | 40.194070 dB |
  | Peripheral matching-blur temporal mean / p99 | 1.654715 / 10 | 1.883143 / 11 |
  | Centre sharp HVS, 10–89 | 38.589534 dB | 37.981399 dB |
  | Centre matching-blur HVS, 10–89 | 42.455854 dB | 41.579830 dB |

  Fence/peripheral values use frames 10–89; temporal values are luma residual
  codes, not optical shimmer. CDF 5/3 loses 0.455447 dB whole-image HVS across
  all 90 frames and 0.457824 dB in 10–89. Centre sharp HVS changes by −0.609990
  dB all-90 / −0.608135 dB trimmed. This favors 9/7 on the measured quality
  metrics for this geometry; it establishes no Quest decoder-speed comparison.
  CDF 5/3 private controller report SHA256:
  `88e33b30ee7f5149750a42055631fb2d4618221a8cb0fafa63a53047d5dfcc9e`.
  Nineteen of 25 Q3 rows are complete. The existing controller has advanced to
  Medium / CDF 5/3 / 1000 Mbps / softness 0.5. Six Q3b cells, final combined
  publication, verified stable pair and owner checklist remain. No owner blocker
  or headset/settings/installed-pair change.

- 2026-10-04 05:01 UTC, three-way Light softness comparison completed: all three
  CDF 9/7 / 1000 Mbps rows contain 90 ordered decoded identities and 90 ordered
  source/transform/reconstruction identities, both score windows and matching
  source/corpus/projection/scorer provenance. All leases closed with zero jobs
  and no cleanup errors. Encoded geometry is 2464×2592/eye; expanded score space
  is 2624×2776/eye. These are offline quality results, not live timing evidence.

  | Light softness | Fence edge PSNR-Y, 10–89 | Fence temporal p99 | Peripheral sharp edge PSNR-Y | Sharp temporal p99 | Peripheral matching-blur edge PSNR-Y | Blur temporal p99 | Centre sharp HVS change vs softness 0, 10–89 |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | 0 | 30.831871 dB | 32 | 33.522726 dB | 24 | 40.998956 dB | 10 | 0 dB |
  | 0.5 | 30.832637 dB | 32 | 32.620879 dB | 26 | 41.495943 dB | 10 | +0.009158 dB |
  | 1 | 30.833070 dB | 32 | 31.916966 dB | 29 | 42.056622 dB | 9 | +0.015855 dB |

  Peripheral columns also use frames 10–89; temporal values are luma residual
  codes, not optical shimmer. Softness 1 has fence temporal mean 5.326945;
  peripheral means are 4.754562 against sharp and 1.561958 against matching blur.
  Centre sharp HVS is 38.861595 dB across all 90 and 38.596231 dB in 10–89:
  cross-cell changes versus softness 0 are +0.015391 / +0.015855 dB respectively.
  Its same-output sharp-minus-matching-blur centre differences are separately
  −3.841910 / −3.870023 dB. Increasing softness does not resolve the fence loss;
  improved matching-blur scores accompany worse peripheral sharp-reference
  scores. Preserve the documented texel-centre alignment investigation. No promotion.
  Softness-1 private controller report SHA256:
  `71a935af63cb64d1b43da97a35237432f100b1709154cca15290cbf7e4811bfb`.
  Eighteen of 25 Q3 rows are complete. The existing controller has continued to
  Light / CDF 5/3 / 1000 Mbps / softness 0.5; seven Q3b cells, combined publication,
  verified stable pair and final owner checklist remain. No owner blocker or
  headset/settings/installed-pair change.

- 2026-10-04, second Q3b result: Light / CDF 9/7 / 1000 Mbps / softness 0.5
  completed all 90 frames at the same geometry as softness 0. Both score windows,
  frame-identity chains, source/build provenance and clean lease closure pass
  publication checks. Tight fence (10–89): 30.832637 dB, temporal residual mean
  5.327900 and p99 32. Versus softness 0, edge PSNR changes by +0.000766 dB and
  temporal p99 is unchanged. Centre sharp-reference HVS changes by +0.009158 dB
  in 10–89 (+0.008891 dB across all 90). Peripheral sharp-reference edge PSNR
  falls by 0.901847 dB to 32.620879, with temporal p99 rising from 24 to 26;
  matching-blur edge PSNR rises by 0.496987 dB to 41.495943, p99 remains 10.
  These two reference domains must stay separate. Whole-image all-90 HVS is
  37.741237 dB / VMAF 93.441130. No profile promoted.
  Private controller report SHA256:
  `e7383074a656c4c031cda7a9de03f4a31e5219ae48b738f7bebe4b01abe2a562`.
  The private publisher now reads the requested softness from its nested
  transform-provenance object; a focused nested-selector CPU test passes and
  the complete eight-Pyro-row requirement is retained. Seventeen of 25 Q3 rows
  are complete. The softness-1 cell is running; eight Q3b rows, combined
  publication, the final signed pair and owner checklist remain. No owner blocker.

- 2026-10-04, Light/softness-0 attribution (CPU-only, retained frames): the
  frozen sharp-source edge mask over frames 10–89 is reproduced exactly
  (259,812 selected pixels). Tight-fence PSNR is 32.066930 dB for sharp source
  versus matching-blur reference, 39.424019 dB for matching-blur versus decoded
  reconstruction, and 30.831871 dB for sharp versus reconstruction. These are
  spatial errors on the same mask, not temporal percentiles; PSNR components
  cannot be added. Substantial loss therefore exists before compression.
  The fence is fully inside the aligned central band, with local squeeze 1.
  For the 2624×2776 → 2464×2592 Light geometry, horizontal encoded pixel centres
  map to source pixel boundaries, while vertical centres remain aligned. The
  area box averages horizontal neighbours even at softness 0. See source at
  `7437279`: [alignment and sampling](../tools/xrbench/foveation.py#L48) and
  [native shader box sampling](../patches/wo8-foveation.patch#L276).
  This is consistent with the current shader algebra, not evidence of a
  CPU/shader or eye/crop mismatch. Audit texel-centre alignment before accepting
  this Light profile; leave the frozen Q3b matrix unchanged for comparison.
  Private diagnostic SHA256:
  `33aa801d365753d08caa177f8a7e122d09bc54646a5d6307e7e30f2ee05ed4bb`.
  No encode, decode, transform or GPU scorer was rerun for this attribution.

- 2026-10-04 03:36 UTC, first Q3b result: Light / CDF 9/7 / 1000 Mbps,
  softness 0, 2464×2592 encoded per eye, reconstructed to 2624×2776 per eye.
  All 90 frames completed; both score windows, sharp/matching-blur references,
  centre/periphery and frame-identity chains pass publication validation.
  Primary fence (10–89): edge PSNR 30.831871 dB, temporal residual mean 5.330430
  and p99 32 luma codes. Whole-image all-90 HVS is 38.110736 dB / VMAF 93.872773.
  This loses to cropped 9/7 without foveation on the fence; no profile promoted.
  The real three-worker reduced/blur first-frame payloads exactly match the
  retained earlier attempts, and the sharp first frame matches the cropped source.
  Private controller report SHA256:
  `e13177c4f7f28ac580c6c217b809bbe9615c6ead4921962eb81dc7450ca9c663`.
  Lease closed with zero jobs and no cleanup errors. The private publisher was
  corrected to read matching peripheral descriptors from each reference result;
  a missing-descriptor negative test rejects, and the final eight-Pyro-row gate
  remains unchanged. The next Light/softness-0.5 cell is running; nine Q3b rows,
  combined publication, final signed pair and owner checklist remain. No owner
  blocker, headset action or settings change.

- 2026-10-04, offline matrix and native source checkpoint:
  [WO-10 PR 25](https://github.com/ljk1291/Quest3-Pyrowave/pull/25) merged as
  `5659c55` after [full CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37164210397).
  [Native CLI timing PR 32](https://github.com/ljk1291/Quest3-Pyrowave/pull/32)
  merged as `8feaa1c` after [full CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37164304925).
  Its downloaded frame-bank tools verify against metadata commit `552bbe942b917935608f7dedfc0d1a8c82c96b1e`
  (CI's synthetic PR merge); archive SHA256
  `2cd6c2cd2f507d6cce4587a66628561fd74c267de555a422fd1912b36bd777a0`.
  The retained HVS scorer has the same verified source implementation and will
  remain the comparison scorer; split bundle identity is explicit. Nothing was
  installed. Q3a score-only recovery finished its first cell and the remaining
  NVENC matrix is progressing under the quality lease with no safety stop.
  [Q3b PR 36](https://github.com/ljk1291/Quest3-Pyrowave/pull/36) at `00aeeac`
  passed [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37165790232).
  It waits for WO-8 integration and closure of the current frozen harness.
  [Score-reuse PR 37](https://github.com/ljk1291/Quest3-Pyrowave/pull/37)
  proves exact input/header/calibration identity before reusing duplicate crop
  scores; 68 local CPU tests and independent review pass, CPU CI pending.
  Neither change alters the active matrix. Final Q3 tables, WO-8 native CI,
  signed matching pair and owner checklist remain; no owner blocker.

- 2026-10-04, Q3a guard repairs and Pyro adapter boundary review:
  [PR 33](https://github.com/ljk1291/Quest3-Pyrowave/pull/33) merged as `cdc55b9`
  after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37164586939).
  The retry then identified a Git file scan mentioning ComfyUI as a backend;
  [PR 34](https://github.com/ljk1291/Quest3-Pyrowave/pull/34) fixes executable and
  entry-point recognition. Its follow-up [PR 35](https://github.com/ljk1291/Quest3-Pyrowave/pull/35)
  distinguishes unreadable Python arguments from actual per-PID GPU compute
  evidence, with 30 targeted tests and [green CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37165108956).
  Unknown process-inventory failures, active compute backends, the VRAM margin,
  driver faults and stop marker remain enforced. Both stopped retries report
  closed leases, zero owned jobs and no cleanup errors. A fourth finite attempt
  is rescoring the same retained H.264 encode before the remaining nine cells.
  [PR 31](https://github.com/ljk1291/Quest3-Pyrowave/pull/31) merged as `eb2332b`
  after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37164918510),
  including the corrected full-parent crop-coordinate builder. The subsequent
  Q3b review is correcting shared scorer/tool boundaries, peripheral masks and
  per-frame provenance before any Pyro Q3 or foveation GPU trial. Native
  WO-10/WO-8/timing CI remains required; no headset or installed-pair changes.

- 2026-10-04, Q3a scoring recovery and WO-13 merge: both 400-Mbps-total H.264
  eye streams completed with 90 verified decodes; scoring stopped after the first
  HVS score because the supervised monitor's atomic state replacement raised
  WinError 5. The stop marker is present; a process inventory confirms both the
  parent and monitor exited, and the registry contains no jobs. The original
  failure remains private evidence. [PR 33](https://github.com/ljk1291/Quest3-Pyrowave/pull/33)
  adds bounded replacement retries and independent parent cleanup; 51 local CPU
  unittest and 108 unattended pytest cases pass, with CPU CI pending. Recovery
  verifies all 90 retained reference/decoded frame hashes and both bitstreams
  before scoring them under a new finite lease; only the other nine NVENC cells
  need encoding. No owner input is required for this tooling repair.
  [WO-13 PR 24](https://github.com/ljk1291/Quest3-Pyrowave/pull/24) merged as
  `1b7af8895ba8558a749528f85749b309c3b9aba3`: native CI at `89dbea86` and
  [integration CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37164227418)
  at `47f7a5f3` pass; the integration follow-up changed no native/network source.
  No network or headset test was run, and no settings or installed pair changed.

- 2026-10-02, checkpoint WO-9/source preparation: adopted the owner’s goal,
  work orders and unattended rules; appended the decoder plan’s quality track
  without rewriting existing evidence. Separate WO-0/1/2/3 branches are in
  progress. No arm file exists, so no unattended hardware action is authorized;
  the Metro frame bank is also awaiting its supervised owner dump. These do not
  block source/CPU work. CI/PR evidence will follow; the goal remains active.

- 2026-10-03, checkpoint WO-9 and supervised capture attempt:
  [WO-9 PR](https://github.com/ljk1291/Quest3-Pyrowave/pull/2) merged into
  `codex/artifact-quality` after its [full CI run](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37069418425)
  passed. [WO-3 PR](https://github.com/ljk1291/Quest3-Pyrowave/pull/3) is building.
  The owner had five minutes; the existing signed d1 pair was verified and used
  under a 270-second independent rollback guard. ComfyUI initially blocked setup,
  then became idle. The owner reported a disconnect after Metro launched; no
  checkpoint or source frames were captured. Stored negotiated settings had
  been checked, but a fresh stream had not, so this is an invalid quality/rate
  attempt. The retained timeout entry was Session 07's, not a newly proved
  encoder fault. All saved files, driver inventory, headset properties and VD
  hashes matched after rollback. [Sanitized result](../results/supervised-framebank-attempt-2026-10-03.json).
  Next supervised capture must prove Streaming and changing selected-output
  telemetry before Metro. WO-0/1/2/4/5 source review continues; no arm file exists.
  Metro dump and headset judgement remain owner tasks; source work is unblocked.

- 2026-10-03, checkpoint supervised Metro source capture:
  The owner confirmed the checkpoint scene was visible. The unchanged signed
  d1 pair saved **90 complete native encoder-input frames** at 6144×3232 stereo,
  8-bit 4:2:0, full range, with the Godlike-sized / Haar / 500 Mbps / requested
  90 Hz profile. A fresh client `Streaming` state was verified before Metro
  launched; the saved client entry was temporarily trusted and restored.
  The independent 270-second guard ended the session and verified all saved
  files, headset properties, runtime registration and VD hashes. The dump has
  89 distinct raw-frame hashes, contiguous encoder indices, and two repeated
  or decreasing display timestamps. Preserve its file order for same-input
  comparisons; the dump is **not** evidence of fresh 90 Hz or optical FPS.
  [Sanitized capture record](../results/metro-source-capture-2026-10-03.json).
  WO-1 now accepts the actual native C420 format rather than forcing 4:4:4.
  Fixed crops and projection evidence still need freezing, and GPU scoring
  remains queued for a valid owner-armed `frame_bank_pc` window after WO-0.
  No arm file exists and no further hardware test is running. Source work is
  unblocked; no optimization or stable-rate profile has been promoted.

- 2026-10-03, checkpoint source review and owner duration approval:
  The owner reports clear compression in the new Metro capture. Inspection of
  source frames 0/44/89 confirms tunnel detail and a later menu-board view;
  these are encoder-input planes, so paired decoded frames are still required
  to attribute codec damage. [Review boundaries](../results/metro-capture-visual-review-2026-10-03.json).
  [WO-3](https://github.com/ljk1291/Quest3-Pyrowave/pull/3),
  [the capture record](https://github.com/ljk1291/Quest3-Pyrowave/pull/4),
  [WO-2](https://github.com/ljk1291/Quest3-Pyrowave/pull/5) and
  [WO-5](https://github.com/ljk1291/Quest3-Pyrowave/pull/7) have merged into the
  experimental integration branch after their full workflows passed; relevant
  [geometry CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37074406100)
  and [PC-filter CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37076371392).
  WO-5's shader checks include tiny software-WARP pixel readbacks and preserve
  the default shader binaries; no Quest improvement is proved. WO-4 is still
  building. WO-1 now requires actual selected crop rectangles and packages
  pinned offline codec tools plus a separately calibrated HVS scorer; source
  review and CI remain. WO-0's cross-process mutation/rollback integration
  remains under review.
  An owner arm file now exists for PC frame-bank work. The owner explicitly
  approved its **eight-hour** once interval ending **08:44:31 Europe/Berlin**;
  [the narrow exception](UNATTENDED.md#owner-exception-2026-10-03) is recorded
  without editing that file. Its duration validation and CPU regressions pass.
  No unattended window has opened: WO-0 must first pass review, full CI and its
  dry run. The installed d1 pair, baseline defaults and VD settings are
  unchanged. Source work is unblocked; no optimization has been promoted.

- 2026-10-03, checkpoint guard concurrency and frozen Metro comparison:
  The eight-hour owner exception/source-review record merged after
  [full CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37078606818)
  passed. [WO-0](https://github.com/ljk1291/Quest3-Pyrowave/pull/10) now has 64
  focused CPU regressions, including a settings API update overlapping rollback,
  simultaneous owned-job registration, crash-released locks, repeated restoration,
  failure publication and lost monitor telemetry. After integration, 13 build
  contract checks, 102 repository unit tests and 9 geometry tests also passed.
  Its Actions CPU and Android jobs passed; Windows/full-pair validation and the
  required bounded dry run remain. Global selector changes and guarded
  chart/property/install orchestration are explicit remaining controller work.
  The current arm permits only `frame_bank_pc`.
  [WO-1](https://github.com/ljk1291/Quest3-Pyrowave/pull/8) failed Windows scorer
  preparation in [this run](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37079088302):
  Git found the enclosing fork and silently skipped the scorer patch. A reproduced
  nested-repository regression fixes that scope; 27 focused harness/scorer tests
  now pass. The runner also binds packaged binaries to their commit/dependencies
  and clears inherited codec experiments, requiring activation confirmation.
  [WO-4](https://github.com/ljk1291/Quest3-Pyrowave/pull/6)'s first combined
  build caught a missed shared `stream.rs` constructor change. Its corrected
  cumulative patch includes all four required client files, preserves the other
  WO-5 files and default shader bytes, and passes clean apply/reverse/identity
  checks. Both corrected PRs require new full CI before merge.
  The 90-frame Metro plan is frozen with 36 cells and four reviewed spatial crops.
  It reuses Session 07's measured projection at 24.20 horizontal / 23.56 vertical
  centre px/deg; Session 09 has no separate retained projection measurement.
  [Preparation record and limitations](../results/framebank-preparation-2026-10-03.json).
  No unattended window or codec/scorer workload has started. No quality gain,
  fresh-rate gain or stable 90-Hz pass is claimed. Source/build work is unblocked;
  the goal remains active.

- 2026-10-03, checkpoint exact rollback and native-frame scorer:
  [WO-4](https://github.com/ljk1291/Quest3-Pyrowave/pull/6) merged after
  [all four CI jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37081909500)
  passed; layer filtering remains default-off. The frozen Metro preparation
  record also merged after [full CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37082594282).
  [WO-0](https://github.com/ljk1291/Quest3-Pyrowave/pull/10) now proves exact saved
  ALVR/SteamVR bytes only after owned runtimes stop and all differences match
  recorded changes. It rejects owner drift and corrupt backups, retries a real
  mutex timeout finitely, and retains a process handle through verified cleanup.
  Its PC/install-only arms cannot mutate VR/device settings; runtime manifest
  bytes are checked as well as registration. **82 focused fake-host tests and
  two disposable Windows CPU-child checks pass locally.** Native identity queries
  avoid a shell lookup that could miss short scorer jobs. The earlier 60114c8
  workflow passed; [the final 75c6257 workflow](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37086277788)
  and required armed dry run remain.
  [WO-1](https://github.com/ljk1291/Quest3-Pyrowave/pull/8)'s next real Windows
  failure was [missing FFmpeg/PkgConfig](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37081762449).
  Review additionally found the upstream predictive-video reader discarded
  frame zero. Its isolated raw-Y4M target now retains every frame, extracts the
  pinned HVS functions unchanged, packages their unchanged shader and licenses,
  and binds the PE import inventory to build provenance. The harness requires
  exact scorer frame counts, fresh output directories and a finite owned-GPU
  identity/amplitude sanity gate before Metro scoring. **29 local harness/scorer
  tests pass; three native-reader tests await CI's g++**. [Current Linux and Android
  jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37085826097) passed;
  Windows/full-pair validation remains. The sanity gate has not run on hardware.
  A CPU-only check reverified the retained stable d1 artifact pair and all six
  installed server binaries; it did not re-query/install the Quest APK or start
  VR. The owner's exact eight-hour exception remains recorded, ending 08:44:31
  Europe/Berlin, with only `frame_bank_pc` allowed and the arm file unchanged.
  No unattended window or codec/scorer GPU workload has opened. No quality gain,
  rate gain or stable 90-Hz pass is claimed. Source/build work remains unblocked;
  chart/property/install controller orchestration and global selector support
  remain explicit WO-0 follow-up scope. The goal remains active.

- 2026-10-03, follow-up verification of the scorer and process cleanup:
  WO-1's Linux log confirms all 32 checks passed, including three compiled
  native-reader checks. The next Windows build exposed source templates omitted
  by an overly broad copy exclusion; head `828a12b` preserves those inputs and
  passes 30 local checks (three native-reader checks require CI's compiler).
  No dependency pin changed. WO-0 head `6d7b8cc` also handles an owned child
  that completes before cleanup; all three disposable Windows process checks
  pass. Final-head full CI and the guarded dry run remain required. The owner
  approved the existing eight-hour window, without extending its PC-only scope.
  No hardware workload has started, and no performance or quality gain is claimed.

- 2026-10-03, checkpoint PC-only cleanup and scorer execution prerequisites:
  The preceding documentation checkpoint merged after
  [all four CI jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37088044082)
  passed. WO-0 head `ef9d8b0` retains the arm's action list for restoration:
  a PC-only window verifies headset state without stopping the app or rewriting
  properties. Unexpected drift is preserved and fails verification. **84 focused
  CPU checks and three disposable Windows process checks pass**; its
  [final-head Windows workflow](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37088239058)
  is still running. Merge and the armed bounded dry run remain required.
  WO-1's [next Windows build](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37087256877)
  reached native compilation and exposed a Granite string/C-string API mismatch,
  corrected without changing the metric algorithm, shader or dependency pins.
  Head `c2c49f2` also retains private child logs and ends the matrix on its first
  failed cell. A real three-frame 64×64 CPU FFmpeg identity check exposed null
  optional PSNR-HVS fields; parsing now preserves the separate valid VMAF score,
  while missing VMAF still fails the required-metric gate. **33 local harness/scorer
  checks pass; three native-reader checks require CI's compiler**. The actual CPU
  graph passes with infinite identity PSNR, SSIM 1 and finite VMAF. This checks
  tool availability/parsing, not Metro quality or Quest performance. Final-head
  Windows/full-pair CI and the guarded HVS GPU sanity gate remain.
  The finite PC-only dry-run controller is prepared privately and binds its ALVR
  snapshot to the reverified retained d1 installation. It has not been executed.
  No ADB, unattended window, codec/scorer GPU run or VR launch occurred during this
  checkpoint. The owner's arm remains unchanged and ends 08:44:31 Europe/Berlin.
  Source/build work is unblocked; the goal remains active, with no optimization
  promoted and no new quality, fresh-submission or stable-90-Hz claim.

- 2026-10-03, checkpoint first unattended precondition check:
  WO-0 merged after its [full final-head CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37088239058)
  passed, followed by [green integration CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37089916823).
  The bounded PC dry run refused before opening a window: Android classified
  the charging Quest as AC, NVIDIA listed resident desktop contexts as compute
  processes, and the VD Streamer had no current disconnection record.
  Independent read-only evidence showed charging at 74%, 33 °C, thermal status 0,
  the armed physical USB device present, 539 available Windows engine counters,
  zero active engines and an idle Comfy queue. One Comfy-discovery row was the
  PowerShell probe itself. [Sanitized evidence](../results/unattended-precondition-check-2026-10-03.json).
  [Detector corrections](https://github.com/ljk1291/Quest3-Pyrowave/pull/14)
  require charging/full status plus pinned physical USB proof for AC-labelled
  power, correlate resident processes with actual engine activity, and exclude
  probe shells. Missing activity telemetry and active/unknown Comfy work still
  fail closed. **97 focused CPU checks and four disposable Windows checks pass**;
  full CI remains required before merge. The VD gate stays closed and the owner
  was asked to disconnect/exit its Streamer manually; the agent never stops VD.
  No guard/window, settings mutation, VR launch or GPU workload started. No
  restoration was needed; VD hash verification remains unset for this refused
  attempt. The arm is unchanged. A successful dry run and final scorer CI remain
  prerequisites to Metro scoring. Source/build work is unblocked; the goal
  remains active, with no quality/rate gain or stable-90-Hz pass claimed.

- 2026-10-03, checkpoint actual packaged-tool provenance:
  The precondition evidence checkpoint merged after
  [all four CI jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37091525611)
  passed. WO-1 head `c2c49f2` also passed
  [all four jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37089583733),
  but local verification of its downloaded tools correctly refused execution:
  the Windows tools manifest used a raw CRLF lock hash while build metadata
  used the canonical LF hash. The paired artifacts themselves verified and
  the pinned scorer source manifest matched. [Sanitized actual failure](../results/framebank-tool-preflight-2026-10-03.json).
  Head `366eebb` uses the existing canonical producer and adds CPU-only
  `framebank verify-tools` against the finished Windows package before upload.
  It also retains both CI test lists after resolving the integration conflict.
  **33 local harness/scorer checks and 13 build-contract checks pass**; three
  native-reader checks still require CI's compiler. The corrected-head
  [workflow](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37092386837)
  is building, as is the combined detector source
  [workflow](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37092388291).
  The VD Streamer remains resident with unknown connection state; the existing
  owner request is pending, and its connection gate remains closed. No new
  window, settings mutation, VR launch or GPU workload ran. The eight-hour arm
  is unchanged. Its scope remains PC frame-bank work only, with no default,
  installed-pair, quality, fresh-rate or stable-90-Hz promotion. Source/build
  work is unblocked and the goal remains active.

- 2026-10-03, checkpoint qualified tools and fresh readiness:
  [WO-1](https://github.com/ljk1291/Quest3-Pyrowave/pull/8) merged after
  [all four corrected-head jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37092386837)
  passed. Its downloaded pair passes local artifact checks; the finished tools
  pass their source, shader, binary and dependency verifier, and all three native
  input-only tests pass locally without creating a Vulkan device. The actual
  artifact commit is `9641944`, the tested PR merge of base `29f4d3f` and head
  `366eebb`; retain those separately from final integration merge `9815153`.
  The earlier preflight record's `repository_commit` denoted the CI head
  `c2c49f2`; its actual artifact commit was `6316110`. This clarification leaves
  the original evidence intact. [Qualified tools and readiness record](../results/framebank-tools-qualified-2026-10-03.json).
  [The supervisor corrections](https://github.com/ljk1291/Quest3-Pyrowave/pull/14)
  also merged after [all four jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37092388291)
  passed, including four real Windows CPU-process checks. Integration `bc21788`
  is building in [this workflow](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37094707992).
  Redundant push workflows of the same PR heads were cancelled; the qualified
  PR workflows were retained. The fresh bounded readiness check now refuses
  **only** the VD connection gate. Battery 57%, charging with pinned physical
  USB proof, 37 °C, thermal status 0, owner idle and zero competing GPU activity
  all pass. No snapshot, guard or window opened; no settings mutation, VR launch
  or GPU work occurred, so restoration/VD hash verification remains unset.
  The owner request to disconnect/exit VD Streamer is pending. The arm is
  unchanged and still permits only PC frame-bank work until 08:44:31 Berlin.
  The required successful dry run and GPU scorer sanity gate have not passed.
  No Metro quality improvement, rate gain or stable 90-Hz pass is claimed.
  WO-6/7/8 remain gated on actual WO-1 results; the goal remains active while
  integration CI and the owner-dependent readiness gate remain outstanding.

- 2026-10-03, checkpoint startup publication and signed-build preparation:
  [The qualified-tools record](https://github.com/ljk1291/Quest3-Pyrowave/pull/16)
  merged after [all four PR jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37095245697)
  passed. Integration `bc21788` also passed
  [all four jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37094707992).
  A [manual signed build](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37097253052)
  is preparing that commit's matching pair. Its downloaded Android artifact
  passes local checksums, fork identity, canonical source-lock and stable
  certificate checks; Windows/full-pair validation remains. Nothing was installed.
  Source review found two startup state writes outside the rollback mutex.
  Real CPU-thread regressions reproduce them reverting a completed restoration
  to pending. Guard publication and exclusive initial-window creation now use
  the shared mutex; cancelled startup and late claims cannot overwrite the final
  report. **105 focused CPU checks pass**, including eight new regressions.
  [Reproduction and scope](../results/supervisor-startup-race-2026-10-03.json).
  Full correction-head CI and the required live restoration dry run remain.
  The VD Streamer is still resident with unknown connection state and its owner
  request remains pending. No ADB, hardware window, settings mutation, VR launch
  or GPU workload occurred in this checkpoint. The arm remains unchanged,
  allowing only PC frame-bank work until 08:44:31 Berlin. Chart/property/install
  controller integration remains explicit follow-up scope. No quality gain,
  fresh-rate gain or stable 90-Hz pass is claimed; WO-6/7/8 stay gated on actual
  WO-1 scores. Source/CI work continues and the goal remains active.

- 2026-10-03, checkpoint signed pair and strict quality-report transport:
  The manual `bc21788` build passed [all four jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37097253052).
  Both downloaded archives pass checksums and matching-pair verification, with
  the fork's stable signing certificate. Packaged frame-bank tools pass their
  source/shader/import/binary verifier and three native input-only CPU tests;
  nothing was installed. [Qualification record](../results/signed-integration-pair-2026-10-03.json).
  The startup-restoration correction merged in
  [PR 17](https://github.com/ljk1291/Quest3-Pyrowave/pull/17) after
  [all four jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37099138211)
  passed. A fresh read-only check at 05:29 UTC passes battery (66%, charging,
  30 °C), thermal, owner-idle and competing-workload gates; VD connection state
  remains unknown and prevents opening a window. Read-only ADB was used; no
  snapshot, guards, settings changes, VR launch or GPU workload occurred.
  Lossless PSNR exposed a report bug: permissive JSON emitted bare `Infinity`.
  Private and sanitized writers now encode infinity as a string, preserve
  numeric in-memory metrics and reject NaN. CPU regressions cover actual CLI
  output and private end-to-end fixture output. Full correction CI remains.
  At 06:26 UTC, less than the required 45 minutes remain in the owner's exact
  eight-hour interval ending 06:44:31 UTC; no new hardware window can start.
  The arm is unchanged. Actual HVS GPU calibration, the 36-cell Metro matrix
  and restoration dry run remain pending. WO-6/7/8 still require WO-1 scores;
  no quality improvement, fresh-rate gain or stable 90-Hz pass is claimed.
  Source/CI work continues, with the installed pair and defaults unchanged.

- 2026-10-03, checkpoint window expiry and measurement blocker:
  The owner's eight-hour exception was accepted exactly; a CPU-only arm check
  at 06:46 UTC confirms expiry at 06:44:31 UTC, unchanged arm bytes and zero
  unattended window state files. No ADB or hardware action ran in this check.
  [Blocker and completion audit](../results/artifact-quality-window-blocker-2026-10-03.json).
  Supervisor integration `ad5308d` passed [all four jobs](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37101851281).
  [The report-format correction](https://github.com/ljk1291/Quest3-Pyrowave/pull/18)
  has passed CPU and Android CI; its Windows and pair validation remain in
  [the same live workflow](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37103211150).
  Merge remains conditional on all four jobs passing. The earlier qualified
  stable-signed `bc21788` tools/pair remain downloaded and uninstalled.
  WO-0/1/2/3/4/5/9 source preparation is present; actual restoration, calibration,
  Metro scores and chart comparisons remain unproved. WO-6/7/8 require WO-1's
  real data; no new optimization is justified by the source-only checks.
  Guarded chart/property/installation controller integration remains explicit
  follow-up before device windows. No quality or rate profile was promoted.
  The goal's three success criteria are unmet. Hardware diagnostics are blocked
  by the expired arm and the unresolved VD-disconnection proof; CI completion
  is the remaining available action in this checkpoint.
  **Owner next steps:** disconnect VD and exit its Streamer manually, then arm
  a fresh `frame_bank_pc` window with at least 45 minutes remaining and resume
  the goal. No new Metro capture is needed: the existing 90-frame source and
  four reviewed crops stay frozen. Repeat live gates and the independent-guard
  restoration dry run first, then HVS GPU calibration and the finite Metro matrix.
  Later chart tests need their own allowed scope/controller or owner supervision.
  No settings, installation or runtime changes require rollback from this interval;
  VD hash verification remains unset rather than claiming an unperformed check.

- 2026-10-03 (Codex, owner-supervised PC pass 1): implemented the explicit owner-attested
  frame-bank lease and separate quality/timing contention policies. Quality retains the
  compute-backend, 2048 MiB free-VRAM, driver/device and stop-marker safety stops, with
  GPU load samples; timing invalidates affected measurements after sustained external
  engine load >10% for at least 10 seconds or an active compute backend. Single browser
  spikes do not revoke quality work. No arm, idle, headset or VD gate was consulted.
  HVS identity/amplitude sanity passed. All nine 500 Mbps × Haar/5/3/9/7 ×
  3072/2560/2080 cells completed on the same 90 source frames and qualified native tools.
  The six resumed CDF cells have 713 load samples, at least 12747 MiB free VRAM and no
  safety stop; retained Haar evidence has the older monitor coverage. All 54 FFmpeg
  comparisons passed the independent 1–90 frame audit. Ancillary PSNR was corrected
  from retained sequence summaries without rescoring; VMAF, SSIM and HVS are unchanged.
  [Results and limits](../results/metro-matrix-pass1-2026-10-03.md): Godlike CDF 9/7
  leads this single-pass quality screen (97.79 display VMAF, 36.43 HVS dB), and both
  CDF wavelets improve VMAF and calibrated HVS on all four crops at all tested sizes.
  [PR #20](https://github.com/ljk1291/Quest3-Pyrowave/pull/20);
  [CPU CI passed](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37112302438).
  Local CPU checks: 49 passed, three compiler-dependent Windows skips. Native/signing
  jobs skipped; no new signed pair, headset actions, settings changes or default
  promotion. Lease closed, no owned jobs remain. Offline quality does not establish
  decoder speed or stable 90 Hz; prior ~82–83 fresh submissions/s remains separate.
  Pass 2 and further hardware work are stopped for owner review, as requested.

- 2026-10-03 (Codex, planner consolidation): read and reconciled PLANNER-NOTES.md.
  [PR #20](https://github.com/ljk1291/Quest3-Pyrowave/pull/20) plus its supervised CLI
  and current-session note merged into this integration branch as `c630f3d` after
  [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37135383541).
  Fifty local CPU checks passed; three compiler-dependent Windows checks skipped.
  Retained prior evidence and the recovered 09:40 note; the new objective/queue
  supersedes the old 300-Mbps/pass-2 schedule. Q1/Q2 are authorized by the current
  owner message. No new signed pair or headset work; planner handoff file is removed
  only after its content is committed here and in the plan.

- 2026-10-03 (Codex, Q1 complete / Q2 compute-work stop): HVS sanity passed and
  all four new Haar cells completed. Each passed six exact 90-frame FFmpeg and six
  calibrated HVS comparisons. At 3072, Haar/1000 scores 35.455 HVS dB / 96.451 VMAF,
  below both CDF/500 references; at 2560 it scores 36.993 / 97.555, but does not match
  either CDF/500 reference on both metrics across every crop. The first CDF cell
  was interrupted when the monitor observed ComfyUI `running=1`; its partial score
  is excluded. This was the retained compute-backend stop, not desktop/browser load.
  The lease closed, owned jobs remaining=0, cleanup errors=[]; four completed cells
  are preserved and eight CDF cells remain. [Partial combined table](../results/metro-q1q2-progress-2026-10-03.md)
  and [segment evidence](../results/metro-q1q2-segment1-2026-10-03.json).
  The owner has been asked to clear compute work before resumption. No headset,
  settings, arm file or installed pair changed; no profile is promoted.

- 2026-10-03 (Codex, Q3 path ready): [PR #21](https://github.com/ljk1291/Quest3-Pyrowave/pull/21)
  and [telemetry follow-up #22](https://github.com/ljk1291/Quest3-Pyrowave/pull/22)
  merged after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37136837252)
  and [follow-up CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37137832608).
  The [NVENC adapter](NVENC-FRAMEBANK.md) preserves native 8-bit decoded planes,
  records actual elementary-stream bytes and observed metadata, and reuses the
  same source/crops/calibration. It keeps external F90 normalization distinct from
  raw-bitstream timing and requires sanitized GPU telemetry plus final lease health.
  Fifty-five focused follow-up CPU tests passed. The real 16-cell HEVC/AV1 plan at
  200/500/800/1000 Mbps × two sizes is frozen; no NVENC GPU matrix or Quest test ran.
  These tool changes require no new signed pair. Stable 90 Hz remains unproved;
  the earlier ~82–83 fresh submissions/s result is separate from offline quality.

- 2026-10-03 (Codex, Q1/Q2 complete after owner-cleared resume): the owner confirmed
  ComfyUI idle and authorized the eight remaining CDF cells. A fresh finite lease
  passed HVS sanity and completed all eight without a stop or failure. Combined
  with the four retained Haar cells, all twelve requested cells passed the audit:
  72 FFmpeg comparisons with exact PSNR/SSIM indices 1–90 and 72 calibrated HVS
  comparisons with `ScoredFrames=90`. Both leases closed with no owned jobs or
  cleanup errors. Both segments retain identical protected Python module hashes,
  source hash, qualified native tools/build and calibration; separate harness commits,
  environment records and 1543 GPU-monitor samples are preserved. The interrupted
  partial cell remains evidence, excluded from scores.
  [Combined 18-row table](../results/metro-q1q2-combined-2026-10-03.md) and
  [audited JSON](../results/metro-q1q2-combined-2026-10-03.json).
  Full-size CDF 9/7/1000 leads at 39.342 HVS dB / 99.163 VMAF. Full-size 5/3/1000
  improves on Haar/1000 by 3.127 HVS dB / 2.495 VMAF and passes every crop; the
  reduced-size 5/3/1000 also passes every crop. Reduced-size 800-Mbps CDF profiles
  do not pass every crop against Haar/1000. WO-6's quality prerequisite is satisfied,
  but Q3 is the next comparison under the owner's codec-independent objective.
  No headset work, settings/arm changes, timing claims or default promotion occurred.

- 2026-10-04 (planner revision and Ethernet): reconciled the complete 22:45 note,
  replaced the active queue and Q3 schedule, and retained historical evidence.
  Get-NetAdapter readback confirms 2.5 Gbps / driver 10.73.813.2024; no settings
  changed. Current owner goal supplies finite offline lease authorization only.

- 2026-10-04 (fence metrics/backfill checkpoint): [PR #23](https://github.com/ljk1291/Quest3-Pyrowave/pull/23)
  merged as `5f320c0` after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37160444658)
  and 14 local CPU tests. Backfilled Haar/500, 5/3/1000 and 9/7/1000 at full FOV;
  exact 270/270 retained decode hashes match. Trimmed-window edge PSNR is
  26.117 / 33.286 / 34.583 dB; temporal residual p99 is 44 / 24 / 21 luma codes.
  All three leases closed with zero owned jobs and no cleanup errors. Two retained
  orchestration interruptions (private-identity lookup and unreadable status response)
  were corrected without repeating an encode/decode. No optical/timing claim.
  [Report](../results/fence-backfill-2026-10-04.md), [JSON](../results/fence-backfill-2026-10-04.json).
  Exact offline crop offsets: left (278,274), right (170,274), size 2624×2776.
  wood_gravel_region is partially excluded; fence and three other fixed crops fit.
  [Geometry and effective FOV](../results/q3-crop-geometry-2026-10-04.json) preserve
  density and explicitly distinguish fixed height 2776 from 0.85×3232=2747.2.
  WO-10, WO-8, revised Q3 and WO-13 source work are active on separate branches;
  Q3a/Q3b and the final stable-signed pair remain incomplete. No owner blocker.

- 2026-10-04 (source review and Q3 preparation): [PR #28](https://github.com/ljk1291/Quest3-Pyrowave/pull/28)
  merged as `9944e63` after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37161080084),
  adding reference-only band masks and sharp/matching-blur scoring. [WO-11 design PR #29](https://github.com/ljk1291/Quest3-Pyrowave/pull/29)
  merged as `961f1aa` after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37161552217).
  Q3a's native C420 crop is prepared without resampling: 90 frames, 5248x2776 stereo,
  SHA256 `4c833e175610488ffa05a8037e52c166424db8308a67a2bfed4ed48861fad2e5`.
  WO-10 is in native CI. WO-13's reviewed follow-up now measures delayed ACKs,
  retains skipped/partial/unacknowledged slots, and bounds receiver teardown;
  11 CPU tests pass, native CI pending. The reconstructed stock-codec audit found
  that Windows NVENC does not explicitly apply the H.264 High-profile setting;
  two-eye H.264 Q3 rows remain offline proxies, not selectable live profiles.
  Before Q3a runs, complete per-frame encoder-call timing/probe evidence and its
  CPU CI. Before Q3b runs, finish WO-8's actual reduced-plane codec path and
  Python/shader area-filter parity. No owner-dependent blocker; no new GPU,
  headset, settings, installed-pair or arm-file changes at this checkpoint.

- 2026-10-04 (Q3a ready; owner-dependent preflight stop): [WO-12 PR #27](https://github.com/ljk1291/Quest3-Pyrowave/pull/27)
  merged as `7263314` after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37162009050).
  [Q3a PR #26](https://github.com/ljk1291/Quest3-Pyrowave/pull/26) merged as `3dfa1c0`
  after [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37162261878)
  and 36 local tests. The adapter records per-frame FFmpeg encoder-call wall
  diagnostics (not GPU execution), explicit full-range 10-bit conversion, native
  format/profile evidence, both score windows and initial H.264/HEVC IDR proof.
  Compressed streams and hashes are retained after successful scoring.
  Ten NVENC cells are frozen under plan SHA256
  `e67a3bf7269239f5b677b00cce5eb8073ab090e39329c7359392ae298c8cc083`.
  The controller adds only the required `kind=per_eye_crop` descriptor to the
  unchanged public geometry; the public-wrapper API needs that small follow-up.
  Fresh preflight then found active ComfyUI/603 MiB free VRAM, so no lease or
  Q3a GPU cell began. Owner confirmation is now required; all agents stopped.
  [Sanitized preflight](../results/q3a-preflight-blocked-2026-10-04.json).

  Retained source checkpoints for resume: WO-10 PR #25 `dcb4d66`, CPU/Android
  green and Windows native CI pending; WO-13 PR #24 `89dbea8`, 11 local CPU
  tests and independent review passed, native CI pending. WO-8 branch
  `codex/wo-8-foveation` at `4865045` is clean: 13 local tests, source-stack and
  DXBC checks pass, but real WARP execution/CI and root review remain required.
  Pyro Q3 adapter `codex/q3-pyro-adapter` at `cc74b27` is source-only, CPU CI
  pending, no PR; shared-scorer integration and native telemetry qualification
  remain. `codex/q3-pyro-timing` retains an uncommitted isolated CLI prototype
  and contract test; patch regeneration, CI and qualified binaries are still
  needed. Q3b adapter has no new edits. Q3a/Q3b results and final signed pair
  remain incomplete; no optimization or default has been promoted.

### 2026-10-04 18:25 CEST — H264Fit complete; extension branches in CI

The owner-authorized single-stream H264Fit / 700 Mbps / P7 / softness 0.5 cell
completed all 90 frames with a clean lease closure, zero owned jobs and unchanged
source/harness hashes. Trimmed fence edge PSNR is 47.837276 dB, temporal residual
p99 4 and mean 0.908247; all-90 full-crop HVS is 36.976144 dB. This is a strong
fence candidate with a substantial peripheral/full-crop quality trade-off, not a
live decoder or 90 Hz result. Its 90 recorded encoded-reference frame hashes match
the retained PyroWave H264Fit input exactly; the final publisher is qualifying
that explicit cross-record provenance without repeating the encode.

WO-7 is [PR #43](https://github.com/ljk1291/Quest3-Pyrowave/pull/43); the Light phase
fix and its source-lock pin are [PR #42](https://github.com/ljk1291/Quest3-Pyrowave/pull/42).
Both have green CPU/Android jobs; full native CI is still in progress. The new
matrix plus exact retained-HVS compatibility is [PR #44](https://github.com/ljk1291/Quest3-Pyrowave/pull/44),
head `761afb5`, with green [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37216124693).
Independent review and focused CPU checks cover the two new native overlays and
the Python provenance path. The original HVS executable/source/shader/imports
remain fixed; current codec and historical scorer lock identities stay separate.
Eight new cells, the combined 32-row report, stable-signed pair verification and
final owner checklist remain pending. No headset, settings or installed-pair
operation occurred. The baseline remains unchanged.

### 2026-10-04 19:24 CEST — extension integrated; signed pair verified

PRs #42, #43 and #44 are merged at `80a16353ca127508fec745dec53dc790ceb77fb2`.
The Light follow-up preserves Medium's aligned sampling exactly; its CPU-only
follow-up passed [CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37217662526)
in addition to the native phase-fix build. The integration's complete
[manual CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37217852222)
passed. Its stable-signed APK/server pair was downloaded and independently verified
against matching identities, artifact/native-library/shader hashes and the retained
stable certificate. It has **not been installed or launched**.

Three of the eight extension cells are complete with clean leases. Primary fence
figures below use frames 10–89; HVS is the separate all-90 secondary score:

| Cell | Fence edge PSNR-Y dB | Temporal p99 | HVS dB |
|---|---:|---:|---:|
| Cropped AV1 Main10 / 200 / P1 / spatial AQ | 42.619633 | 9 | 43.103077 |
| Cropped 9/7 / 1000 / RDO 24 px/deg | 39.933228 | 12 | 43.008816 |
| Cropped 9/7 / 1000 / RDO 36 px/deg | 39.504094 | 13 | 42.598806 |

The retained default-density 9/7 / 1000 comparator is 35.753751 dB / p99 19 /
HVS 39.904984 dB. Its legacy 96 dpi / 1 m constant corresponds to 65.28 px/deg,
not 96 px/deg. Both new native logs confirm the requested/effective densities.
The AV1 control explicitly sets FFmpeg AQ strength 8; live ALVR enables Spatial
AQ but leaves strength to its NVENC preset/driver, so this is not an exact live
encoder-configuration equivalence claim.

The seven new Pyro reports bind their frozen plan but omit a top-level projection
copy. The private publisher now recovers it only from the exact hash-bound plan,
checking selected cell, all 90 source/frame identities and observed HVS calibration;
it publishes that derivation proof without modifying original reports. Independent
review and 15 publication/rate CPU checks pass. Medium/RDO24 is currently preparing
its 90-frame references; corrected Light and three high-rate cells remain. No
headset, VR, VD, network/settings, arm or installed-pair operation occurred. This
checkpoint is offline quality evidence, not a fresh-rate, timing or 90 Hz pass.

### 2026-10-04 20:52 CEST — revised Q3 complete; stop for owner

All nine authorized additions (H264Fit plus eight extension cells) are complete
with clean supervised quality leases. The [combined report](../results/metro-q3-combined-2026-10-04.md)
contains 32 validated rows and the requested default-density bitrate analysis.
The corrected Light publisher proof follows the actual nested transform schema
and checks all 90 frame identities; missing redundant aggregate metadata is not
fabricated in the original report. Both that adjustment and the frozen-plan
projection recovery received independent review. The report retains their
derivation evidence and immutable raw-report hashes.

The [verified build receipt](../results/quality-candidate-build-80a1635-2026-10-04.json)
and [headset preparation checklist](Q3-HEADSET-CHECKLIST.md) are ready. Full native
CI passed for `80a1635`; later documentation commits do not change the pair's
identity. Independent review verifies all 32 rows, correct score windows,
high-rate limitations, provenance/privacy and clean lease closure. Current
queue is owner review only. No new hardware test, install or default promotion.

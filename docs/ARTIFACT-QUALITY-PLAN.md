# Compression-artifact plan: fence-first codec and geometry investigation

## Active owner objective and scope (2026-10-04)

The owner's 2026-10-03 22:45 planner revision below supersedes every earlier planner
note, the old Q3 sixteen-cell matrix, and the earlier engineering order. The target
is the fewest visible artifacts at Godlike density, fresh submissions at least as
high as today's (target 90/s), and pipeline latency no worse than today's. PyroWave
is optional. Rank fence edge PSNR and temporal shimmer first, calibrated HVS next,
VMAF last. Preserve the full objective rather than selecting an easier subset.

The current owner message authorizes finite supervised PC-only frame-bank leases
for fence backfill, Q3a and Q3b. ComfyUI must be idle; retain all quality-mode safety
stops, owned-job registration, deadline and stop marker. No headset, SteamVR, Metro,
VD, network/router, settings, arm-file or installed-pair changes are authorized.
Source work uses separate codex/<wo> branches, CPU checks and green CI before merge.
After Q3a/Q3b reports and WO-10/8/13 merge, build and verify a stable-signed pair
without installing it, write exact section-6 settings/rollback, and stop for owner.
If an owner-dependent blocker arises earlier, record it and stop.

Evidence qualifications: decoder caps, VD field visibility/geometry and VD's likely
dual-stream layout below are owner/planner inputs to verify, not established local
measurements. Pixel-linear decode estimates are hypotheses only. Inter prediction
may reduce codec-induced shimmer but does not guarantee artifact-free thin lines.
The original capture has irregular timestamps and 89 distinct payloads/90 frames;
temporal differences measure sequence reconstruction error, not optical shimmer.
Record both one-based 1–90 and 10–89 score windows explicitly, including temporal
pair indexing. Keep encoder wall/completion time distinct from GPU execution.
Do not silently relax geometry, formats, safety gates or requested cells.

Read-only Ethernet evidence on 2026-10-04: Get-NetAdapter reports Ethernet Up at
2.5 Gbps, Realtek Gaming 2.5GbE Family Controller, rt640x64.sys version
10.73.813.2024 dated 2024-08-15 (NDIS 6.40). This is link negotiation, not TCP
goodput; no network setting changed.

### Fence prerequisite completed (2026-10-04)

[The three-cell backfill](../results/fence-backfill-2026-10-04.md) validates all270
decode hashes against retained evidence and ranks 9/7/1000, 5/3/1000, Haar/500 in
that order for edge PSNR and temporal residuals in both score windows. This is
sequence reconstruction error, not optical shimmer. [Exact crop geometry](../results/q3-crop-geometry-2026-10-04.json)
uses left offset (278,274), right (170,274), 2624×2776/eye and unchanged density.

### Source and Q3 checkpoint (2026-10-04)

WO-10, WO-8 and WO-13 are merged; WO-12 remains an audit and WO-11 a design.
WO-8's resolved source `e61621d` passed full Android/Windows CI and merged as
`55bb65b`. All runtime features remain opt-in/default-off. Q3b adapter PR #36 and
exact-score reuse PR #37 passed CPU CI and merged as `c80fb3f` / `150dcff`;
51 combined CPU tests pass. All ten NVENC and five Pyro Q3a rows are complete
under clean closed quality leases; the final combined ranking waits for ten Q3b
rows. The first Q3b attempt stopped cleanly during CPU reference preparation,
before encoding, to repair redundant per-tile summed-area-table construction.
Retain its partial references for exact-output verification and resume with new
attempt paths; no completed Q3a encode needs repeating. PR #39 merged as `3512b19`
after 53 focused CPU tests, independent review and green CPU CI; the first retained
Metro frame matches bit-for-bit. This caches CPU preparation only, with no runtime
decoder or image-filter change.
The second CPU-only attempt exposed a duplicated forward transform when producing
the matching-blur reference. PR #40 (`7302a25`) reuses the same reduced planes and
adds bounded, ordered CPU preparation (default one, explicitly three for the next
run). Its 55 focused tests, real reduced/blur frame hashes, independent review and
CPU CI pass. Both stopped attempts remain private evidence; neither encoded a Q3b
stream. The r5 plan records the repaired modules and resumes only the ten Q3b cells.
CPU preparation found stale rate/encoded-calibration metadata on the Q3b SBS row;
PR #38 (`9d55e32`) repaired it after CPU CI and independent review. Expanded-space
scoring calibration is unchanged; the actual frozen Metro plan now validates. No runtime,
headset, installed-pair, arm or network change has occurred.
The old wood/gravel crop is partially excluded; other fixed crops and fence fit.
The revised Q3 comparisons and source work below remain required.

The first r5 Q3b result is complete: Light / 9/7 / 1000 Mbps / softness 0,
2464×2592 encoded per eye, scored after reconstruction to the cropped source
geometry. Its frames-10–89 fence edge PSNR is 30.832 dB with temporal residual
p99 32, worse than cropped 9/7 without foveation (35.754 dB / p99 19). Both
windows and sharp/matching-blur domains passed validation; its quality lease
closed cleanly. The softness-0.5 Light row is also complete: fence edge PSNR
30.832637 dB / temporal p99 32, a +0.000766 dB edge change with unchanged p99.
Its centre sharp HVS changes by +0.009158 dB in 10–89; peripheral sharp edge
PSNR falls by 0.901847 dB while matching-blur edge PSNR rises by 0.496987 dB.
These are two of ten Q3b rows, not a final ranking or promotion. Continue the
remaining eight cells without repeating completed encodes; the diagnostic
softness-1 Light cell is active. See the status log for exact report hashes.

Subsequent checkpoint, 2026-10-04 05:01 UTC: the diagnostic softness-1 row is
also complete, bringing Q3b to three of ten and Q3 overall to 18 of 25. Its
fence edge PSNR is 30.833070 dB / temporal p99 32 (10–89), essentially unchanged
from softness 0. Peripheral sharp-reference edge PSNR falls to 31.916966 dB
with p99 29, while matching-blur edge PSNR rises to 42.056622 dB with p99 9.
Centre sharp HVS changes by +0.015855 dB in 10–89 (+0.015391 dB all-90) versus
softness 0. These cross-cell deltas differ from the same-output sharp-minus-blur
centre scores. All three rows pass identity, provenance, both-window and clean
lease checks. The existing controller is running Light / 5/3 / 1000 Mbps /
softness 0.5 next; seven Q3b cells remain. Do not promote softness or alter the
frozen matrix based on a better score against an already blurred reference.

A CPU-only attribution on the retained first Q3b output finds substantial
transform loss before compression: on the same sharp-source fence mask,
sharp→matching-blur PSNR is 32.067 dB and matching-blur→decoded reconstruction
is 39.424 dB (total sharp→decoded is 30.832 dB; these are not additive).
The fence is in the nominal centre, but this Light geometry has a horizontal
half-sample phase, so the area filter still averages neighbouring pixels there
at softness 0. This follows the current shader mapping rather than indicating
a CPU/shader mismatch. Retain the frozen matrix; texel-centre alignment needs
review before accepting Light, and no profile is promoted by these results.

## 1. Owner input (2026-10-03 21:44)

- **Live decoder caps on Quest 3.** These come from the owner's experience; verify them on
  our stack.

  | Codec | Cap | Limited by |
  |---|---|---|
  | HEVC, AV1 | about 200 Mbps | Quest decoder |
  | H.264 | about 700 Mbps | Quest decoder (owner's Meta Link experience) |
  | PyroWave | about 1000 Mbps | Wi-Fi; Q4 verifies |

- **Godlike density is correct and the same in Virtual Desktop (VD).**
  - VD's 2624×2776 per eye is that density over 85 % of the FOV tangent span. VD's
    settings use multipliers 0.854 horizontal and 0.850 vertical.
  - The outer 15 % is not visible on a Quest 3 at all.
  - So an FOV crop is a valid option for this fork.
- **Foveated encoding** (as in Steam Link) should be evaluated, with the outer areas
  **slightly blurred** so their aliasing is less visible.
- **Network questions:** what bitrate Wi-Fi 6 at 160 MHz really sustains, and whether
  bitrate fluctuations would be visible. Section 6 covers both.
- **The fence is the primary target.** The tunnel_fog crop shows the mesh in front of the
  fire. It aliases clearly more than the source, even with CDF 9/7 at 1000 Mbps.
  - It is the worst crop for every codec. Region HVS: Haar/500 30.95 dB, 9/7/1000 37.16 dB.
    The rail crop gets 39.55 dB with 9/7/1000.
  - Single-frame averages understate it, and still frames cannot show shimmer.

## 2. What this changes

- **H.264 size limit.** NVENC H.264 is limited to 4096 px per side per stream.
  - Stock ALVR packs both eyes side by side, so stock H.264 needs ≤2048 px per eye.
  - VD fits by (very likely) encoding one stream per eye.
- **Decode time scales with encoded pixels.** PyroWave's limit is Quest decode time. A crop
  and foveation cut pixels for every codec. The game also renders less with a crop.
- **Intra coding causes shimmer.** PyroWave codes every frame on its own, so thin lines are
  requantized differently each frame. Inter codecs reuse static content. Measure this over
  time, not on single frames.

**Geometry candidates.**
- Sizes come from upstream's `tools/quest3/foveation.py` (centre fraction / edge ratio).
- Decode times are a linear-in-pixels *estimate* from the live full-Godlike numbers (9/7
  24.3 ms, Haar 10.5 ms). They are not measurements.
- The 90 Hz budget is 11.1 ms.

| Profile | Encoded/eye | Stereo width | Pixels vs today | 9/7 est. ms | Haar est. ms | bpp @1000 | bpp @700 |
|---|---|---:|---:|---:|---:|---:|---:|
| Today, full FOV | 3072×3232 | 6144 | 1.00 | 24.3 | 10.5 | 0.56 | 0.39 |
| Crop | 2624×2776 | 5248 | 0.73 | 17.8 | 7.7 | 0.76 | 0.53 |
| Crop + light (0.8 / 1.5×) | 2464×2592 | 4928 | 0.64 | 15.6 | 6.8 | 0.87 | 0.61 |
| Crop + medium (0.6 / 2×) | 2112×2240 | 4224 | 0.48 | 11.6 | 5.0 | 1.17 | 0.82 |
| Crop + H.264-fit (0.5 / 2×) | 1984×2112 | 3968 | 0.42 | 10.3 | 4.4 | 1.33 | 0.93 |

## 3. Fence metrics (add before any new cell)

1. **Fence crop.** Add a tight crop on the mesh-over-fire area inside tunnel_fog and record
   its rectangle.
2. **Edge-masked error.** On pixels where the reference luma Sobel magnitude is in the
   crop's top 5 %, report PSNR-Y and p99.9 |error|.
3. **Temporal shimmer.** On the same mask, report the mean and p99 of
   |(dec_t − dec_{t−1}) − (ref_t − ref_{t−1})| over frames 10–89.
4. **Ranking.** Rank by fence edge PSNR and fence shimmer first, then calibrated HVS on all
   crops. VMAF comes last.
5. **Backfill existing cells.** Compute these for Haar/500, 5/3/1000 and 9/7/1000 at full FOV
   from retained decodes, or re-run only those three cells.

## 4. Q3 revised (offline, PC only)

**Common settings for every cell:**
- the same 90 source frames, scored over frames 10–89 and over frames 1–90, with both
  labelled;
- ALVR-like encoding: CBR, no B-frames, `ull`, 1.1-frame VBV, one IDR at frame 0;
- encode ms per frame per stream recorded;
- 10-bit decodes converted to 8-bit full range with one documented filter for scoring.

**Crop geometry:**
- Use 2624×2776 per eye. Scale the session-07 tangent rectangle about the optical axis by
  0.8542 / 0.8500, centre VD's size on it, and mirror it for the right eye.
- Record the offsets.
- Report any fixed crop that falls outside this rectangle.

### Q3a: crop geometry, no foveation

| # | Codec | Layout | Total Mbps | Preset | Why |
|---|---|---|---|---|---|
| 1–2 | H.264 High 8-bit | two per-eye streams | 400, 700 | p7 | VD-style |
| 3 | H.264 High 8-bit | two per-eye streams | 700 | p4 | live-speed preset |
| 4 | H.264 High 8-bit | two per-eye streams | 700 | p7 + spatial AQ | VD uses AQ |
| 5–6 | HEVC Main10 | one stream | 200 | p7, p4 | at the decoder cap |
| 7–8 | AV1 10-bit | one stream | 200 | p7, p4 | VD's current codec |
| 9 | PyroWave Haar | — | 1000 | — | |
| 10–11 | PyroWave 5/3 | — | 800, 1000 | — | |
| 12–13 | PyroWave 9/7 | — | 800, 1000 | — | |

**Full-FOV references:**
- H.264, per-eye 3072×3232 streams, 700 Mbps, p7;
- HEVC Main10, 200 Mbps, p7.

The PyroWave full-FOV rows already exist.

**Dropped:** HEVC and AV1 at 500, 800 and 1000 Mbps. They are above the Quest decoder cap.

### Q3b: foveation (after WO-8's frame-bank transform lands)

`s` is the peripheral softness defined under WO-8.

| Profile | Cells |
|---|---|
| Crop + light, s = 0 / 0.5 / 1.0 | 9/7 at 1000 Mbps (3 cells); 5/3 at 1000 Mbps with s = 0.5 |
| Crop + medium, s = 0.5 | 5/3 and 9/7 at 1000 Mbps |
| Crop + H.264-fit, s = 0.5 | H.264 as one stream at 700 Mbps, p7 (stock-ALVR compatible); 9/7 at 1000 Mbps |
| Crop + blur-only (light ramp, s = 0.5, no squeeze) | H.264 per-eye at 700 Mbps; 9/7 at 1000 Mbps |

- Score in reconstructed (expanded) space against the cropped reference.
- Report the centre and periphery separately. For each fixed crop, record which band it
  falls in.
- **What the softness cells test.** Blur should cut peripheral shimmer at little visible
  cost, and should move bits to the centre. Report:
  - periphery shimmer;
  - periphery edge PSNR against both the sharp reference and a matching-blur reference;
  - the change in centre HVS.

## 5. Source work

Every item below gets its own `codex/<wo>` branch, CPU tests and CI. Everything is opt-in
and default-off. No hardware.

- **WO-10, FOV crop (new; do first).**
  - Add a client setting for the horizontal and vertical tangent multipliers. The default is
    1.0; the candidate is 0.854 / 0.850.
  - Scale both the FOV the client reports and the stream projection-layer FOV.
  - The server derives the render and encode size from the scaled FOV at unchanged Godlike
    density.
  - Log the active multipliers and sizes.
  - Tests: geometry for both eyes, asymmetric tangents, alignment.
- **WO-8, foveated encoding (raised priority).**
  - Port upstream `061dc0b` + `2b87fc7` (light: 0.8 / 1.5×) on top of WO-10.
  - Add profiles `medium` (0.6 / 2×) and `h264fit` (0.5 / 2×).
  - **Prefilter the compressed bands.** ALVR's compress shader takes one trilinear tap from
    a single-mip source, which is in effect one bilinear tap. At a 1.5–2× squeeze that
    aliases thin lines, which is the very artifact we are fixing. Use an area-weighted
    footprint.
  - **Peripheral softness `s` (owner request).**
    - The prefilter footprint is (local squeeze) × (1 + s); s = 0 is anti-aliasing only.
    - The blur must ramp in smoothly from the centre edge, with no visible boundary.
    - Add a blur-only mode: the same ramp with no squeeze. It cuts codec bits but not
      decode time.
    - Rationale: peripheral vision is poor at fine detail but sensitive to flicker, so
      trading aliasing for softness there is the right trade.
    - Limit: Quest 3 has no eye tracking, so the eyes can rest on the periphery. Keep the
      default mild (light profile, s ≤ 0.5). Centre fence aliasing still has to be fixed
      by codec bits and WO-4.
  - Provide the same forward/inverse mapping and filter as a frame-bank transform with
    shared constants. Add a test that the Python and shader paths agree.
- **WO-13, network tool (source only; run in section 6).**
  - Add a TCP mode to `tools/quest3/network.py` that matches the live transport: frame-paced
    writes at 90 Hz of the per-frame byte cap.
  - Report per-frame delivery time p50/p99/p99.9, the share of frames late against the
    11.1 ms period, and longest stall. Runs: 5 minutes stationary, 2 minutes moving.
  - Record the Quest Wi-Fi link rate, band, channel and channel width before and after,
    from read-only `adb shell cmd wifi status` / `dumpsys wifi`.
  - Add frame-size logging (p50/p99/max bytes) to the live cell telemetry so H.264's
    variable frames can be compared with PyroWave's fixed cap.
- **WO-12, stock-codec audit (report only).**
  - Document what the fork allows today for ALVR H.264, HEVC and AV1: 10-bit, high profile,
    preset, AQ, maximum bitrate, eye packing, and the H.264 4096 check.
  - Document what each Q3 winner would need.
- **WO-11, per-eye dual-stream H.264 (design note only).** Build it only if per-eye
  full-density H.264 clearly beats both the H.264-fit single stream and the best PyroWave.
- **WO-6, fast 5/3: deferred.** Revisit it only if PyroWave CDF wins Q3 and the
  crop + foveation decode still misses 11.1 ms live.
- **WO-4, layer filter: already built** (`debug.q3pw.layer_filter`). Keep it for the headset
  session. The compositor's unfiltered downsample is a second source of fence shimmer that
  no codec can fix.

## 6. Owner-supervised headset session

Run this after Q3 and a stable-signed matching pair that includes WO-10 and WO-8.

0. **Now, read-only (Codex).** Record the PC's Ethernet adapter link speed and driver with
   `Get-NetAdapter`; change nothing. 1 GbE caps TCP payload near 940 Mbps, which makes
   1000 Mbps video impossible. Report it at once if the link is below 2.5 GbE.
1. **Q4 network first,** with WO-13's TCP mode.
   - **Reference (upstream's setup, not ours):** Quest 3 at a 2401 Mbps PHY, 2.5 GbE PC,
     stationary, UDP, 10 s per rate (`results/network-first-pass.json`).

     | Rate | Frames on time | Delivery p99 |
     |---|---:|---:|
     | 600 Mbps | 100 % | 6.1 ms |
     | 800 Mbps | 99.1 % | 7.6 ms |
     | 1000 Mbps | 99.2 % | 9.9 ms |
     | 1500 Mbps | 89 % | 12.2 ms |

     Maximum throughput was about 1.74 Gbps. So about 1000 Mbps is the stationary edge for
     90 Hz, and only just: 9.9 ms of the 11.1 ms frame period.
   - **Runs.**
     - Stationary: 5 minutes each at 600, 800, 1000 and 1200 Mbps.
     - Moving: 2 minutes each at 800 and 1000 Mbps while the owner turns 360°, crouches and
       puts a hand near the headset.
   - **Bitrate rule.** Take the highest rate with ≥99.5 % of frames on time *while moving*
     and use about 85 % of it as the live fixed bitrate. Cap it by the codec's decoder limit.
   - **DFS risk.** Record the router channel. 160 MHz on 5 GHz is usually a DFS channel,
     where a radar event forces a channel change and a drop of about a minute. Only the
     owner changes router settings; agents never touch the network.
2. **Cells.** Run each for 60–90 s on the chart and the owner's fence scene. Record GPU decode,
   decode-to-fence, fresh/s, encoder ms and estimated latency.

   | Cell | Configuration | Purpose |
   |---|---|---|
   | a | Haar, full FOV, 500 Mbps | today's baseline |
   | b | WO-10 crop, Haar, 1000 Mbps | the owner confirms the crop edge is invisible |
   | c | best PyroWave from Q3, crop + its foveation profile, 1000 Mbps | |
   | d | stock H.264 `h264fit`, 700 Mbps | Quest decoder at 90 Hz |
   | e | HEVC or AV1 10-bit, crop, 200 Mbps | |
   | f | the winner with the layer filter off/on/off | |
   | g | the winner with a live bitrate step 1000 → 600 → 1000, 10 s each, unannounced | can the owner see bitrate changes? |
   | h | the winner at the Q4 bitrate rule's rate while the owner moves | stutter versus image |

   Cell h also records stalls, late frames and the latency p99.

3. **VD comparison.** The owner compares the winner with VD H.264+ Godlike on the same fence
   scene. The owner launches VD and Metro; agents never touch VD.

## 7. Decision rule

Consider only candidates that keep fresh submissions at or above today's (target 90) and
latency no worse than today's. Among them, pick the best fence edge PSNR, fence shimmer and
HVS. The owner's in-headset comparison with VD decides close calls.

Run every candidate at the Q4 rule's bitrate, never at a stationary peak. A late frame
(stutter, latency spike) is worse than a slightly softer image.

## Q1/Q2 interpretation (record in status)

- **Bitrate alone does not replace the wavelet.** At 3072, Haar/1000 still trails 5/3/500
  by 0.43 dB and 9/7/500 by 0.98 dB HVS.
- **Haar's 2560 lead at 1000 Mbps is optimistic.** The frame bank's Lanczos resize smooths
  Haar blocks, while the live path is a single tap plus a bilinear upscale.
- **VMAF saturates near 99.** Rank by HVS and the fence metrics.


# Prior plan and measurements (historical; superseded schedule)

# Compression-artifact plan: mura-like texture and line aliasing

## Owner objective and revised investigation (2026-10-03)

The objective is **the fewest compression artifacts possible**, with Godlike per-eye
render, 90 Hz with fresh submissions near 90/s, and pipeline latency no worse than
the current profile. PyroWave is optional: HEVC and AV1 are eligible contenders.
The owner reports about 1000 Mbps available over Wi-Fi 6 at 160 MHz. This is available
bandwidth context, not a measured sustainable video bitrate or network acceptance.
This section supersedes the earlier optimization order and rate matrix below;
historical diagnosis and measurements remain as evidence.

Pass 1 used all 90 Metro frames at 500 Mbps. At 3072×3232/eye, CDF 9/7 gained
8.97 display VMAF and 3.34 calibrated HVS dB over Haar; CDF 5/3 gained 7.98 VMAF
and 2.79 dB. Both CDF wavelets improved both metrics on all four fixed crops at
every tested size. Reducing encode size modestly helped Haar's aggregate scores,
but reduced both CDF wavelets' aggregate display scores. The cells used nearly
their complete byte caps. See the [full pass-1 report](../results/metro-matrix-pass1-2026-10-03.md).

Rank candidates by **calibrated PSNR-HVS-M-H first, VMAF second**, then owner judgement
among profiles meeting the rate and latency constraints. Neither metric alone
establishes VR image quality. VMAF's model is TV-calibrated. The frame bank's per-eye
Lanczos down/upscaling is better than the current live sampling path; reduced-size
rows are optimistic until the real path is measured. Projection reuses Session 07;
the frozen capture contains irregular timestamps and a later menu view. Preserve
its exact file order, four crops, range, chroma and all 90 frames.

### Questions and finite test order

1. **Q1:** offline Haar at 800 and 1000 Mbps, at 3072×3232 and 2560×2688/eye.
   Determine whether bitrate alone reaches CDF-at-500 quality. Exp3's roughly
   twofold byte penalty suggests a hypothesis, not a predicted measured score.
2. **Q2:** offline CDF 5/3 and CDF 9/7 at **both 800 and 1000 Mbps**, at the same
   two sizes (the current owner request expands the planner's 1000-only Q2).
   Together Q1/Q2 are twelve cells. Compare against retained pass-1 500 Mbps rows.
   Run under a new owner-supervised PC lease in response to the current message,
   retaining the quality-mode GPU monitor, stop marker, owned jobs and finite deadline.
   Post the combined table before any headset work.
3. **Q3:** add a separate NVENC HEVC/AV1 frame-bank path using the same source,
   geometry, crops, metrics and calibration. Plan 200/500/800/1000 Mbps with
   ALVR-like CBR, no B-frames, no lookahead, low-latency tuning and approximately
   one frame of VBV. Record exact requested settings, bitstream metadata, actual
   bytes/bitrate, encoder/decoder identities and capability failures. No silent
   bitrate, format or geometry fallback. An offline decode proves reconstruction,
   not Quest decoder throughput. The current request adds this path; its complete
   hardware-codec matrix and subsequent live cells remain separately reported.
4. **Q4:** before any live video cell above 600 Mbps, measure sustained TCP goodput
   and tail latency at 160 MHz using the repository network tools. The planner's
   approximately 1053 Mbps requirement for 1000 Mbps video is a 5% overhead planning
   estimate, not measured transport overhead or network headroom.
5. Later owner-supervised live HEVC/AV1 comparisons at 400/800/1000 Mbps must establish
   Quest 3 hardware-decoder throughput, fresh submissions and latency at Godlike/90.
   No headset work may overlap offline GPU scoring.

The new PyroWave campaign uses 500, 800 and 1000 Mbps, with 1200 Mbps reserved for
a later headroom experiment. Drop 300 Mbps from this campaign; 2080 remains a
diagnostic size. At 1000 Mbps/90 frames/s the derived stereo-luma bits/pixel are
0.56 (3072×3232/eye), 0.81 (2560×2688), and 1.21 (2080×2208).

### Decoder and engineering decisions

Quest decode cost is a central constraint. The retained live screen measured
CDF 9/7 GPU decode at 24.3 ms versus Haar at 10.5 ms; the faster AHB configuration
later reached only about 82–83 fresh submissions/s. Neither is a stable 90 Hz pass.
CDF 5/3 currently shares the apron reconstruction path. Historical HEVC control
was about 89.7 fresh submissions/s at 200 Mbps, with an estimated 62.5 ms pipeline
versus Haar's approximately 85 ms; these are instrumentation estimates, not optical
latency or a controlled high-bitrate codec comparison.

Measure GPU execution and completion latency separately at 800/1000 Mbps before
assuming more bits are free. The planner cites upstream USB completion increasing
8.40→9.12 ms and fresh rate decreasing 106→97/s from 1000→1500 Mbps; those are
upstream context, not equivalent local Godlike results. Preserve this distinction.

WO-6 (fast CDF 5/3 inverse) is gated on Q2 showing a clear quality gain over Haar
at 1000 Mbps. P0–P5 decoder profiling remains relevant once a quality candidate
is selected. Defer 4:4:4/HUD colour-fringe work; its previously reported roughly
34–50% decode overhead must not be assumed affordable. Preserve baseline defaults,
build/dependency/signing provenance and attribution. If the best feasible PyroWave
profile loses to HEVC or AV1, report that result plainly.

PR #20 and its two follow-ups (supervised CLI and current-session authorization
note) merged as `c630f3d`; [CPU CI](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37135383541)
passed. These Python/documentation changes require no new signed client/server pair.

### Q1/Q2 results and Q3 implementation (2026-10-03)

The four Haar/800–1000 cells completed with all 90 frames. Haar/1000 at
3072×3232 remains below both CDF/500 references on display HVS and VMAF. At
2560×2688, Haar/1000 improves the aggregate scores, but fails to match either
CDF/500 reference across every fixed crop on both metrics. Bitrate alone therefore
does not uniformly replace CDF's quality advantage in this frame bank.
See the [complete combined table](../results/metro-q1q2-combined-2026-10-03.md).

Q2 initially stopped when ComfyUI became active. After the owner cleared compute
work, a fresh lease completed the eight CDF cells. The four Haar cells were retained
without repetition, and the partial CDF score was excluded. All twelve cells passed
the exact 90-frame FFmpeg/HVS audit; both leases closed cleanly. No headset or settings
changes were made.

Full-size CDF 9/7/1000 leads the 18-row comparison at **39.342 HVS dB / 99.163 VMAF**.
Full-size CDF 5/3/1000 scores 38.583 / 98.946 and improves on Haar/1000 by
3.127 HVS dB / 2.495 VMAF, with both metrics improving on every crop. The reduced-size
5/3/1000 also improves every crop. Thus WO-6's offline quality prerequisite is met.
At 800 Mbps, both full-size CDF profiles improve every crop over Haar/1000; the
reduced-size profiles improve only two crops (5/3) or three (9/7) on both metrics.
Full-size encoding leads each CDF pair on aggregate display HVS at all three tested
rates. These are single-capture quality results; they do not qualify decoder timing,
transport capacity, fresh rate or optical FPS. Keep ~82–83 fresh submissions/s
separate from stable 90 Hz acceptance.

The [Q3 NVENC frame-bank path](NVENC-FRAMEBANK.md) is implemented with CPU CI and
a frozen 16-cell plan. Its P4/ULL/CBR configuration is an explicit offline proxy;
hardware capability, achieved rates and quality remain unmeasured. It preserves
native decoded samples, records unknown bitstream metadata honestly, and retains
sanitized load samples. Run that comparison before committing to substantial CDF
decoder work; PyroWave remains optional under the owner's artifact-first objective.

## Historical diagnosis and work orders (2026-10-02)

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

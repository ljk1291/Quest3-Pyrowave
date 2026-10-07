# Hands-on candidates

Configurations that passed automatic screening and are worth the owner's in-headset look
(Metro fence checkpoint, head motion). Newest first. Each entry: exact settings, the
evidence that put it here, and what to look at. Rejected options are listed at the end
so they aren't retried by accident.

## Owner hands-on, 2026-10-07 ~08:10–08:25 (worn, SteamVR home + head motion; Metro launch cut short)
| Cell | Fresh/s | Mbps | Network p50/p95/p99 (ms) | Latency p50 | Decode p50 | Owner (verbatim) |
|---|---|---|---|---|---|---|
| hq-haar750-metro | 83.0 | 757 | **321 / 416 / 430** | 387 ms | 6.7 | "Already in steamvr I notice that we cant hold 90fps in motion either" |
| hq-haarfov500-metro | 87.9 | 505 | 10.8 / 46 / 89 | 69 ms | 4.8 | "Still the same issues in motion here, not as bad though" |
- 750 Mbps saturates the link when the headset is worn and moving (unworn it was 12 ms): rejected for now.
- At 500 the remaining motion stutter is network delay spikes (p95 46 ms), not decode or compression. Link at
  the time: Wi-Fi 6, 5580 MHz, 1200 Mbps PHY, RSSI −16 dBm, so not a weak signal. Next: lower bitrate (400),
  UDP vs TCP, buffering, measured with a moving scene and worn-like motion.
- The SteamVR dashboard is disabled during harness cells, so the owner could not launch Metro from VR; launch it
  from the PC (`steam -applaunch 2669410`, Metro Awakening) or allow the dashboard for *-metro cells.
- Restore: all OK except VD `StreamerSettings.json`, rewritten at 08:10:22, 25 s after the snapshot, while the
  headset woke and connected. The harness never writes VD files; the content can't be diffed (only the hash is
  kept). Owner asked to check the VD settings.

## Compression comparison with motion (2026-10-07 00:20–01:45, owner request, all FOV-cropped)
Pair f33c0cc (installed). Chart now sways (`stereo_scene.py --sway 64`: sub-pixel bilinear, ±64 px over 1.2 s
horizontally, ±32 px over 1.7 s vertically, ~3 px/frame peak) so inter-frame codecs must code motion; harness env
`Q3PW_CHART_ARGS="--sway 64"`. Cells in ws/hq_profiles.py (wraps the frame-loss adapter). PyroWave cells use the C3
queue (depth 3). Stock H.264 must use H264Fit foveation (5248-px cropped stereo > the Quest's 4096-px H.264 width).
2–3 interleaved runs per cell (round 3 was lost to a disk-full incident, see below).

| Cell | Fresh/s | Mbps actually streamed (p50) | Encode / decode p50 (ms) | Net (ms) | Latency p50 mean (ms) |
|---|---|---|---|---|---|
| hq-haar500 (C3) | 90.1, 89.9 | 504 | 1.5 / 7.1 GPU | 8.8 | 73 |
| **hq-haar750** | 89.1, 90.1, 89.8 | **757** | 1.6 / 6.5 GPU | 12.4 | 82 |
| **hq-haarfov500** (Haar + Medium FFE) | 89.5, 89.8 | 504 | 2.0 / 4.9 GPU | 8.6 | 73 |
| hq-h264p4-500 (NVENC P4) | 89.9, 90.0, 90.0 | **270** | 9.4 / 15.1 MediaCodec | 5.2 | 73 |
| hq-h264p4-750 (P4) | 90.0, 90.0 | **271** | 9.4 / 15.3 | 5.1 | 69 |
| hq-h264-500 (P7, harness default) | 71.4, 71.5, 71.3 | 259 | **14.7** / 15.2 | 5.2 | 72 |
| hq-h264-750 (P7) | 71.9, 71.7 | 261 | 14.7 / 15.1 | 5.2 | 73 |

- **750 Mbps works over the current Wi-Fi**: 757 Mbps sustained, 90 fresh/s, network time 8.8 → 12.4 ms.
- **Haar + foveation holds 90 Hz** (decode 4.9 ms, lower than crop alone).
- **H.264 P7 cannot hold 90 Hz on moving content** (encode 14.7 ms > 11.1): 71/s. The earlier 90.0 on the static
  chart hid this. P4 encodes in 9.4 ms and holds 90.0. MediaCodec decode reports 15 ms but is pipelined.
- **H.264 never streams more than ~270 Mbps** (p95 ~314) whether set to 500 or 750, at P4 or P7. Cause not
  established: CBR without filler (ALVR `m_fillerData`) lets NVENC undershoot when quality saturates on this
  simple translation, or an implicit level/rate cap. Motion here is pure translation, H.264's best case.
- Visual (lossless dumps, post-fade pairs chosen automatically; sheets in results/local/session-25/compare-hq/,
  made by ws/compare_sheet.py), mean/max |error| on gratings, lines-text, gratings-right:
  Haar 500 1.25/70, 1.26/69, 1.12/66; **Haar 750 0.81/31, 0.59/31, 0.75/60**; Haar+FFE 1.18/58, 0.87/58, 1.17/78;
  H.264 P4 500 1.20/21, 0.43/22, 1.19/21.
  Planner's read: Haar 750 is clearly cleaner than 500 (square patches around text mostly gone, stripe edges
  fainter). Foveation does not visibly improve the central crop. H.264 keeps text almost clean, but whole
  grating stripes come out brighter or darker (motion-compensation residue, not blocks).
  Astra (task-muxbt1kt-i71kf5, read-only, MIDDLE vs LEFT): ranking for thin lines/text **H.264 narrowly first,
  Haar 750 second, Haar 500 + foveation third, Haar 500 fourth**. Severity gratings/lines-text/gratings-right:
  Haar 500 3/3/3 (4–8 px square patches, faint strokes fade, dark squares around the diagonal); Haar 750 2/2/2
  ("a clear visible improvement", patches largely gone); Haar+FFE 2/2/2 (helps the diagonal, no reliable
  centre-wide gain); H.264 2/1/2 (text and wires continuous; stripe brightness/width modulation on gratings).
  For dense gratings Astra leans Haar 750; for isolated wires and faint text, H.264. Shimmer judgements are
  predictions from stills; swayed translation is H.264's easy case.
- Lost/invalid: the first dumps paired frames from SteamVR's fade-in (all dumps start inside it; the sheet tool
  now skips pairs that aren't at full contrast). H.264 P7 and P4-750 have no valid post-fade dump. The last five
  dumps failed because the Quest went to sleep on its charger (~01:34), so the run stopped there.
- Incident: the sweep script exported the server dump variable for every cell, so each capture also wrote
  2.5–4 GB of frames and the disk filled up (restores failed mid-sweep, then succeeded after cleanup; baseline
  verified, VD untouched). Fixed: the variable is now set only around `dump`; unmatched frames are pruned.

## Candidates

### C3 — C1 + client output queue depth 3 (2026-10-06 ~23:45, same pair as C2) — first paced 90.0 fresh/s
- Settings: as C2 but `debug.q3pw.output_queue=3`, `debug.q3pw.output_queue_max_age_us=33334` (three periods;
  the 22,223 default could age-drop the third entry under jitter). Harness cell `queue3-500` (added to
  tools/quest3/frame_loss_profiles.py on codex/output-queue). Marker seen: `[Q3PW_OUTPUT_QUEUE] depth=3
  max_age_us=33334 ring=5 workers=1 copy_handoff=false`.
- Evidence (sweep 2, interleaved with control and queue2, 3 runs each, fresh connection per run):

| Cell | Fresh/s | Mean | Superseded/s | 2-period gaps / ~1790 | Latency p50 (ms) |
|---|---|---|---|---|---|
| loss-control500 | 85.7, 85.9, 75.9 | 82.5 | 4.1, 4.1, 14.1 | 85, 89, 174 (+56 3-gaps) | 75.3, 72.7, 56.6 |
| queue2-500 | 88.9, 89.8, 88.6 | 89.1 | 1.2, 0.1, 1.4 | 26, 3, 35 | 64.6, 85.9, 57.2 |
| **queue3-500** | **89.5, 90.0, 90.0** | **89.8** | 0.5, 0.1, 0.1 | 25, 3, 4 | 68.1, 79.0, 78.7 |

  - Over both sweeps (6 runs each): control mean 82.8 fresh/s, latency p50 mean 63.5 ms; queue2 89.0 / 62.8 ms;
    queue3 (3 runs) 89.8 / 75.3 ms. So depth 3 costs ≈ one 90 Hz period (+~12 ms), as designed; depth 2 costs
    nothing measurable. Latency p50 is phase-bimodal in every cell (44–86 ms), so treat ±10 ms as noise.
  - Decoded 90.0/s with server pacing on, accounting closes (residual −2..+1), equal-key gaps (gap 0) 3–9 per
    run, the same as control. So these are distinct frames, not repeats or overproduction.
  - Rates: runtime accepted 90 Hz; decode 5.9 ms p50 (budget met); sustained live 90 Hz in the headset is
    shown on the static chart only. The owner's Metro look decides.
- Frame dumps (2026-10-07 ~00:00, one per cell, 8–9 exact pairs each): 0 black/blank decoded or presented frames
  for control, queue2 and queue3. The chart crops are bit-identical in error to C1 (gratings 1.43/95,
  lines-text 1.05/95, gratings-right 1.44/90 mean/max). So the queue changes timing only, not the image.
  Sheets: results/local/session-25/compare-output-queue/ (wavelets: compare-wavelets/), made by ws/compare_sheet.py.
- Look at: as C2. Also, compare C2 and C3 back to back. If C3 feels laggier (it adds ~1 frame), prefer C2.

### C2 — C1 + client output queue depth 2 (2026-10-06 ~23:30, pair `codex/output-queue` f33c0cc, CI 37527308692)
- Settings: exactly C1 (PyroWave Haar, 500 Mbps, 90 Hz, FOV crop 0.854/0.85, server pacing ON, TCP, compute
  decode) on APK `20.13.0-ljk1291.2+f33c0cc042ee` + matching server, plus client properties
  `debug.q3pw.output_queue=2` (default age bound 22,223 µs) and `debug.q3pw.decode_workers=1`. Harness cell:
  `queue2-500` via `tools/quest3/frame_loss_profiles.py` (branch codex/output-queue).
- Evidence (automatic, unworn, chart source, 3 interleaved runs per cell, frame-loss counters on):

| Cell | Completed eye copies/s (fresh) | Mean | Superseded/s | 2-period gaps / ~1750 | Pipeline latency p50 (ms) |
|---|---|---|---|---|---|
| loss-control500 (depth 1) | 79.4, 85.5, 84.5 | 83.1 | 10.6, 4.6, 5.5 | 222, 97, 114 | 68.8, 44.3, 63.2 |
| **queue2-500** | **89.3, 88.4, 88.7** | **88.8** | 0.7, 1.7, 1.3 | 28, 54, 32 | **56.9, 55.6, 56.5** |
| queue2-wait-500 (+frame_wait_us=1000) | 84.5, 89.9, 90.0 | 88.1 | 4.5, 0.1, 0.0 | 124, 8, 13 | 68.4, **83.0, 83.7** |

  - Decoded 90.0/s in every cell (server pacing on, so 90 distinct source frames/s); the accounting closes
    (decoded − superseded − copied = 0/−1). So queue2's ~89/s are ~89 distinct frames, not repeats.
    Duplicate source keys presented: `selected_equal=2`, `regressed=0` over 4,847 presents (logcat counters).
  - Depth 2 removes the "bad mode" (no run below 88/s) with no latency cost: p50 56 ms vs control 44–69 ms
    (bimodal phase). + frame_wait 1000 reaches a perfect 90.0 in 2 of 3 runs but parks frames one period
    longer (+~27 ms p50, 83 ms): not worth it. Rates: runtime accepted 90 Hz; decode 5.9 ms (budget met);
    sustained live in-headset 90 Hz still needs the owner's Metro look.
  - Activation: sweep 1's marker had rotated out of the 256 KiB logcat ring; sweep 2 read it right after each
    cell start (`depth=2 max_age_us=22223 ring=4 workers=1`; control `depth=1 ring=3`). Sweep 2 repeated
    queue2 at 88.9, 89.8, 88.6 (see C3).
- Look at: Metro head turns and strafing for micro-stutter vs C1; whether latency feels the same; no
  out-of-order/backwards frames. Compression is unchanged from C1 (same codec settings).

### C1 — FOV crop on PyroWave Haar 500 (2026-10-06, session 25)
- Settings: as the session-25 sanity cell (PyroWave Haar, 3072x3232/eye render, 500 Mbps,
  90 Hz, RDO 65.28 px/deg, compute decode, TCP) plus `video.fov_crop.enabled=true`,
  horizontal 0.854 / vertical 0.85 (stream 2624x2752/eye). Foveated encoding off.
  Harness cell: `diag-crop-only` in `ws/session25.py`.
- Evidence: owner saw no flashing and "no visible difference" on the chart. GPU decode
  p50 5.89 ms (vs ~8.9–9.4 full FOV), decode-to-fence 8.4 ms, latency 49 ms (vs 60–80).
  Fresh rate stayed ~85/s, so the limit moved upstream (server render/encode or network).
- Look at: Metro fence and the edges of the view (is the crop noticeable?), stutter on
  head turns.

## Automatic sweeps, 2026-10-06 evening (unattended, chart source, installed 7705a40 pair)
All cells are FOV crop as C1 unless noted; 20 s captures; restore verified clean after each sweep.

| Cell | Change | Fresh/s (native eye copies) | Notes |
|---|---|---|---|
| crop-500 (x4 incl. diag-crop-only) | – | 85.0, 83.6, 87.0, **64.8** | bimodal from run to run |
| crop-400 | 400 Mbps | 85.5 | net 6.4 ms |
| crop-300 | 300 Mbps | 65.6 | same "bad mode" pattern as the 64.8 run |
| crop-buf25 / crop-buf1 | `max_buffering_frames` 2.5 / 1.0 | 85.8 / 81.0 | |
| crop-300-buf25 | 300 Mbps + buffering 2.5 | 82.1 | |
| **crop-nopace** (x3) | `enforce_server_frame_pacing=false` | **90.0, 90.0, 89.8** | decode 6.4 ms, dtf 8.7 ms; GraphStatistics missing; needs a client relaunch after ALVR's SteamVR restart |
| full-nopace (x2) | pacing off, full FOV (no crop) | 85.9, 85.5 | dtf 11.2 ms: decode-bound again without the crop |

| crop-500 control (x3, phase sweep) | – | 78.5, 84.9, 80.2 (mean 81.2) | |
| **crop-wait** (x3) | `debug.q3pw.frame_wait_us=1000` | **85.7, 87.1, 87.3 (mean 86.7)** | no bad-mode run; capped at 1 ms by design |
| crop-rdt (x3) | `debug.q3pw.runtime_display_time=1` | 85.3, 85.7, 83.9 (mean 85.0) | |

C1 add-on: `debug.q3pw.frame_wait_us=1000` (client property, installed build) gave +5.5 fresh/s over interleaved
controls. It's a harmless C1 extra to try; the full fix (two-deep client output queue) is on `codex/output-queue` (Astra).

Root cause (Codex Astra, `codex/frame-skip`, docs/FRAME-LOSS-DIAGNOSIS.md): the client's one-slot FrameSlot overwrites
decoded frames before the render loop picks them up; counters reconcile exactly. Pacing only shifts the phase.
Pacing-off overproduces (~112 decoded/s), so its 90/s isn't proven to be 90 distinct frames; don't hand it to the
owner until frame dumps or the frame-loss counters confirm freshness.

Findings:
- The source isn't the cap: the chart submitted 89.6 frames/s. The network isn't either: lower bitrates shorten
  network time but don't raise the fresh rate.
- With server pacing on, the client decodes frames and then never presents ~10 % of them (~30 % in the
  "bad mode"). Loss is uniform within a run, not stalls; which mode you get is set per connection.
- With pacing off, the client decoded ~113 frames/s and presented 90.0/s. GraphStatistics disappear, so
  content-freshness and pose timestamps are unverified: possible judder. Investigation: Codex
  `codex/frame-skip` (Astra), docs/FRAME-LOSS-DIAGNOSIS.md when done.
- Foveation flashing root cause found: WO-8 compression shader linkage bug (TEXCOORD0 register 0 vs 1);
  every foveated cell streamed 18–26 Mbps of constant-size packets. Fix on `codex/foveation-flash`
  (5f883ff), full CI build pending; re-test the foveated cells on that pair.

## Foveation-fix pair (2026-10-06 ~22:00, `codex/fov-dump-candidate` c24a9fe, CI 37516841718, installed on the Quest)
APK `20.13.0-ljk1291.2+c24a9fe580d8` (same signing cert; rollback: out/t123-candidate-37444400918). Server staged
separately in ws/server-fov-dump-37516841718.

| Cell | Mbps (was) | Fresh/s | Decode p50 | Notes |
|---|---|---|---|---|
| diag-crop-only | 503.9 | 85.8 | 9.5 | unchanged baseline |
| t1-on (PyroWave Medium FFE + crop) | **503.5 (18.4)** | 74.4 | 18.8 | full-budget, varying packets: encoder input fixed |
| diag-fov-only (FFE, no crop) | **504.5 (25.8)** | 55.4 | 23.4 | decode-bound |
| sanity (Haar full FOV) | 503.8 | 82.7 | 17.4 | |
| **h264-chart (stock H.264, H264Fit + crop)** | 5.4 (23.5) | **90.0** | 12.1 | static chart compresses to almost nothing with inter frames |

- Flashing: the encoder now gets real frames on every foveated path, and the dumps' black-frame checks find
  0 black decoded or presented frames in the H.264 cell. A confident "fixed" needs one human look or the PyroWave dump
  run (in progress).
- **H.264 + foveation is the strongest 90 Hz path so far** (90.0 fresh/s). Compression on the static chart is
  nearly transparent (54–69 dB once the range mapping is accounted for). The apparent limited→full range
  expansion in the dumps (gain 1.16, offset −18.6) is a capture artifact: production applies the correction
  the dump readback skipped (docs/H264-RANGE.md on `codex/h264-range`). Unverified: clipping at the range
  ends. Static-chart H.264 at 5 Mbps says nothing about motion; Metro motion is where H.264 has to prove itself.
- PyroWave foveated (T1) dumps: 11 exact pairs, 0 black/blank decoded or presented frames at 503 Mbps.
  **Flashing fixed** by automatic evidence (needs only the owner's confirmation look).
- Visual review (Claude): Haar shows 8–16 px square tiles and line-strength steps at tile boundaries
  (Haar crop/full FOV; max errors 95–102 levels on text and stripes). CDF 9/7 (T1) has no tiling, just
  fine noise on gratings (max 32–40). Astra's independent review is pending.

### Controlled wavelet comparison (2026-10-06 ~22:40, same pair, identical crop geometry and crop coordinates)
| Cell | Fresh/s | Decode-to-fence p50 | Max/mean abs luma error (gratings crop) |
|---|---|---|---|
| diag-crop-only (Haar, RDO 65.28) | **84.9** | 8.6 ms | 95 / 1.43 |
| crop-cdf97 (CDF 9/7, RDO 65.28) | 54.9 | 18.0 ms | 114 / 2.40 |
| crop-cdf97-rdo24 (CDF 9/7, RDO 24) | 58.7 | 16.6 ms | 44 / 1.77 |
- **CDF 9/7 cannot hold 90 Hz on the Quest decoder** even with the crop. Haar is the only viable PyroWave
  wavelet for 90 Hz here.
- Visually (Claude) all three reproduce every grating and line in the decoded image; differences are barely
  perceptible on this static chart. Haar errors are edge-localized with square patches; CDF 9/7 spreads
  low-amplitude error and faint banding into dark flat areas. Crops: results/local/session-25/visual-review-controlled/.
- Astra's controlled review (task-mux5fdkk-qdka5d, read-only, gpt-6-astra, judged MIDDLE vs LEFT): ranking for thin
  lines/text **1) Haar, 2) CDF 9/7 RDO 65.28, 3) CDF 9/7 RDO 24**. Severity (1–5) per region gratings / lines-text /
  gratings-right: Haar 2/2/2 (faint 8–16 px rectangular patches, uneven faint strokes, rules stay continuous);
  CDF 9/7 RDO 65 3/3/3 (halos and parallel echoes beside rules, faint rules become soft low-contrast bands);
  CDF 9/7 RDO 24 3/**4**/3 (both faint horizontal rules lose a ~60–65 px section: faint fence strands could vanish
  or pop in motion). Main PyroWave-at-500 problem: fine-detail contrast corruption (uneven, ringing, softened or
  dropped thin strokes), not big blocks or smear. Shimmer judgements are predictions from stills.
- Planner and Astra agree: Haar is the best PyroWave wavelet here on both rate and look.
- Astra's earlier, uncontrolled review ranked Haar crop ≳ Haar full > T1 (CDF 9/7 + RDO 24 + foveation: broader
  ringing). Claude's opposite first read relied on the exaggerated x16 diff panel; Astra's reading was adopted.

## Measured, not yet judged (need frame dumps)
- Render 3840x4032 downsampled to Godlike (`downsample-adaptive`: 82.5 fresh/s, latency
  72 ms; `downsample-bilinear`: 84.7 fresh/s, 67 ms). Decode unchanged (~8.95 ms).
  Unattended, so no visual verdict yet; re-screen with codex/frame-dump.
- 72 Hz Haar full FOV (`refresh-72`): 70.3 of 72 fresh/s (98 % fresh vs ~94 % at 90 Hz),
  decode 8.0 ms. Supports the owner's guess that the 90 Hz stutter is missing fresh frames;
  a smoother but lower-rate fallback, not the goal.

## Rejected (session 25)
- Foveated encoding (Medium, H264Fit): black flashing on every codec/path. Blocked until
  codex/foveation-flash lands.
- `debug.q3pw.decode_priority=low`: 69 vs 85 fresh/s.
- `debug.q3pw.layer_filter=sharpen_hq+supersample_hq`: owner saw worse compression on the
  magenta diagonal. `supersample_hq` alone: no visible difference.

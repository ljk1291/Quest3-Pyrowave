# Hands-on candidates

Configurations that passed automatic screening and are worth the owner's in-headset look
(Metro fence checkpoint, head motion). Newest first. Each entry: exact settings, the
evidence that put it here, and what to look at. Rejected options are listed at the end
so they aren't retried by accident.

## Decoder V2 live: CDF 5/3 at 90 Hz (2026-10-08 01:17–01:26, unworn, sweep `v2live`, 9c126c6 installed)
FOV crop 2624x2752/eye (5248x2752 stereo), 90 Hz, queue depth 3, TCP, swaying chart, gpuLevel 7, 160 MHz (2401 Mbps,
RSSI −4), battery 42–44 °C. One sample per cell. Markers confirmed per cell: `[Q3PW_CDF53V2] requested=5 active=5`,
`[Q3PW_PRESENT_YCBCR] active=1` (v2 cells), `[Q3PW_HAAR32] requested=5 active=5` (h32). Server CSF marker: requested=0
(density-only `-csf`, no `PYROWAVE_HEADSET_CSF`). Restore exit 0.

| Cell | Fresh/s | Mbps p50 | Net p50/p95/p99 | GPU decode p50 | Dtf p50 | Latency p50 | Skipped |
|---|---|---|---|---|---|---|---|
| hq-haar1250-fabrc-csf (control, stock Haar) | 89.6 | 1255 | 11.6 / 15.8 / 20.0 | 7.0 | 8.9 | 88.7 | 5 |
| **hq-cdf53-1000-v2** (mode 5) | **89.9** | 1008 | 9.7 / 12.2 / 14.2 | **3.4** | **5.0** | **66.5** | 0 |
| hq-cdf53-1000-v2m4 (mode 4) | 89.6 | 1009 | 9.1 / 12.2 / 15.4 | 4.1 | 6.4 | 70.7 | 0 |
| **hq-cdf53-1000-v2-fabrc-csf** | **89.9** | 1008 | 10.6 / 18.0 / 24.3 | 4.3 | 5.5 | 71.5 | 0 |
| **hq-cdf53-1250-v2-fabrc-csf** | **89.7** | 1232 | 11.2 / 14.9 / 22.1 | 4.5 | 5.4 | 65.1 | 0 |
| hq-haar1250-h32-fabrc-csf (haar32 mode 5) | 90.0 | 1261 | 12.4 / 17.5 / 22.0 | 3.8 | 4.6 | 66.0 | 0 |

- **CDF 5/3 now sustains ~90 fresh/s live at our Godlike-crop size** (fast53 v1 managed 72). Decode-to-fence halves
  (8.9 → 5.0–5.5 ms) and the estimated pipeline latency drops ~20 ms vs the stock-Haar control. Mode 5 beats mode 4
  by 1.4 ms dtf (no separate convert). This removes the only blocker for 5/3, which offline needs ~1.7x fewer bytes
  than Haar on natural content and degrades to blur instead of square blocks.
- haar32 mode 5 also halves Haar's decode cost (7.0 → 3.8 ms) for the same bitstream.
- Unworn, 20 s per cell, one round: runtime-accepted 90 Hz and sustained in this live window; worn/head motion and
  Metro still to do. Quality (dumps, Library thumbnails) below.

## Candidate C9 for the owner's worn Metro look: CDF 5/3 at 90 Hz (2026-10-08 ~02:20)
**`hq-cdf53-1000-v2-fabrc-csf-metro`** (and `hq-cdf53-1250-v2-fabrc-csf-metro`) on the installed Decoder V2 build
9c126c6, vs C8 `hq-haar1250-fabrc-csf-metro` on the same build. Run e.g.
`hq-sweep.ps1 -Pair decoder-v2-37690049712 -Cells hq-cdf53-1000-v2-fabrc-csf-metro` (owner launches Metro).
Evidence: 90.0 fresh/s live with Metro running, ~20 ms lower latency than Haar, 6–7x less block structure, ~30 % less
static-view flicker (sections below). Look for: fine-texture shimmer and thin lines while moving the head; blur vs
Haar's square patches; ringing (halos) at hard edges such as HUD text. Not yet: full `PYROWAVE_HEADSET_CSF=1`.

## Decoder V2 with Metro running, in-headset Library recordings (2026-10-08 01:55–02:10, unworn, sweep `v2metro`)
New `hq-sweep.ps1 -LaunchMetro`: per `-metro` cell it starts Metro on our stream (launch_metro_steamvr.py), waits 75 s,
takes 2 x 5 s `screenrecord` (100 Mbps, 4128x2208) + a screencap, runs the 20 s capture under the game's load, then
closes Metro. Unworn, the SteamVR Library dashboard stays in front of Metro (Metro shows as "now playing"), so the
recordings are the owner's suggested judge: static game thumbnails in the final display buffer. Two rounds, interleaved.
**Health stop at 02:09** (battery ≥ 60 °C during the last capture, after ~50 min of near-continuous streaming at
≥1 Gbps while fast-charging; the charger then stopped, status discharging, 57 °C at 02:12). The sweep's cool-down
only triggers at ≥52 °C between cells, and a cell itself took the battery from <52 to 60 °C. Restore exit 0,
guardian_pause restored, SteamVR and Metro closed.

| Cell | Fresh/s | Mbps p50 | Net p50/p95/p99 | GPU decode | Dtf p50 | Latency p50 | Shimmer: flicker px / tstd textured |
|---|---|---|---|---|---|---|---|
| Haar 1250 headset-RDO (r1) | 89.7 | 1186 | 11.6 / 13.5 / 16.8 | 6.8 | 8.7 | 74.0 | 0.16 % / 0.40–0.43 |
| CDF 5/3 V2 1250 (r1, r2) | 90.0 / 89.9 | 1012 | 9.2–9.9 / 12.3 / 13.5–14.9 | 3.3–3.5 | 4.4–4.9 | **55.6** | **0.11–0.12 %** / 0.41 |
| CDF 5/3 V2 1000 (r1) | 90.0 | 1009 | 10.1 / 12.9 / 16.2 | 4.2 | 5.1 | **51.7** | **0.09–0.12 %** / 0.40–0.41 |

(all with fast ABR v2 Capacity and RDO 27.8; shimmer = `ws/scripts/shimmer.py`, 240 frames per clip, static pixels
~91 %; Haar round 2 not reached)
- **With Metro running, CDF 5/3 V2 holds 90.0 fresh/s and cuts estimated latency by ~20 ms** (52–56 vs 74 ms).
- On the static Library view, measured flicker is tiny for all cells and ~30 % lower for 5/3 (0.09–0.12 % vs 0.16 % of
  static pixels above 1.5 codes temporal std). The screenrecord encoder's own noise is part of this floor, so it is a
  ranking, not an absolute. Unworn static views show little codec shimmer at ≥1000 Mbps; the owner's flicker is likely
  bound to head motion and to Metro's own detail (next: worn check).
- The 1250 5/3 cell sent only ~1012 Mbps on this view (Haar 1186): likely 5/3 reaching the coefficient floor of this
  easy content below the cap (PyroWave stops when everything is coded). Not yet verified from the encoder log.
- Recordings and screencaps: results/local/session-25/metro-rec-v2metro-20261008-015454/.
- After the stop the Quest reported **AC powered: false** (charger no longer detected) and drained ~2 %/min awake on
  the Guardian dialog (39 → 31 %); put to sleep at 02:17 (`KEYCODE_SLEEP`), 56 °C. Testing paused: needs the charger.

## Decoder V2 dumps: chart and SteamVR Library thumbnails (2026-10-08 01:26–01:52, unworn, dump `v2dump`)
Same pair and settings as `v2live`; lossless exact pairs (server encoder input yuv420p vs client post-decode RGBA).
`-metro` cells now dump with no chart: SteamVR shows the Library dashboard (game thumbnails over the grey void; the
owner's suggestion as a natural-image flicker target). Restore exit 0. Scorer: frame_score.py (fov-dump tree).

| Cell | Pairs | PSNR-Y | Edge PSNR | HF err | Temporal static p99 | Blockiness 8/16/32 | Y err mean / MAE / max | ≥1 code |
|---|---|---|---|---|---|---|---|---|
| Chart Haar 1250 headset-RDO | 7 | 62.6 | 55.4 | 0.060 | 0.79 | .011 / .018 / .029 | +0.13 / 0.16 / 1 | 0.0 % |
| Chart CDF 5/3 V2 1000 | 7 | 59.8 | 52.6 | 0.141 | 1.30 | .005 / .007 / .007 | +0.27 / 0.30 / 17 | 0.3 % |
| Chart CDF 5/3 V2 1250 | 7 | 58.0 | 52.1 | 0.119 | 1.37 | .005 / .004 / −.001 | +0.26 / 0.28 / 7 | 0.1 % |
| Library Haar 1250 | 7 | 56.6 | 51.8 | 0.553 | 1.82 | .194 / .194 / .196 | −0.03 / 0.10 / 5 | 0.8 % |
| Library CDF 5/3 V2 1000 | 6 | 55.4 | 50.6 | 0.643 | 1.76 | .034 / .034 / .033 | −0.16 / 0.25 / 20 | 2.4 % |
| Library CDF 5/3 V2 1250 | 6 | 56.5 | 52.5 | 0.537 | 1.54 | .028 / .028 / .028 | −0.15 / 0.23 / 10 | 1.5 % |

(all with fast ABR v2 Capacity and RDO 27.8 px/deg; "Y err" = client RGB→Y minus server Y, 8-bit codes, one pair)
- **Every cell is near-lossless on these targets** (MAE 0.1–0.3 codes): the chart and the dim Library thumbnails are
  too easy at ≥1000 Mbps to rank the codecs. The PSNR gap is mostly a constant 0.15–0.27-code bias from mode 5's
  YCbCr→RGB done in the present/dump shader (different rounding than the separate convert), not visible loss.
- What does separate them: **CDF 5/3 has 6–7x less block structure** (Library .03 vs .19; Haar's 8/16/32 grid is the
  "square patch" artifact), and 1250 5/3 has the lowest Library shimmer (1.54 vs 1.82). Haar keeps hard synthetic edges
  exact while 5/3 shows rare local outliers (max 7–20 codes, ringing at chart edges).
- The owner's visible compression is in Metro, much harder content than either target. Next: Metro itself (in-headset
  `screenrecord` of the menu, `ws/scripts/shimmer.py`), and full `PYROWAVE_HEADSET_CSF=1`.

## Decoder V2 port standalone on the Quest (2026-10-08 ~01:15, CI 37690049712 tools, before install)
`pyrowave_android --compare-v2 cdf53.wave haar.wave <prefix> 30` (5248x2752 C420 chart frame, 750 Mbps budget),
`PYROWAVE_PRECISION=1`, `debug.oculus.gpuLevel`=7, battery 42–44 °C, 12 fresh processes per run, 5 warm-ups,
30 samples. Decode GPU time only (excludes readback; the old path's separate convert, ~4.9 ms, is not in "stock"):

| Arm | mean ms, packed levels 4 | mean ms, packed levels 2 | Parity vs own stock (max / mean Y) |
|---|---|---|---|
| CDF 5/3 stock (apron) | 16.48 (best 12.09) | 13.32 (best 12.09) | – |
| CDF 5/3 V2 mode 1 / 2 | 7.02 / 6.16 | 6.95 / 6.16 | 1 / 0.005 pass |
| **CDF 5/3 V2 mode 3 / 4 / 5** | **3.72 / 3.80 / 4.01** | 4.22 / 4.24 / 4.24 | 1 / 0.005 pass |
| Haar stock (= what we ship) | 6.65 | 6.14 | – |
| haar32 mode 1 / 2 | 5.66 / 4.48 | 5.30 / 4.51 | 1 / 0.004 pass |
| haar32 mode 3 / 4 / 5 | 3.34 / 3.81 / 4.14 | 3.66 / 3.90 / 5.42 | 1 / 0.004 pass |

- **All 20 accelerated arms pass the parity gate (max 1 code value on Y, Cb, Cr).** Exit 0 both runs.
- **CDF 5/3 V2 mode 5: 4.0 ms, 3.3–4x faster than stock 5/3 and faster than the stock Haar we ship (6.1–6.6 ms)**,
  and mode 5 also removes the separate RGBA convert in the live client. Matches upstream's 3.6–4.4 ms at this size.
  Packed levels 4 (default) is as fast or faster than 2. Standalone budget only; live 90 Hz below.
- APK `20.13.0-ljk1291.2+9c126c69a0ba` then installed with `adb install -r` (same cert; rollback a928435 in
  out/q160-candidate-37649808169, 7f85e87 in out/q160-candidate-37589333446).

## Headset RDO weighting, settings only (2026-10-07 23:32–23:50, unworn, dump `csf2`, a928435)
New cell suffix `-csf` (`ws/hq_profiles.py`): `video.pyrowave.rdo_pixels_per_degree` = **27.8** (= upstream's headset
CSF Nyquist 0.5·2752/99 = 13.9 cycles/deg at our crop) instead of 65.28 (the stock 96 dpi monitor at 1 m). This part
of upstream's encoder change needs no build; the LF boost, chroma 1.6 and discard weight are in the `codex/decoder-v2`
port (`PYROWAVE_HEADSET_CSF=1`). FOV crop, Haar, TCP, swaying chart, 8–9 exact lossless pairs per cell.
Sheets: results/local/session-25/compare-csf/.

| Cell | PSNR-Y full | Edge PSNR | HF error | Temporal static p99 | Blockiness 8/16/32 | Region mean \|err\| gratings / lines-text / gratings-right |
|---|---|---|---|---|---|---|
| Haar 1000 monitor | 58.4 | 49.7 | 0.172 | 2.94 | .036 / .048 / .058 | 0.42 / 0.43 / 0.39 |
| **Haar 1000 headset** | 59.8 | 54.7 | 0.075 | **1.21** | .017 / .023 / .020 | 0.32 / 0.33 / 0.29 |
| Haar 1250 monitor | 59.9 | 54.4 | 0.086 | 1.51 | .011 / .014 / .019 | 0.42 / 0.38 / 0.37 |
| **Haar 1250 headset** | **62.7** | **56.4** | **0.046** | **1.18** | **.008 / .007 / .010** | **0.27 / 0.28 / 0.27** |

- **Headset weighting is better on every metric at both rates.** At 1000 Mbps it halves blockiness and cuts the
  static-area temporal p99 from 2.94 to 1.21 codes. That is the frame-to-frame shimmer proxy, matching the owner's
  "flashing". Haar 1000 headset ≈ Haar 1250 monitor; Haar 1250 headset is the cleanest PyroWave image so far.
- Planner's look (lines-text x16): with the monitor weighting, the thin horizontal lines and the grating light up in
  the difference (brightness errors on lines). With the headset weighting they nearly vanish. Haar 1000 headset still
  shows faint square patches around "+" and the text.
- **Astra** (task-muyn6jtn-l3opjo, gpt-6-astra, read-only, native scale; 0–3 blocks / strokes / stripes / ringing):
  1000 M 0/1/1/0, **1000 H 1/1/0/0**, 1250 M 0/1/1/0, **1250 H 0/0–1/0/0** on all three sheets. Ranking on every sheet:
  **1250 H > 1000 H > 1250 M ≥ 1000 M**; "1000 H ≥ 1250 M overall: yes". Trade-off: the headset weighting slightly
  raises faint square-patch structure at 1000 (borderline 0/1). It improves strokes and removes stripe errors.
  Upstream's LF boost (levels ≥3 x6, in the `codex/decoder-v2` port) targets exactly those blocks: test
  `PYROWAVE_HEADSET_CSF=1` next.
- **Candidate C8 for the owner's Metro look: `hq-haar1250-fabrc-csf-metro`** (or `hq-haar1000-fabrc-csf-metro`), on the
  installed a928435. Look at fine texture shimmer and thin lines in menus vs C6 (`hq-haar1250-fabrc-metro`).

## Upstream JMS1717 `.62` as-is, live over Wi-Fi at 90 Hz (2026-10-07 19:52–20:00, unworn, sweep `upstream62`)
Their CI pair b8e905c (APK `20.13.0-quest3.pyro.62`, package io.github.jms1717.quest3pyrowave, installed beside ours;
RECORD_AUDIO granted as for ours so no dialog blocks an unworn launch), their server staged in
ws/server-upstream-jms1717-37643381349 and registered only during the run. Harness: `ws/upstream_profiles.py`
(`up-<haar|cdf53>-<mbps>-e<size>`) via `hq-sweep.ps1 -Adapter`, with `Q3PW_PACKAGE` and `Q3PW_CLIENT=auto`
(their client is 7380.client). Their defaults: every debug.q3pw.* property cleared, no FOV crop, render 3072x3232/eye,
1000 Mbps, TCP, swaying chart, max-GPU-clock setting off. **Their client ran at GPU level 4 (VrApi `GPU=4/4`,
545–640 MHz), not 7**: QGO's `debug.oculus.gpuLevel=7` does not reach it, so these are their "clock off" numbers.

| Cell (encoded per eye) | Submitted/s | Distinct frames/s (proxy) | GPU decode p50 | Dtf p50 / p95 | Net p50/p99 | Latency p50 | GPU clock |
|---|---|---|---|---|---|---|---|
| Haar 2080x2208 | 89.9 | 88.8 | **2.47** | 3.68 / 4.77 | 9.9 / 15.7 | 53 ms | 545 |
| **CDF 5/3 (V2) 2080x2208** | 89.7 | **89.2** | 4.98 | 5.74 / 6.13 | 9.3 / 13.8 | **39 ms** | 545 |
| Haar 2624x2752 (full FOV, scaled) | 88.7 | 87.7 | 8.25 | 9.42 / 10.08 | 10.3 / 15.3 | 52 ms | 545 |
| **CDF 5/3 (V2) 2624x2752** | 88.4 | **87.6** | 8.74 | 9.89 / 10.78 | 10.2 / 15.2 | 52 ms | 599 |
| Haar 3072x3232 (full Godlike) | 89.1 | 88.2 | 6.66 | 9.66 / 11.39 | 10.4 / 15.4 | 60 ms | 640 |
| CDF 5/3 3072x3232 | – | – | – | – | – | – | not run (owner started a game; sweep stopped, restored) |

- Our bench can't read their fresh-output counter, so "distinct frames/s" counts distinct tracking target
  timestamps over the 20 s window. It is a proxy, not verified unique frames. Submission and duplicate counts come
  from the same report.
- **Upstream holds ~88–89/s at 90 Hz for CDF 5/3 even at our Godlike pixel count (5248x2752) on a 545–599 MHz GPU**,
  with network and latency equal to Haar. Our fast53 v1 reaches 72/s on the same pixel count (CDF 5/3 at 90 Hz is
  solved upstream). The e2624 Haar decode (8.25 ms) is slower than e3072 (6.66) because of the clock (545 vs 640 MHz);
  the clock varied cell to cell.
- Caveat: no FOV crop upstream, so 2624x2752 spreads the full FOV over fewer pixels (less detail per degree than our
  crop). 3072x3232 is VD Godlike's full size.
- **Owner look in Metro: still to do** (their dashboard, these settings). Registration and SteamVR files were restored
  (restore exit 0, VD and OpenXR unchanged).

## Candidate a928435 installed and swept (2026-10-07 19:15–19:50, unworn, sweeps `a928` + `a928b`)
APK `20.13.0-ljk1291.2+a928435a8636` installed with `adb install -r` (same cert; rollback 7f85e87 in
out/q160-candidate-37589333446). FOV crop 2624x2752, Haar unless named, 90 Hz, queue depth 3, TCP, swaying chart,
gpuLevel 7. Two samples where two values are given (round 1 / round 2):

| Cell | Fresh/s | Mbps p50 | Net p50/p95/p99 ms | GPU decode | Dtf p50 | Skipped | ABR multiplier mean (min), shrunk/s |
|---|---|---|---|---|---|---|---|
| hq-haar2000-fabrc (v2 Capacity) | **88.5 / 87.9** | 1349 / 1247 | 13 / 26–28 / 36 | 6.6 | 8.7–8.8 | **8 / 17** | 0.70 / 0.63 (0.35), ~90 |
| hq-haar2000-fabrm (v1 m) | 86.1 / 87.7 | 1423 / 1391 | 14–15 / 25–30 / 29–38 | 6.7–7.0 | 9.2–9.3 | 69 / 32 | 0.69 / 0.70 (0.35), ~86 |
| hq-haar1250-fabrc | 89.8 | 1206 | 10 / 14 / 16 | 7.5 | 9.4 | 1 | 0.92 (0.67), 42 |
| hq-haar1000-fabrc | 89.7 / 89.1 | 1007 | 10–11 / 13–22 / 17–32 | 7.3–7.4 | 9.2 | 0 / 7 | 1.00 / 0.99 |
| hq-cdf53-1000-f53 (fast53 v1) | 72.2 | 1008 | 9.5 / 12 / 15 | 11.0 | 13.1 | 339 | – |
| hq-cdf53-1000-f53v3 | 63.3 | 1009 | 9.5 / 13 / 15 | 12.7 | 15.0 | 511 | – |
| hq-cdf53fov1000-f53v3 (+ Medium FFE) | 79.1 | 1008 | 9.5 / 13 / 17 | 9.1 | 12.0 | 202 | – |

- **Fast ABR v2 (Capacity) vs v1 m at the over-capacity proxy**: slightly more fresh frames (88.2 vs 86.9 mean) and
  far fewer client skips (8–17 vs 32–69), at similar network p99 (~36 ms). It still cuts to the 0.35 floor every
  second at 2000. At 1250 it is more conservative than needed (budget mean 0.92, 1206 vs ~1260 Mbps for v1).
  Verdict: v2 is a modest win under overload. It is the better default for the owner's worn head-motion check, but
  not a fix for the saw-tooth.
- **5/3 live**: fast53 v1 72 fresh/s and v3 63; with FFE 79. None reaches 90; superseded by the upstream Decoder V2 port.
- Sweep gotcha fixed: the cool-down ran with the previous cell still streaming (battery 47 → 51 °C while
  "cooling"). `hq-sweep.ps1` now stops the stream first (`session25.py stop`), triggers at ≥52 °C, waits for ≤48 °C,
  and gives up after 5 min without a new low (on the charger it plateaus at ~51 °C). The first sweep was aborted
  at that point and restored by hand (harness restore exit 0, guardian_pause back to '', proximity restored).
- Note for compression: the server log shows our encoder RDO at "65.28 px/deg, Nyquist 32.64 cycles/deg, legacy
  96 DPI @ 1m" = the monitor CSF. Upstream's headset CSF uses 0.5·2752/99 ≈ 13.9 cycles/deg (≈ 27.8 px/deg) at our
  crop height. Our existing `rdo_pixels_per_degree` setting can test the main part of it with no new build.

## Upstream Decoder V2 on our device and frame size (2026-10-07 ~19:10, standalone, no install)
`decoder_ab wavelets 5248 2752 1388889` (their CI build b8e905c, /data/local/tmp/q3pw-ab; synthetic frame at the
1000 Mbps / 90 Hz cap, their in-process encoder; arms interleaved, 4 blocks x 20 frames; governor moved the
clock 421–640 MHz between arms although `debug.oculus.gpuLevel`=7):

| Decoder | p50 per frame (summary) | at 599 MHz |
|---|---|---|
| stock Haar (= ours) | 7.09 ms | – |
| Haar haar32 mode 3 / 5 / 6 | 3.30 / 3.28 / 2.70 | 2.81 / 2.77 / 2.29 |
| stock CDF 5/3 | 13.44 | 12.23 |
| **CDF 5/3 V2 mode 3 (qp) / 5 / 6** | **4.99 / 4.41 / 3.40** | **3.58 / 3.60 / 3.12–3.40** |

- **V2 mode 5 decodes our 5248x2752 5/3 frame in ~3.6–4.4 ms: ~2.3x faster than our fast53 v1 (8.4 ms, below)
  and faster than the Haar we ship (5.1 ms standalone).** Their Haar modes are ~2x faster than stock Haar too.
  Mode 5 also removes the RGBA convert pass (it writes packed YCbCr into the AHB; our convert is 4.9 ms standalone).
- Bitstream: same PyroWave pin d2997ac; Decoder V2 is decode-only (exact to the stock 5/3 decoder within 1 code
  value), so it decodes our encoder's 5/3 stream. Their encoder adds rate-allocation changes only (headset CSF
  `cpd_nyquist = 0.5*height/99`, LF boost x6 on levels 3–4, chroma CSF 1.6, discard-distortion band weight;
  docs/ENCODER-CSF.md upstream): still bitstream-compatible and **a quality lever for us** (the stock CSF assumes a
  96 dpi monitor at 1 m and starves fine luma, which is what Metro textures need). Their published 207 Hz
  2080x2208 live numbers: 5/3 V2 mode 5 at 690 MHz ≈ Haar (192 vs 193.5 fresh/s).
- Conclusion: porting `patches/pyrowave-cdf53v2.patch` + `pyrowave-haar32.patch` (+ the client mode-5 present path)
  is the route to 5/3 at 90 Hz with headroom; our fast53 line is superseded. **Port started 2026-10-07 ~19:20**:
  Astra (gpt-6-astra, xhigh, task-muyddv9s-9chfrk) on branch `codex/decoder-v2` (worktree ws/worktrees/decoder-v2,
  from a928435). It covers decoders, client props `debug.q3pw.cdf53v2`/`haar32`/`packed_levels` (opt-in), mode 5,
  the opt-in headset-CSF encoder setting and a `pyrowave_android --compare-v2` tool.

## fast53 v2/v3 standalone check (2026-10-07 ~19:05, candidate a928435 tools, no install)
`pyrowave_android --compare-fast53 cdf53.wave haar.wave check-v23 30` (5248x2752 C420 chart frame, 750 Mbps
budget), `PYROWAVE_PRECISION=1`, **`debug.oculus.gpuLevel`=7** (v1's earlier 10.13 ms was at gpuLevel 2):

| Arm | decode mean | ratio to Haar | parity vs apron 5/3 |
|---|---|---|---|
| apron 5/3 (stock) | 14.73 ms | 2.87 | – |
| fast53 v1 | **8.40** (was 10.13 at gpuLevel 2) | 1.64 | max 1 (pass) |
| fast53 v2 | 19.32 (best 15.75) | 3.77 | max 1 (pass) |
| fast53 v3 | 9.77 | 1.91 | max 0 (exact) |
| Haar | 5.13 | 1.00 | – |

- All three are exact, none meets the ≤1.3x Haar gate; v2 and v3 are slower than v1. Convert (GLES bridge) adds
  4.92 ms on every arm. **Rejected as the 5/3 route**; upstream Decoder V2 (above) replaces it.

## Research: how others solve compression and motion (planner, 2026-10-07 ~08:50)
- **Virtual Desktop**: H.264+ up to 500 Mbps on Quest 3; recent releases add NVENC adaptive quantization,
  2-pass and 10-bit fixed foveation. No special motion mechanism: VD's own guidance is that H.264+ at
  400–500 needs "pristine network conditions" and otherwise "introduces hiccups". Its inter-coded H.264
  normally sends far less than the cap (our NVENC H.264 at a 500/750 setting sent ~270 Mbps), while
  intra-only PyroWave fills its whole byte budget every frame, so PyroWave uses much more airtime per
  "Mbps setting". WiVRn (open source) splits into per-eye encoders, UDP by default; nothing motion-specific.
- **ALVR itself**: the adaptive bitrate (2023 algorithm; `bitrate.mode = Adaptive` with
  `max_network_latency_ms`, encoder/decoder limiters) updates about once per second, too slow for a head
  turn but useful for sustained drops. The fork already feeds PyroWave's per-frame byte cap from it
  (docs/BITRATE.md). NeSt-VR (UPF, ALVR v20.6 fork, arXiv 2407.15614) is a steadier step-wise ABR; never
  merged upstream. Upstream ALVR's recent work (eye-tracked foveation) doesn't apply to Quest 3.
- **Upstream PyroWave (Themaister)**: designed for exactly this case. Intra-only 32x32 blocks decode
  independently; a missing block becomes a slight local blur. Since 2026-09-02 (already inside our pin
  d2997ac) the API has `pyrowave_encoder_compute_num_critical_packets` (protect only the low-frequency
  "critical" packets with FEC), `*_packetize_with_padding`, and `pyrowave_decoder_decode_is_ready_with_sideband`
  (decode a partial frame once the critical bands are pristine). **Our fork uses none of it**: TCP by default
  (head-of-line blocking and congestion backoff during Wi-Fi dips), and PWU2 UDP byte-fragments the frame
  and drops the whole frame if any fragment is missing (`pyroclient_decode` requires a complete frame).
- **CDF 5/3** (already supported end to end): offline it needs ~1.7x fewer bytes than Haar on natural
  content (Haar +103 %, 5/3 +17.9 % vs 9/7) and degrades to blur instead of square blocks; full-size
  Haar/1000 trails 5/3/500. It is blocked only by the slow shared-memory inverse on the Quest. The fast
  pair-local kernel (WO-6) had only a CPU proof; implementation started 2026-10-07 (Astra, `codex/fast53`).
- Not viable: neural/ML post-filters (no GPU budget left beside a 6–7 ms decode at 90 Hz); HEVC/AV1
  (Quest decode cap ~200 Mbps).
- Plan: (1) re-measure at 160 MHz (network probe + live ladder); (2) TCP vs PWU2 UDP live, then a
  partial-decode + critical-packet UDP transport if UDP loss is the problem; (3) fast 5/3 decode;
  (4) owner's worn check of the winners.

## Upstream JMS1717 `.62` (checked 2026-10-07 ~18:55) — likely answer to our decode limit
Upstream main (adeb86b; code = b8e905c, later commits docs-only) added, all today:
- **Decoder V2**: "Haar in about 2.6 ms and CDF 5/3 in about 3–4 ms per 2080 × 2208 stereo frame at 690 MHz"
  (≈4 ms / 5–6 ms scaled to our 5248x2752; our fast53 v1 is 10.1 ms). "CDF 5/3 removes Haar's block edges."
- Haar mode 5 with packed coefficients/luma, packed YCbCr output, **raw sRGB eye copy on by default**,
  a "maximum GPU clock" (690 MHz) option, 144–240 Hz, parallel wired connections, a 0.25 bpp quality floor.
- Their CI build of b8e905c (run 37643381349) was downloaded with the owner's OK to
  out/upstream-jms1717-37643381349 (checksums OK; APK signed CN=JMS1717, package
  io.github.jms1717.quest3pyrowave, coexists with ours; server zip sha256 052e5960…). It includes standalone
  Quest tools (`decoder_ab`, `pyrowave_android`, fence tests). **Not installed or tested yet** (next chat).

## VD vs ours on the Metro main menu (2026-10-07 ~18:30–18:50, worn, in-headset captures)
- **Method found**: `adb shell screencap -p` returns the headset's final display buffer: 4128x2208, both
  eyes, lens pre-warp, lossless PNG, for VD and ours alike (like-for-like stills). `adb shell screenrecord
  --time-limit 5 --bit-rate 100000000` records 4128x2208 at ~71 fps (headset H.264, lossy) for flicker.
  Files: results/local/metro-menu-2026-10-07/ (vd-screencap-183447.png, ours-haar1250-screencap-*.png,
  compare-vd-vs-haar1250-{full,zoom}.png, ours-haar1250-rec-184530*.mp4; desktop-mirror PNGs = source only).
- Ours (Haar 1250 + fast ABR m, 7f85e87) in the Metro menu: 88.2 fresh/s, GPU decode 6.2 ms, decode-to-fence
  9.0 ms, latency p50 90 ms; battery 51 °C (owner raised the stop to 60 °C for this run, now the rule).
- **Ours is darker**: on the matched picture, median luma 13 vs VD 22 (mean 25.9 vs 32.8, p90 70 vs 80);
  detail energy equal (Laplacian std 10.1 vs 9.9). Our colour path has no adjustments (colour correction
  off, encoding gamma 1.0, full range, `debug.q3pw.raw_srgb_copy=0`); upstream made raw sRGB eye copy the
  default. Either VD brightens or our eye copy darkens: A/B `raw_srgb_copy=1` next.
- At 2x zoom VD looks smoother; ours shows some Haar blockiness on edges (jacket, sign letters); text equal.
- Owner (verbatim): "I feel like the screenshots you took are not from in headset view as they do not show
  the same compression I can see and look identical to the VD ones, which isnt accurate". Our read: the
  captures are the display buffer, but a still cannot show temporal shimmer — intra-only coding re-quantizes
  fine detail every frame ("flashing"), while H.264 reuses static content. Judge compression over time.
- Metro on our stream needs a per-process SteamVR launch (VD is the system OpenXR runtime; see below).

## Owner hands-on, 2026-10-07 ~17:45–18:00 (worn, candidate 7f85e87, Metro Awakening fence)
| Cell | Owner (verbatim) | Measured |
|---|---|---|
| (SteamVR menu, `hq-haar1000-fabrm-metro`) | "What I am noticing in the steamVR menu though: Lines and other details still flickering. It also feels like we are at a lower res than godlike" | – |
| hq-haar1000-fabrm-metro (Metro fence) | "im there, for me compression is clearly visible" | capture stopped: battery 50 °C |

- **Metro was not reaching the stream**: the system OpenXR runtime is Virtual Desktop's
  (`HKLM\SOFTWARE\Khronos\OpenXR\1\ActiveRuntime` = `virtualdesktop-openxr.json`), so Metro (UE5/OpenXR)
  started on VD and exited (this morning's Metro attempt most likely failed the same way). Fixed without
  touching the registry: launch `MetroAwakening\Impact.exe` with `XR_RUNTIME_JSON=...\SteamVR\steamxr_win64.json`
  (per process) plus `SteamAppId/SteamGameId=2669410`, detached; SteamVR then loaded Metro's OpenXR
  bindings (`steam.app.2669410`). VD stays the system runtime. (Scratchpad helper `launch_metro_steamvr.py`;
  recreate from this description.)
- **Resolution check (owner's question)**: the crop is real and correct. Server `[FOV-CROP] active=true
  tangents=h0.8540/v0.8500 stream=3072x3232->2624x2752`; the client scales the same tangents into the
  projection layer it submits (stable-baseline-alvr.patch, `stream_input_loop`), so the image is shown at
  its true angular size, not stretched. Same geometry as VD's Godlike (≈2624x2776 over the same 85 % tangent
  span, docs/ARTIFACT-QUALITY-PLAN.md §1).
- **Flicker on thin lines in menus**: most likely intra-only requantization (every frame coded anew, so thin
  high-contrast lines vary frame to frame; H.264 reuses static content). Levers: higher rate, the compositor
  super-sampling layer flag (`debug.q3pw.layer_filter=supersample_hq`), a more efficient wavelet.
- **Health stop at battery 50 °C** within ~10 min of worn Metro play: the headset was on the charger while
  worn (charging + high-rate decode). Restore exit 0; SteamVR/Metro closed; Guardian unaffected. Next time:
  unplug during worn tests; the sweep script now waits for ≤44 °C when a cell would start at ≥47 °C.
- **Conclusion**: at Haar 1000 the owner sees clearly visible compression in Metro (natural textures), even
  though the chart is near-transparent. This confirms the offline finding that Haar is ~2x less efficient
  than CDF on natural content: the remaining lever is CDF 5/3 at 90 Hz (fast53 v2/v3 building now).

## Pre-hands-on tuning (2026-10-07 17:13–17:35, unworn, candidate pair 7f85e87, sweep `abrtune2`)
Fast ABR parameters are runtime settings, so they were tuned without a new build. Cells `-fabr[gsm]`:
default ×0.6/+0.05/1.0-frame threshold; g ×0.8/+0.02/1.0; s ×0.85/+0.02/1.5; m ×0.7/+0.03/0.75.
Round 1 complete; round 2 stopped by the health rule (battery temperature reached 50 °C during the
`hq-haar1750-fabrs` capture after ~40 min of continuous high-rate streaming on the charger; restore exit 0).

| Cell | Fresh/s (r1, r2) | Delivered Mbps | Net p50/p95/p99 ms | Multiplier mean (min) | Backlog p95 |
|---|---|---|---|---|---|
| 2000, default | 84.6 | 1453 | 23 / 39 / 45 | 0.72 (0.35) | 2.25 |
| 2000, g | 86.2, 87.2 | 1491–1588 | 18–19 / 30–33 / 35–37 | 0.73–0.77 (0.35) | 2.25 |
| 2000, s | 85.0, 86.5 | 1453–1624 | 23–29 / 38–49 / 47–57 | 0.71–0.78 (0.35) | 2.5–2.75 (9–14 drops) |
| **2000, m** | **87.3, 87.5** | 1413–1456 | **14 / 24–26 / 27–30** | 0.71–0.72 (0.35) | **1.5** |
| 1750, default | 87.1, 87.3 | 1576–1631 | 16 / 25 / 29–30 | 0.83–0.86 (0.35) | 1.75–2.75 |
| 1750, s | 87.4 | 1600 | 20 / 33 / 36 | 0.88 (0.35) | 2.25 |
| 1000 (q3 / q2) | 90.0 / 89.0 | 1005–1009 | 10 / 12–15 / 15–20 | 0.99 / 0.97 | – |
| 1250 (q3 / q2) | 89.6 / 88.4 | 1259–1260 | 12 / 14–15 / 18 | 0.99 / 1.00 | – |

- **m (×0.7, +0.03, 0.75-frame threshold) is the best v1 tuning**: reacting earlier keeps the backlog and
  latency lowest at overload (87.4 fresh/s, p99 ~28 ms vs default 84.6 / 45). It is free at normal rates.
- Every v1 setting still hits the 0.35 floor under overload: the controller cuts on every frame while
  already-queued data drains. Structural fix (one cut per episode, cut to the measured capacity, recover
  with memory): fast ABR v2, Astra, in progress.
- **Queue depth 2 vs 3**: about −7 ms latency estimate (1000: 76.5 vs 83.8; 1250: 70.4 vs 78.0) for about −1
  fresh/s. The owner's feel decides; both variants are ready as cells.
- New hands-on cells: `hq-haar1000-fabrm-metro`, `hq-haar1250-fabrm-metro` and `-q2` versions.
- Unworn procedure: the headset had slept; waking it showed the Guardian boundary dialog, which blocks
  the client. The sweep script now uses the documented recovery (docs/OVERNIGHT.md): `guardian_pause=1`
  for the stationary run plus a bounded proximity override and the wake key, restored afterwards. The first
  restore of `guardian_pause` failed silently (PowerShell stripped the `""`), and it was fixed by hand
  within minutes and verified (`[debug.oculus.guardian_pause]: []`). The script now sets it from Python
  with a readback check.

## Candidates for the owner's worn check (2026-10-07, 160 MHz)
Installed pair: **q160 candidate** `codex/q160-candidate` 7f85e87 (CI 37589333446; APK
20.13.0-ljk1291.2+7f85e87fd554, same cert) = output-queue f33c0cc + fast ABR + fast CDF 5/3, both opt-in.
Files out/q160-candidate-37589333446; server ws/server-q160-candidate-37589333446. Rollback APK:
out/output-queue-37527308692. All cells: PyroWave Haar, FOV crop 2624x2752/eye, 90 Hz, queue depth 3, TCP.

### C5 — Haar 1000 + fast ABR (`hq-haar1000-fabr-metro`)  ← try first
- Settings: C3 at 1000 Mbps plus `video.pyrowave.fast_abr.enabled=true` (floor 0.35, ×0.6, +0.05/frame,
  1-frame backlog threshold, send buffer 1 MiB) and `extra.logging.log_to_disk=true` (per-second
  `[Q3PW_FAST_ABR]` stats in the stage's session_log.txt).
- Evidence (unworn, sweep `q160cand`): 89.8 / 89.9 fresh/s at 1009 Mbps, net p99 13.6–15.4 ms, multiplier 1.0
  except one transient (min 0.36, 14 frames shrunk, 0 dropped). Visual: Haar 1000 = severity 1/1/1 (Astra),
  first rate without square patches. Over-capacity proxy (2000 Mbps ceiling on a ~1.6 Gbps link): fast ABR
  86.1 / 86.3 fresh/s at ~1.61 Gbps, net p50/p99 ~20/36 ms, 0 server drops, vs cap 70.2 / 70.0 at 41/53 ms.
- Look at: head turns and strafing in Metro (stutter, lag, smear), fence detail; compare with C6 and C3.

### C6 — Haar 1250 + fast ABR (`hq-haar1250-fabr-metro`)
- As C5 at 1250 Mbps; send buffer 2.5 MB (1.5 frames). Unworn 89.3 / 89.8 fresh/s, net p99 17–18 ms.
  Visual: severity 1/1/1, "nothing objectionable" (quality saturates here; 1500 is no better).
- Less Wi-Fi headroom than C5 (live capacity ~1.6 Gbps unworn): fast ABR has to absorb more dips.

### C7 — Haar 1000 + settings-only cap (`hq-haar1000-cap-metro`, runs on either pair)
- 1 MiB send buffer + `avoid_video_glitching=false`, no new code. Unworn 89.9 / 90.0 fresh/s. Under overload
  it keeps latency bounded by dropping frames (stutter rather than lag). Control for C5.
- Default buffering (`hq-haar1000-metro`) is the "before" feel: unbounded lag on dips.

### Candidate-pair sweep `q160cand` (10:27–10:43, unworn, 2 interleaved rounds)
| Cell | Fresh/s | Mbps p50 | Network p50/p95/p99 ms | GPU decode | Notes |
|---|---|---|---|---|---|
| hq-haar1000 (fast ABR off) | 90.1, 88.5 | 1009 | 9.7–12.5 / 11.9–21.0 / 13.4–26.3 | 6.5–6.6 | new pair = old pair |
| hq-haar1000-fabr | 89.8, 89.9 | 1008 | 9.6–10.0 / 11.8 / 13.6–15.4 | 6.6–7.4 | multiplier 1.0 |
| hq-haar1250-fabr | 89.3, 89.8 | 1260 | 12.2 / 14.3 / 17.2–18.3 | 7.5 | |
| hq-haar2000-cap | 70.2, 70.0 | 1845 | 41.5 / 49.2 / 53 | 8.6 | decode-to-fence 11.2 ms at 2.8 MB frames |
| **hq-haar2000-fabr** | **86.1, 86.3** | **~1615** | **20 / 31 / 36** | 6.8 | multiplier mean 0.70–0.78, min 0.35 every second, 0 drops, 54–62 client skips |
| hq-cdf53-750-f53 | 74.1 | 757 | 7.1 / 8.9 / 9.8 | **10.9** | fast53 live (apron kernel: 62.2 / 13.0 ms) |

- Fast ABR tuning is open: at the capacity edge the AIMD saw-tooths (floor every second), and bunched
  arrivals make the client skip ~4 frames/s. Next: gentler decrease (~×0.85), slower recovery (~0.02), a
  backlog target band, and a send buffer that scales with frame size.

## Visual ladder at 160 MHz (lossless dumps, 2026-10-07 10:04–10:22, swaying chart, unworn)
Dumps by the installed f33c0cc pair; 8–10 exact post-fade pairs per cell (pruned to pairs; 36 GB free after).
Sheets: results/local/session-25/compare-160/ (ws/compare_sheet.py). Mean / max |luma error|:

| Cell | gratings | lines-text | gratings-right |
|---|---|---|---|
| Haar 500 | 1.25 / 70 | 1.26 / 69 | 1.12 / 66 |
| Haar 750 | 0.81 / 31 | 0.59 / 31 | 0.75 / 60 |
| **Haar 1000** | 0.53 / 12 | 0.45 / 18 | 0.45 / 14 |
| **Haar 1250** | **0.35 / 8** | **0.33 / 11** | **0.32 / 8** |
| Haar 1500 | 0.37 / 12 | 0.34 / 14 | 0.32 / 10 |
| CDF 5/3 750 | 0.62 / 61 | 0.69 / 45 | 0.54 / 27 |
| H.264 P4 (~270 Mbps actual) | 1.20 / 21 | 0.43 / 22 | 1.19 / 21 |

- Planner's read: the 4–8 px square patches are gone from Haar 1000 on (only thin outlines along strokes
  remain in the x16 difference); Haar 1250 is close to transparent. **Quality saturates at ~1250**: 1500 is
  no better (the remaining ~0.33 is likely decoder FP16 storage precision and sub-pixel sway, not
  compression), so there is no reason to push the link past ~1250. H.264 keeps text clean but shifts whole
  grating stripes brighter/darker (the strongest structured error on gratings of all rows).
- CDF 5/3 at 750 ≈ Haar 750 on this synthetic chart (Haar's penalty is small on hard-edged UI/text, +10 %
  bytes offline, but +103 % on natural textures). The chart cannot show 5/3's advantage; Metro can.
- **Astra's independent review** (task-muxuciqa-d2vbek, read-only, gpt-6-astra; still-image estimates, MIDDLE vs
  LEFT, native scale checked): severity gratings / lines-text / gratings-right — Haar 500 3/3/3, Haar 750 2/2/2,
  **Haar 1000 1/1/1** ("the first convincing cleanup of the square patches and faint-stroke loss"; borderline
  1–2 under deliberate scrutiny), **Haar 1250 1/1/1** ("no persuasive square patches or disappearing
  strokes"), Haar 1500 1/1/1 (same tier as 1250), CDF 5/3 750 2/2/2 (less rectangular damage but softening
  and thickened faint strokes), H.264 P4 2/1/2 (clean text; systematic stripe brightness/width changes).
  Ranking, thin lines/text: **Haar 1250 ≈ 1500 ≳ 1000 ≈ H.264 > Haar 750 ≳ CDF 750 > Haar 500**; dense
  gratings: **Haar 1250 ≈ 1500 ≳ 1000 ≳ CDF 750 > Haar 750 ≳ H.264 ≳ Haar 500**. Patches stop being
  visible at ~1000; 1250 is the confident "nothing objectionable" point. Motion shimmer is not judged from stills.
- **Conclusion for problem 1 (chart): Haar at 1000–1250 Mbps over 160 MHz is the first configuration that
  is visibly cleaner than the VD-like H.264 reference** (better gratings, text tied or better). Metro
  (natural textures, where Haar is weakest) is the owner's check.

## Fast CDF 5/3 inverse: device check (2026-10-07 ~10:28, candidate pair 7f85e87, standalone)
`pyrowave_android --compare-fast53` on a real 5248x2752 chart frame at the 750 Mbps budget, precision 1:
- **Parity PASS**: max 1 code value in Y/Cb/Cr (mean 0.0053 / 0.0005 / 0.0007): the kernel is exact.
- **Timing**: GPU decode apron 5/3 12.59 ms → **fast53 10.13 ms** (−20 %) vs Haar 6.13 ms: 1.65x Haar
  (target 1.3x) → expect ~80 fresh/s live, not 90. The pair-local kernel is fetch-bound (3.06 fetches/pixel
  vs Haar's 1). Next options: larger blocks per invocation (4x4 pairs ≈ 1.9 fetches/pixel), textureGather,
  or a hybrid (5/3 only on the coarse levels that produce Haar's 4–8 px squares, Haar on level 0).

## Why worn motion turns into 100–300 ms lag (source reading, 2026-10-07 ~09:10)
PyroWave over TCP is sent through ALVR's stream socket: encoder → `send_video_nal` (2-frame
`sync_channel`, `max_queued_server_video_frames = 2`, `try_send`) → video send thread → socket.
1. `connection.server_send_buffer_bytes` defaults to **Maximum = `set_send_buffer_size(u32::MAX)`**
   (`alvr/sockets/src/lib.rs`). Windows honours huge SO_SNDBUF values, so when a head turn makes the Wi-Fi
   capacity dip below the stream rate, the backlog piles up in the PC's TCP socket with no bound. The 2-frame
   channel never fills, so nothing drops and the encoder keeps producing full-size frames. That matches
   this morning's worn 750 Mbps cell (network p50 321 ms ≈ 30 MB queued) and the 46/89 ms p95/p99 at 500.
2. If the channel does fill, ALVR marks the stream corrupted and, with `avoid_video_glitching = true`
   (default), drops every frame until one is flagged IDR. PyroWave flags IDR only on request
   (`VideoEncoderPyroWave.cpp`: `VideoSend(..., insertIDR, ...)`) and `minimum_idr_interval_ms` is 100,
   so one overflow freezes the picture for up to ~9 frames, though every PyroWave frame is intra-only.
3. ALVR's adaptive bitrate reacts ~1 Hz; a head turn is over before it acts.
Settings-only mitigation (cells `*-cap`): `server_send_buffer_bytes = Custom(1 MiB)` (bounds the queue to
~8–11 ms at 750–1000 Mbps; still above the ~0.5 MB bandwidth-delay product) and `avoid_video_glitching =
false` (an overflow drops only that frame). Code follow-up (planned, Astra): shrink the next PyroWave frames
when the send queue backs up, so a dip costs a little sharpness instead of frames.

## Network capacity at 160 MHz (2026-10-07 08:55, unworn, `tools/quest3/network.py --transport tcp`)
Frame-paced TCP probe (one capped frame per 90 Hz slot, receiver ACK after the full frame; no codec).
Link 2401/2401 Mbps, 5180 MHz, RSSI −8 before and after every rate.

| Target Mbps | ACK payload Mbps | ACK p50 / p99 / p99.9 ms | Late % (ACK > 1 period) | Skipped slots |
|---:|---:|---:|---:|---:|
| 500 | 499.9 | 5.9 / 12.9 / 17.9 | 2.1 | 0 |
| 750 | 749.9 | 8.0 / 17.6 / 24.8 | 5.1 | 0 |
| 1000 | 994.1 | 10.7 / 28.4 / 49.3 | 51.7 | 5 |
| 1250 | 1144.5 | 23.0 / 34.4 / 42.7 | 100 | 74 |
| 1500 | 1129.1 | 28.4 / 38.4 / 41.8 | 100 | 221 |
| 2000 | 1167.2 | 37.0 / 50.8 / 52.1 | 100 | 373 |

- **The usable TCP ceiling is ~1.15 Gbps** (80 MHz: ~750). 500 and 750 now have wide margins; 1000 is at
  the edge even unworn; 1250+ exceed TCP capacity. The sender kept pace up to 750 (schedule-lag p99 1.1 ms),
  so beyond that the limit is the link/receiver, not the Python sender. UDP may go higher (not probed:
  the native UDP sender isn't built on this PC); the live PWU2 cells test that.

## 160 MHz live ladder (2026-10-07 09:00–, unworn, swaying chart, FOV crop, queue depth 3, installed f33c0cc)
Sweep `ladder160` (ws/hq_profiles.py cells, 20 s captures, interleaved; table by ws/sweep_table.py).
Link 2401/2401 Mbps, RSSI −7/−8 before and after every cell. Round 1:

| Cell | Fresh/s | Mbps p50 | Network p50/p95/p99 ms | Frame gap p95/p99/max ms | GPU decode p50 | Decode-to-fence p50 | Latency p50 |
|---|---|---|---|---|---|---|---|
| hq-haar500 (TCP) | 90.1 | 504 | 5.5 / 7.4 / 8.2 | 14.8 / 18.5 / 22.2 | 7.5 | 9.3 | 84 |
| hq-haar750 (TCP) | 89.3 | 756 | 7.6 / 9.6 / 10.8 | 14.9 / 18.5 / 25.9 | 5.9 | 8.6 | 69 |
| **hq-haar1000 (TCP)** | **89.8** | **1007** | 9.5 / 12.4 / 14.9 | 18.5 / 22.2 / 51.9 | 6.5 | 8.9 | 81 |
| hq-haar750-udp (PWU2) | 60.3 | 754 | n/a (UDP estimate 0) | 22.4 / 25.9 / 36.8 | 9.6 | 11.4 | 82 |
| hq-haar1000-udp (PWU2) | 53.0 | 1009 | n/a | 26.0 / 33.3 / 40.7 | 9.7 | 11.8 | 88 |
| hq-haar1250-udp (PWU2) | (counters missing) | 1262 | n/a | 29.7 / 40.9 / **3192** | 9.8 | 12.1 | 84 |
| hq-cdf53-750 (5/3, apron kernel) | 62.2 | 756 | 7.2 / 9.3 / 10.3 | 26.0 / 26.1 / 37.1 | **13.0** | 15.5 | 78 |
| hq-haar444-750 (4:4:4) | 63.8 | 756 | 7.4 / 9.1 / 10.0 | 25.9 / 29.6 / 37.0 | **12.1** | 15.1 | 77 |

Round 2 (rotated order) repeated it: Haar 500 89.9 (net p99 7.9), Haar 750 88.5 (10.4), **Haar 1000 88.3
(net p50/p95/p99 10.2 / 13.1 / 36.4: one tail burst)**, PWU2 60.0 / 53.2 / 47.5, 5/3 61.9 (decode 13.0), 4:4:4 63.5
(12.2). Restore: everything OK except VD StreamerSettings.json, rewritten by VD's own service at 08:59:48, 27 s
after the snapshot as SteamVR started (same pattern as 08:10 this morning). The new read-only snapshot copy
shows what VD changed: its DPAPI-encrypted `Accounts.OculusQuest` token was re-encrypted (new random salt, so
new bytes) and `ServerRotation: 5` was removed. No streaming setting changed; the harness never writes VD files.

- **Haar 1000 over TCP holds ~89–90 fresh/s unworn** at 1007 Mbps (network p99 15–36 ms); decode does not grow
  with bitrate (5.9–7.5 ms at 500–1000). 160 MHz makes 1000 Mbps feasible, but with little margin (TCP
  ceiling ~1.15 Gbps), so worn motion will need the latency cap below.
- **Latency-cap A/B (sweep `cap160`, 09:23–09:40, 2 interleaved rounds, unworn)** — fresh/s, network p99 ms:

  | Rate | Default send buffer | Cap (1 MiB + no wait-for-IDR) |
  |---|---|---|
  | 750 | 89.9 / 10.4, 90.0 / 10.3 | 90.0 / 10.7, 90.0 / 10.2 |
  | 1000 | 89.8 / 13.4, 90.0 / 14.4 | 89.9 / 15.5, 90.0 / 15.0 |
  | 1250 | 89.8 / 16.0, 89.7 / 17.9 | 89.8 / 24.1, 89.8 / 20.0 |

  **The live TCP stream carries 1.26 Gbps at 90 fresh/s** (network p50 ~12 ms, decode 6.7–7.5 ms): the
  Python probe's ~1.15 Gbps ceiling was a probe artifact. The cap costs nothing measurable unworn (no
  drops); its benefit only shows when capacity dips (cross-traffic test next, then worn).
- **Upper limit screen (sweep `hi160`, 1 round):**

  | Cell | Fresh/s | Mbps | Network p50/p95/p99 ms | GPU decode |
  |---|---|---|---|---|
  | hq-haar1500 | 89.2 | 1512 | 14.0 / 25.7 / 36.0 | 6.7 |
  | hq-haar1500-cap | 85.9 | 1513 | 32.8 / 39.8 / 42.8 | 7.0 |
  | hq-haar2000 | 75.9 | (stats missing) | – | 7.7 |
  | hq-haar2000-cap | 70.2 | 1849 | 41.7 / 49.2 / 54.1 | 8.5 |

  Live TCP capacity at 160 MHz is between 1.5 and ~1.85 Gbps; 1500 holds ~89 fresh/s unworn with growing
  tails. Above capacity the cap keeps latency bounded (~50 ms p99 at 2000) and drops frames instead.
  **A 1 MiB cap is too small above ~1250 Mbps**: a 2.1 MB frame doesn't fit, TCP becomes window-limited
  (1500-cap 85.9/s, 33 ms). The send buffer should scale with the frame (≳1.5 frames); 1 MiB is fine
  ≤1000 Mbps (measured).
- **Cross-traffic is not a usable motion proxy here (sweep `cross160`, 09:52–).** 800 Mbps TCP bursts to the
  headset (400 ms on / 1600 ms off, `tools/quest3/crosstraffic.py`) left Haar 1000 at 88.8, 89.9 fresh/s
  (default; net p99 16, 16 ms) and 89.2, 89.0 (cap; 21, 22 ms), and Haar 750 at 89.7–89.8 either way
  (p99 13–15 ms), while the cross flow got only ~375 Mbps (vs a 1000 stream) or ~500 (vs 750) with ACK p50
  35–48 ms / p99 57–98 ms. Restore exit 0 (VD rewrite rule above).
  The video wins airtime, consistent with ALVR's DSCP EF marking being mapped to a higher WMM class by this
  router (useful protection against other devices on the network). A worn head turn instead lowers the PHY
  rate for every class, so the over-capacity cells (rate above link capacity) are the unattended proxy.
- **PWU2 UDP is rejected** at every rate: 53–60 fresh/s. Not the radio: the receiver assembled ~4000 complete
  frames per run and dropped 1–5, but the UDP client path decodes serially (GPU decode 9.6–9.8 ms, submit→fence
  11.3–12.3 ms vs 5.9/8.6 on TCP) and has no output queue (docs/OUTPUT-QUEUE.md: "TCP PyroWave only"), so it
  skipped a third of the complete frames. Any UDP transport must reuse the TCP path's decode worker and FIFO.
- **4:4:4 chroma doubles decode (12.1 ms)**: not affordable at 90 Hz. Rejected.
- **CDF 5/3 on the current apron kernel: 13.0 ms decode, 62 fresh/s** (Haar 5.9 ms). The fast pair-local 5/3
  kernel (Astra, `codex/fast53`) must cut the inverse transform from ~8.5 ms to ~3.5 ms to reach 90 fresh/s.

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

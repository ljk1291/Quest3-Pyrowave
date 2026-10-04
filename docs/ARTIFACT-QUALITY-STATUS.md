# Artifact-quality status and queue

The shared channel between the owner, the planning agent (Claude) and the implementing
agent (Codex). Codex reads it at every checkpoint and appends to **Log**. The owner or
Claude may reorder **Queue** or add **Notes for Codex** between checkpoints. Keep
entries short and link to evidence.

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
The finite r5 controller is running Q3b with three preparation workers and fresh
r3 Pyro attempt paths. Its three Light / 9/7 / 1000 Mbps softness cells (0, 0.5,
1) and Light / 5/3 / 1000 Mbps / softness 0.5 are complete with clean lease
closure; six Q3b cells remain. Medium / 5/3 / 1000 Mbps / softness 0.5 is active.
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

<!-- Codex appends entries here: date, checkpoint, verified (links), remaining, blocked? -->

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

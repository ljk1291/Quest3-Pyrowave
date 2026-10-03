# Artifact-quality status and queue

The shared channel between the owner, the planning agent (Claude) and the implementing
agent (Codex). Codex reads it at every checkpoint and appends to **Log**. The owner or
Claude may reorder **Queue** or add **Notes for Codex** between checkpoints. Keep
entries short and link to evidence.

## Current state (2026-10-02)

- **Installed candidate:** signed `d1c3b3d4edb3` pair; colour remap fixed.
- **Profile:** 3072×3232/eye, 90 Hz, Haar, 4:2:0, TCP Wi-Fi, 500 Mbps, recommended-AHB
  allocation.
- **Rate:** about 82 fresh submissions/s (f2 pair). This is not a 90 Hz pass.
- **Quality:** fails. The owner sees mura-like texture and line aliasing. The diagnosis is
  in [ARTIFACT-QUALITY-PLAN.md](ARTIFACT-QUALITY-PLAN.md).
- **Open fault:** a terminal PC encoder fence timeout at Metro startup in session 07.
  The cause is unknown.

## Queue

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

## Log

<!-- Codex appends entries here: date, checkpoint, verified (links), remaining, blocked? -->

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

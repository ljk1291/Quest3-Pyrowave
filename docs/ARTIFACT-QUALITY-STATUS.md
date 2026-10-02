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

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

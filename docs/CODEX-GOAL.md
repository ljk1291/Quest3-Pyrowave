# Codex goal: reduce PyroWave compression artifacts

## Start it (owner, once)

In Codex CLI 0.128 or later, or the Codex desktop app, open the repository root:

```text
codex features enable goals
/goal Follow docs/CODEX-GOAL.md until its stop condition or a recorded blocker.
```

Codex can only work while you're away if it can run commands without approval prompts.
Choose an approval/sandbox mode for this repository that allows that, including
access to ADB, network for GitHub, and processes under `results/local/`. Check
`codex --help` for your version's flags. Keep the PC on and Codex open; the Quest stays
on USB power. `/goal pause`, `/goal resume` and `/goal clear` control the run.

## Objective

Reduce mura-like texture, stair-stepped edges and line shimmer on Quest 3 at 90 Hz over
Wi-Fi by executing [ARTIFACT-QUALITY-PLAN.md](ARTIFACT-QUALITY-PLAN.md), in the order
given by the queue in [ARTIFACT-QUALITY-STATUS.md](ARTIFACT-QUALITY-STATUS.md).

## Read first

[AGENTS.md](../AGENTS.md),
[ARTIFACT-QUALITY-PLAN.md](ARTIFACT-QUALITY-PLAN.md),
[ARTIFACT-QUALITY-STATUS.md](ARTIFACT-QUALITY-STATUS.md),
[DECODER-OPTIMIZATION-PLAN.md](DECODER-OPTIMIZATION-PLAN.md),
[STABLE-BASELINE.md](STABLE-BASELINE.md), [BUILD.md](BUILD.md) and
[patches/README.md](../patches/README.md) (patch regeneration traps).

## Do not change

- Stable defaults, dependency pins, signing, fork identity or protocol version, except
  where a work order explicitly requires a new protocol and pair.
- Virtual Desktop, network, router, Windows power settings, or
  `main` / the stable branch.
- Existing evidence text in results and docs. Add new sections instead.

## Working loop (each checkpoint)

1. Re-read the status file. Take the first queue item that is not blocked.
2. Work on its own branch `codex/<work-order>`, stacked on the integration branch
   `codex/artifact-quality`, created from `codex/stable-alvr-baseline`. Open a PR into
   the integration branch. Every runtime change must be opt-in, default-off, logged
   when active, and covered by CPU tests.
3. Push, then wait for GitHub Actions. Fix failures before moving on. Merge into the
   integration branch only when CI is green and no default changed.
4. If the item needs hardware:
   - Run it with `ws/session25.py` under the lean rules in AGENTS.md, then restore.
   - When it needs Metro gameplay: queue an owner task and continue with other items.
5. Append a progress entry to the status file:
   - the checkpoint;
   - what was verified, with links to CI runs and sanitized results;
   - what remains;
   - whether you are blocked.

## Validation that counts

- CPU tests and the full Actions workflow are green on the integration branch.
- Hardware cells: off/on/off order where an A/B matters, the selected-output counter,
  and restored settings with Virtual Desktop untouched.
- Quality claims use the WO-1 frame bank: exact source/decoded identity, fixed crops,
  PSNR-Y, SSIM, VMAF, and PSNR-HVS-M-H at the measured ~24 px/deg viewing factor.

## Stop condition

Stop when **all** of these hold:

1. A frame-bank report on Metro frames names one profile (encode size × wavelet ×
   bitrate × optional filters) that beats the current Godlike / Haar / 500 Mbps
   baseline on VMAF and PSNR-HVS-M-H for every fixed crop.
2. A chart screen of that profile shows:
   - a fresh-submission rate at or above the baseline's;
   - no decoder/encoder faults;
   - settings restored with matching VD hashes.
3. `docs/ARTIFACT-QUALITY-STATUS.md` names that profile with exact settings and
   rollback steps.

Also stop, writing the blocker to the status file, when no unblocked queue item remains
and the remaining items all need the owner.

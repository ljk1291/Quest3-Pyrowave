# Development and validation

This is ljk1291's Quest 3 Wi-Fi/Godlike/90 Hz baseline fork. Preserve upstream credits.

- Prefer source changes, lightweight CPU checks, and GitHub Actions builds.
- Do not use ADB, install APKs, launch VR applications, run GPU or live streaming benchmarks,
  restart SteamVR, register drivers, or change headset, system, network, or SteamVR settings
  except (a) in a supervised hardware test session authorized by the owner, or (b) inside an
  armed unattended window that satisfies every rule in [docs/UNATTENDED.md](docs/UNATTENDED.md).
  The approved baseline plan authorizes preparing and conducting supervised sessions; confirm
  that the owner is ready before interrupting an active VR session. Outside an armed window,
  do not run unattended trials.
- Do not run heavy local builds while the owner is playing. Build on GitHub Actions.
- Preserve Virtual Desktop's registration, service and settings; snapshot actual state
  before test setup and restore it afterward. Do not assume upstream machine state.
- Use the current user's Git identity. Do not impersonate the upstream maintainer.
- The fork is ljk1291/Quest3-Pyrowave; upstream is JMS1717/Quest3-Pyrowave.
- Never commit private captures, session configurations, device identifiers, or signing keys.
- State separately whether a rate is accepted by the runtime, meets a standalone decode
  budget, and is sustained in live VR. Unverified presets must say they are candidates or experiments.

Keep reconstructed dependencies and private captures in ignored workspace directories.
Do not overwrite an active installation. Hardware acceptance requires actual device and
gameplay evidence; successful builds and CPU tests do not establish 90 Hz performance.

## Unattended windows (owner authorization, 2026-10-02)

The owner authorized bounded unattended hardware windows on this PC and this Quest 3,
under [docs/UNATTENDED.md](docs/UNATTENDED.md). Historical upstream authorizations do
not apply. The hard limits, restated so they are always read:

- A window exists only while the owner's arm file `results/local/unattended/arm.json`
  is valid for the current time. Agents never create, extend or edit it.
- No hardware action until every precondition passes and is recorded: pinned headset,
  battery and thermal state, idle owner, idle competing GPU workloads, a complete
  settings snapshot, and VD state hashes.
- Start the independent deadline restorer and the thermal/battery monitor **before**
  the first device or settings change. Restoration must not depend on the agent being alive.
- Never reboot the PC or headset, change network, router or Windows power settings,
  modify or unregister Virtual Desktop, launch games or store pages, tap unknown dialogs,
  or disable thermal protections. Metro gameplay stays an owner-supervised task.
- Stop the hardware part of the window after the second terminal decoder/encoder
  fault, an unrecoverable disconnect, settings drift, or a thermal/battery stop that
  does not clear. Restore, then continue source and offline work.
- Unattended results are diagnostic evidence. Promoting a default still needs the
  owner's in-headset sign-off.

Long-running agent work follows [docs/CODEX-GOAL.md](docs/CODEX-GOAL.md). Read
[docs/ARTIFACT-QUALITY-STATUS.md](docs/ARTIFACT-QUALITY-STATUS.md) at every checkpoint:
the owner or a planning agent may reorder its queue between checkpoints.

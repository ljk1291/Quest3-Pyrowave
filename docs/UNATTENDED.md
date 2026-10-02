# Bounded unattended hardware windows

The owner granted a standing authorization on **2026-10-02** for agents to run hardware
tests on this owner's PC and Quest 3 without the owner present, **only** under the
rules below. It does not apply to other machines or users. The owner revokes it by
deleting `results/local/unattended/arm.json` or by editing [AGENTS.md](../AGENTS.md).
Upstream's [OVERNIGHT.md](OVERNIGHT.md) is the design reference for these rules. Its
authorization is historical and does not apply here.

Until the supervisor from **WO-0** in [ARTIFACT-QUALITY-PLAN.md](ARTIFACT-QUALITY-PLAN.md)
exists and its CPU tests pass, agents must not open a window. They do source and
offline work only.

## 1. Arming (owner only)

A window exists only while a valid arm file is in force. Agents never create, extend or
edit it; WO-0 provides `python -m tools.quest3.unattended arm …` for the owner to run.
Until then the owner may write it by hand. The path is ignored by git
(`results/local/` is in `.gitignore`).

```json
{
  "schema": 1,
  "mode": "nightly",
  "start_local": "01:00",
  "end_local": "07:00",
  "timezone": "Europe/Berlin",
  "expires_local": "2026-10-31T23:59",
  "headset_serial": "<ADB serial, private>",
  "max_window_hours": 6,
  "allow": ["chart_cells", "decoder_timing", "frame_bank_pc", "install_matching_pair"]
}
```

- `mode` is `nightly` (recurring between the two local times until `expires_local`) or
  `once` (with `not_before_local` / `not_after_local`).
- A window never exceeds 6 hours. A new window does not start with less than
  45 minutes remaining.
- `allow` narrows what the window may do. Anything not listed is forbidden for that window.

## 2. Preconditions (checked and recorded before any change)

Any failure means no hardware actions in this window. Record the reason and continue
with source or offline work.

1. The arm file is valid now, with at least 45 minutes left.
2. Exactly one ADB device. Its model is Quest 3 and its serial equals `headset_serial`.
   Every ADB command uses `-s <serial>`.
3. Headset battery is at least 50 % and charging over USB; Android thermal status is
   none or light; battery temperature is below 40 °C.
4. The owner is not using the system:
   - Windows input idle for at least 30 minutes.
   - No VR session the owner started: no Virtual Desktop or ALVR stream connected, and
     no game or SteamVR scene app other than this repo's test scenes.
5. No competing GPU workload. Sample the ComfyUI queue and other GPU-compute processes,
   following the rule in [STABLE-BASELINE.md](STABLE-BASELINE.md#capture-and-acceptance).
   It must be idle at the start, and is re-sampled throughout every timing window.
6. A complete snapshot is written under `results/local/unattended/<window-id>/before/`
   **before** any change:
   - `python -m tools.quest3.preflight` output, the ALVR session settings and SteamVR settings.
   - The active OpenXR runtime path and the registered SteamVR drivers.
   - Virtual Desktop's driver registration, manifest and settings hashes.
   - Headset `debug.q3pw.*`, `debug.oculus.*` and Guardian/proximity-related properties.

## 3. Guards (started before the first change; independent of the agent)

- **Deadline restorer.** A detached process scheduled for the window's end, or for an
  earlier `stop` marker file. It:
  - stops this fork's client before restoring properties, because XR teardown can
    overwrite earlier readbacks;
  - restores headset properties with readback, physical proximity (`tools.quest3.awake
    --restore`), Guardian, refresh rate, the ALVR and SteamVR settings, and the previous
    OpenXR runtime;
  - verifies the Virtual Desktop hashes against the snapshot;
  - writes `restoration.json`.

  It must run correctly even if the agent crashes, and cleanup steps from the agent must
  not overwrite its work after the deadline.
- **Thermal/battery monitor**, every 30 seconds. Pause device work when Android thermal
  status reaches severe or higher, battery falls below 30 %, or battery temperature
  reaches 46 °C. Resume only after at least 15 minutes and at most 40 °C. A third pause
  ends hardware work for the window. Battery temperature is not GPU die temperature.
- **Keep-awake.** Use the Windows execution-state API only for the window's duration.
  Never change the power plan.
- **Workload monitor.** Any competing GPU workload during a timing window invalidates
  that cell. Do not kill the owner's processes.

## 4. Allowed actions (subject to `allow`)

- ADB to the pinned headset only.
- Install or replace **only** `io.github.ljk1291.quest3pyrowave`, and only from a
  matching APK/server pair:
  - built by a successful GitHub Actions run of a `codex/` branch or the stable branch.
    Use a manual `workflow_dispatch` run, so the pair is stable-signed as described in
    [BUILD.md](BUILD.md); push/PR runs on branches use a temporary key;
  - passing `python tools/ci/build_metadata.py verify-pair`;
  - signed with the stable certificate fingerprint recorded in `fork.json`.

  On a signature mismatch, stop and queue an owner task. Never uninstall to resolve it.
- Start and stop this fork's client.
- Set temporary properties, each recorded and restored by the restorer:
  - `debug.q3pw.*` and `debug.oculus.refreshRate`;
  - proximity via `tools.quest3.awake`;
  - `debug.oculus.guardian_pause=1`, for stationary tests only.
- Start and stop SteamVR. Switch the OpenXR runtime to SteamVR and back with the
  owning application's selector. Register only this fork's driver as described in
  [BUILD.md](BUILD.md); never choose "unregister other drivers".
- Run this repository's test scenes (`tools.quest3.stereo_scene`,
  `tools.xrbench.scene_app`) and capture tools (`tools.quest3.bench`, ADB screenshots,
  logcat windows).
- Run PC-side offline encode/decode and scoring (the frame bank) while the owner is idle.

## 5. Forbidden in every window

- Rebooting or factory-resetting the PC or headset.
- Changing network, router, Wi-Fi or Windows power settings.
- Modifying, stopping or unregistering Virtual Desktop.
- Launching games (including Metro), the store, purchases or accounts.
- Tapping unknown dialogs or disabling thermal protections.
- Editing the arm file or extending a window.
- Pushing to `main` or the stable branch, force-pushing, or merging to the stable
  branch without the owner.
- Committing anything under `results/local/`, device identifiers or screenshots.

## 6. Cell protocol

- **One change at a time:** baseline/candidate/baseline, matched build, the same scene,
  thermal state and recorded GPU clock samples.
- **Timing:** settle for 3 s, then screen for at least 15 s; use the decoder plan's
  50-second windows for rate claims.
- **Required evidence:** the protocol `.2` selected-output counter and settings readback
  at start and end.
- **Stop the cell** on a decoder/encoder fault, disconnect, visible corruption from
  automated pixel checks, settings drift, missing telemetry or a competing workload.
- **Encoder fence timeout:** capture the server logs and a workload sample *before* any
  restart. Session 07's timeout is still unexplained.

## 7. Recovery

Follow the restart rules in [BUILD.md](BUILD.md):

- A terminal decoder fault means restarting the client.
- A terminal encoder fault means fully restarting SteamVR.
- Allow at most two recoveries per window. After the second, end hardware work: restore,
  verify, and continue offline work.
- A resumed session can keep a stale 72 Hz property. Stop the app, let the old XR session
  close, then request the refresh rate before relaunch. Verify the OpenXR frequency and
  frame period, not only the property.

## 8. Reporting

- Private raw evidence goes to `results/local/unattended/<window-id>/`.
- Commit a sanitized summary as `results/unattended-<date>.json` with:
  - preconditions, the guard start time and every cell;
  - stops, recoveries and the restoration result;
  - VD hash verification and build hashes.
- Append a dated entry to [ARTIFACT-QUALITY-STATUS.md](ARTIFACT-QUALITY-STATUS.md). List
  anything only the owner can do under **Owner tasks**.

Unattended evidence cannot establish gameplay quality, comfort, optical FPS or
motion-to-photon latency. Those remain owner-supervised gates.

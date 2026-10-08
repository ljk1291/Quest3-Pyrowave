# Development and validation

This is ljk1291's Quest 3 Wi-Fi/Godlike/90 Hz baseline fork. Preserve upstream credits.
The fork is ljk1291/Quest3-Pyrowave; upstream is JMS1717/Quest3-Pyrowave.

## Hardware testing (owner decision, 2026-10-06)

Agents may run hardware tests on this PC and this Quest 3 without the owner present:
ADB, client launches, SteamVR/ALVR starts, settings changes and live captures. Keep only
these checks, which protect something real:

1. Snapshot everything a run changes (SteamVR files, driver registration, the ALVR
   session, Quest debug properties) and restore it afterwards; restore must be idempotent.
2. Leave Virtual Desktop untouched (registration, service, settings); verify by comparison.
3. Stop and restore on device health: Android thermal status >= 3, battery temperature
   >= 55 C (owner decision 2026-10-08; was 60 C, before that 50 C), or battery < 10 %.
   Start a run only at >= 40 % and < 50 C. Charging is not required. Prefer cooling pauses
   between cells (hq-sweep: at >= 48 C stop the stream and wait for <= 45 C).
4. Don't start a run while the owner is using the PC for VR or gaming.
5. Report feature markers, but never block on them. Record telemetry and any owner
   judgement verbatim.

The harness is `ws/session25.py`. Don't add blocking gates (process-identity proofs,
lock gating, strict log requirements) without a concrete hazard and the owner's say-so.

## Code and reporting

- New runtime behaviour is opt-in/default-off with a log marker; build on GitHub Actions.
- Use the current user's Git identity. Never commit private captures, session
  configurations, device identifiers or signing keys.
- Report rates honestly: say whether a rate is accepted by the runtime, meets a decode
  budget, or is sustained in live VR. Builds and CPU tests don't prove 90 Hz.

Brief new agent threads with `ws/codex-context.md`, not the full status doc.

# Development and validation

This is ljk1291's Quest 3 Wi-Fi/Godlike/90 Hz baseline fork. Preserve upstream credits.

- Prefer source changes, lightweight CPU checks, and GitHub Actions builds.
- Do not use ADB, install APKs, launch VR applications, run GPU or live streaming benchmarks,
  restart SteamVR, register drivers, or change headset, system, network, or SteamVR settings
  except in a supervised hardware test session authorized by the owner. The approved
  baseline plan authorizes preparing and conducting those sessions; confirm that the
  owner is ready before interrupting an active VR session. Do not run unattended trials.
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

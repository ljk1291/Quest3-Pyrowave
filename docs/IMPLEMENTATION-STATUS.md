# Baseline implementation status

Target: Wi-Fi 6 / 5 GHz / 80 MHz, actual VD Godlike dimensions, 90 Hz, Metro Awakening. Reviewed upstream: `f6eae38380ecf0cb706aaa9aabc0fd66ec29cd6a`. Branch: `codex/stable-alvr-baseline`.

## Implemented locally

- Fork identity/package overlay, authoritative source lock and commit-stamped paired builds.
- Required codec libraries, shader hashes, artifact checksums and certificate fingerprint packaging; missing stable signing secrets fail the build.
- Bounded Windows GPU waits and terminal resource preservation; Android terminal decoder failures with process restart requirement.
- Explicit plan/control/capture, fail-closed acceptance, read-only preflight and observation/review templates.
- Supervised qualification, endurance, recovery, bottleneck experiments and return-to-VD runbook.

## Evidence and remaining gates

Local Python checks pass. Clean LF source reconstruction applies the ALVR/PyroWave overlays, and the codec shader manifest passes. Native compilation and headset execution remain separate gates. No Godlike/90 Hz result is claimed. The untouched upstream reference must be built separately and retained with its matching artifacts.

The [GitHub fork](https://github.com/ljk1291/Quest3-Pyrowave) exists, with `upstream` retained and the reviewed commit preserved on `codex/upstream-reference`. A persistent private PKCS12 signing key is configured in encrypted Actions secrets; its public fingerprint in `fork.json` gates stable APK packaging. Cloud build outcomes and matching artifacts still need verification. Actual VD dimensions, Quest OS, chart/gameplay/endurance/recovery checks and return-to-VD verification remain to be recorded. A configuration snapshot does not certify rollback.

Do not claim the milestone passed until matching native builds, controlled runs and operator review pass. Historical upstream captures do not satisfy these requirements for this machine.

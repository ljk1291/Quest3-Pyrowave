# Baseline implementation status

Target: Wi-Fi 6 / 5 GHz / 80 MHz, actual VD Godlike dimensions, 90 Hz, Metro Awakening. Reviewed upstream: `f6eae38380ecf0cb706aaa9aabc0fd66ec29cd6a`. Branch: `codex/stable-alvr-baseline`.

## Implemented locally

- Fork identity/package overlay, authoritative source lock and commit-stamped paired builds.
- Required codec libraries, shader hashes, artifact checksums and certificate fingerprint packaging; missing stable signing secrets fail the build.
- Bounded Windows GPU waits and terminal resource preservation; Android terminal decoder failures with process restart requirement.
- Explicit plan/control/capture, fail-closed acceptance, read-only preflight and observation/review templates.
- Supervised qualification, endurance, recovery, bottleneck experiments and return-to-VD runbook.

## Evidence and remaining gates

Local Python checks pass. Clean LF source reconstruction applies the ALVR/PyroWave overlays, and the codec shader manifest passes. Native compilation and headset execution remain separate gates. No Godlike/90 Hz result is claimed. The untouched upstream reference build is retained with its artifacts.

## Build validation — 2026-10-02

- Reference Actions run `37009583485` completed successfully and its retained Android and Windows artifacts provide the untouched reference pair.
- Stable Actions run `37011907723` built and packaged the signed Android client and Windows streamer successfully. The Android APK was installed successfully with version `20.13.0-ljk1291.1+cbf70c27269d`; its certificate fingerprint was `4a3fe0a8d47ee67b01710df6ffdc870e91ebc5b8e7feec7c87534944ca2a44aa`.
- The run's matching-pair job correctly failed. Android and Windows metadata had the same source commit, package, protocol, application/server version, dependency revisions and shader hashes. Its only mismatch was the raw source-lock digest, caused by LF checkout bytes on Linux and CRLF checkout bytes on Windows. The recorded hash proof is in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json). The metadata writer now fingerprints a canonical LF representation, and the next build must pass the pair gate before the stable pair is promoted.
- These artifacts are diagnostic build evidence only. No headset streaming, Metro Awakening, Godlike-resolution, 90 Hz, endurance, recovery or user-acceptance result has been recorded.

The [GitHub fork](https://github.com/ljk1291/Quest3-Pyrowave) exists, with `upstream` retained and the reviewed commit preserved on `codex/upstream-reference`. A persistent private PKCS12 signing key is configured in encrypted Actions secrets; its public fingerprint in `fork.json` gates stable APK packaging. The canonical lock-hash correction must pass a fresh matching-pair run. Actual VD dimensions, Quest OS, chart/gameplay/endurance/recovery checks and return-to-VD verification remain to be recorded. A configuration snapshot does not certify rollback.

Do not claim the milestone passed until matching native builds, controlled runs and operator review pass. Historical upstream captures do not satisfy these requirements for this machine.

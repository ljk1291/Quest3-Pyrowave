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

The supervised 72 Hz chart diagnostic is summarized in [diagnostic-2026-10-02.json](../results/diagnostic-2026-10-02.json). It confirms a clean decoder-counter window, fresh 72 Hz runtime evidence, initial image clarity, world-grid tracking, both controllers, and audio. It is explicitly unqualified: the reported submission-rate metric is 70.8319 FPS with 30 duplicate target timestamps, and it is not Metro/Godlike/90 Hz/endurance/recovery evidence. Background GPU work was not controlled during capture; the owner subsequently identified ComfyUI, and a later check found ComfyUI processes, 100% overall GPU utilization and approximately 14,600 MiB VRAM allocated. This later observation cannot establish activity at every earlier instant. Repeat performance measurements under controlled conditions before drawing codec-performance conclusions.

## Build validation — 2026-10-02

- Reference Actions run `37009583485` completed successfully and its retained Android and Windows artifacts provide the untouched reference pair.
- Stable Actions run `37011907723` built and packaged the signed Android client and Windows streamer successfully. The Android APK was installed successfully with version `20.13.0-ljk1291.1+cbf70c27269d`; its certificate fingerprint was `4a3fe0a8d47ee67b01710df6ffdc870e91ebc5b8e7feec7c87534944ca2a44aa`.
- The run's matching-pair job correctly failed. Android and Windows metadata had the same source commit, package, protocol, application/server version, dependency revisions and shader hashes. Its only mismatch was the raw source-lock digest, caused by LF checkout bytes on Linux and CRLF checkout bytes on Windows. The recorded hash proof is in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json). The metadata writer was corrected to fingerprint a canonical LF representation.
- Stable Actions run `37016740156` then passed its contract tests, signed Android packaging, Windows native build and regression suite, and the matching-pair gate. Retained artifact checksums are recorded in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json). The verified pair is commit `0c618b809ae47dc67b4ad91a2423579c7efbb6d0`, version `20.13.0-ljk1291.1+0c618b809ae4`, with the same stable signing certificate fingerprint.
- The verified `0c618b809ae4` APK update is installed and its matching server is prepared. The earlier `cbf70c27269d` pair supplied the functional chart checks; the updated pair has not yet been streamed. No Metro Awakening, Godlike-resolution, 90 Hz, endurance or recovery qualification is claimed.

The diagnostic SteamVR session was shut down normally, its prior manual 150% resolution scale was restored, and only the test ALVR driver was unregistered. The remaining driver inventory matches the original VD registration. Functional return-to-VD verification still requires the owner's check.

The original VDXR runtime selection is unchanged. Headset experiment properties were restored to their recorded values, with one limitation: the first failed property-reset attempt did not preserve the original `debug.oculus.forceDisplayScaling` value. It is currently `0`, so exact restoration of that single property's pre-session state cannot be certified. The later reset implementation preserves before/after evidence even when a write fails.

The [GitHub fork](https://github.com/ljk1291/Quest3-Pyrowave) exists, with `upstream` retained and the reviewed commit preserved on `codex/upstream-reference`. A persistent private PKCS12 signing key is configured in encrypted Actions secrets; its public fingerprint in `fork.json` gates stable APK packaging. Actual VD dimensions, Metro gameplay/endurance/recovery checks and return-to-VD verification remain to be recorded. A configuration snapshot does not certify rollback.

Do not claim the milestone passed until matching native builds, controlled runs and operator review pass. Historical upstream captures do not satisfy these requirements for this machine.

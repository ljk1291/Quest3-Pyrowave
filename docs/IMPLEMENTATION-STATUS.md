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

The earlier supervised 72 Hz chart diagnostic is summarized in [diagnostic-2026-10-02.json](../results/diagnostic-2026-10-02.json). It confirms a clean decoder-counter window, fresh 72 Hz runtime evidence, initial image clarity, world-grid tracking, both controllers, and audio. It is explicitly unqualified: the reported submission-rate metric is 70.8319 FPS with 30 reused tracking timestamps, and it is not Metro/Godlike/90 Hz/endurance/recovery evidence. Background GPU work was not controlled during capture; the owner subsequently identified ComfyUI, and a later check found ComfyUI processes, 100% overall GPU utilization and approximately 14,600 MiB VRAM allocated. This later observation cannot establish activity at every earlier instant.

The repeated [controlled chart comparison](../results/controlled-chart-2026-10-02.json) uses the verified `0c618b809ae4` pair, identical 2080×2208-per-eye sources, 72 Hz, a ten-second warm-up and one-minute captures. ComfyUI reported no running or queued jobs in all 28 host samples per run. HEVC at 200 Mbps produced 71.918 selected decoded-buffer submission events/s and a 71.978 client-FPS 1% low. PyroWave at 400 Mbps produced 70.816 events/s and a 36.001 client-FPS 1% low, so the PyroWave diagnostic fails its rate screen despite its near-72 median. The owner confirmed clear upright labels and changing content in the PyroWave chart. No decoder failures, dropped frames or stale packets were counted during that PyroWave window. Decode-to-fence p95 was 14.164 ms against a 13.889 ms frame interval. This points to headset decode/presentation pressure; overlapping stage timings cannot be added, and the different bitrates prevent treating this as a codec-only latency comparison.

Tracking timestamps are not unique frame IDs: the Windows presenter deliberately permits their reuse across different game frames. The former duplicate-timestamp failure rule was incorrect. The report retains its old fields with explicit compatibility definitions, exposes timestamp reuse as diagnostic information, and gates strict fresh-frame acceptance separately. These builds do not yet expose a monotonic selected-output identity, so the current controls cannot establish that stricter acceptance requirement. Optical FPS and motion-to-photon remain unmeasured.

The owner requested proceeding directly to Godlike-sized 90 Hz screens. ALVR was set to 3072×3232 per eye for render and encoding (3072×3216 nominal Godlike height rounded up to ALVR's 32-pixel alignment). OpenVR chart source, ALVR negotiation and the Quest's fresh 90 Hz runtime evidence agreed. Actual VD encoded dimensions remain unverified. The [four one-minute screens](../results/godlike90-screen-2026-10-02.json) recorded:

| Profile | Selected submission events/s | Client FPS 1% low |
| --- | ---: | ---: |
| PyroWave CDF 9/7, staging, 300 Mbps | 22.49 | 18.00 |
| PyroWave CDF 9/7, direct eye copy, 300 Mbps | 29.99 | 22.50 |
| PyroWave Haar, direct eye copy, 300 Mbps | 50.42 | 44.99 |
| HEVC control, 200 Mbps | 89.68 | 89.95 |

All used the same chart dimensions and 90 Hz, with ComfyUI's queue idle at every host sample. The owner reported a clear image with low FPS and frame drops during the PyroWave sequence. Direct-copy telemetry verified activation and completed copies. No measured PyroWave profile meets the target; the best observed profile is an unqualified Haar/direct-copy experiment. HEVC meets the short chart rate proxy, not Metro/endurance acceptance. Median decode completion decreased from 44.03 ms to 32.99 ms to 19.59 ms across the PyroWave cells, all above the 11.11 ms target interval. Profile transform, conversion and synchronization next; raising bitrate is not a remedy for this measured decoder limit.

New source telemetry assigns identities when decoder sources dequeue outputs and counts each selected non-null output once after render submission and both eye-image releases. It excludes repeated/stale identities and null redraws, for MediaCodec and PyroWave. Its counter is not GPU completion or optical presentation. Python acceptance requires the source marker, monotonic counters, complete capture coverage and a passing rate in every endurance window. These packet changes require a new matching APK/server pair; the live results above retain their original build/tool identities and cannot acquire new evidence retrospectively.

## Build validation — 2026-10-02

- Reference Actions run `37009583485` completed successfully and its retained Android and Windows artifacts provide the untouched reference pair.
- Stable Actions run `37011907723` built and packaged the signed Android client and Windows streamer successfully. The Android APK was installed successfully with version `20.13.0-ljk1291.1+cbf70c27269d`; its certificate fingerprint was `4a3fe0a8d47ee67b01710df6ffdc870e91ebc5b8e7feec7c87534944ca2a44aa`.
- The run's matching-pair job correctly failed. Android and Windows metadata had the same source commit, package, protocol, application/server version, dependency revisions and shader hashes. Its only mismatch was the raw source-lock digest, caused by LF checkout bytes on Linux and CRLF checkout bytes on Windows. The recorded hash proof is in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json). The metadata writer was corrected to fingerprint a canonical LF representation.
- Stable Actions run `37016740156` then passed its contract tests, signed Android packaging, Windows native build and regression suite, and the matching-pair gate. Retained artifact checksums are recorded in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json). The verified pair is commit `0c618b809ae47dc67b4ad91a2423579c7efbb6d0`, version `20.13.0-ljk1291.1+0c618b809ae4`, with the same stable signing certificate fingerprint.
- The verified `0c618b809ae4` APK and matching server have streamed the controlled HEVC/PyroWave chart captures above. The earlier `cbf70c27269d` pair supplied the initial functional tracking/controller/audio checks. No Metro Awakening, Godlike-resolution, 90 Hz, endurance or recovery qualification is claimed.

Both supervised diagnostic sessions were shut down normally. The second session's prior manual 150% SteamVR scale, all 22 recorded headset experiment properties, and exact original external-driver inventory were restored and checked; only the test ALVR add-on was removed. The test dashboard and headset app were closed. The owner confirmed Virtual Desktop works normally after restoration, covering image, tracking, controllers and audio.

The original VDXR runtime selection is unchanged. Headset experiment properties were restored to their recorded values, with one limitation: the first failed property-reset attempt did not preserve the original `debug.oculus.forceDisplayScaling` value. It is currently `0`, so exact restoration of that single property's pre-session state cannot be certified. The later reset implementation preserves before/after evidence even when a write fails.

The [GitHub fork](https://github.com/ljk1291/Quest3-Pyrowave) exists, with `upstream` retained and the reviewed commit preserved on `codex/upstream-reference`. A persistent private PKCS12 signing key is configured in encrypted Actions secrets; its public fingerprint in `fork.json` gates stable APK packaging. Actual VD dimensions and Metro gameplay/endurance/recovery checks remain to be recorded. The return-to-VD procedure has now been functionally verified by the owner. A configuration snapshot does not certify rollback.

Do not claim the milestone passed until matching native builds, controlled runs and operator review pass. Historical upstream captures do not satisfy these requirements for this machine.

# Baseline implementation status

Target: Wi-Fi 6 / 5 GHz / 80 MHz, actual VD Godlike dimensions, 90 Hz, Metro Awakening. Reviewed upstream: `f6eae38380ecf0cb706aaa9aabc0fd66ec29cd6a`. Branch: `codex/stable-alvr-baseline`.

## Implemented locally

- Fork identity/package overlay, authoritative source lock and commit-stamped paired builds.
- Required codec libraries, shader hashes, artifact checksums and certificate fingerprint packaging; missing stable signing secrets fail the build.
- Bounded Windows GPU waits and terminal resource preservation; Android terminal decoder failures with process restart requirement.
- Explicit plan/control/capture, fail-closed acceptance, read-only preflight and observation/review templates.
- Supervised qualification, endurance, recovery, bottleneck experiments and return-to-VD runbook.

## Evidence and remaining gates

The first supervised Metro Awakening quality observation is a **subjective
fail**, not a rate or acceptance result. The verified `f2e9df5704cc` protocol
`.2` pair used 3072×3232 per eye, confirmed 90 Hz, PyroWave Haar/Compute,
fixed 500 Mbps TCP, 4:2:0 SDR, direct eye copy and the recommended allocation
(`0x10000300`). The owner reported dull colours, mura-like compression and
aliasing. This was the first Metro observation, so whether allocation changed
quality is unknown. The recorded UE 100% scale does not establish the game's
actual internal render resolution.

The post-exit 30-second telemetry capture and screenshots are excluded: Metro
had already closed, so they are not gameplay or Metro image-quality evidence.
There is no exact source/decode frame identity or numerical quality score.
Full range was negotiated, but a legacy downstream full-RGBA to limited-range
remap is a candidate for the dull-colour symptom. A codec-specific bypass is
implemented in source, with hardware-codec policy regression tests and a
`Q3PW_COLOUR` activation log. Build and headset validation remain pending; the
fix is not in the tested pair and does not diagnose the compression artifacts.
The session restored all recorded settings and verified the original VDXR
registration/manifest with zero restoration errors. The next sequence is
grayscale/range validation of the patch, then a fixed-checkpoint allocation
off/on replay, Haar/CDF 9/7 comparison at fixed 500 Mbps, and HEVC/VD controls
only where needed. See [the sanitized Metro observation](../results/metro-quality-feedback-2026-10-02.json).

The latest owner-authorized AFK Session 05 found a repeatable AHardwareBuffer
allocation improvement on the verified `f2e9df5704cc` pair. At the same
3072×3232 per eye, 90 Hz, 300 Mbps Haar/direct/Compute/4:2:0/TCP profile,
with minimal fragment usage held on, the recommended-allocation off/on/off/on
sequence produced:

| Recommended allocation | Fresh selected outputs/s | Conversion median | Decode-to-fence median |
| --- | ---: | ---: | ---: |
| Off | 56.00 | 4.91 ms | 17.47 ms |
| On | 82.69 | 1.31 ms | 11.54 ms |
| Off repeat | 55.25 | 5.09 ms | 17.62 ms |
| On repeat | 82.02 | 1.36 ms | 11.63 ms |

All four 50-second captures passed diagnostic evidence gates, with actual
allocation flags `0x300 / 0x10000300 / 0x300 / 0x10000300` verified for all
three slots and no fallback. Minimal Vulkan image usage alone was flat in a
separate 0/1/0 sequence (56.08 / 55.80 / 56.00 fresh outputs/s). GPU decode
remained about 9 ms, while conversion improved substantially. Both enabled
captures still fail the 90 Hz rate screen and have client-FPS 1% lows around
45; this is a promising candidate, not a promoted stable profile. See the
[allocation control](../results/allocation-screen-2026-10-02.json),
[recommended-AHB result](../results/optimal-ahb-screen-2026-10-02.json), and
[updated decoder plan](DECODER-OPTIMIZATION-PLAN.md).

Seven separate screenshot pairs showed LEFT/RIGHT labels and changing counters
without obvious new allocation-dependent corruption. Fine chroma edges/text
remain soft or fringed; the second off-control screenshot in the AHB series also
contains small menu indicators. These compositor captures establish neither
exact pixel equivalence nor subjective Metro/motion quality. No video capture
or profiler ran during these rate windows. All saved ALVR setting keys, manual
150% SteamVR scale, dashboard setting, 24 headset properties, external-driver
inventory and VDXR registration/manifest were restored and verified; the test
dashboard, SteamVR and client were closed.

Local Python checks pass. Clean LF source reconstruction applies the ALVR/PyroWave overlays, and the codec shader manifest passes. Native compilation and headset execution remain separate gates. No Godlike/90 Hz result is claimed. The untouched upstream reference build is retained with its artifacts.

The earlier supervised 72 Hz chart diagnostic is summarized in [diagnostic-2026-10-02.json](../results/diagnostic-2026-10-02.json). It confirms a clean decoder-counter window, fresh 72 Hz runtime evidence, initial image clarity, world-grid tracking, both controllers, and audio. It is explicitly unqualified: the reported submission-rate metric is 70.8319 FPS with 30 reused tracking timestamps, and it is not Metro/Godlike/90 Hz/endurance/recovery evidence. Background GPU work was not controlled during capture; the owner subsequently identified ComfyUI, and a later check found ComfyUI processes, 100% overall GPU utilization and approximately 14,600 MiB VRAM allocated. This later observation cannot establish activity at every earlier instant.

The repeated [controlled chart comparison](../results/controlled-chart-2026-10-02.json) uses the verified `0c618b809ae4` pair, identical 2080×2208-per-eye sources, 72 Hz, a ten-second warm-up and one-minute captures. ComfyUI reported no running or queued jobs in all 28 host samples per run. HEVC at 200 Mbps produced 71.918 selected decoded-buffer submission events/s and a 71.978 client-FPS 1% low. PyroWave at 400 Mbps produced 70.816 events/s and a 36.001 client-FPS 1% low, so the PyroWave diagnostic fails its rate screen despite its near-72 median. The owner confirmed clear upright labels and changing content in the PyroWave chart. No decoder failures, dropped frames or stale packets were counted during that PyroWave window. Decode-to-fence p95 was 14.164 ms against a 13.889 ms frame interval. This points to headset decode/presentation pressure; overlapping stage timings cannot be added, and the different bitrates prevent treating this as a codec-only latency comparison.

Tracking timestamps are not unique frame IDs: the Windows presenter deliberately permits their reuse across different game frames. The former duplicate-timestamp failure rule was incorrect. The report retains its old fields with explicit compatibility definitions, exposes timestamp reuse as diagnostic information, and gates strict fresh-frame acceptance separately. The historical `.1` builds used for the captures above did not expose a monotonic selected-output identity, so those capture records cannot establish that stricter acceptance requirement. Optical FPS and motion-to-photon remain unmeasured.

The owner requested proceeding directly to Godlike-sized 90 Hz screens. ALVR was set to 3072×3232 per eye for render and encoding (3072×3216 nominal Godlike height rounded up to ALVR's 32-pixel alignment). OpenVR chart source, ALVR negotiation and the Quest's fresh 90 Hz runtime evidence agreed. Actual VD encoded dimensions remain unverified. The [four one-minute screens](../results/godlike90-screen-2026-10-02.json) recorded:

| Profile | Selected submission events/s | Client FPS 1% low |
| --- | ---: | ---: |
| PyroWave CDF 9/7, staging, 300 Mbps | 22.49 | 18.00 |
| PyroWave CDF 9/7, direct eye copy, 300 Mbps | 29.99 | 22.50 |
| PyroWave Haar, direct eye copy, 300 Mbps | 50.42 | 44.99 |
| HEVC control, 200 Mbps | 89.68 | 89.95 |

All used the same chart dimensions and 90 Hz, with ComfyUI's queue idle at every host sample. The owner reported a clear image with low FPS and frame drops during the PyroWave sequence. Direct-copy telemetry verified activation and completed copies. The direct-copy cells also reported `debug.oculus.refreshRate=90`, whereas staging and HEVC reported it unset; its origin is unverified. Although fresh runtime evidence confirmed 90 Hz in every cell, the staging/direct comparison is not a strictly isolated copy-mode experiment and must be repeated with that property held equal. The legacy `display_scaling` flag includes forced refresh; `forceDisplayScaling` itself remained 0. No measured PyroWave profile meets the target; the best observed profile is an unqualified Haar/direct-copy experiment. HEVC meets the short chart rate proxy, not Metro/endurance acceptance. Median decode completion decreased from 44.03 ms to 32.99 ms to 19.59 ms across the PyroWave cells, all above the 11.11 ms target interval. Profile transform, conversion and synchronization next; raising bitrate is not a remedy for this measured decoder limit.

New source telemetry assigns identities when decoder sources dequeue outputs and counts each selected non-null output once after render submission and both eye-image releases. It excludes repeated/stale identities and null redraws, for MediaCodec and PyroWave. Its counter is not GPU completion or optical presentation. Python acceptance requires the source marker, monotonic counters, complete capture coverage and a passing rate in every endurance window. These packet changes use protocol revision `20.13.0-ljk1291.2` to reject the incompatible earlier `.1` wire format and require a new matching APK/server pair; the live results above retain their original build/tool identities and cannot acquire new evidence retrospectively.

The `.2` pair was tested in owner-authorized AFK Session 03 with 3072×3232-per-eye render and encoded resolution, 90 Hz, PyroWave Haar, direct eye copy, TCP transport and 4:2:0 chroma. Each short chart screen passed the build-identity, unchanged-settings, strict selected-output-counter, runtime, host-isolation and thermal gates, with no stream errors. The fresh source counter was verified in all four runs:

| Profile | Selected-output events/s | 90 Hz rate screen |
| --- | ---: | --- |
| `haar300-a-retry` | 52.95 | Failed |
| `haar400` | 54.12 | Failed |
| `haar600` | 53.42 | Failed |
| `haar300-b` | 55.41 | Failed |

This establishes fresh selected-output telemetry on the matched `.2` build, but none of these profiles met the 90 Hz target. The short chart screens are not Metro, endurance, recovery, optical-latency or display-FPS evidence. Captured screenshots and video are qualitative only: chart overlays obscure the image, and no decoded-buffer score or manual image-quality review was collected. The later pass-profile work is separate from this tested pair.

Owner-authorized AFK Session 04 used the verified `f2e9df5704cc` pair at the same geometry,
300 Mbps, Haar/direct/Compute/4:2:0/TCP, with diagnostic profiling enabled and the performance
HUD and SteamVR dashboard hidden. The short profiler interval measured approximately **3.75 ms
dequantization** and **5.00 ms inverse-wavelet reconstruction**, as delayed Granite window means.
A separate 25-second telemetry window inside that chart measured an 8.99 ms GPU-decode median,
4.92 ms conversion median and 17.31 ms decode-to-fence median. Fresh selected outputs averaged
56.35/s; this is a diagnostic, not an improvement comparison or a 90 Hz pass.
Build/runtime, unchanged settings, telemetry and thermal checks passed, with no reported stream
errors. See [the sanitized profile and visual evidence record](../results/decoder-profile-2026-10-02.json).

Two unobstructed 4128×2208 screenshots and a 7.79-second recording were saved privately in a
separate chart run. LEFT/RIGHT labels and counter changes were visible. Fine coloured text and
thin edges show softness/fringing, but compositor transforms prevent isolating codec loss or
assigning an exact pixel-quality score. Prior tracking/controller/audio confirmation is retained;
AFK captures do not establish motion comfort or Metro quality. Saved resolution, dashboard
setting, all 24 headset properties, driver inventory and VDXR runtime were restored and verified.

## Build validation — 2026-10-02

- Reference Actions run `37009583485` completed successfully and its retained Android and Windows artifacts provide the untouched reference pair.
- Stable Actions run `37011907723` built and packaged the signed Android client and Windows streamer successfully. The Android APK was installed successfully with version `20.13.0-ljk1291.1+cbf70c27269d`; its certificate fingerprint was `4a3fe0a8d47ee67b01710df6ffdc870e91ebc5b8e7feec7c87534944ca2a44aa`.
- The run's matching-pair job correctly failed. Android and Windows metadata had the same source commit, package, protocol, application/server version, dependency revisions and shader hashes. Its only mismatch was the raw source-lock digest, caused by LF checkout bytes on Linux and CRLF checkout bytes on Windows. The recorded hash proof is in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json). The metadata writer was corrected to fingerprint a canonical LF representation.
- Stable Actions run `37016740156` then passed its contract tests, signed Android packaging, Windows native build and regression suite, and the matching-pair gate. Retained artifact checksums are recorded in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json). The verified pair is commit `0c618b809ae47dc67b4ad91a2423579c7efbb6d0`, version `20.13.0-ljk1291.1+0c618b809ae4`, with the same stable signing certificate fingerprint.
- Stable Actions run `37032258856` passed its contract tests, signed Android packaging, Windows native build and regression suite, and the matching-pair gate for the selected-output telemetry protocol revision. The retained pair is commit `d4735d88985a75f3605d00d88aca543327a0f090`, version `20.13.0-ljk1291.2+d4735d88985a`, with stable certificate fingerprint `4a3fe0a8d47ee67b01710df6ffdc870e91ebc5b8e7feec7c87534944ca2a44aa`; artifact IDs and hashes are in [build-validation-2026-10-02.json](../results/build-validation-2026-10-02.json).
- The verified `0c618b809ae4` APK and matching server have streamed the controlled HEVC/PyroWave chart captures above. The earlier `cbf70c27269d` pair supplied the initial functional tracking/controller/audio checks. No Metro Awakening, Godlike-resolution, 90 Hz, endurance or recovery qualification is claimed.
- The `.2` pair completed the owner-authorized AFK Session 03 bitrate screen above. It supplied valid strict selected-output evidence but no 90 Hz pass, and remains unqualified for Metro, endurance, recovery or image-quality acceptance.
- Stable Actions run `37038811141` passed tests, signed Android packaging, Windows native compilation/regressions and matching-pair verification for `f2e9df5704cc679513848bf6ffb63ef1695479f9`. Both retained artifact checksums and local pair verification passed; this pair supplied the Session 04 profiler and clean image captures. The signing certificate is unchanged.

Metadata limitation: the historical `sources.lock.json` contains an unused duplicate
`fork.protocol_version` still set to `.1`. The build/version writers read `fork.json`,
which supplies the actual `.2` protocol; the source-lock snapshot is copied verbatim
under `dependency_revisions`. Both packaged artifacts agree, and the installed/server
versions were verified, but that redundant field is misleading. The source now removes
the duplicate identity and packaging rejects application identity in the dependency lock.
All 13 build-contract tests pass. This packaging cleanup is not part of the tested
`f2e9df5704cc` native pair; its immutable artifact records are preserved. Dependency
revisions themselves are unchanged.

The earlier two supervised diagnostic sessions were shut down normally. The second session's prior manual 150% SteamVR scale, all 22 recorded headset experiment properties, and exact original external-driver inventory were restored and checked; only the test ALVR add-on was removed. The test dashboard and headset app were closed. The owner confirmed Virtual Desktop works normally after restoration, covering image, tracking, controllers and audio.

Session 03 also restored its resolution, driver registration and all 22 recorded headset properties, then closed SteamVR and the test dashboard. The original VDXR selection was unchanged. A new post-session functional Virtual Desktop check remains pending while the owner is away.

The original VDXR runtime selection is unchanged. Headset experiment properties were restored to their recorded values, with one limitation: the first failed property-reset attempt did not preserve the original `debug.oculus.forceDisplayScaling` value. It is currently `0`, so exact restoration of that single property's pre-session state cannot be certified. The later reset implementation preserves before/after evidence even when a write fails.

The [GitHub fork](https://github.com/ljk1291/Quest3-Pyrowave) exists, with `upstream` retained and the reviewed commit preserved on `codex/upstream-reference`. A persistent private PKCS12 signing key is configured in encrypted Actions secrets; its public fingerprint in `fork.json` gates stable APK packaging. Actual VD dimensions and Metro gameplay/endurance/recovery checks remain to be recorded. The return-to-VD procedure has now been functionally verified by the owner. A configuration snapshot does not certify rollback.

Do not claim the milestone passed until matching native builds, controlled runs and operator review pass. Historical upstream captures do not satisfy these requirements for this machine.

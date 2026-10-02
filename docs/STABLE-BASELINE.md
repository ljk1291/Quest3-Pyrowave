# Supervised Wi-Fi / Godlike / 90 Hz baseline

Target: sustained 90 Hz in Metro Awakening at the owner's **observed** VD Godlike render and encoded dimensions. Hardware: RTX 5080, Ryzen 5 7600, Ethernet to dedicated Wi-Fi 6, initially 5 GHz / 80 MHz. Smaller resolution is diagnostic and cannot pass this target.

## Preserve and record the starting point

Close VR applications for the snapshot. From the repository root:

```powershell
python -m tools.quest3.preflight --out results/local/preflight-session-01
```

This reads PC/runtime/network/GPU information and copies named VD/SteamVR configuration files into an ignored private folder. It does not change registration or start VR. Missing files are recorded as missing: confirm configuration locations for your installed versions and back up additional relevant files before changes. Do not publish raw snapshots; they can include usernames, private paths and network information.

Copy `presets/stable-baseline-observations.template.json` into `results/local/`. Record Quest OS, GPU driver, SteamVR/VD versions, router model/channel/width, Ethernet link speed, VD codec/bitrate, and a repeatable Metro checkpoint/graphics configuration. Preserve the current VD AV1 settings. Record render and encoded dimensions **per eye**, identifying any figures which instead describe the whole stereo frame.

Record the active OpenXR runtime, SteamVR driver/add-on state, application resolution scale and motion smoothing. Disable frame synthesis for ALVR target qualification in the runtime UI and record its readback. Requested and negotiated dimensions must both match the recorded target. Document codec padding and projection/FOV differences; equal pixel counts do not establish equal clarity.

VD's overlay may show only a quality name and scale, such as `Godlike, 100%`. That is not evidence of pixel dimensions. Capture fresh runtime/game render-size evidence and encoder/decoder dimensions from the same reference session; distinguish recommended render size from the game's actual submitted image. Leave unavailable dimensions unknown. This inventory is required for target comparisons, but need not delay the first connection and smaller-resolution diagnostic chart.

## Prepare the profile

Use a verified matching APK/server pair from [BUILD.md](BUILD.md). Substitute actual per-eye dimensions for RW/RH/EW/EH below; do not guess the Godlike preset.

```text
python -m tools.quest3.bench baseline-plan --render-width RW --render-height RH --encoded-width EW --encoded-height EH --out results/local/baseline-plan.json
python -m tools.quest3.bench capabilities --adb adb --out results/local/capabilities.json
python -m tools.quest3.control apply --codec PyroWave --mbps 400 --hz 72 --decode-path Compute --wavelet Cdf97 --chroma 420 --transport Tcp --render-width 2080 --render-height 2208 --encoded-width 2080 --encoded-height 2208 --capabilities results/local/capabilities.json
```

`apply` changes ALVR settings and checks readback. Restart the session after codec, transport, resolution or refresh changes and confirm negotiated settings. The 2080×2208 example is diagnostic only; use the recorded target for later cells. The broad historical `bench plan` command is research screening; use `baseline-plan` here.

Start TCP, 4:2:0, Compute, CDF 9/7, SDR, fixed bitrate, no foveation and synchronous presentation. Disable direct/async eye copy, cache/scheduling experiments, multiple workers and display scaling. Capture their start/end readback and restart the client after changing initialization properties. `control experiment-properties --adb adb` reads display properties; adding `--disable-display-scaling --disable-experiments` explicitly resets the documented scaling, copy, scheduling and worker experiments and records before/after. It preserves the source-defined unset `direct_flip_y` default. Do not force clocks or bypass proximity sleep.

Before gameplay, run the deterministic source:

```powershell
python -m tools.quest3.stereo_scene --quality --pulse --seconds 180 --out results/local/chart-session-01
```

Check left/right assignment, orientation, near-black/near-white range, colour patches, labels and changing frames. Record the result in the operator review. Stop for visible corruption, input faults or repeated GPU errors.

## Controlled sequence

| Stage | Configuration | Evidence |
|---|---|---|
| VD reference | Current AV1, Godlike, 90 Hz | Same Metro scene; dimensions, clarity and motion |
| ALVR control | HEVC 200 Mbps, target dimensions, 90 Hz | Same fork/runtime/game/scene |
| Initial qualification | PyroWave 2080×2208 per eye, 72 Hz, 400 Mbps | Chart, inputs, audio and telemetry |
| Target screens | Target dimensions, 72 then 90 Hz, 300/400/600 Mbps | ≥60-second screens after warm-up |
| Optional screen | 800 Mbps after lower-rate stability | Separate gated evidence |
| Endurance | Qualifying target/90 Hz profile | Three ≥5-minute windows, then ≥30 minutes Metro |
| Recovery | Ten reconnects, sleep/resume, controller reconnect, temporary network interruption | Bounded supervised actions and recovery times |

Warm up consistently, alternate comparisons and return to comparable thermal conditions. Keep scene, graphics, SteamVR scale and router/headset placement fixed. Document differences rather than averaging across changed settings. 160 MHz, USB, direct eye copy and Haar come later as separate experiments.

## Capture and acceptance

Use Python 3.12 and install `tools/quest3/requirements.txt` into a local environment for the capture and stereo-chart tools. Before each warm-up, confirm that no unrelated GPU workload is running and that VRAM has enough headroom: check process names and VRAM consumers in a local GPU monitor, including ComfyUI or other compute backends. Record the result in the operator review. Do not infer a competing workload solely from overall GPU utilization, since the VR workload itself can legitimately use the GPU heavily. Start capture after the profile/game settles. Use 310 seconds for a five-minute observed frame window and 1810 seconds for thirty minutes to allow event-boundary overhead:

```powershell
python -m tools.quest3.bench capture --adb adb --seconds 1810 --hz 90 --build-manifest out/android/BUILD-METADATA.json --out results/local/metro-target-final
```

The report records settings at both ends, negotiated dimensions/rate, installed versions, fresh runtime markers, device samples and frame counters. Use metadata from the verified artifact pair. Missing telemetry prevents a pass; improve instrumentation instead of inventing values.

Copy `presets/operator-review.template.json` into the capture folder. Bind it to the report's `capture_id` and record actual chart, Metro clarity/motion, tracking, controller and audio observations. Set `no_competing_gpu_workload` true only after the pre-capture process/VRAM check; unknown or false prevents acceptance. Leave other unknown fields null. Then:

```powershell
python -m tools.quest3.bench accept --report results/local/metro-target-final/report.json --expected results/local/baseline-plan.json --mbps 400 --review results/local/metro-target-final/operator-review.json --out results/local/metro-target-final/acceptance.json
```

Acceptance is separate from legacy rate checks, with explicit failure reasons. `--mbps` must be the exact qualifying capture rate and be one of 300, 400, 600 or 800; use 800 only after recording the lower-rate gate evidence. It requires target dimensions, confirmed 90 Hz, fresh submissions and 1% low within the existing 2% tolerance, matching versions, complete telemetry, unchanged effective settings, no decoder/stream errors, acceptable thermals and operator confirmation. Independent five-minute windows check endurance deterioration. Review the three prior repetitions and recovery checks before promoting a profile: one final accepted capture does not certify the entire milestone.

These counters describe submission/decode/copy stages. Optical display FPS and motion-to-photon remain unknown without independent measurement. Equal resolution alone does not prove VD-equivalent image quality.

## Return to Virtual Desktop

This procedure is prepared; mark it **tested** only after an actual supervised verification:

1. End capture, close Metro and the Quest app, and shut down SteamVR normally. After terminal GPU failure fully exit the affected process; do not loop reconnects.
2. Disable/unregister only this fork's ALVR add-on through the dashboard/SteamVR UI. Restore recorded previous add-on/driver state. Keep VD installed and registered.
3. Restore the previous OpenXR runtime with its owning application's selector (VD if VDXR was active). Compare the exact active-runtime path to preflight; do not guess a registry path.
4. Restore deliberately changed resolution, motion-smoothing and debug properties from their before-state. Confirm VD Godlike, 90 Hz, previous codec and bitrate.
5. Run `python -m tools.quest3.preflight --verify results/local/preflight-session-01/preflight.json`. This checks backup integrity/current drift; it does not restore files. If restoration is needed, close the owning app, preserve its current file, and restore only the documented file from the verified backup.
6. Connect VD, launch the reference checkpoint and verify image, motion, controllers, tracking and audio. Record any difference; only then set `return_to_virtual_desktop_verified` true.

## Improve the measured bottleneck

For network limits, compare 80/160 MHz at the same profile; use USB only as a diagnostic. For Quest limits, separate decode/conversion/fence/eye-copy timings, then compare direct eye copy and Haar/CDF 9/7 individually with chart checks. For PC limits, separate game rendering, SteamVR composition and encoding before editing streamer code. UDP, 4:4:4, asynchronous copying, multiple workers and 120 Hz remain outside the first stable profile.

Publish only reviewed sanitized summaries: build/manifest hashes, software versions, non-identifying settings, aggregate metrics, failures and operator judgement. Remove usernames, IPs, headset serials, secrets, private paths and raw logs. If Godlike/90 Hz fails, report the measured limitation and best passing diagnostic separately.

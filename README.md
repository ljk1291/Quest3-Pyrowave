# Quest3-Pyrowave: stable ALVR baseline

This fork targets sustained **90 Hz at the owner's measured Virtual Desktop Godlike dimensions** on Quest 3 over a dedicated Wi-Fi 6 router. The first game is Metro Awakening, using SteamVR's OpenXR runtime. Godlike/90 Hz is a test target, **not a demonstrated result**.

Development starts from [JMS1717/Quest3-Pyrowave](https://github.com/JMS1717/Quest3-Pyrowave) at `f6eae38380ecf0cb706aaa9aabc0fd66ec29cd6a`. Dependencies remain pinned in [sources.lock.json](sources.lock.json). This fork is `ljk1291/Quest3-Pyrowave`, with Android package `io.github.ljk1291.quest3pyrowave` and its own version identity. See [implementation status](docs/IMPLEMENTATION-STATUS.md) for actual validation.

Latest short diagnostic: driver-recommended Android output-buffer allocation
raised fresh selected outputs from roughly **56/s to 82/s** at 3072×3232 per eye,
90 Hz and 300 Mbps. Reverting and repeating reproduced the change. The low-rate
check still fails, and exact image equivalence, Metro and endurance remain
unqualified. See the [controlled results](results/optimal-ahb-screen-2026-10-02.json)
and [optimization plan](docs/DECODER-OPTIMIZATION-PLAN.md); this is an experimental
Haar/direct-copy profile, not a new default.

## Start here

1. [Build and install a matching pair](docs/BUILD.md). Stable builds require a persistent private signing key; temporary development signatures are labelled.
2. Follow the [supervised baseline and return-to-VD procedure](docs/STABLE-BASELINE.md). Record render and encoded dimensions separately before generating the profile.
3. Keep private configurations and device captures under ignored `results/local/`. Use the observation and operator-review templates in `presets/`.

The initial PyroWave profile is **TCP, 4:2:0, Compute, CDF 9/7, SDR, fixed bitrate, synchronous presentation**. Foveation, adaptive bitrate, frame synthesis and optional decoder/copy experiments are excluded from target qualification. Lower resolution is diagnostic only. HEVC at 200 Mbps in this same fork is the codec control; VD Godlike/90 Hz is the user-experience reference.

For a short decoder diagnostic only, `adb shell setprop debug.q3pw.pass_profile 1` before restarting
the client enables local `[Q3PW_GPU_PASS]` log lines every 90 successful GPU completions. They are
Granite timestamp **frame-context window means** for known decoder passes, not frame-specific
latency, display FPS or acceptance telemetry. Borrowed command buffers retire Granite contexts on
later decode calls, so results lag by the frame-context ring. Ninety completed submissions trigger
reporting; the means do not promise exactly ninety timestamp samples. The off-by-default probe
was verified on the matching `f2e9df5704cc` pair in a short Quest chart diagnostic.
It measured roughly 3.75 ms dequantization and 5.00 ms inverse-wavelet reconstruction;
the separate conversion median was 4.92 ms. See the [sanitized profile](results/decoder-profile-2026-10-02.json).

Save only the fresh diagnostic log window, then parse it with
`python -m tools.quest3.pass_profile --log profile.log --out profile.json`.
The offline parser rejects missing activation, invalid phase timings and native
timestamp warnings. Preserve current decoder activation as configuration provenance and restrict
timing samples to the chart interval; an old activation is not a fresh timing sample.
See the [decoder test plan and backlog](docs/DECODER-OPTIMIZATION-PLAN.md)
for the controlled bitrate results and the next experiments.

## Baseline changes

- Authoritative source pins, fork identity, matching build metadata, artifact checksums, shader verification and APK certificate fingerprints.
- Bounded Windows GPU waits and terminal GPU failure handling on both platforms. Unsafe GPU work cannot be reset and reused; a terminal fault requires restarting the affected process.
- Explicit render/encoded dimensions, refresh, transport, bitrate and codec options in control and plan tools.
- Separate acceptance results rejecting missing evidence, changed settings, mismatched builds, incomplete captures and absent operator review. Existing rate/latency report fields remain; optical display FPS and motion-to-photon are not inferred.

## Runtime compatibility

ALVR provides a SteamVR driver. PC OpenXR games run through **SteamVR's OpenXR runtime → ALVR → Quest**. The Quest client also uses OpenXR. VDXR is Virtual Desktop's PC runtime and is not a backend for ALVR; using VDXR with PyroWave is a separate integration project. Oculus PC games through Revive are a later milestone.

## Validation and history

Run `python -m unittest discover -s tests -v` for Python tooling. CI adds build contracts, native GPU-policy and software GLES checks, Rust checks, Android/Windows compilation and artifact verification. See [BUILD.md](docs/BUILD.md).

[README.upstream.md](README.upstream.md) preserves the reviewed upstream README. Historical results and research documents describe upstream hardware/sessions; they are not results for this owner's RTX 5080, router or Godlike target. Historical unattended-testing instructions do not authorize unattended testing here.

## Credits and licences

This is a fork of JMS1717's Quest port, based on [Terminal-ennui's integration](https://github.com/Terminal-ennui/galaxy-xr-alvr-pyrowave-444). [PyroWave](https://github.com/Themaister/pyrowave) and [Granite](https://github.com/Themaister/Granite) are by Hans-Kristian Arntzen (Themaister); [ALVR](https://github.com/alvr-org/ALVR) supplies streaming, the SteamVR driver, tracking, audio and controllers. Attribution and licences are retained in [LICENSE](LICENSE), [NOTICE](NOTICE), source notices and packaged dependency notices. This is an independent project.

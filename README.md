# Quest3-Pyrowave: ljk1291 fork

This fork tunes [JMS1717/Quest3-Pyrowave](https://github.com/JMS1717/Quest3-Pyrowave) for one
setup: **Quest 3 over a dedicated Wi-Fi 6 router at 160 MHz, 90 Hz, at the owner's measured Virtual
Desktop "Godlike" density.** The owner judges it by fresh frames per second (distinct decoded
frames actually shown) and by visible compression, with Virtual Desktop as the reference.
Godlike at 90 Hz is a target, **not a demonstrated result** of this branch.

[README.upstream.md](README.upstream.md) keeps upstream's README: features, settings, measured
profiles, troubleshooting. Everything there applies here unless this page says otherwise.

## Base

| | |
|---|---|
| Upstream commit | `18d43ceae4ceb808a85acc127375727bd698bd67` (`.65`, protocol `20.13.0-quest3.pyro.65`) |
| Pinned sources | ALVR `7eda092`, PyroWave `d2997ac`, Granite `842d9d5` ([sources.lock.json](sources.lock.json)) |
| Fork identity | [fork.json](fork.json): version `20.13.0-ljk1291.3`, package `io.github.ljk1291.quest3pyrowave` |

## What the fork adds

The fork changes upstream's tree only through overlay patches applied after upstream's own patch
stack, each pinned by SHA-256. [patches/README.md](patches/README.md) lists the stack and the rules.

| Overlay | State |
|---|---|
| `fork-identity-alvr.patch`: own version, protocol and Android package (label "Quest3 PyroWave Baseline"), so it installs beside upstream's app and only pairs with a server of the same fork version | in this branch |
| `fast-abr.patch`: opt-in `video.pyrowave.fast_abr` (default off): per-frame PyroWave budget below ALVR's ceiling over TCP, bounded send buffer, Aimd/Capacity modes, inactive on UDP, markers `[Q3PW_FAST_ABR]` ([docs/FAST-ABR.md](docs/FAST-ABR.md)) | in this branch (not yet built on `.65`) |
| `frame-dump.patch`: opt-in lossless frame dumps for quality scoring, incl. the packed `post_decode` stage (`ALVR_Q3PW_FRAME_DUMP`, `debug.q3pw.frame_dump`; [docs/FRAME-DUMP.md](docs/FRAME-DUMP.md)) | in this branch (not yet built on `.65`) |
| `frame-loss-diagnostics.patch`: opt-in frame-loss counters upstream lacks (`ALVR_FRAME_LOSS`, `debug.q3pw.frame_loss`; [docs/FRAME-LOSS-DIAGNOSIS.md](docs/FRAME-LOSS-DIAGNOSIS.md)) | in this branch (not yet built on `.65`) |
| `client-output-queue.patch`: opt-in decoded output FIFO (`debug.q3pw.output_queue=2\|3`; covers TCP, wired and UDP; marker `[Q3PW_OUTPUT_QUEUE]`; needs the matching `tools/pyroclient`; [docs/OUTPUT-QUEUE.md](docs/OUTPUT-QUEUE.md)) | in this branch (not yet built on `.65`) |
| `fork-baseline.patch`: fork baseline, applied last: fresh-output counter (`selected_output_submissions`), PyroWave full-range fix (`ALVR_Q3PW_PYROWAVE_FULL_RANGE=0` opts out; `[Q3PW_RANGE]`, `[Q3PW_COLOUR]`), FOV crop (`video.fov_crop.enabled`, `.content.horizontal_tangent_multiplier` / `vertical_tangent_multiplier`; `[FOV-CROP]`), shutdown order, NVENC preflight (`ALVR_NVENC_DIMENSION_PREFLIGHT=1`); extends the bincode telemetry packet, so never mix with builds without it ([docs/FORK-BASELINE.md](docs/FORK-BASELINE.md)) | in this branch (not yet built on `.65`) |

The build side adds the overlay pins (`tools/ci/source_lock.py`), a build identity stamped into
both binaries (`20.13.0-ljk1291.3+<commit>`), `BUILD-METADATA.json` for each artifact and a CI check
that the Android and Windows builds match. New runtime behaviour stays opt-in with a log marker.

## Building

GitHub Actions builds the reference artifacts. A push on `main` or `codex/**` runs the CPU checks
only. To build the APK and the Windows streamer:

```
gh workflow run ci.yml --ref codex/upstream-rebase -f cpu_only=false
gh run download <run-id> -n Quest3-Pyrowave-Android -D out/<name>-<run-id>/android
gh run download <run-id> -n Quest3-Pyrowave-Windows -D out/<name>-<run-id>/windows
```

The Android artifact holds `Quest3-Pyrowave-stable.apk` (signed with the fork's stable key in the
`QUEST3_SIGNING_KEYSTORE_BASE64` / `_PASSWORD` secrets), native probes, `APK-CERTIFICATE.txt`,
`BUILD-METADATA.json` and `SHA256SUMS.txt`. The Windows artifact holds
`Quest3-Pyrowave-Windows.zip`, `BUILD-METADATA.json` and `SHA256SUMS.txt`. Install a matching pair
only: the client and server refuse a different fork version. `tools/local/fast_build.py` also
works ([docs/LOCAL-BUILD.md](docs/LOCAL-BUILD.md)) where a toolchain exists.

## Upgrading from `20.13.0-ljk1291.2`

- The headset client resets its stored config when the protocol changes, so it comes up with a
  new random `NNNN.client` hostname; trust it in the dashboard.
- A `session.json` from an older build loads with matching settings kept and new ones defaulted.
  Because the version differs, the dashboard clears the trusted clients and reopens the setup
  wizard on first start. A fresh streamer folder starts from the fork's defaults.

## Credits and licences

Quest3-Pyrowave is JMS1717's Quest 3 port, based on
[Terminal-ennui's Galaxy XR integration](https://github.com/Terminal-ennui/galaxy-xr-alvr-pyrowave-444).
[PyroWave](https://github.com/Themaister/pyrowave) and [Granite](https://github.com/Themaister/Granite)
are by Hans-Kristian Arntzen (Themaister). [ALVR](https://github.com/alvr-org/ALVR) supplies
streaming, the SteamVR driver, tracking, audio and controllers. Licences and attribution are in
[LICENSE](LICENSE), [NOTICE](NOTICE), [licenses/](licenses/), the source notices and the notices
packaged with each build. This fork is independent of upstream and of ALVR.

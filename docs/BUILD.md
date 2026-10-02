# Reproducible fork builds

Build Android and Windows from the **same repository commit**. `sources.lock.json` defines dependency URLs, commits and toolchains; `fork.json` defines the package/version. Reproducibility means recorded inputs and recipe, not byte-identical signatures or ZIP timestamps.

## Cloud build contract

`.github/workflows/ci.yml` runs on main, `codex/**`, pull requests and manual dispatch. It reconstructs sources, checks pins/shaders, runs Python/native/Rust checks, compiles both platforms, and verifies the artifact pair. The client/server version includes the repository commit so captures can compare installed versions to build metadata.

Main and manual builds require repository secrets `QUEST3_SIGNING_KEYSTORE_BASE64` and `QUEST3_SIGNING_KEYSTORE_PASSWORD`. Missing secrets fail the stable build. Branch/PR development builds use a labelled temporary key and are not a persistent installation channel. Keep a private backup of the release keystore/password, outside tracked files. Never paste secrets into issues, logs or reports.

Generate a PKCS12 signing key once with JDK 17 keytool, using its interactive password prompts:

```text
keytool -genkeypair -storetype PKCS12 -keystore <private-directory>/quest3-baseline.p12 -alias quest3-baseline -keyalg RSA -keysize 3072 -validity 10000 -dname "CN=ljk1291 Quest3-Pyrowave"
```

Store the base64 file contents and password in those two Actions secrets. Keep the same key for subsequent stable builds. A development-to-stable signature change may require removing **only this fork's app**, losing its app configuration. Do not uninstall VD or another ALVR package to resolve a signature mismatch.

Download `Quest3-Pyrowave-Android` and `Quest3-Pyrowave-Windows` from one successful workflow, including metadata. Verify the unpacked folders:

```powershell
python tools/ci/build_metadata.py verify-pair out/android/BUILD-METADATA.json out/windows/BUILD-METADATA.json
```

Metadata records dependency revisions, repository version, shader hashes, artifact/native-library hashes and Android signing kind/certificate fingerprint. Missing codec libraries fail packaging.

## Local source reconstruction

Use an empty destination, a short Windows path, Git for Windows, Python, CMake, Ninja and the pinned Rust toolchain. Windows requires Visual Studio 2022 C++ tools, Windows SDK, ATL and LLVM/libclang. Android uses JDK 17, SDK/platform 35/build-tools 35.0.0 and the locked NDK. The workflow contains loader download/integrity checks and Rust helper installation commands.

```powershell
$env:XRWIRED_INPUTS = 'C:\q3pw'
# Use sh.exe from your own Git for Windows installation.
sh tools/ci/fetch_sources.sh C:/q3pw/research
python tools/ci/stamp_alvr_version.py C:/q3pw/research/ALVR-20.13.0
tools\windows\build_pyrowave_pc.cmd interop
tools\windows\build_streamer.cmd
```

For Android set `XRWIRED_ANDROID_SDK`, `XRWIRED_NDK`, `JAVA_HOME`, `CARGO_APK_RELEASE_KEYSTORE` and `CARGO_APK_RELEASE_KEYSTORE_PASSWORD` to local toolchain/private-key locations, then follow CI's `tools/build_pyrowave_android.sh` and `tools/build_alvr_2013.sh` recipe. Environment variables cannot replace locked source revisions.

Source fetch refuses an existing source directory. Reconstruct into a new directory rather than erasing work. ALVR applies the inherited instrumentation and Quest overlays followed by `stable-baseline-alvr.patch` and `fork-identity-alvr.patch`. PyroWave applies its cumulative research overlay then the Quest overlay. Preserve LF checkouts (`core.autocrlf=false`), as set by the fetch script.

## Supervised installation

First complete the snapshot in [STABLE-BASELINE.md](STABLE-BASELINE.md). Stop existing VR sessions and extract the Windows ZIP into a dedicated directory. Verify `bin/win64` includes the PyroWave DLL. Register this ALVR driver through its dashboard and explicitly trust the headset. Use only one active ALVR driver.

```powershell
adb install -r out/android/Quest3-Pyrowave-stable.apk
adb shell am start -n io.github.ljk1291.quest3pyrowave/android.app.NativeActivity
```

SteamVR is the PC OpenXR runtime for Metro's ALVR session. Record the prior runtime before selecting it; retain VD and its registration. Select Quest 3 Touch Plus controller emulation. A terminal decoder fault requires closing/reopening the Quest app; a terminal encoder fault requires fully restarting SteamVR. Repeated faults stop the test sequence.

## Checks and reference build

```powershell
python -m unittest discover -s tests -v
python -m pytest tools/tests/test_ci_pins.py tools/tests/test_build_metadata.py -q
git diff --check
```

CI compiles host policy/decode tests, runs software GLES readback, verifies generated shaders and runs the Rust checks listed in the workflow. Tooling tests alone do not establish native build or headset performance success.

Build the untouched reviewed upstream commit separately and retain its APK/server pair as the reference. Preserve any failed reference run; label any repair separately. Native builds, installation/rollback and sustained hardware qualification are separate gates.

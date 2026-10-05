# NVENC dimension preflight: prepared inactive overlay

Status: **prepared on `codex/nvenc-dimension-preflight-proposal`, inactive by default, not merged, and not included in any build pair.** The source/CPU proof is PR [#56](https://github.com/ljk1291/Quest3-Pyrowave/pull/56), head `9a65d57367a7ee81e2ad7624fe1d5f4e74578b52`; its manual CPU-only CI run [37265993194](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37265993194) passed. That run skipped client, streamer, and matching-pair jobs. It did not compile the Windows native overlay, query a GPU, create a pair, install, or stream.

The verified `80a1635` / `0f07f05` pair remains unchanged. This overlay does not requalify historical artifacts.

## Implemented source scope

`patches/nvenc-dimension-preflight.patch` is lock-pinned in `sources.lock.json` and applied by `tools/ci/fetch_sources.sh` after the existing ALVR overlays. It targets the pinned ALVR source `7eda092dbf0002281410a4222683ec228700cffb`.

It adds `NvencDimensionPolicy.h` and safe capability access in:

- `alvr/server_openvr/cpp/platform/win32/NvEncoder.{h,cpp}`
- `alvr/server_openvr/cpp/platform/win32/VideoEncoderNVENC.cpp`

The check uses the actual `NV_ENC_INITIALIZE_PARAMS::encodeWidth` and `encodeHeight` produced by `FillEncodeConfig()`. It runs after that call and before `CreateEncoder()`. H.264, HEVC, and AV1 map to their existing NVENC GUIDs and query `NV_ENC_CAPS_WIDTH_MAX` and `NV_ENC_CAPS_HEIGHT_MAX`.

`TryGetCapabilityValue()` initializes the output to zero and rejects a null output, absent encoder session or function pointer, and every non-success NVENC result. Validation rejects unknown codecs, non-positive requested dimensions or caps, missing query results, and either cap below the request.

## Activation and default behavior

This supersedes the earlier unconditional proposed hook. The actual hook is strictly opt-in:

```cpp
const char* preflight = std::getenv("ALVR_NVENC_DIMENSION_PREFLIGHT");
if (preflight && std::strcmp(preflight, "1") == 0) {
    std::string reason;
    if (!m_NvNecoder->ValidateEncodeDimensions(initializeParams, &reason)) {
        throw MakeException("NVENC dimension preflight failed: %s", reason.c_str());
    }
    Debug("NVENC dimension preflight passed: %s\\n", reason.c_str());
}
```

When the variable is absent or differs from `1`, this overlay makes no capability query and does not change encoder setup or bitstream handling. When it is `1`, it fails before `CreateEncoder()` if validation fails.

The pass marker is `Warn(...)`. In pinned ALVR `alvr/server_openvr/cpp/alvr_server/Logger.cpp:36-42`, `Warn` always calls `_log(..., LogWarn, true)`: it reaches the ALVR `LogWarn` callback and, when OpenVR has initialized `s_pLogFile`, also calls `DriverLog`. This source path does not prove a particular `vrserver.txt` destination or runtime initialization state. A future native build must still retain the ALVR warning/event evidence and establish actual activation.

## CPU proof and remaining gates

The CPU job runs:

- `tools/tests/test_nvenc_dimension_preflight.py` for source placement, explicit opt-in, fail-closed wiring, and lock/fetch application.
- `tools/nvenc_dimension_preflight_test.cpp` for H.264/HEVC/AV1 acceptance plus width, height, unknown-codec, zero-dimension, missing-query, and invalid-cap rejection.

The historical HVS compatibility proof permits only this exact pair of newly pinned leaves with role `encoder_capability_preflight_inactive_only`. Its tests reject unrelated dependency changes, a PyroWave source pin change, a wrong role, and a wrong hash. Existing historical result metadata was not changed.

Open gates are native Windows compilation, confirmation that the overlay applies to the exact layered source used for a new pair, a read-only capability receipt bound to the active adapter, and live activation evidence. None of those gates is implied by the CPU CI result.
# WO-12: reconstructed stock-codec audit

This is a source audit of the reconstructed Windows ALVR tree, not a hardware
capability, quality, or live-stream result. The authoritative reconstruction is
ALVR `7eda092dbf0002281410a4222683ec228700cffb` plus, in order,
`alvr-20.13.0-server-instrumentation.patch`, `quest3-alvr.patch`,
`stable-baseline-alvr.patch`, and `fork-identity-alvr.patch`, as assembled by
`tools/ci/fetch_sources.sh`. "Available" below means that this source contains
the setting/path; it never means a Quest decoder, GPU, negotiated session, or
elementary stream has been verified.

## Actual Windows NVENC path

`alvr/server_openvr/cpp/alvr_server/Settings.cpp` makes
`m_renderWidth = eye_resolution_width * 2`. `HMD.cpp` exposes the two eyes as
halves of that one side-by-side render target. The Windows NVENC constructor in
`platform/win32/VideoEncoderNVENC.cpp` receives that full width and creates one
`NvEncoderD3D11`; its `Transmit()` submits one texture and calls one
`BitstreamTap::Start(m_codec, m_renderWidth, m_renderHeight)`. There is no
per-eye stream/session identifier, second NVENC instance, or stereo pairing
protocol in this path.

Therefore current stock Windows ALVR is **one side-by-side elementary stream**.
The Q3a two-per-eye H.264 rows are an offline comparison proxy only. They do not
describe a selectable live stock-ALVR mode. WO-11 must first design and then
qualify stream identity, eye pairing, synchronisation, loss recovery and client
presentation before any live dual-stream claim.

## What source proves, and what it does not

| Requested item | Exact reconstructed source evidence | Accurate conclusion |
|---|---|---|
| Codec selection | `alvr/session/src/settings.rs` defines `H264`, `Hevc`, `AV1`, and the fork's `PyroWave`; `alvr/server_core/src/connection.rs` negotiates AV1 against client `encoder_av1` capability and writes the result to `OpenvrConfig`. | H.264, HEVC and AV1 have selectable server paths. AV1 can fall back to HEVC when the client declines it, so negotiated codec/readback is required. |
| Quest 3 capability advertisement | `alvr/client_openxr/src/lib.rs` advertises `encoder_high_profile` and `encoder_10_bits` for non-Unknown platforms, and `encoder_av1` for `Quest3`, `Quest3S`, and `Pico4Ultra`. | This fork's Quest 3 client advertises those capabilities. It is not a decoder-rate or bitstream-depth measurement. |
| H.264 profile on Windows NVENC | `connection.rs` negotiates `h264_profile` and `Settings.cpp` stores it in `m_h264Profile`, but `platform/win32/VideoEncoderNVENC.cpp` never reads `m_h264Profile` or sets an NVENC H.264 profile. The setting is used by the Windows AMF/software paths instead. | The fork does **not** source-prove selection of H.264 High profile on Windows NVENC. Inspect a produced SPS before reporting High profile; do not present the schema setting as an NVENC control. |
| HEVC / AV1 10-bit | `connection.rs` accepts 10-bit only when the advertised client capability permits it, then writes `use_10bit_encoder`. `VideoEncoderNVENC.cpp` selects `ABGR10`/`YUV420_10BIT` and sets HEVC `pixelBitDepthMinus8 = 2` or AV1 `pixelBitDepthMinus8 = 2` when that flag is true. | There is a source path for 10-bit HEVC and AV1. The default session has `server_overrides_use_10bit = true` and `use_10bit = false` in `settings.rs`, so 10-bit is not the default. A live cell must explicitly read back the effective setting and probe the elementary stream and MediaCodec configuration. |
| H.264 depth | In `VideoEncoderNVENC.cpp`, only the HEVC and AV1 codec cases set a 10-bit output bit-depth field. | Treat Windows NVENC H.264 here as an 8-bit candidate unless a future implementation changes and verifies that path. |
| NVENC preset | `settings.rs` defines P1 through P7. `Settings.cpp` forwards `m_nvencQualityPreset`; `VideoEncoderNVENC.cpp::FillEncodeConfig()` maps every value to `NV_ENC_PRESET_P1_GUID` through `P7_GUID` before `CreateDefaultEncoderParams()`. The default is P1. | P4/P7 are real opt-in Windows NVENC controls, requiring a SteamVR restart, not merely Q3 proxy labels. Actual encoder acceptance still needs live logs/bitstream evidence. |
| Adaptive quantization | `settings.rs` defines Disabled/Spatial/Temporal; default is Spatial. `VideoEncoderNVENC.cpp::FillEncodeConfig()` sets `enableAQ` for Spatial or `enableTemporalAQ` for Temporal. | Spatial AQ is a source-backed NVENC option and is default-selected by the session schema. It is not a measured quality improvement; record the applied setting and encoder output in a live cell. |
| Bitrate / rate control | `connection.rs` forwards the session fields. `VideoEncoderNVENC.cpp::FillEncodeConfig()` selects CBR/VBR, sets average/max bitrate, and derives nominal VBV buffer and initial delay from bitrate ÷ refresh rate; hidden NVENC overrides can replace those values. `tools/quest3/control.py` writes `ConstantMbps` in its controlled profile helper. | A requested bitrate is configuration, not achieved payload rate, Wi-Fi goodput, or Quest acceptance. Read the live packet-size/bitstream record per cell. |
| H.264 dimensions | `NvEncoder.cpp` exposes `GetCapabilityValue(..., NV_ENC_CAPS_*)`, but the reconstructed Windows ALVR path does not query `NV_ENC_CAPS_WIDTH_MAX` or a height cap and has no source check enforcing `4096×2048`, `4096×4096`, or any fixed H.264 dimension. `VideoEncoderNVENC.cpp` passes the full side-by-side dimensions to `CreateEncoder()`. | The previous `tools/xrbench/plan.py` `(4096, 2048)` constant is a legacy planning guard, not a stock-ALVR/NVENC source limit. Do not claim any fixed H.264 cap from this repository. A live preflight must query the RTX 5080's H.264 encode caps and fail before `CreateEncoder()` if the negotiated side-by-side dimensions exceed them. |

## Consequences for Q3 and WO-11

* The Q3a offline H.264 dual-eye comparison remains useful for picture quality,
  but cannot establish a deployable stock configuration.
* The live stock-compatible H.264 candidate is one side-by-side stream. Its
  exact width and height must pass a real GPU-capability preflight; `h264fit`
  cannot be described as supported merely because it fits an old planning tuple.
* HEVC/AV1 Main10 candidates need effective `use_10bit_encoder` readback, a
  recorded elementary stream proving 10-bit, and the selected Quest MediaCodec
  before they can be called 10-bit end to end.
* WO-11 is conditional: prototype it only if the ranked Q3 results show that
  per-eye H.264 quality would beat both the best stock H.264-fit and the best
  PyroWave candidate. That comparison decides whether a prototype is warranted;
  prototype qualification then decides whether any live experiment may follow.

## Audit boundary

`tools/xrbench/nvenc_framebank.py` is an offline FFmpeg/NVENC proxy. Its command
line and probes do not configure this ALVR tree, prove its profile selection,
change defaults, or establish Quest decode throughput, fresh submissions,
display FPS, optical latency, Wi-Fi capacity, or live stereo packing.

# Stock H.264 `H264Fit` live-path audit

## Scope and answer

This is a **source-only** audit. It answers whether the reconstructed, fully
patched live path contains a stock Windows NVENC H.264 stream with WO-8
foveated encoding (`H264Fit`). It does not prove that the RTX 5080 accepts a
resolution, that Quest MediaCodec chooses hardware decode, or that a stream is
stable, correct, or performant.

**Answer:** the source has a codec-independent foveated-encoding path and a
stock H.264 path through it. `H264Fit` is therefore a **source-backed live
candidate**, not a PyroWave-only feature. It remains unqualified because the
live path has no NVENC dimension-capability preflight and has no runtime
evidence for Quest H.264 decoder selection, output dimensions, image quality,
or timing. The historical two-H.264-stream work is offline-only; live ALVR
still sends one side-by-side elementary stream.

Line references below are to an isolated reconstruction of the source inputs,
not a mutable shared dependency checkout. It used fork revision
`b495fff52f13ca3845f1adf20080948e7ceb443d`, ALVR
`7eda092dbf0002281410a4222683ec228700cffb` from `sources.lock.json`, and the
patch order in `tools/ci/fetch_sources.sh`:
`alvr-20.13.0-server-instrumentation.patch`, `quest3-alvr.patch`,
`stable-baseline-alvr.patch`, `fork-identity-alvr.patch`, then
`wo8-foveation.patch`. The latter's SHA-256 is
`5300a73dad0ae1092cfd0c0b66b5cb3e1cf689831f02203423ec2ad9f8ab20f4`.

## Forward path: negotiated setting to stock NVENC

| Stage | Exact evidence | Finding |
|---|---|---|
| Quest capability | `alvr/client_openxr/src/lib.rs:409-414` advertises `foveated_encoding` for `Platform::Quest3`, independently of codec. | A matching Quest 3 client can negotiate foveated encoding for H.264 as well as PyroWave. |
| Profile and validation | `alvr/session/src/settings.rs:507-526` defines `H264Fit`; `alvr/server_core/src/connection.rs:139-174` resolves it to centre `0.5`, edge ratio `2.0`, validates the request, and disables malformed configuration. | `H264Fit` is a named, fixed profile rather than a Pyro-only experimental parameter. The switch is default-off (`settings.rs:1966`). |
| Negotiation | `connection.rs:720-736` requires an enabled, valid setting and client capability (or explicit `force_enable`); `:860-890` records the negotiated flag and OpenVR configuration. | The server does not silently enable this profile. The setting requires the documented SteamVR restart (`settings.rs:524-526`). |
| Resolution and compressor | `server_openvr/cpp/platform/win32/FFR.cpp:42-117` derives an aligned optimized side-by-side size; `:151-174` creates the optimized texture and installs the generic compression shader only when `m_enableFoveatedEncoding` is true. `FrameRender.cpp:480-483` replaces the encoder staging texture with that output and `:1105-1109` returns its size. | The compressor operates before codec selection and produces one foveated side-by-side texture. |
| Stock encoder selection | `CEncoder.cpp:61-105` obtains `FrameRender::GetEncodingResolution()`; only the `FrameRender::PyroWaveEnabled()` branch selects PyroWave (`:82-99`). Its normal `Run()` passes `GetTexture()` to the selected encoder (`:180-184`). `FrameRender.cpp:587-590` also makes planar-YUV processing PyroWave-only. | With preferred codec H.264, the regular foveated RGBA staging texture reaches stock NVENC; it does not depend on the PyroWave planar path. |
| NVENC frame and format | `VideoEncoderNVENC.cpp:25-30` uses the normal SDR `ABGR` input unless 10-bit is enabled; `:186-190` selects `NV_ENC_CODEC_H264_GUID`; `:233-234` assigns the full supplied side-by-side width and height to NVENC. Only HEVC and AV1 set `pixelBitDepthMinus8` (`:318-320`, `:356-360`). | Live H.264 remains one 8-bit, side-by-side elementary stream, not a pair of eye streams. |

The forward compression shader is
`server_openvr/cpp/alvr_server/shader/CompressAxisAlignedPixelShader.hlsl:18-27`.
Its eye handling is shader geometry, not a PyroWave condition.

## Reverse path: MediaCodec and foveated compositor

| Stage | Exact evidence | Finding |
|---|---|---|
| Matching negotiated configuration | `client_openxr/src/stream.rs:43-77` accepts foveation only when the server negotiated it; `:203-223` passes it into `StreamRenderer::new`. | A stale local profile cannot make a full-frame stream use inverse foveation. |
| H.264 decode | `client_core/src/video_decoder/mod.rs:359-428` reserves the PyroWave sink/source only for `CodecType::PyroWave`; every other Android codec enters `android::video_decoder_split()` and `MediaCodec`. | H.264 has the normal Android MediaCodec path. Source alone cannot identify the actual selected decoder or prove it is hardware-backed at the candidate dimensions/rate. |
| Inverse map and presentation | `graphics/src/stream.rs:88-104` permits the direct-eye fast path only with *no* foveated configuration; `:162-183` derives foveation staging constants and buffer data, with helpers at `:590-699`. | H.264 with foveation uses the generic compositor/inverse mapping after decode. It does not use the PyroWave direct-eye path. This is functional evidence, not a performance result. |

## Size and the 4096 question

For the WO-10 runtime crop candidate, the per-eye input is `2624 x 2752`.
`FFR.cpp:42-117` uses the profile's centre/edge ratio and rounds each encoded
eye dimension up to 32 pixels. Applying its `H264Fit` values (`0.5`, `2.0`)
gives the following expected geometry:

| Item | Per eye | Side-by-side stream |
|---|---:|---:|
| Input after the runtime FOV crop | 2624 x 2752 | 5248 x 2752 render target |
| Calculated `H264Fit` output | 1984 x 2080 | **3968 x 2080** |

This is a calculation from source; it is not negotiated or live readback. It
must not be substituted with the offline `2624 x 2776` geometry.

`tools/nvenc_caps/README.md:8-20` records a prior probe with a H.264
`WIDTH_MAX` and `HEIGHT_MAX` of 4096. That documentation is useful caution,
but it is not a current RTX 5080 capability result. More importantly, the live
ALVR path does not query either limit: `NvEncoder.cpp:163` only queries async
encode support, even though `GetCapabilityValue()` exists at `:949`; there is
no `NV_ENC_CAPS_WIDTH_MAX` or `NV_ENC_CAPS_HEIGHT_MAX` use in the Windows
encoder tree. `3968` therefore fits the *recorded* 4096-width value but has no
source-enforced or current-device preflight. The same conclusion is recorded
in `docs/WO-12-STOCK-CODEC-AUDIT.md:41`.

## Stock AV1 Main10 / 200 Mbps / P1 / Spatial AQ claim

The proposed tuple is configurable in source, but it is **not the stock default
bundle**. The Q3 offline P4/P7/AQ-off rows are FFmpeg frame-bank settings; they
neither alter nor establish live ALVR defaults.

| Requested part | Source state | Accurate statement |
|---|---|---|
| AV1 | `settings.rs:1850-1852` defaults preferred codec to PyroWave. If AV1 is requested, `connection.rs:800-813` falls back to HEVC when the client does not advertise AV1. | AV1 is an explicit candidate and needs negotiated-codec readback. |
| Main10 | `settings.rs:1884-1885` defaults `use_10bit` to false; `connection.rs:755-767` only enables it when requested and advertised. `VideoEncoderNVENC.cpp:343-360` sets AV1 10-bit output only with that effective flag. | AV1 Main10 is opt-in, not default. It needs an elementary-stream and MediaCodec confirmation. |
| 200 Mbps | The constant-rate control schema allows 5--2000 Mbps (`settings.rs:406-408`), but its default is 400 Mbps (`:1804-1839`). | 200 Mbps is a requested test value, not a stock default or achieved throughput. |
| P1 | `settings.rs:1894-1897` defaults NVENC quality preset to P1; the Windows mapping is in `VideoEncoderNVENC.cpp:201-223`. | P1 is source-default, subject to applied-setting/encoder confirmation. |
| Spatial AQ | `settings.rs:1905-1906` defaults Spatial; `VideoEncoderNVENC.cpp:411-416` sets `enableAQ` for Spatial. | Spatial AQ is source-default, but its image/timing effect is unmeasured. |

For H.264 specifically, do not claim Windows NVENC High profile from the
session setting: `Settings.cpp:73` stores `m_h264Profile`, but
`VideoEncoderNVENC.cpp` does not read it or set an H.264 NVENC profile GUID.
That needs SPS inspection, as already documented in
`docs/WO-12-STOCK-CODEC-AUDIT.md:35`.

## Missing live gates

Before this candidate can be called usable, the implementation needs evidence
that is absent from this audit:

1. A current-device H.264 width/height capability preflight before encoder
   creation, or an equally concrete NVENC acceptance record for `3968 x 2080`.
2. A recorded negotiated profile, codec, foveation flag, source and encoded
   dimensions, plus an H.264 SPS/profile check.
3. Quest MediaCodec identity/output confirmation and image-correctness checks
   for the inverse mapping, including eye assignment, range/colour and
   peripheral behaviour.
4. Controlled live freshness, decoder/compositor timing and endurance evidence.

Until those gates exist, `H264Fit` should be presented as a **single-stream,
source-backed stock H.264 candidate**. It is neither a PyroWave-only feature
nor a qualified replacement for the current baseline.

# WO-12: stock-codec audit

This is a source audit, not a hardware-capability or quality result. It describes
the reconstructed ALVR tree assembled by `tools/ci/fetch_sources.sh`: ALVR
`7eda092dbf0002281410a4222683ec228700cffb`, followed by
`alvr-20.13.0-server-instrumentation.patch`, `quest3-alvr.patch`,
`stable-baseline-alvr.patch`, and `fork-identity-alvr.patch`. No FFmpeg frame-bank
proxy result is evidence of a live ALVR encoder setting or Quest decoder result.

## What the fork exposes today

| Item | Source evidence | Status / limit |
|---|---|---|
| Codec selection | `tools/quest3/control.py` accepts `H264`, `Hevc`, `AV1`, and `PyroWave`; `patches/quest3-alvr.patch` keeps all four visible variants | Configurable. A selected value still needs server and client readback during a live cell. |
| H.264 profile | ALVR session schema keeps `h264_profile`; `patches/quest3-alvr.patch` changes the platform capability for high profile | High profile is an available candidate. The final NVENC profile/level must be reported by the actual encoder. |
| HEVC / AV1 bit depth | ALVR codec choice exists in the packet/client MediaCodec paths (`patches/alvr-20.13.0-server-instrumentation.patch`) | Q3 calls for Main10 / AV1 10-bit, but this fork has no source-only proof that every requested driver setting produces a 10-bit stream. Verify stream metadata and Quest MediaCodec selection per cell. |
| NVENC preset | ALVR schema exposes `video.encoder_config.nvenc.quality_preset`; `tools/quest3/control.py` deliberately does not set it | P4 and P7 are opt-in Q3 candidates, not current defaults or measured live selections. |
| Adaptive quantization | ALVR schema exposes `adaptive_quantization_mode` (`patches/alvr-20.13.0-server-instrumentation.patch`) | Spatial AQ is a distinct H.264 Q3 candidate. It must be read back and logged; no claim that it is currently enabled. |
| Bitrate | `tools/quest3/control.py` writes `ConstantMbps`, checks 1–2000 Mbps, and disables dynamic bitrate | This is a requested payload cap. It does not establish achieved bitrate, Wi-Fi goodput, or decoder acceptance. Owner-planned decoder caps are 200 Mbps for HEVC/AV1 and about 700 Mbps for H.264, pending live verification. |
| Eye packing | `patches/quest3-alvr.patch` passes one encoded render width (`encoderInfo.width = m_renderWidth`) and the current source has no per-eye stream/session identity | Stock ALVR is one encoded stereo stream. The Q3 H.264 crop uses one 3968-wide stream; full-density per-eye H.264 needs WO-11 design/implementation. |
| H.264 4096 check | `docs/ARTIFACT-QUALITY-PLAN.md` §2; `tools/xrbench/plan.py` `NVENC_H264_LIMIT = (4096, 2048)` and `fits_limit()` | Treat 4096 pixels per encoded-stream side as a hard preflight check. Stock side-by-side H.264 is therefore at most 2048 pixels per eye horizontally; `h264fit` at 1984×2112 is within it. |

## Q3 implications

All entries are candidates until Q3 scores, encoder metadata, negotiated client
configuration, and live decode evidence exist.

| Q3 candidate | What it needs beyond the current source | What would disqualify it |
|---|---|---|
| H.264 crop, two per-eye streams, 400/700 Mbps, P7/P4/AQ | WO-11 implementation: two independently identified streams, synchronized stereo presentation, per-stream 4096 preflight | Any missing eye/frame identity, desynchronization, loss recovery ambiguity, or unverified NVENC profile/preset/AQ. |
| H.264-fit, one stream, 700 Mbps, P7 | Stock single-stream H.264, crop/foveation work, 3968×2112 preflight | Width/height fails the encoder check, negotiated format differs, or Quest decoder cannot sustain it. |
| HEVC Main10, one stream, 200 Mbps, P7/P4 | Proven 10-bit elementary stream and Quest MediaCodec configuration | Any fallback to 8-bit/another codec, metadata omission, or decoder-rate failure. |
| AV1 10-bit, one stream, 200 Mbps, P7/P4 | Same 10-bit and negotiated-path evidence | Same failure modes; Q3a does not authorize higher bitrate cells. |
| PyroWave crop, 5/3 or 9/7, 800/1000 Mbps | Q3 frame-bank quality plus later live decoder/network evidence | Offline quality is insufficient for fresh-rate or presentation claims. |

## Audit boundary

The prior NVENC frame-bank adapter uses FFmpeg 6.1 (`tools/xrbench/nvenc_framebank.py`)
as an offline bitstream proxy. It records its own command line and output metadata;
it neither configures ALVR nor demonstrates stock ALVR eye packing, NVENC presets,
AQ, encoder profile, or Quest hardware decode. This document makes no default change.

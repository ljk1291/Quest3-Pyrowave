# NVENC offline frame bank

`tools/xrbench/nvenc_framebank.py` compares NVENC HEVC and AV1 with PyroWave
on the same frozen 90-frame stereo Y4M input. It is an **offline encode proxy**:
it does not configure ALVR, connect a Quest, or establish Quest hardware-decoder
throughput, fresh submissions, display FPS, or optical latency.

The planned Q3 matrix is HEVC and AV1 at 200, 500, 800 and 1000 Mbps, each at
3072x3232 and 2560x2688 per eye. It uses the source hash, frame order, per-eye
Lanczos display normalization, four frozen crops, and calibrated PSNR-HVS-M-H
from the PyroWave frame bank. A report must keep Q3 results distinct from a
verified live ALVR configuration.

## Profile

Every cell is CBR, `p4`, `ull`, 90 fps, one 90-frame GOP, no B frames, no
lookahead, no multipass, zero-latency mode, zero output delay and strict GOP.
The requested target, minrate and maxrate are identical. VBV is
`ceil(1.1 * rate_bits_per_second / 90)` bits, matching ALVR's approximately
one-frame low-delay buffer. The frame bank records the complete FFmpeg argument
vector, requested rate and VBV, the actual elementary-stream bytes and achieved
Mbps normalized to the external 90-frame/F90 sequence; it never uses raw
bitstream timing as proof of 90 Hz. NVENC's CBR padding policy is
backend-dependent (FFmpeg 6.1 AV1 enables bitstream padding); actual elementary
stream bytes include any padding and are measured rather than assumed.

This is deliberately an ALVR-like low-delay profile, not a claim that ALVR has
these exact settings. `p4` is a fixed proxy point from ALVR's selectable P1--P7
range. A live comparison must capture ALVR's negotiated encoder configuration
independently.

The implementation targets the locally recorded FFmpeg 6.1 NVENC option set:
`hevc_nvenc` and `av1_nvenc` accept `p4`, `ull`, `cbr`, `-bf 0`,
`-rc-lookahead 0`, `-zerolatency 1`, `-delay 0`, `-strict_gop 1`, `-ldkfs 1`
and `-multipass disabled`. The source-plane contract is full-range JPEG-sited
4:2:0. BT.709 matrix/primaries and sRGB (`iec61966-2-1`) transfer are an SDR
proxy assumption taken from the reconstructed ALVR encoder, not a claim that
the raw bitstream carries those fields. If a future FFmpeg or driver rejects an
option, the cell fails; it never changes settings silently.
FFmpeg 6.1 uses the raw `hevc` muxer for HEVC and the raw `obu` muxer for AV1.

## Fail-closed checks

Before decode, `ffprobe` must confirm one stream with the requested codec,
stereo geometry, native 8-bit planar 4:2:0, exactly 90 decoded frames and only I/P
pictures. Every decoded-frame record must carry the same geometry and native
format. Raw HEVC/OBU output commonly has unknown chroma location, colour range
or `0/0` timing. Those are retained as observed metadata and never relabelled
as centre/full/90 Hz. A known limited-range or conflicting colour signal fails.

Decode writes raw planes with `-pix_fmt +<observed-native-format>`, which makes
FFmpeg reject a format conversion, and `-fps_mode passthrough`, which prevents
timing-derived duplication or dropping. The only allowed formats are `yuv420p`
and `yuvj420p`; the latter is FFmpeg's full-range 8-bit 4:2:0 alias. Every
decoded frame must have the same observed native format. The runner verifies the
exact raw byte count and hashes each frame, then wraps those byte-identical planes
in a Y4M header taken from the
frozen `C420jpeg`/FULL source contract for the quality scorer. The source's
external F90 sequence rate is recorded separately from bitstream timing.
This proves a reconstruction-quality proxy. Missing or mismatched presentation
metadata means it is not ready to establish live presentation equivalence.

Raw bitstreams, decoded frames, FFmpeg logs, private grids and source identities
remain under `results/local`. The public report includes aggregate scores,
bitstream metadata, command profile, tool hashes and the frozen-plan hash only.

## Invocation

Create a frozen plan with the same projection and crop evidence used by the
PyroWave plan:

```powershell
python -m tools.xrbench.nvenc_framebank plan --source results/local/session-09/metro.y4m `
  --vertical-pixels-per-degree 23.56428154212911 --projection-evidence session-07 `
  --crop-evidence metro-session-09 --crops @results/local/session-09/crops.json `
  --out results/local/session-09/nvenc-plan.json
```

Run only during an owner-supervised `frame_bank_pc` lease. `--supervised` is
required, and each FFmpeg, FFprobe and HVS child is registered with the lease:

```powershell
python -m tools.xrbench.nvenc_framebank run --supervised `
  --plan results/local/session-09/nvenc-plan.json --source results/local/session-09/metro.y4m `
  --private-out results/local/session-09/nvenc-q3 --report results/nvenc-q3.json `
  --window results/local/supervised/nvenc-q3 --ffmpeg <ffmpeg.exe> `
  --ffprobe <ffprobe.exe> --psnr-hvs-m-h <pyrowave-psnr-hvs-m.exe> `
  --tools-metadata <FRAMEBANK-TOOLS-BUILD-METADATA.json>
```

The runner performs the same HVS sanity gate before any NVENC cell. No encode or
decode runs merely by creating a plan. It verifies the existing qualified
frame-bank tool bundle before and after the run and binds the selected HVS scorer
to that bundle. The frozen source must already be `C420jpeg` and full range;
the adapter rejects C420mpeg2, limited/unknown range and non-4:2:0 sources before
starting the encoder.

## Source references and validation scope

The profile was reconciled with the pinned ALVR
[`VideoEncoderNVENC.cpp`](https://github.com/alvr-org/ALVR/blob/7eda092dbf0002281410a4222683ec228700cffb/alvr/server_openvr/cpp/platform/win32/VideoEncoderNVENC.cpp),
the reconstructed fork's corresponding encoder and
[FFmpeg 6.1 NVENC implementation](https://github.com/FFmpeg/FFmpeg/blob/n6.1/libavcodec/nvenc.c).
This adapter invokes installed tools and reuses this repository's scorer; it does
not copy encoder or decoder implementation code from either project.

CPU tests cover frozen calibration order, metadata contradictions, native format
aliases, exact payload wrapping and a mocked end-to-end run. A tiny local FFmpeg
6.1 software HEVC fixture also confirmed the full-range `yuvj420p` case. These
checks do not qualify NVENC capabilities at the planned resolutions/bitrates;
the Q3 hardware matrix must report capability failures and actual output rates.

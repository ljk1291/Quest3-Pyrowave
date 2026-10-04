# Q3 extension frame-bank quality review

This frame-bank quality review contains 32 measured rows: 30 cropped/reconstructed-domain rows in the main tight-fence ordering and two historical full-FOV reference rows shown separately. Main rows rank the fixed tight fence on frames 10–89 by edge PSNR-Y descending, temporal p99 ascending, temporal mean ascending, then HVS only for an exact fence tie. Requested rate is a cap; Pyro payload rate is measured from all 90 native container payloads, and is not network goodput. These are offline image-quality metrics: they do not establish GPU execution timing, fresh-submission rate, display FPS, optical latency, Wi-Fi throughput, or Quest decode feasibility.

All retained dual-eye H.264 rows are offline NVENC proxies; stock ALVR has no runnable dual-eye H.264 transport. Their F90-normalized elementary-stream rates are fixed-sequence rate accounting, not display FPS, optical frame rate, or Wi-Fi throughput. The frozen 90-file-order-frame capture has 89 distinct payloads and irregular original display timestamps, so temporal residuals are sequence-reconstruction error rather than optical shimmer or fresh-90-Hz evidence.

## Main cropped/reconstructed-domain fence review

| Rank | Codec / profile | Requested total Mbps | Actual Pyro payload Mbps (90 frames) | Fence edge dB (10–89) | Temporal p99 (8-bit luma codes) | Temporal mean (8-bit luma codes) | HVS all-90 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | NVENC H.264 H264Fit / P7 / 700 Mbps | 700 | — | 47.837 | 4.000 | 0.908 | 36.976 |
| 2 | NVENC H.264 dual-eye offline proxy (not runnable in stock ALVR) / P4 / 700 Mbps | 700 | — | 47.033 | 4.000 | 1.087 | 47.667 |
| 3 | NVENC H.264 dual-eye offline proxy (not runnable in stock ALVR) / P7 / 700 Mbps | 700 | — | 46.923 | 4.000 | 1.097 | 47.755 |
| 4 | NVENC AV1 Main10 / P7 / 200 Mbps | 200 | — | 43.747 | 8.000 | 1.418 | 43.964 |
| 5 | NVENC H.264 dual-eye offline proxy (not runnable in stock ALVR) / P7 / 400 Mbps | 400 | — | 43.746 | 7.000 | 1.558 | 45.090 |
| 6 | NVENC H.264 dual-eye offline proxy (not runnable in stock ALVR) / P7 / 700 Mbps + spatial AQ | 700 | — | 43.477 | 7.000 | 1.586 | 47.563 |
| 7 | NVENC AV1 Main10 / P4 / 200 Mbps | 200 | — | 42.998 | 9.000 | 1.522 | 43.347 |
| 8 | NVENC AV1 Main10 / P1 + spatial AQ / 200 Mbps | 200 | — | 42.620 | 9.000 | 1.600 | 43.103 |
| 9 | PyroWave 9/7 / Medium s=0.5 / RDO 24 ppd / 1000 Mbps | 1000 | 999.955 | 42.413 | 9.000 | 1.355 | 37.356 |
| 10 | NVENC HEVC Main10 / P4 / 200 Mbps | 200 | — | 41.236 | 10.000 | 1.927 | 42.672 |
| 11 | NVENC HEVC Main10 / P7 / 200 Mbps | 200 | — | 41.075 | 10.000 | 1.951 | 42.738 |
| 12 | PyroWave 9/7 / 1000 Mbps / RDO 24 ppd | 1000 | 999.961 | 39.933 | 12.000 | 1.820 | 43.009 |
| 13 | PyroWave 9/7 / 1000 Mbps / RDO 36 ppd | 1000 | 999.962 | 39.504 | 13.000 | 2.035 | 42.599 |
| 14 | PyroWave CDF 9/7 / 2000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 2000 | 1999.954 | 39.503 | 13.000 | 2.038 | 45.044 |
| 15 | PyroWave CDF 9/7 / H264Fit s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.962 | 38.368 | 14.000 | 2.371 | 35.755 |
| 16 | PyroWave CDF 9/7 / 1500 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1500 | 1499.956 | 37.852 | 15.000 | 2.524 | 42.998 |
| 17 | PyroWave CDF 9/7 / Medium s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.952 | 37.543 | 15.320 | 2.605 | 36.262 |
| 18 | PyroWave 9/7 / Light s=0.5 / phase-fixed / 1000 Mbps | 1000 | 999.950 | 36.525 | 17.000 | 3.012 | 38.711 |
| 19 | PyroWave Haar / 2000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 2000 | 1999.960 | 36.241 | 16.000 | 3.108 | 41.589 |
| 20 | PyroWave CDF 5/3 / Medium s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.956 | 36.151 | 18.000 | 2.890 | 36.013 |
| 21 | PyroWave CDF 9/7 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.956 | 35.754 | 19.000 | 3.300 | 39.905 |
| 22 | PyroWave CDF 9/7 / Light blur-only s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.959 | 35.742 | 19.000 | 3.294 | 39.640 |
| 23 | PyroWave CDF 5/3 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.954 | 34.288 | 22.000 | 3.703 | 39.166 |
| 24 | PyroWave CDF 9/7 / 800 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 800 | 799.951 | 34.267 | 22.000 | 3.974 | 38.658 |
| 25 | PyroWave CDF 5/3 / 800 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 800 | 799.955 | 32.961 | 25.000 | 4.455 | 37.890 |
| 26 | PyroWave CDF 9/7 / Light s=1 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) / historical transform | 1000 | 999.955 | 30.833 | 32.000 | 5.327 | 37.392 |
| 27 | PyroWave CDF 9/7 / Light s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) / historical transform | 1000 | 999.957 | 30.833 | 32.000 | 5.328 | 37.741 |
| 28 | PyroWave CDF 9/7 / Light s=0 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) / historical transform | 1000 | 999.954 | 30.832 | 32.000 | 5.330 | 38.111 |
| 29 | PyroWave Haar / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.954 | 30.518 | 29.000 | 5.695 | 36.304 |
| 30 | PyroWave CDF 5/3 / Light s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) / historical transform | 1000 | 999.951 | 30.452 | 33.000 | 5.615 | 37.286 |

## Historical full-FOV references

These two rows use the same native tight-fence source region, but their whole-image HVS domain differs from cropped/reconstructed rows. They are contextual references and are excluded from the main 30-row ordering.

| Profile | Tight-fence edge PSNR-Y (10–89) | Temporal p99 (8-bit luma codes) | Temporal mean (8-bit luma codes) | All-90 HVS |
|---|---:|---:|---:|---:|
| NVENC H.264 dual-eye offline proxy (not runnable in stock ALVR) / P7 / 700 Mbps | 45.815 | 5.000 | 1.248 | 46.823 |
| NVENC HEVC Main10 / P7 / 200 Mbps | 40.241 | 11.000 | 2.186 | 41.962 |

Scope note: the planned blur-only Light / dual-H.264 row was dropped because PyroWave blur-only did not show a meaningful fence gain and stock ALVR has no dual-eye H.264 transport. This is not a claimed measured H.264 blur-only failure.

## RDO density comparison

The default-density 9/7 baseline and RDO 24/36 ppd rows share the requested 1000 Mbps rate. Values remain offline frame-bank evidence.

| Profile | Tight-fence edge PSNR-Y (10–89) | Temporal p99 (8-bit luma codes) | Temporal mean (8-bit luma codes) | All-90 HVS |
|---|---:|---:|---:|---:|
| PyroWave 9/7 / 1000 Mbps / RDO 24 ppd | 39.933 | 12.000 | 1.820 | 43.009 |
| PyroWave 9/7 / 1000 Mbps / RDO 36 ppd | 39.504 | 13.000 | 2.035 | 42.599 |
| PyroWave CDF 9/7 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 35.754 | 19.000 | 3.300 | 39.905 |

## Medium 9/7 default versus RDO-24

These two rows are compared only after the publisher verifies identical reduced codec-input file and frame-identity hashes. Centre/peripheral domains remain diagnostics unless their descriptors also match.

| Profile | Tight-fence edge PSNR-Y (10–89) | Temporal p99 (8-bit luma codes) | Temporal mean (8-bit luma codes) | All-90 HVS |
|---|---:|---:|---:|---:|
| PyroWave 9/7 / Medium s=0.5 / RDO 24 ppd / 1000 Mbps | 42.413 | 9.000 | 1.355 | 37.356 |
| PyroWave CDF 9/7 / Medium s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 37.543 | 15.320 | 2.605 | 36.262 |

## Light s=0.5 historical versus phase-fixed

The phase-fixed Light row has a distinct transform implementation identity. This is an implementation comparison, not a codec/profile gain claim.

| Profile | Tight-fence edge PSNR-Y (10–89) | Temporal p99 (8-bit luma codes) | Temporal mean (8-bit luma codes) | All-90 HVS |
|---|---:|---:|---:|---:|
| PyroWave 9/7 / Light s=0.5 / phase-fixed / 1000 Mbps | 36.525 | 17.000 | 3.012 | 38.711 |
| PyroWave CDF 9/7 / Light s=0.5 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) / historical transform | 30.833 | 32.000 | 5.328 | 37.741 |

## AV1 Main10 preset/AQ comparison

This compares the owner-added P1 + spatial-AQ control against retained P4/P7 controls at 200 Mbps.
The offline P1 control explicitly used FFmpeg AQ strength 8. The reviewed live ALVR path selects P1 and enables Spatial AQ, but does not assign NVENC `aqStrength`; its live strength is preset/driver-defined unless a config readback proves it. This is not a live strength-8 claim.

| Profile | Tight-fence edge PSNR-Y (10–89) | Temporal p99 (8-bit luma codes) | Temporal mean (8-bit luma codes) | All-90 HVS |
|---|---:|---:|---:|---:|
| NVENC AV1 Main10 / P7 / 200 Mbps | 43.747 | 8.000 | 1.418 | 43.964 |
| NVENC AV1 Main10 / P4 / 200 Mbps | 42.998 | 9.000 | 1.522 | 43.347 |
| NVENC AV1 Main10 / P1 + spatial AQ / 200 Mbps | 42.620 | 9.000 | 1.600 | 43.103 |

## High-rate default-RDO 9/7 analysis

The following is a descriptive fit of tight-fence edge PSNR-Y (10–89) against log2 of requested total video Mbps. It is not a Wi-Fi goodput, decoder-feasibility, or confidence estimate.

- 800→1000 Mbps: 1.487 dB (4.618 dB per doubling).
- 1000→1500 Mbps: 2.098 dB (3.587 dB per doubling).
- 1500→2000 Mbps: 1.651 dB (3.978 dB per doubling).
- Fitted rate for the retained H.264 dual-eye P4/700 target (47.032668 dB): 7628.7 Mbps; extrapolated: True.

Fit sensitivity (each is an offline descriptive fit; an estimate outside that fit's measured interval is explicitly extrapolated):
- `all_four` (800.0–2000.0 Mbps): 3.895 dB/doubling; target 7628.7 Mbps; extrapolated: True.
- `1000_to_2000` (1000.0–2000.0 Mbps): 3.749 dB/doubling; target 8045.7 Mbps; extrapolated: True.
- `highest_interval_1500_to_2000` (1500.0–2000.0 Mbps): 3.978 dB/doubling; target 7426.6 Mbps; extrapolated: True.

## Default-RDO high-rate sweep

The 1500 and 2000 Mbps rows are offline-only and above measured Wi-Fi capacity. Requested caps and measured container payload rates are shown separately; neither is network goodput.

| Profile | Requested total Mbps | Actual payload Mbps (90 frames) | Fence edge PSNR-Y (10–89) | Temporal p99 (8-bit luma codes) | All-90 HVS |
|---|---:|---:|---:|---:|---:|
| PyroWave CDF 9/7 / 800 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 800 | 799.951 | 34.267 | 22.000 | 38.658 |
| PyroWave CDF 9/7 / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.956 | 35.754 | 19.000 | 39.905 |
| PyroWave CDF 9/7 / 1500 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1500 | 1499.956 | 37.852 | 15.000 | 42.998 |
| PyroWave CDF 9/7 / 2000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 2000 | 1999.954 | 39.503 | 13.000 | 45.044 |
| PyroWave Haar / 1000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 1000 | 999.954 | 30.518 | 29.000 | 36.304 |
| PyroWave Haar / 2000 Mbps / default RDO (65.28 px/deg, legacy 96 dpi @ 1 m) | 2000 | 1999.960 | 36.241 | 16.000 | 41.589 |

Centre and peripheral results remain profile/transform diagnostics. They are not matched-domain gains unless their retained rectangle and descriptor are exactly equal. Historical Light and phase-corrected Light results remain distinct transform implementations. High-rate rows are offline-only and do not demonstrate Wi-Fi transport or Quest decode feasibility.

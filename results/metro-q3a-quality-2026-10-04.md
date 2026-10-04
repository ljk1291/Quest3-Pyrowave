# Q3a offline quality results

This is a public-ready **Q3a-only** offline image-quality report: ten qualified NVENC proxy rows and five cropped PyroWave rows. Q3b foveated rows are still running and are excluded. The final 25-row combined publication remains required.

The reports use the same immutable parent/crop corpus, projection and scorer. Each accepted report records a clean closure with zero owned jobs and no cleanup errors. Both 1–90 and 10–89 score windows, all crop metrics and exclusions remain in the companion JSON; the table uses the prescribed trimmed 10–89 tight-fence ranking.

Rows are ordered lexicographically by tight-fence edge PSNR-Y descending, then temporal residual p99 and mean ascending. HVS and VMAF are all-90 secondary/context metrics. PSNR-Y and HVS are dB; temporal values are 8-bit luma-code errors, not latency or optical metrics. The [companion JSON](metro-q3a-quality-2026-10-04.json) retains both windows, crop metrics, exclusions and safe provenance.

| Fence rank | Codec / profile | Encoded eye | Score domain | Requested total Mbps | Observed total Mbps | Edge PSNR-Y 10–89 | Temporal p99 | Temporal mean | Reconstructed HVS 1–90 | VMAF 1–90 |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | h264-dual-p4-700 | 2624×2776 | cropped | 700 | 700.000096 | 47.033 | 4.000 | 1.087 | 47.667 | 99.462 |
| 2 | h264-dual-p7-700 | 2624×2776 | cropped | 700 | 700.000096 | 46.923 | 4.000 | 1.097 | 47.755 | 99.468 |
| 3 | h264-dual-p7-700-full | 3072×3232 | full FOV (contextual whole-image) | 700 | 700.000096 | 45.815 | 5.000 | 1.248 | 46.823 | 99.450 |
| 4 | av1-main10-p7-200 | 2624×2776 | cropped | 200 | 201.025240 | 43.747 | 8.000 | 1.418 | 43.964 | 99.541 |
| 5 | h264-dual-p7-400 | 2624×2776 | cropped | 400 | 400.000096 | 43.746 | 7.000 | 1.558 | 45.090 | 99.313 |
| 6 | h264-dual-p7-aq-700 | 2624×2776 | cropped | 700 | 700.000096 | 43.477 | 7.000 | 1.586 | 47.563 | 99.346 |
| 7 | av1-main10-p4-200 | 2624×2776 | cropped | 200 | 201.141152 | 42.998 | 9.000 | 1.522 | 43.347 | 99.534 |
| 8 | hevc-main10-p4-200 | 2624×2776 | cropped | 200 | 181.861840 | 41.236 | 10.000 | 1.927 | 42.672 | 99.281 |
| 9 | hevc-main10-p7-200 | 2624×2776 | cropped | 200 | 180.895784 | 41.075 | 10.000 | 1.951 | 42.738 | 99.242 |
| 10 | hevc-main10-p7-200-full | 3072×3232 | full FOV (contextual whole-image) | 200 | 179.810256 | 40.241 | 11.000 | 2.186 | 41.962 | 99.079 |
| 11 | PyroWave 97 | 2624×2776 | cropped | 1000 | 999.955616 | 35.754 | 19.000 | 3.300 | 39.905 | 99.271 |
| 12 | PyroWave 53 | 2624×2776 | cropped | 1000 | 999.954240 | 34.288 | 22.000 | 3.703 | 39.166 | 99.127 |
| 13 | PyroWave 97 | 2624×2776 | cropped | 800 | 799.950560 | 34.267 | 22.000 | 3.974 | 38.658 | 99.139 |
| 14 | PyroWave 53 | 2624×2776 | cropped | 800 | 799.955424 | 32.961 | 25.000 | 4.455 | 37.890 | 98.936 |
| 15 | PyroWave haar | 2624×2776 | cropped | 1000 | 999.953600 | 30.518 | 29.000 | 5.695 | 36.304 | 97.852 |

## Scope and interpretation

Dual-eye H.264/700/P4 leads the tight fence; that transport is an offline proxy and is not implemented in ALVR. Among tested single-stream stock codecs, AV1 Main10/P7/200 leads. CDF 9/7/1000 is the best cropped PyroWave row. These are candidates for later runtime checks, not promoted defaults.

- H.264 rows use the retained offline NVENC **dual-eye proxy**. They do not establish a live ALVR dual-stream implementation, Quest decode behavior, or headset performance.
- Full-FOV H.264/HEVC rows use the same native tight-fence source region, but their whole-image HVS/VMAF covers a different domain from cropped rows. Do not read that whole-image difference as a matched-domain gain.
- Requested rate is total across both eyes where H.264 is dual-eye. Observed NVENC rate is elementary-stream bytes normalized at an external 90 fps (90 frames treated as one second for byte-rate accounting only); observed PyroWave rate is packet payload over 90 frames.
- HEVC/AV1 Main10 rows encode from `p010le`; the observed decoder format is planar `yuv420p10le`, followed by the documented full-range conversion to 8-bit scoring input. HEVC retains Annex-B initial-IDR proof; AV1 retains its explicit initial-key-frame proxy because AV1 has no IDR NAL. H.264 retains equivalent per-eye stream evidence.
- The frozen capture has 89 distinct payloads in 90 file-order frames and irregular original display timestamps. Temporal metrics therefore describe sequence reconstruction error, not optical shimmer or fresh-90-Hz evidence.
- This Q3a publication makes no decoder-execution, completion-latency, fresh-submission, display-FPS, optical-latency, or 90 Hz stability claim. Those require the later supervised runtime work.

## Reused full-FOV PyroWave reference

The retained three-row full-FOV PyroWave backfill is separate from Q3a ranking. It has the same parent source, tight fence, two fence windows, scorer and vertical HVS calibration, but only an all-90 HVS value; it is not a cropped Q3a matched-domain row.

| Wavelet | Mbps | Edge PSNR-Y 10–89 | Temporal p99 | Temporal mean | HVS 1–90 |
|---|---:|---:|---:|---:|---:|
| 97 | 1000 | 34.583 | 21.000 | 3.883 | 39.342 |
| 53 | 1000 | 33.286 | 24.000 | 4.330 | 38.583 |
| haar | 500 | 26.117 | 44.000 | 9.707 | 33.090 |


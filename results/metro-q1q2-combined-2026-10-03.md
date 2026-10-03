# Metro Q1/Q2 combined offline quality

All rows use the same 90 frozen source frames, SDR 8-bit 4:2:0, Compute and a common display size of 3072×3232 per eye. HVS is calibrated PSNR-HVS-M-H and is the primary ranking metric; higher is better. `cap fill` is the actual `.wave` container size divided by the 90-frame cap budget, retained as an observed container ratio. Crop comparisons always use the same encoded geometry as their reference.

Reduced-size rows use per-eye Lanczos down/upscaling, which is optimistic relative to the current live sampling path. The source contains tunnel and later menu frames, 89 distinct frame payloads and irregular original display timestamps; file order is preserved. These scores describe this capture, and the nominal F90 sequence does not prove fresh 90 Hz operation. Wavelet `53` means CDF 5/3; `97` means CDF 9/7.

Full-size CDF 9/7 at 1000 Mbps leads this quality screen. CDF 5/3 at 1000 Mbps improves both metrics on every fixed crop over Haar at the same bitrate and geometry, satisfying its offline quality prerequisite for further investigation. The next codec comparison is the separately implemented NVENC HEVC/AV1 path; it has no GPU results in this table. No default or installed build is promoted.

| HVS rank | Wavelet | Mbps | Encoded pixels/eye | Display HVS dB | Display VMAF | Cap fill | Crops improve vs Haar 1000 (same size) |
|---:|---|---:|---:|---:|---:|---:|---:|
| 11 | 53 | 500 | 3072×3232 | 35.881 | 96.806 | 0.9999 | 1/4 |
| 15 | 53 | 500 | 2560×2688 | 35.243 | 95.378 | 0.9999 | 0/4 |
| 10 | 97 | 500 | 3072×3232 | 36.432 | 97.795 | 0.9999 | 3/4 |
| 12 | 97 | 500 | 2560×2688 | 35.671 | 96.959 | 0.9999 | 2/4 |
| 18 | haar | 500 | 3072×3232 | 33.090 | 88.823 | 0.9999 | 0/4 |
| 17 | haar | 500 | 2560×2688 | 33.536 | 90.871 | 0.9999 | 0/4 |
| 6 | 53 | 800 | 3072×3232 | 37.554 | 98.485 | 1.0000 | 4/4 |
| 9 | 53 | 800 | 2560×2688 | 36.901 | 97.817 | 0.9999 | 2/4 |
| 4 | 97 | 800 | 3072×3232 | 38.209 | 98.867 | 1.0000 | 4/4 |
| 7 | 97 | 800 | 2560×2688 | 37.440 | 98.398 | 0.9999 | 3/4 |
| 16 | haar | 800 | 3072×3232 | 34.577 | 94.643 | 0.9999 | 0/4 |
| 14 | haar | 800 | 2560×2688 | 35.265 | 95.940 | 0.9999 | 0/4 |
| 3 | 53 | 1000 | 3072×3232 | 38.583 | 98.946 | 1.0000 | 4/4 |
| 5 | 53 | 1000 | 2560×2688 | 38.198 | 98.382 | 1.0000 | 4/4 |
| 1 | 97 | 1000 | 3072×3232 | 39.342 | 99.163 | 1.0000 | 4/4 |
| 2 | 97 | 1000 | 2560×2688 | 38.726 | 98.761 | 1.0000 | 4/4 |
| 13 | haar | 1000 | 3072×3232 | 35.455 | 96.451 | 1.0000 | 0/4 |
| 8 | haar | 1000 | 2560×2688 | 36.993 | 97.555 | 1.0000 | 0/4 |

## Q1: Haar 1000 against CDF at 500

All comparisons below use the same encoded geometry. Positive values favour Haar 1000.

| Pixels/eye | Reference | Display ΔHVS dB | Display ΔVMAF | All crops match/exceed both |
|---:|---|---:|---:|---:|
| 3072×3232 | cdf53@500 | -0.426 | -0.355 | False |
| 3072×3232 | cdf97@500 | -0.977 | -1.344 | False |
| 2560×2688 | cdf53@500 | +1.751 | +2.177 | False |
| 2560×2688 | cdf97@500 | +1.322 | +0.596 | False |

## Q2: CDF candidates against Haar 1000

All comparisons below use the same encoded geometry. Positive values favour the CDF candidate.

| Pixels/eye | Candidate | Display ΔHVS dB | Display ΔVMAF | All crops improve both |
|---:|---|---:|---:|---:|
| 3072×3232 | cdf53@800 | +2.098 | +2.034 | True |
| 3072×3232 | cdf53@1000 | +3.127 | +2.495 | True |
| 3072×3232 | cdf97@800 | +2.753 | +2.416 | True |
| 3072×3232 | cdf97@1000 | +3.886 | +2.712 | True |
| 2560×2688 | cdf53@800 | -0.092 | +0.262 | False |
| 2560×2688 | cdf53@1000 | +1.204 | +0.827 | True |
| 2560×2688 | cdf97@800 | +0.446 | +0.843 | False |
| 2560×2688 | cdf97@1000 | +1.732 | +1.206 | True |

Each Q1/Q2 cell has six FFmpeg comparisons and six HVS comparisons. The audit requires PSNR and SSIM indices 1–90 in every FFmpeg log and `ScoredFrames = 90` in every HVS log; raw-log hashes are retained in the JSON. GPU load/free-VRAM samples are quality-monitor context only. Segment 1 stopped for active ComfyUI compute work after its four valid Haar cells; its partial CDF cell is retained as discarded evidence and is not scored in the final table. No headset work, timing conclusion, or Q3 codec score is included.

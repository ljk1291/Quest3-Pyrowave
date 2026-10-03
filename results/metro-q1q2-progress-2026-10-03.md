# Metro Q1/Q2 progress — incomplete

This is an incomplete offline measurement record. It includes six retained 500 Mbps 3072/2560 references and four fully completed Haar cells from Q1/Q2 segment 1. The segment stopped when the quality lease detected active ComfyUI compute work. The partial CDF cell is excluded; eight CDF cells have not completed.

| HVS rank | Wavelet | Mbps | Encoded pixels/eye | Display HVS dB | Display VMAF | Cap fill | Crops improve vs same-size Haar 500 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | haar | 1000 | 2560×2688 | 36.993 | 97.555 | 1.0000 | 4/4 |
| 2 | 97 | 500 | 3072×3232 | 36.432 | 97.795 | 0.9999 | 4/4 |
| 3 | 53 | 500 | 3072×3232 | 35.881 | 96.806 | 0.9999 | 4/4 |
| 4 | 97 | 500 | 2560×2688 | 35.671 | 96.959 | 0.9999 | 4/4 |
| 5 | haar | 1000 | 3072×3232 | 35.455 | 96.451 | 1.0000 | 4/4 |
| 6 | haar | 800 | 2560×2688 | 35.265 | 95.940 | 0.9999 | 4/4 |
| 7 | 53 | 500 | 2560×2688 | 35.243 | 95.378 | 0.9999 | 4/4 |
| 8 | haar | 800 | 3072×3232 | 34.577 | 94.643 | 0.9999 | 4/4 |
| 9 | haar | 500 | 2560×2688 | 33.536 | 90.871 | 0.9999 | 0/4 |
| 10 | haar | 500 | 3072×3232 | 33.090 | 88.823 | 0.9999 | 0/4 |

The four new Haar cells each passed six FFmpeg comparisons with PSNR and SSIM frame indices exactly 1–90 and six calibrated HVS comparisons with `ScoredFrames = 90`; log hashes are in the JSON. Native tools, source, projection and frozen crops match the retained baseline. This report makes no timing or headset claim and does not replace the final 12-cell campaign report.

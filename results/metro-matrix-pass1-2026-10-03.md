# Metro matrix, owner-supervised pass 1

All cells: 500 Mbps cap, requested 90 frames/s, 90 fixed source frames, SDR 8-bit 4:2:0, Compute. Native tools: `bc2178842e0c48ada75b2179c56cae06b6204e61`. Frame-bank code is byte-identical at both execution commits (`09bef8a` and `54a9ec2`); the latter changes only the contention policy. HVS GPU sanity passed. No headset or live VR test ran.

| Wavelet | Encoded pixels/eye | Codec VMAF | Display VMAF | Display HVS dB | Display PSNR-Y dB | Display SSIM-Y | Crops improving both metrics |
|---|---:|---:|---:|---:|---:|---:|---:|
| haar | 3072×3232 | 88.82 | 88.82 | 33.09 | 38.77 | 0.953928 | 0/4 |
| haar | 2560×2688 | 91.94 | 90.87 | 33.54 | 39.05 | 0.958035 | 2/4 |
| haar | 2080×2208 | 95.61 | 91.84 | 33.61 | 39.15 | 0.956962 | 3/4 |
| 53 | 3072×3232 | 96.81 | 96.81 | 35.88 | 40.89 | 0.968195 | 4/4 |
| 53 | 2560×2688 | 97.91 | 95.38 | 35.24 | 40.55 | 0.967613 | 4/4 |
| 53 | 2080×2208 | 98.57 | 94.49 | 34.52 | 39.96 | 0.964577 | 4/4 |
| 97 | 3072×3232 | 97.79 | 97.79 | 36.43 | 41.46 | 0.970746 | 4/4 |
| 97 | 2560×2688 | 98.43 | 96.96 | 35.67 | 40.99 | 0.969739 | 4/4 |
| 97 | 2080×2208 | 98.87 | 96.25 | 34.90 | 40.35 | 0.966543 | 4/4 |

Display scores compare both eyes at 3072×3232/eye, with per-eye Lanczos3 resizing for smaller encoded outputs. Crop counts require strictly positive VMAF and calibrated HVS changes against Godlike Haar/500 on every one of the four frozen crops. One pass is screening evidence, not promotion.

| Wavelet | Encoded pixels/eye | UI ΔVMAF / ΔHVS | Fog ΔVMAF / ΔHVS | Rail ΔVMAF / ΔHVS | Gravel ΔVMAF / ΔHVS |
|---|---:|---:|---:|---:|---:|
| haar | 3072×3232 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| haar | 2560×2688 | +1.67 / -0.02 | +1.76 / +0.22 | -0.01 / +0.29 | +1.25 / +0.28 |
| haar | 2080×2208 | +3.09 / +0.83 | +2.91 / +0.61 | -1.29 / -0.07 | +2.14 / +0.09 |
| 53 | 3072×3232 | +7.17 / +3.06 | +6.55 / +2.92 | +6.28 / +3.26 | +5.41 / +2.31 |
| 53 | 2560×2688 | +6.14 / +1.73 | +6.60 / +2.01 | +6.30 / +2.83 | +7.67 / +2.40 |
| 53 | 2080×2208 | +5.53 / +0.99 | +6.15 / +1.32 | +4.47 / +1.52 | +7.44 / +1.52 |
| 97 | 3072×3232 | +8.74 / +3.73 | +8.16 / +3.63 | +8.08 / +4.04 | +7.73 / +2.73 |
| 97 | 2560×2688 | +8.00 / +2.22 | +8.29 / +2.51 | +7.89 / +3.45 | +9.58 / +2.84 |
| 97 | 2080×2208 | +7.36 / +1.41 | +7.92 / +1.74 | +6.29 / +2.03 | +9.29 / +1.94 |

All GPU HVS comparisons explicitly report 90 scored frames. The independent CPU log audit requires six FFmpeg comparisons per cell, each with PSNR and SSIM indices exactly 1–90. Source/tool/plan identities are retained in the JSON report. Ancillary PSNR values were corrected from the retained FFmpeg sequence summaries: the inherited parser selected a per-frame row. Legacy fields and log hashes remain in the JSON provenance; VMAF, SSIM and calibrated HVS scores are unchanged. This was CPU-only postprocessing, with no new GPU scoring.

Limits: the captured sequence contains a later menu frame and irregular display timestamps; file order is preserved. Projection reuses Session 07; Session 09 has no independent measurement. These are offline quality results, not optical FPS, fresh submissions, headset decoder performance or a stable 90 Hz pass. The previous approximately 82–83 fresh submissions/s result remains separate.

The lease was explicitly owner-supervised under AGENTS.md rule (a). No arm, idle, headset or VD gate was consulted. Independent compute-backend/VRAM/device monitoring, stop marker, exact owned-job registration and finite cleanup remained active. Quality ignores desktop/browser load; timing uses sustained unrelated engine load above 10% for at least 10 seconds or a compute backend and invalidates overlapping timing measurements. Native utility timestamps from this quality run are not qualified timing evidence. No headset/SteamVR/VD settings, registration, installed pair or defaults were changed. Pass 2 has not started.

Continuous GPU load and free-VRAM samples cover the six resumed CDF cells: 713 samples, minimum free VRAM 12747 MiB, maximum overall load 63% (context only), no safety stop. The retained Haar segment has only its older monitor evidence, not retroactively invented utilization/VRAM samples. Two old-policy Firefox interruptions and the diagnosed Y4M header refusals are retained separately. Completed Haar quality results were reused; incomplete CDF results were discarded.

Validation: 52 local CPU checks (49 passed, three compiler-dependent Windows skips). [CPU CI passed](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37112302438); client, streamer and matching-pair jobs were skipped. No new signed pair. [Review PR](https://github.com/ljk1291/Quest3-Pyrowave/pull/20).

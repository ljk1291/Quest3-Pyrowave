# Offline quality re-score at 500 Mbps

**4/7 requested rows qualified.** Run outcome: `success` (exit 0). Lease closed: True; owned jobs: 0; cleanup errors: 0.

Display fence/p99 and their reference deltas are CPU-only. Display HVS/deltas remain unavailable; the full requested analysis is therefore incomplete even if all seven native rows finish.

One finite owner-away PC-only quality lease used the existing independent monitor, stop marker, parent-death cancellation and exact job registry. All guard source files are unchanged. No headset/ADB, VR/VD, network, settings, installation or arm-file work. Safety stops and detailed private errors are retained; incomplete rows never rank.

## Requested rows in priority order

| Order | Profile | State |
|---:|---|---|
| 1 | VD-like dual H.264 P7 / 500 | complete |
| 2 | Medium CDF 9/7 / legacy 65.28 / 500 | complete |
| 3 | Medium CDF 9/7 / RDO24 / 500 | complete |
| 4 | Medium CDF 5/3 / legacy 65.28 / 500 | not_completed_run_stopped |
| 5 | Medium CDF 5/3 / RDO24 / 500 | not_completed_run_stopped |
| 6 | Light CDF 9/7 phase-fixed / legacy 65.28 / 500 | not_completed_run_stopped |
| 7 | Single-stream H264Fit H.264 P7 / 500 | complete |

Native fence/p99 use frames 10–89; native whole-crop HVS uses all 90. Δ means row minus the measured VD-like P7/500 dual-eye NVENC proxy. Positive dB and negative p99 deltas favour a row. Missing references or metrics remain unavailable. 1000 Mbps Medium rows are retained controls above the real link budget.

## Native cropped domain

| Rank | Profile | Fence PSNR-Y dB | Temporal p99 codes | HVS dB | Δ fence / p99 / HVS vs VD-like 500 |
|---:|---|---:|---:|---:|---|
| 1 | Dual H.264 P7 / 700 | 46.922809 | 4.000000 | 47.754557 | 1.785733 / -2.000000 / 1.509082 |
| 2 | Single-stream H264Fit H.264 P7 / 500 | 46.258870 | 5.000000 | 36.816815 | 1.121795 / -1.000000 / -9.428660 |
| 3 | VD-like dual H.264 P7 / 500 | 45.137075 | 6.000000 | 46.245476 | 0.000000 / 0.000000 / 0.000000 |
| 4 | Dual H.264 P7 / 400 | 43.745989 | 7.000000 | 45.089760 | -1.391087 / 1.000000 / -1.155716 |
| 5 | Medium CDF 9/7 / RDO24 / 1000 | 42.412796 | 9.000000 | 37.356360 | -2.724280 / 3.000000 / -8.889115 |
| 6 | Medium CDF 5/3 / RDO24 / 1000 | 41.273421 | 11.000000 | 37.233930 | -3.863654 / 5.000000 / -9.011546 |
| 7 | Medium CDF 9/7 / legacy 65.28 / 1000 | 37.543370 | 15.320000 | 36.261744 | -7.593706 / 9.320000 / -9.983732 |
| 8 | Medium CDF 9/7 / RDO24 / 500 | 37.273005 | 16.000000 | 35.581982 | -7.864070 / 10.000000 / -10.663494 |
| 9 | Medium CDF 5/3 / legacy 65.28 / 1000 | 36.150850 | 18.000000 | 36.013034 | -8.986226 / 12.000000 / -10.232442 |
| 10 | Medium CDF 9/7 / legacy 65.28 / 500 | 33.696979 | 23.000000 | 34.359041 | -11.440096 / 17.000000 / -11.886435 |

## Approximate display domain

| Rank | Profile | Fence PSNR-Y dB | Temporal p99 codes | HVS dB | Δ fence / p99 / HVS vs VD-like 500 |
|---:|---|---:|---:|---:|---|
| 1 | Single-stream H264Fit H.264 P7 / 500 | 48.210268 | 4.000000 | unavailable | 0.358003 / 0.000000 / unavailable |
| 2 | VD-like dual H.264 P7 / 500 | 47.852265 | 4.000000 | unavailable | 0.000000 / 0.000000 / unavailable |
| 3 | Dual H.264 P7 / 400 | 46.694024 | 5.000000 | unavailable | -1.158241 / 1.000000 / unavailable |
| 4 | Medium CDF 9/7 / RDO24 / 1000 | 44.395426 | 7.000000 | unavailable | -3.456839 / 3.000000 / unavailable |
| 5 | Medium CDF 5/3 / RDO24 / 1000 | 43.463998 | 8.000000 | unavailable | -4.388267 / 4.000000 / unavailable |
| 6 | Medium CDF 9/7 / legacy 65.28 / 1000 | 41.217348 | 10.000000 | unavailable | -6.634917 / 6.000000 / unavailable |
| 7 | Medium CDF 5/3 / legacy 65.28 / 1000 | 39.746499 | 12.000000 | unavailable | -8.105766 / 8.000000 / unavailable |
| 8 | Medium CDF 9/7 / RDO24 / 500 | 38.688623 | 14.000000 | unavailable | -9.163643 / 10.000000 / unavailable |
| 9 | Medium CDF 9/7 / legacy 65.28 / 500 | 36.550869 | 16.000000 | unavailable | -11.301396 / 12.000000 / unavailable |

## Display method and legacy/RDO24 comparison

CPU Pillow Lanczos radius 3 resamples each complete eye independently. Requested factors are 2064/3072 horizontally and 2208/3232 vertically, from the [Quest 3 panel resolution](https://about.fb.com/news/2023/09/meet-meta-quest-3-mixed-reality-headset/). The cropped eye becomes 1763×1896 (effective factors 0.671875×0.682997); frozen pixel-edge bounds map with ceil/floor to (983,708), 160×186. Reference-only top-5% Sobel masks are recomputed in this domain. This assumes linear mapping of unchanged tangents, not physical optical centre density. It models neither lenses nor the Meta compositor.

For new rows, display analysis is CPU-only and proves all 90 source/decoded identities, input end hashes and native metric parity. Display HVS is unavailable for every row because the qualified scorer requires Vulkan; no extra display scorer pass is launched. Its delta stays unavailable. Existing five CPU-only retained diagnostics stay intact. Publication itself is read-only and starts no lease or scorer. This preserves the CPU-only constraint but leaves the requested display HVS analysis incomplete.

CDF 5/3, 500 Mbps: legacy/RDO24 comparison unavailable.
CDF 5/3, 1000 Mbps: RDO24−legacy native 5.122572 / -7.000000 / 1.220896; display 3.717499 / -4.000000 / unavailable. Fence ranking reversed after resampling: False.
CDF 9/7, 500 Mbps: RDO24−legacy native 3.576026 / -7.000000 / 1.222941; display 2.137754 / -2.000000 / unavailable. Fence ranking reversed after resampling: False.
CDF 9/7, 1000 Mbps: RDO24−legacy native 4.869426 / -6.320000 / 1.094617; display 3.178078 / -3.000000 / unavailable. Fence ranking reversed after resampling: False.

## Evidence and limits

The [matching JSON](offline-500-rescore-2026-10-06.json) carries sanitized final-controller, source, tool, adapter, plan and 90-frame proof hashes. Private captures, streams, decoded planes, process/lease evidence and command logs remain in ignored `results/local`. The earlier sandbox refusal is preserved in `original_sandbox_stop`. Upstream ALVR/PyroWave/HVS credits and pins are unchanged.

No rate, decoder speed, optical visibility or sustained 90 Hz conclusion follows from offline quality. Runtime rate acceptance, standalone decode-budget compliance and sustained live VR remain separate, unverified gates for every requested candidate. No preset is promoted.

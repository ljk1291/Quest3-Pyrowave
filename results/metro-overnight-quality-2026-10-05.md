# Overnight PC quality report

Declared scored-row and source/design queue status: **complete**; requested original full-FOV pre-encode motion coverage remains open.

Original motion coverage is partial: no pre-encode full-FOV Haar/500 head-turn stress row was run. Its retained post-decode moving-window preview is diagnostic only. AV1 motion was withdrawn by the owner.

finite PC-only offline quality evidence; no headset or live-stream measurement.

within each compatible domain, rank fence edge PSNR-Y descending, then temporal residual p99 ascending, then HVS descending; crop, synthetic-motion, and full-FOV rows are not cross-ranked.

Fence metrics use frames 10–89; HVS uses all 90. Temporal p99 is an 8-bit luma temporal-delta residual in code units, not milliseconds or optical shimmer.

| Row | Domain | State | Edge PSNR-Y | Temporal p99 | HVS |
| --- | --- | --- | ---: | ---: | ---: |
| full a2 Haar, 500 Mbps, RDO 24 | full_fov | complete | 29.772956058927512 | 33.0 | 34.622593215 |
| crop Haar, 1000 Mbps, RDO 24 | crop | complete | 35.9126270360497 | 19.0 | 39.547637404 |
| crop Medium Haar, softness 0.5, 1000 Mbps, RDO 24 | crop | complete | 39.71491478373498 | 12.0 | 36.724381503 |
| crop Medium 5/3, softness 0.5, 1000 Mbps, RDO 24 | crop | complete | 41.27342137751026 | 11.0 | 37.233929613 |
| crop Light 9/7, softness 0.5, 1000 Mbps, RDO 24 | crop | complete | 40.81030895597249 | 11.0 | 40.698892689 |
| crop 9/7, 1000 Mbps, RDO 16 | crop | complete | 39.98122220983111 | 12.0 | 42.993882153 |
| crop 9/7, 1000 Mbps, RDO 20 | crop | complete | 39.94082359310013 | 12.0 | 43.004647635 |
| synthetic motion H.264 Fit, 700 Mbps, P7 | synthetic_motion | complete | 47.75893285762635 | 4.0 | 36.899048096 |
| synthetic motion AV1 Main10, 200 Mbps, P4 | synthetic_motion | not_run | — | — | — |
| position_rdo_v1_crop97_1000_ppd24 | crop | complete | 40.89329177088394 | 11.0 | 42.533568052 |
| position_rdo_v2_crop97_1000_ppd24 | crop | complete | 40.00742663532078 | 12.0 | 43.012700843 |
| wo8_width_only_h264_p7_700 | crop | complete | 46.43997980744019 | 5.0 | 39.598477819 |
| temporal_feasibility_motion_pose_shift | synthetic_motion | complete | 30.51508516507626 | 49.0 | 35.293643518 |
| temporal_feasibility_native_previous_decoded | crop | complete | 30.55871383859456 | 49.0 | 35.683889187 |
| motion_intra_97_rdo24_1000 | synthetic_motion | complete | 40.162094969688404 | 12.0 | 42.879843667 |
| motion_medium_97_rdo24_1000 | synthetic_motion | complete | 42.42369235889528 | 9.0 | 37.284166099 |
| dequant_reconstruction_offset_-0.250_crop97_rdo24_1000 | crop | complete | 39.48716329969689 | 13.0 | 42.88488979 |
| dequant_reconstruction_offset_-0.125_crop97_rdo24_1000 | crop | complete | 39.76817001064898 | 12.0 | 42.991183108 |
| dequant_reconstruction_offset_+0.125_crop97_rdo24_1000 | crop | complete | 39.9860419935614 | 12.0 | 42.950906501 |
| dequant_reconstruction_offset_+0.250_crop97_rdo24_1000 | crop | complete | 39.90715131100062 | 12.0 | 42.825348961 |

## Combined cropped comparison

Qualified new rows and selected controls from the hash-bound, completed Q3 report. Fence metrics use frames 10–89; HVS uses all 90 frames.

| Rank | Profile | Evidence | Fence PSNR-Y dB | Temporal p99 | HVS dB |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | crop H.264 Fit, 700 Mbps, P7 | retained | 47.837276 | 4 | 36.976144 |
| 2 | wo8_width_only_h264_p7_700 | tonight | 46.439980 | 5 | 39.598478 |
| 3 | crop AV1 Main10, 200 Mbps, P4, spatial AQ off | retained | 42.997587 | 9 | 43.346668 |
| 4 | crop AV1 Main10, 200 Mbps, P1, spatial AQ on | retained | 42.619633 | 9 | 43.103077 |
| 5 | crop Medium CDF 9/7, softness 0.5, RDO 24, 1000 Mbps | retained | 42.412796 | 9 | 37.356360 |
| 6 | crop Medium 5/3, softness 0.5, 1000 Mbps, RDO 24 | tonight | 41.273421 | 11 | 37.233930 |
| 7 | position_rdo_v1_crop97_1000_ppd24 | tonight | 40.893292 | 11 | 42.533568 |
| 8 | crop Light 9/7, softness 0.5, 1000 Mbps, RDO 24 | tonight | 40.810309 | 11 | 40.698893 |
| 9 | position_rdo_v2_crop97_1000_ppd24 | tonight | 40.007427 | 12 | 43.012701 |
| 10 | dequant_reconstruction_offset_+0.125_crop97_rdo24_1000 | tonight | 39.986042 | 12 | 42.950907 |
| 11 | crop 9/7, 1000 Mbps, RDO 16 | tonight | 39.981222 | 12 | 42.993882 |
| 12 | crop 9/7, 1000 Mbps, RDO 20 | tonight | 39.940824 | 12 | 43.004648 |
| 13 | crop CDF 9/7 uniform RDO 24, 1000 Mbps | retained | 39.933228 | 12 | 43.008816 |
| 14 | dequant_reconstruction_offset_+0.250_crop97_rdo24_1000 | tonight | 39.907151 | 12 | 42.825349 |
| 15 | dequant_reconstruction_offset_-0.125_crop97_rdo24_1000 | tonight | 39.768170 | 12 | 42.991183 |
| 16 | crop Medium Haar, softness 0.5, 1000 Mbps, RDO 24 | tonight | 39.714915 | 12 | 36.724382 |
| 17 | crop CDF 9/7 uniform RDO 36, 1000 Mbps | retained | 39.504094 | 13 | 42.598806 |
| 18 | dequant_reconstruction_offset_-0.250_crop97_rdo24_1000 | tonight | 39.487163 | 13 | 42.884890 |
| 19 | crop Haar, 1000 Mbps, RDO 24 | tonight | 35.912627 | 19 | 39.547637 |
| 20 | crop CDF 9/7 default RDO, 1000 Mbps | retained | 35.753751 | 19 | 39.904984 |

## full fov ranking

| Rank | Row | Edge PSNR-Y | Temporal p99 | HVS |
| ---: | --- | ---: | ---: | ---: |
| 1 | full a2 Haar, 500 Mbps, RDO 24 | 29.772956058927512 | 33.0 | 34.622593215 |

## crop ranking

| Rank | Row | Edge PSNR-Y | Temporal p99 | HVS |
| ---: | --- | ---: | ---: | ---: |
| 1 | wo8_width_only_h264_p7_700 | 46.43997980744019 | 5.0 | 39.598477819 |
| 2 | crop Medium 5/3, softness 0.5, 1000 Mbps, RDO 24 | 41.27342137751026 | 11.0 | 37.233929613 |
| 3 | position_rdo_v1_crop97_1000_ppd24 | 40.89329177088394 | 11.0 | 42.533568052 |
| 4 | crop Light 9/7, softness 0.5, 1000 Mbps, RDO 24 | 40.81030895597249 | 11.0 | 40.698892689 |
| 5 | position_rdo_v2_crop97_1000_ppd24 | 40.00742663532078 | 12.0 | 43.012700843 |
| 6 | dequant_reconstruction_offset_+0.125_crop97_rdo24_1000 | 39.9860419935614 | 12.0 | 42.950906501 |
| 7 | crop 9/7, 1000 Mbps, RDO 16 | 39.98122220983111 | 12.0 | 42.993882153 |
| 8 | crop 9/7, 1000 Mbps, RDO 20 | 39.94082359310013 | 12.0 | 43.004647635 |
| 9 | dequant_reconstruction_offset_+0.250_crop97_rdo24_1000 | 39.90715131100062 | 12.0 | 42.825348961 |
| 10 | dequant_reconstruction_offset_-0.125_crop97_rdo24_1000 | 39.76817001064898 | 12.0 | 42.991183108 |
| 11 | crop Medium Haar, softness 0.5, 1000 Mbps, RDO 24 | 39.71491478373498 | 12.0 | 36.724381503 |
| 12 | dequant_reconstruction_offset_-0.250_crop97_rdo24_1000 | 39.48716329969689 | 13.0 | 42.88488979 |
| 13 | crop Haar, 1000 Mbps, RDO 24 | 35.9126270360497 | 19.0 | 39.547637404 |

## synthetic motion ranking

| Rank | Row | Edge PSNR-Y | Temporal p99 | HVS |
| ---: | --- | ---: | ---: | ---: |
| 1 | synthetic motion H.264 Fit, 700 Mbps, P7 | 47.75893285762635 | 4.0 | 36.899048096 |
| 2 | motion_medium_97_rdo24_1000 | 42.42369235889528 | 9.0 | 37.284166099 |
| 3 | motion_intra_97_rdo24_1000 | 40.162094969688404 | 12.0 | 42.879843667 |

## Retained cropped controls

| Control | Edge PSNR-Y | Temporal p99 | HVS |
| --- | ---: | ---: | ---: |
| crop CDF 9/7 uniform RDO 24, 1000 Mbps | 39.933227699 | 12 | 43.008816136 |
| crop CDF 9/7 uniform RDO 36, 1000 Mbps | 39.504094 | 13 | 42.598806 |
| crop CDF 9/7 default RDO, 1000 Mbps | 35.753751 | 19 | 39.904984 |
| crop H.264 Fit, 700 Mbps, P7 | 47.837275787 | 4 | 36.976144361 |
| crop AV1 Main10, 200 Mbps, P4, spatial AQ off | 42.99758746 | 9 | 43.346668103 |
| crop AV1 Main10, 200 Mbps, P1, spatial AQ on | 42.61963264766207 | 9 | 43.103076774 |
| crop Medium CDF 9/7, softness 0.5, RDO 24, 1000 Mbps | 42.41279562 | 9 | 37.356360346 |

The retained full-FOV baseline is listed separately and is not cross-ranked with cropped controls.

## Matched regional diagnostics

| Row | Centre Δ vs uniform | Centre Δ vs H264Fit | Peripheral Δ vs uniform | Peripheral Δ vs H264Fit |
| --- | ---: | ---: | ---: | ---: |
| position_rdo_v1_crop97_1000_ppd24 | Y 0.479; HVS 0.590 | — | Y -1.094; HVS -1.298 | — |
| position_rdo_v2_crop97_1000_ppd24 | Y 0.068; HVS 0.088 | — | Y -0.111; HVS -0.112 | — |
| wo8_width_only_h264_p7_700 | Y 2.912; HVS 3.749 | Y 1.153; HVS 1.890 | Y -4.298; HVS -4.889 | Y 3.119; HVS 3.405 |

Regional values are matched diagnostics and do not override the primary fence ranking.

## Temporal clipping counters

| Row | Frames | Residual clipped samples | Reconstruction clipped samples |
| --- | ---: | ---: | ---: |
| temporal:temporal-model-motion_pose_shift-r1 | 90 | 4997644 | 6275580 |
| temporal:temporal-model-native_previous_decoded-r2 | 90 | 4797065 | 5884968 |

## H.264 synthetic-motion packet accounting

| Row | Frames | Total bytes | Range bytes |
| --- | ---: | ---: | --- |
| motion-h264-fit-700-p7 | 90 | 87500006 | 972222–972228 |

GPU quality-lease sample ranges:

- full a2 Haar, 500 Mbps, RDO 24: 191 GPU quality-lease samples; overall load 0–64%, external engine 0–17%, free VRAM 8262–9919 MiB.
- crop Haar, 1000 Mbps, RDO 24: 89 GPU quality-lease samples; overall load 0–16%, external engine 0–13%, free VRAM 8248–9897 MiB.
- crop Medium Haar, softness 0.5, 1000 Mbps, RDO 24: 126 GPU quality-lease samples; overall load 0–5%, external engine 0–4%, free VRAM 9904–10131 MiB.
- crop Medium 5/3, softness 0.5, 1000 Mbps, RDO 24: 369 GPU quality-lease samples; overall load 0–5%, external engine 0–3%, free VRAM 9904–10131 MiB.
- crop Light 9/7, softness 0.5, 1000 Mbps, RDO 24: 870 GPU quality-lease samples; overall load 0–4%, external engine 0–7%, free VRAM 9893–10131 MiB.
- crop 9/7, 1000 Mbps, RDO 16: 96 GPU quality-lease samples; overall load 0–9%, external engine 0–3%, free VRAM 9908–10135 MiB.
- crop 9/7, 1000 Mbps, RDO 20: 88 GPU quality-lease samples; overall load 0–14%, external engine 0–0%, free VRAM 9841–10135 MiB.
- synthetic motion H.264 Fit, 700 Mbps, P7: 1053 GPU quality-lease samples; overall load 0–19%, external engine 0–7%, free VRAM 9566–10132 MiB.
- position_rdo_v1_crop97_1000_ppd24: 41 GPU quality-lease samples; overall load 0–9%, external engine 0–4%, free VRAM 9908–10135 MiB.
- position_rdo_v2_crop97_1000_ppd24: 43 GPU quality-lease samples; overall load 0–3%, external engine 0–3%, free VRAM 9908–10135 MiB.
- wo8_width_only_h264_p7_700: 399 GPU quality-lease samples; overall load 0–9%, external engine 0–7%, free VRAM 9440–10131 MiB.
- temporal_feasibility_motion_pose_shift: 99 GPU quality-lease samples; overall load 0–10%, external engine 0–11%, free VRAM 9841–10135 MiB.
- temporal_feasibility_native_previous_decoded: 115 GPU quality-lease samples; overall load 0–9%, external engine 0–9%, free VRAM 9798–10135 MiB.
- motion_intra_97_rdo24_1000: 32 GPU quality-lease samples; overall load 0–13%, external engine 0–5%, free VRAM 9908–10135 MiB.
- motion_medium_97_rdo24_1000: 666 GPU quality-lease samples; overall load 0–4%, external engine 0–3%, free VRAM 9882–10131 MiB.
- dequant_reconstruction_offset_-0.250_crop97_rdo24_1000: 121 GPU quality-lease samples; overall load 0–6%, external engine 0–6%, free VRAM 9836–10131 MiB.
- dequant_reconstruction_offset_-0.125_crop97_rdo24_1000: 121 GPU quality-lease samples; overall load 0–6%, external engine 0–6%, free VRAM 9836–10131 MiB.
- dequant_reconstruction_offset_+0.125_crop97_rdo24_1000: 121 GPU quality-lease samples; overall load 0–6%, external engine 0–6%, free VRAM 9836–10131 MiB.
- dequant_reconstruction_offset_+0.250_crop97_rdo24_1000: 121 GPU quality-lease samples; overall load 0–6%, external engine 0–6%, free VRAM 9836–10131 MiB.

Matching-pair build receipt verified its native RDO-density export, build identity, and explicit opt-in session-setting metadata. It was not installed or run.

## Follow-on quality queue

- position-aware RDO variants for cropped 9/7 at 1000 Mbps versus uniform RDO 24: complete.
- width-only horizontal H.264 700 Mbps P7 versus H.264 Fit: complete.
- source-noise CPU analysis: complete.
- retained latency audit: complete.
- actual codec closed-loop temporal model with shifted-motion analysis: complete.
- entropy-headroom CPU upper bound: complete.
- receive-overlap design using retained timing: complete.
- decoder quantization/reconstruction offset sweep: complete.
- optional WO6 fused inverse CPU or software-Vulkan-only investigation: complete.

All Quest GPU, fresh-submission, pipeline, and optical fields are unset because this report contains no headset measurement.

Encoder/decoder completion records support provenance only; they are not timing qualification.

## Review limits

- the reviewed edge rectangle can include the moving hand at frame 45; it is not pure fence-object segmentation on every frame.
- centre and peripheral scalar summaries are matched diagnostic regions; they do not override the primary fence-first rank.
- negative and cold-start temporal controls remain provenance or unranked attempts unless their completed row proves all 90 decoded identities and terminal gates.
- packet byte counts and ideal serialization arithmetic are provenance or byte-rate calculations, not matched wire-arrival or decode-overlap timing.
- a row may rank only after complete controller, unchanged source/tools/protected hashes, closed zero-job lease, and ordered 90-frame decoded identity proof.
- some older PNG exports used unspecified colour conversion and must not support cross-profile colour claims; new standardized F45 panels use the same BT.709 full-range CPU conversion; private clips and panels are review aids, not optical headset measurements.
- the retained full-FOV Haar moving-window preview extracts after decoding; it is a diagnostic, not a pre-encode head-turn codec stress, and is not cross-ranked by HVS with cropped actual-motion cells. A same-size full-FOV moving window has no source margin; qualifying it requires a new overscan source or an explicitly separate border/warp model.

## CPU-only diagnostics

- [source-content-noise-2026-10-05](source-content-noise-2026-10-05.md): complete; CPU diagnostic on retained Metro source frames and candidate static regions; no toggled-setting, live-FPS or causal film-grain measurement.
- [retained-latency-audit-2026-10-05](retained-latency-audit-2026-10-05.md): complete; CPU audit of retained Session05 Godlike-sized Haar/300Mbps/90Hz off/on/off/on allocation diagnostics; no new hardware timing..
- [pyrowave-entropy-receive-2026-10-05](pyrowave-entropy-receive-2026-10-05.md): complete; parser accounting and byte-prefix arithmetic only.

## Source, CI and staged build

- [Separate source branches and manual CPU CI](overnight-source-ci-2026-10-05.json).
- [Corrected matching-pair receipt](quality-candidate-build-rdo-session-2026-10-05.json): verified and staged, not installed or run.
- [Read-only NVENC dimension and HVS gate](nvenc-dimension-caps-2026-10-05.json): encoder dimensions only, not live stream qualification.
- [Temporal design and negative feasibility result](../docs/TEMPORAL-PREDICTION-FEASIBILITY.md).
- [WO-6 CPU model and remaining shader/runtime gates](../docs/WO6-FUSED-INVERSE-CPU-RESULT.md).

[PR #56](https://github.com/ljk1291/Quest3-Pyrowave/pull/56) prepares the default-inactive NVENC geometry hook on tested source `0e45e06bacd20255c3706fdfb14c48a4a159988f`; CPU-only CI passed and its native jobs were skipped. Only exact `ALVR_NVENC_DIMENSION_PREFLIGHT=1` selects the query before encoder initialization. The release-visible Warn marker replaces an earlier compiled-out Debug marker. Native Windows compilation and runtime activation remain open; it is excluded from the corrected pair. The capability probe remains a read-only no-encode query.

Stock MediaCodec and PyroWave share ALVR's outer packet-receive-to-decoded-callback wall interval and input-to-submit-plus-vsync pipeline estimate. Neither is a hardware decoder execution timestamp or optical latency. [PR #49](https://github.com/ljk1291/Quest3-Pyrowave/pull/49), source `a4b97a4189930b7783dfb738860233179373e652`, adds default-off, bounded queue-input-to-ImageReader-callback logging with CPU CI. It supplies no decoder GPU query or actual codec-name proof, remains unmerged, and is excluded from the staged corrected pair.

## Next measured work

- First profile individual dequantization and inverse-wavelet passes on the faster AHardwareBuffer configuration in a separately authorized matching-build headset session; speed gain is unmeasured.
- Then test final inverse/colour fusion and direct YUV presentation behind full reference-pixel, chroma/range/transfer, synchronization and resource-lifetime gates; CPU models do not prove shader correctness or performance.
- Keep uniform RDO 24 and the legacy zero reconstruction offset: lower densities, position variants and tested offsets have measured image trade-offs.
- The restricted entropy model offers at most 9.20% total payload saving under its assumptions; decode cost and useful receive/decode overlap remain unmeasured.
- Do not repeat the rejected 8-bit residual temporal models without a new residual-precision/clipping hypothesis; neither their bitstream padding variation nor exact decoded-pixel controls establish speed.

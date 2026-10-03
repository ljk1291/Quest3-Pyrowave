# Metro fence backfill — 2026-10-04

All three full-FOV 3072×3232/eye decodes exactly match their previously retained 90-frame decode hashes (270 matches). The source, qualified native tools and source order are unchanged. This adds spatial edge and temporal reconstruction-error measurements; it is not an optical shimmer or timing measurement.

The fixed left-eye rectangle is **x=1740, y=1310, width=240, height=274**, inside tunnel_fog_region. It was selected on source frame 0 before new scores. Source movement and later menu content mean it is a fixed spatial region, not tracked fence content throughout the sequence.

Ranking below uses trimmed-window fence edge PSNR, then shimmer p99/mean. All three agree on ordering in both windows. HVS is the retained full-display 90-frame value and is secondary; it is not a new tight-fence HVS measurement.

| Rank | Wavelet / Mbps | Frames | Edge PSNR-Y dB ↑ | Edge absolute error p99.9 ↓ | Temporal error mean ↓ | Temporal error p99 ↓ | Retained display HVS dB ↑ |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | 97 / 1000 | 10-89 | 34.583 | 26.000 | 3.883 | 21.000 | 39.342 |
| 1 | 97 / 1000 | 1-90 | 34.618 | 26.000 | 3.909 | 21.000 | 39.342 |
| 2 | 53 / 1000 | 10-89 | 33.286 | 31.000 | 4.330 | 24.000 | 38.583 |
| 2 | 53 / 1000 | 1-90 | 33.317 | 31.000 | 4.348 | 25.000 | 38.583 |
| 3 | haar / 500 | 10-89 | 26.117 | 60.000 | 9.707 | 44.000 | 33.090 |
| 3 | haar / 500 | 1-90 | 26.241 | 60.000 | 9.696 | 44.000 | 33.090 |

CDF 9/7/1000 has the lowest spatial and temporal edge error of these three retained configurations. It still adds measurable error; no result establishes that the owner-visible fence issue is resolved. The next comparison is revised Q3a at the explicit crop, including hardware codecs.

Metric definition: reference-only top-5% positive Sobel-magnitude mask, ties included, valid interior. Temporal error uses the same current-frame mask. One-based windows 10–89 and 1–90 contain 79 and 89 temporal pairs respectively. See [metric specification](../docs/FENCE-METRICS.md). Error units are full-range 8-bit luma codes.

All three finite PC leases closed with zero owned jobs and no cleanup errors. The first attempt corrected a lookup from a sanitized public report to retained private identities. A subsequent non-JSON lease-status response stopped scoring safely; retained decodes were reused. Neither interruption required repeating codec work. GPU-load context and segment hashes are in the [JSON](fence-backfill-2026-10-04.json). No headset, settings, installed-pair or arm-file changes occurred.

Q3 crop evidence: exact offsets are left (278,274), right (170,274), size2624×2776/eye. The tight fence maps to (1462,1036). wood_gravel_region is partially outside and must be explicitly excluded or separately labelled as an intersection, never silently moved. The other three fixed crops are contained. [Geometry record](q3-crop-geometry-2026-10-04.json).

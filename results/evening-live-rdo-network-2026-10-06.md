# Supervised RDO comparison and partial Q4 — 2026-10-06

Installed matching pair: `0f07f05`. Full-FOV Haar, TCP, 4:2:0, Compute, SDR; 3072×3232 per eye, requested 90 Hz. Crop and foveation are off. These are diagnostic screens, not stable 90 Hz passes.

| Scene / cell | Mbps | Native RDO px/deg | Fresh submissions/s | GPU decode p50 ms | Decode-to-fence p50 ms | Estimated pipeline p50 ms | Owner judgement |
|---|---:|---:|---:|---:|---:|---:|---|
| normalized stereo chart / a | 500 | 65.280 | 83.511 | 8.968 | 11.472 | 73.325 | Still visible but much better, only really visible on the pink/magenta colour |
| normalized stereo chart / a2 | 500 | 24.000 | 83.826 | 8.999 | 11.438 | 73.156 | Worse |
| Metro fence checkpoint / a | 500 | 65.280 | 83.388 | 8.918 | 11.415 | 81.502 | Im at the fence scene, a lot of compression and blur |
| Metro fence checkpoint / a2 | 500 | 24.000 | 83.931 | 8.950 | 11.432 | 80.311 | Scene visible—worse |

All optical/display-FPS claims remain unset. Pipeline latency is ALVR’s estimate; GPU decode is timestamped GPU execution and decode-to-fence includes completion delay. Metro captures do not prove game internal render dimensions.

## Partial Q4

| Stationary Mbps | ACK payload Mbps | ACK p50 / p99 / p99.9 ms | Late % | Skipped slots | Pacing screen |
|---:|---:|---:|---:|---:|---|
| 600 | 597.534 | 9.827 / 22.309 / 34.601 | 28.681 | 110 | Failed |
| 800 | 683.962 | 24.191 / 45.495 / 166.374 | 100.000 | 3914 | Failed |

Both completed five-minute legs retain valid competing-GPU monitor samples, zero partial/unacknowledged/bad frames, but fail pacing. The 1000-Mbps leg was interrupted at the owner’s request to prioritize Metro; later stationary and moving legs did not complete. The composite sender/ACK test cannot isolate Wi-Fi from sender/receiver scheduling. No nominal 1000-Mbps qualification or Rlive follows.

## Requested Medium 9/7 quality candidate

The owner-requested cropped Medium 9/7 / RDO24 / softness0.5 / 1000 diagnostic produced black/flashing imagery and was stopped immediately. No usable quality score or completed timing capture was collected.

The setup helper selected the named Medium profile and server constants but omitted synchronization of the raw client fields. Server centre/edge parameters were 0.6/2 on both axes; the client retained 0.2/0.178 and 3/4. The client inverse shader consumes those raw fields. Also, `graphics/src/stream.rs` makes direct eye copy ineligible while foveation is enabled, so the staging renderer is used despite the requested property. These source-verified differences require correction and activation/geometry checks; they do not yet prove the sole cause of the failure or rank correctly configured 9/7 quality.

The subsequent session-23 chart synchronized all raw/native Medium fields and confirmed native RDO24. The owner still reported **“Still black/flashing”**. Its native log confirms Compute CDF9/7 and decoded 4224×2208, with optimal AHB allocation and minimal fragment usage active. Staging dimensions remain source-derived rather than observed. The raw mismatch was therefore not the sole cause. No completed timing capture or usable quality judgement was collected; the session was stopped and restored immediately. See the JSON recheck entry for hash-bound evidence.

## Restoration and remaining work

Controllers unresponsive in SteamVR and Meta menu; stopped and restored without comparison. Owner restarted Quest before session 21.

Native legacy RDO and 1000 Mbps selected, but ADB went offline before Metro relaunch/capture. No image judgement or completed measurement. USB reconnection enabled exact restoration.

Every listed session is restored with zero errors; changed keys have exact readbacks and VD/driver/OpenXR verification. Unowned SteamVR UI writes were preserved. No new pair was installed in these sessions. Retained 0f07f05, 80a1635 and d1c3 artifacts remain available.

The matched chart comparison favours legacy RDO according to the owner. It does not overrule or validate the separate offline Medium 9/7 quality candidate. No RDO, codec or decoder default is promoted. Next live steps require a fresh owner-ready supervised session and working controllers. See [the checklist](../docs/Q3-HEADSET-CHECKLIST.md).

Full percentile data, build/geometry checks, immutable raw-report hashes and explicit limitations are retained in [the JSON report](evening-live-rdo-network-2026-10-06.json).

# Finite stationary network continuation — 2026-10-06

Owner-authorized AFK network-only lease: two five-minute stationary legs at 1000/1200 Mbps, with a 25-minute independent deadline. Charging required; the owner approved a session-only 5% battery floor. All thermal, device, workload/VRAM, idle, job-registration and stop checks were retained. No arm edit, VR app, settings or installation work.

| Target Mbps | Source | ACK payload Mbps | ACK p50 / p99 / p99.9 ms | Late % | Skipped slots | Pacing |
|---:|---|---:|---:|---:|---:|---|
| 600 | retained supervised | 597.534 | 9.827 / 22.309 / 34.601 | 28.681 | 110 | Fail |
| 800 | retained supervised | 683.962 | 24.191 / 45.495 / 166.374 | 100.000 | 3914 | Fail |
| 1000 | new AFK | 746.102 | 28.877 / 34.857 / 47.476 | 100.000 | 6853 | Fail |
| 1200 | new AFK | 760.934 | 33.561 / 42.072 / 184.423 | 100.000 | 9877 | Fail |

A pass requires a complete, uncontended capture, no partial/unacknowledged/bad frames, no skipped slots and at most 0.5% late frames. Retained 600/800 rows were not repeated. No Rlive or moving-head qualification follows. This composite ACK test cannot distinguish Wi-Fi from sender/receiver scheduling. The pinned sender already paces independently of its ACK reader and permits three outstanding frames; these results are not a one-frame stop-and-wait test.

Restoration: **restored**, zero errors and owned jobs; 1 exact receiver-file key restored. VD hashes, driver registration and OpenXR match the snapshots. Installed 0f07f05 and rollback pairs are unchanged.

Safety: battery 22–23%, temperature 38.0–41.0°C; charging in every sample. Thermal status maximum 0; 0 timing-affected samples.

Raw report hashes, finite controller provenance, safety samples summary and explicit limitations are in [the JSON report](network-stationary-afk-2026-10-06.json).

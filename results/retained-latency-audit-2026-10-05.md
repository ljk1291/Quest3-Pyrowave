# Retained PyroWave latency audit

CPU audit of retained Session05 Godlike-sized Haar/300Mbps/90Hz off/on/off/on allocation diagnostics; no new hardware timing.

ALVR estimated input-acquisition-to-predicted-display interval; network is residual by construction. Not optical motion-to-photon.

| Allocation cell | Estimated total mean ms | Game/render | Encode | Network residual | Decoder wall | Decoder queue | Client compositor | Predicted-display lead | Fresh submissions/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| optimal-off-a | 81.056 | 3.684 | 1.885 | 6.150 | 23.475 | 4.700 | 17.115 | 23.893 | 55.998 |
| optimal-on | 70.661 | 13.481 | 1.798 | 5.965 | 17.177 | 2.329 | 11.130 | 18.634 | 82.690 |
| optimal-off-b | 81.209 | 3.460 | 1.816 | 6.144 | 23.358 | 4.796 | 17.396 | 24.080 | 55.253 |
| optimal-on-repeat | 61.751 | 4.151 | 1.849 | 6.261 | 17.296 | 2.324 | 11.130 | 18.588 | 82.017 |

The server-compositor mean is retained in JSON; every graph event has all eight stages. Their means partition the estimated total except for nonnegative network clamping: optimal-on has one exception (maximum 1.919 ms excess), repeat has four (maximum 4.919 ms excess). Mean excess is 0.00046/0.00288 ms; all remaining events close within rounding. The network value is a residual, not a measured one-way transport interval.

optimal-on largest three: vsync_queue_ms 18.634 ms, decoder_ms 17.177 ms, game_time_ms 13.481 ms.
optimal-on-repeat largest three: vsync_queue_ms 18.588 ms, decoder_ms 17.296 ms, client_compositor_ms 11.130 ms.

## What can reduce the leading contributors

- **vsync_queue_ms**: Runtime predicted-display lead. Faster decode can merely move time into this interval. Later pose acquisition/production scheduling needs controlled live evidence; do not shorten runtime safety lead blindly.
- **decoder_ms**: Receive-to-decoded notification wall scope includes native completion/queueing. Profile dequant/iDWT on fast allocation; then final-level fusion/direct YUV may remove work. Already-rejected whole-Haar fusion, batch and async trials are not new hypotheses.
- **game_time_ms**: Separate game rendering from SteamVR composition; source scene, render dimensions and graphics settings govern this stage. No codec patch can remove game rendering.
- **client_compositor_ms**: Investigate direct presentation/copy and contention with next decode. The eye wall interval includes waiting; GPU timestamps are needed before assigning it to pure copy.

## GPU execution and missing splits

Allocation-on retains ~9 ms median GPU decode and ~1.3 ms median GPU conversion, with ~11.5 ms record-through-completion. Native wait and eye-render wall times overlap that work. They cannot be added as extra GPU stages.
The earlier allocation-off profile measured mean dequant 3.750 ms and iDWT 4.997 ms in delayed Granite windows. These are not fast-allocation per-pass measurements. Separate PC conversion, send, receive and eye-copy GPU intervals are unavailable.

## Upstream comparison

Upstream publishes a short direct-copy screen at 2080×2208 per eye/1000 Mbps/120 Hz: GPU decode median 4.81 ms, completion 8.74 ms, eye CPU wall 8.69 ms and 103.63 fresh submissions/s. Its smaller geometry, clocks and pipeline differ. This is not a matched Godlike result or a complete latency partition. [Upstream pipeline report, reviewed at fd547804](https://github.com/JMS1717/Quest3-Pyrowave/blob/fd54780483a709140ed31b50e2ee0724d1b75e5c/docs/DECODE-PIPELINE.md).
Themaister’s generic compute performance claim has no matched Quest presentation breakdown. [Reviewed upstream README](https://github.com/Themaister/pyrowave/blob/89f7e47d4abbf650c91fae766728af866c5e32a0/README.md).

The approximately 82–83 fresh submissions/s allocation result remains a diagnostic, not stable90. Optical FPS and optical latency remain unset. [Machine-readable evidence](retained-latency-audit-2026-10-05.json).

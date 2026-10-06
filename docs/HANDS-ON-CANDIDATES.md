# Hands-on candidates

Configurations that passed automatic screening and are worth the owner's in-headset look
(Metro fence checkpoint, head motion). Newest first. Each entry: exact settings, the
evidence that put it here, and what to look at. Rejected options are listed at the end
so they aren't retried by accident.

## Candidates

### C1 — FOV crop on PyroWave Haar 500 (2026-10-06, session 25)
- Settings: as the session-25 sanity cell (PyroWave Haar, 3072x3232/eye render, 500 Mbps,
  90 Hz, RDO 65.28 px/deg, compute decode, TCP) plus `video.fov_crop.enabled=true`,
  horizontal 0.854 / vertical 0.85 (stream 2624x2752/eye). Foveated encoding off.
  Harness cell: `diag-crop-only` in `ws/session25.py`.
- Evidence: owner saw no flashing and "no visible difference" on the chart. GPU decode
  p50 5.89 ms (vs ~8.9–9.4 full FOV), decode-to-fence 8.4 ms, latency 49 ms (vs 60–80).
  Fresh rate stayed ~85/s, so the limit moved upstream (server render/encode or network).
- Look at: Metro fence and the edges of the view (is the crop noticeable?), stutter on
  head turns.

## Measured, not yet judged (need frame dumps)
- Render 3840x4032 downsampled to Godlike (`downsample-adaptive`: 82.5 fresh/s, latency
  72 ms; `downsample-bilinear`: 84.7 fresh/s, 67 ms). Decode unchanged (~8.95 ms).
  Unattended, so no visual verdict yet; re-screen with codex/frame-dump.
- 72 Hz Haar full FOV (`refresh-72`): 70.3 of 72 fresh/s (98 % fresh vs ~94 % at 90 Hz),
  decode 8.0 ms. Supports the owner's guess that the 90 Hz stutter is missing fresh frames;
  a smoother but lower-rate fallback, not the goal.

## Rejected (session 25)
- Foveated encoding (Medium, H264Fit): black flashing on every codec/path. Blocked until
  codex/foveation-flash lands.
- `debug.q3pw.decode_priority=low`: 69 vs 85 fresh/s.
- `debug.q3pw.layer_filter=sharpen_hq+supersample_hq`: owner saw worse compression on the
  magenta diagonal. `supersample_hq` alone: no visible difference.

# Frame-loss counters (default-off diagnostic)

`patches/frame-loss-diagnostics.patch` is an additive ALVR overlay. It applies after
`fork-identity-alvr.patch`, `fast-abr.patch` and `frame-dump.patch`, and before
`client-output-queue.patch`. With the controls unset it changes
nothing: no pacing, selection, buffering, protocol or default changes. ALVR, PyroWave and JMS1717
credits are unchanged.

Ported on 2026-10-08 from the ljk1291 fork (`codex/decoder-v2`) to upstream `18d43ce` (`.65`).
Upstream now has its own frame accounting, so the port keeps only the counters upstream lacks; the
[mapping](#mapping-from-the-fork-counters-to-upstream) says where every dropped one went. Not
compiled locally and not run on a headset.

## Why it exists

The fork's 2026-10-06 diagnosis (session 25, 90 Hz, TCP) found that missing frames were decoded
outputs **superseded in the client's one-slot `FrameSlot` before the render loop took them**: two
decodes finished between consecutive selections, so the second replaced the first. Across ten
captures decoded − superseded − completed eye copies stayed within one in-flight frame, with zero
decode failures. That finding led to the output FIFO ([OUTPUT-QUEUE.md](OUTPUT-QUEUE.md)).
Upstream reached the same picture at 207 Hz with its per-frame trace ([FRAME-TRACE.md](FRAME-TRACE.md)):
the loss is after publication, as supersession and empty selections.

## Controls

Read once per process; restart the server or client to change them.

| Control | Side | Effect |
|---|---|---|
| `ALVR_FRAME_LOSS=1` | server environment | `[Q3PW_FRAME_LOSS] native cumulative ...` and `[Q3PW_FRAME_LOSS] rust cumulative ...` in the server log |
| `debug.q3pw.frame_loss=1` | client property | `[Q3PW_FRAME_LOSS] rust cumulative ...` in logcat (tag `Q3PW_FRAME_LOSS`, info level, bypassing ALVR's error-only log mirroring) |
| `debug.q3pw.stats_source_ts=1` | client property, read when a stream starts | Statistics repair below; logs `[Q3PW_STATS_SOURCE_TS] enabled: ...` |

Lines are process-lifetime cumulative, at most once a second and only when an instrumented event
runs; subtract two lines of one process. Absent fields mean zero so far. Disabled, each site reads
a cached flag and takes no lock, clock or allocation. Enabled has a small cost; use the same
setting in every cell of a comparison. Counters are not reset per stream.

## Counters kept

**Client (Rust):**

| Field | Meaning |
|---|---|
| `decoder_not_submitted` | Stream-socket frame the decoder callback refused (or no decoder yet); an IDR is requested |
| `client_wait_idr` | Stream-socket frame dropped while waiting for an IDR |
| `codec_rejected` | PyroWave refused a complete frame (`pyroclient_push_packet` != 1) |
| `decode_failed` | `pyroclient` decode returned an error, no buffer, or an incomplete frame |
| `pending_reset` | A decoder change discarded a selected frame not yet rendered (opt-in pre-wait selection, or the blocking poll used for MediaCodec) |
| `source_before_display`, `display_timestamp_clamped` | Observations, not losses: the selected frame's source timestamp is before the display time, or more than 1 s before it (the XR-only clamp then changes the display timestamp) |
| `submit_n`, `submit_equal`, `submit_regressed`, `submit_last_ns` | The key passed to `report_submit`: count, adjacent repeats, regressions, last value |
| `stats_sent`, `stats_send_error`, `client_stats_history_miss` | Client statistics sent, failed to send, or not sent because the key had no history entry |
| `received_history_miss` | A frame arrived whose tracking key is no longer (or never was) in the client's statistics history |
| `xr_clock_missing` | No OpenXR time, so no statistics for that frame |
| `socket_old_packet`, `socket_recycled_incomplete`, `socket_no_buffer`, `socket_obsolete_incomplete` | ALVR stream-socket receive discards, all streams together (video only travels there over Wi-Fi TCP; tracking and statistics always do) |

**Server (Rust):**

| Field | Meaning |
|---|---|
| `enqueued`, `server_queue_full`, `server_queue_disconnected` | `send_video_nal` handed the frame to the video thread, found its bounded channel full (dropped; with fast ABR active only that frame, otherwise until an IDR), or found it closed |
| `server_wait_idr` | Dropped while the stream waits for an IDR (`avoid_video_glitching`) |
| `server_no_sender` | `send_video_nal` with no stream (between connections) |
| `sent`, `send_error` | ALVR stream-socket send of a video frame succeeded or failed (Wi-Fi TCP, or USB without wired connections) |
| `wired_sent`, `wired_send_error` | Frame handed to every wired connection's writer, or a connection had failed (the frame may be incomplete; video then falls back to the stream socket) |
| `socket_*` | As on the client, for the server's receive side (tracking and statistics) |

The five `send_video_nal` outcomes add up to its calls, which the fork counted as `encoded`.
Wi-Fi UDP sends are upstream's `[Q3PW_UDP_SEND]`.

**Server (native, `alvr_server/FrameLoss.h`):**

| Field | Meaning |
|---|---|
| `present`, `pose_unmatched`, `present_duplicate_pose` | `Present` calls; ones with no matched pose (timestamp 0); ones repeating the previous pose's timestamp (not discarded) |
| `sync_texture_missing`, `acquire_sync_failed`, `layer_overflow` | Present returned before composition, or a layer beyond `MAX_LAYERS` was ignored |
| `encode_attempt` | `CEncoder::Run` called `Transmit` (any codec) |
| `no_rate`, `zero_budget` | PyroWave dropped the frame silently: no bitrate or frame rate yet, or a byte cap that rounds to zero (ALVR's cap, or fast ABR's reduced cap) |
| `signal_failed`, `fence_event_failed`, `codec_encode_failed`, `packet_count_failed`, `packetize_failed`, `byte_budget_rejected` | PyroWave encoder failures, each also logged as an error |
| `encoded_valid` | A complete PyroWave frame went to `VideoSend` |

For PyroWave, `encode_attempt` is `encoded_valid` plus the drop and failure counters.

## Statistics repair: `debug.q3pw.stats_source_ts=1`

Upstream still passes the **clamped** display timestamp to `report_submit`
(`client_openxr/src/stream.rs`). Every earlier statistics stage used the frame's source key, so
whenever the clamp changes the value the client finds no history entry and the server gets no
graph for that frame. With the property set, `report_submit` gets the selected frame's source
timestamp; the clamp still applies to the display time given to the runtime. It repairs joins
broken by the clamp, not expired or never-created history entries (`received_history_miss`,
`client_stats_history_miss` and upstream's `[Q3PW_STATS]` show those). The unit test
`source_key_survives_a_display_clamp` (client_core `statistics.rs`) covers the lookup.

## Mapping from the fork counters to upstream

Where upstream records the same event at the same place, the fork counter was dropped. "Trace" is
upstream's opt-in per-frame trace (`debug.q3pw.frame_trace=1`, `tools/quest3/frame_trace.py`,
record kinds in that script); "telemetry" is the cumulative `HeadsetTelemetry.pyrowave` counters
the server records (what `frame_loss_analysis.py` reads); `[Q3PW_FRESH]` needs
`debug.q3pw.fresh_probe=1`, `[Q3PW_SELECTION]` needs `debug.q3pw.loop_probe=1`.

| Fork counter (side) | Now | Upstream equivalent |
|---|---|---|
| `received_*` timestamps (client) | dropped | trace `A` (frame handed to the decoder, every transport: stream socket b=1, wired and UDP slices b=0); repeats and regressions from `A` ids in order |
| `decoder_not_submitted`, `client_wait_idr` (client) | **kept** | per-event warnings only |
| `replaced_before_decode` (client) | dropped | telemetry `skipped`; trace `R` |
| `codec_rejected`, `decode_failed` (client) | **kept** | telemetry `decode_failures` is their sum |
| `decoded` (client) | dropped | telemetry `complete`; trace `D`, `U` |
| `decoded_out_of_order` (client) | dropped | trace `O`; part of telemetry and `[Q3PW_FRESH]` `superseded` |
| `replaced_before_present` (client) | dropped | trace `X`; telemetry and `[Q3PW_FRESH]` `superseded` (which also include `O`). Output-FIFO drops are `X` with b=2 |
| `dequeued` (client) | dropped | `[Q3PW_FRESH] taken`; trace `T` (b=1 held, b=2 FIFO) |
| `pending_reset` (client) | **kept** | none |
| `render` (client) | dropped | trace `G`; `[Q3PW_SELECTION] slots` |
| `render_copy_blocked` (client) | dropped | `[Q3PW_SELECTION] copy_pending`; telemetry `pending_eye_copy_deferrals` counts every blocked poll |
| `repeat` (client) | dropped | `[Q3PW_SELECTION]` empty + copy_pending + no_decoder |
| `presented` (client) | dropped | trace `H` with a nonzero id (`eye_draws_fresh`) |
| `xr_should_not_render` (client) | dropped | trace `W`, b=0 |
| `xr_end_ok`, `xr_end_error` (client) | dropped | trace `N`, a=1 or 0 |
| `source_before_display`, `display_timestamp_clamped` (client) | **kept** | none |
| `selected_*` timestamps (client) | dropped | trace `T` ids |
| `submit_*` timestamps (client) | **kept** | none |
| `stats_sent`, `stats_send_error`, `client_stats_history_miss`, `received_history_miss`, `xr_clock_missing` (client) | **kept** | none (`[Q3PW_STATS]` is server-side) |
| `socket_*` (both) | **kept** | none |
| `encoded` (server) | dropped | the sum of the five `send_video_nal` outcomes below; also `StatisticsSummary.video_packets_total` |
| `enqueued`, `server_queue_full`, `server_queue_disconnected`, `server_wait_idr`, `server_no_sender` (server) | **kept**, in fast ABR's `match` arms | per-event warnings only |
| `sent`, `send_error` (server) | **kept** (stream socket, after fast ABR's `let sent = ...is_ok()`) | none; Wi-Fi UDP has `[Q3PW_UDP_SEND] frames`, `errors` |
| (new) `wired_sent`, `wired_send_error` (server) | added | the wired path did not exist in the fork; upstream logs only the first lost connection |
| `stats_received_*` timestamps, `server_stats_history_miss` (server) | dropped | `[Q3PW_STATS] N client statistics in 5 s, M without a server frame` (logged when none arrive or most miss) |
| `graph` (server) | dropped | `GraphStatistics` events; `PerformanceSnapshot.frames_total` |
| `server_present` (server) | dropped | native `present` (the same `ReportPresent` call) |
| native `present` ... `layer_overflow` | **kept** | none |
| native `encoder_terminal`, `encode_terminal`, `encode_cancelled`, `fence_wait_failed` | dropped | upstream's encoder has no terminal or cancellation state and waits on its fence without a timeout |
| native `encode_attempt` | **kept**, moved | was the start of `VideoEncoderPyroWave::Transmit`; now just before `Transmit` in `CEncoder::Run` |
| native `no_rate`, `zero_budget` | **kept**; `zero_budget` also covers fast ABR's reduced cap | none |
| native `signal_failed` ... `encoded_valid` | **kept** | error lines only |

Transport counters upstream has and the fork never had: `[Q3PW_TRANSPORT]` on the client (complete,
dropped, missing bytes, gaps, late and rejected slices per transport), `[Q3PW_UDP_SEND]` and
`[Q3PW_TRACKING_RX]` on the server ([TRANSPORT.md](TRANSPORT.md)).

## Harness compatibility

No harness parses `[Q3PW_FRAME_LOSS]` fields; people read them. The marker names and the
properties (`debug.q3pw.frame_loss`, `debug.q3pw.stats_source_ts`, `ALVR_FRAME_LOSS`) are
unchanged, and every kept counter keeps its name. The fork's `frame_loss_analysis.py` reads
telemetry counters, which upstream still sends, and its `frame_loss_profiles.py` sets only
properties that still exist.

## Verification

- Generated against upstream's ALVR stack plus `fork-identity-alvr.patch` (4387d54c...) and
  `fast-abr.patch` (33533b59..., codex/ur-fast-abr a5fb33b), after `frame-dump.patch`. On a fresh
  reconstruction it applies, reproduces the generating tree and reverses cleanly. Its server
  counters sit inside fast ABR's code (`send_video_nal`'s `match`, the video thread's sends, the
  encoder's byte cap), so it needs that exact fast ABR patch underneath.
- Rust tests: `frame_loss.rs` timestamp accounting (alvr_common, which upstream CI does not test)
  and the client statistics source-key test (runs in the Windows CI test step).
- Not compiled locally and not run on a headset.

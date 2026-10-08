# Opt-in decoded-output FIFO (`debug.q3pw.output_queue`)

`patches/client-output-queue.patch` is an additive ALVR overlay, last after
`fork-identity-alvr.patch`, `fast-abr.patch`, `frame-dump.patch` and
`frame-loss-diagnostics.patch`. It needs `pyroclient_decode_guarded_many` from this repository's
`tools/pyroclient` (built into the APK by `tools/build_alvr_2013.sh`), so build the client from the
same commit. With the property unset or `1`, decoding, selection and buffer rings are exactly
upstream's. ALVR, PyroWave and JMS1717 credits are unchanged.

Ported on 2026-10-08 from the ljk1291 fork (`codex/decoder-v2`) to upstream `18d43ce` (`.65`). On
the fork, at 90 Hz over TCP, this FIFO took the client from about 83 to 89-90 fresh frames per
second (owner's live measurements). The port keeps that selection contract; it has not been
compiled or measured on upstream yet.

## Why

The client's `FrameSlot` keeps one decoded output. When two decodes finish between two render-loop
selections, the second supersedes the first and that frame is never shown
([FRAME-LOSS-DIAGNOSIS.md](FRAME-LOSS-DIAGNOSIS.md); at 207 Hz the same effect is in
[FRAME-TRACE.md](FRAME-TRACE.md)). A short FIFO lets the later frame wait for the next display
period instead.

## Controls

Read when the decoder is created; restart the client between arms.

| Android property | Effect |
|---|---|
| `debug.q3pw.output_queue` | Unset, `1` or anything else: upstream's latest-output slot. `2` or `3`: the FIFO with that depth. |
| `debug.q3pw.output_queue_max_age_us` | Source-timestamp age bound for catch-up, 1-1,000,000 µs. Unset or invalid: **22,223 µs**, two 90 Hz periods rounded up. Ignored at depth 1. Set it explicitly at other refresh rates (two periods at 207 Hz is 9,662 µs). |

An explicitly set `debug.q3pw.output_queue` logs, under logcat tag `PYROWAVE`:

```
[Q3PW_OUTPUT_QUEUE] depth=2 max_age_us=22223 ring=4 workers=1 copy_handoff=false frame_hold_ignored=false
```

A requested depth above 1 that cannot be used logs
`[Q3PW_OUTPUT_QUEUE] depth=1 fallback: <decode_handoff=1|ready_fd=1|prerecord_mode=1> is incompatible with depth>1`
and runs upstream's path.

## Contract

- Each published output is appended. A full FIFO drops only its oldest output.
- Publication also drops the oldest outputs whose source timestamp is **strictly** more than
  `max_age` behind the newly published one. Repeated or regressed tracking keys never trigger
  that; keys are never rewritten. This is a relative source-time bound, not a wall-clock timeout
  and not an image-identity check.
- Every drop counts once in the decoder's `superseded` (HeadsetTelemetry), in `[Q3PW_FRESH]
  superseded` and as trace record `X` with b=2.
- The render loop takes the oldest output. Upstream's loop already takes at most one output per
  rendered frame. An empty FIFO repeats the previous image and keeps its lease; upstream's
  publication wait (`debug.q3pw.frame_wait_us`) still applies while the FIFO is empty.
- A taken FIFO output is trace record `T` with b=2 and counts as `[Q3PW_FRESH] taken`.
- Source keys, selection and statistics are unchanged; `debug.q3pw.stats_source_ts=1` still
  repairs the display-clamp statistics join.

## How it sits in upstream's structure

Upstream's `FrameSlot` (`client_core/src/video_decoder/mod.rs`) has grown since the fork: release
tokens, a pending ready FD, freshness counters, the in-flight flag and the opt-in frame hold
(`debug.q3pw.frame_hold_us`, 285cf99). The fork's patch replaced `pending` with a `VecDeque`; a
literal port would have rewritten all of that. The port keeps `pending` as the newest output and
adds a queue of older untaken outputs beside it, reusing the hold's per-output record (buffer,
publication time, release token, late flag):

- `publish`: if an output is pending and the FIFO is on, the pending one moves to the back of the
  queue instead of being superseded; then overflow and catch-up trim the front.
- `take`: the queue's front first, then `pending`. So a non-empty queue always has a newer output
  pending, and `wait_for_pending`, the in-flight wait and the producer probe need no change.
- `protected_buffers_many`: the lease, the pending output and every queued output, read under one
  lock, for `pyroclient_decode_guarded_many`.

The frame hold is a narrower form of the same idea: one extra frame, a wall-clock age limit checked
when it is taken. With both properties set the FIFO wins and the hold is turned off
(`frame_hold_ignored=true`).

| Mode | With the FIFO |
|---|---|
| frame hold | replaced, see above |
| `decode_handoff=1` (single worker) | not compatible: handoff serializes production and cannot fill a FIFO; depth 1 |
| `ready_fd=1` (early publication) | not compatible: one pending ready FD only; depth 1 |
| `prerecord_mode=1` | not compatible: fixed three-slot ring, two protected buffers; depth 1 |
| `decode_workers=2` | supported; each worker has its own ring; late or equal ingress-order completions are still rejected (trace `O`) |
| `release_fd=1` | compatible; release tokens move with each queued output |
| `async_eye_copy=1` | compatible; selection still waits for the previous copy's fence |
| `pre_wait_poll=1` | compatible; the pre-wait selection takes the oldest output |

## Transports

The FIFO is in the PyroWave decoder that every current transport feeds:

- **TCP stream socket** (Wi-Fi TCP): `connection.rs` hands each frame to the decoder callback.
- **Wired, two parallel connections** (the default over USB): `wired_video.rs` assembles the slices
  and calls the same decoder callback.
- **Wi-Fi UDP** (`.65`, PyroWave → Transport → UDP): the server's `UdpVideoSender` sends the wired
  path's slices as datagrams; the client's `wired_video.rs` UDP receiver assembles them with the
  same code and calls the same decoder callback.

All three reach `pyrowave.rs`, because the server always registers the decoder configuration with
the UDP byte off (`new_openvr_config.pyrowave_udp = false` in `server_core/src/connection.rs`). The
older `pyrowave_udp.rs` decoder (own socket, own `FrameSlot`, ring of three) is not covered: only a
server sending that byte set selects it, and this server never does.

UDP and wired transports deliver frames in bursts more often than TCP did, so the FIFO is more
likely to hold two outputs there. At high Wi-Fi bitrates many consecutive frames repeat a tracking
timestamp ([TRANSPORT.md](TRANSPORT.md)); equal keys never trigger catch-up, so such frames are
queued and shown, but fresh-FPS counts by distinct timestamp still count them once.

## Buffers and memory

Each worker's output ring is depth + 2 buffers when the FIFO is on: the queued outputs (depth),
the render lease and one writable slot. Depth 2 uses 4, depth 3 uses 5; otherwise upstream's 3 (4
with the hold). `pyroclient_decode_guarded_many` excludes the lease, the pending output and every
queued output, from one snapshot. The consumer can take any of those while the decode runs; only
this worker publishes buffers from its own ring, so nothing outside the snapshot can be taken.

Extra memory per worker against depth 1: (depth − 1) output buffers. In PyroWave mode 5 an output
is 18.4 MB at 2080x2208 per eye (width x height/2 RGBA8), so depth 2 adds 18.4 MB and depth 3
36.7 MB. The direct eye copy's image cache holds 8 imports; two workers at depth 3 (10 buffers)
make it fall back to per-frame import, which it logs.

## Latency

At regular consumption, depth 2 can add up to one display period when two outputs are waiting
(11.1 ms at 90 Hz, 4.8 ms at 207 Hz) and depth 3 up to two. This is queueing at a steady rate, not a
bound during stalls; catch-up limits it to `max_age` of source time. Compare fresh FPS together
with ALVR's latency estimate, frame age at display (`frame_trace.py`) and phase shifts. A higher
rate with persistently older frames can be worse.

## Verification

- `pyroclient_decode_guarded_many` is added beside upstream's `guarded`, `guarded3` and
  `submit_guarded`, which now share one list-based slot search; their behaviour is unchanged (ring
  buffers are never null). `pyroclient_test` mode `2` (`protect_first_buffer=2`) runs a ring of
  five with four buffers excluded and fails if one is recycled.
- Rust unit tests (`video_decoder/mod.rs`, run by the Windows CI test step): FIFO order and empty
  repeat, overflow at depth 2 and 3 with every queued buffer protected, strict catch-up counting
  each drop, source keys and late workers, hold replacement with release tokens, handoff fallback,
  and property bounds. Upstream's FrameSlot tests are unchanged.
- Generated against upstream's ALVR stack plus `fork-identity-alvr.patch`, `fast-abr.patch`,
  `frame-dump.patch` and `frame-loss-diagnostics.patch`; on a fresh reconstruction it applies,
  reproduces the generating tree and reverses cleanly. It touches only `video_decoder/mod.rs` and
  `pyrowave.rs`, and does not depend on the frame-loss counters. Not compiled locally, not run on
  a headset.
- Still needed: an Actions build, then interleaved live cells (control, depth 2, depth 3 with
  `max_age_us` set for the refresh rate) per transport, recording fresh FPS, superseded and empty
  selections, frame age at display and the latency estimate.

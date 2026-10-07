# Fast TCP PyroWave budget experiment

Default off. This overlay extends the existing ALVR/PyroWave and JMS1717-derived
paths and preserves their credits. It is a candidate for reducing motion-related
TCP backlog, not a qualified bitrate or a guarantee of lossless frame delivery.

## Configuration

In the dashboard, enable Video > PyroWave > Fast TCP bitrate adaptation. The
saved `session_settings.video.pyrowave.fast_abr` object is:

```json
{
  "enabled": true,
  "content": {
    "floor": 0.35,
    "decrease": 0.6,
    "recovery": 0.05,
    "backlog_frames": 1.0,
    "send_buffer_bytes": 1048576
  }
}
```

Use PyroWave TCP (`video.pyrowave.transport.variant = "Tcp"`) and TCP for the
ALVR stream (`connection.stream_protocol.variant = "Tcp"`). ALVR's existing
constant or adaptive bitrate remains the ceiling. No new environment variables.
The effective codec/transport includes the existing PyroWave environment overrides;
an incompatible codec or transport logs `enabled=false` even if requested.
Configuration is latched on connection; reconnect after changes. The UI marks the
setting as requiring restart, like the other PyroWave settings.

Allowed ranges: floor 0.01–1, decrease 0.01–less than 1, recovery 0.0001–1 per
frame, threshold 0.25–8 frames, send buffer 64 KiB–16 MiB. Non-finite or out-of-range
active parameters reject connection setup. The 0.35 floor is the starting candidate.
Very small budgets can hit the codec's minimum usable frame size.

## Design

The producer increments the queue count before `try_send`; rejection rolls that
increment back. The consumer decrements on dequeue and times the complete sender
operation, including buffer preparation, scheduling and interleaved stream writes.
At each native PyroWave encode, the controller samples:

```
pressure = max(queued_frames + active_send_time / frame_period,
               longest_completed_send_since_last_sample / frame_period)
if pressure > threshold or a frame was dropped:
    multiplier = max(floor, multiplier * decrease)
else:
    multiplier = min(1, multiplier + recovery)
```

The age of an unfinished send is observed while that send is blocked. Completed
send durations and drop indications are consumed once. Queue/send feedback and
controller arithmetic use atomics; there is one encoder caller. The FFI callback
uses the existing server-context lifetime read guard and a per-connection read
guard, but never takes the send socket lock. Each connection owns fresh state;
disconnect removes it and the callback returns 1.

`VideoEncoderPyroWave.cpp` calls the new callback every encode, regardless of
`GetDynamicEncoderParams().updated`. It computes the original integer byte ceiling,
then floors ceiling × multiplier and applies the existing four-byte alignment.
ALVR's stored bitrate is never overwritten or recursively scaled. The codec's
existing complete-frame/budget validation remains in place. At multiplier 1 the
old integer budget is used exactly.

Fast ABR overrides the **shared ALVR TCP stream socket** send buffer, including
audio/haptics on that socket. Control traffic has a separate socket. A strict
socket call checks errors and reads the effective size back; connection setup
fails if the requested bound was not established. Linux's doubled SO_SNDBUF
accounting is allowed. Disabled streams retain the legacy buffer configuration
and error handling. Timing with a bounded buffer uses ALVR's existing cross-platform
socket path and requires no Windows IOCTL definitions or Windows-version-specific
TCP_INFO handling. It is a pressure proxy, not a measurement of bytes in TCP, the
NIC, access point or headset.

While enabled, every PyroWave frame is marked `is_idr` in the ALVR packet header.
A full channel discards that frame without setting STREAM_CORRUPTED or requesting
an IDR; the following complete frame passes both server and client IDR gates.
Repeated full-channel events can still drop several frames during a severe dip.
This codec-specific change is also gated by fast ABR to preserve disabled behavior.
H.264/HEVC/AV1 and disabled PyroWave retain the original overflow/IDR behavior.

## Logs and counters

Connection setup logs `[Q3PW_FAST_ABR] enabled=... requested=... floor=...`
with decrease, recovery, threshold, requested `sndbuf` and `sndbuf_actual` readback.
Disabled connections report `sndbuf=unchanged`. Enabled connections emit a line
on the existing one-second server telemetry cadence:

- `samples`: encode budget requests in the interval.
- `multiplier_min`, `multiplier_mean`: multipliers returned to the encoder.
- `frames_shrunk`: budget requests below 1; includes attempts that subsequently
  fail before enqueue. This does not prove successful encode or headset delivery.
- `frames_dropped`: rejected enqueue or failed send. `send_errors` is the failed
  send subset. Native encode failures and disconnect-discarded queued frames are
  outside these counters; use the existing frame-loss diagnostics as well.
- `backlog_p95_frames`: sampled pressure, rounded up to a quarter-frame bucket;
  `backlog_p95_saturated=true` means the last bucket (over 15.75 frames), rather
  than an exact tail value. Atomic interval counters can straddle the reporting
  boundary by a concurrent sample; use multiple intervals for aggregate comparisons.

No client overlay or protocol extension was added. Preserve the server markers
alongside the client's existing network/fresh-frame telemetry in captures.

## Validation and planner cells

The patch applies last, after `client-output-queue.patch`, using the pinned fetch
order. The CPU Actions job compiles and runs the actual standalone Rust controller
tests: step response, floor, additive recovery, live blocked-send feedback, stale
sample consumption, enqueue rollback, send errors, transport gating, tuning,
invalid inputs and reconnect reset. Session tests cover default-off migration,
round-trip settings and dashboard visibility. Full Actions builds must validate
the Rust/C++ callback, schema generation and sockets integration before installation.
Local checks do not compile Rust or C++.

Local source validation (2026-10-07): a fresh 17-patch reconstruction passed;
all 12 overlay files matched the edited source byte-for-byte, reverse application
and whitespace checks passed, and all pinned patch hashes matched. The two focused
pin/order contract functions passed when run directly with Python's standard
library. The local pytest runner is unavailable. Rust tests and native compilation
are pending Actions; no device acceptance evidence was collected.

Suggested planner sequence with otherwise identical geometry, codec and client
output-queue settings:

1. Run CPU CI, then dispatch the full build on the planner's committed branch.
   Keep the installed pair as rollback until the new build is verified.
2. Compare off/on/off at 750 and 1000 Mbps, 90 Hz: first unworn, then owner-worn
   head motion. Include the settings-only 1 MiB cap with
   `avoid_video_glitching=false` as a separate control, so the controller's gain
   is distinguishable from the smaller socket buffer alone. Keep the two-frame
   server channel unchanged. A bounded 1250 Mbps stress cell can compare with the
   planner's existing over-capacity A/B; it is not a qualified operating point.
3. Confirm startup readback, contraction during pressure and recovery afterward.
   Correlate multiplier and bitrate with network p50/p95/p99, fresh frames/s,
   encode/decode latency, queue drops and visible detail in motion. With fast ABR
   enabled, explicitly check `avoid_video_glitching=true`: a queue-full event must
   not produce a run of `server_wait_idr` drops. Set `ALVR_FRAME_LOSS=1` before
   server startup if those existing diagnostics are needed.
4. Repeat one tuned recovery (e.g. 0.01/frame) if the default produces repeated
   quality pumping; compare buffers of 1 and 2 MiB only if throughput stalls.
   Test ALVR adaptive mode separately after constant-cap behavior is understood.
5. Disable fast ABR and reconnect to restore the previous socket policy, original
   IDR behavior and full byte budget. Restore all other cell settings as usual.

No device, network, VR or GPU operation is part of this source change. Runtime
rate acceptance, standalone decode budget and sustained live VR remain **unverified**.

## Risks

The aggressive default recovers from 0.35 to 1 in about 13 frames (144 ms at 90 Hz),
so persistent near-capacity operation may oscillate. A completed long send can
cause one further decrease after reductions made during that send. ALVR adaptive
mode may lower its ceiling in response to the same dip and cause a double reduction;
it may also interpret deliberately smaller frames as changed capacity. The absolute
rate always stays below its current ceiling.

A 1 MiB send buffer can limit TCP throughput at 1000+ Mbps depending on RTT and
Windows behavior, and shared audio writes or CPU scheduling can resemble network
pressure. Socket buffering and TCP retransmission still impose latency; the controller
cannot recall bytes already queued. Capacity below the floor, a complete outage,
or native encoder/decoder limits will still cause drops. Build and CPU success
alone cannot establish a quality or 90 Hz improvement.

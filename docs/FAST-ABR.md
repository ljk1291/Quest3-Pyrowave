# Fast ABR: per-frame PyroWave budget over TCP

`patches/fast-abr.patch` is an additive overlay on upstream `.65` (18d43ce): ALVR 7eda092 plus
`alvr-20.13.0-server-instrumentation.patch`, `quest3-alvr.patch` and the fork-identity overlay.
It is the first of the fork's functional overlays; `frame-dump`, `frame-loss-diagnostics` and
`client-output-queue` follow it. **Default off.** Nothing in this port has been built or run yet:
the measurements below were taken with the same controller on the previous base (the fork's
October 7 builds `7f85e87` and `a928435`).

## What it does

With `video.pyrowave.fast_abr` enabled and PyroWave video travelling over TCP, the server measures
how far its video sender is behind and lowers the next frame's byte budget below ALVR's per-frame
cap. It also bounds the send buffer of ALVR's stream connection and stops a full server video queue
from waiting for an IDR frame.

The problem it addresses: by default ALVR asks for the largest possible send buffer on its stream
socket (`connection.server_send_buffer_bytes = Maximum`, `u32::MAX`). When Wi-Fi briefly carries
less than the bitrate, TCP queues the excess and latency grows to hundreds of milliseconds
([WIRELESS.md](WIRELESS.md): about 380 ms at 1500 Mbit/s). A full two-frame server queue then makes
`avoid_video_glitching` drop every frame until the next IDR, and PyroWave frames are flagged IDR
only on request.

## Settings

Dashboard: **Video → PyroWave → Advanced / Research controls → Show → Fast TCP bitrate adaptation
(experimental)**. The saved `session_settings.video.pyrowave.fast_abr`:

```json
{
  "enabled": true,
  "content": {
    "mode": { "variant": "Aimd" },
    "floor": 0.35,
    "decrease": 0.6,
    "recovery": 0.05,
    "backlog_frames": 0.75,
    "send_buffer_bytes": 0
  }
}
```

| Field | Default | Range | Meaning |
|---|---|---|---|
| `mode` | `Aimd` | `Aimd`, `Capacity` | controller, see below |
| `floor` | 0.35 | 0.01–1 | lowest budget, as a share of ALVR's per-frame cap |
| `decrease` | 0.6 | 0.01–0.99 | Aimd: multiplier applied per congested frame |
| `recovery` | 0.05 | 0.0001–1 | share regained per uncongested frame (both modes) |
| `backlog_frames` | 0.75 | 0.25–8 | congestion threshold in frames waiting or in flight |
| `send_buffer_bytes` | 0 | 0 or 64 KiB–16 MiB | stream socket send buffer; 0 = automatic |

- **Best measured tuning (previous base):** Aimd with `decrease` 0.7, `recovery` 0.03,
  `backlog_frames` 0.75. Capacity mode was a modest further win under overload. The defaults
  above are unchanged from the previous port; see [measurements](#measurements-on-the-previous-base).
- **Older sessions load unchanged.** A `.65` session.json has no `fast_abr` and loads it disabled.
  A session from the fork's v1 build (no `mode`) keeps its values and gets `Aimd`.
- **Applying a change:** `fast_abr` is read at stream start. It sits under `video.pyrowave`, which
  upstream's settings watcher compares, so a change while streaming reconnects the headset about
  2 s later ([SETTINGS-APPLY.md](SETTINGS-APPLY.md)). The driver configuration does not change, so
  SteamVR does not restart. The setting therefore no longer carries the "SteamVR restart" flag.
- Out-of-range or non-finite values, or a send buffer the OS does not establish, fail the
  connection setup with `[Q3PW_FAST_ABR] ...`.
- No environment variables. `ALVR_PYROWAVE*` overrides change the effective codec and transport,
  and therefore whether fast ABR is active.

## Where it is active

| PyroWave video path | Fast ABR | Feedback it times | Send-buffer bound |
|---|---|---|---|
| Wi-Fi, PyroWave Transport TCP, ALVR stream TCP | active (`video_path=stream_tcp`) | stream socket send | stream socket |
| USB, 1–4 wired video connections (default 2) | active (`wired_tcp`) | hand-off to the wired writers | stream socket only |
| USB with 0 wired connections, or a client that does not answer on them | active (`stream_tcp`) | stream socket send | stream socket |
| Wi-Fi, PyroWave Transport UDP | **inactive** (`pyrowave_udp`) | – | unchanged |
| Wi-Fi, PyroWave TCP but ALVR's stream protocol UDP | inactive (`stream_udp`) | – | unchanged |
| H.264, HEVC, AV1 | inactive | – | unchanged |

A requested but inactive controller logs its setup line once per connection at warning level, with
`enabled=false requested=true video_path=...`. The encoder then keeps ALVR's cap exactly. If a wired
connection fails mid-stream, video and fast ABR's timing move to the stream socket; the setup line
keeps `wired_tcp`.

**PyroWave UDP stays out of scope.** UDP `send_to` does not block on the link (the socket has an
8 MiB buffer, and at 1500 Mbit/s the server spent 1.9–2.5 ms per frame in system calls,
[TRANSPORT.md](TRANSPORT.md#live-results-65)), and the excess is lost on the air instead of queueing
on the sender. A UDP controller would need the client's missing-frame counts (`[Q3PW_TRANSPORT]`,
client side only today; PLAN 1.7 forwards them) sent back to the server. That is a protocol change,
not a small extension.

**Two wired connections.** The video thread hands each frame to one writer thread per connection,
through a one-frame channel. The hand-off blocks only while a writer still has a frame being written
and another queued. Fast ABR times that hand-off, so on USB it sees congestion after up to two frames
have queued in the writers, later than on the stream socket. A failed wired hand-off counts as a
send error, and video falls back to the stream socket as upstream does.

The send-buffer bound is **not** applied per wired connection:
- those are loopback sockets into the adb server, so SO_SNDBUF would bound only the hop to adb, not
  the USB pipeline behind it;
- the writers already bound the frame queue and give up after a 1 s write timeout;
- no wired measurement supports another buffer size.

The stream socket is still bounded on USB, because it carries audio, haptics and the fallback video.

## How it composes with ALVR's bitrate

The encoder's per-frame cap is `floor(ALVR bitrate / 8 / round(frame rate))`, aligned down to four
bytes ([BITRATE.md](BITRATE.md)). Fast ABR returns a multiplier `m` with `floor <= m <= 1`, and the
encoder uses `floor(cap × m)`, aligned down, only when `m < 1`. In every case:

- **Never above ALVR's ceiling.** `m` is at most 1, the encoder applies it only below 1, and ALVR's
  bitrate is never written back or rescaled. The codec's serialized-frame check still rejects
  anything over the unshrunk cap.
- **Quality floor (13ff836, 0.25 bit per stream pixel).** The floor is part of the ceiling fast ABR
  receives: a constant bitrate below the floor is raised first, and Auto starts from at least the
  floor. Under congestion fast ABR's own `floor` (a share of that ceiling) is the only lower bound,
  so a frame can go below the quality floor. This follows upstream's decision for Auto (1aa43b4):
  the network-latency limiter wins over the quality floor, because a link that cannot carry the
  floor otherwise queues or drops frames, as `.62` showed. Example: 2080x2208 at 207 Hz has a
  500 Mbit/s floor; with `floor` 0.35 the smallest frame cap is 0.35 × 500 Mbit/s / 8 / 207,
  about 106 KB.
- **Per-frame cap and PLAN 2.1.** The encoder passes the bitrate and the frame rate its cap comes
  from to fast ABR for every frame. Fast ABR measures pressure in that frame period and sizes the
  automatic send buffer from it. Today the rate is the stream's refresh rate (or the measured rate
  with `bitrate.adapt_to_framerate`). When PLAN 2.1 caps frames at `bitrate / measured frame rate`,
  the multiplier composes without changes, provided the encoder keeps passing the rate it divides
  by. Fast ABR's Capacity estimate is a measured link rate that 2.1's "never above what the link
  can burst" could reuse.
- **Auto.** Fast ABR is meant for a constant bitrate. With Auto, both controllers can lower the rate
  for the same dip, and Auto's estimate (frame bytes over network time) sees the smaller frames. Not
  measured.

## Controller

**Aimd** (v1). At every PyroWave encode:

```
pressure = max(queued frames + active send time / frame period,
               longest send completed since the last frame / frame period)
if pressure > backlog_frames or a frame was dropped:
    m = max(floor, m × decrease)
else:
    m = min(1, m + recovery)
```

**Capacity** (v2):

- **Throughput.** The sender estimates it from up to three adjacent busy sends. Each must take more
  than a quarter frame, with at most a tenth-frame gap. The first send after idle is excluded,
  because it may only fill free socket buffer. Failures and gaps reset the window.
- **Congestion.** It is detected from waiting frames plus the active send time beyond one frame
  period.
- **Cut.** An episode cuts once, to 90% of a fresh estimate (one provisional 10% cut without one),
  then holds for three frames. It allows no further cut until the frames queued at the cut have
  drained. An emergency cut needs a backlog above both twice the threshold and the episode's peak
  plus one frame.
- **Recovery.** `recovery` per frame up to 97% of the remembered capacity, then +0.01 per frame.
  Three idle samples allow probing toward the high-water capacity. Capacity memory is kept in bit/s,
  so changes of ALVR's ceiling do not rescale it.

Only the encoder callback takes Capacity's small mutex. The sender publishes feedback through
atomics. There is no allocation, logging or socket call per frame.

**Independent frames.** While a controller is published, every PyroWave frame is marked `is_idr`
in ALVR's packet header and the wired slice header. A full server queue then drops only that frame,
without setting `STREAM_CORRUPTED` or requesting an IDR, and the next frame passes both IDR gates.
With fast ABR off, and for other codecs, the upstream overflow behaviour is unchanged.

**Send buffer.** Automatic sizing (`send_buffer_bytes` 0) uses 1 MiB up to 1000 Mbit/s, and above
that `ceil(1.5 × bitrate / 8 / frame rate / 64 KiB) × 64 KiB`, within 1–16 MiB. That is 3 MiB at
1500 Mbit/s and 4 MiB at 2000 Mbit/s at 90 Hz. Connection setup starts from the constant bitrate
(raised to the quality floor) or Auto's maximum (1000 Mbit/s if unset). The sender then follows the
encoder's live ceiling and frame rate, resizing only when the 64 KiB-rounded bound changes. Each
size is set strictly and read back; Linux may report up to double. A failed resize disconnects
rather than continuing with an unknown bound. An explicit nonzero size stays fixed.

## Log markers

The marker names are unchanged from the previous port.

- **`[Q3PW_FAST_ABR] enabled=... requested=... floor=... decrease=... recovery=... backlog_frames=... sndbuf=... sndbuf_actual=... mode=... sndbuf_auto=... video_path=...`**
  Once per connection: info level, or warning when requested but inactive. `video_path` is new in
  this port. A disabled stream reports `sndbuf=unchanged sndbuf_actual=None`.
- **`[Q3PW_FAST_ABR] samples=... multiplier_min=... multiplier_mean=... frames_shrunk=... frames_dropped=... send_errors=... backlog_p95_frames=... backlog_p95_saturated=... mode=... capacity_mbps=... cuts=... frames_at_floor=... capacity_age_ms=...`**
  Every second while active, on the existing real-time update thread.
  - `frames_dropped` counts rejected enqueues and failed sends, wired hand-offs included.
  - `backlog_p95_frames` is rounded up to a quarter frame; `saturated=true` means above 15.75.
- **`[Q3PW_FAST_ABR] sndbuf_update=... sndbuf_actual=...`**: an automatic resize.
- **`[Q3PW_FAST_ABR] send buffer update failed: ...`**: then a disconnect.

Read them alongside upstream's `[Q3PW_QUALITY_FLOOR]`, `[Q3PW_TRANSPORT]` (client) and
`[Q3PW_TRACKING_RX]`. Fast ABR adds no client code and no protocol change.

## Changes from the previous port

| Change | Why |
|---|---|
| Dropped the `frame_loss::count` calls and the `FrameLoss("zero_budget")` context | They belong to `frame-loss-diagnostics.patch`, which now applies after this overlay |
| The encoder samples the multiplier after the D3D11 fence wait, just before the encode, and shrinks `rateControl` there | Fresher feedback; a frame that fails before encoding is no longer counted; the hunk stays clear of the lines `frame-loss-diagnostics` instruments |
| The callback also takes the encoder's frame rate (`GetPyroWaveBudgetMultiplier(ceiling_bps, framerate)`) | Pressure period and automatic buffer follow the cap's own frame rate (PLAN 2.1, `adapt_to_framerate`) |
| Active on the wired connections, timing the hand-off; bound only on the stream socket | Upstream's default USB path (two connections) did not exist before |
| Inactive over PyroWave UDP, decided by the UDP sender actually created; `video_path` in the setup line | Upstream's `.65` UDP transport replaces the old one |
| The stream socket's builder call is untouched; the bound is set strictly after connecting | Fewer changed upstream lines; ALVR's builder also sets buffers after connecting |
| `#[serde(default)]` on `fast_abr`, and the control placed under PyroWave's advanced group | Upstream's direct `PyroWaveConfig` deserialization test and its schema test pass unchanged |
| No "SteamVR restart" flag; new test that a change only reconnects | Upstream reconnects on `video.pyrowave` changes; the driver configuration does not change |
| Initial automatic buffer uses the quality-floored constant bitrate | Matches the ceiling the encoder actually receives |
| Linux and Android both allow doubled SO_SNDBUF readback | Android is Linux; server-only today |

## Tests

These compile in upstream's Windows job (`cargo test --release -p alvr_server_core --lib` and
`-p alvr_session --lib`):

- **`fast_abr.rs`:** AIMD step response, floor and recovery; blocked-send feedback before completion;
  stale-sample consumption; enqueue rollback; send errors; transport gating; tuning; invalid
  inputs; reconnect reset; the encoder frame rate setting the pressure period and automatic buffer
  (new).
- **`fast_abr_tests.rs`:** the deterministic TCP simulation, at 100 µs virtual steps, with a bounded
  socket buffer, blocking writes, the two-frame channel, and the real controller and estimator.
  - At fixed 1000/1100/1500/1600 Mbit/s under a 2000 Mbit/s ceiling: no floor hit, bounded backlog,
    and within 5% of capacity from ten frames after detection.
  - A 1600 → 1100 → 1600 Mbit/s dip, and a ±10% jitter variant.
  - Episode and emergency cuts, estimator exclusions, stale estimates, a changing ceiling, and
    automatic sizes.
- **`connection.rs`:** a `fast_abr` change reconnects without changing the driver configuration
  (new).
- **`beta_tests.rs`:**
  - opt-in default off, under the advanced group;
  - `.65` sessions without the field, and direct `PyroWaveConfig` deserialization (new);
  - explicit values kept, v1 sessions keep their mode, threshold and buffer.

`fast_abr.rs` uses only the standard library. A CPU-only gate can therefore compile it without a
reconstructed tree. Proposed step for the `tests` job:

```sh
mkdir -p /tmp/fast-abr-src && cd /tmp/fast-abr-src
git apply --include='alvr/server_core/src/fast_abr*.rs' "$GITHUB_WORKSPACE/patches/fast-abr.patch"
rustc --edition=2021 --test alvr/server_core/src/fast_abr.rs -o /tmp/fast-abr && /tmp/fast-abr
```

## Wiring

Uncomment the insertion point in `tools/ci/fetch_sources.sh`, right after the fork-identity overlay:

```sh
overlay "$dest/ALVR-20.13.0" patches/fast-abr.patch   # default-off per-frame PyroWave TCP budget (docs/FAST-ABR.md)
```

Then pin it in `sources.lock.json` `"overlays"`:

```sh
python3 tools/ci/source_lock.py pin patches/fast-abr.patch
```

The patch is `git diff --full-index --binary` from the reconstructed upstream ALVR stack to the
edited tree. The fork-identity overlay shares no lines with it. The patch:
- applies with `git apply --check --binary` both on the upstream stack alone and after the
  fork-identity overlay;
- reverses cleanly;
- passes `tests/test_patch_hunks.py`.

Lines that `frame-loss-diagnostics.patch` instruments and this overlay also changes:
- the `try_send` in `send_video_nal`, now a `match` with `Full`, `Disconnected` and `Ok` arms;
- the stream socket `send` in the video thread, now `let sent = ...is_ok()`.

Port its counters into those arms. Its encoder hunks around the zero-budget check are at least
eight lines away from this overlay's.

## Measurements on the previous base

October 7: 90 Hz, Haar 4:2:0, 2624x2752 per eye, Wi-Fi on a 160 MHz channel (PHY 2401 Mbit/s,
about 1.6 Gbit/s live capacity unworn), PyroWave over ALVR's TCP stream socket, constant bitrate.
Unworn short screens; the 2000 Mbit/s ceiling is the over-capacity proxy. v1 = Aimd with the then
defaults (×0.6, +0.05, 1-frame threshold, 1 MiB buffer).

| Cell | Fresh FPS | Network p50 / p99 | Note |
|---|---|---|---|
| 1000 Mbit/s, fast ABR off | 90.1, 88.5 | 10–12 / 13–26 ms | |
| 1000 Mbit/s, v1 | 89.8, 89.9 | 10 / 14–15 ms | multiplier 1.0: no cost |
| 2000 Mbit/s, 1 MiB buffer and `avoid_video_glitching` off, no controller | 70.2, 70.0 | 41 / 53 ms | settings-only cap |
| 2000 Mbit/s, v1 | 86.1, 86.3 | 20 / 36 ms | about 1.6 Gbit/s delivered, 0 server drops |
| 2000 Mbit/s, Aimd ×0.7 / +0.03 / 0.75 | 87.3, 87.5 | 14 / 27–30 ms | best Aimd tuning |

In a later sweep at 2000 Mbit/s, Capacity gave 88.2 fresh FPS against 86.9 for Aimd ×0.7 / +0.03 /
0.75, at a similar p99 (about 36 ms), with client skips of 8–17 against 32–69.

- Every setting still reached the 0.35 floor about once a second at 2000 Mbit/s.
- Capacity was slightly conservative at 1250 Mbit/s (budget mean 0.92).
- None of this has been repeated on `.65`, on USB, with two wired connections, or worn.

## Validation status and next checks

- **Local (no toolchain on the PC):** the reconstruction, `git apply --check`, reverse application,
  `git diff --check` and the hunk-count test.
- **Not yet run:** Rust compilation and tests, the C++ encoder and bindgen. Actions is the only
  compiler.
- **Unverified:** runtime acceptance, decode budget, sustained live VR and any optical latency.

Suggested cells once a build exists. Keep geometry, refresh, wavelet and
`max_queued_server_video_frames` identical, and use ABBA order:

1. **Wi-Fi, PyroWave Transport TCP, constant 1000 and 1500 Mbit/s:** off / Aimd ×0.7 +0.03 /
   Capacity. Compare fresh FPS, network p50/p99, repeated poses (`[Q3PW_TRACKING_RX]`) and client
   skips. Add the same cells with Transport UDP as the reference: upstream recommends UDP on Wi-Fi.
2. **USB, two wired connections, 2000 Mbit/s,** where frames take longer than a frame period
   ([BITRATE.md](BITRATE.md)): off / Capacity. Check the `wired_tcp` setup line and `frames_dropped`.
3. **Overflow recovery:** with fast ABR on, a full server queue must not produce runs of "Waiting for
   IDR frame".

Disable the setting to restore upstream behaviour: the send buffer, IDR handling and full byte
budget.

## Risks

- **Pressure is a proxy.** It measures the server's queue and send time, not bytes in TCP, the NIC,
  the access point or the headset. Shared audio writes and CPU scheduling can look like congestion.
- **A bounded buffer is not an empty one.** Socket buffering and retransmission still add latency,
  and bytes already queued cannot be recalled. A 1 MiB buffer can limit TCP throughput at
  1000 Mbit/s and above, depending on RTT.
- **Wired feedback is later.** It arrives about two frames late, and the adb pipeline's own buffering
  is outside the bound.
- **Saw-tooth.** At the capacity edge both modes still reach the floor periodically. Capacity below
  the floor, an outage, or decoder limits still cause drops.
- **Visible pumping.** A changing per-frame budget can add frame-to-frame quality variation. It
  could add to the chroma toggling under investigation; compare with fast ABR off.

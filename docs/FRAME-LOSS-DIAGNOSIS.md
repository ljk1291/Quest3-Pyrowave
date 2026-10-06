# Session 25 frame-loss diagnosis — 2026-10-06

The missing **decoded outputs are being superseded in the client's one-slot
`FrameSlot` before the render loop dequeues them**. Existing telemetry establishes
this without a new hardware run. The reason that consumption falls behind in
some paced runs remains a timing/scheduling question, not a demonstrated bitrate
threshold. No pacing or frame-selection default is changed.

This work read the reconstructed ALVR tree in
`ws/worktrees/foveation-flash/ws/alvr` without modifying it, and read the main
checkout's `results/local/session-25/*crop*-capture/{events.jsonl,report.json}`.
References below are paths and line numbers in that reconstructed ALVR tree
**before this overlay**, relative to its `alvr/` directory. Existing ALVR, PyroWave and
JMS1717 credits remain intact.

## 1. What the counters establish

Use differences between the **same first and last HeadsetTelemetry snapshots**.
`gpu_decode_ms.n` includes the sample batch preceding the first snapshot; it is
not the same measurement window as a last-minus-first eye-copy counter.

| Capture prefix / cell | Decoded delta | Before-decode skips | Superseded delta | Completed eye-copy delta | Decoded − superseded − copies |
|---|---:|---:|---:|---:|---:|
| 1791310761 / diag-crop-only | 1631 | 0 | 90 | 1540 | 1 |
| 1791311886 / crop-500 | 1764 | 0 | 125 | 1638 | 1 |
| 1791311967 / crop-400 | 1766 | 0 | 89 | 1678 | −1 |
| 1791312048 / crop-300 | 1630 | 1 | **440** | **1190** | **0** |
| 1791312131 / crop-500 | 1721 | 0 | 57 | 1664 | 0 |
| 1791312362 / crop-buf25 | 1676 | 3 | 76 | 1601 | −1 |
| 1791312444 / crop-buf1 | 1720 | 0 | 173 | 1547 | 0 |
| 1791312563 / crop-nopace | 2199 | 1063 | 434 | 1765 | 0 |
| 1791312647 / crop-300-buf25 | 1718 | 3 | 149 | 1570 | −1 |
| 1791312731 / crop-500 | 1719 | 0 | **481** | **1238** | **0** |

All these windows have zero decode failures, zero `dropped`, and zero pending
eye-copy deferrals. Differences of one are consistent with an output in flight
and separately updated counters. `superseded` combines pending-output replacement
and out-of-order worker completion rejection; with the default single TCP worker,
the latter cannot explain steady-state loss. The new instrumentation separates them.

Two later captures were present beyond the original brief: **500 Mbps also falls
to about 65 graph frames/s**, and 300 Mbps with buffer 2.5 reaches about 82/s.
Thus “300 Mbps causes the loss” is not supported by the complete capture set.
The bad 500 run has 58–72 graph records in each complete second. The first bad
300 run starts at 81, 77, 69, then mostly 57–73/s: persistent loss with some drift,
not one stall consuming the entire average.

Reproduce the accounting with the standard-library-only analyzer:

```powershell
$caps = Get-ChildItem '<main checkout>/results/local/session-25' -Directory |
    Where-Object Name -Match 'crop.*-capture$'
python tools/quest3/frame_loss_analysis.py $caps.FullName
```

The analyzer rejects counter resets, retains captures with no GraphStatistics,
and reports neighboring x2-gap medians and paired changes. It writes no captures.

## 2. Pacing, source identity, and statistics: explicit answers

### What `enforce_server_frame_pacing` actually does

`server_openvr/cpp/platform/win32/OvrDirectModeComponent.cpp:266` calls
`WaitForVSync()` from **PostPresent**, after composition/encoder notification.
`server_openvr/src/lib.rs:665` computes the time until the server's next virtual
vsync. With pacing on it sleeps
`(duration + ALVR_PACING_DELAY_US).saturating_sub(ALVR_PACING_HEADROOM_US)`;
with pacing off it only `thread::yield_now()`. Before a statistics manager exists
it sleeps 8 ms. This is neither a TCP send-queue policy nor a client decoder flag.

`server_core/src/statistics.rs:401` advances a free-running `Instant` clock in
nominal frame intervals. Its initial phase is unrelated to the headset clock.
Optional `ALVR_PHASE_LOCK` can move that clock using submitted-frame statistics
(`statistics.rs:226,434`); it is separate from this setting. There is **no client
read of `enforce_server_frame_pacing`** and no paced-only statistics filter.

The causal link to decoded-output loss is indirect: pacing changes completion
phase relative to the client consumer. The consumer polls after `xrWaitFrame`,
normally without waiting, then performs synchronous eye rendering. If two
decodes complete between consumer dequeues, the second replaces the first.
A poll just before completion repeats the previous layer; a later poll can find
that completion already replaced. A decoded frame is not rejected because its
target timestamp crossed a TCP decode deadline. The deadline parsed in the
PyroWave config is for the separate UDP assembler.

Faster arrivals can move this phase across a polling boundary, but the captures
do not establish that bitrate is the cause. Server phase, the source timestamp
used at `xrEndFrame`, and eye-copy/GPU contention remain plausible contributors.

### Why nopace can decode over 90/s, and whether the 90 copies are distinct

Removing PostPresent's sleep lets the compositor/driver path run faster than
the application submission cadence. `Present:213` detects equal target timestamps
but its duplicate-discard `return` is commented out. `CEncoder.cpp:181` transmits
every signaled composed output; the PyroWave encoder has no source-frame identity
or duplicate filter and uses a nominal per-frame byte budget, not a wall-time
bitrate limiter (`VideoEncoderPyroWave.cpp:442–462`). Extra submissions can therefore
re-encode repeated or compositor-reprojected application content. Which of those
SteamVR produced in this capture is not recorded.

In the aligned nopace telemetry window, **2199 / 19.6133 = 112.12 decoded/s**,
**1765 / 19.6133 = 89.99 completed eye copies/s**, with 1063 input replacements
and 434 output supersessions. The former number is preferable to dividing the
2308 GPU samples by a counter window. Assuming a single running worker, the
received rate is roughly (2199 + 1063) / 19.6133 = 166.3/s, up to pending frames.
There is substantial overproduction, not 112 unique application frames/s.

**Neither the 90 eye copies nor distinct decoder selection IDs prove 90 distinct
source images or correct presentation timestamps.** `video_decoder/mod.rs:317`
assigns a new selection ID to every dequeue, regardless of timestamp or pixels.
`PoseHistory.cpp:44` matches rotation only, oldest-to-newest with strict `<`
improvement: exact ties retain the oldest pose. `SubmitLayer:169` uses that match's
tracking timestamp, or zero on no match. Repeated pose keys do not by themselves
prove repeated image content; different pose keys do not prove fresh chart content.
The extra native counters reveal duplicate pose submissions, but exact source
identity still needs the chart's visible frame number or the separate paired
frame-dump work. Nopace is a diagnostic cell, not a promoted 90 Hz solution.

### Why GraphStatistics can vanish, and the opt-in repair

There is no “stats keyed only on paced frames” branch. The joins are:

1. Client tracking creates a history entry keyed by the reported target timestamp
   (`client_core/src/lib.rs:347`, `statistics.rs:42`). The server independently
   creates one on tracking receipt (`server_core/src/statistics.rs:125`).
2. Receive, decode, and compositor-start look up that exact key.
3. `stream.rs:575` clamps the display timestamp to at least `vsync_time − 1 s`.
   **It then passes the clamped value to `report_submit` at line 665**, although
   earlier stages used the original source key. This is a definite identity bug
   whenever the clamp changes the value.
4. Client `report_submit` sends only if `summary(timestamp)` finds a history entry
   (`client_core/src/lib.rs:448–456`). Server `report_statistics:220` emits a graph
   only if its own tracking history contains the received key. Repeats with no
   selected output deliberately send no frame stats; a missing XR clock also
   prevents submission. Graph reporting happens before `xrEndFrame` returns.

The histories default to 256 tracking entries (`session/src/settings.rs:2370`), while
PoseHistory keeps 360 (`PoseHistory.cpp:38`). With approximately 270 tracking samples/s,
those cover about 0.95 s and 1.33 s respectively. An old/tied pose match can already
be absent from both statistics histories, and a >1 s display clamp can independently
destroy the lookup key. Zero/unmatched timestamps also have no tracking entry.

**The provided nopace files cannot identify which join failed.** They contain only
19 HeadsetTelemetry events, no video target timestamps, client logs or stats-send
counts. They do not prove that the clamp fired, that a pose tie happened, or that
the server alone lost the reports. A categorical explanation of this capture
would exceed the evidence.

The minimal implemented repair, `debug.q3pw.stats_source_ts=1`, preserves the
original selected frame's key for `report_submit`, while retaining the existing
display clamp and rendering behavior. It defaults off and logs
`[Q3PW_STATS_SOURCE_TS]`. It restores joins broken **by the clamp**, not expired
or nonexistent history. The nopace diagnostic profile additionally sets the
existing `connection.statistics_history_size=1024` on both ends, covering the
pose history. This does not fabricate statistics for unknown timestamps. A
remaining `received_history_miss`, `client_stats_history_miss`,
`server_stats_history_miss`, or `xr_clock_missing` identifies the next failure.
Restoration in the actual nopace run still requires hardware verification.

Even recovered graphs can be ambiguous for duplicate keys: history entries are
deduplicated and stage times can be overwritten by another frame with the same
key. Their rates and latencies must be read alongside duplicate counters.

## 3. Frame path and discard/reporting map

| Stage and original ALVR file:line | Condition / consequence |
|---|---|
| `server_openvr/cpp/platform/win32/OvrDirectModeComponent.cpp:156,169,187` | SubmitLayer chooses a tracking key by pose, not source image ID. Layers beyond MAX_LAYERS are ignored. |
| Same, `:198,213,218,234` | Present reports a server frame. Duplicate timestamps are **not** discarded. Missing sync texture or AcquireSync failure returns before composition/encoding. |
| Same, `:272,283,333` | CopyTexture ignores missing eye texture handles; terminal encoder stops copying; WaitForEncode serializes reuse of the shared D3D context. |
| `server_openvr/cpp/platform/win32/CEncoder.cpp:149,170,222,235` | CopyToStaging renders; the event worker transmits. Terminal/exiting/no-texture cases do not encode. Normal operation blocks for the previous encode rather than maintaining a latest-frame overwrite queue here. |
| `server_openvr/cpp/platform/win32/FrameRender.cpp:758,827,851,859,1116,1123` | Missing eye texture skips a layer; SRV errors return false (CopyToStaging does not propagate that RenderFrame result). FFR, if enabled, then planar YUV rendering feed the imported encoder planes. These crop-only cells bypass FFR. Shader-linkage fix is orthogonal. |
| `server_openvr/cpp/platform/win32/VideoEncoderPyroWave.cpp:434,451,462,467,476,484,492,534,543,549,561` | Drops on terminal state, no rate/zero budget, D3D signal/event/wait/cancellation failure, codec encode/packet-count/packetization failure, or invalid/oversize complete frame. Never truncate a frame. TCP VideoSend at `:598`; UDP path is separate. |
| `server_core/src/lib.rs:429,444,473,490,511` | No sender loses the output; corrupted-stream/avoid-glitching gate waits for IDR. Bounded channel `try_send` drops on Full, requests IDR; disconnected sender cannot deliver. Existing encoded statistics are updated even after a queue drop, so they are not send-success counts. |
| `server_core/src/connection.rs:980,985,996–1001` | `max_queued_server_video_frames` bounds the channel. Sender copies a complete payload into ALVR shards; socket send errors were ignored via `.ok()`. No pacing flag in this thread. |
| `sockets/src/stream_socket.rs:95,237,508,533,591,610` | TCP transports ALVR shards reliably; application buffer exhaustion can still discard them. Old completed packet indices are discarded; incomplete buffers can be recycled; no free buffer discards the incoming packet's shards; older incomplete packets are retired after a newer complete packet. Receive pool is 10 packets per stream (`client_core/connection.rs:64,323`). |
| `client_core/src/connection.rs:342–395` | Receive/header errors terminate reception; no decoder callback or rejection means not submitted; corrupted-stream gate can wait for IDR. TCP zero packet loss does not mean all application queues are lossless. |
| `client_core/src/video_decoder/pyrowave.rs:75–84,141–146,182–237` | One encoded pending slot, latest wins; worker dequeues it and clears/pushes/decodes one complete frame. Codec rejection or native failure stops the instance. `decode_workers` defaults one, optionally two. `decode_handoff=1` only works with one worker and blocks production until copy submission. |
| `client_core/src/video_decoder/mod.rs:206–219` | **Implicated site:** successful decode replaces an unconsumed pending output. Separately, older/equal ingress-order completions from independent workers are rejected, even after take(). Both increment existing `superseded`. |
| Same, `:179–198,225–237,317` | take() leases the selected AHB; pending and leased buffers are protected from native reuse. Handoff waits for pending/awaiting-copy state; it can move loss back to the encoded pending slot. Selection IDs track decoder outputs, not source content. |
| `client_core/src/video_decoder/android.rs:109–115,213` | MediaCodec drops queue front when its running buffering average exceeds max_buffering_frames and sizes its buffer pool from that setting. **Not used by PyroWave TCP.** |
| `client_openxr/src/lib.rs:685–693,797` | Optional pre-wait polling; should_render=false ends an empty XR frame, leaving decoded output susceptible to replacement. |
| `client_openxr/src/stream.rs:366,436,453,492–553` | Decoder recreation clears held pending_frame. Pre-wait polling never overwrites an already-held selection. After xrWaitFrame, poll copy completion, consume held frame or newest output. Empty queue normally repeats immediately; frame_wait_us optionally waits ≤1 ms and ≤period/8. A pending async eye copy defers selection. |
| `client_openxr/src/stream.rs:570–577,606–672` | Compositor-start uses source key, then clamps display timestamp. Acquires/waits/renders/releases both eyes; selected-output counter increments after release. Repeats may reuse released images. Native copy failures/panics/XR acquire failures are not silent timestamp selection policies. |
| `graphics/src/direct_eye.rs:335,401–416` | Default synchronous direct-eye draw calls glFinish. Async mode uses a fence and later polling; failure falls back to glFinish. No max_buffering_frames or target-deadline discard here. |
| `client_openxr/src/lib.rs:845–849` | Default xrEndFrame display time is the source-derived (clamped) timestamp; runtime_display_time=1 uses xrWaitFrame's predicted display time. Successful eye release or a GraphStatistics record does not prove runtime scanout acceptance. |
| `client_core/src/statistics.rs:64,77,89,99,126`; `client_core/src/lib.rs:442`; `server_core/src/statistics.rs:215,333` | Exact-key joins, history eviction, missing XR clock, send/receive failures and server lookup misses can suppress graphs. No graph for a repeat with no fresh decoder selection. |

The rare layer/RenderFrame failure paths already have native diagnostics; the
new counters focus on per-frame pipeline discard boundaries and do not attempt
to catch process panics or every graphics API error. Socket counters aggregate
all ALVR streams in the process, not only video.

## 4. Gap-adjacent timing tests

Each entry below is the median **before → after** an x2 target-key gap, in ms.
Only surviving graph frames can be analyzed; the missing frame's times are not
in GraphStatistics. Network time is a residual of total minus other stages,
including tracking transport, not a direct per-packet stopwatch.

| Cell (capture prefix) | x2 pairs | Decoder queue | Vsync queue | Network | Total pipeline |
|---|---:|---:|---:|---:|---:|
| 500 (1791311886) | 146 | 1.342 → 1.340 | 35.043 → 34.634 | 8.131 → 8.424 | 60.492 → 60.445 |
| 400 | 92 | 1.466 → 2.114 | 37.802 → 28.533 | 6.563 → 6.538 | 61.405 → 61.368 |
| 300 | 376 | 1.281 → 1.653 | 32.876 → 32.721 | 5.599 → 5.650 | 56.247 → 56.189 |
| 500 (1791312131) | 77 | 2.337 → 3.608 | 39.824 → 31.043 | 8.455 → 8.456 | 65.331 → 65.261 |
| buf2.5 | 97 | 1.468 → 1.853 | 37.926 → 28.666 | 8.752 → 8.913 | 70.519 → 63.149 |
| buf1 | 185 | 1.727 → 1.354 | 18.198 → 18.042 | 9.607 → 7.842 | 44.793 → 44.672 |
| Later 500 (1791312731) | 382 | 1.198 → 1.348 | 32.951 → 32.921 | 7.985 → 8.068 | 58.407 → 58.392 |

Pairwise after-minus-before medians strengthen the phase evidence: at 400,
vsync_queue changes **−9.054 ms**, network **+0.058 ms**, total **−0.084 ms**;
at the good repeated 500, vsync_queue changes **−8.431 ms** with network
**+0.025 ms**. These are near-period changes in runtime lead without network
spikes. At bad 300, the paired changes are queue **+0.421**, vsync **−0.290**,
network **+0.034**, total **−0.059 ms**. There is no common queue-age threshold
or large transport stall preceding the skips.

The direct-eye render CPU wall time also matters: crop-300 p50/p95/p99 is
2.397/9.788/10.195 ms, first crop-500 is 1.701/10.077/10.332 ms, and nopace is
7.178/9.330/9.832 ms. These include synchronous GPU completion, not just draw
submission. A 9 ms decode-to-fence budget alone does not guarantee the consumer
polls once per 11.1 ms. Zero async deferrals does not exclude synchronous waiting.

**Why buffer 1.0 was worse and 2.5 no better:** neither value changes this decoder's
queues, ring size or wait deadline. The observed difference cannot be attributed
to PyroWave honoring those limits. Across runs the vsync/total medians move by
whole display periods (buf1 total 44.78 ms versus buf2.5 63.13 ms), consistent
with a different timing regime. Repeat sessions, phase and contention need
separating before changing a production selection policy.

Target timestamps are tracking keys, not a guaranteed numbered 90 Hz image
sequence. x0 gaps already show that distinction. x2 is a useful skip indicator
here; the native supersession accounting is the stronger localization evidence.

## 5. Added diagnostics and experiments

`patches/frame-loss-diagnostics.patch` is additive after shader linkage and pinned
by SHA-256. Defaults and wire format are unchanged. Set **before process startup**:

- Server `ALVR_FRAME_LOSS=1`: native and Rust `[Q3PW_FRAME_LOSS]` lines.
- Client `debug.q3pw.frame_loss=1`: direct logcat lines, bypassing ALVR's default
  Error-only client-log mirroring. They need not appear in events.jsonl.
- Independently, client `debug.q3pw.stats_source_ts=1`: the source-key repair above.

Counter logs are process-lifetime cumulative, emitted at most once per second
when an instrumented event runs; subtract lines in one process. They do not reset
per stream, and do not emit a heartbeat during complete inactivity. All absent
count fields mean zero so far. Disabled logging reads the gate once and avoids
counter locks, clock reads and formatting. Enabled logging has measurement cost;
use the same instrumentation in all comparison cells and later repeat without it.

Native fields distinguish `present`, `present_duplicate_pose`, `pose_unmatched`,
sync acquisition failure, encoder entry, invalid-rate/budget/codec/fence failures,
and `encoded_valid`. Rust server fields distinguish `encoded`, `enqueued`,
`server_queue_full`, `server_queue_disconnected`, `server_wait_idr`,
`server_no_sender`, `sent`, `send_error`, statistics received, history miss, and
`graph`. `encoded` means VideoSend ingress, `sent` means socket send succeeded,
neither means client presentation.

Client fields distinguish `received_n`, `decoder_not_submitted`, `client_wait_idr`,
`replaced_before_decode`, `codec_rejected`, `decode_failed`, `decoded`,
`decoded_out_of_order`, `replaced_before_present`, `dequeued`, `pending_reset`,
`render`, `render_copy_blocked`, `repeat`, `presented`, `xr_should_not_render`,
`xr_end_ok`, `xr_end_error`, and the statistics failure points above. `presented`
means selected output rendered and both eye images released, not verified scanout.
`source_before_display` and `display_timestamp_clamped` are observations, not
additional discarded-frame counts. Received, selected, submitted, and server
statistics-received timestamp fields report counts, adjacent equal/regressed
keys, and the last raw key. They do not hash images or claim unique source frames.

No new pacing/selection fix is justified yet. Existing `frame_wait_us` and
`runtime_display_time` are the smallest experiments for the unresolved cause.

## 6. Four settings-only confirmation cells

The adapter `tools/quest3/frame_loss_profiles.py` adds these variants to the
existing **main checkout** `ws/session25.py`; it does not edit that file. All use
crop-only Haar, TCP compute, direct-eye copy, 500 Mbps, 90 Hz, 20 s captures,
frame-loss counters, source-key stats repair, and existing loop_probe=1.

| Variant | Difference from control | What would confirm / falsify the hypothesis |
|---|---|---|
| `loss-control500` | Paced, frame_wait_us=0, runtime_display_time=0 | Establish render/repeat/supersession and native duplicate rates in this session. |
| `loss-runtime500` | runtime_display_time=1 | Fewer supersessions plus stable ~90 XR render iterations implicates source-derived end-time scheduling. Fresh copies alone do not establish optical smoothness. |
| `loss-wait500` | frame_wait_us=1000 | Wait hits with fewer repeats/supersessions implicate just-missed completion polls; added wait can also worsen GPU overlap. |
| `loss-nopace500` | Pacing off; statistics_history_size=1024 | Recover measurable keys; count overproduction/duplicates and locate any remaining stats miss. Larger history also changes smoothing, so this is diagnostic, not a clean latency A/B. |

Repeat control around the experiments; repeat the first three at 300 Mbps by
changing only `session_settings.video.bitrate.mode.ConstantMbps` to 300 in the
profile wrapper if the 500 run does not reproduce the bad phase. Keep buffering
1.5, one worker, handoff off, and all other source/filter/refresh settings fixed.
Do not combine frame_wait and runtime-display-time until each is measured alone.

Use the adapter for **the whole snapshot → cell → capture → restore cycle** so
new properties enter the saved/restored inventory. It inherits the harness's
existing hardware-session requirements. No hardware was run for this diagnosis.
Example command shape (first inspect with `--dry-run`):

```powershell
python tools/quest3/frame_loss_profiles.py --session25 '<main checkout>/ws/session25.py' --dry-run cell loss-control500
# In the separately authorized session, use the same prefix for:
# snapshot
# cell loss-control500
# capture
# cell loss-runtime500
# capture
# ... then restore, including after any early stop.
```

The server variable is set only in the adapter process and inherited by newly
launched children, then restored in its Python environment. Cached gates require
restarting the relevant client/server processes through the harness. Use a
matching pair built with this overlay; the adapter does not install it. Retain
native server logs and logcat in addition to events/report. Confirm the actual
keys, defaults and markers before interpreting a cell.

Acceptance remains separate: runtime accepting 90 Hz, standalone decode meeting
11.1 ms, and sustained distinct source frames in live VR are three different
claims. These captures establish neither correct nopace source identity nor an
owner-approved 90 Hz gameplay result.

## 7. Offline validation and remaining gates

- Python accounting/profile tests and source-lock/overlay-order tests: 17 passed.
- Read all ten captures, including zero-graph nopace; counter conservation holds
  within one in-flight frame across each aligned telemetry window.
- Overlay applies after shader linkage and reverse-checks in an ignored verification
  copy; all 16 resulting overlay files match generated sources after Git CRLF
  normalization. The read-only input files remain unchanged. At verification time
  the supplied tree already contained the shader fix, so it was reversed/reapplied
  **only in the verification copy** to check the stated stack order.
- Added Rust tests exercise repeated/regressed timestamp accounting and an actual
  client StatisticsManager lookup before/after a display clamp. Existing FrameSlot
  tests cover supersession, worker ordering and protected buffer leases. The full
  Actions workflow already runs common/client-core/server-core library tests.
- Local Rust/C++ toolchains are unavailable. Runtime compilation, those Rust tests,
  a matching Actions build, and hardware confirmation remain unrun. Python success
  and patch applicability do not establish runtime or 90 Hz performance.

Changed tracked deliverables: this document; `patches/frame-loss-diagnostics.patch`;
`patches/README.md`; `sources.lock.json`; `tools/ci/source_lock.py`;
`tools/ci/fetch_sources.sh`; `tools/quest3/frame_loss_analysis.py`;
`tools/quest3/frame_loss_profiles.py`; `tools/tests/test_frame_loss.py`;
`tools/tests/test_ci_pins.py`; `.github/workflows/ci.yml`. Reconstructed and
verification sources stay under ignored `ws/`. Nothing was committed.

# Opt-in decoded output FIFO

Candidate experiment, default off. `patches/client-output-queue.patch` stacks
after `frame-loss-diagnostics.patch`; upstream ALVR/PyroWave and JMS1717 credits
are preserved. Build a matching pair with this tree's `tools/pyroclient` library:
the overlay requires its new `pyroclient_decode_guarded_many` symbol.

Set before decoder creation (restart the client for comparison cells):

| Android property | Policy |
|---|---|
| `debug.q3pw.output_queue` | Unset, `1`, or invalid: existing latest-output slot. `2` or `3`: bounded FIFO for TCP PyroWave only. MediaCodec and UDP retain their policies. |
| `debug.q3pw.output_queue_max_age_us` | Positive source-timestamp age bound, 1–1,000,000 µs; unset/invalid defaults to **22,223 µs**, two 90 Hz periods rounded up. Ignored at depth 1. Set explicitly for other refresh rates. |

An explicit queue property emits `[Q3PW_OUTPUT_QUEUE] depth=.. max_age_us=..`
with effective ring size, workers and handoff state directly to logcat.
`decode_handoff=1` with a requested depth >1 logs a fallback to depth 1;
handoff waits for the previous copy submission and cannot fill a FIFO.
The existing one/two-worker policy is retained. Workers have independent rings;
late/equal ingress-order completions remain rejected as `decoded_out_of_order`.

Each accepted decode appends an output. A full FIFO drops only its oldest entry.
Publication also drops oldest entries whose source timestamp is strictly more
than the age bound behind the newly appended output. Both kinds of drop increment
`replaced_before_present` and telemetry `superseded`, once per discarded output.
Equal/regressed tracking keys do not trigger age-based drops. This is a relative
source-key bound, not a wall-clock timeout or a unique-image identity check.

The existing render polling stops after one successful dequeue, now the oldest
retained output. An empty queue repeats the previous image and retains its lease.
Pre-wait polling holds one selection without replacing it. Async eye-copy mode
still defers selection until its fence completes, even if outputs are waiting;
the comparison cells use synchronous copy. `should_render=false` does not consume
an output in the normal post-wait path. Source keys and selection IDs are not
retimed: `debug.q3pw.stats_source_ts=1` still repairs the display-clamp stats join.
Duplicate/expired tracking keys retain the limitations in FRAME-LOSS-DIAGNOSIS.

The native RGBA AHB ring grows only for effective depth >1: **depth + 2** buffers
per worker (3/4/5): pending outputs, one lease, one writable slot. The guard snapshots
every pending pointer plus the lease. A consumer may dequeue those during decode;
another worker can only publish from its own disjoint ring. The native compute
planes remain reusable scratch because decode/conversion finishes synchronously
before publishing the RGBA output. Descriptor pools already size from the ring.
Direct-eye synchronous copy and PyroWave staging both finish the source read before
lease replacement; async direct-eye fences gate selection. The optional import
cache holds eight entries and safely falls back to legacy import if two depth-3
workers expose more pointers. No cache capacity or staging allocation change is needed.

**Latency cost:** at 90 Hz, depth 2 can add up to one display period (~11.1 ms)
when two outputs are waiting; depth 3 can add two (~22.2 ms). This is queueing cost
at regular consumption, not an end-to-end latency guarantee during stalls.
Extra RGBA storage per worker versus depth 1 is `(depth - 1) × width × height × 4`
bytes before driver overhead. Observe pipeline p50/p95 and phase shifts alongside
fresh-copy rate; a higher rate with persistently older presentation may be worse.

## Hardware evidence and next cells

Owner-supplied 2026-10-06 evidence, installed **7705a40** pair, FOV-crop Haar,
500 Mbps, paced, three interleaved runs. Rates are completed eye copies/s:

| Cell | Runs | Mean |
|---|---|---|
| Control | 78.5, 84.9, 80.2 | 81.2 |
| `frame_wait_us=1000` | 85.7, 87.1, 87.3 | 86.7 |
| `runtime_display_time=1` | 85.3, 85.7, 83.9 | 85.0 |

Pipeline p50 alternated between ~40–46 and ~60–65 ms. Pacing off gave
90.0/89.8/90.0 copies/s but ~112 decoded/s: overproduction, not a queue fix.
These measurements predate this FIFO and do not establish its benefit.

Use `tools/quest3/frame_loss_profiles.py` for the entire snapshot/cell/capture/restore
cycle with the session25 harness, starting with `--dry-run`. The adapter includes
both new properties in the restore inventory. All cells use crop-only Haar,
500 Mbps, 90 Hz, one worker, handoff off, frame-loss counters and source-key repair.

| Variant | Depth | Wait µs | Runtime display time |
|---|---:|---:|---:|
| `loss-control500` | 1 | 0 | 0 |
| `queue2-500` | 2 | 0 | 0 |
| `loss-wait500` | 1 | 1000 | 0 |
| `queue2-wait-500` | 2 | 1000 | 0 |

Interleave at least three captures each, bracketing with controls and using a fresh
connection per run. Retain activation/fallback markers, logcat loss counters,
GraphStatistics and aligned telemetry deltas. Compare supersession, repeats,
completed eye copies, decoder queue age, pipeline latency and duplicate source
keys. `frame_loss_analysis.py` retains the same accounting; its
`decoded - superseded - copies` residual can now include changes in up to `depth`
pending outputs plus the selected/in-flight output. It is not an uncounted-loss
assertion. Depth 3, two workers, async copy and pre-wait polling are separate
follow-up cells, not part of the first comparison.

No hardware was run for this change. Runtime acceptance of 90 Hz, standalone
decode meeting 11.1 ms, and sustained distinct frames in live VR remain separate
claims; none is established by CPU checks or compilation of this experiment.

## Validation

- Focused pin/profile/analyzer checks: **20 passed, 4 subtests passed**.
- All **16 ALVR overlays** applied to the pinned base, matched the reconstructed
  tree byte-for-byte, reversed to a clean base, and reapplied identically. Every
  locked patch hash matched; both source and repository `git diff --check` passed.
- Actual session25 adapter dry-runs passed for both queue cells, control and
  snapshot; both queue properties appeared in the snapshot inventory.
- Five added Rust tests cover FIFO/empty-repeat leases, overflow and all protected
  pointers, strict stale catch-up/counts, source keys/worker order, and property
  bounds/handoff fallback. Existing depth-1 and handoff tests remain. Every changed
  Rust hunk and native FFI signature/call site was reread; no local Rust/C++ compiler
  is available. Rust tests, Android linking, full Actions build and hardware
  validation remain unrun. Nothing was committed.

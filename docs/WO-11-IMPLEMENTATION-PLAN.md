# WO-11 implementation plan — phase 1, 2026-10-06

## Owner decision and scope

The owner explicitly requested implementation on 2026-10-06, although the trigger
in [the design](WO-11-DUALSTREAM-H264-DESIGN.md) was only partly met. This is an
owner decision to investigate, not a claim that the original 700 Mbps trigger
passed. The owner-supplied T4 evidence is on `codex/t4-offline-500`, in
`results/offline-500-rescore-2026-10-06.md`:

| Offline proxy at 500 Mbps total | Fence PSNR dB | Temporal p99 | HVS dB |
|---|---:|---:|---:|
| Full-density dual-eye H.264 P7 | 45.14 | 6 | 46.25 |
| Single-stream H264Fit P7 | 46.26 | 5 | 36.82 |
| Best PyroWave: Medium / 9/7 / RDO24 | 37.27 | 16 | 35.58 |

Dual H.264 loses slightly to H264Fit on the leading fence metrics, but preserves
full Godlike density everywhere. H264Fit loses about 9.4 dB HVS in the periphery
in the owner's comparison. The owner records RTX 5080 H.264 NVENC caps of
4096x4096: the full 6144-wide stereo texture exceeds the width cap, whereas each
3072x3232 eye fits that recorded geometry. The existing dimension preflight must
still query the actual GPU for **each** future encoder; this work performs no GPU
query. The earlier [H.264](STOCK-H264-FOVEATION-AUDIT.md) and
[codec](WO-12-STOCK-CODEC-AUDIT.md) audits describe their earlier source boundaries;
the present base includes the later NVENC dimension-preflight overlay.

The revised candidate budget is **500 Mbps total, 250 Mbps per eye**, the measured
practical Wi-Fi budget supplied by the owner. The goal is 3072x3232/eye at sustained
90 fresh stereo submissions/s, with less compression than VD H.264+ at 500 Mbps.
Neither this quality proxy nor CPU tests establish that goal. Runtime acceptance,
standalone decode completion within 11.11 ms, and sustained live VR are separate
unverified gates. No defaults are promoted.

This work order authorizes phase-1 source and CPU/software checks only. No ADB,
installation, VR launch, GPU work, settings change, arm-file use, push or PR.
All probes below are **prepared specifications, not executed probes**. A future
owner-supervised session needs fresh readiness and separate execution authorization.

## Retire the unknowns before building the complete live path

| Risk, in priority order | Smallest future supervised probe | Required evidence / stop |
|---|---|---|
| Two concurrent Quest MediaCodec hardware H.264 decoders at 3072x3232 and 90 Hz | An isolated client probe with two independently labelled chart elementary streams, two codec instances and two ImageReaders; first configure/start both, then a short concurrent 250 Mbps/eye run. Extend only after acceptance. | Actual codec names/hardware status, SPS/profile/level, output dimensions, per-eye enqueue/output/completion, concurrent pair rate and resource cleanup. One decoder or software fallback fails. Configuration acceptance and the 11.11-ms completion budget are recorded separately; this is not a live-VR result. |
| Two simultaneous NVENC H.264 sessions at that geometry | An isolated synthetic left/right texture probe: query each cap, create both sessions atomically, submit one shared frame, then a short concurrent sequence with the 500/250 split. | Two distinct sessions, cap/format/preset/AQ/profile/level readback, bytes/eye, encode start/end and total completion, GPU/VRAM/CPU evidence. Failure of either destroys both. Driver session availability and timing are unknown. |
| Frame pairing and pose binding survive reorder/loss/reconnect | After the CPU tests, an isolated dual pipeline with charts carrying visible eye, frame, generation and pose IDs. Inject one missing eye and reconnect once. | Zero mixed generations/poses/frames, complete-pair-only selection, explicit paired/dropped/incomplete/late/resync counters, both queues flushed and both IDRs requested. Identity is provenance, not optical latency. |
| Each decoded eye reaches its own OpenXR image | After independent decoder acceptance, a supervised chart-only OpenXR pass using distinct solid colours, asymmetric arrows, frame counters and a seam pattern; then lose one eye deliberately. | Readback of each swapchain image and owner in-headset confirmation: left source to left image, right to right, no half-texture crop, stale eye or eye exchange; both images released together. Stop on black/flashing or incorrect stereo. No game launch. |

Before any future probe, prepare a complete settings/VD-state snapshot and rollback
receipt, verify the exact matching signed pair, and obtain owner readiness. Preserve
VD registration/services/settings and the active installation. A probe executable
and its cleanup must first pass CI; this table does not authorize running it.

## Actual reconstructed source map

Paths here are inside `ALVR-20.13.0` reconstructed at ALVR
`7eda092dbf0002281410a4222683ec228700cffb` plus the ordered overlays in
`tools/ci/fetch_sources.sh`. The branch base is `c7513be` (T1/T2/T3 plus the
dimension preflight). Upstream authors and credits remain intact.

| Area | Actual files and current boundary |
|---|---|
| Settings and dashboard | `alvr/session/src/settings.rs`, `beta.rs`, `beta_tests.rs`; `alvr/dashboard/src/dashboard/components/settings.rs` builds controls from `Settings::schema`, with `settings_controls/boolean.rs` and `settings_controls/presets/builtin_schema.rs`. Phase 1 adds a schema-generated visible boolean, not a live preset. |
| Negotiation and wire | `alvr/common/src/version.rs`, workspace `Cargo.toml`, `alvr/packets/src/lib.rs`; client/server `src/connection.rs`. Existing fork protocol ID is checked before streaming; capability and negotiated JSON are extensible. Existing `VideoPacketHeader` and VIDEO framing remain untouched. |
| Compositor/encoder | `alvr/server_openvr/cpp/platform/win32/CEncoder.{cpp,h}`, `FrameRender.{cpp,h}`, `VideoEncoderNVENC.{cpp,h}`, `NvEncoder.{cpp,h}`, `NvEncoderD3D11.{cpp,h}`; `alvr/server_openvr/cpp/alvr_server/Settings.{cpp,h}` and `HMD.cpp`. Today `CEncoder::Run` transmits one staging texture to one encoder. |
| Packetizer / FFI | `alvr/server_openvr/src/lib.rs::send_video`, `alvr/server_openvr/cpp/alvr_server/bindings.h`, `alvr/server_core/src/lib.rs::send_video_nal`, `src/connection.rs` video sender and `src/bitrate.rs`. Today the callback/channel/header have no eye identity and must not be repurposed implicitly. |
| Decoder creation and lifetime | `alvr/client_core/src/video_decoder/mod.rs::create_decoder`, `SelectedFrame`, sink/source and latest-frame publisher; `android.rs::video_decoder_split`, `decoder_attempt_setup`, `decoder_lifecycle`, `VideoDecoderSink::push_frame_nal`, `VideoDecoderSource::get_frame`. Today there is one MediaCodec/ImageReader path and timestamp-based output association. |
| OpenXR presentation | `alvr/client_openxr/src/lib.rs` event/frame loop; `src/stream.rs::StreamContext`, decoder setup, `render` and destructor. There are two XR swapchains fed from one decoded buffer. `alvr/graphics/src/stream.rs::StreamRenderer::render`, `staging.rs` and `direct_eye.rs` currently assume a stereo source; a per-eye AU cannot be passed into that API as if it were side-by-side. |

## Phases and gates

### Phase 1 — settings, compatibility, AU and pairing contracts (this change)

Add `video.dual_stream_h264=false`; standard profiles explicitly reset it off.
Requests require H.264, 8-bit SDR, both encoded and client-side foveation off,
TCP and constant total bitrate 5–500 Mbps with frame-rate adaptation off. Compute
the equal split in integer bits/s; keep the original single-stream bitrate path.
Native `[WO11_DUAL_H264]` markers report requested/effective/reason, and valid
requests also report framing version and total/left/right budgets.

Use fork protocol `20.13.0-ljk1291.3` (authority `fork.json`, reconstructed
workspace Cargo version aligned). This intentionally rejects previous fork/stock
peers even with dual off. Advertise the executable's compiled version on a cloned
session, so a saved pre-upgrade version cannot misidentify a standalone driver;
missing peer versions fail instead of being extrapolated. Dual requests require
identical full compiled build versions (including the stamped repository commit)
on both peers, in addition to the signed-artifact matching-pair gate. Additionally
require explicit AU version 1 when dual is
requested; missing, malformed, unsupported or request/effective mismatch is an
error. The client advertises **framing support**, not dual-decoder acceptance.
Single-stream negotiated JSON omits the new effective field. Existing VIDEO bytes,
encoder, decoder, renderer, shaders and timing policies remain unchanged.

Add `alvr/packets/src/dual_stream.rs`: a fixed 56-byte little-endian `DSH1` header:
magic/version, eye (0 left / 1 right), reserved-zero bytes, generation, shared
stereo frame, pose/prediction ID, independent per-eye AU ID, encode timestamp and
u32 byte count. Header parsing is separate from exact payload-length validation;
zero/oversized (>16 MiB) AUs and malformed headers fail closed. This header is
defined for a future complete AU on TCP, not added to the legacy NAL stream.

Add `alvr/client_core/src/stereo_pairing.rs`: generic owned eye handles, capacity
1–8 pairs and a caller-supplied common monotonic deadline. Key is
`(generation, stereo_frame_id, pose_id)`. Both eyes must be complete; selection
requires the oldest pending frame and its exact display prediction. Arrival may
be reordered within an eight-frame ID span, but per-eye AU order must agree with
stereo-frame order; the bounded span also rejects simultaneous frame/AU wrap while
a pair is pending. Duplicate,
wrong pose/ID/generation, byte mismatch, timeout (including an unselected complete
pair), capacity overflow, decoder fault, disconnect or clock regression flushes
the table and returns an explicit recovery requiring **both decoder queues flushed,
both IDRs requested, and a strictly newer generation**. No ID/generation wrap in
the same connection. `begin_generation` is called only after that recovery;
untrusted packet generations cannot advance the table. It resets pending handles
and retirement watermarks, not cumulative telemetry. Counts describe buffered
stereo frames dropped/incomplete, pairs released, and recovery causes.

Phase 1 deliberately refuses dual startup on both peers with
`effective=false reason=pipeline_not_implemented`, before server audio/stream
setup or OpenVR config/restart, and before client streaming/decoder setup.
There is no second encoder/decoder and no live pairing integration.

Tests: production Rust host tests for wire round-trip/malformed data, policy split,
version rejection, distinct eye/AU IDs, reorder, loss, duplicates/reuse, pose
mismatch, reconnect/generation rollback, wrap, deadline, queue bounds, faults and
clock regression. Cargo tests additionally cover actual JSON negotiation, default
settings/schema/profile resets and legacy bincode bytes. Python checks pin/apply
order, source guards, exact patch inventory and unchanged legacy source regions.

CI gate: the `tests` job compiles the two pure production modules via
`tools/wo11_contract_test.rs` with pinned rustc. Full `ci.yml` (`cpu_only=false`)
must pass `tests`, Android `client`, Windows `streamer` (existing Cargo package
tests) and `matching-pair`. Local source checks are not compilation evidence.
No phase-1 hardware gate is exercised; probes stay prepared.

### Phase 2 — atomic per-eye NVENC and TCP AU packetization

In `FrameRender` expose independently cropped full-density eye textures; in
`CEncoder`/`VideoEncoderNVENC` create two sessions under a separate dual owner.
Query each geometry with the base preflight before creation, require the supported
8-bit input, record actual profile/level (the audits found H.264 profile selection
is not yet proven), and split all average/max/VBV budgets from one total.
Use one compositor frame and pose ID, two distinct AU sequences and one shared
generation/deadline. Encoded output must preserve those associations through async
completion. Add a separate typed FFI callback and complete-AU channel in
`bindings.h`, `server_openvr/src/lib.rs`, `server_core/src/lib.rs` and the video
sender. Do not prepend dual headers to legacy `send_video_nal` output.

Tests: mock session-creation failure in either eye, texture geometry/eye identity,
budget sums, AU assembly across NALs, async completion order, paired IDRs, stale
generation shutdown and common backpressure. Recheck every C/Rust signature and
constructor. CI builds both platforms and verifies off-path/source shader
immutability. The smallest two-session synthetic GPU probe above is a separate
future gate. Keep the phase-1 refusal until a matching client path is ready.

### Phase 3 — atomic MediaCodec pair and identity-preserving decode

In client `connection.rs`, validate a complete dual AU before routing to the
correct sink; extend decoder config/control with explicit stream/generation.
In `video_decoder/mod.rs` and `android.rs`, create two hardware codecs and two
ImageReaders atomically. Resolve SPS dimensions and output format rather than
assuming the current 512x1024 MediaFormat hints prove the candidate size.
Record selected hardware codec and dimensions; disallow software fallback.

Keep a bounded per-eye mapping from an unambiguous codec presentation token to the
full AU header. The current code sends nanosecond values through a microsecond API
and tracking timestamps may be reused; neither timestamp nor callback order alone
is a stereo identity. Define and test token units/overflow, output timestamp
round-trip, drops and cleanup. Replace latest-frame overwrite for dual only with
identity-preserving output and the phase-1 pairing table. Propagate every recovery
to both codecs and server paired-IDR control; generation changes must retire all
old handles before output callbacks can publish again.

Tests: mock output reorder, repeated tracking timestamp, late callback after
teardown, ImageReader lifetime/buffer release, partial startup failure, input
capacity checks before native copies, output-format change and terminal faults.
CI compiles Android paths and host lifecycle tests. The standalone two-decoder
probe gates further presentation work; it cannot establish live VR. Keep live
startup unavailable until phase 4 is compiled and reviewed.

### Phase 4 — pair-aware OpenXR selection and separate eye imports

Extend `client_openxr/src/stream.rs` and its event loop to own a paired sink/source,
select one shared pose/prediction, acquire/wait both XR images, render both eyes and
release both together. Extend `graphics/src/stream.rs` with a dedicated paired-eye
input, importing each eye's full AHB with its own lifetime/fence and destination.
Audit `staging.rs`/`direct_eye.rs`: legacy half-width UV logic must never sample a
per-eye image. Retain existing colour/range rules and isolation; no foveation inverse
in this candidate. Never substitute one eye from a prior frame. If a complete pair
is unavailable, skip fresh submission; any allowed repeat must repeat an entire
previous stereo pair with its original pose and be counted separately.

Tests: software eye-labelled readback, exact swapchain routing, common deadline,
release-on-error and shutdown during import; mock pose/frame selection and repeated
pair provenance. Native per-eye ingress/decode/pair-wait/import/submit counters are
joined by generation/frame/pose, with pair freshness counted once. Full CI and
matching signed-pair verification precede the chart-only supervised probe. Remove
the phase-1 refusal only when this complete lifecycle is reachable safely under
the opt-in; single-stream remains the existing branch.

### Phase 5 — supervised qualification, no automatic default promotion

Off/on/off chart checks first, then a separately authorized owner gameplay
comparison with H264Fit, best PyroWave and VD H.264+ at the same 500 Mbps total,
scene and measurement window. Apply the design's Q4 moving network-rate rule,
fresh paired submissions, encoder completion, per-eye network/decode, pair wait,
compositor/queue latency, image/fence/HVS gates and endurance. Record battery,
thermal and fault stops, exact binaries/settings and verified restoration.
Optical latency requires independent instrumentation. Report separately whether
the runtime accepted 90 Hz, standalone decode met 11.11 ms, and live VR sustained
90 fresh stereo submissions/s. Only explicit in-headset owner sign-off may promote
a candidate. Failure leaves defaults and the active installation unchanged.

## Patch and evidence procedure

`patches/dual-stream-h264-phase1.patch` stacks last after T1/T2 and is SHA-256
pinned in `sources.lock.json`, validated by `source_lock.py` and checked before
application by `fetch_sources.sh`. Dependency/toolchain revisions stay fixed.
The overlay is generated from two isolated ignored reconstructions using
`git diff --no-index --binary --full-index --output=...`, normalizing only the
snapshot path prefixes. This includes new files without taking any Git index
lock. Verify clean forward apply, reverse check and byte-exact reconstructed files.
The [source evidence](../results/wo11-phase1-source-2026-10-06.json) records local
checks and pending CI; source checks do not certify compilation. Work remains
uncommitted because the linked worktree's external Git index is unavailable.

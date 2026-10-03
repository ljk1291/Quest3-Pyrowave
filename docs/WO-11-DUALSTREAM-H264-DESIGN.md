# WO-11: per-eye dual-stream H.264 design

This is a design note only. The current pinned ALVR stack carries one stereo video
stream; it has no per-eye stream IDs, independent loss recovery, or stereo pairing
contract. No client, server, packet, or default-setting behavior changes here.

## Trigger

Implement only after Q3 shows that full-density per-eye H.264 at 700 Mbps clearly
beats both stock one-stream `h264fit` and the best PyroWave candidate on fence
metrics first, then HVS, while meeting the live rate and latency constraints. A
proxy score or single-eye encode does not meet that trigger.

## Wire, pose, and scheduling contract

Each access unit carries `stream_id` (left/right), a shared `stereo_frame_id`, an
encoder-generation ID, byte count, a per-eye encode timestamp, and an independently
monotonic access-unit ID. The server submits both eyes from one compositor frame and
binds them to one pose/prediction ID. It records per-eye encode start/end, packet-byte
counts, and pose association. The client holds a bounded pairing table keyed by
`(generation, stereo_frame_id, pose_id)` and releases only a complete pair for the
same display prediction.

The client must never display a new left eye beside an old right eye. An unmatched
eye, timeout, duplicate/mismatched ID, decoder fault, or pose mismatch drops the
whole stereo frame. It never reuses a wrong frame. Loss/reconnect resets generation,
flushes both decoder queues, and requests an IDR for both streams.

## Transport, queues, and resources

Keep TCP until a separately authorized transport experiment changes it. The protocol
needs a matching server/client pair and an explicit version negotiation before video;
old clients or servers fail compatibility rather than guessing a framing layout.
Backpressure uses one common stereo deadline. Each eye's network delivery, decoder
output, pair wait, compositor submit, and display selection are reported separately.
Frame identity proves provenance, not optical latency.

Two H.264 NVENC sessions encode 3072x3232 eyes in parallel. Preflight verifies each
stream remains within the 4096-pixel NVENC side limit and logs profile, level, preset,
AQ, bit depth, bitrate allocation, GPU encoder utilization, VRAM, and CPU use. The
700 Mbps Q3 value is total until a later plan explicitly changes the split. Two Quest
decoder sessions require capability confirmation; one session or a software fallback
invalidates the comparison.

## Lifecycle and error handling

Startup creates both encoders, transport tracks, and decoders atomically. A failure
in either eye tears down both, reports the failed stage, and reconnects only through a
new generation. Shutdown drains neither stale eye into a later generation. Protocol,
encoder, decoder, and stream-layout changes require a new matching signed pair; no
mixed installed builds are accepted.

## Quality and timing gates

Before headset work, test deterministic distinct left/right charts, out-of-order
delivery, one-eye packet loss, reconnect during an incomplete pair, decoder failure,
ID wrap, and generation change. Require zero cross-eye swaps, no stale-eye
presentation, bounded pair queues, and explicit paired/dropped/incomplete/late/resync
telemetry. Frame-bank input and output retain side-specific identities.

Live qualification compares full-density dual stream with `h264fit` and the best
PyroWave Q3 candidate at the same scene. It separately measures encoder wall and
completion time, network delivery, decode, pair wait, fresh submissions, and optical
claims only with independent instrumentation. It must pass the Q4 moving network
rate rule, image/fence quality, sustained fresh-rate, latency, and owner review gates.
This design does not authorize headset, network, SteamVR, or installed-pair changes.

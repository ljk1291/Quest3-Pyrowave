# WO-6/7: actual PyroWave bitplane bound and receive-order model

This CPU-only, read-only analysis parses a retained 90-frame PyroWave `.wave`
container. It did not invoke an encoder, decoder, GPU query, device, network
test, or entropy coder. The report intentionally omits the private artifact
location; its SHA-256 is
`3136947417471628466e3b082bdb5dc834195a62063712475d425f3ec043c3d4`.

## Actual serialized bitplanes

`tools/xrbench/pyrowave_bitplanes.py` validates the native serialized layout
rather than estimating entropy from another corpus. Its contract follows the
pinned source definitions in `pyrowave_common.hpp` (`BitstreamHeader` and
`BitstreamSequenceHeader`) and the parser in
`pyrowave_encoder.cpp::Encoder::Impl::validate_bitstream`:

- a `.wave` container has `PYROWAVE`, eight signed 32-bit container fields,
  then length-prefixed full-frame payloads;
- each payload begins with an extended sequence header, followed by strictly
  increasing active 32x32 block records;
- a block has its 8-byte header, `N = popcount(ballot)` 16-bit controls, `N`
  8-bit Q/quant controls, plane bytes, a significance-derived sign tail, and
  up to three alignment bytes.

The retained input parsed completely: 90 frames, a 5248x2776 4:2:0 full-range
container at a declared 90/1 rate, CDF 9/7 sequence code 0, and 4,462--7,264
active blocks per frame. Payloads total 124,995,088 bytes (1,388,744--
1,388,888 per frame). The byte-class accounting below covers every payload
byte exactly.

| Serialized class | Bytes |
| --- | ---: |
| Sequence headers | 720 |
| Block headers | 4,315,880 |
| Controls | 17,284,161 |
| Actual bitplane symbols | 83,689,797 |
| Sign tails | 18,887,600 |
| Alignment padding | 816,930 |
| Total payload | 124,995,088 |

The parser builds byte histograms by plane ordinal and by the available native
control context: the `q_bits` nibble plus plane ordinal. The latter zero-order
Shannon `H0` model gives 72,190,793.77 bytes for the 83,689,797 actual
bitplane bytes (86.26% of the raw plane bytes), a theoretical
11,499,003.23-byte, 13.74% difference **within plane symbols only**. It uses
existing controls and needs no new side data, but it remains a model rather
than a coder. Plane ordinal alone gives 72,778,515.59 bytes; pooling all plane
ordinals gives 74,683,766.12 bytes. The first three plane ordinals carry
36,164,683, 24,068,621, and 13,358,894 bytes respectively, with `H0` values
6.1540, 7.3005, and 7.7704 bits/byte; later planes are close to 8 bits/byte.

This is a coding headroom model, not a predicted saving. It excludes headers,
controls, signs, framing, model signalling, context selection, tails, and
decoder work. No entropy-coded stream or timing measurement exists, so the
analysis does not claim emitted-size reduction, throughput, quality, or
latency improvement.

The parser has synthetic CPU tests for byte-class coverage and rejects malformed
lengths, inconsistent block words, and sequence mismatches. It writes a
sanitized JSON result with the input hash and no source path.

## Receive order

`pyrowave_encoder.cpp::Encoder::Impl::packetize` writes the sequence header
then iterates non-empty 32x32 blocks in ascending block-index order. It has no
coarse/fine packet ordering. The retained transport contract remains
whole-frame:

1. One complete codec frame is encoded.
2. The UDP form divides its bytes into payloads no larger than 1368 bytes.
3. The receiver reassembles every fragment.
4. A missing fragment drops the frame; only a complete frame is pushed once
   into the codec.

The receiver has bounded assembly state, holds a latest complete frame, and
may replace older complete work. It does not expose partial codec input. Thus
changing the current block order cannot make the decoder start sooner; it can
only move bytes earlier inside a frame. No wire-packet arrival trace was used,
so this section has no timing result.

For a frame `f`, retain the model:

```
complete(f) = max(arrival(f, fragment_i)) over all required fragments
decode_start(f) = max(complete(f), decoder_available)
present(f) = runtime-selected display time after decoding
```

A future layered design must add a versioned packet map containing frame,
layer, band/block range, required coarse set, and checksum; then independently
measure completeness, quality under missing fine data, decoder readiness,
queue replacement, and display age. Until then, retain the complete-frame gate
and do not call a proposed packet order a latency improvement.


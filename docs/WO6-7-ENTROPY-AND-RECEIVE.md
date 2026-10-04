# WO-6/7: entropy bound and receive-order model

This is a CPU-only analysis of retained artifacts. It does not run an encoder,
receiver, GPU query, device, or network test.

## What the retained artifacts say

The CDF 9/7 research rows in
`captures/decoder-experiments/mathlab/rd.csv` are not captured PyroWave
packets. They are quantised coefficient bands measured offline, with two
derived size functions:

- `bytes_bitplane`: the existing raw bit-plane packing model.
- `bytes_entropy`: zero-order Shannon entropy of each quantised band.

At the 416,667-byte cap and 2560-square source, the four Kodak rows have a
mean raw-model size of 416,634 bytes and a mean zero-order entropy value of
242,012 bytes. The 174,621-byte gap is 41.9% of the raw model. The synthetic
panel has 416,408 raw-model bytes and a 460,993-byte zero-order entropy value.

The zero-order value is an upper bound on the unknown entropy rate when
cross-symbol structure is allowed. It is not emitted size, a decoder-cost
estimate, or a predicted saving. The Kodak gap cannot be reported as bytes
available to a new coder: packet/block headers, framing, code tables, context
choice, tail behavior, and decoder work are all outside this calculation. The
synthetic row also shows why an entropy result cannot be assumed to improve
the existing raw bit-plane representation.

No retained artifact exposes native bit-plane payload records with band,
plane, block, and bit count. A parser for *actual* bit planes therefore cannot
be truthfully run from this checkout. The required input is a per-frame,
lossless coefficient/bit-plane trace from the native packetizer, including
the exact source and packer identity. Once present, report raw payload bytes,
per-band symbol counts, `H0`, headers, and any coded bytes separately.

## Receive order

The retained transport contract is whole-frame:

1. One complete codec frame is encoded.
2. The UDP form divides its bytes into payloads no larger than 1368 bytes.
3. The receiver reassembles every fragment.
4. A missing fragment drops the frame; only a complete frame is pushed once
   into the codec.

The receiver has bounded assembly state, holds a latest complete frame, and
may replace older complete work. It does not expose partial codec input. Thus
a coarse-to-fine wire order cannot make the current decoder start sooner. It
can only change which bytes arrive earlier inside a frame; without partial
decode or quality-layer acceptance, completion still occurs at the last
required fragment.

For a frame `f`, retain the model:

```
complete(f) = max(arrival(f, fragment_i)) over all required fragments
decode_start(f) = max(complete(f), decoder_available)
present(f) = runtime-selected display time after decoding
```

This model deliberately makes no claim about a duration. Existing latency
telemetry partitions the input-acquisition-to-predicted-display interval; it
does not measure a proposed packet-order change. A future layered design must
add a versioned packet map containing frame, layer, band/block range, required
coarse set, and checksum; then independently measure completeness, quality
under missing fine data, decoder readiness, queue replacement, and display
age. Until then, retain the present complete-frame gate and do not call
coarse-first ordering a latency improvement.


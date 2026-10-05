# PyroWave entropy and receive order — CPU analysis

**Complete:** yes, for parser accounting and byte-prefix arithmetic only. This
is not an encoder, decoder, GPU, device, transport, or timing result.

## Provenance and method

The retained 90-frame CDF 9/7 stream has SHA-256
`3136947417471628466e3b082bdb5dc834195a62063712475d425f3ec043c3d4`.
The parser method is `tools/xrbench/pyrowave_bitplanes.py` at reviewed harness
revision `cd55b93cd34f8fae782e259d86162e0775d9f42a`. It validates the `.wave`
container framing and each native block's header, control, plane, sign-tail,
and word-alignment layout. Its synthetic tests reject malformed frame lengths,
block word counts, and sequence mismatches.

The source attribution was corrected to the locked PyroWave base
`d2997ac172bdc00e29c58e3f2938acb7e94580bf`. The matching-pair Windows
build binds repository commit `80a16353ca127508fec745dec53dc790ceb77fb2`,
sources-lock SHA-256
`f8510aa72b713ca658475bab0956c98f3adf98b1962b553c781bdc62e5e7bbb0`,
build-metadata SHA-256
`53cbcfdeb0ef4f379a2d5a89190794213618c3aa7deeb15090a5655e916a6064`,
tools-metadata SHA-256
`602bce856cd45b0efac49a112e6e49f5ff2fdde204536270d14b60fb5f5577d1`,
and its reviewed RDO-density and centre-phase overlays. `pyrowave_common.hpp`
defines `BitstreamHeader` and `BitstreamSequenceHeader`; the locked base
validates serialized blocks in `pyrowave_encoder.cpp`, packetizes non-empty
metadata in increasing block index, and establishes block ranges in
`WaveletBuffers::init_block_meta()`. Review of the matching-pair overlay list
shows the CDF 9/7 start-of-frame path retains the base code and that the block
metadata loop is unchanged. This supports the parser prefix mapping only for
the retained CDF 9/7 stream; it makes no source-equivalence claim for Haar or
CDF 5/3 overlays.

## Measured bytes and restricted entropy model

The 90 payloads total 124,995,088 bytes: 83,689,797 bitplane bytes,
18,887,600 sign bytes, 17,284,161 control bytes, 4,315,880 block-header bytes,
720 sequence-header bytes, and 816,930 alignment bytes.

The restricted zero-order model conditions only on the already serialized
`q_bits` nibble and plane ordinal. It gives 72,190,793.77 bytes for bitplanes,
a 11,499,003.23-byte difference: 13.74% of bitplanes and **9.20% of full
payload**. It is an upper-bound model, not an emitted size or a predicted gain.
Huffman/table coding has table and branch cost; rANS requires tables,
renormalisation and parallel streams; contextual arithmetic coding has serial
dependencies and possible GPU-decode cost. No decode cost or coded stream was
measured.

## Receive-order facts and limits

`WaveletBuffers::init_block_meta()` orders decomposition level 4 through 0,
then component and band. `packetize()` emits non-empty blocks in increasing
index. The initial contiguous luma level-4 ranges are therefore received in this
order:

| Prefix through luma level-4 band | Bytes over 90 frames | Payload share | Ideal 1000 Mb/s serialization/frame |
| --- | ---: | ---: | ---: |
| 0 (LL) | 2,017,636 | 1.61% | 0.179 ms |
| 1 | 3,116,048 | 2.49% | 0.277 ms |
| 2 | 4,220,024 | 3.38% | 0.375 ms |
| 3 | 5,123,060 | 4.10% | 0.455 ms |

The mean 1,388,834-byte frame is 11.111 ms at that ideal byte rate.

Those are byte/rate calculations only. No retained artifact matches packet
arrival timestamps to these block ranges or measures decoder work per range.
The current complete-frame API exposes zero usable decode overlap. A proposed
partial design would be bounded by `min(actual_stage_work, remaining_transfer)`
until both terms are measured.

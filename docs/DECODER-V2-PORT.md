# Decoder V2 / haar32 port candidate

Source port from **JMS1717/Quest3-Pyrowave** commit
`adeb86b83f2d23333faeb315105f164a198271b8` (MIT), using its DECODER-V2,
HAAR32, PRESENT-YCBCR and ENCODER-CSF work. Original PyroWave/Granite credits
remain intact. The inverse shader sources retain upstream's copyright notices.
Our PyroWave pin remains `d2997ac172bdc00e29c58e3f2938acb7e94580bf`.

**Not ready to build until the shader fold below.** No native compiler, shader
compiler, device, GPU or network was used for this port. The checked-in library
and client generated headers still describe the preceding stack; manifest checks
deliberately reject them. No new default or performance claim is established.

`pyrowave-decoder-v2.patch` applies after our research, Quest, three RDO and
fast53 overlays. `alvr-decoder-v2.patch` applies after the complete ALVR stack,
including frame dumps, output queue and fast ABR. Earlier patches are unchanged.
Both overlays are listed and hashed by `sources.lock.json` / `source_lock.py`.

Offline validation: all 7 PyroWave and 18 ALVR patches apply to clean archives of
their pinned local Git objects; reconstructed files match the edited trees byte
for byte. New overlays reverse/reapply, and the shader workflow's fast53 reversal
and immutable-control check pass. The focused Python suite passed **75 tests and
15 subtests** (port, fast53, CI pins, build metadata, RDO wiring and bench properties).
Both stale shader gates were also checked and reject the pending fold as intended.

## Controls and behavior

Android properties are sampled at decoder creation; reconnect after changing them.
Invalid/unset mode values select 0. These switches select a decoder, not a wavelet;
the server must encode the matching Haar or CDF 5/3 stream.

| Property | Values | Default |
| --- | --- | --- |
| `debug.q3pw.cdf53v2` | 0–5 | 0, disabled |
| `debug.q3pw.haar32` | 0–5 | 0, disabled |
| `debug.q3pw.packed_levels` | 2 or 4 | 4; only affects enabled packing |

| Mode | CDF 5/3 V2 | Haar32 |
| --- | --- | --- |
| 1 | Register inverse, one pass per level | Multilevel inverse, two passes per plane |
| 2 | Also packed luma output | Also packed coefficients |
| 3 | Also packed coefficients | Also packed luma output |
| 4 | Also dual Cb/Cr output | Also dual Cb/Cr output |
| 5 | Also packed YCbCr presentation | Also packed YCbCr presentation |

Coefficient packing covers levels 0–3 (or 0–1 with the value 2). Packed coefficients
require precision 1. Haar32 requires 4:2:0 and excludes fused Haar. V2 modes 4–5
require 4:2:0. All accelerated modes require compute. Packed outputs require even
dimensions; mode 5 requires dimensions divisible by four, full range, and an AHB
that can be imported for storage writes. Unsupported requests step down through
lower modes; AHB allocation/import failure specifically retries mode 4. V2 takes
priority over a simultaneous fast53 request; fast53 remains available otherwise.

Markers are `[Q3PW_CDF53V2] requested=N active=M reason=... packed_levels=L`,
`[Q3PW_HAAR32] ...`, `[Q3PW_PRESENT_YCBCR] active=... reason=...`, and the existing
`[Q3PW_FAST53]`. Reasons include `disabled`, `wavelet`, `fragment`, `limited_range`,
`decoder_precondition`, `no_ahb_storage`, and `ahb_allocation_or_import`.
Property snapshots record requests; only native markers establish activation.

Mode 5 writes one RGBA8 AHB at full stereo width and half height: left half holds
2×2 Y quads; right half holds Cb/Cr in RG. At the crop this is **5248×1376** for
**2624×2752 per eye**. ALVR recognizes this layout using decoded dimensions, then
converts full-range BT.709 in direct-eye, staging and post-decode dump shaders.
WO-8/T1 UV mapping, FIFO leases and protected-buffer selection are retained.
Mode 5 skips the Vulkan conversion dispatch (`convert_ms=0`); ownership acquisition
precedes decode and release follows it. Frame dumps remain full-sized RGB with
their existing stages/timestamps. `pyroclient_test` accepts timing-only `-` in
mode 5 and refuses to label raw packed data as an RGB dump.

For the PC encoder, set **`PYROWAVE_HEADSET_CSF=1` in the streamer process environment**
before encoder creation. Every other value is off. No persistent setting is added.
Enabled weighting uses `cpd_nyquist = 0.5 * height / 99`, LF amplitude ×6 at levels
≥3, chroma amplitude 1.6 (retaining the coarsest-band exception), and the band
distortion weight for discarded coefficients. It overrides the selected RDO density
after existing configuration validation; library readback and the server's
`[Q3PW_HEADSET_CSF] requested=... active=...` marker report that override. Off keeps
the existing RDO behavior and quantizer variant. Packet/bitstream format is unchanged.

## Exact CI and shader fold handoff

The planner must publish the reviewed source candidate; this implementing agent
leaves it uncommitted. A push changing `shaders.yml` on `codex/decoder-v2` triggers
regeneration. If dispatch is available on the default branch, use:

```powershell
gh workflow run shaders.yml --ref codex/decoder-v2
gh run list --workflow shaders.yml --branch codex/decoder-v2 --limit 5
gh run watch <shader-run-id> --exit-status
gh run download <shader-run-id> -n PyroWave-generated-shaders -D out/decoder-v2-shaders
```

The workflow builds the pinned Granite slangmosh, reverses V2 then fast53 to obtain
the prior headers, verifies the existing 18 fast53 permutations, reapplies both,
and regenerates. The new gate requires all existing inverse/encoder kernels
(including CSF-off) to remain byte-identical, except specialization-modified dequant;
it also checks 24 new inverse permutations for workgroup storage/barriers. Pinned
NDK glslc regenerates the three client conversion headers. Do not bypass these gates.

Use the prepared `ws/decoder-v2/pyrowave` tree, whose **index is the complete
pre-port stack** and whose new shaders already have intent-to-add entries. Do not
stage its working tree before generating the overlay. Run from this worktree root:

```powershell
$portRoot = (Get-Location).Path
$pw = Join-Path $portRoot 'ws/decoder-v2/pyrowave'
$overlay = Join-Path $portRoot 'patches/pyrowave-decoder-v2.patch'
Copy-Item out/decoder-v2-shaders/slangmosh.hpp,out/decoder-v2-shaders/quest3-manifest.json -Destination "$pw/shaders"
Copy-Item out/decoder-v2-shaders/pyroclient/convert_vert_spv.h,out/decoder-v2-shaders/pyroclient/convert_frag_spv.h,out/decoder-v2-shaders/pyroclient/ycbcr_to_rgba_spv.h,out/decoder-v2-shaders/pyroclient/shader-manifest.json -Destination tools/pyroclient
python tools/ci/check_shader_manifest.py $pw
python tools/pyroclient/compile_shaders.py --check
git -C $pw diff --binary --full-index --output=$overlay
git -C $pw apply --check -R $overlay
python -c "import hashlib,json;from pathlib import Path;p=Path('sources.lock.json');d=json.loads(p.read_text());q=d['patches']['pyrowave_decoder_v2'];q['sha256']=hashlib.sha256(Path(q['path']).read_bytes()).hexdigest();p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')"
python -m pytest tools/tests/test_decoder_v2_port.py tools/tests/test_fast53.py tools/tests/test_ci_pins.py tools/tests/test_build_metadata.py -q
```

If that scratch tree is unavailable, reconstruct with `fetch_sources.sh`, reverse
only `pyrowave-decoder-v2.patch`, stage that base in its own scratch Git index,
reapply the overlay, and `git add -N shaders/idwt_haar32.comp shaders/idwt_cdf53v2.comp`
before the same fold. Never regenerate an earlier overlay against the new stack.
Client manifest hashes normalize CRLF/LF; library artifacts retain their LF bytes.

After reviewing, committing and pushing the fold, run:

```powershell
gh workflow run ci.yml --ref codex/decoder-v2 -f cpu_only=false
```

Require tests, client, streamer and matching-pair. CI includes C++ mode-selection
and CSF tests plus Mesa software GLES tests for packed RGB dumps and both eyes
through staging/direct rendering. Native/GLSL compilation has not run locally.

## Planner's device test plan (separate authorization)

1. Run `pyrowave_android --compare-v2 cdf53.wave haar.wave <prefix> 30` on matching
   8-bit 4:2:0 files (first frame, dimensions divisible by four), with
   `PYROWAVE_PRECISION=1`. Repeat with both `PYROWAVE_V2_PACKED_LEVELS` and
   `PYROWAVE_HAAR32_PACKED_LEVELS` set to 2, then 4. Each of 12 fresh processes
   performs five warmups, reports mean GPU decode milliseconds, and dumps unpacked
   Y/Cb/Cr. Each mode is compared to its own wavelet's stock decode: per-plane
   maximum/mean code-value differences, max ≤1 gate. Exit 0 passes, 2 fails parity,
   1 reports an execution/input error. Decode timing excludes readback and conversion;
   this does not test AHB interop. Sequential runs need clock/thermal controls.
2. Use the matching CI pair: off/on/off for both wavelets, modes 1–5, precision
   fallback, limited range, both packed-level choices, crop 2624×2752/eye, output
   queue 1/2/3, direct/staging, then foveation. Check markers, protected-buffer
   behavior, dumps, eye seams/orientation and validation errors. First compare
   mode 5 against mode 4; RGB rounding/filtering differs from a separate conversion
   pass, so plane parity alone cannot qualify presentation.
3. CSF off/on/off with identical retained frames, rate cap and other RDO controls;
   compare quality, bytes and encode tails before any live promotion. Upstream's
   reported timings are motivation, not measurements of this port.

Runtime acceptance of 90 Hz, standalone decode budget and sustained live VR are
**separately unverified**. The harness labels a mean under 11.111 ms as
`within_mean_only` and always prints `live_vr=unverified`. Default shader branches,
Adreno AHB storage/foreign ownership, mode-5 foveation/filtering and encoder quality
remain validation risks. Upstream mode 6, cost probes, prerecord/fused-dequant paths
and `decoder_ab` were not imported; that harness depends on those additional APIs.

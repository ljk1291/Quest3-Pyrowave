# WO-6 pair-local CDF 5/3 candidate

The v2/v3 follow-up on `codex/fast53` keeps the measured v1 (`f977193` +
`74a3a3b`) and apron paths as controls. This follow-up used no compiler, network,
ADB, device or GPU. v2/v3 are **unmeasured experiments**, default off.

Planner-provided Quest 3 evidence for v1, precision 1, real stereo 5248x2752
C420 chart at a 750 Mbps budget:

- Standalone parity passed: max 1 code value in every plane; mean absolute
  differences Y/Cb/Cr = 0.0053 / 0.0005 / 0.0007.
- GPU decode: apron53 12.59 ms, v1 10.13 ms, Haar 6.13 ms. v1/Haar = 1.65,
  failing the 1.3x standalone target (about 7.97 ms at that Haar timing).
- Live v1: 74.1 fresh/s, GPU decode 10.9 ms, decode-to-fence 12.8 ms. Apron:
  62 fresh/s at 13.0 ms; Haar: about 90 fresh/s at 5.9-7.5 ms. The reported
  live v1 result fails sustained 90 fresh/s; it is separate from runtime rate
  acceptance. No new runtime-rate or Metro visual acceptance is established.

`patches/pyrowave-fast53.patch` stacks last on the pinned PyroWave overlays.
`debug.q3pw.fast53=1|2|3` selects v1/v2/v3 only for CDF53 + Compute. Unset, `0`
and all other strings select the original path. `PYROWAVE_FAST53` behaves the
same in the standalone harness. The marker reports requested and active variant:
`[Q3PW_FAST53] requested=3 active=1 variant=3 reason=enabled`.
The managed-property snapshot retains the exact raw value and recognizes all
three values as experiments.

The additive `pyrowave_decoder_set_fast53_variant(decoder, variant)` API accepts
0..3 and rejects enabling outside CDF53 + Compute. The old
`pyrowave_decoder_set_fast53_enabled` API retains its 0/off, nonzero/v1 meaning.
No create-info ABI changes. Existing Haar/CDF97 dispatch and arithmetic stay
unchanged; v1 retains its 16x16-pair workgroup and exact shader source. v2/v3
use 64 invocations covering 32x32 pairs, with the matching host dispatch divisor.

Arithmetic was checked against reconstructed `shaders/idwt.comp`:

- `load_image_with_apron`, `generate_mirror_uv` and `write_shared_4x4` map
  layers LL=0, first-axis high=2, second-axis high=1, HH=3. Those axes are
  **transposed**: the first lift is image-vertical; native image x-high is
  layer 1 and y-high is layer 2. This agrees with `inverse_haar_pairs`.
- `inverse_transform8x2` and `inverse_transform4x2` undo update before predict:
  `e[i] = low[i] - .25 * (high[i-1] + high[i])`, then
  `o[i] = high[i] + .5 * (e[i] + e[i+1])`. No K scaling and no rounding
  between these two lifting steps at precision 1/2.
- Round on initial gather storage, after the complete first-axis lift, and
  after the complete second-axis lift, before DCShift. `dwt_common.h`
  defines precision 0 as FP16 arithmetic/storage, 1 as FP32 arithmetic/FP16
  storage and 2 as FP32 throughout. Initial rounding matters for precision 1's
  coarse R32 coefficient images. `fast53_store` follows `haar_intermediate`.
- Match the mirror sampler by applying `generate_mirror_uv`'s adjustments at
  each **even gather origin**, selecting the `.wxzy` lane, then mirroring.
  Simple coefficient clamping is not equivalent. The CPU proof includes both
  borders, corners, odd coarse dimensions and partial output tiles.
- DCShift remains after final shared-store-equivalent rounding, on the same
  final levels (Y level 0; C420 Cb/Cr level 1). Intermediate image formats and
  inter-level dispatch barriers remain the original library's.

v2/v3 retain the arithmetic above, including raw FP32 horizontal updated evens
until prediction in precision 1. Only completed first-axis columns use FP16
register storage (when FP16 is supported and precision != 2). Fallback storage
uses the same explicit half round-trip as v1. There is no additional rounding.

| Variant | Pairs / invocation | Texture instructions / full block | Instructions / output pixel | Rough p1 live-register estimate |
|---|---:|---:|---:|---:|
| v1 | 2x2 | 49 scalar fetches / 16 pixels | 3.0625 | 40-64 |
| v2 | 4x4 | 121 scalar fetches / 64 pixels | 1.890625 | 40-64 |
| v3 | 4x4 | 36 gathers / 64 pixels | 0.5625 | 48-80 |

Register estimates are **32-bit-equivalent per-thread working-set estimates**,
including temporaries and addressing, not compiler/Adreno register counts.
Half-register packing and instruction scheduling are unverified. Precision 2 or
lack of FP16 support increases pressure. Partial blocks have higher cost per
retained output pixel.

4x4 is chosen over 2x4 because streaming columns keeps only the current/next
horizontal dependencies live instead of a 121-value register tile. v2 rolls
one column at a time. v3 loads two columns at a time and consumes old values
before the next pair arrives. Neither introduces shared storage or barriers.
The expected ranking is **v3, then v2, then v1** if register allocation does not
spill; v3 is the highest register-pressure risk. No claim of 90 Hz or <=1.3x is
made before device testing. No v4 is added without Adreno evidence favoring it.

v3's three 2x2 gathers per axis/band load 144 scalar texel slots for the 121
required coefficients (2.25 fetched slots/pixel). Its texture instruction count
is 3.36x lower than v2's, not a claim of 3.36x GPU speedup. Low-band gather
origins are even (0,2,4); high-band origins are odd (-1,1,3), avoiding a fourth
halo gather. The exact `generate_mirror_uv` arithmetic and `.wxzy` swizzle are
retained. At a crossed mirror point the duplicated endpoint makes these odd
high-band gathers equal to selecting lanes from the original even-origin
mapping. Tests check every gathered lane, including unused lanes, tiny/odd
images, both borders and corners. This addressing and GPU precision remain
part of the <=1-code readback gate.

Local validation: all 10 `python -m unittest tools.tests.test_fast53 -v` tests
pass, including unchanged v1, v2/v3 2D parity/coverage, texture instruction counts,
coarse 164x86 geometry, impulse/rounding cases and shader permutation checks.
The native policy test now covers 48 property/wavelet/path combinations in CPU
CI. All 31 `python -m unittest tests.test_bench -v` tests also pass, including raw
managed-property values for all three variants (41 local CPU tests total).
C++ and GLSL compilation remain CI-only.

## Planner: regenerate, fold in, then build

The current patch intentionally leaves `slangmosh.hpp` and
`quest3-manifest.json` stale. **Do not run full CI before folding regenerated
artifacts in.** The new selection requires generated `idwt[3][4]` (24 permutations, 18 fast).
`check_shader_manifest.py` already covers every changed shader input, including
`dwt_common.h` and `slangmosh.json`; no new manifest filename is needed.

After reviewing, committing and pushing this handoff (including the harmless
workflow comment change) to `codex/fast53`, `shaders.yml` runs automatically
because that workflow file changed. This trigger is retained because dispatch
requires the workflow on the default branch. From this worktree:

```powershell
# Alternatively, if workflow_dispatch is available:
# gh workflow run shaders.yml --ref codex/fast53
gh run list --workflow shaders.yml --branch codex/fast53 --limit 5
# Use the run ID for the source commit just pushed:
$shaderRun = <run-id>
gh run watch $shaderRun --exit-status
gh run download $shaderRun --name PyroWave-generated-shaders --dir out/fast53-v23-shaders
```

`shaders.yml` temporarily reverses this additive patch to recover the original
pinned header, reapplies the patch, then compiles all variants. The new
`check_fast53_shaders.py` gate requires byte-identical default SPIR-V and
compares v1 with frozen hashes from measured commit 74a3a3b. It verifies exactly
24 idwt permutations and checks all 18 fast modules for `OpControlBarrier`,
`OpMemoryBarrier` and Workgroup variables. Investigate any failure; do not bypass the default-binary gate.

The ignored reconstructed tree `ws/fast53-pyrowave` has the pre-change stack
committed as local baseline `dbe4679381d47723fef3c4f8a0f706f46f6f0544`; its index
still holds that baseline. It was archived offline from pinned d2997ac and
normalized to LF before applying the exact existing overlay order. Fold in:

```powershell
$pw = Join-Path (Get-Location) 'ws/fast53-pyrowave'
$overlay = Join-Path (Get-Location) 'patches/pyrowave-fast53.patch'
Copy-Item -LiteralPath out/fast53-v23-shaders/slangmosh.hpp -Destination "$pw/shaders/slangmosh.hpp"
Copy-Item -LiteralPath out/fast53-v23-shaders/quest3-manifest.json -Destination "$pw/shaders/quest3-manifest.json"
python tools/ci/check_shader_manifest.py $pw
git -C $pw diff --full-index --binary "--output=$overlay"
@'
from pathlib import Path
import hashlib, json
p = Path('sources.lock.json')
d = json.loads(p.read_text())
d['patches']['pyrowave_fast53']['sha256'] = hashlib.sha256(Path('patches/pyrowave-fast53.patch').read_bytes()).hexdigest()
p.write_text(json.dumps(d, indent=2) + '\n', encoding='utf-8', newline='\n')
'@ | python -
git -C $pw apply --check -R $overlay
python -m unittest tools.tests.test_fast53 -v
# Review, commit and push the folded patch + lock, then:
gh workflow run ci.yml --ref codex/fast53 -f cpu_only=false
gh run list --workflow ci.yml --branch codex/fast53 --limit 5
$ciRun = <full-ci-run-id>
gh run watch $ciRun --exit-status
gh run download $ciRun --name Quest3-Pyrowave-Android --dir out/fast53-v23-android
```

If reconstructing elsewhere, commit the stack **before** applying fast53 as
the baseline; otherwise `git diff` would omit this patch's source changes.
There is no new harness SPIR-V header: fast53 goes through the production
`libpyrowave-shared.so` and its regenerated `slangmosh.hpp`. Existing standalone
`haar_fused_spv.h` and `idwt97_fused_spv.h` are unchanged and disabled in the check.

## Planner: standalone device check

Use the matching full-CI Android artifact's `pyrowave_android`,
`libpyrowave-shared.so` and `libc++_shared.so`. Put two retained .wave inputs in
`results/local/fast53/`: `cdf53.wave` and `haar.wave`, made from the same 8-bit
C420 source, geometry 5248x2752, same byte budget. To match the v1 comparison, at 750 Mbps / 90 Hz the
encoder byte target is 1041666/frame. The existing encoder accepts
`pyrowave-encode <source.y4m> <output.wave> 1041666` with process environment
`PYROWAVE_WAVELET=53` or `haar`. The check uses the first frame; repeat with
representative retained frames/edge patterns before accepting parity.

After device-test authorization, with artifact files under `out/fast53-v23-android`:

```powershell
adb shell mkdir -p /data/local/tmp/q3pw-fast53-v23
adb push out/fast53-v23-android/pyrowave_android /data/local/tmp/q3pw-fast53-v23/
adb push out/fast53-v23-android/libpyrowave-shared.so /data/local/tmp/q3pw-fast53-v23/
adb push out/fast53-v23-android/libc++_shared.so /data/local/tmp/q3pw-fast53-v23/
adb push results/local/fast53/cdf53.wave /data/local/tmp/q3pw-fast53-v23/
adb push results/local/fast53/haar.wave /data/local/tmp/q3pw-fast53-v23/
adb shell chmod 755 /data/local/tmp/q3pw-fast53-v23/pyrowave_android
adb shell 'cd /data/local/tmp/q3pw-fast53-v23 && LD_LIBRARY_PATH=. PYROWAVE_PRECISION=1 ./pyrowave_android --compare-fast53 cdf53.wave haar.wave check-v23-p1 30'
adb pull /data/local/tmp/q3pw-fast53-v23 results/local/fast53/device-v23
```

The single invocation runs five fresh worker processes sequentially, with five
warm-up decodes and 30 measured decodes each. It reuses the existing GPU timestamp
window (upload/dequant + inverse; conversion and readback excluded), reports
per-plane maximum/mean absolute R8 code differences and mean GPU decode times
for apron53, v1, v2, v3 and Haar. Each fast variant is compared to the same apron
readback, with per-plane differences, GPU ms and ratio to Haar. It prints
`passing_variants` and `fastest_passing_variant` (0 = none), without changing any
client property. Exit 0 means at least one variant passed **both** gates; 2 means
none passed parity; 3 means some passed parity but none also met timing; 1 means
an execution, input or readback failure.
Readbacks and timing sidecars stay in the chosen private directory. No Android
property or installed library is changed. Repeat with `PYROWAVE_PRECISION=0`
and `=2`, changing the output prefix, if testing those precision modes.

For a later matching-client live check, set `debug.q3pw.fast53=1`, `2` or `3` before creating
a CDF53/Compute decoder and verify the marker; the managed harness must snapshot
and restore it. Standalone success establishes neither runtime 90 Hz acceptance
nor sustained fresh frames in live VR. No change to defaults without the owner's
in-headset assessment.

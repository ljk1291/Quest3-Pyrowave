# WO-6 pair-local CDF 5/3 candidate

Source-only handoff on `codex/fast53`, based on `codex/output-queue` d8a5fc4.
No shader/C++ compilation, network, ADB, device or GPU work was performed.
Runtime acceptance, standalone timing, live VR performance and owner visual
acceptance are all **unverified**. This is an experiment, default off.

`patches/pyrowave-fast53.patch` stacks last on the pinned PyroWave overlays.
It adds a per-decoder `pyrowave_decoder_set_fast53_enabled` API and a second
compile-time `idwt` variant. The API rejects enabling outside CDF53 + Compute.
The client reads `debug.q3pw.fast53` on decoder creation; only the exact value
`1` requests it, and `[Q3PW_FAST53] requested=... active=... reason=...` reports
the resolved choice. Unset/other values select the original variant. Existing
Haar and CDF97 arithmetic, dispatches, barriers and bitstreams are unchanged.
The harness's managed-property snapshot includes this property.

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

Each invocation reconstructs 2x2 coefficient pairs (4x4 pixels): seven fetched
values per vertical column times seven horizontal columns = **49 texelFetch
calls / 16 output pixels = 3.0625 fetches/pixel** in a full block. Partial edge
blocks cost more per retained pixel. Haar uses one fetch/pixel. There is no
shared tile or workgroup barrier in the compiled fast variant. Register pressure,
texture bandwidth, driver contraction/precision and edge gather behaviour are
the remaining risks for the <=1-code and ~1.3x-Haar gates. No speedup is claimed.

Local validation: `python -m unittest tools.tests.test_fast53 -v` passes the
2D gather/apron equivalence proof and shader-gate/overlay checks; all 31
`tests.test_bench` tests pass using the existing benchmark Python environment.
The native policy test exercises all 32 property/wavelet/path combinations in
CPU CI. Neither Python environment has pytest installed; no packages were added.

## Planner: regenerate, fold in, then build

The current patch intentionally leaves `slangmosh.hpp` and
`quest3-manifest.json` stale. **Do not run full CI before folding regenerated
artifacts in.** The new C++ indexing requires generated `idwt[3][2]`.
`check_shader_manifest.py` already covers every changed shader input, including
`dwt_common.h` and `slangmosh.json`; no new manifest filename is needed.

After reviewing, committing and pushing the source handoff to `codex/fast53`,
run these in PowerShell from this worktree (planner actions, not run here):

```powershell
gh workflow run shaders.yml --ref codex/fast53
gh run list --workflow shaders.yml --branch codex/fast53 --limit 5
# Use the run ID for the source commit just pushed:
$shaderRun = <run-id>
gh run watch $shaderRun --exit-status
gh run download $shaderRun --name PyroWave-generated-shaders --dir out/fast53-shaders
```

`shaders.yml` temporarily reverses this additive patch to recover the original
pinned header, reapplies the patch, then compiles all variants. The new
`check_fast53_shaders.py` gate requires byte-identical existing SPIR-V and checks
every fast53 module for `OpControlBarrier`, `OpMemoryBarrier` and Workgroup
variables. Investigate any failure; do not bypass the default-binary gate.

The ignored reconstructed tree `ws/fast53-pyrowave` has the pre-change stack
committed as local baseline `dbe4679381d47723fef3c4f8a0f706f46f6f0544`; its index
still holds that baseline. It was archived offline from pinned d2997ac and
normalized to LF before applying the exact existing overlay order. Fold in:

```powershell
$pw = Join-Path (Get-Location) 'ws/fast53-pyrowave'
$overlay = Join-Path (Get-Location) 'patches/pyrowave-fast53.patch'
Copy-Item -LiteralPath out/fast53-shaders/slangmosh.hpp -Destination "$pw/shaders/slangmosh.hpp"
Copy-Item -LiteralPath out/fast53-shaders/quest3-manifest.json -Destination "$pw/shaders/quest3-manifest.json"
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
C420 source, geometry 5248x2752, same byte budget. For 500 Mbps / 90 Hz the
encoder byte target is 694444/frame. The existing encoder accepts
`pyrowave-encode <source.y4m> <output.wave> 694444` with process environment
`PYROWAVE_WAVELET=53` or `haar`. The check uses the first frame; repeat with
representative retained frames/edge patterns before accepting parity.

After device-test authorization, with artifact files under `out/fast53-android`:

```powershell
adb shell mkdir -p /data/local/tmp/q3pw-fast53
adb push out/fast53-android/pyrowave_android /data/local/tmp/q3pw-fast53/
adb push out/fast53-android/libpyrowave-shared.so /data/local/tmp/q3pw-fast53/
adb push out/fast53-android/libc++_shared.so /data/local/tmp/q3pw-fast53/
adb push results/local/fast53/cdf53.wave /data/local/tmp/q3pw-fast53/
adb push results/local/fast53/haar.wave /data/local/tmp/q3pw-fast53/
adb shell chmod 755 /data/local/tmp/q3pw-fast53/pyrowave_android
adb shell 'cd /data/local/tmp/q3pw-fast53 && LD_LIBRARY_PATH=. PYROWAVE_PRECISION=1 ./pyrowave_android --compare-fast53 cdf53.wave haar.wave check-p1 30'
adb pull /data/local/tmp/q3pw-fast53 results/local/fast53/device
```

The single invocation runs three fresh worker processes sequentially, with five
warm-up decodes and 30 measured decodes each. It reuses the existing GPU timestamp
window (upload/dequant + inverse; conversion and readback excluded), reports
per-plane maximum/mean absolute R8 code differences and mean GPU decode times
for all three paths. It reports fast53/Haar and returns 0 for both gates passing,
2 for parity/readback failure, 3 for timing >1.3x, 1 for execution/input failure.
Readbacks and timing sidecars stay in the chosen private directory. No Android
property or installed library is changed. Repeat with `PYROWAVE_PRECISION=0`
and `=2`, changing the output prefix, if testing those precision modes.

For a later matching-client live check, set `debug.q3pw.fast53=1` before creating
a CDF53/Compute decoder and verify the marker; the managed harness must snapshot
and restore it. Standalone success establishes neither runtime 90 Hz acceptance
nor sustained fresh frames in live VR. No change to defaults without the owner's
in-headset assessment.

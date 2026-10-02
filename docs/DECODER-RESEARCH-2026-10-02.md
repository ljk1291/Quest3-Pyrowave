# Decoder research reconciliation — 2026-10-02

This review extends the [optimization plan](DECODER-OPTIMIZATION-PLAN.md).
It changes neither the baseline nor dependency pins. No new hardware test,
third-party program execution, or optimization promotion was performed.
The ordered recommendation is **profile the faster allocation, test final-luma
fusion, then establish direct YUV sampling into Vulkan RGB targets**. Later
work depends on those measurements; source architecture supplies no speedup estimate.

## Measured control and unresolved quality

The headset-tested pair remains `f2e9df5704cc679513848bf6ffb63ef1695479f9`:
ALVR `7eda092dbf0002281410a4222683ec228700cffb`, PyroWave
`d2997ac172bdc00e29c58e3f2938acb7e94580bf`, Granite
`842d9d5686ba8c799a7d34a78a68f98d6aeb5a68`, with the repository overlays.
The measured allocation comparison used 3072×3232 per eye, 90-Hz runtime,
300 Mbps TCP, Haar/Compute, 4:2:0 SDR, fragment conversion, synchronous direct
eye copy and one worker. `fragment_min_usage=1` was held constant while
`optimal_ahb_usage` changed off/on/off/on.

| Measurement | Control / enabled / control / enabled repeat | Interpretation |
| --- | --- | --- |
| Fresh selected outputs/s | 56.00 / 82.69 / 55.25 / 82.02 | Repeatable improvement; every 90-Hz screen still failed |
| Conversion median | 4.91 / 1.31 / 5.09 / 1.36 ms | GPU conversion interval, not an entire frame or guaranteed removable cost |
| Decode-to-fence median | 17.47 / 11.54 / 17.62 / 11.63 ms | Completion latency overlaps GPU work and CPU recording/wait scopes |
| Allocation | `0x300 / 0x10000300 / 0x300 / 0x10000300` | Actual flags verified for all three slots; no fallback |

GPU decode remained roughly 9 ms; enabled client-FPS 1% lows remained near 45.
The earlier **3.75-ms Dequant / 5.00-ms iDWT** profile used the older allocation
configuration and delayed Granite window means. It is not a per-pass profile
of the faster configuration. Sources: [allocation result](../results/optimal-ahb-screen-2026-10-02.json)
and [earlier phase profile](../results/decoder-profile-2026-10-02.json).

The first Metro observation at 500 Mbps failed subjective image quality:
dull colours, mura-like compression and aliasing. Earlier charts supply no
gameplay control, so allocation regression is unknown. Post-exit captures are
not Metro evidence. Commit `d1c3b3d4edb354be8176ccaf5604918fe9ee4a52` removes
PyroWave's extra RGB-to-limited-range presentation remap. Its
[signed build](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37053223424)
passed CI, including matching-pair verification, but is not installed or
headset-validated. Establish a new pair-local colour-correct control before
quality-sensitive optimization comparisons; never relabel the old rate data.

## Immutable research sources

These are research snapshots, not proposed dependency updates. Locations in
the following sections are commit-pinned. Licences describe the inspected
source; dependencies and individual files still require review before reuse.

| Source | Reviewed revision | Licence / scope |
| --- | --- | --- |
| WiVRn `proto/pyrowave` | [`a0f5700d0bae9bbe72876a59c78a385930c5c70d`](https://github.com/WiVRn/WiVRn/tree/a0f5700d0bae9bbe72876a59c78a385930c5c70d) | Inspected decoder GPL-3.0-or-later |
| PyroWave `master` | [`89f7e47d4abbf650c91fae766728af866c5e32a0`](https://github.com/Themaister/pyrowave/tree/89f7e47d4abbf650c91fae766728af866c5e32a0) | MIT; newer than our pin |
| PyroFling `master` | [`99620dabd652550192f4359a500b8dd310fa213f`](https://github.com/Themaister/pyrofling/tree/99620dabd652550192f4359a500b8dd310fa213f) | MIT; separate capture/viewer product |
| FFmpeg `master` | [`98e92563a3b60dbf6d370fd3491d7f896398e4c1`](https://github.com/FFmpeg/FFmpeg/tree/98e92563a3b60dbf6d370fd3491d7f896398e4c1) | Inspected APV host/shaders LGPL-2.1-or-later |
| Meta IGL | [`5be0f2c6bf545e062f415a0215627984297f49a3`](https://github.com/facebook/igl/tree/5be0f2c6bf545e062f415a0215627984297f49a3) | MIT; dependencies have separate notices |
| libplacebo | [`92b5ac6db79f4d680eb656692f7bf51e9606f42a`](https://github.com/haasn/libplacebo/tree/92b5ac6db79f4d680eb656692f7bf51e9606f42a) | Inspected renderer/colour/sampling LGPL-2.1-or-later |
| Polaris | [`7910cb1f3062285ac6c518b4e90707b7d8dfba0e`](https://github.com/papi-ux/polaris/tree/7910cb1f3062285ac6c518b4e90707b7d8dfba0e) | GPL-3.0; host encoder |
| Nova | [`f2ce2b2e6d38ffc5d4089a35e0260a719ce39afe`](https://github.com/papi-ux/nova/tree/f2ce2b2e6d38ffc5d4089a35e0260a719ce39afe) | GPL-3.0; actual Android decoder/presenter |
| NX Warp | [`9b06836210f13eca90e21074c65b887120169213`](https://github.com/nerdrx/nx-warp/tree/9b06836210f13eca90e21074c65b887120169213) | Apache-2.0; different codec |
| Nightfall | [`e111b5c0825ad27be28d6584007c60cac2b017ea`](https://github.com/tB0nE/nightfall/tree/e111b5c0825ad27be28d6584007c60cac2b017ea) | GPL-3.0; HEAD unchanged since our previous review |

The [Meta Vulkanised 2024 presentation](https://vulkan.org/user/pages/09.events/vulkanised-2024/vulkanised-2024-sergey-kosarevsky-alexey-medvedev-meta.pdf)
was reviewed at SHA-256
`2e22956711f35ca9500b38743fc1e335b2cd5b47be82006455e3ac1ac52f874b`.
PDF pages 9, 12, 14 and 18 cover command buffers, fence/submit handles, staging
resource growth, and layout/dependency tracking. It is a design reference,
not a licence to copy slides or evidence of this decoder's performance.

## Reconciliation: what is present and what is different

**Our current path:** compressed payload → Vulkan dequant/iDWT → three R8
planes → fragment conversion into RGBA AHardwareBuffer → EGL/GLES eye draws
→ OpenXR. Conversion resources and a three-slot output ring already exist.
The measured control waits for Vulkan completion and GLES completion before
reusing producer resources. See [native recording, barriers and waits](https://github.com/ljk1291/Quest3-Pyrowave/blob/d1c3b3d4edb354be8176ccaf5604918fe9ee4a52/tools/pyroclient/pyroclient.cpp#L610-L738)
and [direct-eye integration](https://github.com/ljk1291/Quest3-Pyrowave/blob/d1c3b3d4edb354be8176ccaf5604918fe9ee4a52/patches/quest3-alvr.patch#L4061-L4432).

**PyroWave/PyroFling:** the [mobile fragment heuristic](https://github.com/Themaister/pyrowave/blob/89f7e47d4abbf650c91fae766728af866c5e32a0/pyrowave_decoder.cpp#L913-L929)
includes Qualcomm's proprietary driver. That is upstream CDF reconstruction;
our Haar overlay requires Compute. Fragment *conversion* is already active
in our faster control and must not be confused with fragment *wavelets*.
The [sampled linear-image payload path](https://github.com/Themaister/pyrowave/blob/89f7e47d4abbf650c91fae766728af866c5e32a0/pyrowave_decoder.cpp#L932-L1034)
is also already present, subject to capabilities/allocation. Eight saved
Session 05/06 native-init logs contain no payload-mode activation or fallback
marker; the active representation remains unknown. Absence of the library's
log message is not evidence of fallback. Emit effective mode and reason from
the decoder before testing that factor. The upstream
revision diff adds encoder/scaler/API work, not decoder/shader improvements.
PyroFling's [deadline and new-frame selection](https://github.com/Themaister/pyrofling/blob/99620dabd652550192f4359a500b8dd310fa213f/pyrofling_viewer.cpp#L500-L725)
and explicit semaphore dependencies inform scheduling; they are not an OpenXR
or cross-API implementation we can drop in.

**WiVRn:** [three-plane allocation and sampler conversion](https://github.com/WiVRn/WiVRn/blob/a0f5700d0bae9bbe72876a59c78a385930c5c70d/client/decoder/pyrowave/decoder.cpp#L60-L156)
expose R8 plane views for writes and a full YUV view for sampling. Its Vulkan
compositor consumes [a timeline value at the fragment stage](https://github.com/WiVRn/WiVRn/blob/a0f5700d0bae9bbe72876a59c78a385930c5c70d/client/scenes/stream.cpp#L872-L951).
This avoids a separate final RGBA conversion image. Internal wavelet images
and payload uploads remain. The worker still [waits on a CPU fence without a timeout](https://github.com/WiVRn/WiVRn/blob/a0f5700d0bae9bbe72876a59c78a385930c5c70d/client/decoder/pyrowave/decoder.cpp#L345-L351).
It has no Vulkan→GLES boundary to eliminate and supplies no comparable Quest
result. Keep our timeout/device-loss policy.

**FFmpeg:** APV [clears a flat coefficient buffer, writes sparse values and
orders its transform consumer](https://github.com/FFmpeg/FFmpeg/blob/98e92563a3b60dbf6d370fd3491d7f896398e4c1/libavcodec/vulkan_apv.c#L231-L308).
Its [branch-reduced variable-length reader](https://github.com/FFmpeg/FFmpeg/blob/98e92563a3b60dbf6d370fd3491d7f896398e4c1/libavcodec/vulkan/apv_decode.comp.glsl#L45-L117)
and [dequantization during iDCT loads](https://github.com/FFmpeg/FFmpeg/blob/98e92563a3b60dbf6d370fd3491d7f896398e4c1/libavcodec/vulkan/apv_idct.comp.glsl#L35-L152)
are techniques to study. PyroWave already has packed payloads, storage-mode
specialization, ballot/bit-count offsets and sparse decoding. Its dependent
wavelet pyramid differs from APV's independent 8×8 DCT blocks. Neither APV
bit parsing nor its transform/dispatch geometry is compatible decoder code.
Ternary source expressions do not prove branchless GPU machine code.

**IGL/libplacebo:** IGL's [submission dependencies](https://github.com/facebook/igl/blob/5be0f2c6bf545e062f415a0215627984297f49a3/src/igl/vulkan/VulkanImmediateCommands.cpp#L236-L286)
and [wait injection](https://github.com/facebook/igl/blob/5be0f2c6bf545e062f415a0215627984297f49a3/src/igl/vulkan/VulkanImmediateCommands.cpp#L365-L386)
support explicit resource ownership; its staging helpers still use CPU waits.
libplacebo [composes plane sampling into shader subpasses](https://github.com/haasn/libplacebo/blob/92b5ac6db79f4d680eb656692f7bf51e9606f42a/src/renderer.c#L1998-L2010)
and [appends colour operations](https://github.com/haasn/libplacebo/blob/92b5ac6db79f4d680eb656692f7bf51e9606f42a/src/renderer.c#L2310-L2414).
Its [finite-bit-depth range treatment](https://github.com/haasn/libplacebo/blob/92b5ac6db79f4d680eb656692f7bf51e9606f42a/src/colorspace.c#L1882-L1905)
is a correctness reference. Our converter already combines Y/Cb/Cr sampling,
matrix conversion and range expansion in one pass. Audit full-range chroma
centring against our encoder before changing it; do not silently substitute a
different colour convention during a performance experiment.

**Polaris/Nova:** Polaris contains the [host encoder](https://github.com/papi-ux/polaris/blob/7910cb1f3062285ac6c518b4e90707b7d8dfba0e/src/platform/linux/pyrowave_encode.cpp#L520-L547).
Nova is the actual Android implementation. It [forces Compute after a failed
fragment round-trip test](https://github.com/papi-ux/nova/blob/f2ce2b2e6d38ffc5d4089a35e0260a719ce39afe/app/src/main/jni/pyrowave-core/pyrowave_renderer.cpp#L474-L506)
and [converts planes into an ordinary Android Vulkan swapchain](https://github.com/papi-ux/nova/blob/f2ce2b2e6d38ffc5d4089a35e0260a719ce39afe/app/src/main/jni/pyrowave-core/pyrowave_renderer.cpp#L1035-L1137).
There is no AHB/OES/EGL/OpenXR path in that renderer; its unbounded waits are
unsuitable here. This motivates isolated Vulkan measurement, not a claim that
Nova has solved Godlike Quest PCVR.

**NX Warp:** the implemented Vulkan library has [timeline submission and
completed timing retrieval](https://github.com/nerdrx/nx-warp/blob/9b06836210f13eca90e21074c65b887120169213/vk/decoder/nxvc_vkdec.cpp#L4185-L4299),
[two-plane R8_UINT/RG8_UINT output](https://github.com/nerdrx/nx-warp/blob/9b06836210f13eca90e21074c65b887120169213/include/nxvc/nxvc_vk.h#L62-L80)
and [borrowed Vulkan output images](https://github.com/nerdrx/nx-warp/blob/9b06836210f13eca90e21074c65b887120169213/vk/decoder/nxvc_vkdec.cpp#L4526-L4585).
The latter is constrained to eligible NXVC 8-bit 4:2:0 streams; it is not a
PyroWave/OpenXR interface. The [Android shell](https://github.com/nerdrx/nx-warp/blob/9b06836210f13eca90e21074c65b887120169213/android/src/nxc_vk.h#L1-L23)
has no OpenXR, and its [decoder declaration](https://github.com/nerdrx/nx-warp/blob/9b06836210f13eca90e21074c65b887120169213/android/src/nxc_decoder.h#L20-L26)
describes placeholder passes. Its AHB helper samples MediaCodec hybrid input.
Sparse/ATLAS and compact-periphery modes can change codec semantics or sampling;
they are not equivalent-resolution optimizations to copy. Borrow its separation
of completed timings, output ownership and challenging image corpora, while
keeping architectural timing estimates and Pico/WiVRn evidence separate from
Quest/ALVR measurements.

**Nightfall:** the [existing comparison](NIGHTFALL-COMPARISON.md) still applies.
Its three-slot RGBA-AHB/EGL path resembles ours; persistent imports and an
asynchronous ready/release-fence ring differ. We already avoid CPU pixel
readback, have import caching as an experiment, and have the measured AHB
allocation improvement. Whole-decoder FP16 remains rejected; converter-only
precision is a separate unproven candidate. No new equivalent live result was found.

## Prioritized shortlist

Effort is relative engineering scope, not a schedule or predicted speed gain.
Every candidate needs the common image/provenance gates below.

| Order | Candidate and measured target | Mechanism | Effort / principal risks |
| --- | --- | --- | --- |
| P0 | Per-pass profile and activation proof on faster AHB; remaining ~9-ms decode and long tails | Identify component/level costs and distinguish execution from completion/selection | Medium; instrumentation overhead, query reuse and misleading aggregation |
| P1 | Final-luma Haar → existing fragment conversion | Remove final R8 luma materialization/read while retaining faster RGBA allocation | High; coordinate/rounding errors, fragment pressure, lifetime/barriers |
| P2 | Direct planar sampling into Vulkan RGB targets, then OpenXR feasibility | Sample decoder planes in the final eye draw; potentially remove RGBA AHB and cross-API handoff | Small offscreen proof, very high full migration; runtime binding, feature support, filtering, ownership |
| P3 | New fragment Haar reconstruction | Evaluate proprietary Qualcomm graphics path for measured expensive Haar levels | High; new shaders/attachments, extra passes, bandwidth, exact Haar arithmetic |
| P4 | Narrow dequant payload/zero-store/divergence experiments | Reduce verified dequant memory or divergent work, one factor at a time | Low for existing payload toggle; high for new layout; extra clears, register pressure, stale coefficients |
| P5 | New bounded output-ring/scheduling design, only if selection/interop remains material | Overlap safely leased producer and consumer work; select completed new frames near deadline | Very high; stale/reordered frames, extra latency, teardown and device-loss faults |

### P0 — measurement contract first

Extend the existing [completed-window collector](https://github.com/ljk1291/Quest3-Pyrowave/blob/d1c3b3d4edb354be8176ccaf5604918fe9ee4a52/tools/pyroclient/pyroclient.cpp#L170-L208)
and [strict phase parser](https://github.com/ljk1291/Quest3-Pyrowave/blob/d1c3b3d4edb354be8176ccaf5604918fe9ee4a52/tools/pyroclient/pass_profile.h#L10-L67).
Upstream [compute iDWT](https://github.com/Themaister/pyrowave/blob/89f7e47d4abbf650c91fae766728af866c5e32a0/pyrowave_decoder.cpp#L702-L779)
already has debug regions per level/component; those are not per-level timing
results. Add opt-in timestamps for payload upload, dequant component/level/band,
each inverse-wavelet level, final luma, and conversion. Identify query stage
boundaries and keep barrier/queue-wait attribution explicit.

Use a bounded query ring; read only completed slots and honour timestamp valid
bits/period. Do not insert new device-idle waits or reuse pending queries.
Associate exact records with decoder generation/decoded frame identity where
available; keep delayed Granite means explicitly aggregate. Extend parser and
missing-label checks together. Record payload storage mode, actual shader
variant/precision, subgroup configuration, output allocation and fallback.
Requested Android properties alone are insufficient activation evidence.

**Isolated experiment:** matched new pair, faster allocation held fixed,
profiler off/on/off with equal finite windows and workload. Establish profiler
overhead separately, then collect detailed phases. Disable instrumentation for
rate qualification. **Correctness gate:** unchanged decoded pixels and source
identities, valid/completed timestamps, no missing phases, no reuse/failure.
Do not sum percentiles or overlapping wall/GPU intervals.

### P1 — final producer/consumer fusion

For 4:2:0, chroma reaches final planes at level 1; level 0 materializes luma.
Keep levels 4→1, expose the final luma coefficient view under an explicit
library lifetime/barrier contract, and reconstruct Haar luma inside a new
variant of [our fragment converter](https://github.com/ljk1291/Quest3-Pyrowave/blob/d1c3b3d4edb354be8176ccaf5604918fe9ee4a52/tools/pyroclient/convert.frag#L1-L20).
Retain the actual recommended-AHB allocation, synchronous lease and completed
chroma sampling. This is distinct from the rejected multi-level
`idwt_haar_fused.comp` and from compute-writing RGBA AHB.

**Isolated experiment:** only after P0 quantifies final-luma cost, one opt-in
Haar/4:2:0/Compute+fragment variant versus control on identical packets;
unsupported combinations retain the existing path. **Correctness gate:**
transposed coefficient coordinates, pair parity, DC shift, intermediate
rounding and final R8 quantization must match. Check both coded ranges, neutral
patches, saturated thin edges, mirror boundaries, padding and stereo seams.
Measure combined affected GPU work; moving work into a slower fragment pass
is not a win merely because a dispatch disappeared.

### P2 — remove the intermediate before redesigning the application

**A. Offscreen proof:** decode the same packets into ordinary Vulkan R8 planes
and sample them directly into a final RGB render target. No RGBA AHB, GLES or
OpenXR is needed for this narrow experiment. Preserve the current sampling,
range and transfer math. Compare RGB correctness with the existing bridge's
conversion result. Time Vulkan plane sampling into the offscreen RGB target
separately. A timing control needs equivalent Vulkan output work and dimensions;
this proof omits GLES/OpenXR and cannot measure their handoff/presentation cost.

**B. Optional sampler-conversion variant:** then test WiVRn-style multi-plane
allocation and `VkSamplerYcbcrConversion` independently. Query exact image
format/usage support, mutable/extended plane views, storage/attachment writes,
sampling, chroma locations and required linear-filter features. WiVRn's nearest
filter is not permission to replace our chroma filtering. If matching colour
sampling is unavailable, retain explicit three-plane sampling.

**C. Vulkan OpenXR feasibility:** after A and any selected optional B, create a separate minimal
Vulkan-bound OpenXR session using supported RGB swapchain formats. Query
runtime Vulkan graphics requirements and use the compatible device/queue;
our current GLES session cannot simply accept Vulkan images. Prove acquire,
wait, release, stereo orientation, rendering completion and loss/recreation.
Integrating ALVR's lobby, overlays and renderer is a larger follow-on task.
This route could remove both the intermediate RGBA AHB and Vulkan→GLES boundary;
it does not assume the runtime accepts a YUV swapchain or eliminate final RGB output.

**Gate:** exact full/limited-range frame comparisons, matched chroma siting and
transfer, no stale planes, validation-clean transitions and no slot reuse until
consumer completion. Keep bounded waits initially. Making the path asynchronous
at the same time would confound the comparison. An external YUV AHB→GLES probe
is a fallback if native Vulkan migration is disproportionate; it must prove
gralloc plane-write/import support and native-fence ownership and still retains
the cross-API boundary. IGL's YUV sample proves none of those capabilities.

### P3 — fragment Haar is new shader work

Do not force Haar through upstream's CDF fragment code. Implement a separate
Haar fragment variant for one level first, with identical coefficients and
R8 results; expand only if the measured level warrants it. Keep fragment
conversion/allocation fixed. **Gate:** exact or explicitly bounded per-plane
and RGB comparisons, intermediate rounding/edge checks, shader activation
proof, then same-packet compute/fragment/compute timing. Test total render-pass
traffic, not just arithmetic. Qualcomm's heuristic and Nova's contrary device
experience are hypotheses, not a prediction for this Quest workload.

### P4 — use APV as a question, not an implementation

First log the existing selected payload representation and quantify dequant
work on the same corpus. If linear images activate, the existing
`PYROWAVE_NO_LINEAR_TEX` escape hatch supplies a narrow sampled-image versus
texel-buffer experiment. Its presence means it is not a missing upstream port.
Require an explicit activation/fallback result in each cell and packet-exact
outputs; do not silently change the native app environment.

Only if P0 implicates zero-store bandwidth, compare a properly synchronized
clear-then-skip variant to existing zero stores. Missing blocks currently write
zeros into reused images; omitting those writes without clearing is incorrect.
Count missing/coded blocks in a separate diagnostic run. Flat coefficient
storage is a later variant because it discards current texture-layer access
patterns. If branch/divergence counters implicate unpacking, change one PyroWave
bit/sign decision and inspect generated code/register pressure; do not port
APV VLC parsing. Preserve fixed lane/block mappings, all packet bounds and
malformed-input checks. **Gate:** exact decoded coefficient/output comparisons,
including absent blocks and frame-to-frame content changes. Reject extra clear,
register or conversion costs that offset the isolated saving.

### P5 — asynchronous scheduling requires a different ownership design

Nightfall's [slot ownership](https://github.com/tB0nE/nightfall/blob/e111b5c0825ad27be28d6584007c60cac2b017ea/addons/nightfall-stream/src/video/texture_uploader.cpp#L1715-L1835),
WiVRn's retained image handles and PyroFling's new-frame selection are references.
We already have an AHB ring; the missing hypothesis is independently leased
pending producer/consumer work with verified release synchronization, not
simply increasing the buffer count or enabling `async_eye_copy` again.

Design slot states, generation/frame IDs, ready and release fences, stale-frame
discard, maximum queue age, starvation and shutdown/device-loss behavior first.
A Vulkan timeline semaphore is not an EGL wait primitive; cross-API operation
needs supported exported/native fences and correct ownership direction.
**Experiment:** only after profiling attributes meaningful time to handoff or
selection, use the same corpus and one bounded queue policy, then an authorized
short live off/on/off comparison. **Gate:** no overwritten source, stale/reordered
frame, unbounded wait, extra queue-age tail or visual mismatch. Fresh submissions
and completion throughput must remain separate. Retain synchronous control.

## Experiments that remain closed without new evidence

| Existing experiment | Reconciliation / condition for reopening |
| --- | --- |
| Whole/multi-level fused Haar | Previously regressed. P1 changes final luma materialization only; enabling the old flag is not P1. |
| Band-batched dequant | No measured gain. APV dispatch batching alone does not justify another run. |
| Whole-decoder FP16 | Failed the existing PSNR-loss gate. Nightfall's default does not overturn it. Converter-only precision remains a separate low-priority image-gated question. |
| Existing async eye copy / two workers | Previous regressions/contention. P5 requires a new lease model and profiling evidence. |
| Import cache / raw sRGB | No demonstrated gain; raw-sRGB activation was unproven. Reopen only for measured import cost or a separately verified colour hypothesis. |
| More bitrate as a decoder fix | 300/400/600/300 Mbps did not improve delivery. New bitrate tests need a network or image-quality question. |
| Sparse sampling, foveation, temporal reuse, lower resolution | Different image work. Keep outside equivalent Godlike optimization claims. |

Several older rejected results are inherited upstream 2080×2208/120-Hz/USB
screens, not this owner's 3072×3232/90-Hz/Wi-Fi evidence. Preserve that scope.
They select hypotheses to avoid repeating; their numeric FPS values are not
comparators for the present profile.

## Shared isolated experiment and image gates

Extend the existing [standalone probe](https://github.com/ljk1291/Quest3-Pyrowave/blob/d1c3b3d4edb354be8176ccaf5604918fe9ee4a52/tools/pyroclient/pyroclient_test.cpp#L15-L126)
before treating it as a sequence benchmark. It currently loads one frame and
clears/replays it. Its legacy `fence_p50_ms` derives from `total_ms`, which
includes recording and query retrieval; preserve the field but document its
scope and add explicit submit→observed-completion timing.

1. Freeze complete, ordered packets from our exact encoder, with source frame
   IDs, encoded-frame IDs, per-packet hashes, coded range, chroma, wavelet,
   dimensions/padding and encoder settings. Use both static and changing
   multi-frame inputs; record single-frame replay separately. Cross-project
   bitstream/wavelet support must match before any same-input timing is valid.
2. Include full/limited grayscale patches, saturated thin text, natural detail,
   asymmetric eyes/disparity, moving edges and boundaries. Retain raw game
   captures privately. Pair frames by proven identity, never reusable tracking
   timestamps. A different encoder, wavelet or lower-sampling image is a
   different comparison.
3. Match native libraries, shaders, build flags, device/driver, allocation,
   clocks/thermal observations and output size. Separate initialization,
   CPU record, GPU stages, host fence wait, completion throughput and queue age.
   Check every frame's completion and actual option activation.
4. Run readback QA separately from timing. Prefer bit-identical output for
   storage/scheduling-only changes. For arithmetic changes, investigate at
   max channel error ≤1 eight-bit value and source-PSNR loss ≤0.05 dB, alongside
   range/edge/eye tests; those existing thresholds are not perceptual equivalence
   or permission to alter sampling. Compare exact decoded outputs and the
   original source, with fixed colour representation.
5. A native AHB readback does not exercise the downstream GLES remap. Colour
   correction and presentation candidates also need final-draw range/transfer
   checks. Headset compositor screenshots/videos are qualitative corroboration;
   they do not supply exact codec PSNR, panel range, optical FPS or latency.
6. Plan finite off/on/off cells: bounded warm-up, at most 600 measured packets
   and a 60-second wall cap per standalone cell; stop earlier on error. Live
   profile windows are separately bounded, with instrumentation off for rate
   qualification. These are proposals, not authorization to run unattended.

Obtain explicit readiness and scope for each hardware session, including any
AFK period. Snapshot exact ALVR keys, SteamVR scale/dashboard/driver inventory,
VDXR registration/manifest and affected headset properties; restore and verify
them afterward. Keep matched signed binaries separate from the active install.
Stop for decoder/device loss, corruption, thermal or settings drift. Never
reset/recycle possibly pending GPU resources after a timeout.

For Metro, record the game process as alive at both capture endpoints and
retain checkpoint/settings coverage, actual external projection/encoded sizes
and available internal-render evidence. A standalone win proceeds to repeated
live screens, manual clarity/motion review, three five-minute runs, a 30-minute
endurance run and recovery checks. Runtime-accepted 90 Hz, GPU execution time,
CPU-observed completion, fresh selected submissions and optical display FPS
are separate quantities. The latter stays unset without independent measurement.

## Reuse and attribution

This change incorporates analysis only. No third-party implementation is copied.
Before copying/adapting a file, record its exact commit, file header and licence,
review compatibility with the intended distributed component, retain required
copyright/licence/NOTICE material and update packaged notices. In particular,
GPL/LGPL implementations must not be relabelled MIT because this integration's
own files are MIT. Prefer independently written experiments from the mechanisms
above. Existing ALVR/PyroWave/Granite attribution and licences remain intact.

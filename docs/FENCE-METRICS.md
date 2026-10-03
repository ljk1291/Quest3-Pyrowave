# Fence reconstruction metrics

`tools.xrbench.fence_metrics` evaluates native full-range 8-bit luma in a frozen
eye-local rectangle. It measures error added by reconstruction; it does not claim
to measure optical shimmer or live presentation. The frozen Metro sequence has
irregular original timestamps and contains later menu frames. Keep source order.

Each reference frame defines its own Sobel edge mask. Use valid 3×3 support inside
the crop (exclude the outer pixel), squared gradient magnitude, and the linearly
interpolated 95th percentile. Include positive ties at the threshold and report
the actual selected counts; a flat crop has no mask and cannot yield a valid
perfect score. Never select a mask using the candidate decode.

Accumulate masked squared reconstruction error across pixels/frames for PSNR-Y
with peak 255. Also report p99.9 absolute reconstruction error. For temporal error,
evaluate `abs((dec[t]-dec[t-1])-(ref[t]-ref[t-1]))` on the **same current reference
mask**, using signed arithmetic. Report pixel-pooled mean and p99. Integer error
histograms compute exact linearly interpolated percentiles without large arrays.
These masks do not perform motion compensation; subtracting the source temporal
difference isolates added temporal error, but perceptual equivalence is unproved.

Report **one-based inclusive frames 1–90 and 10–89** separately. The first has 89
temporal pairs (current frames 2–90); the second has 79 pairs (11–89), keeping both
frames inside the scored window. Do not include frame 9 in the trimmed window.
Record per-frame source/decode hashes and both whole-file hashes. Missing frames,
changed dimensions, non-full-range input and geometry mismatch fail scoring.

The CLI requires an existing owner-supervised PC-only lease. The caller registers
the scorer process using WindowGuard and closes its lease afterward; the scorer
checks lease health during evaluation. No GPU, ADB, settings, or VR calls occur in
the metric itself. Rerunning a codec to obtain missing decodes still requires the
same finite authorized lease and GPU stops as other frame-bank jobs.

## Crop geometry

Scale Session 07 left/right/top/bottom tangents about zero, locate the scaled
rectangle's centre in original pixels, and centre the fixed 2624×2776 extent on
it. Round offsets to nearest even pixel, ties-to-even, to preserve native 4:2:0
planes. Slice without resizing. Record ideal/aligned offsets and original/scaled/
effective tangent bounds for both eyes. Horizontal mirrors yield mirrored offsets.

The requested vertical factor 0.8500 produces a 2747.2-pixel span from 3232; the
fixed offline target is 2776 high. These are explicitly distinct. Actual effective
FOV follows the fixed pixel extent and preserves pixels per tangent unit. Runtime
WO-10 derives its own codec-aligned dimensions from the multiplier. Fixed crops
that extend outside the offline rectangle get an exclusion/coverage record rather
than being silently clipped or moved.

Fence-first ranking must expose edge PSNR (higher better) and shimmer p99/mean
(lower better), then calibrated HVS for comparable regions, with VMAF last. If
these disagree, retain the tradeoff instead of asserting universal superiority.

## Centre/periphery and softness comparisons

The optional boolean `region_mask` restricts the threshold population and selected
pixels to a fixed band, without creating artificial edges at the band boundary.
The report binds its shape, pixel count, byte hash and caller's serializable band
descriptor. Band geometry comes from the shared foveation transform. An empty band
is explicitly invalid rather than a perfect result.

`score_against_references` compares a decode with both the sharp source and an
optional matching-blur reference. Both use the **same sharp-reference Sobel mask**,
so deliberate blur cannot erase the edge population being evaluated. Per-frame
reference, decode and mask-reference hashes are kept separately. Temporal deltas
are relative to the chosen sharp/blur reference respectively. Blur-reference
quality does not replace the sharp-reference score or certify visible equivalence.

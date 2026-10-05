# WO-6 fused inverse design

This is a source-design investigation. It does not enable a runtime path,
change a default, generate a shader header, or claim timing.

The existing CDF 5/3 and 9/7 compute inverse uses the shared-memory apron path
in PyroWave's `shaders/idwt.comp`. Haar has a separate pair-local fast inverse.
The proposed 5/3 candidate is a sibling shader, selected only by an explicit
decoder experiment setting after its output is qualified.

For each output pair, the 5/3 candidate fetches LL, HL, LH and HH coefficients
with a one-coefficient halo in each axis. It applies the existing inverse 5/3
lifting order and boundary extension exactly, then writes the same intermediate
format as `idwt.comp`. It must not change quantisation, dequantisation, band
orientation, chroma layout, colour range, or the final YCbCr conversion.

CDF 9/7 is deliberately excluded from this first implementation. Its lifting
support requires the existing wider apron. Reusing the 5/3 neighbourhood would
silently alter boundary samples. A separate 9/7 design must derive and test its
own halo before code is written.

The optional last-level YCbCr conversion is also excluded. It would change
rounding, chroma sampling and range handling at the last inverse level. It needs
an independent byte-for-byte CPU reference and a per-plane range proof first.

The current CPU model proves the literal one-dimensional 5/3 lifting loops on
an already gathered apron, including the pair-local ±1 calculation. It does
not yet establish the complete two-dimensional shader replacement: the exact
mapping from `load_image_with_apron()`'s transposed gathers and four texture
layers to LL/HL/LH/HH, and the intermediate shared-memory layout between the
horizontal and vertical transforms, still need an independently checked model.
That missing mapping blocks an `idwt53` shader, header regeneration, or any
claim that a candidate reproduces retained frames.

Qualification gates before any production activation are:

1. A scalar CPU reference mirrors the current 5/3 inverse loops, gathered
   apron, clamped line boundary rule, update-before-predict order and FP16
   shared-memory round trips. It must agree with the candidate on random,
   impulse, edge and odd-sized coefficient grids.
2. Candidate output differs by at most one code value from the existing decoder
   for all Y, Cb and Cr planes on retained 5/3 streams; exact equality is the
   preferred gate.
3. The shader header and manifest are regenerated from the selected source, and
   their hashes are bound to the tested artifact.
4. The candidate remains opt-in and decoder-only. Default 5/3 output must pass
   the retained all-90 decoded-frame hash gate unchanged.
5. Any device timing requires a separate armed measurement. CPU or software
   Vulkan correctness does not establish a performance gain.

## Separate CDF 9/7 CPU proof, no activation

The 9/7 candidate now has a deliberately separate literal CPU model in
`tools/xrbench/wo6_cdf97_model.py`. It models the pinned `idwt.comp` inverse
order exactly: scale even coefficients by `K` and odd coefficients by `1/K`,
then apply Delta, Gamma, Beta, Alpha over the 16-sample apron. Arithmetic is
rounded to float32 and the kept eight samples are stored as FP16. The 2D model
interleaves LL, x-high, y-high and HH as `(even,even)`, `(odd,even)`,
`(even,odd)`, `(odd,odd)`, performs the horizontal FP16 shared-tile writeback,
then performs the vertical pass. Random, impulse, zero, alternating and large
finite-coefficient tests compare this reference with the fused candidate model.

The source gather mapping is now explicit in the CPU model. In the pinned
`idwt.comp`, layers are LL=0, x-high=2, y-high=1 and HH=3. For each layer,
`generate_mirror_uv()` adds its parity-dependent coordinate adjustment and
then transposes the UV. GLSL `textureGather` returns `(i0,j1), (i1,j1),
(i1,j0), (i0,j0)`; its `.wxzy` swizzle therefore feeds `write_shared_4x4()`
as source coordinates `(x,y), (x,y+1), (x+1,y+1), (x+1,y)`, after its +1 adjustment and normalized
mirrored-repeat addressing. This is checked at interior and near-edge points
by `test_wo6_cdf97_model.py`, using the [GLSL gather ordering](https://registry.khronos.org/OpenGL/specs/gl/GLSLangSpec.4.60.html).

The candidate uses `texelFetch` after equivalent index resolution. What still
needs an independent proof is whole-stage equivalence: workgroup/tile coverage
for every level, final-image boundary writeback, and comparison against retained
decoder output. The CPU model establishes the stated apron lifting, FP16 order,
layer convention and endpoint assumptions; it does not qualify the fused
shader, regenerate a header, enable a runtime setting, or claim output parity
or performance.

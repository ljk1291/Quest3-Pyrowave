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

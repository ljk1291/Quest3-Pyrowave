# WO-6 inverse CPU proof result

Revision `9177afccbe3d24ef1642159e8d82c67a4c5d404a` adds explicit CPU CI
steps for the two inverse models. This result covers scalar arithmetic and
model topology only. It does not enable a shader, alter a decoder default,
regenerate `slangmosh.hpp`, or make a device timing claim.

The CDF 5/3 model checks the existing inverse update-before-predict order on
an interleaved apron. The pair-local candidate uses its current and adjacent
coefficient pairs only. It agrees exactly with the reference for randomized
lines, impulse and endpoint cases, and both float and FP16 shared-store/load
models. The focused suite has four tests.

The CDF 9/7 model separately checks the pinned 16-sample apron sequence:
even/odd scaling by K and inverse K, then Delta, Gamma, Beta and Alpha. It
uses float32 arithmetic and FP16 writeback. The 2D model covers the pinned
layer convention (LL=0, x-high=2, y-high=1, HH=3), gather `.wxzy` source
order, interior and near-edge mirrored addressing, horizontal shared-tile
writeback, and vertical lifting. Its focused suite has five tests.

The local focused CPU command completed successfully:

```
python -m pytest tools/tests/test_wo6_fused_inverse.py -q       # 4 passed
python -m unittest tools.tests.test_wo6_cdf97_model -v          # 5 passed
```

The authoritative manual `cpu_only` workflow ran at
[run 37253579925](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37253579925)
for this exact revision and completed successfully. It ran the two explicit
model-parity steps above. This checkout does not infer that result from the
local tests; it records the owner-scoped API result.

Open gates remain for both transforms: whole-stage workgroup coverage and
final-image boundary writeback; retained-stream decoded-frame comparison for
Y, Cb and Cr; shader compilation with regenerated header and manifest; an
opt-in-only decoder integration; and a default all-90-frame regression gate.
No source candidate is qualified until those gates pass. The 5/3 model also
still lacks a checked full 2D gather-to-shared-layout proof. The 9/7 CPU
mapping proof does not substitute for retained decoder output parity.

# WO-8 width-only H.264 candidate

This is an opt-in offline quality candidate. It encodes a 2624 by 2776 crop
as 2048 by 2784 per eye. Its 23/41 centre fraction and 2x horizontal edge
ratio are the least aligned reduction that reaches exactly 4096 SBS. The final eight rows are replicated allocation
padding and are removed after reconstruction. They are not vertical
resampling. The resulting 4096-pixel SBS width meets the H.264
limit.

The existing layered source already transports independent axis parameters:

- `alvr/server_core/src/connection.rs` in `patches/wo8-foveation.patch`
  constructs and forwards `foveation_center_size_x/y` and
  `foveation_edge_ratio_x/y`.
- `alvr/server_openvr/cpp/alvr_server/Settings.cpp` loads the corresponding
  X/Y values into `m_foveationEdgeRatioX/Y`.
- `alvr/server_openvr/cpp/platform/win32/FFR.cpp` computes
  `foveationScaleX` and `foveationScaleY` separately.
- `alvr/server_openvr/cpp/alvr_server/shader/FoveatedRendering.hlsli` and
  `CompressAxisAlignedPixelShader.hlsl` use vector `float2` centre and edge
  values in the forward mapping.
- `alvr/client_openxr/src/stream.rs` only exposes the receiver's existing
  inverse mapping after the server negotiated foveated encoding; it does not
  select a local profile on its own.

`patches/wo8-width-only-h264.patch`, layered after
`patches/wo8-foveation.patch` and the pinned receiver foveation source,
adds an opt-in `H264WidthOnly` profile. Its
Rust transport writes X as 23/41 / 2x and Y as the explicit 1.0 / 1.0 identity
sentinel. In `FFR.cpp`, `verticalIdentity` branches before the zero-height
band alignment and shift divisions, preserves full target-eye height, and
writes a constant-buffer flag. The forward HLSL shader receives that flag,
uses finite neutral Y coefficients, then restores output Y and its unit
derivative. The source patch is checked by a CPU contract test alongside the
offline parity tests.

On the receiver, `alvr/graphics/src/stream.rs` recognizes the same profile,
provides finite H.264-fit Y coefficients only for the inactive vector algebra,
and emits `FFE_IDENTITY_Y`. `alvr/graphics/resources/stream.wgsl` restores the
decoded pre-inverse Y coordinate under that flag. This keeps the inverse's X
mapping and Y identity explicit rather than relying on a 0/0 edge-band case.

This does not claim a compiled or installed native build, headset test, or
timing qualification. Until the separately pinned native source is built with
the matching receiver inverse path, the candidate remains qualified only for
CPU frame-bank and offline NVENC proxy work.

## Offline controller

The existing NVENC frame-bank controller exposes this one-cell plan through
`python -m tools.xrbench.nvenc_framebank plan --width-only-h264`. It requires
the same frozen source, crop geometry, fence rectangle, and crops arguments as
`--revised-q3a`; supply `--foveation-implementation-revision` and
`--foveation-implementation-source-sha256` as a pair to bind the plan to the
exact CPU transform. The resulting descriptor records 2048x2784 per eye,
4096 SBS, eight allocation-only bottom rows, `softness=0.5`, and the forced
one-pixel Y footprint. Planning runs no encoder; the standard supervised
`run` command remains the separate owner-controlled execution step.

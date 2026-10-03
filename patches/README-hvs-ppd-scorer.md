# PyroWave PSNR-HVS-M-H pixels/degree scorer adapter

This is an **opt-in scorer-only patch** for upstream PyroWave commit
`d2997ac172bdc00e29c58e3f2938acb7e94580bf`. It changes only `psnr.cpp`; it does
not change the PyroWave encoder, decoder, Android client, ALVR server, dependency
pin, or any runtime default.

The upstream scorer's formula is `pixels_per_degree = view_height * height_factor
* pi / 180`. Its default output retains the upstream 16-factor sweep byte-for-byte
in meaning and output shape. When `--pixels-per-degree <positive>` is supplied,
the patch evaluates exactly one factor derived from the actual scored image height
and logs `PixelsPerDegree`, `HeightFactor`, and PSNR-HVS-M-H. `--height-factor`
also evaluates one explicit positive factor. The two options are mutually exclusive.

License: MIT; `psnr.cpp` is Copyright (c) 2025-2026 Hans-Kristian Arntzen,
SPDX-License-Identifier: MIT. The companion manifest records source and patch hashes.

The preparation tool first validates the exact recorded LF or Windows CRLF
preimage hash, then normalizes that one file to LF before applying the patch.
The resulting canonical source hash is identical on Windows and Linux; Git's
global line-ending configuration does not affect the scorer provenance.

Prepare a separate clean source copy, then build its scorer target:

```powershell
python -m tools.xrbench.hvs_scorer verify-patch --source <clean-d2997ac-source>
python -m tools.xrbench.hvs_scorer prepare-source --source <clean-d2997ac-source> --out <private-scorer-source>
cmake -S <private-scorer-source> -B <private-scorer-build> -DPYROWAVE_UTILS=ON -DPYROWAVE_DEVEL=OFF
cmake --build <private-scorer-build> --target pyrowave-psnr-hvs-m
```

The frame-bank runner calls that separate executable with measured **vertical**
pixels per degree and rejects absent or mismatched emitted calibration.

## Raw-Y4M transport correction, 2026-10-03

The first Windows build reached the legacy scorer's configuration and failed at
Granite's FFmpeg/PkgConfig dependency. Review also found that `psnr.cpp` discards
the first reference/distorted frame for predictive video. That would omit part
of this fixed raw corpus. CI now builds a separate `pyrowave-framebank-hvs` target
with `PYROWAVE_UTILS=OFF` and `PYROWAVE_DEVEL=ON`, packaged under the existing
`pyrowave-psnr-hvs-m.exe` tool name. The calibrated legacy patch remains retained
and reversible; it is not the frame bank's video transport.

The new target extracts `contrast_sensitivity_function` and
`compute_total_errors_psnr_hvs_m` unchanged from pinned `psnr.cpp` and uses the
unchanged `shaders/psnr_hvs_m.comp`. Its native reader accepts explicit 8-bit
C420jpeg/C444 range, geometry and rate, and scores every frame from index zero.
It rejects incomplete planes, extra frames/bytes and mismatched metadata. It
reports `ScoredFrames`, which the harness requires to equal the frozen count.
The pinned shader's stride, CSF, masking and error accumulation are unchanged,
as is upstream's 223/255 limited-range peak convention; Metro is full range.
The manifest binds the extracted functions, generated source, reader, main,
CMake overlay and shader. Upstream MIT attribution remains in generated source
and the packaged notices.

Use `tools/windows/build_pyrowave_hvs_scorer.cmd` for this isolated target.
`--verify-inputs-only` runs finite native parsing checks without initializing
Vulkan and does not emit a metric. CI tests this mode on the built Windows
executable and tests the reader with g++ on Linux. The actual Vulkan metric still
needs a guarded same-input sanity check before its Metro results are accepted;
these CPU checks do not establish GPU metric correctness or Quest performance.

The subsequent Windows configuration exposed a separate copy-filter bug: a
`build*` ignore glob removed glslang's tracked `build_info.h.tmpl` and SDL's
`include/build_config` templates. Source preparation now excludes known root
output trees or directories with a generated `CMakeCache.txt`, preserving the
tracked build templates/scripts. A regression reproduces both missing inputs;
dependency revisions and runtime sources remain unchanged.

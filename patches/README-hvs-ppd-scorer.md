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

Prepare a separate clean source copy, then build its scorer target:

```powershell
python -m tools.xrbench.hvs_scorer verify-patch --source <clean-d2997ac-source>
python -m tools.xrbench.hvs_scorer prepare-source --source <clean-d2997ac-source> --out <private-scorer-source>
cmake -S <private-scorer-source> -B <private-scorer-build> -DPYROWAVE_UTILS=ON -DPYROWAVE_DEVEL=OFF
cmake --build <private-scorer-build> --target pyrowave-psnr-hvs-m
```

The frame-bank runner calls that separate executable with measured **vertical**
pixels per degree and rejects absent or mismatched emitted calibration.

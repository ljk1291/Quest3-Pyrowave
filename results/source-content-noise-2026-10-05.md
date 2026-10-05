# Source-content noise check

CPU-only analysis of the retained 90 Metro frames. The source contains 89 distinct frame payloads and irregular capture timestamps; its F90 header is a codec budget convention, not a live rate measurement.

| Candidate region | Qualified adjacent pairs / 89 | Mean pairwise noise diagnostic, luma codes | Aligned low-gradient difference p99 |
|---|---:|---:|---:|
| fence | 27 | 0.393 | 4.863 |
| fog | 27 | 0.300 | 1.668 |
| dark_wall | 24 | 0.366 | 3.373 |
| wood_gravel | 15 | 0.333 | 1.416 |

Phase correlation of high-passed adjacent source ROIs; only response >=0.3 and shift <=4 px qualify. Align previous with bilinear interpolation, exclude 8-pixel border, select current gradient <=2 codes/pixel. MAD(diff)/0.67449/sqrt(2) is a noise diagnostic, not an identified film-grain amplitude.

The low-gradient residuals are small in the qualifying pairs. They do not establish that film grain caused the visible compression. Motion, changing light, temporal antialiasing, sharpening and the interpolation used for alignment remain confounders. The selected rectangles are candidate static regions; no clean render or toggled-setting comparison exists.

Settings to compare at the same checkpoint, if the game exposes them:
- Film grain: compare off at the identical checkpoint; random high-frequency content consumes intra-codec bytes.
- Motion blur: compare off for the moving-line/clarity test; it changes the source and must be a separate comparison.
- Sharpening or DLSS sharpening: compare zero/default strength; halos and amplified noise are candidate contributors.
- Dynamic resolution: hold a fixed render scale for comparisons.
- Do not treat renderer dithering or temporal AA as a known user toggle. If exposed, test separately; disabling temporal AA may worsen the reported aliasing.

No game or system settings were changed. [Machine-readable evidence](source-content-noise-2026-10-05.json).

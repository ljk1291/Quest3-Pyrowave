# Lossless live frame pairs (default-off diagnostic)

The additive `patches/frame-dump.patch` stacks last after direct-eye foveation.
It preserves ALVR/Themaister/upstream credits and adds no protocol or default changes.
Native builds and Quest behavior still require Actions and device verification.
CPU scores establish image differences; they establish neither a runtime-accepted
rate, a standalone decode budget nor sustained live VR performance.

## Planner interface

Enable before constructing the encoder / connecting the client. These are commands
for a separately authorized hardware session; none were run during implementation.
An existing encoder or stream does not reread its controls. Restore the environment
and property after the cell. `ws/session25.py` integration belongs to the planner.

```powershell
# In the environment inherited by vrserver, before its next encoder is initialized:
$env:ALVR_Q3PW_FRAME_DUMP = 'C:\private\cell-source:32:1'
# In the authorized session, before the next client stream is constructed:
adb -s <serial> shell setprop debug.q3pw.frame_dump 128:1
```

Both limits are **capture attempts**, including readback failures and writer-busy
drops: count 1..128, interval 1..9000. The first new frame and every interval-th new
frame are selected. Server counts encoder submissions; client counts fresh selected
decoded timestamps, excluding repeated presentation. These counters are local and
are never used to pair frames. Use interval 1 on both and a longer client window;
packet loss, decoder dropping, startup delay and sparse independent sampling can
leave unmatched source frames. Clear controls with an absent/empty server variable
and `debug.q3pw.frame_dump=0`; absent client property also disables dumping.

Each encoder/stream creates a unique `server-<time>` / `client-<time>` subdirectory.
Client root:
`/sdcard/Android/data/io.github.ljk1291.quest3pyrowave/files/q3pw-dumps/`.
Collection changes no device settings and does not remove device files:

```powershell
python tools/quest3/frame_score.py pull --serial <serial> --out results/local/cell-client
python tools/quest3/frame_score.py score --server C:\private\cell-source\server-<time> --client results/local/cell-client/client-<time> --out results/local/cell-score.json
```

`pull` requires a new output directory and performs exactly one `adb -s ... pull`.
`score` is CPU-only and needs NumPy/OpenCV from `tools/quest3/requirements-cpu.txt`.
Select one run per side. Duplicate timestamp/stage records, incomplete sidecars,
truncated raw bytes, unsupported color domains and dimensional mismatches fail.
No exact pairs produces JSON/Markdown with warnings and exit 2; at least one pair
produces exit 0. Exit 0 is a scoring completion signal, not a quality pass. JSON
contains per-pair and aggregate values; `.md` uses the output JSON's stem. Captures
must stay in ignored private directories; never commit raw files or device IDs.

## Files and stages

Files are `<transported_timestamp_ns>-<stage>.raw` and `.json`. Raw data is
uncompressed and lossless at the named stage. The sidecar is written only after
raw bytes complete. Fields: `schema=1`, `complete=true`, `timestamp_ns`, local
zero-based `frame_index`, `stage`, `width`, `height`, `format`, `range`,
`matrix=bt709`, `row_order`, `bytes`. Rows have no stride padding. Pair identity
is the transported `Duration` / `targetTimestampNs`, never the XR-clamped timestamp,
discovery order, capture ordinal or approximate nearest timestamp.

* `encoder_input`: taken immediately before `VideoEncoder::Transmit`, after crop,
  packing and color conversion. PyroWave's actual R8 planar encoder textures are
  concatenated Y/U/V (`yuv420p` or `yuv444p`, full or limited range). Stock SDR paths
  capture the actual texture passed to the encoder (`rgba8`/`bgra8`, full range),
  before NVENC's internal RGB-to-YUV conversion. Rows are top-down. HDR/10-bit
  texture formats log unsupported and are not reinterpreted as 8-bit.
* `post_decode`: the completed decoder AHardwareBuffer sampled at native packed
  texel centers into RGBA8, using nearest filtering with no range/gamma correction,
  FFE expansion or rescaling, before the production renderer's EGL import.
  Covers PyroWave's compute RGBA output and stock
  MediaCodec's EGL external RGB view (its YUV-to-RGB conversion is part of this
  stage). UV v=0/source top row is stored first. No CPU_READ allocation flags or
  AHB locks are added. The selected decoder lease remains held through readback.
* `presented_left` / `presented_right`: exact SDR acquired OpenXR eye textures
  after ALVR's render, including FFE expansion (staging/WGSL or T1 direct), gamma,
  color correction and any application upscaling. Captured before release, with
  both eye writes completed by GL readback. Raw GL rows are bottom-up and flipped
  by the scorer. These exclude later runtime layer filters, timewarp and optics.

The server input and packed decode are comparable in the same dimensions. Final
eyes are analyzed for blank/black output separately; they are not silently resized
and compared to packed source. To score final reconstruction quality, a future
capture needs a reference rendered through the same inverse/gamma/filter pipeline.

## Metrics and crops

PSNR-Y uses full-range BT.709 R'G'B' luma. Planar limited Y is normalized from
16..235; planar full Y is used directly. RGB luma uses .2126/.7152/.0722, without
a transfer-function change. This measures the complete encode/decode color path,
including RGB/YUV conversion. It is not a codec-internal Y-plane PSNR for MediaCodec.
SSIM-Y uses 11x11 Gaussian sigma 1.5, population covariance and valid interior.
`null` PSNR plus `identical=true` means infinite identity PSNR; an empty edge mask
also gives null edge PSNR, with `edge_pixels=0`. Strict JSON never emits Infinity/NaN.

Fixed crops are full SBS, each eye's central half in both axes and four quarter-eye
corner rectangles. Chart line and stripe boxes come from `stereo_scene.py`:

```powershell
# Full-FOV/unwarped normalized chart only: JSON {"left":[l,r,t,b],"right":[l,r,t,b]}
python tools/quest3/frame_score.py score --server <run> --client <run> --chart-projections projections.json --out results/local/chart-score.json
# Cropped or packed chart: supply measured/mapped rectangles in packed SBS pixels.
# JSON {"left_chart_lines":[x,y,width,height],"left_chart_stripes":[...], ...}
python tools/quest3/frame_score.py score --server <run> --client <run> --crops packed-chart-crops.json --grids 8 16 32 --out results/local/chart-score.json
```

Do not scale full-FOV chart rectangles into FFE coordinates: packing is nonlinear,
and FOV crop changes chart placement. The planner must map/freeze those rectangles
from the cell geometry. Missing chart definitions are explicit warnings. No semantic
chart crop is guessed for arbitrary gameplay. Each box needs at least 11x11 pixels.

Blockiness is boundary gradient minus adjacent non-boundary gradients on specified
grids (default 8/16/32); crop origins retain the full encoded grid phase. Source,
decoded and signed excess values avoid counting source grid lines as codec blocks.
Use `--grids` for a measured PyroWave tile period; 32 is a diagnostic scale, not a
claim that all PyroWave transforms have that tile size. Source-defined Sobel edge
masks reuse WO-1/T4 `fence_metrics.edge_mask`. Edge PSNR, Laplacian detail-energy
ratio and high-frequency residual expose edge/detail loss; ringing can increase
detail energy, so that ratio is not a quality score alone.

Temporal residual is `abs((D[t]-D[t-1])-(R[t]-R[t-1]))`, with mean/p99 and a separate
static-source mask (`abs(source difference)<=1` luma code), per crop. Timestamps and
actual gaps are reported; sparse sampling does not establish between-frame flicker
or optical shimmer. Aggregation gives means of per-pair metrics (finite PSNR only,
identity counts separately). Black means >=99.5% of luma <=3; blank means std<=.5.
Unexpected decoded black/blank is compared against source, including separate eyes.
Presented-eye flags are unconditional diagnostics: genuine black scenes can trigger
them. No threshold automatically promotes a default. Calibrated PSNR-HVS is explicit
`measured=false`: WO-1's qualified native HVS runner requires projection/PPD and a
separate qualified run; this CPU scorer does not invent that calibration.

## Cost, verification and limits

Off: no dump allocation, worker, GPU readback, file I/O or per-frame environment/
property polling; the hot paths only check optional capture state. On: selected
frames synchronously read GPU data, with `[Q3PW_FRAME_DUMP] encoder_stall_ms` /
`client_stall_ms`; actual stall durations require device measurements.
Client markers distinguish `phase=decode` and `phase=presented`; add the two costs.
Disk writes run on a bounded asynchronous queue (one waiting job), with explicit busy drops and
write/readback failures. Shutdown drains the writer. Full Godlike pairs are large:
client jobs include packed RGBA plus both final eyes, and memory/storage must be
budgeted by the planner. Capture-enabled cells are quality diagnostics and cannot
establish timing performance. Use capture-disabled cells for timing.

CPU synthetic scorer/chart tests run in `tests/`. CI additionally runs standalone
C++ server path parsing and Rust client configuration tests. Manual full CI runs
the software GLES exact decoded/eye readback and state restoration regression,
then compiles the matching Windows server and Android client. No local compiler,
ADB, GPU benchmark, settings change or installation was used for this implementation.

Local validation: 43 synthetic scorer/chart/fence tests and 12 source-lock tests
passed. The full 13-overlay stack applies to a fresh pinned ALVR checkout; all 11
capture source files match the generation tree byte-for-byte, and reverse patch
checks and `git diff --check` pass. Native parser/GLES tests are wired into CI but
were not executable in the local sandbox.

# WO-5: opt-in Windows composition quality experiments

These candidates change no stable default, source pin, protocol or installed build.
The Windows server supports two process-local environment options, read once when
composition starts:

| Option | Default | Experimental value | Mechanism |
| --- | --- | --- | --- |
| `ALVR_Q3PW_DOWNSCALE` | absent or `off` | `area` | Integrate an axis-aligned area-box footprint in linear source values before the existing transfer conversion; clamp all source accesses to the submitted eye crop. |
| `ALVR_Q3PW_DITHER` | absent or `0` | `1` | Add a fixed, zero-mean 4×4 Bayer offset smaller than half an R8 code before planar quantization, in the existing conversion pass. |

Both require SDR PyroWave with foveation disabled. Invalid values fail startup.
Area filtering supports at most four source texels per output pixel on each axis;
larger or invalid eye bounds fail the frame explicitly. Equal-size/magnified samples
use clamped linear sampling. There is no new image allocation or presentation path.
Activation logs include the selected filter and dither; retain those logs with the
requested environment and matching-build identity. These logs do not prove a quality
or performance improvement.

## Reconstructed source and shader provenance

The implementation is retained in `patches/stable-baseline-alvr.patch`, after the
inherited instrumentation and Quest overlays. It preserves the old `FrameRenderPS.cso`
and `rgbtoyuvplanar.cso` byte-for-byte. Default-off composition still uses those
original shaders and its original 16-byte constant buffer. The opt-in area variant
uses a separate 48-byte constant buffer; dither uses separate planar bytecode.

`tools/windows/quality-shaders.json` records the modified HLSL/wrapper source hashes,
both legacy and experimental DXBC hashes, Windows SDK 10.0.26100.0 compiler hash and
flags: `fxc /nologo /O3 /T ps_5_0 /E PS` for the area wrapper, and `/E main` for dither.
The Windows CI job recompiles and checks the variant hashes, then runs tiny **software
WARP** readbacks. CPU references check fractional weights, DC preservation, seam
clamping, dither mean, integer neutrals and output range. WARP exercises the real
embedded shaders on a checkerboard, a fractional ramp, both cropped eyes and planar
R8 outputs. This is pixel correctness, not hardware timing.

The recorded FXC emits its existing transfer-function `pow` warnings and an area
function X4000 warning despite initialized dimensions. The tested WARP cases pass;
this is not proof for arbitrary submitted layers, projections or the PC hardware
driver. Keep those checks in the supervised/armed validation gate.

No upstream decoder/encoder code was transplanted. The changed ALVR/HLSL files retain
their upstream licences and attribution. PyroWave's newer scaling API would require
different PyroWave/Granite pins and remains a separate, unimplemented investigation.

## Finite comparison, queued until authorized

Run only in a supervised session or a valid armed window after WO-0 is merged and its
restoration dry run passes. Do not launch Metro unattended. Use one matching signed
pair and a fixed WO-3 normalized source chart. Preserve all saved settings and VD
hashes. Keep recommended-AHB allocation and synchronous direct-eye copy enabled.

1. At the chosen WO-2 geometry (initial candidate: render 3072×3232/eye, encode
   2560×2688/eye), keep TCP, Haar, 4:2:0, 90 Hz, fixed 500 Mbps and foveation off.
2. Compare **off / area / off**, changing only `ALVR_Q3PW_DOWNSCALE`. Fully restart
   the owned SteamVR processes between cells so the process-local option is read.
3. Separately compare **off / dither / off** at the same geometry, with area off.
   Do not combine both options before each independent comparison passes.
4. For every finite cell, settle for three seconds and capture a 50-second window.
   Record exact render/encode/decoded geometry, selected-output fresh counts, decode
   GPU execution and completion latency, server encode/composition proxies, workload,
   temperatures, requested environment and activation logs. Stop on faults, drift,
   missing telemetry or contention. The independent deadline guard owns rollback.
5. Restore the pre-window process environment by ending only the owned processes;
   never persist these options in Windows user/system environment variables. Verify
   exact saved settings, registration and VD hashes after restoration.

Image gates require same-input source/decoded identity from WO-1, no eye leakage or
orientation change, correct range/transfer/chroma positioning, unchanged flat-field
integer neutrals, and no new structured noise. Compare fixed text, fine texture,
dark-gradient and line crops. Area filtering may soften text or fine details; ordered
dither may add a visible pattern or consume bits. Reject a candidate if those tradeoffs
lose the recorded objective, even if a timing proxy improves. Owner headset judgement
and endurance remain required before promotion. No speedup estimate or stable 90 Hz
claim is made here.

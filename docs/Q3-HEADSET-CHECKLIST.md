# Q4 and owner-supervised headset preparation-only checklist

This is a preparation-only checklist. It does not authorize a headset, router,
SteamVR, ALVR setting, ADB, or installation action. Use it only after the Q3a/Q3b
tables, WO-10/WO-8/WO-13 merge, and a verified matching signed pair are available.

## Pinned matching build for later supervised preparation

The available matching pair is GitHub Actions run `37217852222` from source
commit `80a16353ca127508fec745dec53dc790ceb77fb2`. Its verified APK is
`Quest3-Pyrowave-stable.apk` SHA-256
`3d74c6e76964ecf752a4e0dc5414a562c92e14f2b072411f8f83f5e2d281ed53`,
signed by certificate SHA-256
`4a3fe0a8d47ee67b01710df6ffdc870e91ebc5b8e7feec7c87534944ca2a44aa`.
The matching Windows server ZIP is SHA-256
`3359e5670580e061609c5b5d7333414536285dde2279bc66aece6bf15b49610a`; its
server DLL and PyroWave shared-library members are respectively
`6f40366ed01166541471f22714090cae10b04b344c6fb43dda0f8fffc3de8670` and
`1b0a6bd0b7c978c063c58f5349f87748fd7d44806dda1ed5fc4111c19d880cc1`.
The package check also confirms the WO-10 crop, WO-8 Light centre-phase, WO-13 TCP frame-paced network
tools, and WO-7 RDO-density sources in this pair. See the paired build
record at [quality-candidate-build-80a1635-2026-10-04.json](../results/quality-candidate-build-80a1635-2026-10-04.json)
and the eventual combined quality review at
[metro-q3-combined-2026-10-04.md](../results/metro-q3-combined-2026-10-04.md).
This pin identifies a build for a later authorized session; it does not
promote any profile to a runtime default or authorize installation, connection,
or capture.

## Owner session revision — preparation, then confirmation

The owner has requested installation of this verified `80a1635` pair, replacing
the retained `d1c3b3d4edb3` pair, then Q4, cells **a, a2, b, c, d**, and **f–h**
on the winning runnable cell. Preparation is authorized now. **Wait for the
owner's confirmation to begin before installing, issuing ADB commands, starting
VR or network tests, or changing settings.** Record the confirmation with the
finite supervised session evidence; do not use or alter the unattended arm file.

Keep the original d1c3 APK/server artifacts and its extracted server directory
for rollback. Stage the new server in a separate directory. The authorized build
replacement is distinct from settings restoration: retain the verified 80a1635
pair after a healthy session and retain d1c3 for a necessary build rollback.
Snapshot current settings/registration immediately before the first change,
restore every changed value exactly, and verify them before telling the owner
that ALVR is fully restored. The owner performs the VD comparison themselves.

Ask for and retain the owner's actual in-headset judgement for every chart and
Metro cell, each f off/on/off leg, the blinded g sequence, and h movement test.
Do not infer an image, tracking, controller, audio or motion judgement from
telemetry or a previous session. Winning-cell selection requires the owner's
clarity/periphery/motion judgement as well as the recorded live measurements.

### Historical preparation finding: native RDO proof is blocked on 80a1635

Source inspection during preparation found that the live Windows encoder uses
`pyrowave_encoder_create()` in `pyrowave_c.cpp`, which sets a release
`NullLogger` before `Encoder::init()`. That logger suppresses the WO-7
`PyroWave RDO viewing density` message. The pinned Windows build has
`PYROWAVE_DEVEL=OFF`; its C API exposes no initialized-density readback.
Consequently this pair cannot supply the required native RDO confirmation for
**a, a2 or d**. A process environment value proves intent, not the density
actually held by the initialized encoder. Do not substitute it for native proof.

The offline frame-bank encoder calls `Encoder` directly, so its retained native
RDO logs and quality scores are unaffected. The earlier live-log requirement
was a planned gate, not a gate already demonstrated on 80a1635. A narrowly scoped
native getter and ALVR log bridge are prepared separately on local
`codex/wo7-live-readback`; their source checks and standalone CPU parity test
pass, while native export/build/runtime gates remain open. Using them
requires a newly built, verified matching pair and an owner decision about the
explicit 80a1635 pin. Until that decision, retain 80a1635 and mark these live
RDO-proof gates blocked. No alternate pair is installed automatically.

### 2026-10-05 corrected candidate: staged, not installed

The separately verified candidate is source `0f07f05b4df88f8fa08ea034f794cda4be9eaf38`,
from successful manual [CI run 37249212605](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37249212605).
Its [build receipt](../results/quality-candidate-build-rdo-session-2026-10-05.json)
binds the matching APK/server, dependency pins, native payloads, shaders, stable
certificate and exported `pyrowave_encoder_get_rdo_density` symbol. The original
80a1635, getter-only 71c1be0 and d1c3 artifacts remain staged separately. No pair
was installed and no headset session began overnight. Agree on the replacement
pin with the owner before a future installation.

The dashboard launches `cmd /C start steam://rungameid/250820`; an existing Steam
process can launch `vrserver.exe` without the dashboard's environment. Directly
launching `vrmonitor.exe` with a child environment proves the monitor's input,
but cannot establish the closed-source SteamVR process inheritance. Use the new
opt-in session setting for reproducible RDO selection instead:

```text
session_settings.video.pyrowave.rdo_pixels_per_degree.enabled = true
session_settings.video.pyrowave.rdo_pixels_per_degree.content = 24.0
```

The Rust connection config transfers it through `pyrowave_rdo_pixels_per_degree`
to the Windows encoder's create-info; the native getter then reports the stored
initialized value. Require a fresh native encoder marker in ALVR's warning/event
log for a2 and the RDO24 PyroWave candidate:

```text
[PYROWAVE] native encoder RDO density applied: 24 px/deg, Nyquist 12 cycles/deg, ALVR session RDO setting
```

Retain the event timestamp, current encoder/process identity and effective value.
Pinned ALVR `7eda092dbf0002281410a4222683ec228700cffb`,
`alvr/server_openvr/cpp/alvr_server/Logger.cpp:36`, routes `Warn()` to the
ALVR warning callback and conditionally to OpenVR `DriverLog` when initialized.
The Rust bridge is `alvr/server_openvr/src/lib.rs:724` and
`alvr/server_core/src/c_api.rs:202`. Source alone does not prove a
`vrserver.txt` file sink; do not make that particular filename the native-proof
gate. A launch environment or requested setting still cannot replace the fresh
initialized-encoder warning record.

For **a**, pin the same switch to `65.28` to select the bit-identical legacy
density independently of inherited environment. Its native marker must report
approximately 65.2799988 px/deg, 32.6399994 cycles/deg and `legacy 96 DPI @ 1m`.
This pins the baseline's existing encoder weighting; it does not change a's
Haar/full-FOV/500 Mbps geometry, codec or target refresh. **a2** changes only
that density to 24. Snapshot and restore both switch fields exactly. The shipped
default remains disabled, preserving the environment/legacy selection path.

Position-aware RDO, decoder-offset, width-only H.264 and stock MediaCodec logging
are separate investigation branches and are excluded from this corrected pair.
They cannot be activated by changing this pair's settings. Keep their offline
quality results separate from the runnable headset cells until native build,
matching-pair and image-correctness gates pass.

The morning offline ranking does not alter cell d: the position-RDO mode-1 and
mode-2 experiments used the same fixed 1000-Mbps cap but have regional tradeoffs
and no matching live pair. Mode 2 is an effective-density divisor, not an
eye-tracked or peripheral-acuity setting. Do not add either positional variable
to this checklist or infer a live quality, cost, fresh-submission, latency, or
90-Hz benefit from its 90-frame offline evidence.

The offline width-only H.264 branch offers a trade-off, not a replacement for c:
at 700 Mbps/P7 it gains 2.622 dB whole-crop HVS versus H264Fit, but loses
1.397 dB fence edge PSNR and changes temporal p99 from 4 to 5. Its offline
allocation is 4096×2784 SBS with eight padding rows; the prospective live crop
would be 4096×2752. Separate x/y foveation parameters exist, but the vertical
identity guard and profile require that branch's native build and a newly
verified matching pair. Neither is in the staged corrected pair. Keep c at
H264Fit until owner review and those gates justify a separate cell.

The completed reconstruction-offset sweep does not change any live cell:
none of the four tested offsets improves both the fence and calibrated HVS.
Keep the legacy zero offset. The uniform 16/20 px/deg rows also trade a very
small fence gain for HVS loss; a2 and d retain explicit uniform RDO 24.

Private PNG previews produced by different exporters are not colour-comparable.
Use the standardized full-range BT.709 comparison pack for baseline/a2 image
review; the original previews remain retained. All codec metrics and source
hashes are unaffected. Offline preview playback is not a headset, pacing,
display-FPS or optical-latency measurement.

## Final offline decode-cost ladder — quality only

The [overnight combined table](../results/metro-overnight-quality-2026-10-05.md)
adds the same Medium/softness-0.5/RDO24/1000 quality ladder and the
phase-fixed Light comparison. Fence uses frames 10–89; HVS uses all 90.

| Profile | Fence PSNR-Y dB | Temporal p99, luma codes | HVS dB |
| --- | ---: | ---: | ---: |
| Medium Haar | 39.714915 | 12 | 36.724382 |
| Medium 5/3 | 41.273421 | 11 | 37.233930 |
| Medium 9/7 (retained) | 42.412796 | 9 | 37.356360 |
| Light 9/7, phase fixed | 40.810309 | 11 | 40.698893 |

Keep d at Medium 9/7/RDO24. Light trades 1.602 dB of fence accuracy for
3.343 dB higher whole-crop HVS against Medium 9/7. This ladder measures image quality only;
it does not establish which transform is faster on Quest. The Light row
has a different encoded size and must not be used to infer a decode-speed
gain. Its baseline phase fix is in the corrected pair; new experimental
branches are not. Profile individual dequant/iDWT passes on the faster
allocation path before any further timing or promotion.

No overnight headset session occurred. Require new owner confirmation,
fresh snapshots, exact native readbacks and owner judgements before Q4
or a/a2/b/c/d. All live fields in the offline report remain unset.

## Fixed geometry distinction

The offline crop is a fixed, centred `2624x2776` per eye rectangle derived from
the `0.8542 / 0.8500` tangent multipliers. It has left offset `(278,274)` and
right offset `(170,274)` within the `3072x3232` parent eyes. It is the source and
score geometry for Q3.

The WO-10 runtime crop is different: configure the full `3072x3232` requested
per-eye render/encode geometry and set
`session_settings.video.fov_crop.content.horizontal_tangent_multiplier=0.854`
and `.vertical_tangent_multiplier=0.85`. The runtime aligns upward to
`2624x2752` per eye (`ceil32(3072*.854)=2624`,
`ceil32(3232*.85)=2752`). The offline horizontal `.8542` candidate instead
gives `ceil32(3072*.8542)=2656`; it must not be used for the runtime crop. It must
never be relabelled as the offline `2624x2776` rectangle. Require the matching
client/server `[FOV-CROP]` markers, negotiated geometry, decoder geometry, and
the active multipliers before treating a runtime crop cell as valid.

## Preconditions and retained snapshot

1. The owner starts a supervised lease explicitly covering the finite Q4 and
   headset cells. Confirm no offline GPU scorer is active and record the selected
   signed server/APK manifests, commit, dependency lock hash, shader hashes,
   APK/server checksums and signing-certificate fingerprint.
2. Save before changing anything: `python -m tools.quest3.control status`, the
   raw dashboard session document, `python -m tools.quest3.control experiment-properties
   --adb <ADB>`, current SteamVR/OpenXR registration, relevant ALVR config files,
   and read-only Wi-Fi state. Pin the Quest serial used for every ADB command.
  The raw session and experiment-property documents are evidence and per-key
  restoration inputs, not importable whole-session restore files. The only
  automatic raw restore helper is `control resolution --restore`, and it
  restores exactly the two recorded resolution settings.
   The current `control experiment-properties` and `bench capture` CLIs lack a
   `--serial` argument. Run them only in the owned child process with
   `ANDROID_SERIAL` set to the verified Quest serial in that child's environment;
   retain the launch contract. Use explicit `adb -s <QUEST_SERIAL>` for direct
   commands. Do not change the user/system environment or rely on default-device
   selection; the network CLI already requires `--serial`.
3. Require the Q4 Android receiver binary from the verified pair at
   `/data/local/tmp/q3pw/tcpframerecv-android`; do not substitute an unverified
   local binary. Before Q4, record the read-only PC link/driver evidence:

   ```powershell
   Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed,DriverInformation
   ```

   A link below 2.5 GbE makes the nominal 1000 Mbps Q4/live cells unqualified;
   retain the readback and use only a separately labelled lower-rate diagnostic.
4. The fixed **offline-quality preparation candidate** is PyroWave CDF 9/7,
   `Medium` softness `0.5`, RDO-24 and fixed 1000 Mbps. This uses the completed
   Medium default/RDO comparison and is recorded below; it is not a runtime
   default. Reconfirm it against the final combined quality review before any
   authorized headset cell. The prior approximately 82–83 fresh submissions/s
   is a baseline observation, never a 90 Hz pass.

The base controlled PyroWave apply command is:

```powershell
python -m tools.quest3.control apply --codec PyroWave --mbps <RATE> --hz 90 `
  --decode-path Compute --chroma 420 --transport Tcp --wavelet <Haar|Cdf53|Cdf97> `
  --capabilities <CAPABILITIES.json> --render-width 3072 --render-height 3232 `
  --encoded-width 3072 --encoded-height 3232
```

It explicitly selects constant bitrate, SDR, 90 Hz, TCP, 4:2:0, Compute and
turns both foveation settings off. It does **not** reset FOV crop, 10-bit,
NVENC preset, or AQ. Read back the exact session after every write. For every
full-FOV cell, explicitly set/read back `video.fov_crop.enabled = false`.
For a WO-10 crop, apply the base command first, then write and verify these
exact dashboard paths before the SteamVR restart:

```text
session_settings.video.fov_crop.enabled = true
session_settings.video.fov_crop.content.horizontal_tangent_multiplier = 0.854
session_settings.video.fov_crop.content.vertical_tangent_multiplier = 0.85
```

### Common Pyro allocation baseline for cells a, a2 and d

Cells **a**, **a2** and **d** use the same allocation baseline. First record each
property's literal readback, then set and verify both values before the required
client/decoder restart:

```powershell
adb -s <QUEST_SERIAL> shell getprop debug.q3pw.fragment_min_usage
adb -s <QUEST_SERIAL> shell getprop debug.q3pw.optimal_ahb_usage
adb -s <QUEST_SERIAL> shell setprop debug.q3pw.fragment_min_usage 1
adb -s <QUEST_SERIAL> shell setprop debug.q3pw.optimal_ahb_usage 1
adb -s <QUEST_SERIAL> shell getprop debug.q3pw.fragment_min_usage
adb -s <QUEST_SERIAL> shell getprop debug.q3pw.optimal_ahb_usage
```

Require the readback values `1`/`1`, then restart the client/decoder because
both are initialization options. Require
`[Q3PW_FRAGMENT_USAGE]` to confirm fragment conversion and all three minimal
slots. Require `[Q3PW_AHB_USAGE]` to show requested and active `1`, a nonzero
recommendation, three matching allocations, and no fallback or retry. A
missing marker, nonzero fallback, changed colour/range/eye mapping, or rate/tail
regression invalidates that cell; the requested driver recommendation alone is
not proof of use. On rollback restore each captured literal property value with
the per-key property restoration procedure and read it back; do not replace an
original unset/empty state with `0`, and do not use `0` as a generic rollback.
Keep every other experimental decoder/allocation option unchanged and recorded;
this checklist contains no allocation on/off experiment.

For a WO-8 foveation candidate, only after the runtime crop is verified, write
and verify:

```text
session_settings.video.foveated_encoding.enabled = true
session_settings.video.foveated_encoding.content.profile.variant = <Light|Medium|H264Fit>
session_settings.video.foveated_encoding.content.peripheral_softness = <0.0|0.5|1.0>
session_settings.video.foveated_encoding.content.blur_only = <true|false>
session_settings.video.foveated_encoding.content.follow_gaze = false
session_settings.video.clientside_foveation.enabled = false
```

The existing `control apply` CLI deliberately writes foveation off. Therefore
the foveation paths must be set through the dashboard's per-setting request
surface, followed by session readback and a SteamVR restart; `set_values` is
the Python helper behind `control apply`, not a generic `control` CLI command.
No later `control apply` may overwrite them unnoticed. `Light`, `Medium`,
`H264Fit`, and `Custom` are the only FoveationProfile enum values; `Custom`
also requires recording every centre/edge field it exposes. Quest 3 has no eye tracking: a `Light` candidate above softness `0.5` is a separately labelled diagnostic, not the default winner; the owner must judge both centre detail and peripheral shimmer.

### Light history and the new phase-fix qualification

The retained **pre-phase-fix** offline Light/softness-0 result at
`2624x2776 -> 2464x2592` per eye showed substantial central-fence loss before
compression. Its horizontal mapping put encoded pixel centres on source pixel
boundaries, so the area filter averaged neighbours even at softness 0. That
historical result is not an eye-assignment fault and must remain attributed to
the earlier transform.

The newer `wo8-light-centre-phase.patch` moves that half-integral Light lattice
to the lower source-texel centre and the Quest WGSL inverse subtracts the same
translation. It has a source/WARP and Python numerical gate, but it has no
headset quality or timing result yet. It must also be part of the pinned,
matching signed pair; an unpinned or mismatched phase overlay invalidates the
cell. The current zero-shift Medium and `H264Fit` profiles have zero phase for
both the offline `2624x2776` and runtime `2624x2752` geometries, so this repair
does not change their mapping.

Before accepting any Light live profile, retain the actual runtime mapping and
geometry, inspect centre fine lines and the Metro fence against the unfoveated
control, and explicitly record the owner's sharpness/aliasing judgement. The
runtime crop uses a different height, so neither historical nor repaired
offline scores establish runtime equivalence. A Light result remains a separate
controlled candidate until its image-correctness and live metrics pass.

### Runtime foveated geometry: expectation, then readback

These are separate from Q3's fixed offline `2624x2776` crop. Starting with
WO-10's runtime-cropped `2624x2752` eye, the current WO-8 `encoded_size`
helper (the ALVR 32-pixel allocation formula) gives the following expected
per-eye encoded allocations when `blur_only=false`:

| Profile | Centre / edge ratio | Expected per-eye allocation |
|---|---:|---:|
| `Light` | `0.8 / 1.5` | `2464x2592` |
| `Medium` | `0.6 / 2.0` | `2112x2208` |
| `H264Fit` | `0.5 / 2.0` | `1984x2080` |

With `blur_only=true`, all three profiles retain the complete `2624x2752`
encoded allocation; it is an image-quality prefilter experiment, not reduced
encoding. These are preflight expectations only. Every candidate must retain
its parent runtime crop and the effective encoder/decoder dimensions from
session and runtime readback after the SteamVR restart. A mismatch, missing
readback, or reuse of the offline `2776` height makes the cell unqualified.

### Exact dashboard restoration manifest

Before the first write, retain raw values for every path below. Restore only a
path that this session changed, one path at a time through the dashboard request
surface, and read it back before restarting SteamVR. There is no generic
`control set_values` command and a captured session document is not an import
format.

- The base PyroWave apply changes `preferred_codec.variant`, `preferred_fps`,
  `bitrate.mode.variant`, `bitrate.mode.ConstantMbps`,
  `enforce_server_frame_pacing`, `pyrowave.chroma_444`,
  `pyrowave.transport.variant`, `pyrowave.wavelet.variant`,
  `pyrowave.decode_path.variant`, `connection.stream_protocol.variant`,
  `foveated_encoding.enabled`, `foveated_encoding.content.follow_gaze`,
  `clientside_foveation.enabled`, `encoder_config.enable_hdr`, and
  `encoder_config.server_overrides_enable_hdr`.
- A crop cell additionally changes `fov_crop.enabled`,
  `fov_crop.content.horizontal_tangent_multiplier`, and
  `fov_crop.content.vertical_tangent_multiplier`.
- A WO-8 cell additionally changes `foveated_encoding.enabled`,
  `foveated_encoding.content.profile.variant`,
  `foveated_encoding.content.peripheral_softness`,
  `foveated_encoding.content.blur_only`, and
  `foveated_encoding.content.follow_gaze`; retain all six `center_size_*`,
  `center_shift_*`, and `edge_ratio_*` values too whenever the saved or tested
  profile is `Custom`. Restore `clientside_foveation.enabled` separately.
- A stock codec cell additionally records/restores
  `encoder_config.nvenc.quality_preset.variant`,
  `encoder_config.nvenc.adaptive_quantization_mode.variant`,
  `encoder_config.use_10bit`, and `encoder_config.server_overrides_use_10bit`
  when they were changed.

`control resolution --restore` is the sole automatic restore: it restores only
`emulated_headset_view_resolution` and `transcoding_view_resolution` from the
captured raw values, then requires its own readback. It restores none of the
paths above.

For stock-codec cells, the exact NVENC controls are
`session_settings.video.encoder_config.nvenc.quality_preset.variant` (`P1`
through `P7`) and
`session_settings.video.encoder_config.nvenc.adaptive_quantization_mode.variant`
(`Disabled`, `Spatial`, or `Temporal`). Both require a SteamVR restart. Keep
the Q3-selected preset/AQ tuple for a comparable live stock-codec cell and
record its readback. A later `P1` change is a separate diagnostic, not an
equivalent-quality substitute. For HEVC/AV1 Main10, set/read back
`session_settings.video.encoder_config.use_10bit = true` and
`session_settings.video.encoder_config.server_overrides_use_10bit = true`
before the restart. These setting values do not by themselves prove the
elementary-stream depth or hardware decoder selection.

The live AV1 candidate below intentionally uses **P4 with AQ Disabled** to
match the retained offline AV1 comparison. The owner-added AV1 Main10 / 200
Mbps / **P1 with Spatial AQ** row is a separate stock-default control. It must
be reported as that control and never substituted for the P4/AQ-off live cell
or described as a same-settings comparison.

The offline P1/Spatial-AQ control explicitly used FFmpeg `aq-strength=8`. In
the reviewed live ALVR NVENC path, selecting Spatial AQ sets NVENC
`enableAQ=1`, but the code does not assign `NV_ENC_RC_PARAMS::aqStrength`; the
strength therefore remains the selected NVENC preset/driver value. Record the
live setting as Spatial AQ enabled, with AQ strength **unknown** unless an
encoder-config readback proves it. Do not describe a live P1/Spatial capture as
an AQ-strength-8 match solely from the setting selection.

### H.264 source-audit verdict and live preflight

`docs/STOCK-H264-FOVEATION-AUDIT.md` finds a codec-independent foveation path:
the stock H.264 NVENC path can consume `H264Fit`'s single side-by-side texture,
and the non-Pyro Android MediaCodec/compositor path has the matching inverse
map. This establishes a source-backed candidate only. It does not establish
hardware decoder choice, RTX 5080 dimension acceptance, quality, freshness or
90 Hz operation.

Historical source limitation: checked-in `tools/nvenc_caps` describes an
unbuilt RTX 3090-era standalone probe and does not consume ALVR's negotiated
side-by-side geometry or block ALVR before `CreateEncoder()`. The reconstructed
ALVR Windows path likewise has no integrated H.264 `NV_ENC_CAPS_WIDTH_MAX` /
`HEIGHT_MAX` gate.

New offline evidence is the owner-authorized, no-encode DirectX capability query
in [nvenc-dimension-caps-2026-10-05.json](../results/nvenc-dimension-caps-2026-10-05.json).
It read H.264 limits of 4096 by 4096 on this RTX 5080 and accepted H264Fit's
3968 by 2080 dimensions. It did not initialize an encoder, encode a frame, query a
Quest decoder, or measure runtime performance. Cell c remains blocked until the
same actual negotiated SBS geometry is accepted by a fail-closed pre-CreateEncoder
live integration/readback, with retained SPS/profile, Android decoder identity,
quality, freshness and timing gates. The offline capability result is supporting
hardware-dimension evidence, not a live preflight or a 90 Hz qualification.

The inactive source hook is prepared separately in
[PR #56](https://github.com/ljk1291/Quest3-Pyrowave/pull/56), tested source
`0e45e06bacd20255c3706fdfb14c48a4a159988f`, with successful manual CPU-only
[run 37266489403](https://github.com/ljk1291/Quest3-Pyrowave/actions/runs/37266489403).
Only exact `ALVR_NVENC_DIMENSION_PREFLIGHT=1` selects safe width/height queries
after `FillEncodeConfig` and before `CreateEncoder`; the default makes no
capability call or marker. Its `Warn("NVENC dimension preflight passed:")`
record uses the ALVR warning route described above. Do not infer activation from
a launcher environment, a suppressed Debug message, or a specific log filename.
The hook is not in the staged 0f07f05 pair and its Windows native compilation,
matching-build and runtime gates remain open. Do not activate or silently add it
to a pinned session. Source and CPU CI preparation do not close cell c's live
geometry, decoder, quality or timing gates.

### Reproducible native RDO selection in the corrected candidate

The verified `0f07f05` candidate adds the opt-in session switch described above.
It is staged only; its installation still requires the next owner-supervised
session. Preserve the raw `enabled` and `content` values before any application.
For a, explicitly enable `65.28`; for a2 and the selected RDO24 PyroWave cell,
explicitly enable `24.0`. Restart the encoder under the supervised procedure,
read back both settings, and require its fresh native `Warn()` record to report
the effective density and `ALVR session RDO setting` source. The explicit legacy
value uses the unchanged legacy weighting calculation, rather than relying on
Steam to inherit an unset environment variable.

The environment variable remains supported for standalone offline tools and
when the session switch is disabled. It is not a reliable live selection method
when SteamVR is launched through an already-running Steam process. Historical
80a1635 suppresses the live native readback and remains blocked for a2; the
corrected candidate resolves that specific blocker without changing the default.
Restore both raw session-switch values after the comparison and verify them.
Do not change user/system environment values. Requested settings without the
native effective-value record do not establish an RDO comparison.

For each live Pyro cell, capture only after streaming is confirmed. Choose a
whole duration from 60 through 90 seconds and record it; this is a time-based
capture, never a 90-frame acceptance interval:

```powershell
python -m tools.quest3.bench capture --adb <ADB> --out <CELL_DIR> --seconds <60..90> --hz 90 `
  --build-manifest <MATCHED_BUILD_MANIFEST.json> --require-resolution-evidence
```

Use `--resolution-profile` only for an existing matching profile. Current
profiles do not describe the `2624x2752` WO-10 runtime crop, so a crop cell
must retain the explicit session/FOV/decoder evidence rather than claim a
profile check it cannot satisfy. The current `--require-resolution-evidence`
gate is PyroWave-only and requires `enable_foveated_encoding=false`; do not
use it to certify WO-8 or stock-codec cells. Preserve their requested,
negotiated, decoded and effective-config evidence, but leave formal geometry
acceptance pending a matching gate.

The offline frame-bank `F90:1` header and
`actual_mbps_external_f90_normalization` normalize a fixed source sequence for
quality comparison. They are not live encoder cadence, GPU execution, observed
fence completion, fresh submissions, display FPS, or optical timing. Retain
live per-frame timestamps and separate runtime telemetry for those claims.
## Q4 TCP frame-paced network gate

Run without an ALVR video stream. Each command is network-only and records
sanitized pre/post Wi-Fi link rate, band, channel and width. The ACK is complete
receiver-read turnaround; it is not one-way latency, decode time, fresh rate,
or display FPS.

```powershell
python -m tools.quest3.network --transport tcp --adb <ADB> --serial <QUEST_SERIAL> --ip <QUEST_WIFI_IP> `
  --tcp-receiver /data/local/tmp/q3pw/tcpframerecv-android --rates 600 800 1000 1200 `
  --seconds 300 --hz 90 --out <Q4_ROOT>\stationary

python -m tools.quest3.network --transport tcp --adb <ADB> --serial <QUEST_SERIAL> --ip <QUEST_WIFI_IP> `
  --tcp-receiver /data/local/tmp/q3pw/tcpframerecv-android --rates 800 1000 `
  --seconds 120 --hz 90 --out <Q4_ROOT>\moving
```

For every rate retain ACK-delivery p50/p99/p99.9, late-frame share, longest
completed ACK-delivery stall, censored missing-ACK lower bound, and the synthetic
`frame_byte_cap`. Q4 uses fixed-size frames; the separate live-cell telemetry
below supplies the measured variable frame-size p50/p99/max. Reject a rate if its report is incomplete, has a receiver/protocol
error, partial/unacknowledged/skipped frames, or its moving result has fewer
than 99.5% on-time scheduled frames. Let `Rmax-moving` be the highest remaining
moving rate. Define `Rlive=floor(0.85*Rmax-moving)` Mbps, then cap it by the
selected codec's verified decoder limit. Retain the values rather than assuming
1000 Mbps. Router channel/width changes, including any 160 MHz or DFS change,
are owner-only and must be logged as a new network condition.

The exact 500-Mbps a/a2 rate is covered when the same-condition moving result
qualifies `Rlive >= 500`: record that headroom-based qualification and the passing
moving rate. This is an inference from the scheduled Q4 screen, not a directly
measured 500-Mbps network leg. Do not add an unrequested network leg or describe
it as a measured 500-Mbps result.

The scheduled moving screen tops out at 1000 Mbps, so its 15% headroom rule
can qualify at most 850 Mbps. It cannot qualify the exact 1000-Mbps PyroWave
cell by itself. For the owner's next-session approval, include one conditional
120-second moving 1200-Mbps leg only after the stationary 1200 and moving 1000
legs pass. A passing 1200 leg yields `Rlive=1020`, before the decoder cap.
Otherwise keep the nominal 1000-Mbps cell explicitly unqualified; do not
silently lower it or remove the headroom requirement.

## Live cells, in order

The listed nominal rates are deliberate. A cell runs only if Q4 and the selected
codec's verified decoder limit support its exact rate; otherwise it is recorded
unqualified rather than silently reduced to `Rlive`. Run a 60–90 second chart
capture and the same owner-selected Metro fence scene. Preserve the runtime
marker, requested/negotiated/decoded geometry, codec path, packet-size
p50/p99/max, and native per-frame encode telemetry.

Keep these fields separate in every result: `gpu_decode_ms` (GPU execution only
when an explicit decoder GPU query produced it), `observed_fence_completion_ms`,
`fresh_submissions_per_s`, and `estimated_pipeline_latency_ms` (ALVR
`total_pipeline_latency_s`). Do not derive one from another or call any of them
display/optical FPS or optical latency. For stock AV1/H.264 cells, set
`gpu_decode_ms = null` unless a stock decoder GPU query is actually available;
the present source paths do not provide one. Set any missing fresh-rate or
estimated-pipeline field to `null`, with a reason, rather than filling it from
the F90 normalization or an offline timing estimate.

### Live telemetry record, initially blank

Populate this table only from the corresponding headset cell. The retained
approximately 82–83 fresh submissions/s observation belongs to the historical
baseline; it is not a value for any blank cell and does not establish 90 Hz.

| Cell | GPU decode execution ms | Observed fence completion ms | Fresh submissions/s | Estimated pipeline latency ms | Optical FPS / latency |
|---|---:|---:|---:|---:|---:|
| a | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — no optical measurement |
| a2 | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — no optical measurement |
| b | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — no optical measurement |
| c | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — no optical measurement |
| d | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — pending headset | `null` — no optical measurement |

| Cell | Exact intended configuration | Runnable state and gate |
|---|---|---|
| a | Today’s full baseline: PyroWave Haar, 4:2:0, Compute, TCP, SDR, 90 Hz, fixed 500 Mbps; `fov_crop=false`, WO-8 off, and the common allocation baseline above. On the corrected candidate, explicitly enable the session RDO switch with content `65.28`; require the native encoder log to report legacy default effective `65.28` px/deg and Nyquist `32.64` cycles/deg (allow the established float-log tolerance). | Baseline comparison only. Record and restore the raw RDO switch `enabled` and `content` values exactly. It is not evidence of a 90 Hz pass merely because the historical rate was ~82–83/s. Require Q4 to establish that the requested rate is transport-feasible; do not silently replace 500 with `Rlive`. |
| a2 | Immediately after a: identical full-FOV Haar / 500 Mbps configuration and common allocation baseline, except the explicit session RDO content is `24.0`. | Require the native encoder initialization log to show requested/effective `24` px/deg and Nyquist `12` cycles/deg. Restart the encoder with that explicit session setting; retain all other a settings/property values and compare their readbacks. Use the same chart and owner-selected Metro scene and ask the owner for each judgement. Restore both original RDO session-switch values exactly when finished. Missing native activation proof or any other changed comparison knob invalidates the a/a2 comparison. |
| b | Stock single-SBS AV1: WO-10 crop, AV1 Main10 requested, fixed 200 Mbps, 90 Hz, SDR, NVENC `P4`, AQ `Disabled`. Set/read `preferred_codec=AV1`, `use_10bit=true`, `server_overrides_use_10bit=true`, `quality_preset=P4`, and `adaptive_quantization_mode=Disabled`, then restart SteamVR. | This is the P4/AQ-off live comparison, distinct from the offline P1/Spatial-AQ stock-default control. Source supports these settings but AV1 can negotiate/fall back to HEVC. Block/mark inconclusive without AV1 negotiated-codec readback, elementary-stream Main10 proof, MediaCodec identity/output evidence, and the runtime crop proof. `gpu_decode_ms` is null unless a real stock decoder GPU query is added. |
| c | Stock single-SBS H.264: WO-10 crop + WO-8 `H264Fit`, softness `0.5`, fixed 700 Mbps, 90 Hz, SDR, NVENC `P7`, AQ `Disabled`, 8-bit. | The completed H264Fit row ranks well on the fence; require the final comparison and close the live H.264 audit gates before capture: active-device dimension acceptance/preflight, matching phase-patch provenance, negotiated/decoded `3968x2080` SBS evidence, H.264 SPS/profile evidence, and Quest decoder identity. Explicitly set/read `use_10bit=false`, `server_overrides_use_10bit=true` and AQ `Disabled` to match the offline row, then restore their original values. Stock ALVR two-per-eye H.264 remains unimplemented and the offline dual-stream rows are not runnable live cells. |
| d | Selected **offline-quality preparation candidate**: PyroWave CDF 9/7, WO-10 crop + WO-8 `Medium` softness `0.5`, 4:2:0, Compute, TCP, SDR, fixed 1000 Mbps, RDO-24 (explicit session switch enabled, content `24.0`), and the common allocation baseline above. Require the native encoder log to report effective `24` px/deg and Nyquist `12` cycles/deg. | The completed Medium default/RDO pair is clean and shares the exact reduced input; RDO-24 has the stronger measured Medium fence: its tight-fence 10–89 edge PSNR-Y / temporal p99 / mean / all-90 HVS are `42.4128 dB / 9 codes / 1.3552 codes / 37.3564`, versus retained default `37.5434 dB / 15.32 codes / 2.6052 codes / 36.2617`. Its broad whole-image HVS remains below cropped Q3a RDO-24 (`43.0088`), which is a recorded transform/profile quality tradeoff rather than a default-setting decision. This is not a runtime promotion: retain the pending 32-row review, Q4 transport qualification at 1000 Mbps, matching WO-8 phase-pinned builds, runtime crop and Medium encoded-geometry readback. Apply the requested/effective native RDO session-setting and restoration gate above; no blur-only substitute for the reduced-encode candidate. |
| f | The winning runnable cell, init-only `debug.q3pw.layer_filter` `0 -> 1 -> 0`, with all other applied keys and `Rlive` unchanged. | Set each value with `adb -s <QUEST_SERIAL> shell setprop debug.q3pw.layer_filter <0|1>`, read it back, and restart the client for every leg. For the `1` leg, require its `[Q3PW_LAYER_FILTER]` startup record to show the requested active flags; missing/unsupported/invalid activation fails the cell. Require identical settings/readback around all legs; judge fence aliasing and any new blur. |
| g | The winning runnable cell, nominal fixed-rate steps `1000 -> 600 -> 1000` Mbps, 10 seconds each, without telling the owner the transition times. | Run only if the selected codec and network have verified 1000 Mbps support. Keep stream, scene and all non-rate keys fixed; retain packet-size telemetry and the owner's blinded change judgement. If the verified cap `Rlive < 1000`, mark this nominal test unqualified/unavailable. A capped `Rlive -> 600 -> Rlive` sequence may be recorded only as an owner-review alternative, never as the same requested test. |
| h | The winning runnable cell at `Rlive`, owner turns 360°, crouches and moves a hand near the headset. | Record Q4-style stalls/late frames, fresh submissions, observed fence completion and subjective stutter. |

For any candidate requiring stock H.264 dual-eye transport, stop at the label
`BLOCKED: WO-11 live dual-stream transport/prototype qualification absent`.
Never recast the offline two-stream FFmpeg/NVENC proxy as a stock-ALVR selection.

## Per-cell acceptance and rollback

1. A valid cell has matching signed build identity; complete telemetry; settings
   and runtime readback; exactly the requested codec/wavelet/transport/chroma;
   the recorded 60–90 second capture interval; no decoder/device failure or
   disconnect; and an owner image/motion judgement. Missing any item records a
   failed/inconclusive cell, never a pass.
2. A stable 90 Hz pass requires confirmed 90 Hz runtime operation and fresh
   submissions sustained at the declared threshold. Fresh submission rate,
   observed fence completion, GPU execution and display/optical FPS remain
   distinct fields. Optical FPS and optical latency stay `null` unless an
   independent optical measurement exists; no completion or pipeline value may
   fill either field.
3. On any failure, stop the current cell and preserve its private logs and
   partial artifacts. Restore the raw resolution snapshot with `python -m
   tools.quest3.control resolution --restore <RESOLUTION_SNAPSHOT.json>`.
   Restore each changed dashboard and Android experiment property from its
   recorded raw before-value, one key at a time, with readback; no tool may
   submit a captured whole session document as a replacement. Restart SteamVR
   when any restored setting has the restart flag. Verify the saved
   registration/config/APK/server hashes and post-restore session readback.
4. Restore the saved raw values of both `video.fov_crop` and
   `video.foveated_encoding` rather than assuming defaults. If the saved crop
   switch was disabled, verify that the runtime no longer emits an active
   `[FOV-CROP]` marker; if it was enabled, record that the marker is expected
   after restoration. Restore the saved router state only by owner action if it
   was changed.
5. Do not install, uninstall, pair, or alter Virtual Desktop during this session.
   After ALVR restoration is independently verified, the owner launches VD and
   Metro and compares the selected preparation candidate against VD H.264+ Godlike on the same
   fence scene. Record the owner's clarity, shimmer and motion judgement; the
   agent does not operate VD.

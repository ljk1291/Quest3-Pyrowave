# Quest compositor layer-filter experiment

`debug.q3pw.layer_filter` is an init-only Quest 3 experiment. It leaves the
shipping behaviour unchanged when unset or `0`.

| Property | Requested filter | Requirement | Active flags |
| --- | --- | --- | --- |
| `0` or unset | off | none | no settings chain |
| `1` | normal supersampling | `XR_FB_composition_layer_settings` | `NORMAL_SUPER_SAMPLING` |
| `2` | quality supersampling | `XR_FB_composition_layer_settings` | `QUALITY_SUPER_SAMPLING` |
| `3` | automatic normal supersampling | both `XR_FB_composition_layer_settings` and `XR_META_automatic_layer_filter` | `NORMAL_SUPER_SAMPLING | AUTO_LAYER_FILTER` |

The client reads the property before it creates its OpenXR instance. It enables
only the advertised extensions required by the requested mode. Missing support,
an invalid value, and every non-Quest platform produce no settings chain. The
client logs one `[Q3PW_LAYER_FILTER]` startup record for an active, unsupported
or invalid request, with the requested mode and active flags. Off adds no new
startup log. It chains the settings only to the **stream** projection
layer; lobby, passthrough, and the local performance quad remain untouched.

The settings node is heap-owned by the projection wrapper and is kept alive for
the synchronous `xrEndFrame` call. It is then dropped normally. This is
important: a pointer to a stack-local raw OpenXR structure would be unsafe if
the wrapper moved before submission. The returned wrapper also borrows the
builder, keeping its projection-view array alive through submission.

The flag values and automatic mode's required companion flag follow the
[Khronos flag specification](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrCompositionLayerSettingsFlagBitsFB.html).

## Finite comparison protocol

Do not run this outside an armed unattended window or an owner-supervised
session. Use a verified matching Android/Windows build pair and preserve the
existing profile: 3072x3232 per eye, 90 Hz, Haar, 4:2:0, TCP, SDR, direct eye
copy, `fragment_min_usage=1`, `optimal_ahb_usage=1`, and 500 Mbps. Record the
full property snapshot, negotiated render and encoded geometry, build identity,
frame counter, thermal samples, and the one startup activation record.

1. Restart the client with `debug.q3pw.layer_filter=0`; warm up, then take one
   bounded chart-rate screen and a separate unobstructed image-quality capture.
2. Restore the identical profile, set exactly one candidate (`1`, then on a
   separate trial `2`, or `3`), restart the client, and reject the cell unless
   the startup record reports the requested nonzero active flags.
3. Repeat the `0` cell. Stop and restore after a decoder/encoder fault,
   disconnect, setting drift, missing telemetry, missing activation record, or
   thermal stop.

Rate captures assess fresh submissions, completion counters, and compositor-cost
proxies. Image frames are a separate run with exact source/decoded identity;
manual in-headset judgement remains required for line shimmer. No result may
attribute an artifact to the codec or the layer filter without the matching
controls.

## Integration verification, 2026-10-03

The cumulative ALVR patch was regenerated with the merged WO-5 PC filters from
the pinned ALVR plus instrumentation/Quest patch base. A separate clean apply
reproduced all 30 changed files: the three WO-4 client files and every WO-5 file
byte-for-byte. Reverse application, the subsequent fork-identity patch, and the
Windows shader manifest checks passed. The legacy default shader binaries remain
unchanged. CI runs the three pure Rust filter-policy tests without an OpenXR
runtime before compiling the client. These source checks do not establish a
Quest quality or performance improvement.

The first combined build failed: `StreamContext::new` still had its baseline
signature while the caller supplied the filter flags. The integration review
had missed WO-4's fourth client file, `stream.rs`, shared with the baseline
patch. The corrected reconstruction includes its constructor, stored flags and
projection-layer chain. All other WO-5 files remain byte-identical, the clean
apply/reverse and fork-identity checks pass, and the shader manifest is unchanged.
This correction requires a new full CI result before merge.

## T2 token vocabulary, 2026-10-06

The additive presentation overlay extends this numeric policy with `sharpen`,
`sharpen_hq`, `supersample`, `supersample_hq` and companion `auto` tokens, keeping
0–3 behavior. See [T2 configuration, exact flags, attribution and pending gates](T2-PRESENTATION-FILTERS.md).
Unknown/empty tokens and auto-only requests reject the complete request. Missing
advertised extensions produce no chain. Normal and HQ together are valid and normal
takes precedence under the FB spec. Active native logs now retain the raw request
alongside flags. Six pure Rust tests cover vocabulary, atomic rejection and support
mapping; Actions execution and this fork's headset acceptance remain pending.

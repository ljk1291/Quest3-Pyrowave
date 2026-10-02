# Render and encode geometry candidates

This runbook changes no default. It prepares three **candidates** for an owner-supervised Metro comparison and a separately armed unattended chart screen. It does not establish image quality, sustainable 90 Hz, or a recommended profile.

The ALVR settings are per eye:

| Setting | ALVR/OpenVR effect | Evidence recorded |
| --- | --- | --- |
| `emulated_headset_view_resolution` | SteamVR recommended game render target | requested and negotiated render eye size |
| `transcoding_view_resolution` | server composition/encode and client decode/output size | requested and negotiated encode eye size; decoder-reported stereo frame size |

The render request is `3072x3216`. ALVR rounds each axis upward to 32 pixels, so its expected negotiated render size is `3072x3232`. The candidate encode sizes are `3072x3232`, `2560x2688`, and `2080x2208`.

## Candidate profiles and payload budget

The runbook requires TCP, 4:2:0, Haar, Compute, SDR, fixed 500 Mbps, 90 Hz, foveation disabled, direct synchronous eye copy, and the recommended-AHB allocation. The profile command changes only the two ALVR geometry settings, so preflight/readback must verify every other requirement rather than assuming it.

| Profile | Requested render | Aligned render | Requested/encoded eye | 500 Mbps at 90 Hz |
| --- | --- | --- | --- | --- |
| `godlike-3072` | 3072x3216 | 3072x3232 | 3072x3232 | 0.280 bits/stereo-pixel, 694,444 bytes/frame |
| `quality-2560` | 3072x3216 | 3072x3232 | 2560x2688 | 0.404 bits/stereo-pixel, 694,444 bytes/frame |
| `quality-2080` | 3072x3216 | 3072x3232 | 2080x2208 | 0.605 bits/stereo-pixel, 694,444 bytes/frame |

The payload cap is a rate budget, not achieved bitrate, network throughput, image-quality score, or decoder performance prediction. Regenerate the values from the tracked profile file:

```powershell
python -m tools.quest3.budget --resolution-profiles presets/resolution-comparison.json
```

## Apply, verify, and exactly restore geometry

Save every command's JSON under the private capture directory. The returned `previous_resolution_settings` preserves raw ALVR values, including Scale/optional-height forms, for reversible restoration. Never reconstruct a previous setting from the aligned dimensions.

```powershell
# Read the active session first.
python -m tools.quest3.control status

# Example: apply the 2560 encode candidate; this changes only geometry.
python -m tools.quest3.control resolution --profile quality-2560 `
  | Tee-Object results/local/geometry-quality-2560-apply.json

# For an unattended normalized-chart cell, restart/reconnect through the existing
# owner-approved process, start the WO-3 chart, then verify geometry during capture.
python -m tools.quest3.bench capture --adb adb --hz 90 --seconds 60 `
  --resolution-profile quality-2560 --require-resolution-evidence `
  --scene-metadata results/local/geometry-quality-2560-source/scene.json --require-scene-geometry `
  --out results/local/geometry-quality-2560-r1

# Restore the exact saved pre-change values, then restart/reconnect and read back status.
python -m tools.quest3.control resolution --restore results/local/geometry-quality-2560-apply.json
python -m tools.quest3.control status
```

`bench capture` records `resolution_evidence` with separate aligned requested, negotiated and decoder-reported dimensions. A geometry-profile capture fails closed as `resolution_mismatch` when known dimensions conflict, or `resolution_evidence_incomplete` when any required decoder evidence is absent. It does not substitute a requested or negotiated size for decoder evidence.

The normalized stereo chart belongs to WO-3. Start it only after the client reconnects, using its `--normalized-chart --source-eye 3072 3232` interface. Its `scene.json` must record `source_eye_size: [3072, 3232]` and `normalized_chart: true`; pass it through `--scene-metadata ... --require-scene-geometry`. This pins chart source geometry while the three candidate cells vary encoded/decode geometry; an absent or mismatched record fails the chart cell closed.

## Owner-supervised Metro A/B/A

Metro gameplay and visual judgement are owner tasks. Do not run this sequence unattended.

1. Snapshot current ALVR/SteamVR/VD state and confirm the matching signed server/client pair, fixed Metro checkpoint, game graphics, SteamVR scale, no competing GPU job, and baseline direct-copy/recommended-AHB properties.
2. Run `godlike-3072` for a fixed warm-up, then capture 60 seconds of telemetry at the same checkpoint using `--resolution-profile godlike-3072 --require-resolution-evidence`. Record fresh selected outputs, decoder timings, bitrate, errors, exact geometry and owner notes on text, fog/gradients, fine foliage and line shimmer.
3. Apply one candidate (`quality-2560` first; repeat the whole sequence later for `quality-2080`), restart/reconnect, re-check the same conditions, then make the matching capture and owner observation at the same checkpoint.
4. Return to `godlike-3072`, restart/reconnect, repeat the capture and owner observation. This final A distinguishes a geometry effect from order, warm-up and thermal drift.
5. Restore the pre-session geometry using the saved JSON and verify the original settings/VD hashes. A failed readback, geometry mismatch, decoder/encoder fault, visible corruption, settings drift, or restoration mismatch invalidates that comparison.

Do not call a lower encoded geometry sharper, higher quality, faster, or a 90-Hz pass without the paired evidence and owner judgement. The game may render a texture different from SteamVR's recommendation; record available game/SteamVR evidence separately.

## Queued unattended chart cells

These cells may run only after WO-0 is merged, the owner has armed a valid window, and every [unattended precondition](UNATTENDED.md) passes. They do not include Metro.

For each sequence, use a fixed normalized chart, 60-second finite capture, and the same 90 Hz / 500 Mbps / Haar / Compute / fast-AHB settings:

1. `godlike-3072` (A)
2. `quality-2560` (B), then `godlike-3072` (A)
3. After a comparable cooldown and baseline re-check: `godlike-3072` (A), `quality-2080` (B), `godlike-3072` (A)

Each cell uses `--resolution-profile <name> --require-resolution-evidence`, captures the WO-3 scene metadata, and stops on a geometry failure, decoder/encoder fault, settings drift, thermal/battery stop, or restorer failure. The independent deadline restorer owns return-to-baseline; never extend an arm file or alter it from this runbook. These are diagnostic chart cells, not gameplay acceptance.

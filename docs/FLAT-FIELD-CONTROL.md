# Flat-field panel-mura control

This is WO-3's controlled diagnostic. It does not establish that a codec causes
panel mura, compression artefacts, optical image quality, or a 90 Hz pass.

`tools.quest3.stereo_scene` has three opt-in source modes. Its ordinary chart
is unchanged when no new option is supplied.

| Mode | Purpose | Source telemetry |
| --- | --- | --- |
| `--flat 16`, `24`, `48`, or `128` | Label-free, deterministic neutral full field | `flat_rgb_code`, `source_neutral_rgb_codes` |
| `--neutral-patches` | The Session 07 range-chart variant with 0/16/32/64/128/192/235/255 neutral patches | `neutral_patch_chart`, `source_neutral_rgb_codes` |
| no new mode | Existing orientation/chart diagnostic | Existing metadata plus an empty `source_neutral_rgb_codes` list |

`--flat` accepts any integer RGB code from 0 through 255. It is mutually
exclusive with the quality and neutral-patch charts, and cannot be combined
with `--pulse`: labels or a changing pulse would invalidate a uniform-field
comparison. Full fields intentionally omit eye labels; use the ordinary chart
in a separate functional/tracking check.

Use `--source-eye WIDTH HEIGHT` to pin the submitted source texture to the
recorded render geometry instead of asking SteamVR for its current recommendation.
For render/encode comparisons, add `--normalized-chart`: it scales the legacy
2080×2208 reference canvas into that source texture and records
`normalized_chart: true` and `reference_canvas_eye: [2080, 2208]`. At the
reference dimensions its pixels are byte-identical to the legacy chart. This
keeps chart placement and line widths comparable as render geometry changes;
the decoded/encoded geometry remains separate evidence. Normalization has no
meaning for a full field and is rejected with `--flat`.

The pinned-canvas contract follows the inspected upstream geometry-control
revision [`2f6f0878484aae8904f47a8a964505e29d5befab`](https://github.com/JMS1717/Quest3-Pyrowave/commit/2f6f0878484aae8904f47a8a964505e29d5befab).
This fork keeps the reference canvas explicit rather than treating source and
encoded dimensions as interchangeable.

## Queued comparison

This run is only permitted in an armed unattended window after WO-0's supervisor
has passed its dry run, or as an owner-supervised test. It must use a verified
matching signed APK/server pair, identical render and encoded geometry, refresh,
transport, chroma, range, SteamVR scale, headset placement, thermal state and
scene duration. Preserve the normal snapshot and restoration requirements in
[UNATTENDED.md](UNATTENDED.md).

For each chosen code, queue finite PyroWave / HEVC / PyroWave cells. The exact
codec setting is the only intentional change. Settle for three seconds, capture
the approved finite timing window, record source metadata, requested and
negotiated settings, selected-output evidence, host/thermal samples and both
endpoint readbacks. Stop and restore on a fault, settings drift, missing
telemetry or failed pixel check. Do not create or edit an arm file for this
comparison.

Capture source/reference PNGs and screenshots privately under `results/local/`.
The sanitized report may state whether the same visible non-uniformity appears
in matched PyroWave and HEVC fields. It must not name a codec or the panel as the
cause without those completed controls.

## Owner judgement

The owner separately views the same fields in-headset, with the dashboard and
performance HUD absent where possible, and records field code, codec, geometry,
whether the field looks uniform, and any location/pattern of non-uniformity.
That subjective judgement is not an unattended result and does not replace the
timing, identity, or restoration gates. Compare it only after the functional
chart confirms both eyes, orientation and changing source content.

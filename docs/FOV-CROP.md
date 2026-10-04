# Opt-in FOV crop

`video.fov_crop` is disabled by default. When enabled, it accepts
`horizontal_tangent_multiplier` and `vertical_tangent_multiplier` in the inclusive
range 0.5–1.0. The candidate is horizontal `0.854` and vertical `0.850`.

The client scales the tangent of each OpenXR FOV side about the optical axis. It
therefore preserves the measured left/right asymmetric eye frusta, reports that
same cropped FOV to ALVR, and submits it on the stream projection layer. The
server applies the same factors to both the requested render and stream size and
pads each dimension upward to a 32-pixel boundary. `[FOV-CROP]` log entries on
both sides record the active values and resulting sizes.

At 3072×3232 per eye, the candidate produces 2624×2752: `3072 × 0.854` rounds
up to 2624 and `3232 × 0.850` rounds up to 2752. The Q3 frame-bank's
2624×2776 geometry is a separate, centred offline comparison rectangle. It is
not a runtime size override.

Older servers without the negotiated multiplier field decode as identity. A
present malformed or out-of-range multiplier rejects stream setup so the server
cannot render one FOV while the client presents another.

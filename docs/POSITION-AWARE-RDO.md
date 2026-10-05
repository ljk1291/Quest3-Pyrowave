# Position-aware PyroWave RDO

This encoder-only overlay retains the existing coefficient orientation and band-midpoint RDO model. It does not change the bitstream syntax or decoder. `PYROWAVE_RDO_POSITIONAL` is disabled when unset or `0`; the shader returns exactly `1.0` before calculating position, so the default uses the prior RDO arithmetic. Modes `1` and `2` additionally require an explicit, non-legacy `PYROWAVE_RDO_PX_PER_DEG` and the fixed 5248x2776 dual-eye crop. Any invalid mode or geometry fails initialization rather than selecting a fallback.

The crop geometry is the Session-07 projection calibration reused by Session 09. Each 2624x2776 eye uses left `[-1.17589234, 0.71649807, -1.22520507, 0.83088732]` tangent bounds. The right bounds `[-0.71649807, 1.17589234, -1.22520507, 0.83088732]` are a mirror derived from the retained left-eye calibration, not an independent right-eye measurement. The crop centre is not assumed to be the optical axis.

For tangent coordinates `(tx, ty)`, `spanx = right-left`, and `spany = top-bottom`, the scalar uses:

```
PPDx = W/spanx * (1 + tx^2 + ty^2) / sqrt(1 + ty^2) * pi/180
PPDy = H/spany * (1 + tx^2 + ty^2) / sqrt(1 + tx^2) * pi/180
physicalPPD = sqrt(PPDx * PPDy)
localPPD = requestedPPD * physicalPPD(tx, ty) / physicalPPD(0, 0)
```

The optical-axis normalization leaves a requested 24 PPD equal to 24 at `(0, 0)`; it does not substitute an absolute calibration PPD. The geometric mean yields one scalar for each code block, avoiding an unreviewed horizontal/vertical coefficient preference. The existing orientation midpoint remains responsible for the coefficient-specific CSF.

Mode `1` multiplies the existing distortion term by `(CSF(localCPD) / CSF(uniformCPD))^2`. Mode `2` divides `localPPD` by `1 + min(1, eccentricity / cropEdge)`, where `cropEdge` is the farthest of the four eye-frustum corners. It is a bounded (at most twofold) falloff hypothesis, not a quality claim: its interaction with the band-sensitive CSF can redistribute bits non-monotonically.

The native log records the mode and calibration frusta. The patch and shader are pinned by `sources.lock.json`; the planned offline matrix is crop 97/1000 with explicit 24 PPD, once for each mode, with centre/fence/periphery reporting. It is a plan only and does not schedule a runtime or headset capture.

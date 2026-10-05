# Supervised RDO chart checkpoint — 2026-10-05

Cell a confirms visible compression on the diagonal chart lines and falls short
of sustained 90 fresh submissions/s. Cell a2 confirms native RDO 24 activation,
but the session stopped before its complete capture. No live quality improvement
or stable 90 Hz result is established. [Sanitized JSON](metro-rdo-supervised-2026-10-05.json)
binds the retained private evidence by SHA-256.

The owner authorized installation and the visual comparison before Q4. The
installed corrected APK is source `0f07f05b4df88f8fa08ea034f794cda4be9eaf38`;
its pulled installed bytes match the verified stable-signed APK. The isolated
server uses the matching verified native payloads. The 80a1635 and d1c3 rollback
pairs remain intact. See the [build receipt](quality-candidate-build-rdo-session-2026-10-05.json).

Both requested cells use Haar, full FOV, no foveation, 500 Mbps, TCP, 4:2:0,
Compute, SDR, direct-eye copy and the faster AHardwareBuffer allocation path.
Requested render and encoded dimensions are 3072×3232 per eye; cell a's decoded
stereo dimensions are verified as 6144×3232. These aligned dimensions do not
establish identical VD projection or image quality.

| Cell | Native RDO px/deg | GPU decode median / p95 ms | Decode-to-fence median / p95 ms | Fresh submissions/s | Estimated pipeline median ms | Owner judgement / outcome |
|---|---:|---:|---:|---:|---:|---|
| a: full-FOV Haar / 500 | 65.2799988, legacy equivalent | 9.033 / 9.337 | 11.456 / 12.244 | 84.076 | 67.170 | Upright chart; compression clearly visible on diagonal lines. Diagnostic only. |
| a2: same profile / RDO 24 | 24.0, native session-setting marker | — | — | — | — | Chart started; no complete capture. Retrospective owner judgement pending. |

Cell a requested 60 seconds, with 66.088 seconds capture elapsed and a verified
59.256-second fresh-counter window. GPU and completion summaries contain 5072
samples. The runtime freshly reports 90 Hz, while the requested-rate screen and
sustained-rate checks both fail. GPU execution, CPU-observed completion, fresh
submissions and the estimated pipeline are distinct measurements. Optical FPS
and optical latency remain unset.

The SteamVR Library dashboard overlaid the chart during cell a's telemetry
capture. The owner dismissed it afterward and then reported visible compression;
an unobstructed screenshot is retained privately. The raw capture has verified
stream dimensions but **unknown scene metadata**. Do not use it as a clean
matched chart timing reference for the decode ladder. Colour and motion quality
were not confirmed for this cell. Screenshots are qualitative exports, not
source-pixel or through-lens measurements.

The last successful guard sample recorded 10% battery while charging; after the
stop it read 9%, below the retained 10% floor. The owner removed controller
thermal cutoffs for this supervised session; temperature was still sampled and
the Quest's built-in protections were unchanged. The original controller
overwrote the terminal stop text during restoration, so the exact terminal
reason is unavailable. The low-battery readback independently prevents another
cell. The private controller now preserves stop text; 39 CPU guard/adapter tests
pass. No new signed application build or installation followed this fix.

All **48 changed keys** now match their saved values. SteamVR scale is restored
to 150%; the temporary ALVR driver registration is removed; VD settings hashes,
driver registration inventory and the OpenXR runtime match the pre-session
snapshot. Owned Windows VR/chart jobs and the test client are stopped. The
corrected APK remains installed, with rollback artifacts preserved.

The independent restorer first rejected an unexpected empty
`debug.oculus.refreshRate` value. Its failure is retained. After verifying all
Windows test runtimes were stopped and closing only the test client, the recorded
value `72` was restored and every changed key was read back. The drift's origin
is unverified. SteamVR's whole-file hash changed through UI placement and GPU
calibration entries; those unrelated writes were preserved, while both changed
supersampling keys were verified exactly.

A/a2 Metro, Q4, both full-FOV 1000-Mbps comparisons and the remaining headset
cells were not run. Resume with a clean matched a/a2 chart comparison once the
headset has sufficient charge and the owner confirms a new finite session.
No default is promoted.

# H264Fit live-preflight build candidate

This candidate is exactly corrected pair source
`0f07f05b4df88f8fa08ea034f794cda4be9eaf38` plus the reviewed NVENC
dimension-capability overlay from PR #56. Dependency revisions, RDO selection
and getter, WO-8 mapping, client identity, signing and stable defaults are retained.

Only exact child-process `ALVR_NVENC_DIMENSION_PREFLIGHT=1` enables the check.
The initialized NVENC session queries width/height limits for the actual encode
GUID and final side-by-side dimensions, before `CreateEncoder()`. Missing or
nonpositive caps fail closed. The native warning marker is
`NVENC dimension preflight passed:` with requested and maximum dimensions.

For a supervised H264Fit preview, require 3968 x 2080 at the WO-10 crop,
700 Mbps, P7, AQ disabled, 8-bit SDR and requested 90 Hz. Fresh marker ownership
must be bound to the launched vrserver PID/start time; the launcher environment
alone is not activation proof. Launching through an already-running Steam
process cannot be assumed to propagate environment. If the owned direct
vrmonitor launch does not yield a fresh marker, stop this candidate and add an
explicit opt-in session setting rather than changing system/user environment.

Matching artifact/certificate/native-payload verification is required before
installation. This build is not installation authorization, a network pass,
Quest MediaCodec acceptance, image correctness or sustained 90 fresh frames/s.
Keep the installed 0f07f05 pair and both earlier rollback artifacts intact.

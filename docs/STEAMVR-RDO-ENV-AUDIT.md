# SteamVR RDO environment audit

`PYROWAVE_RDO_PX_PER_DEG` is read by the native PyroWave encoder during
`Encoder::init()` in the pinned PyroWave source's `pyrowave_encoder.cpp`. The
new readback marker reports the stored result only after that initialization.

ALVR's Windows dashboard launcher cannot reliably carry a process environment
to `vrserver.exe`. In the pinned ALVR source,
`alvr/dashboard/src/steamvr_launcher/windows_steamvr.rs` starts
`cmd /C start steam://rungameid/250820`. Steam may already be running and is
free to create the SteamVR processes independently of that command's inherited
environment. Do not use a dashboard launch or a user-scoped environment change
to select RDO density.

The repository's supported launcher for a controlled PyroWave session is
`tools/windows/start_steamvr_pyro_clean.cmd`, used by the
`XRWiredSteamVRPyroClean` task. It invokes a per-session
`<workspace>/bench/pyro_env.cmd` in its own `cmd.exe` process and directly
starts SteamVR's `vrmonitor.exe`. Put the one-time override there before
launching:

```cmd
set "PYROWAVE_RDO_PX_PER_DEG=24"
```

This gives `vrmonitor.exe` the requested value and is the best available
process-inheritance path in the current implementation. SteamVR's closed
source process topology still prevents a source-only guarantee that a later
`vrserver.exe` receives it. A session may call this method reliable only when
the corrected pair's `vrserver.txt` contains the exact marker:

```text
[PYROWAVE] native encoder RDO density applied: 24 px/deg, Nyquist 12 cycles/deg, PYROWAVE_RDO_PX_PER_DEG
```

Absent that marker, treat the density as unproven and stop the cell rather than
inferring it from the launcher, the dashboard, or the parent process.

The default remains the legacy 96-DPI-at-one-metre calculation when the
variable is unset. A future opt-in session setting can remove this
process-propagation dependency, but it must be a separately built and verified
pair; it is not part of the corrected readback-only pair.

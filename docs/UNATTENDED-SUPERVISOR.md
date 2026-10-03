# Unattended supervisor source review

This tool implements the owner window rules in [UNATTENDED.md](UNATTENDED.md).
It does not open a window merely by importing the module or validating an arm.
The arm command is for the owner. Agents leave an existing arm file unchanged.

Every start requires a fresh successful check, the same arm digest and deadline,
unchanged saved settings, repeated live preconditions, and new nonce/PID-bound
guard records with valid timestamps. Every ADB call uses the pinned serial and
the explicit ADB executable. The independent workers release Windows execution
state when they exit. The monitor revokes the window on owner activity,
unclaimed VR/VD use, unrecorded configuration drift, lost telemetry, or a changed
arm. Thermal/workload pauses and an unhealthy guard also deny the lease.

Mutation, ownership and rollback writers share an OS-backed lock. Restoration
revokes the lease before waiting, so no subsequent child may start. An update
already in flight finishes within the lock; rollback reloads its recorded keys
and undoes it. Crashed holders release the lock. A stale restoration marker
cannot block a retry. A lock timeout leaves the lease revoked and records a
separate failed attempt; it cannot overwrite a writer's state or publish a
competing final result. The final restoration record is saved both in state and
`restoration.json`. Repeated restoration is idempotent; late cleanup/fault/runtime
claims cannot overwrite final state.

The supervisor verifies VD files and the global OpenXR selection. It has no
global OpenXR selector mutation adapter: use a process-local `XR_RUNTIME_JSON`
for a permitted chart, or queue selector changes for owner supervision. This is
an explicit limitation, not a promise to restore an arbitrary external selector
change. Likewise, only verified owned PIDs may be stopped. A remaining unclaimed
VR runtime makes rollback fail rather than killing the owner's processes. A
cold ALVR session file is copied only after claimed runtimes are stopped; an
unchanged file is verified without rewriting it, and unclaimed drift is retained
and reported as a failure. Chart/property/installation orchestration still needs
its guarded controller integration and matching stable-signed pair gate before
those actions are usable unattended. The current owner arm permits PC frame-bank
work only.

CPU verification includes actual thread exclusion, an abruptly exiting lock
holder, simultaneous job registration, an API update overlapping restoration,
exception publication, lock-timeout recovery, repeated restoration, final-state
preservation, timestamp rejection, settings drift and monitor failure. These
checks use fake hosts and do not establish a live hardware rollback. Before the
first offline codec job, merge only after full CI, then run the required bounded
check/start/restore dry run and verify exact saved configuration and VD hashes.

## Additional rollback review, 2026-10-03

The stopped dashboard's live API cannot be assumed available. Full snapshots now
restore exact ALVR/SteamVR bytes only after the owned runtimes stop and all current
differences match recorded changes or their original values. Partial setup is
accepted; unrelated changes and corrupt backups are retained and reported. VD
files and global runtime selection remain verification-only. Key-only compatibility
rollback also rejects unexpected values before writing.

The independent restorer retries an actual state-lock timeout at most three times
(60 seconds per attempt), with a revoked lease throughout. Exhaustion records
attempt failures without publishing a competing final state. Process cleanup binds
the executable and start time to a retained Windows process handle; it never falls
back to terminating a newly looked-up PID. A finite disposable CPU-child regression
tests rejection of a mismatched identity and termination of the owned child. Eleven
new rollback regressions bring the focused fake-host suite to 75 passing tests;
corrupt VD backups cannot report a successful restoration.
Neither these checks nor green CI replace the required armed dry run.

Seven further regressions (82 total) enforce the arm's action list for settings
mutations and reject legacy/unknown property changes. A `frame_bank_pc` or
install-only arm cannot mutate VR/device settings. SteamVR updates must address
the saved settings path. OpenXR checks also compare the runtime manifest bytes,
and startup refuses corrupt backups before guard/mutation setup.

Short offline jobs now use `OpenProcess`, `QueryFullProcessImageNameW` and
`GetProcessTimes` to obtain identity on one retained handle without starting a
shell. Creation time uses the same millisecond convention as cleanup. Both
Windows CPU checks pass locally, including a short child that could finish
before the former PowerShell query. No GPU execution or timing claim follows
from this process-registration test.

New window state also retains its allowed actions. PC-only cleanup verifies
headset properties without force-stopping the client or replaying setprop;
unexpected property drift fails restoration without overwriting the owner.
Two regressions cover unchanged state and drift. Device-window cleanup preserves
the required client-stop-before-property-restore ordering.

## First live precondition check, 2026-10-03

The first PC-only check refused before opening a window. The Quest reported
74%, 33 °C, thermal status 0 and Android AC/charging, with Windows independently
confirming the armed physical USB device. AC alone remains insufficient: startup
accepts that classification only with charging/full status and the pinned USB
presence proof. An explicit discharging state still fails.

On this WDDM host NVIDIA listed resident shell/browser contexts, while Windows
reported 539 engine counters and zero active engines. The workload detector now
joins the resident-process inventory to per-process engine activity. Active
Comfy GPU work fails even with an idle queue; a running/pending/unknown queue
also fails independently. Missing engine telemetry fails closed. These are
precondition detector corrections, not performance or GPU metric results.

The retained check also showed one Comfy-discovery row was the PowerShell query
itself. Discovery now excludes probe shells, including parallel monitor probes.
A disposable Windows CPU-child regression exercises that case; a stopped Comfy
server is no longer misidentified solely because the probe contains its name.

The resident VD Streamer supplied no current connection log. Its connection gate
remains closed; the agent does not stop VD to get around it. The owner is asked
to disconnect and exit the Streamer themselves. No test window, settings mutation,
VR launch or GPU workload occurred in this failed check.

## Startup publication review, 2026-10-03

Two CPU-thread regressions reproduce a startup writer overwriting a completed
restorer: `restoration.json` said restored while `state.json` had reverted to
pending, with the old guard-ready flag. Both guard-registration writes now use
the same OS-backed mutex as rollback, reload state under that mutex, and reject
cancelled, restoring, completed or different-nonce windows. They recheck the
guard readiness and liveness before publication. A stop arriving during the
write refuses startup; the waiting restorer reloads and publishes the final
state. Late registration cannot overwrite it. Historical ready flags alone do
not grant a lease after restoration.

Initial state creation uses that mutex too. A second creator cannot replace an
existing window or clear its readiness/cancellation markers. Eight new regressions
bring the focused CPU suite to **105 passing checks** on Windows. The race cases
use the real CLI, threads and lock with fake hardware hosts; they perform no ADB,
VR launch or GPU work. [Sanitized reproduction](../results/supervisor-startup-race-2026-10-03.json).
Full CI and the successful armed check/start/restore dry run are still required.

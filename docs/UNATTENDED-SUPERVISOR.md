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

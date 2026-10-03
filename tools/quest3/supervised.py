"""Owner-attested, finite PC-only leases. No arm, ADB, VR or settings access.

The independent worker monitors competing GPU work and stops only registered
children on cancellation, expiry or parent death. This is not an unattended
authorization mechanism; the caller must retain the owner's session attestation.
"""
from __future__ import annotations
import argparse
import contextlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from . import unattended as u

FRESH_SECONDS = 60
AUTHORITY = 'owner_supervised_pc'

def alive(record, nonce, host):
    try:
        actual = host.process_identity(record['pid'])
        return not actual.get('exited', False) and u.ownership_matches(record, actual, nonce)
    except Exception:
        return False

def status_payload(directory, *, host=None, now=None, require_allow='frame_bank_pc'):
    directory = Path(directory)
    host = host or u.Host()
    now = time.time() if now is None else now
    state = u.json_read(directory/'state.json')
    nonce = state.get('guard_nonce')
    attestation = state.get('authorization', {})
    deadline = state.get('deadline_epoch_s')
    monitor = state.get('monitor', {})
    blockers = []
    if (attestation.get('kind') != AUTHORITY or attestation.get('owner_present') is not True
            or not isinstance(attestation.get('evidence'), str) or not attestation['evidence'].strip()
            or attestation.get('allow') != ['frame_bank_pc'] or require_allow != 'frame_bank_pc'):
        blockers.append('owner_attestation_missing_or_wrong_scope')
    if (not isinstance(deadline, (int, float)) or not math.isfinite(deadline) or now >= deadline):
        blockers.append('deadline_expired')
    stopped = (directory/'stop').exists() or state.get('closed') is True
    if stopped: blockers.append('stop_requested')
    monitor_alive = alive(monitor, nonce, host)
    if not monitor_alive: blockers.append('monitor_dead')
    if not alive(state.get('parent', {}), nonce, host): blockers.append('parent_dead')
    sampled = monitor.get('sample_epoch_s')
    fresh = isinstance(sampled, (int, float)) and math.isfinite(sampled) and 0 <= now-sampled < FRESH_SECONDS
    if not fresh or monitor.get('ready') is not True: blockers.append('monitor_not_ready_or_stale')
    conflicts = monitor.get('conflicts', ['gpu_status_unknown'])
    if conflicts: blockers.append('competing_gpu')
    return {'schema': 1, 'authorization': attestation,
            'lease': {'active': not blockers, 'deadline_epoch_s': deadline, 'blockers': blockers},
            'guards': {'monitor': {'ready': monitor.get('ready') is True, 'alive': monitor_alive}},
            'cancellation': {'stop_requested': stopped, 'paused': False,
                             'competing_gpu': conflicts, 'monitor_fresh': fresh}}

class JobRegistry:
    def register(self, state_path, pid, arm_path=None, *, host=None):
        if arm_path is not None: raise u.Refusal('supervised PC lease does not accept an arm')
        state_path = Path(state_path)
        host = host or u.Host()
        with u.state_lock(state_path):
            if not status_payload(state_path.parent, host=host)['lease']['active']:
                raise u.Refusal('supervised PC lease inactive')
            state = u.json_read(state_path)
            actual = host.process_identity(pid)
            if actual.get('exited'): raise u.Refusal('child already exited')
            record = {**actual, 'role': 'pc_job', 'nonce': state['guard_nonce']}
            if any(row['pid'] == pid for row in state['owned_pc_jobs']): raise u.Refusal('job already registered')
            state['owned_pc_jobs'].append(record)
            u.atomic_write(state_path, state)
            return record
    def unregister(self, state_path, pid):
        with u.state_lock(state_path):
            state = u.json_read(state_path)
            state['owned_pc_jobs'] = [row for row in state['owned_pc_jobs'] if row['pid'] != pid]
            u.atomic_write(state_path, state)

def stop_jobs(state, host):
    errors = []
    for row in state.get('owned_pc_jobs', []):
        try: host.stop_owned_runtime(row)
        except Exception as exc: errors.append(str(exc))
    return errors

def worker(directory, nonce):
    directory = Path(directory)
    state_path = directory/'state.json'
    host = u.Host()
    while True:
        # Sample outside the mutex, then exclude freshly registered identities.
        sample = host.gpu_sample()
        with u.state_lock(state_path):
            state = u.json_read(state_path)
            if state['guard_nonce'] != nonce: raise u.Refusal('supervised lease identity changed')
            sample = u.exclude_owned_compute_jobs(state, host, sample)
            state['monitor'].update(ready=True, sample_epoch_s=time.time(), conflicts=sample['conflicts'])
            state['last_gpu_sample'] = sample
            u.atomic_write(state_path, state)
            status = status_payload(directory, host=host)
            if not status['lease']['active']:
                (directory/'stop').touch()
                state['closed'] = True
                state['stop_reasons'] = status['lease']['blockers']
                state['cleanup_errors'] = stop_jobs(state, host)
                u.atomic_write(state_path, state)
                return
        time.sleep(2)

@contextlib.contextmanager
def session(directory, *, evidence, duration_s=5400):
    """Create once, after explicit owner authorization; never inspect the arm."""
    if not isinstance(evidence, str) or not evidence.strip(): raise ValueError('owner attestation required')
    if not isinstance(duration_s, (int, float)) or not math.isfinite(duration_s) or not 0 < duration_s <= 7200:
        raise ValueError('PC session duration must be finite and at most two hours')
    directory = Path(directory).resolve()
    private = (u.ROOT/'results/local').resolve()
    if not directory.is_relative_to(private): raise ValueError('lease must remain private')
    directory.mkdir(parents=True, exist_ok=False)
    host = u.Host()
    nonce = uuid.uuid4().hex
    state = {'schema': 1, 'authorization': {'kind': AUTHORITY, 'owner_present': True,
             'evidence': evidence, 'allow': ['frame_bank_pc']}, 'guard_nonce': nonce,
             'deadline_epoch_s': time.time()+duration_s, 'owned_pc_jobs': [], 'closed': False,
             'parent': {**host.process_identity(os.getpid()), 'nonce': nonce}, 'monitor': {}}
    path = directory/'state.json'
    u.atomic_write(path, state)
    with (directory/'monitor.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'tools.quest3.supervised', 'worker',
                                 '--window', str(directory), '--nonce', nonce], cwd=u.ROOT,
                                stdout=log, stderr=log, creationflags=0x08000000 if os.name=='nt' else 0)
        with u.state_lock(path):
            state = u.json_read(path)
            state['monitor'].update(host.process_identity(proc.pid), nonce=nonce)
            u.atomic_write(path, state)
        try:
            startup = time.monotonic()+45
            while not status_payload(directory)['lease']['active']:
                if proc.poll() is not None or (directory/'stop').exists() or time.monotonic() >= startup:
                    raise u.Refusal('supervised monitor startup failed')
                time.sleep(.5)
            yield directory
        finally:
            (directory/'stop').touch()
            try: proc.wait(timeout=45)
            except subprocess.TimeoutExpired:
                # The independent worker normally does this; retain a finite
                # fallback that never stops unrelated applications.
                with u.state_lock(path):
                    state = u.json_read(path)
                    state['cleanup_errors'] = stop_jobs(state, host)
                    state['closed'] = True
                    u.atomic_write(path, state)
                proc.terminate(); proc.wait(timeout=10)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'worker'])
    parser.add_argument('--window', required=True)
    parser.add_argument('--require-allow', default='frame_bank_pc')
    parser.add_argument('--nonce')
    args = parser.parse_args(argv)
    if args.command == 'worker': worker(args.window, args.nonce); return 0
    value = status_payload(args.window, require_allow=args.require_allow)
    print(json.dumps(value))
    return 0 if value['lease']['active'] else 2

if __name__ == '__main__': raise SystemExit(main())

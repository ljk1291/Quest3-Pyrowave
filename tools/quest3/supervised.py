"""Owner-attested, finite PC-only leases. No arm, ADB, VR or settings access.

The independent worker monitors competing GPU work and stops only registered
children on cancellation, expiry or parent death. This is not an unattended
authorization mechanism for headset work; the caller must retain the owner's
session attestation. An explicit PC-only authorization while the owner is away
records that fact separately, without claiming physical presence.
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
from . import contention

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
    presence_authorized = (attestation.get('owner_present') is True or
        (attestation.get('owner_present') is False and
         attestation.get('owner_authorized_while_away') is True))
    if (attestation.get('kind') != AUTHORITY or not presence_authorized
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
            'measurement_policy':state.get('last_policy'),
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
            if state.get('measurement_mode')=='timing' and state.get('last_policy',{}).get('timing_invalidation_reasons'):
                raise u.Refusal('this timing measurement is invalid under the contention policy')
            actual = host.process_identity(pid)
            if actual.get('exited'): raise u.Refusal('child already exited')
            record = {**actual, 'role': 'pc_job', 'nonce': state['guard_nonce']}
            if any(row['pid'] == pid for row in state['owned_pc_jobs']): raise u.Refusal('job already registered')
            state['owned_pc_jobs'].append(record)
            u.atomic_write(state_path, state)
            return record
    def unregister(self, state_path, pid, *, completion_observed=False):
        with u.state_lock(state_path):
            state = u.json_read(state_path)
            completed=next((row for row in state['owned_pc_jobs'] if row['pid']==pid),None)
            state['owned_pc_jobs'] = [row for row in state['owned_pc_jobs'] if row['pid'] != pid]
            if completed is not None:
                completed['completed_epoch_s']=time.time()
                # Popen.poll()/wait() is the authoritative parent-side proof
                # that this exact registered child exited. Do not preserve the
                # stale ``exited: false`` captured at registration.
                if completion_observed:
                    completed['exited'] = True
                    completed['completion_observed_by_parent'] = True
                state.setdefault('completed_pc_jobs',[]).append(completed)
            u.atomic_write(state_path, state)
            return completed

def stop_jobs(state, host):
    errors = []
    for row in state.get('owned_pc_jobs', []):
        try: host.stop_owned_runtime(row)
        except Exception as exc: errors.append(str(exc))
    return errors

def _close_owned_jobs(state_path, host, nonce, *, reason):
    """Best-effort terminal cleanup under the state mutex, without reopening a lease."""
    with u.state_lock(state_path):
        state = u.json_read(state_path)
        if state.get('guard_nonce') != nonce:
            raise u.Refusal('supervised lease identity changed before cleanup')
        errors = stop_jobs(state, host)
        state['closed'] = True
        state.setdefault('cleanup_errors', []).extend(errors)
        state.setdefault('cleanup_reasons', []).append(reason)
        u.atomic_write(state_path, state)
        if errors:
            raise u.Refusal('registered PC job cleanup failed')

def worker(directory, nonce):
    directory = Path(directory)
    state_path = directory/'state.json'
    host = u.Host()
    try:
      while True:
        # Sample outside the mutex, then exclude freshly registered identities.
        sample = host.gpu_sample()
        sample['gpu_telemetry']=contention.telemetry(host)
        with u.state_lock(state_path):
            state = u.json_read(state_path)
            if state['guard_nonce'] != nonce: raise u.Refusal('supervised lease identity changed')
            sample = u.exclude_owned_compute_jobs(state, host, sample)
            now=time.time()
            decision=contention.evaluate(sample,mode=state.get('measurement_mode','quality'),now=now,
                above_since=state.get('last_policy',{}).get('above_since_epoch_s'))
            state['last_policy']=decision
            state['monitor'].update(ready=True, sample_epoch_s=now, conflicts=decision['stop_reasons'])
            state.setdefault('gpu_load_samples',[]).append({'epoch_s':now,**sample['gpu_telemetry'],
                'external_max_engine_percent':decision['external_max_engine_percent'],
                'compute_backend_reasons':decision['compute_backend_reasons'],
                'stop_reasons':decision['stop_reasons'],
                'timing_invalidation_reasons':decision['timing_invalidation_reasons']})
            if decision['timing_invalidation_reasons']:
                for job in state['owned_pc_jobs']:
                    job.setdefault('timing_invalidation_reasons',[]).extend(
                        reason for reason in decision['timing_invalidation_reasons']
                        if reason not in job.get('timing_invalidation_reasons',[]))
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
    except Exception:
        (directory/'stop').touch()
        try:
            _close_owned_jobs(state_path, host, nonce, reason='monitor_worker_error')
        except Exception:
            # The parent session has the independent final cleanup fallback.
            pass
        raise

@contextlib.contextmanager
def session(directory, *, evidence, duration_s=5400, measurement_mode='quality',
            owner_present=True, owner_authorized_while_away=False):
    """Create once, after explicit owner authorization; never inspect the arm."""
    if not isinstance(evidence, str) or not evidence.strip(): raise ValueError('owner attestation required')
    if type(owner_present) is not bool or type(owner_authorized_while_away) is not bool:
        raise ValueError('owner presence and away authorization must be explicit booleans')
    if not owner_present and not owner_authorized_while_away:
        raise ValueError('owner absence requires explicit PC-only away authorization')
    if measurement_mode not in ('quality','timing'): raise ValueError('unknown measurement mode')
    if not isinstance(duration_s, (int, float)) or not math.isfinite(duration_s) or not 0 < duration_s <= 7200:
        raise ValueError('PC session duration must be finite and at most two hours')
    directory = Path(directory).resolve()
    private = (u.ROOT/'results/local').resolve()
    if not directory.is_relative_to(private): raise ValueError('lease must remain private')
    directory.mkdir(parents=True, exist_ok=False)
    host = u.Host()
    nonce = uuid.uuid4().hex
    state = {'schema': 1, 'authorization': {'kind': AUTHORITY, 'owner_present': owner_present,
             'owner_authorized_while_away': owner_authorized_while_away,
             'evidence': evidence, 'allow': ['frame_bank_pc']}, 'guard_nonce': nonce,
             'deadline_epoch_s': time.time()+duration_s, 'owned_pc_jobs': [], 'closed': False,
             'measurement_mode':measurement_mode,
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
            # Whether the monitor observed cancellation itself or died first,
            # the owning session publishes a closed state and stops only jobs
            # whose identities were registered in this lease.
            try:
                _close_owned_jobs(path, host, nonce, reason='session_finally')
            except Exception:
                # Preserve the stop marker and surface terminal cleanup failure
                # to the caller; do not report a successful lease teardown.
                raise

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'worker', 'start', 'stop'])
    parser.add_argument('--window', required=True)
    parser.add_argument('--require-allow', default='frame_bank_pc')
    parser.add_argument('--nonce')
    parser.add_argument('--owner-attested',help='quote the explicit owner authorization from the current session')
    parser.add_argument('--owner-authorized-while-away',action='store_true',
                        help='record explicit current PC-only authorization while the owner is absent')
    parser.add_argument('--duration-s',type=float,default=5400)
    parser.add_argument('--measurement-mode',choices=['quality','timing'],default='quality')
    parser.add_argument('--allow',choices=['frame_bank_pc'],default='frame_bank_pc')
    args = parser.parse_args(argv)
    if args.command == 'worker': worker(args.window, args.nonce); return 0
    if args.command == 'start':
        if not args.owner_attested or not args.owner_attested.strip():
            parser.error('start requires --owner-attested from the current owner session')
        try:
            with session(args.window,evidence=args.owner_attested,duration_s=args.duration_s,
                         measurement_mode=args.measurement_mode,
                         **({'owner_present':False,'owner_authorized_while_away':True}
                            if args.owner_authorized_while_away else {})) as directory:
                print(json.dumps({'ready':True,'allow':['frame_bank_pc'],
                                  'measurement_mode':args.measurement_mode}),flush=True)
                while status_payload(directory)['lease']['active']: time.sleep(1)
        except KeyboardInterrupt: return 130
        return 0
    if args.command == 'stop':
        directory=Path(args.window).resolve()
        if not directory.is_relative_to((u.ROOT/'results/local').resolve()):
            parser.error('lease must remain private')
        if u.json_read(directory/'state.json').get('authorization',{}).get('kind')!=AUTHORITY:
            parser.error('not an owner-supervised PC lease')
        (directory/'stop').touch();return 0
    value = status_payload(args.window, require_allow=args.require_allow)
    print(json.dumps(value))
    return 0 if value['lease']['active'] else 2

if __name__ == '__main__': raise SystemExit(main())

import threading, time
import pytest
from tools.quest3 import unattended as u

def test_same_process_threads_exclude_each_other(tmp_path):
    state=tmp_path/'state.json'; u.atomic_write(state,{})
    entered=threading.Event(); release=threading.Event(); result=[]
    def first():
        with u.state_lock(state): entered.set(); release.wait(1)
    def second():
        entered.wait(1)
        try:
            with u.state_lock(state,timeout_s=.05): result.append('entered')
        except u.Refusal: result.append('timeout')
    a=threading.Thread(target=first); b=threading.Thread(target=second); a.start(); b.start(); b.join(); release.set(); a.join()
    assert result==['timeout']

def test_dead_holder_lock_is_released(tmp_path):
    state=tmp_path/'state.json'; u.atomic_write(state,{})
    with u.state_lock(state): pass
    with u.state_lock(state,timeout_s=.1): pass

def test_late_cleanup_preserves_final_state(tmp_path):
    state=tmp_path/'state.json'; u.atomic_write(state,{'restoration':{'status':'restored'},'owned_pc_jobs':[{'pid':1}]})
    assert u.unregister_owned_pc_job(state,1) is None
    assert u.json_read(state)['restoration']['status']=='restored'


def test_crashed_process_holder_releases_os_lock(tmp_path):
    import subprocess, sys
    state=tmp_path/'state.json'; u.atomic_write(state,{})
    code="from tools.quest3.unattended import state_lock; import os,sys;\nwith state_lock(sys.argv[1]): os._exit(0)"
    child=subprocess.run([sys.executable,'-c',code,str(state)],timeout=3)
    assert child.returncode==0
    with u.state_lock(state,timeout_s=.5): pass

def test_two_concurrent_writers_are_serialized(tmp_path):
    state=tmp_path/'state.json'; u.atomic_write(state,{'count':0})
    def bump():
        with u.state_lock(state):
            value=u.json_read(state); value['count']+=1; time.sleep(.02); u.atomic_write(state,value)
    a=threading.Thread(target=bump); b=threading.Thread(target=bump); a.start(); b.start(); a.join(); b.join()
    assert u.json_read(state)['count']==2

def test_restore_exception_publishes_failure(monkeypatch,tmp_path):
    state=tmp_path/'state.json'; u.atomic_write(state,{'serial':'Q3','adb':'adb','snapshot':{'headset_properties':{'managed':{}},'configuration_snapshots':[]},'restoration':{'status':'pending'}})
    class H:
        def adb_run(self,*a): raise RuntimeError('device gone')
        def vr_connected(self): return False
    monkeypatch.setattr(u,'managed_properties',lambda:())
    result=u.restore(state,H())
    assert result['status']=='restore_failed' and u.json_read(state)['restoration']['status']=='restore_failed'


def test_two_job_records_preserved_under_lock(monkeypatch,tmp_path):
    state=tmp_path/'state.json'; u.atomic_write(state,{'guard_nonce':'n','restoration':{'status':'pending'},'owned_runtime':[{}],'owned_pc_jobs':[]})
    monkeypatch.setattr(u,'status_payload',lambda *a,**k:{'lease':{'active':True,'blockers':[]}})
    class H:
        def process_identity(self,pid): return {'pid':pid,'path':f'C:/j{pid}.exe','started_epoch_s':float(pid)}
    threads=[threading.Thread(target=lambda i=i:u.register_owned_pc_job(state,i,f'C:/j{i}.exe',float(i),host=H())) for i in (1,2)]
    [x.start() for x in threads]; [x.join() for x in threads]
    assert {x['pid'] for x in u.json_read(state)['owned_pc_jobs']}=={1,2}

def test_late_fault_preserves_final_bytes(tmp_path):
    state=tmp_path/'state.json'; final={'restoration':{'status':'restored'},'terminal_faults':[]} ; u.atomic_write(state,final); before=state.read_bytes()
    import pytest
    with pytest.raises(u.Refusal): u.record_terminal_fault(state,'decoder')
    assert state.read_bytes()==before


def test_escaping_restore_body_publishes_failure(monkeypatch,tmp_path):
    state=tmp_path/'state.json'; u.atomic_write(state,{'restoration':{'status':'pending'}})
    monkeypatch.setattr(u,'_restore_locked',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('boom')))
    import pytest
    with pytest.raises(RuntimeError): u.restore(state)
    assert u.json_read(state)['restoration']['status']=='restore_failed'


class RestoreHost:
    def adb_run(self, *args): return ''
    def vr_connected(self): return False
    def stop_owned_runtime(self, record): return True


def restore_state(path):
    u.atomic_write(path, {'serial':'Q3','guard_nonce':'n','guards_ready':True,
                         'deadline_epoch_s':time.time()+3600,
                         'snapshot':{'headset_properties':{'managed':{}},'configuration_snapshots':[]},
                         'owned_runtime':[{'role':'dashboard'}],
                         'restoration':{'status':'pending'}})


def test_inflight_setting_is_observed_and_undone_after_restore_revokes(monkeypatch,tmp_path):
    from tools.quest3 import control, preflight
    path=tmp_path/'state.json'; restore_state(path)
    entered=threading.Event(); release=threading.Event(); errors=[]; applied=[]
    settings={'session_settings':{'test':1}}
    def status(*args,**kwargs):
        stopped=(tmp_path/'stop').exists()
        return {'lease':{'active':not stopped,'blockers':['stop'] if stopped else []},'arm':{'allowed_actions':['chart_cells']}}
    def current(): return settings
    def set_values(values):
        value=values['session_settings.test']
        if value==2:
            entered.set()
            if not release.wait(3): raise TimeoutError('test mutation did not release')
        settings['session_settings']['test']=value; applied.append(value)
    monkeypatch.setattr(u,'status_payload',status)
    monkeypatch.setattr(control,'session',current)
    monkeypatch.setattr(control,'set_values',set_values)
    monkeypatch.setattr(preflight,'verify_snapshot',lambda rows:[])
    def mutate():
        try: u.apply_alvr_changes(path,{'session_settings.test':2},api=(current,set_values))
        except Exception as exc: errors.append(exc)
    def restore():
        try: u.restore(path,RestoreHost())
        except Exception as exc: errors.append(exc)
    writer=threading.Thread(target=mutate); restorer=threading.Thread(target=restore)
    writer.start(); assert entered.wait(1); restorer.start()
    deadline=time.monotonic()+1
    while not (tmp_path/'stop').exists() and time.monotonic()<deadline: time.sleep(.01)
    try:
        assert (tmp_path/'stop').exists(), 'restoration must revoke before the writer unlocks'
        assert not status()['lease']['active']
        assert restorer.is_alive()
    finally:
        release.set(); writer.join(4); restorer.join(4)
    assert not writer.is_alive() and not restorer.is_alive() and not errors
    final=u.json_read(path)
    assert applied==[2,1] and settings['session_settings']['test']==1
    assert final['changes'][0]['before_value']==1
    assert final['restoration']['status']=='restored' and final['restoration']['alvr_restored']
    assert u.json_read(tmp_path/'restoration.json')==final['restoration']


def test_repeated_restore_and_stale_claim_remain_idempotent(monkeypatch,tmp_path):
    from tools.quest3 import preflight
    path=tmp_path/'state.json'; restore_state(path)
    monkeypatch.setattr(preflight,'verify_snapshot',lambda rows:[])
    u.atomic_write(tmp_path/'restoration.lock',{'pid':999999,'at_utc':'old'})
    first=u.restore(path,RestoreHost()); before=path.read_bytes()
    for _ in range(3):
        assert u.restore(path,RestoreHost())==first
        assert path.read_bytes()==before and not (tmp_path/'restoration.lock').exists()


def test_lock_timeout_cannot_overwrite_writer_or_publish_competing_final(monkeypatch,tmp_path):
    from tools.quest3 import preflight
    path=tmp_path/'state.json'; restore_state(path); before=path.read_bytes()
    entered=threading.Event(); release=threading.Event()
    def holder():
        with u.state_lock(path): entered.set(); release.wait(2)
    thread=threading.Thread(target=holder); thread.start(); assert entered.wait(1)
    monkeypatch.setattr(u,'RESTORE_LOCK_SECONDS',.04)
    try:
        with pytest.raises(u.Refusal,match='state lock timeout'): u.restore(path,RestoreHost())
        assert path.read_bytes()==before
        assert not (tmp_path/'restoration.json').exists()
        assert (tmp_path/'stop').exists() and (tmp_path/'restoration.lock').exists()
        assert len(list(tmp_path.glob('restore-attempt-*.json')))==1
    finally: release.set(); thread.join(3)
    monkeypatch.setattr(preflight,'verify_snapshot',lambda rows:[])
    assert u.restore(path,RestoreHost())['status']=='restored'


def test_late_runtime_claim_preserves_final_bytes(tmp_path):
    path=tmp_path/'state.json'; restore_state(path)
    value=u.json_read(path); value['restoration']={'status':'restored'}; u.atomic_write(path,value)
    before=path.read_bytes()
    with pytest.raises(u.Refusal): u.record_owned_runtime(path,{},RestoreHost())
    assert path.read_bytes()==before


@pytest.mark.parametrize('stage', ['restorer', 'monitor'])
def test_startup_publication_cannot_revive_a_restored_window(monkeypatch, tmp_path, stage):
    """Race a real CPU-thread restoration against each CLI startup state write."""
    from datetime import timedelta
    from pathlib import Path
    from types import SimpleNamespace
    from tools.quest3 import preflight
    path=tmp_path/'state.json'; arm_path=tmp_path/'arm.json'
    arm={'headset_serial':'Q3','allow':['frame_bank_pc']}; arm_path.write_text('{}')
    deadline=u.utc_now()+timedelta(hours=1)
    snapshot={'headset_properties':{'managed':{}},'configuration_snapshots':[], 'preflight':{}}
    u.atomic_write(tmp_path/'check.json', {'passed':True,'snapshot':snapshot,'serial':'Q3',
        'arm_sha256':u.arm_digest(arm),'checked_utc':u.utc_now().isoformat(),
        'window':{'deadline_utc':deadline.isoformat()}})
    original_write=u.atomic_write; finished=threading.Event(); threads=[]; errors=[]
    def restore():
        try: u.restore(path, RestoreHost())
        except Exception as exc: errors.append(exc)
        finally: finished.set()
    def write(target, value):
        guards=value.get('guard_pids', {}) if isinstance(value,dict) else {}
        if Path(target)==path and stage in guards and not threads:
            thread=threading.Thread(target=restore); threads.append(thread); thread.start()
            until=time.monotonic()+1
            while not (tmp_path/'stop').exists() and time.monotonic()<until: time.sleep(.005)
            assert (tmp_path/'stop').exists(), 'restoration must revoke before its lock wait'
            # Without the startup mutex the restorer can finish before this stale
            # write. With it, the restorer waits and reloads the published state.
            finished.wait(.15)
        original_write(target,value)
    def spawn(state_path, monitor):
        role='monitor' if monitor else 'restorer'; pid=20 if monitor else 10
        state=u.json_read(state_path)
        original_write(tmp_path/(role+'.ready'), {'pid':pid,'role':role,
            'nonce':state['guard_nonce'],'ready_utc':u.utc_now().isoformat()})
        return SimpleNamespace(pid=pid)
    monkeypatch.setattr(u,'atomic_write',write)
    monkeypatch.setattr(u,'load_arm',lambda _: (arm, {'deadline':deadline}))
    monkeypatch.setattr(u,'spawn_worker',spawn)
    monkeypatch.setattr(u,'pid_alive',lambda _: True)
    monkeypatch.setattr(u,'live_preconditions',lambda *args: ([],{},0))
    monkeypatch.setattr(preflight,'verify_snapshot',lambda _: [])
    monkeypatch.setattr('sys.argv',['unattended.py','start','--arm',str(arm_path),'--window',str(tmp_path)])
    try:
        with pytest.raises(SystemExit): u.main()
    finally:
        for thread in threads: thread.join(3)
    assert threads and all(not t.is_alive() for t in threads) and not errors
    final=u.json_read(path)
    assert final['restoration']['status']=='restored'
    assert u.json_read(tmp_path/'restoration.json')==final['restoration']
    status=u.status_payload(tmp_path,arm_path)
    assert not status['lease']['active']
    assert {'stop_requested','restoration_started'} <= set(status['lease']['blockers'])
    before=path.read_bytes()
    with pytest.raises(u.Refusal,match='cancelled'):
        u.publish_started_guard(path,'monitor',20,final['guard_nonce'],all_ready=True)
    assert path.read_bytes()==before


def test_two_startup_creators_cannot_claim_the_same_window(tmp_path):
    path=tmp_path/'state.json'; barrier=threading.Barrier(2); created=[]; refused=[]; errors=[]
    def create(nonce):
        try:
            barrier.wait(timeout=2)
            u.create_startup_state(path,{'guard_nonce':nonce,'restoration':{'status':'pending'}})
            created.append(nonce)
        except u.Refusal: refused.append(nonce)
        except Exception as exc: errors.append(exc)
    threads=[threading.Thread(target=create,args=(nonce,)) for nonce in ('first','second')]
    for thread in threads: thread.start()
    for thread in threads: thread.join(3)
    assert all(not t.is_alive() for t in threads) and not errors
    assert len(created)==len(refused)==1 and u.json_read(path)['guard_nonce']==created[0]


@pytest.mark.parametrize('existing', ['state', 'stop', 'pause'])
def test_startup_creation_retains_existing_window_and_markers(tmp_path, existing):
    path=tmp_path/'state.json'; ready=tmp_path/'restorer.ready'; ready.write_text('original readiness')
    if existing=='state': u.atomic_write(path,{'restoration':{'status':'restored'}})
    else: (tmp_path/existing).write_text('owner cancellation')
    saved={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(u.Refusal,match='already'):
        u.create_startup_state(path,{'restoration':{'status':'pending'}})
    assert all((tmp_path/name).read_bytes()==contents for name,contents in saved.items())
    if existing!='state': assert not path.exists()


@pytest.mark.parametrize('changed', ['nonce', 'restorer_died'])
def test_final_startup_claim_rechecks_both_guard_proofs(monkeypatch, tmp_path, changed):
    path=tmp_path/'state.json'; now=u.utc_now()
    state={'guard_nonce':'current','guard_started_epoch_s':now.timestamp(),
           'guard_pids':{'restorer':10},'guards_ready':False,'restoration':{'status':'pending'}}
    u.atomic_write(path,state)
    for role,pid in [('restorer',10),('monitor',20)]:
        u.atomic_write(tmp_path/(role+'.ready'), {'role':role,'pid':pid,
            'nonce':'current','ready_utc':now.isoformat()})
    monkeypatch.setattr(u,'pid_alive',lambda pid: not (changed=='restorer_died' and pid==10))
    before=path.read_bytes()
    with pytest.raises(u.Refusal):
        u.publish_started_guard(path,'monitor',20,'stale' if changed=='nonce' else 'current',all_ready=True)
    assert path.read_bytes()==before

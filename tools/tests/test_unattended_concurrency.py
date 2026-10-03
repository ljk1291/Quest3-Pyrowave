import threading, time
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

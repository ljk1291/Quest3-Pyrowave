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
    import multiprocessing, os
    state=tmp_path/'state.json'; u.atomic_write(state,{})
    def die(path):
        with u.state_lock(path): os._exit(0)
    child=multiprocessing.Process(target=die,args=(state,)); child.start(); child.join(2); assert child.exitcode==0
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
    with __import__('pytest').raises(Exception): u.restore(state,H())
    assert u.json_read(state)['restoration']['status']=='restore_failed'

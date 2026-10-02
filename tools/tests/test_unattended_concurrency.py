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

import pytest
from tools.quest3 import unattended as u


@pytest.mark.parametrize('name,command,path,expected', [
    ('git.exe', 'git ls-files -- ComfyUI_windows_portable/outputs', '', False),
    ('git.exe', 'git show ComfyUI/main.py --port 8192', '', False),
    ('firefox.exe', 'firefox http://127.0.0.1:8192', '', False),
    ('python.exe', 'python inspect.py ComfyUI/main.py', '', False),
    ('python.exe', 'python -c "print(\'ComfyUI\')"', '', False),
    ('python.exe', 'python -m unittest tests.comfyui', '', False),
    ('python.exe', 'python -s ComfyUI/main.py --windows-standalone-build', '', True),
    ('python.exe', 'python main.py --port 8192', '', True),
    ('pythonw.exe', 'pythonw main.py', 'C:/ComfyUI/.venv/pythonw.exe', True),
    ('python.exe', 'python -m comfyui', '', True),
    ('ComfyUI.exe', 'ComfyUI.exe', '', True),
    ('python.exe', None, '', True),
])
def test_comfy_detection_checks_the_backend_entry_point(name,command,path,expected):
    assert u.is_comfy_backend_process(dict(Name=name,CommandLine=command,ExecutablePath=path)) is expected


def test_backend_inventory_failure_is_not_treated_as_idle(monkeypatch):
    class Host(u.Host):
        def _comfy_pids(self): return [{'discovery_error':'backend_process_inventory_unavailable'}]
        def _comfy_queue(self): return {'known':True,'running':0,'pending':0}
    monkeypatch.setattr(u.shutil,'which',lambda name:None)
    sample=Host().gpu_sample()
    assert sample['comfy']['known'] is False
    assert 'comfy_queue_active_or_unknown' in sample['conflicts']


@pytest.mark.parametrize('physical,status,passes',[(True,2,True),(True,5,True),
                                                 (False,2,False),(True,3,False)])
def test_ac_classified_power_requires_charging_and_pinned_physical_usb(physical,status,passes):
    class Host:
        def adb_devices(self): return ['Q3']
        def adb_run(self,serial,*args):
            assert serial=='Q3'
            if args==('shell','getprop','ro.product.model'): return 'Quest 3'
            if args==('shell','dumpsys','battery'):
                return f'level: 74\ntemperature: 330\nAC powered: true\nUSB powered: false\nstatus: {status}'
            if args==('shell','dumpsys','thermalservice'): return 'Thermal Status: 0'
            raise AssertionError('unexpected device command')
        def pinned_usb_present(self,serial): assert serial=='Q3'; return physical
        def idle_seconds(self): return 1801
        def vr_connected(self): return False
        def competing_gpu(self): return []
    failures,battery,_=u.live_preconditions({'headset_serial':'Q3'},Host())
    assert (not failures) is passes
    assert battery['charging'] is passes
    if passes: assert 'pinned physical USB' in battery['charging_evidence']


def test_usb_power_flag_cannot_override_an_explicit_discharging_status():
    assert not u.parse_battery('USB powered: true\nstatus: 3')['charging']


def activity(pid=22,percent=40):
    return u.parse_gpu_activity({'instance_count':539,'active':[
        {'Name':f'pid_{pid}_luid_0x00000000_0x0000abcd_phys_0_eng_1_engtype_3D',
         'UtilizationPercentage':percent}]})


@pytest.mark.parametrize('data',[{'instance_count':0,'active':[]},
                               {'instance_count':539,'active':None},
                               {'instance_count':539,'active':[None]},
                               {'instance_count':539,'active':[{'Name':'unknown','UtilizationPercentage':5}]}])
def test_unknown_or_malformed_activity_cannot_be_idle(data):
    with pytest.raises(u.Refusal): u.parse_gpu_activity(data)


@pytest.mark.parametrize('state,queue,expected',[
    ({'known':True,'instance_count':539,'active_pids':{}},(0,0),[]),
    (activity(),(0,0),['22, ComfyUI.exe, N/A']),
    ({'known':False,'active_pids':{}},(0,0),['gpu_engine_activity_unknown']),
    ({'known':True,'instance_count':539,'active_pids':{}},(1,0),['comfy_queue_active_or_unknown'])])
def test_resident_contexts_are_distinct_from_activity_but_comfy_remains_guarded(monkeypatch,state,queue,expected):
    class Host(u.Host):
        def _comfy_pids(self): return [{'ProcessId':22}]
        def _comfy_queue(self):
            return {'known':True,'running':queue[0],'pending':queue[1],'error':None}
        def gpu_activity(self): return state
        def run(self,*args,**kwargs):
            assert args[0]=='fake-nvidia-smi'
            return '11, explorer.exe, N/A\n22, ComfyUI.exe, N/A'
    monkeypatch.setattr(u.shutil,'which',lambda name:'fake-nvidia-smi')
    assert Host().gpu_sample()['conflicts']==expected

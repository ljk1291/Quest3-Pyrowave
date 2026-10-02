import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from tools.quest3 import unattended as u

ARM={"schema":1,"mode":"nightly","start_local":"23:00","end_local":"05:00","timezone":"Europe/Berlin","expires_local":"2026-11-01T23:59","headset_serial":"Q3","max_window_hours":6,"allow":["chart_cells"]}
class Fake(u.Host):
 def __init__(self, devices=('Q3',), model='Quest 3', idle=1801, vr=False, gpu=(), battery=None, thermal=0):
  self.devices=list(devices); self.model=model; self.idle=idle; self.vr=vr; self.gpu=list(gpu); self.battery=battery or 'level: 80\ntemperature: 350\nUSB powered: true\n'; self.thermal=thermal; self.calls=[]; self.properties={}
 def adb_devices(self): return self.devices
 def adb_run(self, serial,*args):
  self.calls.append((serial,args))
  if serial!='Q3': raise AssertionError('unpinned adb')
  if args==('shell','getprop','ro.product.model'): return self.model
  if args==('shell','dumpsys','battery'): return self.battery
  if args==('shell','dumpsys','thermalservice'): return f'Thermal Status: {self.thermal}'
  if args==('shell','getprop'): return '[debug.q3pw.test]: [1]\n[debug.oculus.refreshRate]: [90]'
  if len(args)==2 and args[0]=='shell' and args[1].startswith('setprop '):
   import shlex
   _,key,value=shlex.split(args[1]); self.properties[key]=value; return ''
  if len(args)==3 and args[:2]==('shell','getprop'): return self.properties.get(args[2],'')
  return ''
 def idle_seconds(self): return self.idle
 def vr_connected(self): return self.vr
 def competing_gpu(self): return self.gpu

def now(hour, minute=0): return datetime(2026,10,3,hour,minute,tzinfo=timezone.utc)
def test_nightly_crosses_midnight_and_expiry():
 a=dict(ARM,expires_local='2026-10-04T23:59')
 out=u.arm_window(a,now(1)); assert out['remaining_s']>45*60
 with pytest.raises(u.Refusal): u.arm_window(a,datetime(2026,10,5,1,tzinfo=timezone.utc))
def test_once_and_remaining_gate():
 a={"schema":1,"mode":"once","not_before_local":"2026-10-03T00:00","not_after_local":"2026-10-03T06:00","timezone":"UTC","expires_local":"2026-10-03T06:00","headset_serial":"Q3","max_window_hours":6,"allow":[]}
 assert u.arm_window(a,now(1))['remaining_s']
 with pytest.raises(u.Refusal): u.arm_window(a,now(5,30))
def test_missing_arm_refuses(tmp_path):
 with pytest.raises(u.Refusal): u.load_arm(tmp_path/'none.json')
@pytest.mark.parametrize('fake,reason',[ (Fake(devices=('Q3','other')),'adb_devices'),(Fake(model='Quest 2'),'not_quest'),(Fake(idle=1),'owner_not_idle'),(Fake(vr=True),'vr_or'),(Fake(gpu=('ComfyUI',)),'competing'),(Fake(battery='level: 49\ntemperature: 350\nUSB powered: true\n'),'battery'),(Fake(thermal=2),'thermal')])
def test_every_gate_fails_before_snapshot(monkeypatch,tmp_path,fake,reason):
 monkeypatch.setattr(u,'snapshot',lambda *x: (_ for _ in ()).throw(AssertionError('snapshot after bad guard')))
 r=u.check_preconditions(ARM,fake,tmp_path,now(1)); assert not r['passed']; assert any(reason in x for x in r['failures'])
def test_good_guard_snapshots_only_after_all_gates(monkeypatch,tmp_path):
 monkeypatch.setattr(u,'snapshot',lambda *x:{'ok':True})
 r=u.check_preconditions(ARM,Fake(),tmp_path,now(1)); assert r['passed'] and r['snapshot']=={'ok':True}
def test_monitor_pause_resume_and_third_pause():
 s={}; assert u.health_decision({'thermal_status':3,'battery':90,'temperature_c':30},s,0)=='pause'
 assert u.health_decision({'thermal_status':0,'battery':90,'temperature_c':39},s,899)=='paused'
 assert u.health_decision({'thermal_status':0,'battery':90,'temperature_c':40},s,900)=='resume'
 assert u.health_decision({'thermal_status':3,'battery':90,'temperature_c':30},s,1000)=='pause'
 assert u.health_decision({'thermal_status':0,'battery':90,'temperature_c':40},s,2000)=='resume'
 assert u.health_decision({'thermal_status':3,'battery':90,'temperature_c':30},s,2100)=='end'
def test_restore_order_idempotence(monkeypatch,tmp_path):
 source=tmp_path/'vd.json'; backup=tmp_path/'backup.json'; source.write_text('{"old":1}'); backup.write_text('{"old":1}')
 st={'serial':'Q3','adb':'adb','snapshot':{'headset_properties':{'all_filtered':['[debug.q3pw.x]: [1]']},'configuration_snapshots':[{'label':'vd','exists':True,'snapshot':str(backup),'source':str(source),'sha256':None}]},'restoration':{'status':'pending'}}
 path=tmp_path/'state.json'; u.atomic_write(path,st); h=Fake(); monkeypatch.setattr('tools.quest3.preflight.verify_snapshot',lambda r:[{'error':None,'current_matches':True}])
 one=u.restore(path,h); two=u.restore(path,h)
 assert one['status']=='restored' and two['status']=='restored'; assert h.calls[0][1][:3]==('shell','am','force-stop'); assert source.read_text()=='{"old":1}'

def test_dst_nightly_interval_is_bounded():
    # Europe/Berlin falls back on this date. Both repeated local 02:30 moments
    # remain inside the overnight interval and retain the arm's six-hour cap.
    a=dict(ARM,start_local='01:00',end_local='05:00',expires_local='2026-10-26T23:59',max_window_hours=6)
    value=u.arm_window(a,datetime(2026,10,25,1,30,tzinfo=timezone.utc))
    assert 0 < value['remaining_s'] <= 6*3600

def test_cli_missing_arm_refuses(monkeypatch,tmp_path):
    monkeypatch.setattr('sys.argv',['unattended.py','check','--arm',str(tmp_path/'missing.json')])
    with pytest.raises(SystemExit): u.main()


def test_restore_replays_empty_managed_property(monkeypatch, tmp_path):
    source=tmp_path/'vd.json'; backup=tmp_path/'backup.json'; source.write_text('x'); backup.write_text('x')
    state={'serial':'Q3','adb':'adb','snapshot':{'headset_properties':{'managed':{'debug.q3pw.direct_eye_copy':'','debug.oculus.refreshRate':'90'}},'configuration_snapshots':[{'label':'vd','exists':True,'snapshot':str(backup),'source':str(source)}]},'restoration':{'status':'pending'}}
    path=tmp_path/'state.json'; u.atomic_write(path,state); host=Fake()
    monkeypatch.setattr('tools.quest3.preflight.verify_snapshot',lambda r:[{'error':None,'current_matches':True}])
    assert u.restore(path,host)['status']=='restored'
    assert ('Q3',('shell',"setprop debug.q3pw.direct_eye_copy ''")) in host.calls
    assert ('Q3',('shell','setprop debug.oculus.refreshRate 90')) in host.calls

def test_guard_readiness_is_bound_to_new_nonce_and_pid(tmp_path):
    assert not u.wait_for_guard(tmp_path,'restorer','new',10,timeout_s=0)
    u.atomic_write(tmp_path/'restorer.ready', {'role':'restorer','pid':9,'nonce':'old','ready_utc':'now'})
    assert not u.wait_for_guard(tmp_path,'restorer','new',10,timeout_s=0.01)
    u.atomic_write(tmp_path/'restorer.ready', {'role':'restorer','pid':10,'nonce':'new','ready_utc':'now'})
    assert u.wait_for_guard(tmp_path,'restorer','new',10,timeout_s=0.1)


def test_status_lease_fails_closed_for_guard_staleness_or_revoke(monkeypatch, tmp_path):
    now=datetime(2026,10,3,1,tzinfo=timezone.utc)
    arm=tmp_path/'arm.json'; arm.write_text(json.dumps(dict(ARM, expires_local='2026-10-04T23:59')))
    state={'window_id':'window','deadline_epoch_s':now.timestamp()+3600,'guards_ready':True,
           'guard_pids':{'restorer':11,'monitor':12},'arm_sha256':u.arm_digest(json.loads(arm.read_text())),'guard_nonce':'n','monitor':{'last_sample_epoch_s':now.timestamp()},
           'restoration':{'status':'pending'}}
    u.atomic_write(tmp_path/'state.json',state)
    for name in ('restorer.ready','monitor.ready'): u.atomic_write(tmp_path/name, {'pid':11 if name.startswith('restorer') else 12,'role':'restorer' if name.startswith('restorer') else 'monitor','nonce':'n','ready_utc':'now'})
    monkeypatch.setattr(u,'pid_alive',lambda pid: True)
    status=u.status_payload(tmp_path,arm,now)
    assert status['lease']['active']
    state['monitor']['last_sample_epoch_s']=now.timestamp()-1000; u.atomic_write(tmp_path/'state.json',state)
    assert 'monitor_stale' in u.status_payload(tmp_path,arm,now)['lease']['blockers']
    arm.unlink()
    assert 'arm_inactive' in u.status_payload(tmp_path,arm,now)['lease']['blockers']

def test_start_orders_guards_before_ready_state(monkeypatch, tmp_path):
    arm_path=tmp_path/'arm.json'; arm_path.write_text('{}')
    arm={'headset_serial':'Q3'}; deadline=datetime.now(timezone.utc)+timedelta(hours=1)
    snapshot={'headset_properties':{'managed':{},'all_filtered':[]},'configuration_snapshots':[], 'preflight':{}}
    u.atomic_write(tmp_path/'check.json',{'passed':True,'snapshot':snapshot,'serial':'Q3','arm_sha256':u.arm_digest(arm),
                                          'checked_utc':u.utc_now().isoformat(),'window':{'deadline_utc':deadline.isoformat()}})
    order=[]
    class Process:
        def __init__(self,pid): self.pid=pid
    def spawn(path, monitor):
        role='monitor' if monitor else 'restorer'; order.append(role); state=u.json_read(path)
        u.atomic_write(tmp_path/(role+'.ready'), {'pid':20 if monitor else 10,'role':role,'nonce':state['guard_nonce'],'ready_utc':'now'})
        return Process(20 if monitor else 10)
    monkeypatch.setattr(u,'spawn_worker',spawn)
    monkeypatch.setattr(u,'load_arm',lambda path: (arm, {'deadline':deadline}))
    monkeypatch.setattr(u,'pid_alive',lambda pid: True)
    monkeypatch.setattr('tools.quest3.preflight.verify_snapshot',lambda records: [])
    monkeypatch.setattr(u,'live_preconditions',lambda arm,host: ([],{},0))
    monkeypatch.setattr('sys.argv',['unattended.py','start','--arm',str(arm_path),'--window',str(tmp_path)])
    u.main()
    state=u.json_read(tmp_path/'state.json')
    assert order==['restorer','monitor'] and state['guards_ready']
    assert state['guard_pids']=={'restorer':10,'monitor':20}

def test_start_replaces_stale_ready_marker_with_nonce_bound_record(monkeypatch, tmp_path):
    arm_path=tmp_path/'arm.json'; arm_path.write_text('{}')
    arm={'headset_serial':'Q3'}; deadline=datetime.now(timezone.utc)+timedelta(hours=1)
    snapshot={'headset_properties':{'managed':{},'all_filtered':[]},'configuration_snapshots':[], 'preflight':{}}
    u.atomic_write(tmp_path/'check.json',{'passed':True,'snapshot':snapshot,'serial':'Q3','arm_sha256':u.arm_digest(arm),
                                          'checked_utc':u.utc_now().isoformat(),'window':{'deadline_utc':deadline.isoformat()}})
    u.atomic_write(tmp_path/'restorer.ready', {'pid':999,'role':'restorer','nonce':'stale','ready_utc':'old'})
    observed=[]
    class Process:
        def __init__(self,pid): self.pid=pid
    def spawn(path, monitor):
        role='monitor' if monitor else 'restorer'; observed.append((role,(tmp_path/'restorer.ready').exists()))
        state=u.json_read(path); u.atomic_write(tmp_path/(role+'.ready'), {'pid':20 if monitor else 10,'role':role,'nonce':state['guard_nonce'],'ready_utc':'new'})
        return Process(20 if monitor else 10)
    monkeypatch.setattr(u,'load_arm',lambda path: (arm, {'deadline':deadline}))
    monkeypatch.setattr('tools.quest3.preflight.verify_snapshot',lambda records: [])
    monkeypatch.setattr(u,'live_preconditions',lambda arm,host: ([],{},0))
    monkeypatch.setattr(u,'spawn_worker',spawn)
    monkeypatch.setattr(u,'pid_alive',lambda pid: True)
    monkeypatch.setattr('sys.argv',['unattended.py','start','--arm',str(arm_path),'--window',str(tmp_path)])
    u.main()
    ready=u.json_read(tmp_path/'restorer.ready')
    assert observed[0] == ('restorer',False) and ready['nonce'] != 'stale'

def test_start_refuses_before_monitor_when_restorer_is_not_ready(monkeypatch, tmp_path):
    arm_path=tmp_path/'arm.json'; arm_path.write_text('{}')
    arm={'headset_serial':'Q3'}; deadline=datetime.now(timezone.utc)+timedelta(hours=1)
    snapshot={'headset_properties':{'managed':{},'all_filtered':[]},'configuration_snapshots':[], 'preflight':{}}
    u.atomic_write(tmp_path/'check.json',{'passed':True,'snapshot':snapshot,'serial':'Q3','arm_sha256':u.arm_digest(arm),
                                          'checked_utc':u.utc_now().isoformat(),'window':{'deadline_utc':deadline.isoformat()}})
    calls=[]
    monkeypatch.setattr(u,'spawn_worker',lambda path,monitor: calls.append(monitor) or type('P',(),{'pid':1})())
    monkeypatch.setattr(u,'wait_for_guard',lambda *args: False)
    monkeypatch.setattr(u,'load_arm',lambda path: (arm, {'deadline':deadline}))
    monkeypatch.setattr('tools.quest3.preflight.verify_snapshot',lambda records: [])
    monkeypatch.setattr(u,'live_preconditions',lambda arm,host: ([],{},0))
    monkeypatch.setattr('sys.argv',['unattended.py','start','--arm',str(arm_path),'--window',str(tmp_path)])
    with pytest.raises(SystemExit): u.main()
    assert calls==[False] and (tmp_path/'stop').is_file()

def test_status_and_restore_are_available_after_arm_revocation(monkeypatch, tmp_path):
    u.atomic_write(tmp_path/'state.json',{'deadline_epoch_s':0,'restoration':{'status':'pending'}})
    monkeypatch.setattr('sys.argv',['unattended.py','status','--window',str(tmp_path),'--arm',str(tmp_path/'missing-arm.json')])
    u.main()


def test_status_checks_required_allow(monkeypatch, tmp_path):
    now=datetime(2026,10,3,1,tzinfo=timezone.utc)
    arm=tmp_path/'arm.json'; arm.write_text(json.dumps(dict(ARM, expires_local='2026-10-04T23:59', allow=['chart_cells'])))
    state={'deadline_epoch_s':now.timestamp()+3600,'guards_ready':True,'guard_pids':{'restorer':1,'monitor':2},'arm_sha256':u.arm_digest(json.loads(arm.read_text())),'guard_nonce':'n',
           'monitor':{'last_sample_epoch_s':now.timestamp()},'restoration':{'status':'pending'}}
    u.atomic_write(tmp_path/'state.json',state)
    for name in ('restorer.ready','monitor.ready'):
        u.atomic_write(tmp_path/name, {'pid':1 if name.startswith('restorer') else 2,'role':'restorer' if name.startswith('restorer') else 'monitor','nonce':'n','ready_utc':'now'})
    monkeypatch.setattr(u,'pid_alive',lambda pid: True)
    assert u.status_payload(tmp_path,arm,now,require_allow='chart_cells')['lease']['active']
    assert 'action_not_allowed' in u.status_payload(tmp_path,arm,now,require_allow='frame_bank_pc')['lease']['blockers']


def test_berlin_fallback_distinguishes_repeated_fall_hour():
    zone=u._BerlinFallback()
    first=datetime(2026,10,25,0,30,tzinfo=timezone.utc).astimezone(zone)
    second=datetime(2026,10,25,1,30,tzinfo=timezone.utc).astimezone(zone)
    assert first.fold == 0 and second.fold == 1
    assert first.utcoffset() == timedelta(hours=2)
    assert second.utcoffset() == timedelta(hours=1)


def test_usb_charging_is_required_not_ac_or_status():
    assert not u.parse_battery('level: 80\ntemperature: 350\nAC powered: true\nstatus: 2')['charging']
    assert u.parse_battery('level: 80\ntemperature: 350\nUSB powered: true')['charging']

def test_restore_never_copies_virtual_desktop_files(monkeypatch, tmp_path):
    source=tmp_path/'vd.json'; backup=tmp_path/'backup.json'; source.write_text('changed'); backup.write_text('original')
    state={'serial':'Q3','adb':'adb','snapshot':{'headset_properties':{'managed':{}},'configuration_snapshots':[{'label':'virtual_desktop_streamer','exists':True,'snapshot':str(backup),'source':str(source),'sha256':'x'}]},'restoration':{'status':'pending'}}
    path=tmp_path/'state.json'; u.atomic_write(path,state); host=Fake()
    monkeypatch.setattr('tools.quest3.preflight.verify_snapshot',lambda records:[{'label':'virtual_desktop_streamer','error':None,'current_matches':False}])
    result=u.restore(path,host)
    assert result['status']=='restore_failed' and not result['vd_hashes_match']
    assert source.read_text()=='changed' and 'vd_verify_only:virtual_desktop_streamer' in result['steps']

def test_real_experiment_property_set_is_used():
    names=u.managed_properties()
    assert 'debug.q3pw.fragment_min_usage' in names
    assert 'debug.q3pw.optimal_ahb_usage' in names
    assert 'debug.q3pw.direct_flip_y' in names


def test_ownership_record_requires_exact_identity_and_nonce(tmp_path):
    class OwnedHost:
        def process_identity(self,pid): return {'pid':pid,'path':'C:/q3pw/ALVR Dashboard.exe','started_epoch_s':10.0}
    state={'guards_ready':True,'guard_nonce':'n','restoration':{'status':'pending'}}
    path=tmp_path/'state.json'; u.atomic_write(path,state)
    record={'role':'dashboard','pid':1,'path':'C:/q3pw/ALVR Dashboard.exe','started_epoch_s':10.0,'nonce':'n'}
    assert u.record_owned_runtime(path,record,OwnedHost())['role']=='dashboard'
    bad=dict(record,pid=2)
    with pytest.raises(u.Refusal): u.record_owned_runtime(path,bad,OwnedHost())

def test_restore_does_not_stop_unproved_owned_runtime(monkeypatch,tmp_path):
    class OwnedHost(Fake):
        def stop_owned_runtime(self,record): raise u.Refusal('ownership changed')
    state={'serial':'Q3','snapshot':{'headset_properties':{'managed':{}},'configuration_snapshots':[]},
           'owned_runtime':[{'role':'dashboard','pid':1,'path':'C:/q3pw/ALVR Dashboard.exe','started_epoch_s':1,'nonce':'n'}],
           'restoration':{'status':'pending'}}
    path=tmp_path/'state.json'; u.atomic_write(path,state); host=OwnedHost()
    monkeypatch.setattr('tools.quest3.preflight.verify_snapshot',lambda records: [])
    result=u.restore(path,host)
    assert result['status']=='restore_failed' and result['owned_runtime_stopped'] is False

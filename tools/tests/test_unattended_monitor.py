import hashlib, time
from datetime import datetime, timezone, timedelta
import pytest
from tools.quest3 import unattended as u


def test_guard_record_requires_real_timestamp_bound_to_start():
    now=datetime(2026,10,3,1,tzinfo=timezone.utc)
    good={'pid':1,'role':'monitor','nonce':'n','ready_utc':now.isoformat()}
    assert u.guard_record_valid(good,'monitor',1,'n',now.timestamp()-1,now)
    for value in ('now',now.replace(tzinfo=None).isoformat(),
                  (now-timedelta(minutes=1)).isoformat(),(now+timedelta(minutes=1)).isoformat()):
        assert not u.guard_record_valid(dict(good,ready_utc=value),'monitor',1,'n',now.timestamp()-1,now)


def test_configuration_drift_allows_only_recorded_exact_values(tmp_path):
    path=tmp_path/'alvr.json'; backup=tmp_path/'backup.json'
    original={'session_settings':{'rate':500,'size':3072},'clients':{}}
    u.atomic_write(path,original); backup.write_bytes(path.read_bytes())
    state={'snapshot':{'configuration_snapshots':[{'label':'alvr_session','source':str(path),
              'snapshot':str(backup),'sha256':hashlib.sha256(backup.read_bytes()).hexdigest()}]},
           'changes':[{'kind':'alvr','key':'session_settings.rate','expected_after':600}]}
    assert u.configuration_drift(state)==[]
    u.atomic_write(path,{'session_settings':{'rate':600,'size':3072},'clients':{}})
    assert u.configuration_drift(state)==[]
    u.atomic_write(path,{'session_settings':{'rate':600,'size':2080},'clients':{}})
    assert u.configuration_drift(state)==['settings_drift:alvr_session']


def test_virtual_desktop_drift_is_never_exempted_by_an_alvr_change(tmp_path):
    path=tmp_path/'vd.json'; backup=tmp_path/'backup.json'; path.write_text('{}'); backup.write_text('{}')
    state={'snapshot':{'configuration_snapshots':[{'label':'virtual_desktop_streamer','source':str(path),
           'snapshot':str(backup),'sha256':hashlib.sha256(b'{}').hexdigest()}]},
           'changes':[{'kind':'alvr','key':'rate','expected_after':600}]}
    path.write_text('{"owner":true}')
    assert u.configuration_drift(state)==['settings_drift:virtual_desktop_streamer']


def test_monitor_device_failure_revokes_and_releases_keep_awake(monkeypatch,tmp_path):
    path=tmp_path/'state.json'
    u.atomic_write(path,{'serial':'Q3','guard_nonce':'n','deadline_epoch_s':time.time()+3600,
                        'snapshot':{'configuration_snapshots':[]}})
    awake=[]
    class Host:
        def keep_awake(self,value): awake.append(value)
        def idle_seconds(self): return 1801
        def vr_connected(self): return False
        def adb_run(self,*args): raise RuntimeError('USB telemetry lost')
    monkeypatch.setattr(u,'Host',lambda *args:Host())
    with pytest.raises(RuntimeError,match='USB telemetry lost'): u.worker(path,monitor=True)
    assert awake==[True,False] and (tmp_path/'stop').exists()
    assert u.json_read(tmp_path/'worker-error-monitor.json')['error']=='RuntimeError'


@pytest.mark.parametrize('idle,vr,reason',[(1,False,'owner_activity'),(1801,True,'unclaimed_vr_or_vd_session')])
def test_monitor_stops_on_owner_or_unclaimed_session(monkeypatch,tmp_path,idle,vr,reason):
    path=tmp_path/'state.json'
    u.atomic_write(path,{'serial':'Q3','guard_nonce':'n','deadline_epoch_s':time.time()+3600,
                        'snapshot':{'configuration_snapshots':[]}})
    class Host:
        def keep_awake(self,value): pass
        def idle_seconds(self): return idle
        def vr_connected(self): return vr
        def adb_run(self,*args): raise AssertionError('no device sampling after owner stop')
    monkeypatch.setattr(u,'Host',lambda *args:Host())
    u.worker(path,monitor=True)
    assert reason in u.json_read(tmp_path/'monitor.json')['stop_reasons']
    assert (tmp_path/'stop').exists()


def test_restore_does_not_overwrite_unclaimed_alvr_file(monkeypatch,tmp_path):
    path=tmp_path/'session.json'; backup=tmp_path/'backup.json'
    path.write_text('{"owner":true}'); backup.write_text('{}')
    state=tmp_path/'state.json'
    u.atomic_write(state,{'serial':'Q3','restoration':{'status':'pending'},
                'snapshot':{'headset_properties':{'managed':{}},'configuration_snapshots':[
                {'label':'alvr_session','source':str(path),'snapshot':str(backup),'exists':True,
                 'sha256':hashlib.sha256(b'{}').hexdigest()}]}})
    class Host:
        def adb_run(self,*args): return ''
        def vr_connected(self): return False
    result=u.restore(state,Host())
    assert path.read_text()=='{"owner":true}'
    assert result['status']=='restore_failed' and not result['alvr_restored']

import json
import threading
import time
import pytest
from tools.quest3 import unattended as u, preflight


class Host:
    def adb_run(self, *args): return ''
    def vr_connected(self): return False
    def stop_owned_runtime(self, record): return True


def setup_file(tmp_path, label='alvr_session', kind='alvr'):
    source=tmp_path/'settings.json'; backup=tmp_path/'saved.json'
    original=b'{ "video": { "fps": 72, "bitrate": 200 }, "owner": "preserve" }\n'
    source.write_bytes(original); backup.write_bytes(original)
    record={'label':label,'source':str(source),'snapshot':str(backup),
            'exists':True,'sha256':preflight.sha256(backup),'error':None}
    state={'serial':'fake','owned_runtime':[{'role':'dashboard'}],
           'snapshot':{'headset_properties':{'managed':{}},'configuration_snapshots':[record]},
           'changes':[{'kind':kind,'key':'video.fps','before_present':True,'before_value':72,'expected_after':90},
                      {'kind':kind,'key':'video.bitrate','before_present':True,'before_value':200,'expected_after':500}],
           'restoration':{'status':'pending'}}
    return source,backup,record,state


@pytest.mark.parametrize('label,kind',[('alvr_session','alvr'),('steamvr_settings','steamvr')])
def test_cold_restore_needs_no_live_api_and_restores_exact_bytes(monkeypatch,tmp_path,label,kind):
    from tools.quest3 import control
    source,backup,record,state=setup_file(tmp_path,label,kind)
    u.atomic_write(source,{'video':{'fps':90,'bitrate':500},'owner':'preserve'})
    def unavailable(*args): raise AssertionError('dashboard was already stopped')
    monkeypatch.setattr(control,'session',unavailable)
    monkeypatch.setattr(control,'set_values',unavailable)
    path=tmp_path/'state.json'; u.atomic_write(path,state)
    result=u.restore(path,Host())
    assert result['status']=='restored'
    assert source.read_bytes()==backup.read_bytes()
    assert u.json_read(tmp_path/'restoration.json')==result


@pytest.mark.parametrize('changed',[
    {'video':{'fps':90,'bitrate':500},'owner':'new owner value'},
    {'video':{'fps':120,'bitrate':500},'owner':'preserve'}])
def test_unrecorded_steamvr_drift_is_never_overwritten(tmp_path,changed):
    source,backup,record,state=setup_file(tmp_path,'steamvr_settings','steamvr')
    u.atomic_write(source,changed); before=source.read_bytes()
    path=tmp_path/'state.json'; u.atomic_write(path,state)
    result=u.restore(path,Host())
    assert result['status']=='restore_failed' and not result['steamvr_restored']
    assert source.read_bytes()==before


def test_partial_owned_setup_can_restore(tmp_path):
    source,backup,record,state=setup_file(tmp_path)
    u.atomic_write(source,{'video':{'fps':90,'bitrate':200},'owner':'preserve'})
    assert u.restore_configuration_bytes(state,record,owned_ok=True)=='exact_saved_bytes_restored'
    assert source.read_bytes()==backup.read_bytes()


def test_unclaimed_runtime_cannot_authorize_cold_restore(tmp_path):
    source,backup,record,state=setup_file(tmp_path)
    state['owned_runtime']=[]
    u.atomic_write(source,{'video':{'fps':90,'bitrate':500},'owner':'preserve'})
    before=source.read_bytes()
    with pytest.raises(u.Refusal,match='unclaimed'): u.restore_configuration_bytes(state,record,owned_ok=True)
    assert source.read_bytes()==before


def test_corrupt_backup_cannot_replace_configuration(tmp_path):
    source,backup,record,state=setup_file(tmp_path)
    backup.write_text('{}'); before=source.read_bytes()
    with pytest.raises(u.Refusal,match='backup invalid'): u.restore_configuration_bytes(state,record,owned_ok=True)
    assert source.read_bytes()==before


def test_corrupt_vd_backup_cannot_report_successful_restoration(tmp_path):
    source,backup,record,state=setup_file(tmp_path,'virtual_desktop_streamer','unused')
    state['changes']=[]; backup.write_text('{}'); before=source.read_bytes()
    path=tmp_path/'state.json'; u.atomic_write(path,state)
    result=u.restore(path,Host())
    assert result['status']=='restore_failed' and not result['vd_hashes_match']
    assert source.read_bytes()==before


def test_configuration_race_is_detected_before_replace(monkeypatch,tmp_path):
    from pathlib import Path
    source,backup,record,state=setup_file(tmp_path)
    u.atomic_write(source,{'video':{'fps':90,'bitrate':500},'owner':'preserve'})
    real_read=Path.read_bytes; reads=0
    def read(path):
        nonlocal reads
        if path==source:
            reads+=1
            if reads==2: source.write_text('{"owner":"changed during restore"}')
        return real_read(path)
    monkeypatch.setattr(Path,'read_bytes',read)
    with pytest.raises(u.Refusal,match='changed during'): u.restore_configuration_bytes(state,record,owned_ok=True)
    assert json.loads(source.read_text())['owner']=='changed during restore'
    assert not list(tmp_path.glob('settings.json.q3pw-*'))


def test_independent_restorer_retries_after_actual_mutex_timeout(monkeypatch,tmp_path):
    source,backup,record,state=setup_file(tmp_path)
    path=tmp_path/'state.json'; u.atomic_write(path,state)
    monkeypatch.setattr(u,'RESTORE_LOCK_SECONDS',.05)
    entered=threading.Event(); release=threading.Event(); errors=[]; result=[]
    def writer():
        with u.state_lock(path): entered.set(); release.wait(3)
    def restorer():
        try: result.append(u.restore_with_retry(path,Host()))
        except Exception as exc: errors.append(exc)
    held=threading.Thread(target=writer); worker=threading.Thread(target=restorer)
    held.start(); assert entered.wait(1); worker.start()
    deadline=time.monotonic()+1
    try:
        while not list(tmp_path.glob('restore-attempt-*.json')) and time.monotonic()<deadline: time.sleep(.005)
        assert list(tmp_path.glob('restore-attempt-*.json'))
        assert (tmp_path/'stop').exists() and not (tmp_path/'restoration.json').exists()
    finally:
        release.set(); held.join(3); worker.join(3)
    assert not held.is_alive() and not worker.is_alive() and not errors
    assert result[0]['status']=='restored'


def test_retry_exhaustion_is_finite_and_does_not_publish_competing_final(monkeypatch,tmp_path):
    source,backup,record,state=setup_file(tmp_path)
    path=tmp_path/'state.json'; u.atomic_write(path,state); before=path.read_bytes()
    monkeypatch.setattr(u,'RESTORE_LOCK_SECONDS',.02)
    entered=threading.Event(); release=threading.Event()
    def writer():
        with u.state_lock(path): entered.set(); release.wait(3)
    held=threading.Thread(target=writer); held.start(); assert entered.wait(1)
    try:
        with pytest.raises(u.Refusal,match='state lock timeout'): u.restore_with_retry(path,Host())
        assert len(list(tmp_path.glob('restore-attempt-*.json')))==u.RESTORE_LOCK_ATTEMPTS
        assert path.read_bytes()==before and not (tmp_path/'restoration.json').exists()
    finally: release.set(); held.join(3)


@pytest.mark.parametrize('allowed',[['frame_bank_pc'],['install_matching_pair'],[]])
def test_pc_or_install_only_arm_cannot_mutate_settings(monkeypatch,tmp_path,allowed):
    source,backup,record,state=setup_file(tmp_path)
    path=tmp_path/'state.json'; u.atomic_write(path,state); before=path.read_bytes()
    monkeypatch.setattr(u,'status_payload',lambda *a,**k:{'lease':{'active':True},'arm':{'allowed_actions':allowed}})
    with pytest.raises(u.Refusal,match='does not allow'): u.record_change(path,'alvr','video.fps',True,72,90)
    assert path.read_bytes()==before


@pytest.mark.parametrize('key',['debug.xrwired.perf_level','debug.oculus.forceDisplayScaling','owner.property'])
def test_legacy_or_unknown_properties_cannot_be_new_mutations(tmp_path,key):
    with pytest.raises(u.Refusal,match='property is not authorized'):
        u.record_change(tmp_path/'state.json','headset_property',key,False,None,'1')


def test_openxr_manifest_drift_is_detected_without_changing_the_registration(monkeypatch,tmp_path):
    source,backup,record,state=setup_file(tmp_path)
    manifest=tmp_path/'runtime.json'; manifest.write_text('{"runtime":"owner"}')
    state['snapshot']['preflight']={'active_openxr_runtime':{'value':str(manifest)},
        'active_openxr_runtime_manifest':{'path':str(manifest),'sha256':preflight.sha256(manifest)}}
    monkeypatch.setattr(preflight,'registry_value',lambda *a,**k:{'value':str(manifest),'error':None})
    assert u.configuration_drift(state)==[]
    manifest.write_text('{"runtime":"changed"}')
    assert u.configuration_drift(state)==['openxr_manifest_drift']
    path=tmp_path/'state.json'; u.atomic_write(path,state)
    result=u.restore(path,Host())
    assert result['status']=='restore_failed' and not result['openxr_runtime_restored']
    assert manifest.read_text()=='{"runtime":"changed"}'

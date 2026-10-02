"""Fail-closed supervisor for owner-armed Quest 3 unattended windows.

No hardware action is taken by importing this module. The CLI's ``arm`` command is
an owner-only convenience: it requires an explicit acknowledgement and is never
called by automation. All device commands include the serial stored in the arm.
"""
from __future__ import annotations
import argparse, ctypes, hashlib, json, os, re, shlex, shutil, subprocess, sys, time, uuid, urllib.request
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'results' / 'local' / 'unattended'
ARM = PRIVATE / 'arm.json'
MIN_REMAINING = 45 * 60
MAX_HOURS = 6
POLL_SECONDS = 30
PAUSE_STATUS = 3  # Android THERMAL_STATUS_SEVERE
def managed_properties():
    # Single source of truth for real experiment keys. These are the only
    # properties the harness may subsequently change and therefore restore.
    from .bench import EXPERIMENT_PROPERTIES
    return tuple(dict.fromkeys((*EXPERIMENT_PROPERTIES, 'debug.q3pw.direct_flip_y',
                                'debug.oculus.guardian_pause')))
GUARD_READY_SECONDS = 5
CHECK_FRESH_SECONDS = 5 * 60

class Refusal(RuntimeError): pass

class _BerlinFallback(tzinfo):
    """EU DST fallback for the owner-approved Europe/Berlin Windows host."""
    @staticmethod
    def _last_sunday(year, month):
        last = datetime(year, month + 1, 1) - timedelta(days=1) if month < 12 else datetime(year, 12, 31)
        return last.day - (last.weekday() + 1) % 7
    def _summer_local(self, naive):
        start=datetime(naive.year,3,self._last_sunday(naive.year,3),2)
        end=datetime(naive.year,10,self._last_sunday(naive.year,10),3)
        return start <= naive < end
    def utcoffset(self, dt):
        if dt is None: return timedelta(hours=1)
        naive=dt.replace(tzinfo=None)
        # 02:00–02:59 on the fall-back date occurs twice. ``fold`` selects
        # the second, CET occurrence so expiry and deadline arithmetic remain
        # monotonic even without the Windows IANA time-zone database.
        fall=datetime(naive.year,10,self._last_sunday(naive.year,10),2)
        if fall <= naive < fall + timedelta(hours=1):
            return timedelta(hours=1 if dt.fold else 2)
        return timedelta(hours=2 if self._summer_local(naive) else 1)
    def dst(self, dt): return self.utcoffset(dt)-timedelta(hours=1)
    def tzname(self, dt): return 'CEST' if self.dst(dt) else 'CET'
    def fromutc(self, dt):
        utc=dt.replace(tzinfo=None)
        start=datetime(utc.year,3,self._last_sunday(utc.year,3),1)
        end=datetime(utc.year,10,self._last_sunday(utc.year,10),1)
        if start <= utc < end:
            return (utc + timedelta(hours=2)).replace(tzinfo=self,fold=0)
        fold=1 if end <= utc < end+timedelta(hours=1) else 0
        return (utc + timedelta(hours=1)).replace(tzinfo=self,fold=fold)

def timezone_for(name):
    if name == 'UTC': return timezone.utc
    try: return ZoneInfo(name)
    except Exception:
        if name == 'Europe/Berlin': return _BerlinFallback()
        raise Refusal('timezone data unavailable for '+str(name))

def utc_now(): return datetime.now(timezone.utc)
def json_read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def arm_digest(arm): return hashlib.sha256(json.dumps(arm,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def atomic_write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding='utf-8')
    temp.replace(path)

def local_dt(value, zone):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None: return dt.astimezone(zone)
    return dt.replace(tzinfo=zone)

def parse_clock(value):
    h, m = map(int, value.split(':'))
    if not 0 <= h <= 23 or not 0 <= m <= 59: raise ValueError('invalid local clock')
    return h, m

def _night_interval(now, arm):
    zone = timezone_for(arm['timezone']); here = now.astimezone(zone)
    sh, sm = parse_clock(arm['start_local']); eh, em = parse_clock(arm['end_local'])
    start = here.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = here.replace(hour=eh, minute=em, second=0, microsecond=0)
    if (eh, em) <= (sh, sm):
        if here < end: start -= timedelta(days=1)
        else: end += timedelta(days=1)
    return start, end

def validate_arm_definition(arm):
    """Validate an owner file without requiring that its future window is active."""
    if arm.get('schema') != 1 or arm.get('mode') not in {'once', 'nightly'}:
        raise Refusal('unsupported arm schema or mode')
    if not isinstance(arm.get('headset_serial'), str) or not arm['headset_serial']:
        raise Refusal('missing headset serial')
    if not isinstance(arm.get('allow'), list) or not all(isinstance(x, str) for x in arm['allow']):
        raise Refusal('invalid allow list')
    try:
        zone=timezone_for(arm['timezone']); max_hours=float(arm['max_window_hours'])
        expires=local_dt(arm['expires_local'], zone)
        if arm['mode']=='nightly':
            sh,sm=parse_clock(arm['start_local']); eh,em=parse_clock(arm['end_local'])
            start=datetime(2026,1,1,sh,sm,tzinfo=zone); end=datetime(2026,1,1,eh,em,tzinfo=zone)
            if end <= start: end += timedelta(days=1)
        else:
            start=local_dt(arm['not_before_local'], zone); end=local_dt(arm['not_after_local'], zone)
    except (KeyError, ValueError, TypeError) as exc:
        raise Refusal('invalid arm time fields') from exc
    if not 0 < max_hours <= MAX_HOURS or end <= start or end-start > timedelta(hours=max_hours):
        raise Refusal('window duration invalid')
    if expires <= start: raise Refusal('arm expires before window')
def arm_window(arm, now=None, require_remaining=True):
    now = now or utc_now()
    validate_arm_definition(arm)
    if arm.get('mode') not in {'once','nightly'}: raise Refusal('invalid arm mode')
    if not isinstance(arm.get('headset_serial'), str) or not arm['headset_serial']: raise Refusal('missing headset serial')
    if not isinstance(arm.get('allow'), list) or not all(isinstance(x,str) for x in arm['allow']): raise Refusal('invalid allow list')
    try:
        zone=timezone_for(arm['timezone']); expires=local_dt(arm['expires_local'],zone)
        max_hours=float(arm.get('max_window_hours', 0))
    except (KeyError, ValueError, TypeError) as exc: raise Refusal('invalid arm time fields') from exc
    if not 0 < max_hours <= MAX_HOURS: raise Refusal('max window exceeds six hours')
    if arm['mode']=='nightly':
        try: start,end=_night_interval(now,arm)
        except (KeyError,ValueError) as exc: raise Refusal('invalid nightly window') from exc
    else:
        try: start=local_dt(arm['not_before_local'],zone); end=local_dt(arm['not_after_local'],zone)
        except (KeyError,ValueError) as exc: raise Refusal('invalid once window') from exc
    if end <= start or end-start > timedelta(hours=max_hours): raise Refusal('window duration invalid')
    deadline=min(end,expires)
    if now.astimezone(zone) < start or now.astimezone(zone) >= deadline: raise Refusal('arm is not active now')
    remaining=(deadline-now.astimezone(zone)).total_seconds()
    if require_remaining and remaining < MIN_REMAINING: raise Refusal('less than 45 minutes remain')
    return {'start':start.astimezone(timezone.utc), 'deadline':deadline.astimezone(timezone.utc), 'remaining_s':remaining, 'zone':str(zone)}

def load_arm(path=ARM, now=None):
    if not Path(path).is_file(): raise Refusal('arm file missing')
    return json_read(path), arm_window(json_read(path),now)

class Host:
    """Small system boundary; tests use a deterministic fake."""
    def __init__(self, adb='adb'): self.adb=adb
    def run(self, *args, timeout=20):
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if p.returncode: raise Refusal((p.stderr or p.stdout or 'command failed').strip())
        return p.stdout.strip()
    def adb_run(self, serial, *args): return self.run(self.adb,'-s',serial,*args)
    def adb_devices(self):
        lines=self.run(self.adb,'devices').splitlines()[1:]
        # Offline/unauthorized devices still invalidate the exclusive-device gate.
        return [line.split('\t',1)[0] for line in lines if '\t' in line and line.strip()]
    def idle_seconds(self):
        if os.name!='nt': return 0
        class LASTINPUTINFO(ctypes.Structure): _fields_=[('cbSize',ctypes.c_uint),('dwTime',ctypes.c_uint)]
        info=LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO)); ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
        return ((ctypes.windll.kernel32.GetTickCount64() - info.dwTime) & 0xffffffff) / 1000
    def _tasklist(self):
        return self.run('tasklist','/FO','CSV','/NH',timeout=10).lower() if os.name=='nt' else ''
    def _comfy_queue(self):
        url=os.environ.get('Q3PW_COMFY_URL','http://127.0.0.1:8192')+'/queue'
        try:
            with urllib.request.urlopen(url,timeout=3) as response:
                data=json.loads(response.read().decode('utf-8'))
            running=data.get('queue_running',[]); pending=data.get('queue_pending',[])
            return {'endpoint':url,'known':True,'running':len(running),'pending':len(pending),'error':None}
        except Exception as exc: return {'endpoint':url,'known':False,'running':None,'pending':None,'error':str(exc)}
    def gpu_sample(self):
        """Record compute contention without treating every Python/service process as GPU work."""
        out=self._tasklist(); comfy_running='comfyui' in out
        comfy=self._comfy_queue() if comfy_running else {'known':True,'running':0,'pending':0,'error':None}
        conflicts=[]
        if comfy_running and (not comfy['known'] or comfy['running'] or comfy['pending']): conflicts.append('comfy_queue_active_or_unknown')
        apps=[]; executable=shutil.which('nvidia-smi') or shutil.which('nvidia-smi.exe')
        if executable:
            try:
                rows=self.run(executable,'--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader,nounits',timeout=5)
                apps=[line.strip() for line in rows.splitlines() if line.strip() and 'No running processes' not in line]
                # A live Comfy process is allowed only when its local queue reports idle.
                conflicts.extend(row for row in apps if 'comfy' not in row.lower())
            except Refusal as exc: apps=['nvidia-smi-error:'+str(exc)]; conflicts.append('gpu_compute_status_unknown')
        else: conflicts.append('gpu_compute_status_unknown')
        sample={'at_utc':utc_now().isoformat(),'comfy':comfy,'nvidia_compute_apps':apps,'conflicts':conflicts}
        self.last_gpu_sample=sample; return sample
    def competing_gpu(self): return self.gpu_sample()['conflicts']
    def _vd_log_state(self):
        candidates=[Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData'))/'Virtual Desktop/Streamer.log',
                    Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'Virtual Desktop/Streamer.log']
        lines=[]
        for path in candidates:
            try: lines.extend(path.read_text(encoding='utf-8',errors='replace')[-65536:].splitlines())
            except OSError: pass
        for line in reversed(lines):
            low=line.lower()
            if 'disconnected' in low or 'streaming stopped' in low: return False
            if 'connected' in low or 'streaming started' in low: return True
        return None
    def vr_connected(self):
        if os.name!='nt': return False
        out=self._tasklist()
        if any(x in out for x in ('vrserver.exe','vrcompositor.exe','vrmonitor.exe','steamvr.exe')): return True
        alvr='alvr dashboard.exe' in out or 'alvr_server.exe' in out
        if alvr:
            try:
                from .control import session as alvr_session
                clients=alvr_session().get('client_connections',{})
                return bool(clients)
            except Exception:
                # Dashboard exists but its actual session state cannot be read.
                return True
        if 'virtualdesktop.streamer.exe' in out:
            state=self._vd_log_state()
            # A resident streamer is acceptable only with a recent, explicit
            # disconnected record; unknown is fail-closed.
            return state is not False
        return False
    def keep_awake(self, active):
        if os.name=='nt':
            flags=0x80000000 | (0x00000001 if active else 0)
            ctypes.windll.kernel32.SetThreadExecutionState(flags)

def parse_battery(text):
    data={}
    for line in text.splitlines():
        if ':' in line:
            k,v=(x.strip() for x in line.split(':',1)); data[k.lower()]=v
    def number(k):
        try:return float(data[k])
        except (KeyError,ValueError):return None
    temperature=number('temperature')
    return {'level':number('level'),'temperature_c':None if temperature is None else temperature/10,
            'charging': data.get('usb powered','false')=='true'}
def parse_thermal(text):
    import re
    m=re.search(r'Thermal Status:\s*(\d+)',text)
    return int(m.group(1)) if m else None

def snapshot(host, serial, directory):
    """Capture only private evidence before settings change. Any read failure rejects the window."""
    directory=Path(directory); before=directory/'before'; before.mkdir(parents=True,exist_ok=False)
    from . import preflight
    from .control import session as alvr_session
    inv,sources=preflight.inventory(); records=preflight.snapshot_files(sources,before/'configurations')
    if any(r.get('error') or not r.get('exists') for r in records): raise Refusal('incomplete PC/VD settings snapshot')
    try: session_snapshot=alvr_session()
    except Exception as exc: raise Refusal('matched ALVR session snapshot unavailable: '+str(exc)) from exc
    # Android getprop has no glob form. Preserve the exact old values of every
    # property this supervisor can restore; an absent value is explicitly saved.
    all_props=host.adb_run(serial,'shell','getprop')
    props={'all_filtered':[line for line in all_props.splitlines() if 'debug.q3pw.' in line or 'debug.oculus.' in line],
           'managed':{key: host.adb_run(serial,'shell','getprop',key) for key in managed_properties()}}
    data={'schema':1,'created_utc':utc_now().isoformat(),'preflight':inv,'alvr_session':session_snapshot,'configuration_snapshots':records,'headset_properties':props}
    atomic_write(before/'snapshot.json',data); return data

def live_preconditions(arm, host):
    """Read-only gates repeated immediately before start; no snapshot or mutation."""
    serial=arm['headset_serial']; failures=[]; devices=host.adb_devices()
    if devices != [serial]: failures.append('adb_devices_not_exactly_pinned')
    if not failures:
        if host.adb_run(serial,'shell','getprop','ro.product.model').strip()!='Quest 3': failures.append('not_quest_3')
        battery=parse_battery(host.adb_run(serial,'shell','dumpsys','battery'))
        thermal=parse_thermal(host.adb_run(serial,'shell','dumpsys','thermalservice'))
        if battery['level'] is None or battery['level'] < 50 or not battery['charging'] or battery['temperature_c'] is None or battery['temperature_c'] >= 40: failures.append('battery_or_charge_precondition')
        if thermal is None or thermal > 1: failures.append('thermal_precondition')
    else: battery={}; thermal=None
    if host.idle_seconds() < 30*60: failures.append('owner_not_idle')
    if host.vr_connected(): failures.append('vr_or_virtual_desktop_connected')
    if host.competing_gpu(): failures.append('competing_gpu_workload')
    return failures,battery,thermal

def check_preconditions(arm, host, directory, now=None):
    window=arm_window(arm,now); serial=arm['headset_serial']; failures,battery,thermal=live_preconditions(arm,host)
    report={'schema':1,'checked_utc':utc_now().isoformat(),'arm_sha256':arm_digest(arm),'window':{'deadline_utc':window['deadline'].isoformat(),'remaining_s':window['remaining_s']},'serial':serial,'failures':failures,'battery':battery,'thermal_status':thermal,'gpu_sample':getattr(host,'last_gpu_sample',None),'passed':not failures}
    if not failures:
        try: report['snapshot']=snapshot(host,serial,directory)
        except Exception as exc: report['failures'].append('snapshot_incomplete:'+str(exc)); report['passed']=False
    atomic_write(Path(directory)/'check.json',report); return report

def restore(state_path, host=None):
    """Idempotent deadline-safe fallback with an offline file-copy fallback."""
    state_path=Path(state_path); state=json_read(state_path)
    if state.get('restoration',{}).get('status')=='restored': return state['restoration']
    host=host or Host(state.get('adb','adb')); serial=state['serial']; steps=[]
    client_stopped=False; awake_restored=True
    try:
        host.adb_run(serial,'shell','am','force-stop','io.github.ljk1291.quest3pyrowave'); client_stopped=True; steps.append('fork_client_stopped')
    except Exception as exc: steps.append('fork_client_stop_failed:'+str(exc))
    awake_state = state_path.parent / 'awake.json'
    if awake_state.is_file():
        try:
            awake=json_read(awake_state)
            if awake.get('device') != serial: raise Refusal('awake state serial mismatch')
            from .awake import restore as restore_awake
            restore_awake(awake_state); steps.append('physical_proximity_restored')
        except Exception as exc:
            awake_restored=False; steps.append('physical_proximity_restore_failed:'+str(exc))
    # Restore each managed property, including the empty value which represents
    # an absent pre-window override. Never replay arbitrary getprop output.
    properties=state['snapshot']['headset_properties']
    for key, value in properties.get('managed', {}).items():
        if key in managed_properties():
            try: host.adb_run(serial,'shell',f"setprop {shlex.quote(key)} {shlex.quote(value)}"); steps.append('prop:'+key)
            except Exception as exc: steps.append('prop_failed:'+key+':'+str(exc))
    if not properties.get('managed'):
        # Compatibility with early snapshots: only replay safe, explicit keys.
        import re
        for line in properties.get('all_filtered',[]):
            m=re.match(r'\[([^]]+)\]: \[([^]]*)\]',line)
            if m and m.group(1) in managed_properties():
                try: host.adb_run(serial,'shell',f"setprop {shlex.quote(m.group(1))} {shlex.quote(m.group(2))}"); steps.append('prop:'+m.group(1))
                except Exception as exc: steps.append('prop_failed:'+m.group(1)+':'+str(exc))
    # Do not write OpenXR's registry key directly: the owning runtime selector
    # must own that change. Record whether it already matches the snapshot.
    runtime = state['snapshot'].get('preflight',{}).get('active_openxr_runtime', {}).get('value')
    runtime_restored = runtime is None
    if runtime:
        try:
            from .preflight import registry_value
            current=registry_value(r'SOFTWARE\Khronos\OpenXR\1','ActiveRuntime').get('value')
            runtime_restored = current == runtime
            steps.append('openxr_runtime_verified' if runtime_restored else 'openxr_runtime_requires_owner_selector')
        except Exception as exc: steps.append('openxr_runtime_verify_failed:'+str(exc))
    # Virtual Desktop files and OpenVR driver registration are never copied back.
    # They are verification-only to preserve the owner's registration/settings.
    for record in state['snapshot']['configuration_snapshots']:
        if record.get('label') == 'steamvr_settings' and record.get('exists') and record.get('snapshot'):
            if host.vr_connected():
                steps.append('steamvr_settings_not_restored_active_vr')
            else:
                try: shutil.copyfile(record['snapshot'],record['source']); steps.append('steamvr_settings_restored')
                except OSError as exc: steps.append('steamvr_settings_restore_failed:'+str(exc))
        elif record.get('label','').startswith('virtual_desktop'):
            steps.append('vd_verify_only:'+record['label'])
        elif record.get('label') == 'openvr_paths':
            steps.append('steamvr_drivers_verify_only')
    verification=[]
    try:
        from .preflight import verify_snapshot
        verification=verify_snapshot(state['snapshot']['configuration_snapshots'])
    except Exception as exc: verification=[{'error':str(exc)}]
    files_ok=all(x.get('error') is None and x.get('current_matches') is True for x in verification)
    property_readback={}; properties_ok=True
    for key, wanted in properties.get('managed', {}).items():
        try:
            got=host.adb_run(serial,'shell','getprop',key)
            property_readback[key]={'expected':wanted,'actual':got,'matches':got == wanted}
            properties_ok = properties_ok and got == wanted
        except Exception as exc:
            property_readback[key]={'expected':wanted,'error':str(exc),'matches':False}; properties_ok=False
    vd_checks=[row for row in verification if str(row.get('label','')).startswith('virtual_desktop')]
    vd_hashes_match=all(x.get('error') is None and x.get('current_matches') is True for x in vd_checks)
    ok=files_ok and runtime_restored and properties_ok and client_stopped and awake_restored
    state['restoration']={'status':'restored' if ok else 'restore_failed','at_utc':utc_now().isoformat(),'steps':steps,'fallback':'only_steamvr_settings_copy_when_inactive;_vd_and_driver_files_verify_only','vd_hashes_match':vd_hashes_match,'openxr_runtime_restored':runtime_restored,'client_stopped':client_stopped,'physical_proximity_restored':awake_restored,'property_readback':property_readback,'properties_restored':properties_ok,'verification':verification}
    atomic_write(state_path,state); return state['restoration']

def health_decision(sample, state, now):
    """Pure monitor transition. Third pause ends window; resume needs 15 min and <=40C."""
    hot=(sample.get('thermal_status') is None or sample.get('thermal_status')>=PAUSE_STATUS or
         sample.get('battery') is None or sample.get('battery')<30 or
         sample.get('temperature_c') is None or sample.get('temperature_c')>=46)
    if state.get('ended'): return 'ended'
    if hot:
        if not state.get('paused'): state.update(paused=True,paused_at=now,pauses=state.get('pauses',0)+1)
        if state['pauses']>=3: state['ended']=True; return 'end'
        return 'pause'
    if (state.get('paused') and now-state['paused_at']>=15*60 and sample.get('temperature_c',99)<=40 and
            sample.get('thermal_status') is not None and sample.get('thermal_status') <= 1 and
            sample.get('battery') is not None and sample.get('battery') >= 30):
        state['paused']=False; return 'resume'
    return 'paused' if state.get('paused') else 'run'

def worker(state_path, monitor=False):
    state_path=Path(state_path); host=Host(); state=json_read(state_path); host.keep_awake(True)
    role='monitor' if monitor else 'restorer'
    ready = state_path.parent / (role+'.ready')
    try:
        atomic_write(ready, {'pid':os.getpid(),'role':role,'nonce':state['guard_nonce'],'ready_utc':utc_now().isoformat()})
        while True:
            state=json_read(state_path); now=time.time()
            if (state_path.parent/'stop').exists() or now>=state['deadline_epoch_s']:
                if not monitor: restore(state_path,host)
                return
            if monitor:
                b=parse_battery(host.adb_run(state['serial'],'shell','dumpsys','battery')); t=parse_thermal(host.adb_run(state['serial'],'shell','dumpsys','thermalservice'))
                # The monitor owns a separate record. It never rewrites state.json,
                # so it cannot race the deadline restorer's final restoration record.
                monitor_path=state_path.parent/'monitor.json'
                m=json_read(monitor_path) if monitor_path.is_file() else {'schema':1}
                m['last_sample_epoch_s']=now
                action=health_decision({'battery':b['level'],'temperature_c':b['temperature_c'],'thermal_status':t},m,now)
                gpu_sample=host.gpu_sample() if hasattr(host,'gpu_sample') else {'conflicts':host.competing_gpu()}
                workload=gpu_sample['conflicts']; m['competing_gpu']=workload; m['gpu_sample']=gpu_sample
                pause_marker=state_path.parent/'pause'
                if workload:
                    # A timing cell cannot remain valid once the owner's GPU work
                    # appears. Pause the controlled worker; never kill its process.
                    m['workload_paused']=True; action='pause_workload'
                    pause_marker.write_text('competing GPU workload\n',encoding='utf-8')
                elif m.pop('workload_paused',False) and not m.get('paused') and pause_marker.exists():
                    pause_marker.unlink()
                if action == 'pause': pause_marker.write_text('thermal/battery pause\n',encoding='utf-8')
                elif action == 'resume' and pause_marker.exists() and not workload: pause_marker.unlink()
                m['last_action']=action; atomic_write(monitor_path,m)
                if action=='end': (state_path.parent/'stop').write_text('thermal/battery terminal\n',encoding='utf-8'); continue
            # The deadline restorer sleeps only until its exact deadline; the
            # monitor retains its fixed 30-second cadence.
            time.sleep(POLL_SECONDS if monitor else max(0, min(POLL_SECONDS, state['deadline_epoch_s']-time.time())))
    finally: host.keep_awake(False)

def spawn_worker(state, monitor):
    args=[sys.executable,'-m','tools.quest3.unattended','--worker',str(state),'--monitor' if monitor else '--restorer']
    opts={'creationflags':(getattr(subprocess,'CREATE_NO_WINDOW',0) | getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0) | getattr(subprocess,'DETACHED_PROCESS',0))} if os.name=='nt' else {'start_new_session':True}
    return subprocess.Popen(args,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**opts)

def wait_for_guard(directory, name, nonce, pid, timeout_s=GUARD_READY_SECONDS):
    marker=Path(directory)/(name+'.ready'); deadline=time.monotonic()+timeout_s
    while time.monotonic()<deadline:
        if marker.is_file():
            try:
                ready=json_read(marker)
                if (set(ready) == {'pid','role','nonce','ready_utc'} and ready['pid'] == pid and
                        ready['role'] == name and ready['nonce'] == nonce and isinstance(ready['ready_utc'],str)):
                    return True
            except (OSError, ValueError, json.JSONDecodeError): pass
        time.sleep(.05)
    return False

def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0: return False
    try:
        if os.name == 'nt':
            result=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/NH'],capture_output=True,text=True,timeout=5)
            return str(pid) in result.stdout
        os.kill(pid,0); return True
    except (OSError, subprocess.SubprocessError): return False

def status_payload(directory, arm_path=ARM, now=None, require_allow=None):
    """Stable read-only lease contract for other unattended tools.

    A consumer must check ``lease.active`` immediately before every subprocess
    and terminate it if polling changes this to false. It is deliberately false
    for a revoked/expired arm, stale or dead guard, stop marker, thermal pause,
    or competing workload.
    """
    directory=Path(directory); state_path=directory/'state.json'; now=now or utc_now()
    stop=(directory/'stop').is_file(); pause=(directory/'pause').is_file()
    arm={'present':Path(arm_path).is_file(),'active':False,'reason':None}; arm_value=None
    if arm['present']:
        try:
            arm_value=json_read(arm_path); arm_window(arm_value,now,require_remaining=False); arm['active']=True
            arm['allowed_actions']=arm_value.get('allow',[])
        except Exception as exc: arm['reason']=str(exc); arm['allowed_actions']=[]
    else: arm['reason']='arm file missing or revoked'; arm['allowed_actions']=[]
    empty_guards={'restorer':{'ready':False,'alive':False},'monitor':{'ready':False,'alive':False}}
    if not state_path.is_file():
        return {'schema':1,'window_id':directory.name,'lease':{'active':False,'reason':'window state missing','blockers':['window_state_missing']},'arm':arm,
                'guards':empty_guards,'cancellation':{'stop_requested':stop,'paused':pause,'competing_gpu':[]}}
    state=json_read(state_path); deadline=state.get('deadline_epoch_s',0)
    guard_pids=state.get('guard_pids',{})
    guards={}
    for role in ('restorer','monitor'):
        pid=guard_pids.get(role); marker=directory/(role+'.ready'); ready=False
        try:
            record=json_read(marker)
            ready=(set(record)=={'pid','role','nonce','ready_utc'} and record['pid']==pid and
                   record['role']==role and record['nonce']==state.get('guard_nonce'))
        except (OSError, ValueError, json.JSONDecodeError): pass
        guards[role]={'ready':ready,'pid':pid,'alive':pid_alive(pid)}
    monitor_path=directory/'monitor.json'
    monitor=json_read(monitor_path) if monitor_path.is_file() else state.get('monitor',{})
    sample=monitor.get('last_sample_epoch_s')
    sample_age=now.timestamp()-sample if isinstance(sample,(int,float)) else None
    sample_fresh=sample_age is not None and 0 <= sample_age <= POLL_SECONDS*2+5
    restored=state.get('restoration',{}).get('status') != 'pending'
    blockers=[]
    if not arm['active'] or arm_value is None or state.get('arm_sha256') != arm_digest(arm_value): blockers.append('arm_inactive')
    if require_allow and require_allow not in arm['allowed_actions']: blockers.append('action_not_allowed')
    if now.timestamp() >= deadline: blockers.append('deadline_expired')
    if stop: blockers.append('stop_requested')
    if restored: blockers.append('restoration_started')
    if not state.get('guards_ready'): blockers.append('guards_not_ready')
    if not guards['restorer']['ready'] or not guards['restorer']['alive']: blockers.append('restorer_unhealthy')
    if not guards['monitor']['ready'] or not guards['monitor']['alive']: blockers.append('monitor_unhealthy')
    if not sample_fresh: blockers.append('monitor_stale')
    if pause or monitor.get('paused'): blockers.append('thermal_or_battery_paused')
    if monitor.get('workload_paused') or monitor.get('competing_gpu'): blockers.append('competing_gpu_workload')
    return {'schema':1,'window_id':state.get('window_id',directory.name),
            'lease':{'active':not blockers,'deadline_epoch_s':deadline,'reason':None if not blockers else blockers[0],'blockers':blockers},
            'arm':arm,'guards':guards,'cancellation':{'stop_requested':stop,'paused':pause,
            'monitor_action':monitor.get('last_action'),'competing_gpu':monitor.get('competing_gpu',[]),
            'monitor_sample_epoch_s':sample,'monitor_fresh':sample_fresh},'restoration':state.get('restoration',{})}

def main():
    if '--worker' in sys.argv:
        index=sys.argv.index('--worker')
        try: worker(Path(sys.argv[index+1]), '--monitor' in sys.argv)
        except IndexError: raise SystemExit('worker state missing')
        return
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('arm'); a.add_argument('--file',type=Path,required=True); a.add_argument('--owner-confirm',action='store_true')
    for name in ('check','start','status','stop','restore'):
        x=sub.add_parser(name); x.add_argument('--arm',type=Path,default=ARM); x.add_argument('--window',type=Path); x.add_argument('--require-allow')
    p.add_argument('--worker',type=Path,help=argparse.SUPPRESS); p.add_argument('--monitor',action='store_true',help=argparse.SUPPRESS); p.add_argument('--restorer',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    if args.worker: worker(args.worker,args.monitor); return
    if args.cmd=='arm':
        if not args.owner_confirm: p.error('owner-only: pass --owner-confirm after reviewing the arm file')
        arm=json_read(args.file); validate_arm_definition(arm); PRIVATE.mkdir(parents=True,exist_ok=True)
        if ARM.exists(): p.error('refusing to overwrite existing owner arm file')
        shutil.copyfile(args.file,ARM); print(json.dumps({'armed':str(ARM)})); return
    if not args.window: p.error('--window is required')
    directory=Path(args.window)
    state_path=directory/'state.json'
    # Emergency status/stop/restore remain available after expiry or owner arm
    # revocation. Only starting or checking a window requires an active arm.
    if args.cmd in {'check','start'}:
        if not args.arm.is_file(): p.error('arm file missing')
        arm,window=load_arm(args.arm)
    if args.cmd=='check': print(json.dumps(check_preconditions(arm,Host(),directory),indent=2)); return
    if args.cmd=='start':
        check=json_read(Path(directory)/'check.json') if (Path(directory)/'check.json').is_file() else None
        if not check or not check.get('passed') or not check.get('snapshot'): p.error('refusing start: successful check and snapshot required')
        try:
            checked=datetime.fromisoformat(check['checked_utc']).astimezone(timezone.utc)
            check_deadline=datetime.fromisoformat(check['window']['deadline_utc']).astimezone(timezone.utc)
        except (KeyError, ValueError, TypeError): p.error('refusing start: malformed check record')
        check_age=(utc_now()-checked).total_seconds()
        if (check.get('serial') != arm['headset_serial'] or check.get('arm_sha256') != arm_digest(arm) or
                check_deadline != window['deadline'] or not 0 <= check_age <= CHECK_FRESH_SECONDS):
            p.error('refusing start: check is stale or belongs to a different arm/window')
        try:
            from .preflight import verify_snapshot
            source_ok=all(x.get('error') is None and x.get('current_matches') is True
                          for x in verify_snapshot(check['snapshot']['configuration_snapshots']))
        except (KeyError, OSError, ValueError): source_ok=False
        if not source_ok: p.error('refusing start: source settings changed after snapshot')
        live_failures, _, _ = live_preconditions(arm,Host())
        if live_failures: p.error('refusing start: preconditions changed: '+','.join(live_failures))
        if state_path.exists() or (directory/'stop').exists() or (directory/'pause').exists():
            p.error('refusing start: window already has state or a cancellation marker')
        # Ready records are generated by fresh workers and bound to a nonce/PID.
        for name in ('restorer.ready','monitor.ready','monitor.json'):
            (directory/name).unlink(missing_ok=True)
        nonce=uuid.uuid4().hex
        state={'schema':1,'window_id':directory.name,'serial':arm['headset_serial'],'adb':'adb','deadline_epoch_s':window['deadline'].timestamp(),'snapshot':check['snapshot'],'restoration':{'status':'pending'},'guards_ready':False,'guard_pids':{},'guard_nonce':nonce,'arm_sha256':arm_digest(arm)}
        atomic_write(state_path,state)
        r=spawn_worker(state_path,False)
        if not wait_for_guard(directory,'restorer',nonce,r.pid) or not pid_alive(r.pid):
            (directory/'stop').write_text('restorer failed readiness\n',encoding='utf-8')
            p.error('refusing start: deadline restorer did not become ready')
        state=json_read(state_path); state['guard_pids']['restorer']=r.pid; atomic_write(state_path,state)
        m=spawn_worker(state_path,True)
        if not wait_for_guard(directory,'monitor',nonce,m.pid) or not pid_alive(m.pid):
            (directory/'stop').write_text('monitor failed readiness\n',encoding='utf-8')
            p.error('refusing start: thermal monitor did not become ready')
        state=json_read(state_path); state['guard_pids']['monitor']=m.pid; state['guards_ready']=True; atomic_write(state_path,state)
        print(json.dumps({'window':str(directory),'restorer_pid':r.pid,'monitor_pid':m.pid})); return
    if not state_path.is_file(): p.error('window state missing')
    if args.cmd=='status': print(json.dumps(status_payload(directory,args.arm,require_allow=args.require_allow),indent=2)); return
    if args.cmd=='stop': (Path(directory)/'stop').write_text('requested\n'); print(json.dumps({'stop_marker':str(Path(directory)/'stop')})); return
    if args.cmd=='restore': print(json.dumps(restore(state_path),indent=2)); return
if __name__=='__main__': main()

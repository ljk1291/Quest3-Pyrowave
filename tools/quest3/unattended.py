"""Fail-closed supervisor for owner-armed Quest 3 unattended windows.

No hardware action is taken by importing this module. The CLI's ``arm`` command is
an owner-only convenience: it requires an explicit acknowledgement and is never
called by automation. All device commands include the serial stored in the arm.
"""
from __future__ import annotations
import argparse, contextlib, ctypes, hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile, threading, time, uuid, urllib.request
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo
import math

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
RESTORE_LOCK_SECONDS = 60
RESTORE_LOCK_ATTEMPTS = 3

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
        # 02:00�02:59 on the fall-back date occurs twice. ``fold`` selects
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
_LOCK_DEPTH={}
@contextlib.contextmanager
def state_lock(state_path, timeout_s=5):
    """Cross-process state lock; released by the OS if a holder crashes."""
    path=Path(state_path).with_suffix('.lock'); key=(threading.get_ident(),str(path.resolve())); depth=_LOCK_DEPTH.get(key,0)
    if depth:
        _LOCK_DEPTH[key]=depth+1
        try: yield
        finally: _LOCK_DEPTH[key]-=1
        return
    path.parent.mkdir(parents=True,exist_ok=True); stream=open(path,'a+b'); deadline=time.monotonic()+timeout_s
    while True:
        try:
            if os.name=='nt':
                import msvcrt; stream.seek(0); msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl; fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            break
        except OSError:
            if time.monotonic()>=deadline: stream.close(); raise Refusal('state lock timeout')
            time.sleep(.05)
    _LOCK_DEPTH[key]=1
    try: yield
    finally:
        _LOCK_DEPTH.pop(key,None)
        try:
            if os.name=='nt': stream.seek(0); msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        finally: stream.close()

def locked_state_mutation(func):
    def wrapped(state_path, *args, **kwargs):
        with state_lock(state_path): return func(state_path, *args, **kwargs)
    return wrapped

def json_read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def arm_digest(arm): return hashlib.sha256(json.dumps(arm,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def atomic_write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True)); temp=Path(stream.name)
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

def effective_window_limit(arm):
    """Apply only a recorded, exact owner exception; never alter the arm file."""
    declared = float(arm['max_window_hours'])
    result = {'hours': declared, 'ceiling_hours': MAX_HOURS, 'exception_id': None}
    path = ROOT / 'presets' / 'unattended-owner-exceptions.json'
    if not path.is_file(): return result
    try:
        policy = json_read(path)
        if policy.get('schema') != 1 or not isinstance(policy.get('once_windows'), list):
            raise ValueError('invalid exception policy')
        for entry in policy['once_windows']:
            fields = ('mode', 'timezone', 'not_before_local', 'not_after_local', 'expires_local')
            if (all(arm.get(key) == entry.get(key) for key in fields)
                    and arm.get('mode') == 'once'
                    and arm.get('allow') == entry.get('allow')
                    and declared == float(entry['arm_max_window_hours'])):
                approved = float(entry['approved_max_window_hours'])
                if not math.isfinite(approved) or not declared <= approved <= 8:
                    raise ValueError('invalid approved limit')
                return {'hours': approved, 'ceiling_hours': approved, 'exception_id': entry['id']}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Refusal('owner duration exception policy invalid') from exc
    return result

def validate_arm_definition(arm):
    """Validate an owner file without requiring that its future window is active."""
    if arm.get('schema') != 1 or arm.get('mode') not in {'once', 'nightly'}:
        raise Refusal('unsupported arm schema or mode')
    if not isinstance(arm.get('headset_serial'), str) or not arm['headset_serial']:
        raise Refusal('missing headset serial')
    if not isinstance(arm.get('allow'), list) or not all(isinstance(x, str) for x in arm['allow']):
        raise Refusal('invalid allow list')
    try:
        zone=timezone_for(arm['timezone']); limit=effective_window_limit(arm); max_hours=limit['hours']
        expires=local_dt(arm['expires_local'], zone)
        if arm['mode']=='nightly':
            sh,sm=parse_clock(arm['start_local']); eh,em=parse_clock(arm['end_local'])
            start=datetime(2026,1,1,sh,sm,tzinfo=zone); end=datetime(2026,1,1,eh,em,tzinfo=zone)
            if end <= start: end += timedelta(days=1)
        else:
            start=local_dt(arm['not_before_local'], zone); end=local_dt(arm['not_after_local'], zone)
    except (KeyError, ValueError, TypeError) as exc:
        raise Refusal('invalid arm time fields') from exc
    if not 0 < max_hours <= limit['ceiling_hours'] or end <= start or end-start > timedelta(hours=max_hours):
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
        limit=effective_window_limit(arm); max_hours=limit['hours']
    except (KeyError, ValueError, TypeError) as exc: raise Refusal('invalid arm time fields') from exc
    if not 0 < max_hours <= limit['ceiling_hours']: raise Refusal('max window exceeds authorized limit')
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
    return {'start':start.astimezone(timezone.utc), 'deadline':deadline.astimezone(timezone.utc), 'remaining_s':remaining, 'zone':str(zone), 'duration_authorization':limit}

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
    def _comfy_pids(self):
        if os.name != 'nt': return []
        script="Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match 'ComfyUI|--port\\s+8192|:8192'} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        try:
            data=json.loads(self.run('powershell','-NoProfile','-NonInteractive','-Command',script,timeout=8)); return data if isinstance(data,list) else ([data] if data else [])
        except Exception: return []
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
        comfy_pids=self._comfy_pids(); comfy_running=bool(comfy_pids)
        comfy=self._comfy_queue() if comfy_running else {'known':True,'running':0,'pending':0,'error':None}
        conflicts=[]
        if comfy_running and (not comfy['known'] or comfy['running'] or comfy['pending']): conflicts.append('comfy_queue_active_or_unknown')
        apps=[]; executable=shutil.which('nvidia-smi') or shutil.which('nvidia-smi.exe')
        if executable:
            try:
                rows=self.run(executable,'--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader,nounits',timeout=5)
                apps=[line.strip() for line in rows.splitlines() if line.strip() and 'No running processes' not in line]
                # A live Comfy process is allowed only when its local queue reports idle.
                idle_comfy={str(row.get('ProcessId')) for row in comfy_pids} if comfy.get('known') and not comfy.get('running') and not comfy.get('pending') else set()
                conflicts.extend(row for row in apps if row.split(',',1)[0].strip() not in idle_comfy)
            except Refusal as exc: apps=['nvidia-smi-error:'+str(exc)]; conflicts.append('gpu_compute_status_unknown')
        else: conflicts.append('gpu_compute_status_unknown')
        sample={'at_utc':utc_now().isoformat(),'comfy':comfy,'comfy_processes':comfy_pids,'nvidia_compute_apps':apps,'conflicts':conflicts}
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
                states=[str(row.get('connection_state','')).casefold() for row in clients.values() if isinstance(row,dict)]
                return any(state in {'connected','streaming','streamingactive'} for state in states)
            except Exception:
                # Dashboard exists but its actual session state cannot be read.
                return True
        if 'virtualdesktop.streamer.exe' in out:
            state=self._vd_log_state()
            # A resident streamer is acceptable only with a recent, explicit
            # disconnected record; unknown is fail-closed.
            return state is not False
        return False
    def process_identity(self, pid):
        return windows_process_identity(pid)
    def stop_owned_runtime(self, record):
        """Gracefully close, then force only the already verified owned PID."""
        try: actual=self.process_identity(record['pid'])
        except Refusal:
            if not pid_alive(record['pid']): return True
            raise
        if not ownership_matches(record,actual,record['nonce']): raise Refusal('runtime ownership changed; no stop issued')
        if actual.get('exited') is True: return True
        if os.name != 'nt': raise Refusal('Windows process stop is required')
        script=owned_stop_script(record)
        self.run('powershell','-NoProfile','-NonInteractive','-Command',script,timeout=20)
        return True
    def keep_awake(self, active):
        if os.name=='nt':
            flags=0x80000000 | (0x00000001 if active else 0)
            ctypes.windll.kernel32.SetThreadExecutionState(flags)

def windows_process_identity(pid):
    """Query one retained handle promptly, including for short offline children."""
    if os.name!='nt': raise Refusal('Windows process identity is required')
    from ctypes import wintypes as w
    pid=int(pid)
    if not 0<pid<=0xffffffff: raise Refusal('invalid process identity')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; kernel.OpenProcess.restype=w.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    kernel.QueryFullProcessImageNameW.restype=w.BOOL
    kernel.GetProcessTimes.argtypes=[w.HANDLE]+[ctypes.POINTER(w.FILETIME)]*4
    kernel.GetProcessTimes.restype=w.BOOL
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)]; kernel.GetExitCodeProcess.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE]; kernel.CloseHandle.restype=w.BOOL
    handle=kernel.OpenProcess(0x1000,False,pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle: raise Refusal('process identity unavailable')
    try:
        path=ctypes.create_unicode_buffer(32768); size=w.DWORD(len(path))
        created=w.FILETIME(); exited=w.FILETIME(); kernel_time=w.FILETIME(); user_time=w.FILETIME()
        if (not kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) or
                not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),
                                           ctypes.byref(kernel_time),ctypes.byref(user_time))):
            raise Refusal('process identity unavailable')
        exit_code=w.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code)): raise Refusal('process exit state unavailable')
        ticks=(int(created.dwHighDateTime)<<32)|int(created.dwLowDateTime)
        # Same millisecond convention as the retained-handle PowerShell stop.
        started=(ticks//10000-11644473600000)/1000.0
        return {'pid':pid,'path':path.value,'started_epoch_s':started,'exited':exit_code.value!=259}
    finally: kernel.CloseHandle(handle)

def owned_stop_script(record):
    """Verify and retain the same Windows process handle through termination."""
    pid=int(record['pid']); started=float(record['started_epoch_s'])
    if pid<=0 or not math.isfinite(started): raise Refusal('invalid process identity')
    expected=Path(record['path']).resolve().as_posix().replace("'","''")
    return ("$ErrorActionPreference='Stop'; $p=Get-Process -Id %d; $null=$p.Handle; "
            "if($p.HasExited){exit 0}; "
            "$actualPath=[IO.Path]::GetFullPath($p.Path).Replace('\\','/'); "
            "$started=([DateTimeOffset]$p.StartTime.ToUniversalTime()).ToUnixTimeMilliseconds()/1000.0; "
            "if(-not [string]::Equals($actualPath,'%s',[StringComparison]::OrdinalIgnoreCase) "
            "-or [Math]::Abs($started-%.6f) -ge 0.001){throw 'runtime ownership changed; no stop issued'}; "
            "$null=$p.CloseMainWindow(); if(-not $p.WaitForExit(5000)){ $p.Kill(); "
            "if(-not $p.WaitForExit(10000)){throw 'owned process did not exit'}}") % (pid,expected,started)

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

def snapshot(host, serial, directory, alvr_session_path=None):
    """Capture only private evidence before settings change. Any read failure rejects the window."""
    directory=Path(directory); before=directory/'before'; before.mkdir(parents=True,exist_ok=False)
    from . import preflight
    from .control import session as alvr_session
    inv,sources=preflight.inventory()
    try:
        if alvr_session_path:
            cold=Path(alvr_session_path)
            session_snapshot=json_read(cold); sources['alvr_session']=cold
        else:
            session_snapshot=alvr_session()
            alvr_path=session_snapshot.get('drivers_backup',{}).get('alvr_path')
            if not alvr_path: raise Refusal('ALVR session path unavailable')
            sources['alvr_session']=Path(alvr_path)/'session.json'
    except Exception as exc: raise Refusal('matched ALVR session snapshot unavailable: '+str(exc)) from exc
    records=preflight.snapshot_files(sources,before/'configurations')
    required={'virtual_desktop_streamer','virtual_desktop_games','openvr_paths','steamvr_settings','alvr_session'}
    if not required.issubset({row['label'] for row in records}): raise Refusal('required settings snapshot missing')
    if any(r.get('error') or not r.get('exists') for r in records): raise Refusal('incomplete PC/VD/ALVR settings snapshot')
    runtime=inv.get('active_openxr_runtime',{})
    manifest=inv.get('active_openxr_runtime_manifest',{})
    if (runtime.get('error') or not runtime.get('value') or manifest.get('error')
            or not manifest.get('exists') or not manifest.get('sha256')):
        raise Refusal('active OpenXR runtime provenance unavailable')
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

def check_preconditions(arm, host, directory, now=None, alvr_session_path=None):
    window=arm_window(arm,now); serial=arm['headset_serial']; failures,battery,thermal=live_preconditions(arm,host)
    report={'schema':1,'checked_utc':utc_now().isoformat(),'arm_sha256':arm_digest(arm),'window':{'deadline_utc':window['deadline'].isoformat(),'remaining_s':window['remaining_s']},'serial':serial,'failures':failures,'battery':battery,'thermal_status':thermal,'gpu_sample':getattr(host,'last_gpu_sample',None),'adb':getattr(host,'adb','adb'),'passed':not failures}
    if not failures:
        try: report['snapshot']=snapshot(host,serial,directory,alvr_session_path)
        except Exception as exc: report['failures'].append('snapshot_incomplete:'+str(exc)); report['passed']=False
    atomic_write(Path(directory)/'check.json',report); return report

def _restore_locked(state_path, host=None):
    """Idempotent deadline-safe fallback with an offline file-copy fallback."""
    state_path=Path(state_path); state=json_read(state_path)
    if state.get('restoration',{}).get('status')=='restored': return state['restoration']
    lock=state_path.parent/'restoration.lock'
    state['restoration']={'status':'restoring','at_utc':utc_now().isoformat()}; atomic_write(state_path,state)
    host=host or Host(state.get('adb','adb')); serial=state['serial']; steps=[]
    # New windows retain their action scope for deadline cleanup. PC-only work
    # never launched the client or changed properties, so verify without writes.
    # Missing scope preserves cleanup for historical device-window state files.
    device_cleanup=bool(set(state.get('allowed_actions',['chart_cells','decoder_timing'])) &
                        {'chart_cells','decoder_timing'})
    client_stopped=None; awake_restored=True
    if device_cleanup:
        client_stopped=False
        try:
            host.adb_run(serial,'shell','am','force-stop','io.github.ljk1291.quest3pyrowave'); client_stopped=True; steps.append('fork_client_stopped')
        except Exception as exc: steps.append('fork_client_stop_failed:'+str(exc))
    else: steps.append('headset_verify_only_for_pc_window')
    owned_results=[]; owned_ok=True
    for record in state.get('owned_runtime',[]):
        try: host.stop_owned_runtime(record); owned_results.append({'role':record.get('role'),'stopped':True})
        except Exception as exc: owned_ok=False; owned_results.append({'role':record.get('role'),'stopped':False,'error':str(exc)})
    jobs_ok=True; job_results=[]
    for record in state.get('owned_pc_jobs',[]):
        try: host.stop_owned_runtime(record); job_results.append({'pid':record['pid'],'stopped':True})
        except Exception as exc: jobs_ok=False; job_results.append({'pid':record['pid'],'stopped':False,'error':str(exc)})
    if host.vr_connected():
        owned_ok=False; steps.append('unclaimed_or_unstopped_vr_runtime_present')
    alvr_restored=not any(row.get('kind')=='alvr' for row in state.get('changes',[]))
    records=state['snapshot']['configuration_snapshots']
    exact_files={row['label'] for row in records if row.get('sha256') and row.get('snapshot')}
    if not alvr_restored and owned_ok and 'alvr_session' not in exact_files:
        try:
            from .control import session as _session, set_values as _set_values
            alvr_restored=restore_recorded_alvr(state,(_session,_set_values)); steps.append('alvr_api_restored')
        except Exception as exc: steps.append('alvr_api_restore_failed:'+str(exc))
    steamvr_restored=not any(row.get('kind')=='steamvr' for row in state.get('changes',[]))
    if not steamvr_restored and owned_ok and 'steamvr_settings' not in exact_files:
        try: steamvr_restored=restore_recorded_steamvr(state); steps.append('steamvr_exact_keys_restored')
        except Exception as exc: steps.append('steamvr_restore_failed:'+str(exc))
    driver_restored=not any(row.get('kind')=='fork_driver' for row in state.get('changes',[]))
    if not driver_restored and owned_ok:
        try:
            steam=next((row for row in state.get('owned_runtime',[]) if row.get('role')=='steamvr'),None)
            if not steam: raise Refusal('claimed SteamVR runtime missing')
            vrpathreg=Path(steam['path']).resolve().parent/'vrpathreg.exe'
            driver_restored=restore_recorded_driver(state,vrpathreg); steps.append('fork_driver_membership_restored')
        except Exception as exc: steps.append('fork_driver_restore_failed:'+str(exc))
    awake_state = state_path.parent / 'awake.json'
    if awake_state.is_file() and device_cleanup:
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
    for key, value in (properties.get('managed', {}) if device_cleanup else {}).items():
        if key in managed_properties():
            try: host.adb_run(serial,'shell',f"setprop {shlex.quote(key)} {shlex.quote(value)}"); steps.append('prop:'+key)
            except Exception as exc: steps.append('prop_failed:'+key+':'+str(exc))
    if device_cleanup and not properties.get('managed'):
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
            from .preflight import registry_value,sha256
            current=registry_value(r'SOFTWARE\Khronos\OpenXR\1','ActiveRuntime').get('value')
            runtime_restored = current == runtime
            manifest=state['snapshot'].get('preflight',{}).get('active_openxr_runtime_manifest',{})
            if manifest.get('sha256'):
                runtime_restored=runtime_restored and sha256(Path(manifest['path']))==manifest['sha256']
            steps.append('openxr_runtime_verified' if runtime_restored else 'openxr_runtime_requires_owner_selector')
        except Exception as exc: steps.append('openxr_runtime_verify_failed:'+str(exc))
    # VD/driver files are verification-only. Exact ALVR/SteamVR restoration
    # requires stopped owned runtimes and proof that every difference is ours.
    for record in state['snapshot']['configuration_snapshots']:
        if record.get('label','').startswith('virtual_desktop'):
            steps.append('vd_verify_only:'+record['label'])
        elif record.get('label') == 'openvr_paths':
            steps.append('steamvr_drivers_verify_only')
        if record.get('label') in {'alvr_session','steamvr_settings'}:
            label=record['label']
            try:
                result=restore_configuration_bytes(state,record,owned_ok=owned_ok)
                steps.append(label+':'+result)
                if label=='alvr_session': alvr_restored=True
                else: steamvr_restored=True
            except Exception as exc:
                steps.append(label+'_exact_restore_failed:'+str(exc))
                if label=='alvr_session': alvr_restored=False
                else: steamvr_restored=False
    verification=[]
    try:
        from .preflight import verify_snapshot
        verification=verify_snapshot(state['snapshot']['configuration_snapshots'])
    except Exception as exc: verification=[{'error':str(exc)}]
    files_ok=all(x.get('error') is None and x.get('backup_valid') is not False and x.get('current_matches') is True for x in verification)
    property_readback={}; properties_ok=True
    for key, wanted in properties.get('managed', {}).items():
        try:
            got=host.adb_run(serial,'shell','getprop',key)
            property_readback[key]={'expected':wanted,'actual':got,'matches':got == wanted}
            properties_ok = properties_ok and got == wanted
        except Exception as exc:
            property_readback[key]={'expected':wanted,'error':str(exc),'matches':False}; properties_ok=False
    vd_checks=[row for row in verification if str(row.get('label','')).startswith('virtual_desktop')]
    vd_hashes_match=all(x.get('error') is None and x.get('backup_valid') is not False and x.get('current_matches') is True for x in vd_checks)
    ok=files_ok and runtime_restored and properties_ok and (not device_cleanup or client_stopped) and awake_restored and owned_ok and alvr_restored and steamvr_restored and driver_restored and jobs_ok
    state['restoration']={'status':'restored' if ok else 'restore_failed','at_utc':utc_now().isoformat(),'steps':steps,'fallback':'exact_owned_configuration_only;_VD_and_global_runtime_verify_only','vd_hashes_match':vd_hashes_match,'openxr_runtime_restored':runtime_restored,'client_stop_required':device_cleanup,'client_stopped':client_stopped,'owned_runtime':owned_results,'owned_runtime_stopped':owned_ok,'alvr_restored':alvr_restored,'steamvr_restored':steamvr_restored,'driver_restored':driver_restored,'owned_pc_jobs':job_results,'owned_pc_jobs_stopped':jobs_ok,'physical_proximity_restored':awake_restored,'property_readback':property_readback,'properties_restored':properties_ok,'verification':verification}
    atomic_write(state_path,state)
    atomic_write(state_path.parent/'restoration.json',state['restoration'])
    return state['restoration']

def restore(state_path, host=None):
    """Revoke the lease before waiting on state writers, then reload under lock."""
    state_path=Path(state_path); stop=state_path.parent/'stop'; stop.write_text('restoration requested\n',encoding='utf-8')
    claim=state_path.parent/'restoration.lock'
    # This is a revocation marker, not the mutex. A crashed claimant must never
    # prevent the independent restorer from acquiring the OS-backed state lock.
    atomic_write(claim,{'pid':os.getpid(),'at_utc':utc_now().isoformat()})
    acquired=False
    try:
        with state_lock(state_path,timeout_s=RESTORE_LOCK_SECONDS):
            acquired=True
            try:
                result=_restore_locked(state_path,host)
                atomic_write(state_path.parent/'restoration.json',result)
                return result
            except Exception as exc:
                # Reload while still holding the mutex: never replace a state
                # snapshot that an earlier mutation has just completed.
                state=json_read(state_path)
                if state.get('restoration',{}).get('status')!='restored':
                    state['restoration']={'status':'restore_failed','at_utc':utc_now().isoformat(),
                                          'error':type(exc).__name__}
                    atomic_write(state_path,state)
                    atomic_write(state_path.parent/'restoration.json',state['restoration'])
                raise
            finally:
                claim.unlink(missing_ok=True)
    except Exception as exc:
        if not acquired:
            # A lock timeout is an attempt failure, not a competing final state.
            # Keep stop/claim revoked and publish a separate recovery diagnostic.
            atomic_write(state_path.parent/('restore-attempt-'+uuid.uuid4().hex+'.json'),
                         {'status':'lock_wait_failed','at_utc':utc_now().isoformat(),
                          'error':type(exc).__name__})
        raise

def restore_with_retry(state_path, host=None):
    """Finite retry when a bounded in-flight writer still owns the mutex."""
    for attempt in range(RESTORE_LOCK_ATTEMPTS):
        try: return restore(state_path,host)
        except Refusal as exc:
            if str(exc)!='state lock timeout' or attempt+1==RESTORE_LOCK_ATTEMPTS: raise

def terminal_fault_decision(state, fault):
    """A second terminal codec/connection fault ends device work and requests restore."""
    faults=state.setdefault('terminal_faults',[]); faults.append({'fault':fault,'at_utc':utc_now().isoformat()})
    if len(faults) >= 2:
        state['ended']=True; return 'restore'
    return 'recover'

@locked_state_mutation
def record_terminal_fault(state_path, fault):
    """Persist a terminal fault; second fault atomically requests deadline restoration."""
    state_path=Path(state_path); state=json_read(state_path)
    if ((state_path.parent/'stop').exists() or (state_path.parent/'restoration.lock').exists()
            or state.get('restoration',{}).get('status') != 'pending'): raise Refusal('rollback has begun')
    action=terminal_fault_decision(state,fault); atomic_write(state_path,state)
    if action=='restore': (state_path.parent/'stop').write_text('second terminal fault\n',encoding='utf-8')
    return action

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
    state_path=Path(state_path); state=json_read(state_path); host=Host(state.get('adb','adb')); host.keep_awake(True)
    role='monitor' if monitor else 'restorer'
    ready = state_path.parent / (role+'.ready')
    try:
        atomic_write(ready, {'pid':os.getpid(),'role':role,'nonce':state['guard_nonce'],'ready_utc':utc_now().isoformat()})
        while True:
            state=json_read(state_path); now=time.time()
            if state.get('guards_ready'):
                arm_path=Path(state.get('arm_path',ARM))
                try:
                    arm=json_read(arm_path); arm_window(arm,require_remaining=False)
                    if arm_digest(arm)!=state['arm_sha256']: raise Refusal('arm changed')
                except Exception:
                    (state_path.parent/'stop').write_text('arm revoked or changed\n',encoding='utf-8')
            if (state_path.parent/'stop').exists() or now>=state['deadline_epoch_s']:
                if not monitor: restore_with_retry(state_path,host)
                return
            if monitor:
                failures=[]
                if host.idle_seconds()<30*60: failures.append('owner_activity')
                if not state.get('owned_runtime') and host.vr_connected(): failures.append('unclaimed_vr_or_vd_session')
                failures.extend(configuration_drift(state))
                if failures:
                    atomic_write(state_path.parent/'monitor.json',{'schema':1,'last_sample_epoch_s':now,
                                'last_action':'end','ended':True,'stop_reasons':failures})
                    (state_path.parent/'stop').write_text('monitor safety stop\n',encoding='utf-8'); return
                b=parse_battery(host.adb_run(state['serial'],'shell','dumpsys','battery')); t=parse_thermal(host.adb_run(state['serial'],'shell','dumpsys','thermalservice'))
                # The monitor owns a separate record. It never rewrites state.json,
                # so it cannot race the deadline restorer's final restoration record.
                monitor_path=state_path.parent/'monitor.json'
                m=json_read(monitor_path) if monitor_path.is_file() else {'schema':1}
                m['last_sample_epoch_s']=now
                action=health_decision({'battery':b['level'],'temperature_c':b['temperature_c'],'thermal_status':t},m,now)
                gpu_sample=host.gpu_sample() if hasattr(host,'gpu_sample') else {'conflicts':host.competing_gpu()}
                gpu_sample=exclude_owned_compute_jobs(state,host,gpu_sample) if hasattr(host,'process_identity') else gpu_sample
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
    except Exception as exc:
        atomic_write(state_path.parent/('worker-error-'+role+'.json'),
                     {'role':role,'at_utc':utc_now().isoformat(),'error':type(exc).__name__})
        (state_path.parent/'stop').write_text(role+' worker failure\n',encoding='utf-8')
        raise
    finally: host.keep_awake(False)

def spawn_worker(state, monitor):
    args=[sys.executable,'-m','tools.quest3.unattended','--worker',str(state),'--monitor' if monitor else '--restorer']
    opts={'creationflags':(getattr(subprocess,'CREATE_NO_WINDOW',0) | getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0) | getattr(subprocess,'DETACHED_PROCESS',0))} if os.name=='nt' else {'start_new_session':True}
    return subprocess.Popen(args,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**opts)

def guard_record_valid(record, role, pid, nonce, minimum_epoch_s=0, now=None):
    try:
        ready=datetime.fromisoformat(record['ready_utc'])
        if ready.tzinfo is None: return False
        timestamp=ready.timestamp(); current=(now or utc_now()).timestamp()
        return (set(record)=={'pid','role','nonce','ready_utc'} and record['pid']==pid
                and record['role']==role and record['nonce']==nonce
                and minimum_epoch_s<=timestamp<=current+1
                and (minimum_epoch_s==0 or timestamp<=minimum_epoch_s+GUARD_READY_SECONDS*2+2))
    except (KeyError, ValueError, TypeError, OverflowError): return False

def wait_for_guard(directory, name, nonce, pid, timeout_s=GUARD_READY_SECONDS, minimum_epoch_s=0):
    marker=Path(directory)/(name+'.ready'); deadline=time.monotonic()+timeout_s
    while time.monotonic()<deadline:
        if marker.is_file():
            try:
                ready=json_read(marker)
                if guard_record_valid(ready,name,pid,nonce,minimum_epoch_s):
                    return True
            except (OSError, ValueError, json.JSONDecodeError): pass
        time.sleep(.05)
    return False

def ownership_matches(record, actual, nonce):
    """Require exact PID, normalized executable path, start time and window nonce."""
    try:
        return (record.get('nonce') == nonce and record.get('pid') == actual.get('pid') and
                Path(record['path']).resolve().as_posix().casefold() == Path(actual['path']).resolve().as_posix().casefold() and
                abs(float(record['started_epoch_s']) - float(actual['started_epoch_s'])) < .001)
    except (KeyError, TypeError, ValueError, OSError): return False

@locked_state_mutation
def record_owned_runtime(state_path, record, host=None):
    """Persist a verified ownership record before any ALVR/SteamVR mutation."""
    state_path=Path(state_path); state=json_read(state_path); host=host or Host(state.get('adb','adb'))
    if ((state_path.parent/'stop').exists() or (state_path.parent/'restoration.lock').exists()
            or time.time()>=state.get('deadline_epoch_s',0)
            or state.get('restoration',{}).get('status') != 'pending'
            or not state.get('guards_ready')): raise Refusal('window not mutable')
    actual=host.process_identity(record.get('pid'))
    if not ownership_matches(record,actual,state.get('guard_nonce')): raise Refusal('runtime ownership cannot be proved')
    owned=state.setdefault('owned_runtime',[])
    if any(item.get('role') == record.get('role') for item in owned): raise Refusal('runtime role already recorded')
    owned.append({key:record[key] for key in ('role','pid','path','started_epoch_s','nonce')})
    atomic_write(state_path,state); return owned[-1]

def _path_get(value, dotted):
    node=value
    for part in dotted.split('.'):
        node=node[part]
    return node

def _path_set(value, dotted, expected):
    parts=dotted.split('.'); node=value
    for part in parts[:-1]: node=node.setdefault(part,{})
    node[parts[-1]]=expected

def _path_delete(value, dotted):
    parts=dotted.split('.'); node=value
    for part in parts[:-1]: node=node.get(part,{})
    node.pop(parts[-1],None)

def restore_configuration_bytes(state, record, *, owned_ok):
    """Restore original bytes after proving all changed keys belong to us."""
    from .preflight import sha256
    source=Path(record['source']); backup=Path(record['snapshot']); digest=record.get('sha256')
    if not digest or not backup.is_file() or sha256(backup)!=digest:
        raise Refusal('configuration backup invalid')
    if source.is_file() and sha256(source)==digest: return 'unchanged'
    if not owned_ok or not state.get('owned_runtime'): raise Refusal('configuration runtime unclaimed or still running')
    kind={'alvr_session':'alvr','steamvr_settings':'steamvr'}.get(record['label'])
    changes=[row for row in state.get('changes',[]) if row.get('kind')==kind]
    if not kind or not changes: raise Refusal('no recorded changes permit a file restore')
    original=json_read(backup); expected=json.loads(json.dumps(original)); current=json_read(source)
    latest={row['key']:row for row in changes}
    for key,row in latest.items():
        present=_path_present(current,key); before=_path_present(original,key)
        value=_path_get(current,key) if present else None
        is_original=present==before and (not present or value==_path_get(original,key))
        is_ours=present and value==row['expected_after']
        if not is_original and not is_ours: raise Refusal('unrecorded configuration drift')
        if present: _path_set(expected,key,value)
    # Mixed original/owned values allow partial setup or an already completed
    # API rollback. No unrelated key or pairing change is accepted.
    if current!=expected: raise Refusal('unrecorded configuration drift')
    observed=source.read_bytes()
    with tempfile.NamedTemporaryFile('wb',dir=source.parent,prefix=source.name+'.q3pw-',delete=False) as stream:
        stream.write(backup.read_bytes()); temporary=Path(stream.name)
    try:
        if source.read_bytes()!=observed: raise Refusal('configuration changed during restoration')
        temporary.replace(source)
    finally: temporary.unlink(missing_ok=True)
    if sha256(source)!=digest: raise Refusal('exact configuration rollback did not match')
    return 'exact_saved_bytes_restored'

def configuration_drift(state):
    """Detect unrecorded settings changes without writing any owner file."""
    from .preflight import sha256, registry_value
    failures=[]
    for record in state['snapshot']['configuration_snapshots']:
        label=record['label']; path=Path(record['source'])
        try:
            if not path.is_file(): failures.append('settings_missing:'+label); continue
            if sha256(path)==record.get('sha256'): continue
            kind={'alvr_session':'alvr','steamvr_settings':'steamvr'}.get(label)
            changes=[row for row in state.get('changes',[]) if row.get('kind')==kind] if kind else []
            if changes:
                expected=json_read(record['snapshot'])
                for row in changes: _path_set(expected,row['key'],row['expected_after'])
                if json_read(path)==expected: continue
            failures.append('settings_drift:'+label)
        except (OSError, ValueError, KeyError, TypeError): failures.append('settings_unreadable:'+label)
    expected=state['snapshot'].get('preflight',{}).get('active_openxr_runtime',{}).get('value')
    if expected:
        actual=registry_value(r'SOFTWARE\Khronos\OpenXR\1','ActiveRuntime')
        if actual.get('error') or actual.get('value')!=expected: failures.append('openxr_runtime_drift')
    manifest=state['snapshot'].get('preflight',{}).get('active_openxr_runtime_manifest',{})
    if manifest.get('sha256'):
        try:
            if sha256(Path(manifest['path']))!=manifest['sha256']: failures.append('openxr_manifest_drift')
        except (OSError,KeyError,TypeError): failures.append('openxr_manifest_unreadable')
    return failures

def mutable_state(state_path, arm_path=ARM):
    """Fail closed before recording or applying a new setting mutation."""
    state_path=Path(state_path); status=status_payload(state_path.parent,arm_path)
    if not status['lease']['active']: raise Refusal('lease is not active: '+','.join(status['lease']['blockers']))
    allowed=status.get('arm',{}).get('allowed_actions',[])
    if not set(allowed).intersection({'chart_cells','decoder_timing'}):
        raise Refusal('arm does not allow device or VR settings changes')
    state=json_read(state_path)
    if (state_path.parent/'restoration.lock').exists() or state.get('restoring') or state.get('restoration',{}).get('status') != 'pending': raise Refusal('rollback has begun')
    if not state.get('owned_runtime'): raise Refusal('claimed runtime ownership required before mutation')
    return state

@locked_state_mutation
def record_change(state_path, kind, key, before_present, before_value, expected_after, arm_path=ARM):
    """Append an immutable exact-key record before applying one owned change."""
    if kind not in {'alvr','steamvr','fork_driver','headset_property'}: raise Refusal('unsupported change kind')
    if kind=='headset_property' and (key not in managed_properties() or
            not (key.startswith('debug.q3pw.') or key in {'debug.oculus.refreshRate','debug.oculus.guardian_pause'})):
        raise Refusal('headset property is not authorized for mutation')
    state=mutable_state(state_path,arm_path); changes=state.setdefault('changes',[])
    if any(row['kind']==kind and row['key']==key for row in changes): raise Refusal('change already recorded')
    row={'kind':kind,'key':key,'before_present':bool(before_present),'before_value':before_value,
         'expected_after':expected_after,'recorded_utc':utc_now().isoformat()}
    changes.append(row); atomic_write(state_path,state); return row

@locked_state_mutation
def apply_alvr_changes(state_path, values, arm_path=ARM, api=None):
    """Read/record exact ALVR paths before setting them, then require readback."""
    state=mutable_state(state_path,arm_path)
    if api is None:
        from .control import session, set_values
        api=(session,set_values)
    session,set_values=api; before=session()
    rows=[]
    for key, expected in values.items():
        try: old=_path_get(before,key); present=True
        except (KeyError, TypeError): old=None; present=False
        rows.append(record_change(state_path,'alvr',key,present,old,expected,arm_path))
    set_values(values); after=session()
    if any(_path_get(after,key) != expected for key,expected in values.items()): raise Refusal('ALVR setting readback differs')
    return rows

def restore_recorded_alvr(state, api):
    """Restore only exact prior ALVR paths through the live owning API."""
    session,set_values=api; values={}; current=session()
    for row in state.get('changes',[]):
        if row['kind']=='alvr':
            validate_rollback_key(current,row)
            if row['before_present']: values[row['key']]=row['before_value']
    if values:
        set_values(values); after=session()
        if any(_path_get(after,key) != value for key,value in values.items()): raise Refusal('ALVR rollback readback differs')
    return bool(values)

def _path_present(value, dotted):
    try: _path_get(value,dotted); return True
    except (KeyError, TypeError): return False

def validate_rollback_key(current,row):
    present=_path_present(current,row['key'])
    value=_path_get(current,row['key']) if present else None
    original=present==row['before_present'] and (not present or value==row['before_value'])
    ours=present and value==row['expected_after']
    if not original and not ours: raise Refusal('unrecorded configuration drift')

@locked_state_mutation
def apply_steamvr_changes(state_path, settings_path, values, arm_path=ARM):
    """Record presence/value, then change exact SteamVR JSON keys while owned runtime is live."""
    state=mutable_state(state_path,arm_path); path=Path(settings_path)
    recorded=next((row for row in state['snapshot']['configuration_snapshots'] if row.get('label')=='steamvr_settings'),None)
    if not recorded or Path(recorded['source']).resolve()!=path.resolve(): raise Refusal('SteamVR path is not the saved configuration')
    current=json_read(path)
    rows=[]
    for key, expected in values.items():
        present=_path_present(current,key); old=_path_get(current,key) if present else None
        rows.append(record_change(state_path,'steamvr',key,present,old,expected,arm_path))
        _path_set(current,key,expected)
    atomic_write(path,current)
    actual=json_read(path)
    if any(_path_get(actual,key)!=expected for key,expected in values.items()): raise Refusal('SteamVR setting readback differs')
    return rows

def restore_recorded_steamvr(state):
    rows=[row for row in state.get('changes',[]) if row.get('kind')=='steamvr']
    if not rows: return True
    record=next((row for row in state['snapshot']['configuration_snapshots'] if row.get('label')=='steamvr_settings'),None)
    if not record or not record.get('source'): raise Refusal('SteamVR settings source not recorded')
    path=Path(record['source']); current=json_read(path)
    for row in rows: validate_rollback_key(current,row)
    observed=path.read_bytes()
    for row in rows:
        if row['before_present']: _path_set(current,row['key'],row['before_value'])
        else: _path_delete(current,row['key'])
    if path.read_bytes()!=observed: raise Refusal('configuration changed during restoration')
    atomic_write(path,current); actual=json_read(path)
    return all((_path_present(actual,row['key']) == row['before_present'] and
                (not row['before_present'] or _path_get(actual,row['key']) == row['before_value'])) for row in rows)

def driver_membership(vrpaths, fork_driver):
    values=json_read(vrpaths).get('external_drivers',[])
    needle=Path(fork_driver).resolve().as_posix().casefold()
    return any(Path(item).resolve().as_posix().casefold()==needle for item in values), values

@locked_state_mutation
def record_driver_change(state_path, vrpaths, fork_driver, expected_present, arm_path=ARM):
    present, all_before=driver_membership(vrpaths,fork_driver)
    row=record_change(state_path,'fork_driver',str(Path(fork_driver).resolve()),present,all_before,bool(expected_present),arm_path)
    return row

def restore_recorded_driver(state, vrpathreg):
    rows=[row for row in state.get('changes',[]) if row.get('kind')=='fork_driver']
    if not rows:return True
    record=next((row for row in state['snapshot']['configuration_snapshots'] if row.get('label')=='openvr_paths'),None)
    if not record or not record.get('source'): raise Refusal('OpenVR driver inventory unavailable')
    for row in rows:
        present,_=driver_membership(record['source'],row['key'])
        if present != row['before_present']:
            command='adddriver' if row['before_present'] else 'removedriver'
            subprocess.run([str(vrpathreg),command,row['key']],check=True,capture_output=True,timeout=20)
    _,current=driver_membership(record['source'],rows[0]['key'])
    wanted=rows[0]['before_value']
    norm=lambda values:sorted(Path(x).resolve().as_posix().casefold() for x in values)
    return norm(current)==norm(wanted)

@locked_state_mutation
def register_owned_pc_job(state_path, pid, path, started_epoch_s, arm_path=ARM, host=None):
    """Register only this window's offline encoder/decoder/scorer child."""
    state_path=Path(state_path); status=status_payload(state_path.parent,arm_path,require_allow='frame_bank_pc')
    if not status['lease']['active']: raise Refusal('PC job lease invalid: '+','.join(status['lease']['blockers']))
    state=json_read(state_path); host=host or Host(state.get('adb','adb'))
    record={'role':'pc_job','pid':pid,'path':path,'started_epoch_s':started_epoch_s,'nonce':state['guard_nonce']}
    actual=host.process_identity(pid)
    if not ownership_matches(record,actual,state['guard_nonce']): raise Refusal('PC job identity cannot be proved')
    jobs=state.setdefault('owned_pc_jobs',[])
    if any(row['pid']==pid for row in jobs): raise Refusal('PC job already registered')
    jobs.append(record); atomic_write(state_path,state); return record

@locked_state_mutation
def unregister_owned_pc_job(state_path, pid, host=None):
    state_path=Path(state_path); state=json_read(state_path)
    if ((state_path.parent/'stop').exists() or (state_path.parent/'restoration.lock').exists()
            or state.get('restoration',{}).get('status') != 'pending'): return None
    jobs=state.get('owned_pc_jobs',[])
    record=next((row for row in jobs if row['pid']==pid),None)
    if not record: raise Refusal('PC job not registered')
    host=host or Host(state.get('adb','adb'))
    try:
        if ownership_matches(record,host.process_identity(pid),state['guard_nonce']): jobs.remove(record)
        else: raise Refusal('PC job identity changed')
    except Refusal:
        if not pid_alive(pid): jobs.remove(record)
        else: raise
    atomic_write(state_path,state); return record

def exclude_owned_compute_jobs(state, host, sample):
    """Exclude only live jobs whose PID/path/start/nonce still exactly match."""
    owned=[]
    for record in state.get('owned_pc_jobs',[]):
        try:
            if ownership_matches(record,host.process_identity(record['pid']),state.get('guard_nonce')): owned.append(str(record['pid']))
        except Exception: pass
    kept=[]
    for row in sample.get('conflicts',[]):
        pid=row.split(',',1)[0].strip()
        if pid not in owned: kept.append(row)
    result=dict(sample); result['conflicts']=kept; result['excluded_owned_pids']=owned; return result

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
            arm_value=json_read(arm_path); approved_window=arm_window(arm_value,now,require_remaining=False); arm['active']=True
            arm['duration_authorization']=approved_window['duration_authorization']
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
            ready=guard_record_valid(record,role,pid,state.get('guard_nonce'),
                                     state.get('guard_started_epoch_s',0),now)
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
    if monitor.get('ended') or monitor.get('stop_reasons'): blockers.append('monitor_safety_stop')
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
        x=sub.add_parser(name); x.add_argument('--arm',type=Path,default=ARM); x.add_argument('--window',type=Path); x.add_argument('--require-allow'); x.add_argument('--adb',default='adb'); x.add_argument('--alvr-session',type=Path)
    claim=sub.add_parser('claim-runtime'); claim.add_argument('--window',type=Path,required=True); claim.add_argument('--role',choices=('dashboard','steamvr'),required=True); claim.add_argument('--pid',type=int,required=True); claim.add_argument('--path',required=True); claim.add_argument('--started-epoch-s',type=float,required=True)
    p.add_argument('--worker',type=Path,help=argparse.SUPPRESS); p.add_argument('--monitor',action='store_true',help=argparse.SUPPRESS); p.add_argument('--restorer',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    if args.worker: worker(args.worker,args.monitor); return
    if args.cmd=='arm':
        if not args.owner_confirm: p.error('owner-only: pass --owner-confirm after reviewing the arm file')
        arm=json_read(args.file); validate_arm_definition(arm); PRIVATE.mkdir(parents=True,exist_ok=True)
        if ARM.exists(): p.error('refusing to overwrite existing owner arm file')
        shutil.copyfile(args.file,ARM); print(json.dumps({'armed':str(ARM)})); return
    if args.cmd=='claim-runtime':
        state_path=Path(args.window)/'state.json'
        if not state_path.is_file(): p.error('window state missing')
        state=json_read(state_path)
        record={'role':args.role,'pid':args.pid,'path':args.path,'started_epoch_s':args.started_epoch_s,'nonce':state.get('guard_nonce')}
        try: print(json.dumps(record_owned_runtime(state_path,record),indent=2))
        except Refusal as exc: p.error(str(exc))
        return
    if not args.window: p.error('--window is required')
    directory=Path(args.window)
    state_path=directory/'state.json'
    # Emergency status/stop/restore remain available after expiry or owner arm
    # revocation. Only starting or checking a window requires an active arm.
    if args.cmd in {'check','start'}:
        if not args.arm.is_file(): p.error('arm file missing')
        arm,window=load_arm(args.arm)
    if args.cmd=='check': print(json.dumps(check_preconditions(arm,Host(args.adb),directory,alvr_session_path=args.alvr_session),indent=2)); return
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
            source_ok=all(x.get('error') is None and x.get('backup_valid') is not False and x.get('current_matches') is True
                          for x in verify_snapshot(check['snapshot']['configuration_snapshots']))
            source_ok=source_ok and not configuration_drift({'snapshot':check['snapshot']})
        except (KeyError, OSError, ValueError): source_ok=False
        if not source_ok: p.error('refusing start: source settings changed after snapshot')
        live_failures, _, _ = live_preconditions(arm,Host(check.get('adb',args.adb)))
        if live_failures: p.error('refusing start: preconditions changed: '+','.join(live_failures))
        if state_path.exists() or (directory/'stop').exists() or (directory/'pause').exists():
            p.error('refusing start: window already has state or a cancellation marker')
        # Ready records are generated by fresh workers and bound to a nonce/PID.
        for name in ('restorer.ready','monitor.ready','monitor.json'):
            (directory/name).unlink(missing_ok=True)
        nonce=uuid.uuid4().hex
        state={'schema':1,'window_id':directory.name,'serial':arm['headset_serial'],'adb':check.get('adb',args.adb),'deadline_epoch_s':window['deadline'].timestamp(),'snapshot':check['snapshot'],'restoration':{'status':'pending'},'guards_ready':False,'guard_pids':{},'guard_nonce':nonce,'guard_started_epoch_s':utc_now().timestamp(),'arm_path':str(args.arm.resolve()),'arm_sha256':arm_digest(arm)}
        state['allowed_actions']=list(arm.get('allow',[]))
        atomic_write(state_path,state)
        r=spawn_worker(state_path,False)
        if not wait_for_guard(directory,'restorer',nonce,r.pid,minimum_epoch_s=state['guard_started_epoch_s']) or not pid_alive(r.pid):
            (directory/'stop').write_text('restorer failed readiness\n',encoding='utf-8')
            p.error('refusing start: deadline restorer did not become ready')
        state=json_read(state_path); state['guard_pids']['restorer']=r.pid; atomic_write(state_path,state)
        m=spawn_worker(state_path,True)
        if not wait_for_guard(directory,'monitor',nonce,m.pid,minimum_epoch_s=state['guard_started_epoch_s']) or not pid_alive(m.pid):
            (directory/'stop').write_text('monitor failed readiness\n',encoding='utf-8')
            p.error('refusing start: thermal monitor did not become ready')
        state=json_read(state_path); state['guard_pids']['monitor']=m.pid; state['guards_ready']=True; atomic_write(state_path,state)
        print(json.dumps({'window':str(directory),'restorer_pid':r.pid,'monitor_pid':m.pid})); return
    if not state_path.is_file(): p.error('window state missing')
    if args.cmd=='status': print(json.dumps(status_payload(directory,args.arm,require_allow=args.require_allow),indent=2)); return
    if args.cmd=='stop': (Path(directory)/'stop').write_text('requested\n'); print(json.dumps({'stop_marker':str(Path(directory)/'stop')})); return
    if args.cmd=='restore': print(json.dumps(restore(state_path),indent=2)); return
if __name__=='__main__': main()

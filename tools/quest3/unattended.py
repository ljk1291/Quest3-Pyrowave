"""Fail-closed supervisor for owner-armed Quest 3 unattended windows.

No hardware action is taken by importing this module. The CLI's ``arm`` command is
an owner-only convenience: it requires an explicit acknowledgement and is never
called by automation. All device commands include the serial stored in the arm.
"""
from __future__ import annotations
import argparse, ctypes, json, os, shutil, subprocess, sys, time
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
MANAGED_PROPERTIES = (
    'debug.q3pw.codec', 'debug.q3pw.transport', 'debug.q3pw.bitrate_mbps',
    'debug.q3pw.render_width', 'debug.q3pw.render_height',
    'debug.q3pw.encoded_width', 'debug.q3pw.encoded_height',
    'debug.q3pw.refresh_hz', 'debug.q3pw.foveation', 'debug.q3pw.adaptive_bitrate',
    'debug.q3pw.reprojection', 'debug.q3pw.decoder_experiment',
    'debug.oculus.refreshRate', 'debug.oculus.guardian_pause',
)
GUARD_READY_SECONDS = 5

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
    def competing_gpu(self):
        # Deliberately conservative. The owner can replace this check in a future integration.
        names=('ComfyUI','python.exe','blender.exe'); running=[]
        if os.name=='nt':
            out=self.run('tasklist','/FO','CSV','/NH',timeout=10).lower()
            running=[n for n in names if n.lower() in out]
        return running
    def vr_connected(self):
        if os.name!='nt': return False
        out=self.run('tasklist','/FO','CSV','/NH',timeout=10).lower()
        # Any existing VR session is owner work. A test scene is only started after
        # this gate and therefore cannot be mistaken for an idle machine.
        return any(x in out for x in ('vrserver.exe','vrcompositor.exe','vrmonitor.exe',
                                      'steamvr.exe','virtualdesktop.streamer.exe','alvr_server.exe'))
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
            'charging': data.get('ac powered','false')=='true' or data.get('usb powered','false')=='true' or data.get('status')=='2'}
def parse_thermal(text):
    import re
    m=re.search(r'Thermal Status:\s*(\d+)',text)
    return int(m.group(1)) if m else None

def snapshot(host, serial, directory):
    """Capture only private evidence before settings change. Any read failure rejects the window."""
    directory=Path(directory); before=directory/'before'; before.mkdir(parents=True,exist_ok=False)
    from . import preflight
    inv,sources=preflight.inventory(); records=preflight.snapshot_files(sources,before/'configurations')
    if any(r.get('error') or not r.get('exists') for r in records): raise Refusal('incomplete PC/VD settings snapshot')
    # Android getprop has no glob form. Preserve the exact old values of every
    # property this supervisor can restore; an absent value is explicitly saved.
    all_props=host.adb_run(serial,'shell','getprop')
    props={'all_filtered':[line for line in all_props.splitlines() if 'debug.q3pw.' in line or 'debug.oculus.' in line],
           'managed':{key: host.adb_run(serial,'shell','getprop',key) for key in MANAGED_PROPERTIES}}
    data={'schema':1,'created_utc':utc_now().isoformat(),'preflight':inv,'configuration_snapshots':records,'headset_properties':props}
    atomic_write(before/'snapshot.json',data); return data

def check_preconditions(arm, host, directory, now=None):
    window=arm_window(arm,now); serial=arm['headset_serial']; failures=[]
    devices=host.adb_devices()
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
    report={'schema':1,'checked_utc':utc_now().isoformat(),'window':{'deadline_utc':window['deadline'].isoformat(),'remaining_s':window['remaining_s']},'serial':serial,'failures':failures,'battery':battery,'thermal_status':thermal,'passed':not failures}
    if not failures:
        try: report['snapshot']=snapshot(host,serial,directory)
        except Exception as exc: report['failures'].append('snapshot_incomplete:'+str(exc)); report['passed']=False
    atomic_write(Path(directory)/'check.json',report); return report

def restore(state_path, host=None):
    """Idempotent deadline-safe fallback with an offline file-copy fallback."""
    state_path=Path(state_path); state=json_read(state_path)
    if state.get('restoration',{}).get('status')=='restored': return state['restoration']
    host=host or Host(state.get('adb','adb')); serial=state['serial']; steps=[]
    try:
        host.adb_run(serial,'shell','am','force-stop','io.github.ljk1291.quest3pyrowave'); steps.append('fork_client_stopped')
    except Exception as exc: steps.append('fork_client_stop_failed:'+str(exc))
    awake_state = state_path.parent / 'awake.json'
    if awake_state.is_file():
        try:
            awake=json_read(awake_state)
            if awake.get('device') != serial: raise Refusal('awake state serial mismatch')
            from .awake import restore as restore_awake
            restore_awake(awake_state); steps.append('physical_proximity_restored')
        except Exception as exc:
            steps.append('physical_proximity_restore_failed:'+str(exc))
    # Restore each managed property, including the empty value which represents
    # an absent pre-window override. Never replay arbitrary getprop output.
    properties=state['snapshot']['headset_properties']
    for key, value in properties.get('managed', {}).items():
        if key in MANAGED_PROPERTIES:
            try: host.adb_run(serial,'shell','setprop',key,value); steps.append('prop:'+key)
            except Exception as exc: steps.append('prop_failed:'+key+':'+str(exc))
    if not properties.get('managed'):
        # Compatibility with early snapshots: only replay safe, explicit keys.
        import re
        for line in properties.get('all_filtered',[]):
            m=re.match(r'\[([^]]+)\]: \[([^]]*)\]',line)
            if m and m.group(1) in MANAGED_PROPERTIES:
                try: host.adb_run(serial,'shell','setprop',m.group(1),m.group(2)); steps.append('prop:'+m.group(1))
                except Exception as exc: steps.append('prop_failed:'+m.group(1)+':'+str(exc))
    # Restore OpenXR registration directly when the owning selector/API is unavailable.
    runtime = state['snapshot'].get('preflight',{}).get('active_openxr_runtime', {}).get('value')
    runtime_restored = runtime is None
    if runtime and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Khronos\OpenXR\1', 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, 'ActiveRuntime', 0, winreg.REG_SZ, runtime)
            runtime_restored = True; steps.append('openxr_runtime')
        except OSError as exc: steps.append('openxr_runtime_failed:'+str(exc))
    # API-independent fallback: copies saved settings back exactly, then hashes with preflight.
    for record in state['snapshot']['configuration_snapshots']:
        if record.get('exists') and record.get('snapshot'):
            try: shutil.copyfile(record['snapshot'],record['source']); steps.append('file:'+record['label'])
            except OSError as exc: steps.append('file_failed:'+record['label']+':'+str(exc))
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
    ok=files_ok and runtime_restored and properties_ok
    state['restoration']={'status':'restored' if ok else 'restore_failed','at_utc':utc_now().isoformat(),'steps':steps,'fallback':'saved_configuration_files_when_control_api_is_unavailable','vd_hashes_match':files_ok,'openxr_runtime_restored':runtime_restored,'property_readback':property_readback,'properties_restored':properties_ok,'verification':verification}
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
    if state.get('paused') and now-state['paused_at']>=15*60 and sample.get('temperature_c',99)<=40:
        state['paused']=False; return 'resume'
    return 'paused' if state.get('paused') else 'run'

def worker(state_path, monitor=False):
    state_path=Path(state_path); host=Host(); state=json_read(state_path); host.keep_awake(True)
    ready = state_path.parent / ('monitor.ready' if monitor else 'restorer.ready')
    try:
        atomic_write(ready, {'pid':os.getpid(),'role':'monitor' if monitor else 'restorer','ready_utc':utc_now().isoformat()})
        while True:
            state=json_read(state_path); now=time.time()
            if (state_path.parent/'stop').exists() or now>=state['deadline_epoch_s']:
                restore(state_path,host); return
            if monitor:
                b=parse_battery(host.adb_run(state['serial'],'shell','dumpsys','battery')); t=parse_thermal(host.adb_run(state['serial'],'shell','dumpsys','thermalservice'))
                # The monitor owns a separate record. It never rewrites state.json,
                # so it cannot race the deadline restorer's final restoration record.
                monitor_path=state_path.parent/'monitor.json'
                m=json_read(monitor_path) if monitor_path.is_file() else {'schema':1}
                m['last_sample_epoch_s']=now
                action=health_decision({'battery':b['level'],'temperature_c':b['temperature_c'],'thermal_status':t},m,now)
                workload=host.competing_gpu(); m['competing_gpu']=workload
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
            time.sleep(POLL_SECONDS)
    finally: host.keep_awake(False)

def spawn_worker(state, monitor):
    args=[sys.executable,'-m','tools.quest3.unattended','--worker',str(state),'--monitor' if monitor else '--restorer']
    opts={'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)} if os.name=='nt' else {'start_new_session':True}
    return subprocess.Popen(args,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**opts)

def wait_for_guard(directory, name, timeout_s=GUARD_READY_SECONDS):
    marker=Path(directory)/(name+'.ready'); deadline=time.monotonic()+timeout_s
    while time.monotonic()<deadline:
        if marker.is_file(): return True
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
    arm={'present':Path(arm_path).is_file(),'active':False,'reason':None}
    if arm['present']:
        try:
            arm_value=json_read(arm_path); arm_window(arm_value,now); arm['active']=True
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
        pid=guard_pids.get(role); guards[role]={'ready':(directory/(role+'.ready')).is_file(),'pid':pid,'alive':pid_alive(pid)}
    monitor_path=directory/'monitor.json'
    monitor=json_read(monitor_path) if monitor_path.is_file() else state.get('monitor',{})
    sample=monitor.get('last_sample_epoch_s')
    sample_fresh=isinstance(sample,(int,float)) and now.timestamp()-sample <= POLL_SECONDS*2+5
    restored=state.get('restoration',{}).get('status') != 'pending'
    blockers=[]
    if not arm['active']: blockers.append('arm_inactive')
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
        if not check or not check.get('passed'): p.error('refusing start: successful check and snapshot required')
        state={'schema':1,'window_id':directory.name,'serial':arm['headset_serial'],'adb':'adb','deadline_epoch_s':window['deadline'].timestamp(),'snapshot':check['snapshot'],'restoration':{'status':'pending'},'guards_ready':False,'guard_pids':{}}
        atomic_write(state_path,state)
        r=spawn_worker(state_path,False)
        if not wait_for_guard(directory,'restorer'):
            (directory/'stop').write_text('restorer failed readiness\n',encoding='utf-8')
            p.error('refusing start: deadline restorer did not become ready')
        state=json_read(state_path); state['guard_pids']['restorer']=r.pid; atomic_write(state_path,state)
        m=spawn_worker(state_path,True)
        if not wait_for_guard(directory,'monitor'):
            (directory/'stop').write_text('monitor failed readiness\n',encoding='utf-8')
            p.error('refusing start: thermal monitor did not become ready')
        state=json_read(state_path); state['guard_pids']['monitor']=m.pid; state['guards_ready']=True; atomic_write(state_path,state)
        print(json.dumps({'window':str(directory),'restorer_pid':r.pid,'monitor_pid':m.pid})); return
    if not state_path.is_file(): p.error('window state missing')
    if args.cmd=='status': print(json.dumps(status_payload(directory,args.arm,require_allow=args.require_allow),indent=2)); return
    if args.cmd=='stop': (Path(directory)/'stop').write_text('requested\n'); print(json.dumps({'stop_marker':str(Path(directory)/'stop')})); return
    if args.cmd=='restore': print(json.dumps(restore(state_path),indent=2)); return
if __name__=='__main__': main()

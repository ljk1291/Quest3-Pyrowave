"""Separate quality safety from timing validity; utilization is not quality.

Timing load uses unrelated per-process engine counters, never overall GPU load.
Overall utilization and VRAM are retained as context. Device/query errors and a
2 GiB free-VRAM margin are safety stops in either mode.
"""
import math
import re
import shutil

VRAM_MARGIN_MIB=2048
BACKENDS=re.compile(r'(?:python(?:w)?\.exe|ollama|llama|vllm|kobold|lm[ _-]?studio|blender|octane|redshift|tensorrt|tritonserver|automatic1111|forge|invokeai)',re.I)

def telemetry(host):
    executable=shutil.which('nvidia-smi') or shutil.which('nvidia-smi.exe')
    if not executable: return {'device_error':'gpu_driver_query_unavailable'}
    try:
        text=host.run(executable,'--query-gpu=memory.free,memory.total,utilization.gpu','--format=csv,noheader,nounits',timeout=5)
        free,total,load=map(float,text.splitlines()[0].split(','))
        if not all(math.isfinite(v) for v in (free,total,load)) or not 0<=free<=total or not 0<=load<=100:
            raise ValueError('invalid telemetry')
        return {'free_vram_mib':free,'total_vram_mib':total,'overall_load_percent':load,'device_error':None}
    except Exception: return {'device_error':'gpu_driver_query_failed'}

def evaluate(sample,*,mode,now,above_since=None,margin_mib=VRAM_MARGIN_MIB):
    if mode not in ('quality','timing'): raise ValueError('unknown contention mode')
    owned=set(sample.get('excluded_owned_pids',[]))
    activity=sample.get('gpu_engine_activity') or {}
    active={pid:row for pid,row in activity.get('active_pids',{}).items() if str(pid) not in owned}
    backends=[]
    comfy=sample.get('comfy',{})
    if sample.get('comfy_processes') and (comfy.get('known') is not True or comfy.get('running') or comfy.get('pending')):
        backends.append('comfy_queue_active_or_unknown')
    for app in sample.get('nvidia_compute_apps',[]):
        fields=app.split(',',2)
        if len(fields)<2 or fields[0].strip() in owned: continue
        pid,name=fields[0].strip(),fields[1].strip()
        # Idle resident Python/LLM contexts are accounted for by VRAM; active
        # engines plus backend identity constitute competing compute evidence.
        if BACKENDS.search(name) and (pid in active or activity.get('known') is not True):
            backends.append('compute_backend_active_or_unknown')
    gpu=sample.get('gpu_telemetry',{})
    stop=[]
    if gpu.get('device_error') or not isinstance(gpu.get('free_vram_mib'),(int,float)):
        stop.append('gpu_driver_or_device_error')
    elif not math.isfinite(gpu['free_vram_mib']) or gpu['free_vram_mib']<margin_mib:
        stop.append('free_vram_below_margin')
    if sample.get('stop_requested'): stop.append('stop_requested')
    maximum=max((row.get('max_percent',0) for row in active.values()),default=0)
    if activity.get('known') is True and maximum>10:
        above_since=now if above_since is None else above_since
    else: above_since=None
    timing=[]
    if mode=='quality': stop+=backends
    else:
        timing+=backends
        if activity.get('known') is not True: timing.append('timing_activity_unknown')
        if above_since is not None and now-above_since>=10: timing.append('sustained_external_gpu_load')
    return {'mode':mode,'stop_reasons':list(dict.fromkeys(stop)),
            'timing_invalidation_reasons':list(dict.fromkeys(timing)),
            'above_since_epoch_s':above_since,'external_max_engine_percent':maximum,
            'compute_backend_reasons':list(dict.fromkeys(backends)),
            'free_vram_margin_mib':margin_mib}

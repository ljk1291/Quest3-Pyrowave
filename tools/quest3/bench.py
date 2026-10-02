"""python -m tools.quest3.bench: capability-gated plans, captures and summaries."""
import argparse
import json
import math
import random
import re
import subprocess
import time
import threading
import uuid
from pathlib import Path
from .baseline import baseline_plan, acceptance

RATES = (72, 90, 120, 144, 207, 240)
BITRATES = (400, 600, 800, 1000, 1500, 2000)
SUSTAINED_RATE_WINDOW_SECONDS = 300
ENDURANCE_WINDOW_SECONDS = 300
SELECTED_OUTPUT_SOURCE = 'selected_nonnull_post_render_release_v1'
EXPERIMENT_PROPERTIES = (
    'debug.q3pw.direct_eye_copy', 'debug.q3pw.async_eye_copy', 'debug.q3pw.copy_wait_us',
    'debug.q3pw.raw_srgb_copy', 'debug.q3pw.image_cache', 'debug.q3pw.frame_wait_us',
    'debug.q3pw.pre_wait_poll', 'debug.q3pw.repeat_render', 'debug.q3pw.decode_workers',
    'debug.q3pw.decode_handoff', 'debug.q3pw.direct_flip_y',
    'debug.oculus.forceDisplayScaling', 'debug.oculus.refreshRate',
    'debug.q3pw.haar_fused','debug.q3pw.dequant_batch','debug.q3pw.convert_compute',
    'debug.q3pw.fragment_min_usage','debug.q3pw.optimal_ahb_usage','debug.q3pw.loop_probe',
    'debug.q3pw.runtime_display_time','debug.q3pw.pass_profile','debug.q3pw.hide_performance_overlay',
    'debug.q3pw.layer_filter',
    'debug.xrwired.pyro_precision','debug.xrwired.early_poll',
    'debug.xrwired.perf_level',
)


def measurement_clock():
    """Return the high-resolution, monotonic capture clock.

    On Windows ``monotonic`` can be backed by GetTickCount64 (15.625 ms on
    this host), which is too coarse to timestamp 72 Hz GraphStatistics
    arrivals. ``perf_counter`` uses QueryPerformanceCounter there.
    """
    return time.perf_counter()


def measurement_clock_info():
    info = time.get_clock_info('perf_counter')
    return {
        'name': 'perf_counter',
        'implementation': info.implementation,
        'monotonic': info.monotonic,
        'adjustable': info.adjustable,
        'resolution_s': info.resolution,
    }

def supported(requested, rates):
    return any(math.isfinite(r) and r > 0 and abs(r - requested) < .01 for r in rates)

def parse_capabilities(log):
    matches = list(re.finditer(r'\[Q3PW_CAPS\] model=(\S+) rates=\[([^]]*)\] runtime=(true|false)(?: source=(\w+))?', log))
    if not matches:
        raise ValueError('No Quest3-Pyrowave runtime capability log. Launch the built APK first.')
    model, values, runtime, source = matches[-1].groups()
    rates = [float(v.strip()) for v in values.split(',') if v.strip()]
    begin = matches[-2].end() if len(matches)>1 else 0
    probes = [{'requested_hz':float(hz), 'confirmed':ok=='true'} for hz,ok in
        re.findall(r'\[Q3PW_PROBE\] request=([0-9.]+) confirmed=(true|false)', log[begin:matches[-1].start()])]
    return {'model':model, 'rates_hz':sorted(set(r for r in rates if math.isfinite(r) and r>0)),
            'refresh_extension':runtime=='true', 'source':'request_and_frame_period' if source=='probe' else 'enumeration',
            'probe_results':probes}


def plan(caps, repeats=3, seed=1717, seconds=15):
    if not caps.get('refresh_extension'):
        raise ValueError('Refresh extension not advertised; a fallback rate is not a measured capability.')
    cells = []
    skipped = []
    for hz in RATES:
        if not supported(hz, caps['rates_hz']):
            skipped.append({'requested_hz':hz, 'status':'not_confirmed',
                'reason':('startup probe did not confirm this mode' if caps.get('source')=='request_and_frame_period'
                    else 'enumeration alone is incomplete; launch current APK for request/frame-period probing'),
                'requires_display_scaling':hz>207})
            continue
        for mbps in BITRATES:
            for path in ('Compute', 'Fragment'):
                for rep in range(repeats):
                    cells.append({'id': f'pyro-{hz}-{mbps}-{path.lower()}-r{rep+1}',
                        'codec': 'PyroWave', 'requested_hz': hz, 'mbps': mbps,
                        'decode_path': path, 'wavelet': 'Cdf97', 'chroma': '420', 'transport': 'Tcp', 'replicate': rep+1,
                        'seconds': seconds, 'status': 'planned', 'frame_budget_ms': 1000/hz,
                        'budget_bytes_per_frame': mbps*1e6/8/hz})
        for codec in ('H264', 'Hevc', 'AV1'):
            for rep in range(repeats):
                cells.append({'id': f'{codec.lower()}-{hz}-200-r{rep+1}', 'codec': codec,
                    'requested_hz': hz, 'mbps': 200, 'replicate': rep+1, 'seconds': seconds,
                    'status': 'planned', 'decode_path': None})
    random.Random(seed).shuffle(cells)
    return {'schema_version': 1, 'capabilities': caps, 'seed': seed, 'cells': cells, 'skipped': skipped,
            'method': 'Quick screening with interleaved repetitions; same scene and resolution; cool between cells. Longer explicit runs are required for sustained and thermal acceptance.'}

def distribution(values):
    v = sorted(float(x) for x in values if x is not None and math.isfinite(float(x)))
    if not v: return None
    def percentile(p):
        i = (len(v)-1)*p; lo=int(i); hi=min(lo+1,len(v)-1)
        return v[lo]+(v[hi]-v[lo])*(i-lo)
    return {'n':len(v), 'p01':percentile(.01), 'p50':percentile(.5),
            'p95':percentile(.95), 'p99':percentile(.99), 'max':v[-1]}

PYROWAVE_COUNTERS = (
    'complete', 'partial', 'skipped', 'dropped', 'superseded', 'stale_packets',
    'decode_failures', 'direct_eye_copies', 'staging_eye_copies',
    'completed_eye_copies', 'pending_eye_copy_deferrals',
)


def pyrowave_counter_window(samples):
    """Use the same endpoints for every producer/consumer counter and rate.

    Missing or reset counters remain unknown. An invalid/non-increasing timestamp
    anywhere in this window invalidates every rate, without hiding counter deltas.
    These counters do not measure unique optical presentations.
    """
    deltas={}
    for field in PYROWAVE_COUNTERS:
        values=[data.get(field) for _,data in samples]
        valid=len(values)>1 and all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for v in values)
        monotonic=valid and all(b>=a for a,b in zip(values,values[1:]))
        deltas[field]=values[-1]-values[0] if monotonic else None
    times=[elapsed for elapsed,_ in samples]
    valid_times=len(times)>1 and all(isinstance(t,(int,float)) and not isinstance(t,bool)
        and math.isfinite(t) and t>=0 for t in times)
    increasing=valid_times and all(b>a for a,b in zip(times,times[1:]))
    span=times[-1]-times[0] if increasing else None
    return {'samples':len(samples), 'interval_s':span, 'counter_deltas':deltas,
        'counter_rates_per_s':{name:delta/span if span is not None and delta is not None else None
            for name,delta in deltas.items()},
            'definition':'Matching HeadsetTelemetry endpoints. Complete is producer decode completion; superseded includes pending replacement and out-of-order publication. Eye completion can include configuration redraws; staging completion is unobserved. Not unique or optical display FPS.'}

def selected_output_window(samples, max_gap_s=15, capture_end_elapsed=None):
    """Validate the native monotonic, post-render selected-output counter."""
    if len(samples) < 2:
        return {'valid':False,'reason':'selected_output_samples_missing','samples':len(samples)}
    times=[]; counts=[]
    for elapsed, count, source in samples:
        if (not isinstance(elapsed,(int,float)) or isinstance(elapsed,bool) or not math.isfinite(elapsed) or elapsed < 0
                or not isinstance(count,int) or isinstance(count,bool) or count < 0):
            return {'valid':False,'reason':'selected_output_counter_invalid','samples':len(samples)}
        if source != SELECTED_OUTPUT_SOURCE:
            return {'valid':False,'reason':'selected_output_source_unverified','samples':len(samples)}
        times.append(elapsed); counts.append(count)
    if any(b<=a for a,b in zip(times,times[1:])):
        return {'valid':False,'reason':'selected_output_time_invalid','samples':len(samples)}
    if any(b<a for a,b in zip(counts,counts[1:])):
        return {'valid':False,'reason':'selected_output_counter_reset','samples':len(samples)}
    span=times[-1]-times[0]; delta=counts[-1]-counts[0]; gap=max(b-a for a,b in zip(times,times[1:]))
    if gap>max_gap_s:
        return {'valid':False,'reason':'selected_output_coverage_gap','samples':len(samples),'max_gap_s':gap}
    if span<=0 or delta<=0:
        return {'valid':False,'reason':'selected_output_no_fresh_frames','samples':len(samples),'interval_s':span,'counter_delta':delta}
    result={'valid':True,'source':SELECTED_OUTPUT_SOURCE,'samples':len(samples),'interval_s':span,
            'counter_delta':delta,'rate_fps':delta/span,'max_gap_s':gap,
            'first_elapsed_s':times[0],'last_elapsed_s':times[-1]}
    if capture_end_elapsed is not None:
        if (not isinstance(capture_end_elapsed,(int,float)) or isinstance(capture_end_elapsed,bool)
                or not math.isfinite(capture_end_elapsed) or capture_end_elapsed < times[-1]):
            return dict(result,valid=False,reason='selected_output_capture_bounds_invalid')
        result['start_gap_s']=times[0]
        result['end_gap_s']=capture_end_elapsed-times[-1]
        if result['start_gap_s']>max_gap_s or result['end_gap_s']>max_gap_s:
            return dict(result,valid=False,reason='selected_output_capture_coverage_incomplete')
    return result

def selected_output_stability(samples, requested_hz, window_seconds=ENDURANCE_WINDOW_SECONDS, required_windows=6):
    """Require a native selected-output counter rate in every five-minute window."""
    windows=[]
    if (not isinstance(requested_hz,(int,float)) or isinstance(requested_hz,bool)
            or not math.isfinite(requested_hz) or requested_hz <= 0):
        return {'status':'pending_or_failed','reason':'selected_output_requested_rate_invalid','windows':windows}
    # Validate all telemetry before using a timestamp as a window boundary. This
    # prevents missing/NaN capture elapsed values from raising during arithmetic.
    whole=selected_output_window(samples)
    if not whole.get('valid'):
        return {'status':'pending_or_failed','reason':whole.get('reason','selected_output_unverified'),'windows':windows}
    start=samples[0][0]
    for index in range(required_windows):
        rows=[row for row in samples if start+index*window_seconds <= row[0] <= start+(index+1)*window_seconds]
        check=selected_output_window(rows)
        passed=(check.get('valid') and check.get('interval_s',0)>=window_seconds*.98
                and check.get('rate_fps',0)>=requested_hz*.98)
        windows.append({'index':index,'status':'passed' if passed else 'failed','rate_fps':check.get('rate_fps'),
                        'window_s':check.get('interval_s'),'reason':check.get('reason')})
    return {'status':'stable' if all(w['status']=='passed' for w in windows) else 'pending_or_failed','windows':windows}

def rate_stability(graphs, requested_hz, window_seconds=ENDURANCE_WINDOW_SECONDS, required_windows=6):
    """Check independent five-minute submission windows for a 30-minute endurance run."""
    timed=list(graphs)
    if (not requested_hz or len(timed)<2 or any(not isinstance(t,(int,float)) or isinstance(t,bool)
        or not math.isfinite(t) for t,_ in timed)):
        return {'status':'missing_timed_frames','windows':[]}
    start=timed[0][0]; buckets={}
    for t,data in timed:
        index=int((t-start)//window_seconds)
        buckets.setdefault(index,[]).append((t,data))
    windows=[]
    for index in range(required_windows):
        rows=buckets.get(index,[])
        if len(rows)<2:
            windows.append({'index':index,'status':'incomplete','submission_rate_fps':None})
            continue
        span=rows[-1][0]-rows[0][0]
        rate=(len(rows)-1)/span if span>0 else None
        fps=distribution([row.get('client_fps') for _,row in rows])
        passed=bool(rate is not None and span>=window_seconds*.98 and fps is not None
                    and rate>=requested_hz*.98 and fps['p01']>=requested_hz*.98)
        windows.append({'index':index,'status':'passed' if passed else 'failed','submission_rate_fps':rate,
                        'window_s':span,'client_fps_p01':fps['p01'] if fps else None})
    return {'status':'stable' if all(window['status']=='passed' for window in windows) else 'pending_or_failed',
            'window_seconds':window_seconds,'windows':windows}


def summarise(events, requested_hz=None, capture_end_elapsed=None):
    graphs=[]; summaries=[]; telemetry=[]; graph_times=[]; pyro_samples=[]; selected_samples=[]
    timed_graphs=[]
    for item in events:
        event=item.get('event',item).get('event_type',{})
        data=event.get('data',{})
        if event.get('id')=='GraphStatistics':
            graphs.append(data)
            graph_times.append(item.get('capture_elapsed_s'))
            timed_graphs.append((item.get('capture_elapsed_s'),data))
        if event.get('id')=='StatisticsSummary': summaries.append(data)
        if event.get('id')=='HeadsetTelemetry':
            telemetry.append(data)
            elapsed=item.get('capture_elapsed_s')
            if data.get('pyrowave'):
                pyro_samples.append((elapsed,data['pyrowave']))
            selected_samples.append((elapsed, data.get('selected_output_submissions'),
                                     data.get('selected_output_submission_source')))
    result={'schema_version':1,'status':'measured' if graphs else 'no_stream_frames', 'frames':len(graphs),
            'requested_hz':requested_hz, 'metrics':{}, 'headset_telemetry':telemetry,
            'optical_motion_to_photon_ms':None,
            'latency_definition':'ALVR estimated pipeline; optical motion-to-photon requires a separate camera/photodiode measurement.'}
    for field in ('encoder_s','decoder_s','network_s','total_pipeline_latency_s',
                  'decoder_queue_s','server_compositor_s','client_compositor_s','vsync_queue_s'):
        result['metrics'][field.replace('_s','_ms')]=distribution([g.get(field,0)*1000 for g in graphs if field in g])
    # Submission-event rate over capture wall time exposes missed slots that a
    # median instantaneous FPS can hide. This is not an optical/display counter.
    valid_graph_times=len(graph_times)>1 and all(isinstance(t,(int,float))
        and not isinstance(t,bool) and math.isfinite(t) and t>=0 for t in graph_times)
    increasing=valid_graph_times and all(b>a for a,b in zip(graph_times,graph_times[1:]))
    span=graph_times[-1]-graph_times[0] if increasing else 0
    result['submitted_frame_rate_fps']=(len(graph_times)-1)/span if span>0 else None
    # GraphStatistics is emitted after client report_submit() selects a non-null
    # decoded buffer. Its capture-arrival rate is therefore a submission-event
    # proxy, not a unique image/frame identifier. Tracking target timestamps are
    # deliberately reusable by different game frames, so they cannot invalidate
    # this rate or establish freshness by themselves.
    result['selected_submission_event_rate_fps']=result['submitted_frame_rate_fps']
    result['submission_rate_window_s']=span if span>0 else None
    result['sustained_rate_window_min_seconds']=SUSTAINED_RATE_WINDOW_SECONDS
    result['rate_stability']=rate_stability(timed_graphs,requested_hz)
    result['rate_check_scope']='Submission and available direct-completion rate proxies. A short pass is screening only; even a long rate pass does not certify configuration, image correctness, gameplay, thermals or optical FPS.'
    result['submission_rate_definition']='GraphStatistics events per QPC capture-time span. Each is a selected decoded-buffer submission event under the client report_submit path, not a unique source/image identifier, GPU completion, repeated OpenXR layer count or optical display FPS.'
    result['metrics']['client_fps']=distribution([g.get('client_fps') for g in graphs])
    result['metrics']['server_fps']=distribution([g.get('server_fps') for g in graphs])
    result['metrics']['video_mbps']=distribution([g.get('bitrate_bps',0)/1e6 for g in graphs])
    raw_timestamps=[g['target_timestamp_ns'] for g in graphs if 'target_timestamp_ns' in g]
    timestamps=sorted(set(raw_timestamps))
    result['duplicate_frame_events']=max(0, len(raw_timestamps)-len(timestamps))
    result['target_timestamp_reuse_events']=result['duplicate_frame_events']
    result['distinct_target_timestamp_count']=len(timestamps) if raw_timestamps else None
    # Compatibility only. This historic name counted distinct tracking timestamps,
    # not fresh frames. Keep it until downstream consumers migrate.
    result['fresh_frames']=result['distinct_target_timestamp_count']
    result['fresh_frames_definition']='Deprecated compatibility field: distinct tracking target timestamps, not unique fresh video frames. Use selected_submission_event_rate_fps for the selected decoded-buffer submission-event rate.'
    selected=selected_output_window(selected_samples,capture_end_elapsed=capture_end_elapsed)
    result['selected_output_submission_window']=selected
    result['fresh_selected_output_rate_fps']=selected.get('rate_fps') if selected.get('valid') else None
    result['fresh_frame_identity_verified']=selected.get('valid',False)
    result['fresh_frame_identity_definition']='Native cumulative post-render/release selected decoder outputs, source marker required; never derived from reusable tracking timestamps.'
    result['selected_output_endurance']=selected_output_stability(selected_samples,requested_hz) if requested_hz else {'status':'pending_or_failed','windows':[]}
    result['metrics']['frame_timestamp_gap_ms']=distribution([(b-a)/1e6 for a,b in zip(timestamps,timestamps[1:])])
    # Counter deltas; never report the last lifetime total as this capture's losses.
    result['packet_loss_delta']=None
    if len(summaries)>1 and 'packets_lost_total' in summaries[0]:
        delta=summaries[-1]['packets_lost_total']-summaries[0]['packets_lost_total']
        result['packet_loss_delta']=delta if delta>=0 else None
    result['network_latency_definition']='ALVR residual estimate; PyroWave separate UDP timing can clamp this to zero. Not a direct one-way measurement.'
    result['gpu_decode_ms']=distribution([v for t in telemetry if t.get('pyrowave')
        for v in t['pyrowave'].get('gpu_decode_ms',[])])
    result['decode_to_fence_ms']=distribution([v for t in telemetry if t.get('pyrowave')
        for v in t['pyrowave'].get('fence_ms',[])])
    for field in ('convert_ms','record_ms','wait_ms'):
        result['native_'+field]=distribution([v for t in telemetry if t.get('pyrowave')
            for v in t['pyrowave'].get(field,[])])
    for field in ('eye_acquire_wait_ms', 'eye_render_ms', 'eye_release_ms', 'eye_completion_observed_ms'):
        result[field]=distribution([v for t in telemetry if t.get('pyrowave')
            for v in t['pyrowave'].get(field,[])])
    result['eye_timing_definition']='Client CPU wall time: acquire/wait, renderer call, release. Async completion is wall time until a later nonblocking fence poll, quantized by polling; none of these are GPU timer-query durations.'
    window=pyrowave_counter_window(pyro_samples)
    result['pyrowave_counter_window']=window
    result['eye_copy_counter_deltas']={field:window['counter_deltas'][field] for field in (
        'direct_eye_copies', 'staging_eye_copies', 'completed_eye_copies', 'pending_eye_copy_deferrals')}
    result['completed_eye_copy_rate_fps']=None
    if ((result['eye_copy_counter_deltas']['direct_eye_copies'] or 0)>0
            and result['eye_copy_counter_deltas']['staging_eye_copies']==0):
        result['completed_eye_copy_rate_fps']=window['counter_rates_per_s']['completed_eye_copies']
    result['completion_rate_definition']='GPU-complete direct eye copies per telemetry-time span, only for exclusively direct windows; staging completion is unobserved. Includes configuration-forced redraws. Not optical display or unique fresh-frame FPS.'
    if requested_hz and graphs:
        fps=result['metrics']['client_fps']
        submitted=result['selected_submission_event_rate_fps']
        result['requested_rate_screen_passed']=(fps is not None and submitted is not None
            and fps['p01']>=requested_hz*.98 and submitted>=requested_hz*.98)
        completed=result['completed_eye_copy_rate_fps']
        if completed is not None:
            result['requested_rate_screen_passed'] &= completed>=requested_hz*.98
        # Keep the legacy key, but never label a short screen as sustained.
        # This remains a rate check, not full native120/thermal/image acceptance.
        result['sustained_requested_fps']=(result['requested_rate_screen_passed']
            and span>=SUSTAINED_RATE_WINDOW_SECONDS)
    return result

def adb_run(adb, *args):
    p=subprocess.run([adb,*args],capture_output=True,text=True,timeout=20)
    if p.returncode: raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout

def snapshot(adb):
    # No root or clock overrides. Inaccessible counters remain explicit errors.
    result={}
    for key,cmd in {'battery':'dumpsys battery','thermals':'dumpsys thermalservice',
        'gpu_clock_hz':'cat /sys/class/kgsl/kgsl-3d0/gpuclk',
        'gpu_busy':'cat /sys/class/kgsl/kgsl-3d0/gpubusy',
        'gpu_available_frequencies':'cat /sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies'}.items():
        try: result[key]={'value':adb_run(adb,'shell',cmd),'error':None}
        except (RuntimeError,subprocess.TimeoutExpired) as e: result[key]={'value':None,'error':str(e)}
    for name in EXPERIMENT_PROPERTIES:
        key='property:' + name
        try: result[key]={'value':adb_run(adb,'shell','getprop',name).strip(),'error':None}
        except (RuntimeError,subprocess.TimeoutExpired) as e: result[key]={'value':None,'error':str(e)}
    return result

def experiment_effective(state):
    """Preserve raw Android properties and derive only documented source semantics."""
    raw={name:state.get('property:'+name,{}) for name in EXPERIMENT_PROPERTIES}
    if any(item.get('error') or item.get('value') is None for item in raw.values()):
        return {'raw':raw,'verified':False,'enabled':None}
    value=lambda name: raw[name].get('value') or ''
    integer=lambda name: int(value(name)) if value(name).strip().lstrip('-').isdigit() else 0
    enabled={
        'direct_eye_copy':value('debug.q3pw.direct_eye_copy')=='1',
        'async_eye_copy':value('debug.q3pw.async_eye_copy')=='1',
        'copy_wait':integer('debug.q3pw.copy_wait_us') != 0,
        'raw_srgb_copy':value('debug.q3pw.raw_srgb_copy')=='1',
        'image_cache':value('debug.q3pw.image_cache')=='1',
        'frame_wait':integer('debug.q3pw.frame_wait_us') != 0,
        'pre_wait_poll':value('debug.q3pw.pre_wait_poll')=='1',
        'repeat_render':value('debug.q3pw.repeat_render')=='1',
        'decode_workers':value('debug.q3pw.decode_workers')=='2',
        'decode_handoff':value('debug.q3pw.decode_handoff')=='1',
        'display_scaling':(value('debug.oculus.forceDisplayScaling') == '1'
                           or value('debug.oculus.refreshRate') != ''),
        'haar_fused':value('debug.q3pw.haar_fused')=='1',
        'dequant_batch':value('debug.q3pw.dequant_batch')=='1',
        'convert_compute':value('debug.q3pw.convert_compute')=='1',
        'fragment_min_usage':value('debug.q3pw.fragment_min_usage')=='1',
        'optimal_ahb_usage':value('debug.q3pw.optimal_ahb_usage')=='1',
        'loop_probe':value('debug.q3pw.loop_probe')=='1',
        'runtime_display_time':value('debug.q3pw.runtime_display_time')=='1',
        'pass_profile':value('debug.q3pw.pass_profile')=='1',
        'hide_performance_overlay':value('debug.q3pw.hide_performance_overlay')=='1',
        'layer_filter':integer('debug.q3pw.layer_filter') if integer('debug.q3pw.layer_filter') in (1,2,3) else 0,
    }
    # direct_flip_y is recorded but not treated as an opt-in experiment: source defaults it true.
    return {'raw':raw,'verified':True,'enabled':enabled,
            'effective_decode_workers':2 if enabled['decode_workers'] else 1,
            'effective_direct_flip_y':value('debug.q3pw.direct_flip_y')!='0',
            'effective_pyro_precision':value('debug.xrwired.pyro_precision') or '1',
            'effective_early_poll':value('debug.xrwired.early_poll')!='0',
            'effective_perf_level':value('debug.xrwired.perf_level') or 'sustained_high'}

def effective_pyrowave_config(config):
    return {'enabled':config.get('pyrowave_enabled'),'transport':'Udp' if config.get('pyrowave_udp') else 'Tcp',
            'chroma':'444' if config.get('pyrowave_chroma_444') else '420',
            'wavelet':'Haar' if config.get('pyrowave_wavelet_haar') else ('Cdf53' if config.get('pyrowave_wavelet_53') else 'Cdf97'),
            'decode_path':{0:'Auto',1:'Fragment',2:'Compute'}.get(config.get('pyrowave_decode_path')),
            'foveated_encoding':config.get('enable_foveated_encoding')}

def active_settings():
    from .control import session
    s=session();v=s['session_settings']['video'];o=s.get('openvr_config',{})
    mode = v['bitrate']['mode']
    encoder_config=v.get('encoder_config',{})
    foveated=v.get('foveated_encoding',{}); client_foveated=v.get('clientside_foveation',{})
    return {'server_version':s.get('server_version'), 'codec':v['preferred_codec']['variant'],
        'bitrate_mode':mode['variant'], 'bitrate_config':mode,
        'target_mbps':mode['ConstantMbps'] if mode['variant']=='ConstantMbps' else None,
        'requested_hz':v['preferred_fps'], 'decode_path':v['pyrowave']['decode_path']['variant'],
        'wavelet':v['pyrowave']['wavelet']['variant'],
        'chroma':'444' if v['pyrowave'].get('chroma_444',False) else '420',
        'transport':v['pyrowave']['transport']['variant'], 'stream_protocol':s['session_settings']['connection']['stream_protocol']['variant'],
        'configured_view_resolution':v['transcoding_view_resolution'],
        'hdr_enabled':encoder_config.get('enable_hdr'),
        'hdr_server_override':encoder_config.get('server_overrides_enable_hdr'),
        'enforce_server_frame_pacing':v.get('enforce_server_frame_pacing'),
        'foveated_encoding_enabled':foveated.get('enabled'),
        'clientside_foveation_enabled':client_foveated.get('enabled'),
        'encoded_resolution':absolute_resolution(v.get('transcoding_view_resolution')),
        'render_resolution':absolute_resolution(v.get('emulated_headset_view_resolution')),
        # ALVR connection.rs assigns stream_view_resolution to eye_resolution;
        # target_eye_resolution is the game's recommended render target.
        'negotiated_encoded_resolution':openvr_resolution(o,'eye_resolution_width','eye_resolution_height'),
        'negotiated_render_resolution':openvr_resolution(o,'target_eye_resolution_width','target_eye_resolution_height'),
        'negotiated_hz':o.get('refresh_rate'),
        'effective_pyrowave':effective_pyrowave_config(o),
        'openvr':{k:o.get(k) for k in ('refresh_rate','eye_resolution_width','eye_resolution_height',
            'target_eye_resolution_width','target_eye_resolution_height','pyrowave_enabled','pyrowave_decode_path','pyrowave_wavelet_53','pyrowave_wavelet_haar','pyrowave_udp','pyrowave_chroma_444','enable_foveated_encoding')}}

def absolute_resolution(value):
    """Normalise ALVR's optional Absolute setting without inventing a scale."""
    if not isinstance(value, dict) or value.get('variant') != 'Absolute': return None
    absolute=value.get('Absolute', {})
    height=absolute.get('height')
    if isinstance(height, dict): height=height.get('content') if height.get('set') else None
    width=absolute.get('width')
    return {'width':width, 'height':height} if isinstance(width,int) and isinstance(height,int) else None

def openvr_resolution(config, width_key, height_key):
    width,height=config.get(width_key),config.get(height_key)
    return {'width':width,'height':height} if isinstance(width,int) and isinstance(height,int) else None

def _log_epoch(line):
    match=re.match(r'\s*([0-9]+(?:\.[0-9]+)?)\s+', line)
    return float(match.group(1)) if match else None

def filter_runtime_evidence(log, capture_id=None, since_epoch=None):
    """Keep only Q3PW diagnostics, with a durable timestamp cursor after ring rotation."""
    lines=log.splitlines()
    if capture_id:
        markers=[i for i,line in enumerate(lines) if 'Q3PW_CAPTURE' in line and capture_id in line]
        if not markers: return []
        marker_line=lines[markers[-1]]
        since_epoch=_log_epoch(marker_line) if since_epoch is None else since_epoch
    return [line for line in lines if (since_epoch is None or (_log_epoch(line) is not None and _log_epoch(line)>=since_epoch))
        and re.search(r'\[Q3PW_(CAPS|PROBE|VERIFIED|RATE|EFFECTIVE)\]',line)]

def capture_marker_epoch(adb, capture_id):
    log=adb_run(adb,'logcat','-d','-v','epoch','-t','20000')
    for line in reversed(log.splitlines()):
        if 'Q3PW_CAPTURE' in line and capture_id in line:
            return _log_epoch(line)
    return None

def runtime_evidence(adb, capture_id=None, since_epoch=None):
    log=adb_run(adb,'logcat','-d','-v','epoch','-t','20000')
    return filter_runtime_evidence(log,capture_id,since_epoch)

def fresh_rate_evidence(lines, requested_hz):
    effective=[line for line in lines if '[Q3PW_EFFECTIVE]' in line]
    if not effective: return False
    expected_period=1e9/requested_hz
    for line in effective:
        # The pinned OpenXR client logs the Result<f32> directly: Ok(...), not Some(...).
        match=re.search(r'\[Q3PW_EFFECTIVE\].*requested=Some\(([0-9.]+)\).*runtime_hz=(?:Ok|Some)\(([0-9.]+)\)',line)
        period=re.search(r'period_ns=([0-9]+)',line)
        if not (match and period and abs(float(match.group(1))-requested_hz)<.01
                and abs(float(match.group(2))-requested_hz)<.01
                and abs(float(period.group(1))-expected_period)<=expected_period*.02): return False
    return True

def runtime_coverage(polls, elapsed, max_gap_s=15):
    """A capture must continuously collect scoped Q3PW evidence, not only a final tail."""
    times=[p['elapsed_s'] for p in polls if p.get('records',0)>0]
    if not times: return {'status':'incomplete','polls':polls}
    gaps=[b-a for a,b in zip(times,times[1:])]
    complete=(times[0]<=max_gap_s and elapsed-times[-1]<=max_gap_s and all(0<g<=max_gap_s for g in gaps))
    return {'status':'covered' if complete else 'incomplete','polls':polls,
            'max_gap_s':max(gaps,default=times[0])}

def build_identity_verified(manifest, settings, client):
    required=('schema_version','application_version','protocol_version','client_package_id','repository_commit',
              'sources_lock_sha256','dependency_revisions','shader_hashes','artifact_sha256','signing_certificate_sha256')
    if not isinstance(manifest,dict) or any(not manifest.get(key) for key in required): return False
    version=manifest.get('application_version')
    return bool(version and settings and client and client.get('version') == version
                and settings.get('server_version') == version)

def benchmark_tool_provenance():
    """Identify the exact capture tool revision; dirty/untracked tool files cannot certify a run."""
    root=Path(__file__).resolve().parents[2]
    try:
        commit=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
        status=subprocess.run(['git','-C',str(root),'status','--porcelain','--','tools/quest3'],capture_output=True,text=True,timeout=10,check=True).stdout
        return {'repository_commit':commit,'tool_tree_dirty':bool(status.strip()),'verified':not bool(status.strip()),'error':None}
    except (OSError,subprocess.SubprocessError) as exc:
        return {'repository_commit':None,'tool_tree_dirty':None,'verified':False,'error':str(exc)}

def thermal_ok(samples):
    """Return a decision only from readable Android thermal-service status values."""
    statuses=[]
    for sample in samples:
        entry=sample.get('state',{}).get('thermals',{})
        if entry.get('error'): return None
        match=re.search(r'(?:thermal\s+)?status\s*:\s*(\d+)', entry.get('value',''),re.I)
        if not match: return None
        statuses.append(int(match.group(1)))
    return bool(statuses) and max(statuses)<=2

def merge_review(report, review):
    """Merge only human-observable checks from a capture-bound operator attestation."""
    if not isinstance(review,dict) or review.get('capture_id') != report.get('capture_id'):
        return report
    fields=('controllers_ok','audio_ok','tracking_ok','image_ok','manual_confirmation','metro_clarity_ok','metro_motion_ok',
            'no_disconnects_ok','no_crashes_ok','no_competing_gpu_workload')
    report=dict(report)
    report.update({field:review.get(field) for field in fields})
    report['operator_review']={key:review.get(key) for key in ('capture_id','reviewer','reviewed_at','notes')}
    return report

def client_build(adb):
    try:
        package=adb_run(adb,'shell','dumpsys','package','io.github.ljk1291.quest3pyrowave')
        version=re.search(r'^\s*versionName=(\S+)',package,re.MULTILINE)
        return {'version':version.group(1) if version else None,
                'error':None if version else 'Package version unavailable'}
    except (RuntimeError,subprocess.TimeoutExpired) as exc:
        return {'version':None,'error':str(exc)}

def capture(args):
    import websocket
    root=Path(args.out);root.mkdir(parents=True,exist_ok=False)
    provenance=benchmark_tool_provenance()
    start=snapshot(args.adb);start_experiments=experiment_effective(start);build=client_build(args.adb);events=[];samples=[];error=None;ws=None
    try:settings_start=active_settings()
    except Exception as exc:
        report={'status':'server_unavailable','frames':0,'error':str(exc),'state_start':start,
                'client_build':build}
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'status':report['status'],'out':str(root)}));return 1
    capture_id=str(uuid.uuid4())
    # A marker lets post-capture collection reject stale Q3PW records without
    # clearing global logcat or changing a system setting.
    adb_run(args.adb,'shell','log','-t','Q3PW_CAPTURE',capture_id)
    marker_epoch=capture_marker_epoch(args.adb,capture_id)
    # Keep event-arrival timing on perf_counter rather than time.monotonic:
    # Windows can expose the latter through a 15.625 ms GetTickCount64 clock.
    # Do not relax duplicate-frame validation; measure the arrivals precisely.
    clock=measurement_clock
    clock_info=measurement_clock_info()
    stop=threading.Event();begin_wall_ns=time.time_ns();begin=clock()
    runtime_samples=[];runtime_polls=[];runtime_cursor=[marker_epoch - .001 if marker_epoch is not None else None]
    def sample_device():
        while not stop.is_set():
            samples.append({'elapsed_s':clock()-begin,'state':snapshot(args.adb)})
            # Poll frequently enough that the log ring cannot lose a 30-minute session;
            # retain only Q3PW records after the immutable marker timestamp.
            if runtime_cursor[0] is not None:
                try:
                    batch=runtime_evidence(args.adb,since_epoch=runtime_cursor[0])
                    fresh=[line for line in batch if (_log_epoch(line) or -1)>runtime_cursor[0]]
                    if fresh: runtime_cursor[0]=max(_log_epoch(line) for line in fresh)
                    runtime_samples.extend(fresh)
                    runtime_polls.append({'elapsed_s':clock()-begin,'records':len(fresh)})
                except (RuntimeError,subprocess.TimeoutExpired): runtime_polls.append({'elapsed_s':clock()-begin,'records':0})
            stop.wait(5)
    sampler=threading.Thread(target=sample_device,daemon=True);sampler.start()
    try:
        ws=websocket.create_connection(args.events,header=['X-ALVR: true'],timeout=2)
        with (root/'events.jsonl').open('w',encoding='utf-8') as out:
            while clock()-begin<args.seconds:
                try:
                    event=json.loads(ws.recv())
                    if event.get('event_type',{}).get('id') in ('GraphStatistics','StatisticsSummary','HeadsetTelemetry'):
                        row={'capture_elapsed_s':clock()-begin,'event':event}
                        events.append(row);out.write(json.dumps(row)+'\n')
                except websocket.WebSocketTimeoutException: pass
    except Exception as e:error=str(e)
    finally:
        capture_end_elapsed=clock()-begin
        stop.set();sampler.join(timeout=25)
        if ws:ws.close()
    report=summarise(events,args.hz,capture_end_elapsed)
    try:settings_end=active_settings()
    except Exception as exc:settings_end=None;error=str(exc)
    manifest = json.loads(Path(args.build_manifest).read_text(encoding='utf-8')) if args.build_manifest else None
    evidence=list(dict.fromkeys(runtime_samples)) if marker_epoch is not None else []
    coverage=runtime_coverage(runtime_polls,capture_end_elapsed)
    fresh=fresh_rate_evidence(evidence,args.hz)
    identity_ok=build_identity_verified(manifest,settings_start,build)
    report.update({'duration_requested_s':args.seconds,'capture_started_unix_ns':begin_wall_ns,'elapsed_s':clock()-begin,
        'measurement_clock':clock_info,
        'error':error,'state_start':start,'state_end':snapshot(args.adb),'device_samples':samples,
        'settings_start':settings_start,'settings_end':settings_end,'client_build':build,
        'capture_id':capture_id, 'runtime_evidence':evidence, 'fresh_runtime_evidence':fresh,
        'runtime_evidence_coverage':coverage,
        'build_identity':manifest, 'build_identity_verified':identity_ok,
        'benchmark_tool_provenance':provenance,
        'experiment_options_start':start_experiments,
        'telemetry_complete':len(report.get('headset_telemetry',[])) >= 2,
        'thermal_ok':thermal_ok(samples),
        'stream_errors':([error] if error else ([] if report['pyrowave_counter_window']['counter_deltas'].get('decode_failures') == 0 else None))})
    report['experiment_options_end']=experiment_effective(report['state_end'])
    if settings_start!=settings_end:report['status']='settings_changed_during_capture'
    if settings_start['openvr'].get('refresh_rate')!=args.hz:report['status']='negotiated_rate_mismatch'
    if error:report['status']='capture_failed'
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'frames':report['frames'],'out':str(root)}))
    return 0 if report['status']=='measured' else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('capabilities');c.add_argument('--adb',default='adb');c.add_argument('--out',required=True)
    c=sub.add_parser('plan');c.add_argument('--capabilities',required=True);c.add_argument('--out',required=True)
    c.add_argument('--repeats',type=int,default=3);c.add_argument('--seconds',type=int,default=15)
    c=sub.add_parser('capture');c.add_argument('--adb',default='adb');c.add_argument('--out',required=True)
    c.add_argument('--seconds',type=int,default=15);c.add_argument('--hz',type=int,required=True)
    c.add_argument('--events',default='ws://127.0.0.1:8082/api/events')
    c.add_argument('--build-manifest',help='matching CI build-identity manifest; recorded but not trusted without runtime marker')
    c=sub.add_parser('baseline-plan');c.add_argument('--out',required=True);c.add_argument('--render-width',type=int,required=True);c.add_argument('--render-height',type=int,required=True)
    c.add_argument('--encoded-width',type=int,required=True);c.add_argument('--encoded-height',type=int,required=True);c.add_argument('--repeats',type=int,default=3)
    c=sub.add_parser('accept');c.add_argument('--report',required=True);c.add_argument('--expected',required=True);c.add_argument('--out',required=True)
    c.add_argument('--mbps',type=int,help='selected target profile bitrate; required for a baseline-plan acceptance')
    c.add_argument('--review',help='operator attestation JSON bound to report capture_id')
    c=sub.add_parser('summarise');c.add_argument('events');c.add_argument('--out',required=True)
    a=p.parse_args()
    if a.command=='capture': return capture(a)
    if a.command=='capabilities': data=parse_capabilities(adb_run(a.adb,'shell','logcat -d -t 20000'))
    elif a.command=='plan': data=plan(json.loads(Path(a.capabilities).read_text()),a.repeats,seconds=a.seconds)
    elif a.command=='baseline-plan': data=baseline_plan({'width':a.render_width,'height':a.render_height},{'width':a.encoded_width,'height':a.encoded_height},a.repeats)
    elif a.command=='accept':
        report=json.loads(Path(a.report).read_text())
        if a.review: report=merge_review(report,json.loads(Path(a.review).read_text()))
        data=acceptance(report,json.loads(Path(a.expected).read_text()),a.mbps)
    else: data=summarise([json.loads(line) for line in Path(a.events).read_text().splitlines()])
    Path(a.out).write_text(json.dumps(data,indent=2),encoding='utf-8');print(a.out);return 0

if __name__=='__main__': raise SystemExit(main())

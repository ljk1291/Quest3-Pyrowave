"""Explicit ALVR session changes for reproducible Quest experiments."""
import argparse
import json
import urllib.request
import subprocess
import time
import os
import shlex
from pathlib import Path
from .bench import supported

API='http://127.0.0.1:8082/api/dashboard-request'
EVENTS='ws://127.0.0.1:8082/api/events'
CLIENT_PACKAGE_ID=json.loads((Path(__file__).resolve().parents[2] / 'fork.json').read_text(encoding='utf-8'))['client_package_id']
EXPERIMENT_PROPERTIES=('debug.oculus.forceDisplayScaling','debug.oculus.refreshRate','debug.q3pw.direct_eye_copy',
    'debug.q3pw.async_eye_copy','debug.q3pw.copy_wait_us','debug.q3pw.raw_srgb_copy','debug.q3pw.image_cache',
    'debug.q3pw.frame_wait_us','debug.q3pw.pre_wait_poll','debug.q3pw.repeat_render','debug.q3pw.decode_workers',
    'debug.q3pw.decode_handoff','debug.q3pw.haar_fused','debug.q3pw.dequant_batch','debug.q3pw.convert_compute',
    'debug.q3pw.fragment_min_usage','debug.q3pw.optimal_ahb_usage','debug.q3pw.loop_probe',
    'debug.q3pw.runtime_display_time','debug.q3pw.pass_profile','debug.q3pw.hide_performance_overlay',
    'debug.xrwired.pyro_precision','debug.xrwired.early_poll','debug.xrwired.perf_level')

def windows_process_running(executable):
    """Read the process snapshot directly; tasklist can hang during SteamVR shutdown."""
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD),
                    ('pid', wintypes.DWORD), ('heap', ctypes.c_size_t),
                    ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', wintypes.LONG),
                    ('flags', wintypes.DWORD), ('name', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for method in (kernel.Process32FirstW, kernel.Process32NextW):
        method.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        method.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = Entry(); entry.size = ctypes.sizeof(Entry)
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            if entry.name.casefold() == executable.casefold(): return True
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18: # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        return False
    finally:
        kernel.CloseHandle(handle)
def request(value):
    req=urllib.request.Request(API,data=json.dumps(value).encode(),
        headers={'X-ALVR':'true','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as response:
        if response.status!=200: raise RuntimeError(f'ALVR HTTP {response.status}')

def session():
    import websocket
    ws=websocket.create_connection(EVENTS,header=['X-ALVR: true'],timeout=10)
    try:
        request('GetSession')
        deadline=time.monotonic()+10
        for _ in range(1000):
            remaining=deadline-time.monotonic()
            if remaining<=0: raise TimeoutError('ALVR session response deadline exceeded')
            ws.settimeout(remaining)
            event=json.loads(ws.recv()).get('event_type',{})
            if event.get('id')=='Session': return event['data']
        raise RuntimeError('No session response')
    finally: ws.close()

def set_values(values):
    request({'SetValues':[{'path':[{'Name':s} for s in path.split('.')],'value':value}
        for path,value in values.items()]})

def adb_property_snapshot(adb):
    """Read only the two display-scaling experiment properties; no defaults inferred."""
    result={}
    for name in EXPERIMENT_PROPERTIES:
        run=subprocess.run([adb,'shell','getprop',name],capture_output=True,text=True,timeout=20)
        result[name]={'value':run.stdout.strip() if not run.returncode else None,
                      'error':None if not run.returncode else (run.stderr.strip() or run.stdout.strip())}
    return result

def experiment_properties(adb, disable=False, disable_experiments=False):
    """Explicitly reset selected experiment properties and return before/after readback."""
    before=adb_property_snapshot(adb)
    changes=[]
    if disable:
        changes.extend((('debug.oculus.forceDisplayScaling','0'),('debug.oculus.refreshRate','')))
    if disable_experiments:
        # Do not touch direct_flip_y: an unset property intentionally means the source default true.
        changes.extend((
            ('debug.q3pw.direct_eye_copy',''),('debug.q3pw.async_eye_copy',''),
            ('debug.q3pw.copy_wait_us',''),('debug.q3pw.raw_srgb_copy',''),
            ('debug.q3pw.image_cache',''),('debug.q3pw.frame_wait_us',''),
            ('debug.q3pw.pre_wait_poll',''),('debug.q3pw.repeat_render',''),
            ('debug.q3pw.decode_workers',''),('debug.q3pw.decode_handoff',''),
            ('debug.q3pw.haar_fused','0'),('debug.q3pw.dequant_batch','0'),
            ('debug.q3pw.convert_compute','0'),('debug.q3pw.fragment_min_usage','0'),
            ('debug.q3pw.optimal_ahb_usage','0'),('debug.q3pw.loop_probe','0'),
            ('debug.q3pw.runtime_display_time','0'),('debug.q3pw.pass_profile','0'),
            ('debug.q3pw.hide_performance_overlay','0'),('debug.xrwired.pyro_precision','1'),
            ('debug.xrwired.early_poll','1'),('debug.xrwired.perf_level','sustained_high'),
        ))
    writes=[]
    for name,value in changes:
        # adb's argument forwarding drops a literal empty final argument. Send one
        # explicitly quoted remote shell command so `setprop NAME ''` clears it.
        remote='setprop %s %s' % (shlex.quote(name), shlex.quote(value))
        run=subprocess.run([adb,'shell',remote],capture_output=True,text=True,timeout=20)
        error=None if not run.returncode else (run.stderr.strip() or run.stdout.strip())
        writes.append({'property':name,'value':value,'error':error})
        if error: break
    after=adb_property_snapshot(adb)
    return {'changed':any(item['error'] is None for item in writes), 'before':before,
            'after':after, 'writes':writes, 'errors':[item for item in writes if item['error']]}

def usb(enabled):
    if enabled:
        set_values({'session_settings.connection.wired_client_type.variant':'Custom',
                    'session_settings.connection.wired_client_type.Custom':CLIENT_PACKAGE_ID,
                    'session_settings.video.pyrowave.transport.variant':'Tcp',
                    'session_settings.connection.stream_protocol.variant':'Tcp'})
    request({'UpdateClientList':{'hostname':'client.wired',
        'action':{'AddIfMissing':{'trusted':True,'manual_ips':[]}} if enabled else 'RemoveEntry'}})

def _absolute_resolution(width, height):
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError('Resolution dimensions must be positive integer per-eye pixels')
    return {'variant':'Absolute', 'Scale':1.0,
            'Absolute':{'width':width, 'height':{'set':True, 'content':height}}}

def apply(codec, mbps, hz, path, caps, chroma="420", transport="Tcp", wavelet="Cdf97",
          render_resolution=None, encoded_resolution=None):
    if not caps.get('refresh_extension') or not supported(hz,caps['rates_hz']):
        raise ValueError(f'{hz} Hz unsupported by provided runtime capabilities')
    if hz>120 and caps.get('source')!='request_and_frame_period':
        raise ValueError('Extended rates require current APK startup probe; enumeration is incomplete on HorizonOS v2.7.')
    if codec not in ('PyroWave','H264','Hevc','AV1') or not (1<=mbps<=2000):
        raise ValueError('Invalid codec or bitrate')
    values={'session_settings.video.preferred_codec.variant':codec,
            'session_settings.video.preferred_fps':hz,
            'session_settings.video.bitrate.mode.variant':'ConstantMbps',
            'session_settings.video.bitrate.mode.ConstantMbps':mbps,
            'session_settings.video.enforce_server_frame_pacing':True,
            'session_settings.video.foveated_encoding.content.follow_gaze':False,
            'session_settings.video.foveated_encoding.enabled':False,
            'session_settings.video.clientside_foveation.enabled':False}
    # These are real ALVR schema fields and server override makes SDR negotiated,
    # rather than merely expressing a client preference.
    values.update({'session_settings.video.encoder_config.enable_hdr':False,
                   'session_settings.video.encoder_config.server_overrides_enable_hdr':True})
    if (render_resolution is None) != (encoded_resolution is None):
        raise ValueError('Specify both render and encoded resolutions together')
    if render_resolution is not None:
        values.update({
            'session_settings.video.emulated_headset_view_resolution':_absolute_resolution(**render_resolution),
            'session_settings.video.transcoding_view_resolution':_absolute_resolution(**encoded_resolution),
        })
    if codec=='PyroWave':
        if transport not in ('Tcp', 'Udp'): raise ValueError('Invalid transport')
        if chroma not in ('420','444'): raise ValueError('Invalid chroma')
        if path not in ('Auto','Compute','Fragment'): raise ValueError('Invalid decode path')
        if wavelet not in ('Cdf97','Cdf53','Haar'): raise ValueError('Invalid wavelet')
        if wavelet in ('Cdf53','Haar') and path == 'Fragment':
            raise ValueError('CDF 5/3 and Haar require Compute or Auto decode')
        values.update({'session_settings.video.pyrowave.chroma_444':chroma=='444',
                       'session_settings.video.pyrowave.transport.variant':transport,
                       'session_settings.connection.stream_protocol.variant':'Tcp',
                       'session_settings.video.pyrowave.wavelet.variant':wavelet,
                       'session_settings.video.pyrowave.decode_path.variant':path})
    set_values(values)
    current=session()
    for key,value in values.items():
        node=current
        for field in key.split('.'):node=node[field]
        if node!=value:raise RuntimeError(f'Setting rejected: {key}')
    return {'codec':codec,'mbps':mbps,'requested_hz':hz,'decode_path':path,'chroma':chroma,
            'transport':transport if codec=='PyroWave' else None,'settings_verified':True,
            'wavelet':wavelet if codec=='PyroWave' else None,
            'render_resolution':render_resolution, 'encoded_resolution':encoded_resolution,
            'dynamic_bitrate':False, 'foveated_encoding':False, 'clientside_foveation':False,
            'hdr':False,
            'sustained_performance_verified':False}

def restart(steamvr,streamer=None):
    # The HTTP request shuts the server down; only the dashboard's UI also launches it.
    # Re-register this driver after upstream restores its registration backup on shutdown.
    s=session()
    if streamer is None:streamer=s.get('drivers_backup',{}).get('alvr_path') if s.get('drivers_backup') else None
    if not streamer:raise ValueError('Specify --streamer: no driver path in session backup')
    driver=Path(streamer).resolve();runtime=Path(steamvr).resolve()
    reg=runtime/'bin/win64/vrpathreg.exe';startup=runtime/'bin/win64/vrstartup.exe'
    if not (driver/'driver.vrdrivermanifest').is_file() or not reg.is_file() or not startup.is_file():
        raise ValueError('Invalid SteamVR runtime or streamer directory')
    request('RestartSteamvr')
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        if not windows_process_running('vrserver.exe'):break
        time.sleep(.5)
    else:raise RuntimeError('SteamVR did not shut down; leaving registrations unchanged')
    subprocess.run([str(reg),'adddriver',str(driver)],check=True,capture_output=True)
    info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
    subprocess.Popen([str(startup)],startupinfo=info)
    print('SteamVR launch requested; wait for streaming to settle before capture')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    sub.add_parser('status');r=sub.add_parser('restart')
    r.add_argument('--steamvr',required=True);r.add_argument('--streamer')
    u=sub.add_parser('usb');g=u.add_mutually_exclusive_group(required=True)
    g.add_argument('--enable',action='store_true');g.add_argument('--disable',action='store_true')
    e=sub.add_parser('experiment-properties');e.add_argument('--adb',required=True)
    e.add_argument('--disable-display-scaling',action='store_true',
                   help='explicitly reset display-scaling experiment properties and print before/after readback')
    e.add_argument('--disable-experiments',action='store_true',
                   help='explicitly clear all known direct-copy, scheduling and worker experiment properties')
    c=sub.add_parser('apply');c.add_argument('--codec',choices=['PyroWave','H264','Hevc','AV1'],default='PyroWave')
    c.add_argument('--mbps',type=int,required=True);c.add_argument('--hz',type=int,required=True)
    c.add_argument('--decode-path',choices=['Auto','Compute','Fragment'],default='Compute');c.add_argument('--capabilities',required=True)
    c.add_argument('--chroma',choices=['420','444'],default='420')
    c.add_argument('--wavelet',choices=['Cdf97','Cdf53','Haar'],default='Cdf97')
    c.add_argument('--transport',choices=['Tcp','Udp'],default='Tcp')
    c.add_argument('--render-width',type=int,required=True);c.add_argument('--render-height',type=int,required=True)
    c.add_argument('--encoded-width',type=int,required=True);c.add_argument('--encoded-height',type=int,required=True)
    a=parser.parse_args()
    if a.cmd=='restart':restart(a.steamvr,a.streamer);return
    if a.cmd=='usb':usb(a.enable);print('USB mode enabled; restart SteamVR if transport changed' if a.enable else 'USB mode disabled');return
    if a.cmd=='experiment-properties':
        result=experiment_properties(a.adb,a.disable_display_scaling,a.disable_experiments)
        print(json.dumps(result));return 1 if result['errors'] else 0
    if a.cmd=='apply':print(json.dumps(apply(a.codec,a.mbps,a.hz,a.decode_path,json.loads(Path(a.capabilities).read_text()),a.chroma,a.transport,a.wavelet,
        {'width':a.render_width,'height':a.render_height},{'width':a.encoded_width,'height':a.encoded_height})));return
    s=session();v=s['session_settings']['video'];clients=s.get('client_connections',{})
    print(json.dumps({'video':{key:v.get(key) for key in ('preferred_codec','preferred_fps','bitrate','pyrowave','transcoding_view_resolution')},
                     'client_count':len(clients)}))

if __name__=='__main__':main()

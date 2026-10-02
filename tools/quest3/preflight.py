"""Read-only PC inventory and private rollback snapshot. Never starts or stops VR."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def registry_value(key, name, hive='HKLM'):
    try:
        import winreg
        root = winreg.HKEY_LOCAL_MACHINE if hive == 'HKLM' else winreg.HKEY_CURRENT_USER
        with winreg.OpenKey(root, key) as handle:
            return {'value': winreg.QueryValueEx(handle, name)[0], 'error': None}
    except (ImportError, OSError) as exc:
        return {'value': None, 'error': str(exc)}


def nvidia_driver():
    """Read the installed NVIDIA driver when nvidia-smi is available; never change it."""
    executable=shutil.which('nvidia-smi') or shutil.which('nvidia-smi.exe')
    if not executable:
        return {'gpus': None, 'error': 'nvidia-smi unavailable'}
    try:
        run=subprocess.run([executable,'--query-gpu=name,driver_version','--format=csv,noheader'],
                           capture_output=True,text=True,timeout=5,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if run.returncode: raise RuntimeError(run.stderr.strip() or run.stdout.strip())
        rows=[]
        for line in run.stdout.splitlines():
            values=[value.strip() for value in line.split(',',1)]
            if len(values) != 2: raise ValueError('unexpected nvidia-smi CSV output')
            rows.append({'name':values[0],'driver_version':values[1]})
        return {'gpus':rows, 'error':None}
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return {'gpus':None,'error':str(exc)}


def runtime_manifest(value):
    """Give the exact OpenXR runtime registration target and immutable file evidence."""
    path=Path(value) if isinstance(value,str) and value else None
    record={'path':str(path) if path else None,'exists':bool(path and path.is_file()),'sha256':None,'error':None}
    if record['exists']:
        try: record['sha256']=sha256(path)
        except OSError as exc: record['error']=str(exc)
    return record


def snapshot_files(sources, out):
    """Copy only named configuration files; this output is private and untracked."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for label, source in sources.items():
        source = Path(source)
        record = {'label': label, 'source': str(source), 'exists': source.is_file(),
                  'snapshot': None, 'sha256': None, 'error': None}
        if record['exists']:
            try:
                # A fixed basename prevents a label from escaping the private output.
                dest = out / (hashlib.sha256(label.encode()).hexdigest()[:16] + '.json')
                shutil.copyfile(source, dest)
                record.update(snapshot=str(dest.resolve()), sha256=sha256(dest))
                if sha256(source) != record['sha256']:
                    raise RuntimeError('Source changed while snapshotting; retry while idle')
            except (OSError, RuntimeError) as exc:
                record['error'] = str(exc)
        records.append(record)
    return records


def verify_snapshot(records):
    result = []
    for item in records:
        row = {'label': item['label'], 'backup_valid': None, 'current_matches': None,
               'error': item.get('error')}
        try:
            if item['exists'] and item.get('snapshot') and item.get('sha256'):
                row['backup_valid'] = sha256(item['snapshot']) == item['sha256']
                source = Path(item['source'])
                row['current_matches'] = source.is_file() and sha256(source) == item['sha256']
            elif not item['exists']:
                row['current_matches'] = not Path(item['source']).exists()
        except OSError as exc:
            row['error'] = str(exc)
        result.append(row)
    return result


def inventory(steamvr=None):
    env = os.environ
    program_data = Path(env.get('PROGRAMDATA', r'C:\ProgramData'))
    roaming = Path(env.get('APPDATA', str(Path.home() / 'AppData/Roaming')))
    local = Path(env.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    steam = registry_value(r'Software\Valve\Steam', 'SteamPath', 'HKCU')
    sources = {
        'virtual_desktop_streamer': program_data / 'Virtual Desktop/StreamerSettings.json',
        'virtual_desktop_games': roaming / 'Virtual Desktop/GameSettings.json',
        'openvr_paths': local / 'openvr/openvrpaths.vrpath',
    }
    if steam['value']:
        sources['steamvr_settings'] = Path(steam['value']) / 'config/steamvr.vrsettings'
    runtime = Path(steamvr) if steamvr else (
        Path(steam['value']) / 'steamapps/common/SteamVR' if steam['value'] else None)
    version = None
    if runtime:
        try:
            version = (runtime / 'bin/version.txt').read_text(encoding='utf-8').strip()
        except OSError:
            pass
    active_openxr=registry_value(r'SOFTWARE\Khronos\OpenXR\1', 'ActiveRuntime')
    data = {
        'platform': platform.platform(), 'steam_path': steam,
        'cpu': registry_value(r'HARDWARE\DESCRIPTION\System\CentralProcessor\0', 'ProcessorNameString'),
        'active_openxr_runtime': active_openxr,
        'active_openxr_runtime_manifest': runtime_manifest(active_openxr['value']),
        'nvidia_driver':nvidia_driver(),
        'steamvr_version': version,
        'steamvr_version_status': 'read' if version else 'unavailable',
        'network_adapters': {'value': None, 'error': None},
        'vr_running': None,
    }
    if os.name == 'nt':
        try:
            from .control import windows_process_running
            data['vr_running'] = windows_process_running('vrserver.exe')
        except (OSError, AttributeError, ImportError) as exc:
            data['vr_process_error'] = str(exc)
        try:
            cmd = ('Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed '
                   '| ConvertTo-Json -Compress')
            run = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],
                                 text=True, capture_output=True, timeout=10,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if run.returncode:
                raise RuntimeError(run.stderr.strip())
            data['network_adapters']['value'] = json.loads(run.stdout)
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            data['network_adapters']['error'] = str(exc)
    return data, sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', help='New private directory under results/local; never commit it')
    parser.add_argument('--steamvr', help='Explicit SteamVR installation directory')
    parser.add_argument('--verify', type=Path, help='Verify a previous preflight.json without changing settings')
    args = parser.parse_args()
    if args.verify:
        try:
            report = json.loads(args.verify.read_text(encoding='utf-8'))
            checks = verify_snapshot(report['configuration_snapshots'])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error('Invalid snapshot: ' + str(exc))
        print(json.dumps({'checks': checks, 'restoration_performed': False}, indent=2))
        return 1 if any(c['error'] or c['backup_valid'] is False for c in checks) else 0
    if not args.out:
        parser.error('--out is required unless --verify is supplied')
    root = Path(args.out).resolve()
    private_root = Path(__file__).resolve().parents[2] / 'results/local'
    try:
        root.relative_to(private_root.resolve())
    except ValueError:
        parser.error('--out must be under results/local so private settings remain git-ignored')
    root.mkdir(parents=True, exist_ok=False)
    data, sources = inventory(args.steamvr)
    data.update(schema_version=1, created_unix_ns=time.time_ns(),
                configuration_snapshots=snapshot_files(sources, root / 'configurations'),
                settings_changed=False, hardware_tested=False, rollback_tested=False,
                required_session_observations=['Quest OS and GPU driver', 'router band/channel width',
                    'Godlike render and encoded eye dimensions', 'Metro checkpoint and graphics settings',
                    'headset runtime rate and frame period'])
    data['rollback_snapshot_valid'] = not any(item['error'] for item in data['configuration_snapshots'])
    (root / 'preflight.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps({'out': str(root), 'settings_changed': False,
                      'vr_running': data['vr_running'], 'rollback_tested': False,
                      'rollback_snapshot_valid': data['rollback_snapshot_valid']}))
    return 0 if data['rollback_snapshot_valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

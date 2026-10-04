"""CPU-only supervised lease contract; no device or GPU execution."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.quest3 import supervised as s
from tools.quest3 import unattended as u
from tools.quest3 import contention
from xrbench import framebank as fb

class Host:
    def __init__(self): self.stopped=[]; self.changed=False
    def process_identity(self,pid):
        return {'pid':pid,'path':'python.exe' if pid<3 else 'scorer.exe',
                'started_epoch_s':float(pid)+(1 if self.changed else 0),'exited':False}
    def gpu_sample(self): return {'conflicts':[], 'gpu_engine_activity':{'known':True}}
    def stop_owned_runtime(self,row):
        if not u.ownership_matches(row,self.process_identity(row['pid']),row['nonce']): raise u.Refusal('identity changed')
        self.stopped.append(row['pid'])

class SupervisedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name);self.host=Host()
        self.state={'guard_nonce':'nonce','closed':False,'deadline_epoch_s':110,
                    'authorization':{'kind':s.AUTHORITY,'owner_present':True,'evidence':'explicit owner message', 'allow':['frame_bank_pc']},
                    'parent':dict(self.host.process_identity(1),nonce='nonce'),
                    'monitor':dict(self.host.process_identity(2),nonce='nonce',ready=True,sample_epoch_s=99,conflicts=[]),
                    'owned_pc_jobs':[]}
        self.write()
    def write(self): u.atomic_write(self.path/'state.json',self.state)
    def status(self): return s.status_payload(self.path,host=self.host,now=100)
    def test_valid_owner_lease_without_arm_restorer_device_or_vd(self):
        with mock.patch.object(u,'arm_window',side_effect=AssertionError('arm consulted')):
            self.assertTrue(self.status()['lease']['active'])
    def test_health_and_attestation_fail_closed(self):
        cases=[('deadline_epoch_s',100),('closed',True),('deadline_epoch_s',float('nan'))]
        for key,value in cases:
            with self.subTest(key=key,value=value):
                old=copy.deepcopy(self.state);self.state[key]=value;self.write()
                self.assertFalse(self.status()['lease']['active']);self.state=old
        for field,value in [('owner_present',False),('evidence',''),('kind','unattended'),('allow',['chart'])]:
            with self.subTest(field=field):
                old=copy.deepcopy(self.state);self.state['authorization'][field]=value;self.write()
                self.assertFalse(self.status()['lease']['active']);self.state=old
    def test_explicit_away_authorization_is_pc_only_and_records_absence(self):
        self.state['authorization'].update(owner_present=False,owner_authorized_while_away=True)
        self.write()
        status=self.status()
        self.assertTrue(status['lease']['active'])
        self.assertIs(status['authorization']['owner_present'],False)
        self.assertTrue(status['authorization']['owner_authorized_while_away'])
        self.assertFalse(s.status_payload(self.path,host=self.host,now=100,require_allow='chart')['lease']['active'])
        self.state['authorization']['allow']=['frame_bank_pc','chart'];self.write()
        self.assertFalse(self.status()['lease']['active'])
    def test_away_authorization_keeps_every_lease_stop(self):
        self.state['authorization'].update(owner_present=False,owner_authorized_while_away=True)
        for key,value in [('deadline_epoch_s',100),('closed',True)]:
            old=copy.deepcopy(self.state);self.state[key]=value;self.write()
            self.assertFalse(self.status()['lease']['active']);self.state=old
        self.state['monitor']['conflicts']=['free_vram_below_margin'];self.write()
        self.assertFalse(self.status()['lease']['active'])
        self.state['monitor']['conflicts']=[];self.write();(self.path/'stop').touch()
        self.assertFalse(self.status()['lease']['active'])
    def test_away_flag_must_be_boolean_and_session_requires_explicit_authorization(self):
        self.state['authorization'].update(owner_present=False,owner_authorized_while_away='yes');self.write()
        self.assertFalse(self.status()['lease']['active'])
        for kwargs in [dict(owner_present=False),dict(owner_present='no'),
                       dict(owner_present=False,owner_authorized_while_away='yes')]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                with s.session(self.path,evidence='current owner message',duration_s=60,**kwargs):pass
    def test_stale_competing_and_replaced_monitor(self):
        for key,value in [('sample_epoch_s',39),('sample_epoch_s',101),('ready',False),('conflicts',['comfy_queue_active_or_unknown']),('started_epoch_s',5)]:
            with self.subTest(key=key):
                old=copy.deepcopy(self.state);self.state['monitor'][key]=value;self.write()
                self.assertFalse(self.status()['lease']['active']);self.state=old
    def test_stop_marker_and_wrong_scope(self):
        self.assertFalse(s.status_payload(self.path,host=self.host,now=100,require_allow='chart')['lease']['active'])
        (self.path/'stop').touch();self.assertFalse(self.status()['lease']['active'])
    def test_registry_locked_identity_and_monitor_exclusion(self):
        with mock.patch.object(s.time,'time',return_value=100):
            row=s.JobRegistry().register(self.path/'state.json',3,host=self.host)
        sample={'conflicts':['3, scorer.exe, 200','4, competitor.exe, 400']}
        self.assertEqual(u.exclude_owned_compute_jobs(u.json_read(self.path/'state.json'),self.host,sample)['conflicts'],['4, competitor.exe, 400'])
        self.host.changed=True
        self.assertEqual(u.exclude_owned_compute_jobs(u.json_read(self.path/'state.json'),self.host,sample)['conflicts'],sample['conflicts'])
        self.assertTrue(s.stop_jobs({'owned_pc_jobs':[row]},self.host));self.assertEqual(self.host.stopped,[])
        self.host.changed=False
        self.assertEqual(s.stop_jobs({'owned_pc_jobs':[row]},self.host),[]);self.assertEqual(self.host.stopped,[3])
        s.JobRegistry().unregister(self.path/'state.json',3)
        self.assertEqual(u.json_read(self.path/'state.json')['owned_pc_jobs'],[])

    def test_completed_child_uses_parent_poll_evidence_not_registration_snapshot(self):
        with mock.patch.object(s.time,'time',return_value=100):
            s.JobRegistry().register(self.path/'state.json',3,host=self.host)
            completed=s.JobRegistry().unregister(self.path/'state.json',3,completion_observed=True)
        self.assertTrue(completed['exited'])
        self.assertTrue(completed['completion_observed_by_parent'])
        self.assertTrue(u.json_read(self.path/'state.json')['completed_pc_jobs'][0]['exited'])

    def test_monitor_exception_marks_stop_and_runs_owned_cleanup(self):
        self.state['owned_pc_jobs']=[dict(self.host.process_identity(3),nonce='nonce')];self.write()
        self.host.gpu_sample=lambda: (_ for _ in ()).throw(RuntimeError('monitor fault'))
        with mock.patch.object(u,'Host',return_value=self.host),mock.patch.object(s,'_close_owned_jobs',wraps=s._close_owned_jobs) as cleanup:
            with self.assertRaisesRegex(RuntimeError,'monitor fault'):
                s.worker(self.path,'nonce')
        cleanup.assert_called_once_with(self.path/'state.json',self.host,'nonce',reason='monitor_worker_error')
        self.assertTrue((self.path/'stop').exists())
        self.assertTrue(u.json_read(self.path/'state.json')['closed'])

    def test_monitor_death_during_session_runs_parent_cleanup(self):
        class DeadProcess:
            pid = 2
            def poll(self): return 1
            def wait(self, timeout=None): return 1
        with tempfile.TemporaryDirectory() as root:
            private_root = Path(root) / 'results' / 'local'
            window = private_root / 'lease'
            with mock.patch.object(u, 'ROOT', Path(root)), mock.patch.object(u, 'Host', return_value=self.host), \
                 mock.patch.object(s.subprocess, 'Popen', return_value=DeadProcess()), \
                 mock.patch.object(s, 'status_payload', return_value={'lease': {'active': False}}), \
                 mock.patch.object(s, '_close_owned_jobs', wraps=s._close_owned_jobs) as cleanup:
                with self.assertRaisesRegex(u.Refusal, 'monitor startup failed'):
                    with s.session(window, evidence='owner present', duration_s=60):
                        pass
            self.assertTrue((window/'stop').exists())
            cleanup.assert_called_once()
            self.assertEqual(cleanup.call_args.kwargs['reason'], 'session_finally')

    def test_cleanup_rejects_replaced_state_before_stopping_jobs(self):
        self.state['owned_pc_jobs']=[dict(self.host.process_identity(3),nonce='nonce')]
        self.state['guard_nonce']='replacement'; self.write()
        with self.assertRaisesRegex(u.Refusal, 'identity changed'):
            s._close_owned_jobs(self.path/'state.json', self.host, 'nonce', reason='test')
        self.assertEqual(self.host.stopped, [])
    def test_registration_refused_after_stop_or_with_arm(self):
        (self.path/'stop').touch()
        with mock.patch.object(s.time,'time',return_value=100):
            with self.assertRaises(u.Refusal): s.JobRegistry().register(self.path/'state.json',3,host=self.host)
        with self.assertRaises(u.Refusal): s.JobRegistry().register(self.path/'state.json',3,Path('arm'),host=self.host)
    def test_worker_stops_owned_jobs_on_parent_death_without_device_probes(self):
        self.state['parent']['started_epoch_s']=7
        self.state['owned_pc_jobs']=[dict(self.host.process_identity(3),nonce='nonce')];self.write()
        with mock.patch.object(u,'Host',return_value=self.host),mock.patch.object(s.time,'time',return_value=100),mock.patch.object(contention,'telemetry',return_value={'free_vram_mib':8000,'device_error':None}),mock.patch.object(u,'arm_window',side_effect=AssertionError('arm consulted')):
            s.worker(self.path,'nonce')
        self.assertEqual(self.host.stopped,[3]);self.assertTrue((self.path/'stop').exists())
        self.assertTrue(u.json_read(self.path/'state.json')['closed'])
    def test_windowguard_accepts_explicit_supervised_authority_only(self):
        data=self.status()
        response=mock.Mock(returncode=0,stdout=json.dumps(data))
        with mock.patch.object(fb.subprocess,'run',return_value=response) as run:
            self.assertTrue(fb.WindowGuard(self.path,clock=lambda:100,supervised=True).status()['lease']['active'])
            self.assertIn('tools.quest3.supervised',run.call_args.args[0])
            self.assertNotIn('--arm',run.call_args.args[0])
            with self.assertRaises(PermissionError): fb.WindowGuard(self.path,clock=lambda:100).status()
        with self.assertRaises(ValueError): fb.WindowGuard(self.path,arm=Path('arm'),supervised=True)
    def test_session_requires_explicit_evidence_and_finite_duration(self):
        for evidence,duration in [('',60),('owner',float('inf')),('owner',0),('owner',7201)]:
            with self.subTest(evidence=evidence,duration=duration),self.assertRaises(ValueError):
                with s.session(self.path,evidence=evidence,duration_s=duration): pass

    def test_windowguard_accepts_away_only_with_explicit_pc_authorization(self):
        self.state['authorization'].update(owner_present=False,owner_authorized_while_away=True);self.write()
        data=self.status()
        response=mock.Mock(returncode=0,stdout=json.dumps(data))
        with mock.patch.object(fb.subprocess,'run',return_value=response):
            self.assertTrue(fb.WindowGuard(self.path,clock=lambda:100,supervised=True).status()['lease']['active'])
        for field,value in [('owner_authorized_while_away',False),('owner_present',None),('allow',['frame_bank_pc','chart'])]:
            bad=copy.deepcopy(data);bad['authorization'][field]=value
            response.stdout=json.dumps(bad)
            with self.subTest(field=field),mock.patch.object(fb.subprocess,'run',return_value=response):
                with self.assertRaises(PermissionError):fb.WindowGuard(self.path,clock=lambda:100,supervised=True).status()

    def test_cli_start_requires_current_attestation_and_uses_finite_session(self):
        with self.assertRaises(SystemExit): s.main(['start','--window',str(self.path)])
        with mock.patch.object(s,'session') as session, mock.patch.object(s,'status_payload',side_effect=[
                {'lease':{'active':True}},{'lease':{'active':False}}]),mock.patch.object(s.time,'sleep'):
            session.return_value.__enter__.return_value=self.path
            self.assertEqual(s.main(['start','--window',str(self.path),'--owner-attested','Owner: run Q1 now',
                                     '--duration-s','60','--allow','frame_bank_pc']),0)
            session.assert_called_once_with(str(self.path),evidence='Owner: run Q1 now',duration_s=60,
                                            measurement_mode='quality')

    def test_cli_away_authorization_records_absence_without_broadening_scope(self):
        with mock.patch.object(s,'session') as session, mock.patch.object(s,'status_payload',return_value={
                'lease':{'active':False}}):
            session.return_value.__enter__.return_value=self.path
            self.assertEqual(s.main(['start','--window',str(self.path),'--owner-attested','Owner: offline while away',
                                    '--owner-authorized-while-away','--duration-s','60']),0)
            session.assert_called_once_with(str(self.path),evidence='Owner: offline while away',duration_s=60,
                measurement_mode='quality',owner_present=False,owner_authorized_while_away=True)
    def sample(self,pct=80,name='firefox.exe'):
        return {'gpu_engine_activity':{'known':True,'active_pids':{'9':{'max_percent':pct,'engine_types':['3D']}}},
                'nvidia_compute_apps':['9, '+name+', N/A'],'comfy_processes':[],
                'gpu_telemetry':{'free_vram_mib':8000,'overall_load_percent':99,'device_error':None}}
    def test_quality_ignores_browser_load_but_stops_compute_vram_and_errors(self):
        sample=self.sample()
        self.assertEqual(contention.evaluate(sample,mode='quality',now=100)['stop_reasons'],[])
        sample['nvidia_compute_apps']=['9, python.exe, N/A']
        self.assertIn('compute_backend_active_or_unknown',contention.evaluate(sample,mode='quality',now=100)['stop_reasons'])
        sample['excluded_owned_pids']=['9']
        self.assertEqual(contention.evaluate(sample,mode='quality',now=100)['stop_reasons'],[])
        sample['comfy_processes']=[{}];sample['comfy']={'known':True,'running':1,'pending':0}
        self.assertIn('comfy_queue_active_or_unknown',contention.evaluate(sample,mode='quality',now=100)['stop_reasons'])
        sample=self.sample();sample['gpu_telemetry']['free_vram_mib']=2047
        self.assertIn('free_vram_below_margin',contention.evaluate(sample,mode='quality',now=100)['stop_reasons'])
        sample['gpu_telemetry']['device_error']='device lost'
        self.assertIn('gpu_driver_or_device_error',contention.evaluate(sample,mode='quality',now=100)['stop_reasons'])
        sample['stop_requested']=True
        self.assertIn('stop_requested',contention.evaluate(sample,mode='quality',now=100)['stop_reasons'])
    def test_timing_sustained_external_load_invalidates_only_measurement(self):
        sample=self.sample()
        first=contention.evaluate(sample,mode='timing',now=100)
        self.assertEqual(first['timing_invalidation_reasons'],[])
        almost=contention.evaluate(sample,mode='timing',now=109.9,above_since=first['above_since_epoch_s'])
        self.assertEqual(almost['timing_invalidation_reasons'],[])
        sustained=contention.evaluate(sample,mode='timing',now=110,above_since=first['above_since_epoch_s'])
        self.assertEqual(sustained['stop_reasons'],[])
        self.assertEqual(sustained['timing_invalidation_reasons'],['sustained_external_gpu_load'])
        self.assertIsNone(contention.evaluate(self.sample(10),mode='timing',now=111,above_since=100)['above_since_epoch_s'])
        sample['excluded_owned_pids']=['9']
        self.assertEqual(contention.evaluate(sample,mode='timing',now=120,above_since=100)['timing_invalidation_reasons'],[])
        sample=self.sample(1,'ollama.exe')
        decision=contention.evaluate(sample,mode='timing',now=100)
        self.assertEqual(decision['stop_reasons'],[])
        self.assertIn('compute_backend_active_or_unknown',decision['timing_invalidation_reasons'])

if __name__=='__main__': unittest.main()

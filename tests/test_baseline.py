import unittest

from tools.quest3.baseline import acceptance, baseline_plan


class BaselineTests(unittest.TestCase):
    def expected(self):
        return {'render_resolution': {'width': 3100, 'height': 3200},
                'encoded_resolution': {'width': 3300, 'height': 3400},
                'requested_hz': 90, 'minimum_duration_s': 1800, 'mbps':400}

    def passing_report(self):
        settings = dict(self.expected(), negotiated_hz=90,
                        negotiated_render_resolution=self.expected()['render_resolution'],
                        negotiated_encoded_resolution=self.expected()['encoded_resolution'],
                        hdr_enabled=False,hdr_server_override=True, codec='PyroWave',transport='Tcp',
                        chroma='420',decode_path='Compute',wavelet='Cdf97', bitrate_mode='ConstantMbps',
                        target_mbps=400,enforce_server_frame_pacing=True,foveated_encoding_enabled=False,
                        clientside_foveation_enabled=False,effective_pyrowave={'enabled':True,'transport':'Tcp',
                        'chroma':'420','wavelet':'Cdf97','decode_path':'Compute','foveated_encoding':False})
        return {'status': 'measured', 'frames': 2, 'elapsed_s': 1800, 'submission_rate_window_s':1800,
                'settings_start': settings, 'settings_end': settings,
                'fresh_runtime_evidence': True, 'build_identity': {'server': 'x'},
                'build_identity_verified': True, 'telemetry_complete': True,
                'benchmark_tool_provenance':{'verified':True},
                'thermal_ok': True, 'stream_errors': [], 'controllers_ok': True, 'audio_ok':True,
                'tracking_ok':True, 'image_ok': True, 'manual_confirmation': True,
                'metro_clarity_ok':True, 'metro_motion_ok':True,
                'no_disconnects_ok':True, 'no_crashes_ok':True,
                'pyrowave_counter_window':{'counter_deltas':{'decode_failures':0,'complete':1}},
                'experiment_options_start':{'verified':True,'enabled':{},'effective_pyro_precision':'1',
                    'effective_early_poll':True,'effective_perf_level':'sustained_high'},
                'experiment_options_end':{'verified':True,'enabled':{},'effective_pyro_precision':'1',
                    'effective_early_poll':True,'effective_perf_level':'sustained_high'},
                'runtime_evidence_coverage':{'status':'covered'},
                'rate_stability':{'status':'stable'}, 'sustained_requested_fps': True}

    def test_plan_is_bounded_and_800_is_gated(self):
        plan = baseline_plan({'width':3100, 'height':3200}, {'width':3300, 'height':3400})
        self.assertEqual([cell['mbps'] for cell in plan['cells'] if cell['phase'] == 'target-screen' and cell['requested_hz'] == 90], [300,400,600])
        self.assertEqual(plan['gated'][0]['mbps'], 800)
        self.assertTrue(any(cell['phase']=='vd-reference' for cell in plan['cells']))
        self.assertTrue(any(cell['phase']=='alvr-hevc-control' for cell in plan['cells']))
        self.assertFalse(next(cell for cell in plan['cells'] if cell['phase']=='diagnostic')['acceptance_eligible'])
        self.assertEqual(plan['defaults']['transport'], 'Tcp')
        report = self.passing_report()
        self.assertTrue(acceptance(report, plan, 400)['accepted'])

    def test_no_frames_and_unknown_manual_confirmation_fail(self):
        report = self.passing_report(); report.update({'frames':0, 'manual_confirmation':None})
        result = acceptance(report, self.expected())
        self.assertFalse(result['accepted'])
        self.assertIn('no_fresh_stream_frames', result['failure_reasons'])
        self.assertIn('manual_confirmation_missing', result['failure_reasons'])

    def test_missing_identity_settings_change_and_stale_runtime_fail(self):
        report = self.passing_report(); report['build_identity_verified'] = False
        report['fresh_runtime_evidence'] = False
        report['settings_end'] = dict(report['settings_end'], requested_hz=72)
        reasons = acceptance(report, self.expected())['failure_reasons']
        self.assertIn('build_identity_unverified', reasons)
        self.assertIn('missing_fresh_runtime_evidence', reasons)
        self.assertIn('settings_changed_during_capture', reasons)

    def test_mismatched_runtime_and_diagnostic_dimensions_fail(self):
        report = self.passing_report(); report['settings_start']['negotiated_hz'] = 72
        report['settings_end']['negotiated_hz'] = 72
        report['settings_start']['encoded_resolution'] = {'width':2080,'height':2208}
        report['settings_end']['encoded_resolution'] = {'width':2080,'height':2208}
        reasons = acceptance(report, self.expected())['failure_reasons']
        self.assertIn('runtime_rate_mismatch', reasons)
        self.assertIn('encoded_resolution_mismatch', reasons)

    def test_truncated_capture_fails(self):
        report = self.passing_report(); report['submission_rate_window_s'] = 1799
        self.assertIn('capture_too_short', acceptance(report, self.expected())['failure_reasons'])

    def test_duplicate_frames_fail(self):
        report = self.passing_report(); report['duplicate_frame_events'] = 1
        self.assertIn('duplicate_frame_events', acceptance(report, self.expected())['failure_reasons'])

    def test_decoder_failure_counter_fails(self):
        report = self.passing_report()
        report['pyrowave_counter_window'] = {'counter_deltas': {'decode_failures': 1}}
        self.assertIn('decoder_failures_reported', acceptance(report, self.expected())['failure_reasons'])

    def test_missing_counter_and_stream_status_fail_closed(self):
        report = self.passing_report(); report.pop('stream_errors'); report.pop('pyrowave_counter_window')
        reasons=acceptance(report, {'requested_hz':90})['failure_reasons']
        self.assertIn('stream_error_status_missing', reasons)
        self.assertIn('decoder_failure_counter_missing', reasons)

    def test_missing_submission_window_and_non_90_target_fail(self):
        report=self.passing_report(); report['submission_rate_window_s']=None
        reasons=acceptance(report, dict(self.expected(), requested_hz=72))['failure_reasons']
        self.assertIn('capture_too_short', reasons)
        self.assertIn('target_acceptance_requires_90hz', reasons)

    def test_enabled_hidden_experiment_and_missing_fresh_counter_fail(self):
        report=self.passing_report()
        report['experiment_options_end']={'verified':True,'enabled':{'direct_eye_copy':True}}
        report['pyrowave_counter_window']['counter_deltas']['complete']=None
        reasons=acceptance(report, self.expected())['failure_reasons']
        self.assertIn('experiment_options_changed_during_capture', reasons)
        self.assertIn('experiment_options_unverified_or_enabled', reasons)
        self.assertIn('fresh_frame_counter_missing', reasons)

    def test_target_bitrate_must_be_selected_and_match(self):
        report=self.passing_report()
        self.assertIn('selected_target_bitrate_missing', acceptance(report, dict(self.expected(), mbps=None))['failure_reasons'])
        self.assertIn('target_bitrate_mismatch', acceptance(report, dict(self.expected(), mbps=600))['failure_reasons'])

import unittest
from unittest.mock import patch
from tools.quest3.bench import parse_capabilities,plan,summarise,distribution,pyrowave_counter_window, fresh_rate_evidence, build_identity_verified, merge_review, rate_stability, filter_runtime_evidence, measurement_clock, measurement_clock_info, selected_output_window, selected_output_stability, SELECTED_OUTPUT_SOURCE

class BenchTests(unittest.TestCase):
    def test_selected_output_rejects_reset_gap_and_wrong_source(self):
        good=[(0,0,SELECTED_OUTPUT_SOURCE),(10,900,SELECTED_OUTPUT_SOURCE)]
        self.assertTrue(selected_output_window(good)['valid'])
        self.assertEqual(selected_output_window([(0,2,SELECTED_OUTPUT_SOURCE),(5,1,SELECTED_OUTPUT_SOURCE)])['reason'],'selected_output_counter_reset')
        self.assertEqual(selected_output_window([(0,0,SELECTED_OUTPUT_SOURCE),(20,100,SELECTED_OUTPUT_SOURCE)])['reason'],'selected_output_coverage_gap')
        self.assertEqual(selected_output_window([(0,0,'wrong'),(5,100,'wrong')])['reason'],'selected_output_source_unverified')
        self.assertEqual(selected_output_window([(-1,0,SELECTED_OUTPUT_SOURCE),(5,100,SELECTED_OUTPUT_SOURCE)])['reason'],'selected_output_counter_invalid')
        self.assertEqual(selected_output_window([(1,0,SELECTED_OUTPUT_SOURCE),(10,810,SELECTED_OUTPUT_SOURCE)],capture_end_elapsed=30)['reason'],'selected_output_capture_coverage_incomplete')
        self.assertTrue(selected_output_window([(1,0,SELECTED_OUTPUT_SOURCE),(10,810,SELECTED_OUTPUT_SOURCE)],capture_end_elapsed=20)['valid'])

    def test_selected_output_endurance_rejects_slow_window(self):
        # A real 1810-second capture may first report at t=1; six complete
        # 300-second windows through t=1801 must still qualify.
        rows=[(1+i*10, i*10*90, SELECTED_OUTPUT_SOURCE) for i in range(181)]
        self.assertEqual(selected_output_stability(rows,90)['status'],'stable')
        rows[120:]=[(1+i*10, 81100+(i-120)*900, SELECTED_OUTPUT_SOURCE) for i in range(120,181)]
        self.assertEqual(selected_output_stability(rows,90)['status'],'pending_or_failed')

    def test_capture_clock_uses_perf_counter_not_coarse_monotonic(self):
        # Capture timing must go through the QPC-backed abstraction. On Windows,
        # monotonic may otherwise be a 15.625 ms GetTickCount64 clock.
        with patch('tools.quest3.bench.time.perf_counter', return_value=12.5) as perf, \
             patch('tools.quest3.bench.time.monotonic', side_effect=AssertionError('coarse clock used')):
            self.assertEqual(measurement_clock(), 12.5)
            perf.assert_called_once_with()
        info=measurement_clock_info()
        self.assertEqual(info['name'], 'perf_counter')
        self.assertTrue(info['monotonic'])
        self.assertGreater(info['resolution_s'], 0)

    def test_unprobed_rates_are_not_declared_unsupported(self):
        caps=parse_capabilities('[Q3PW_CAPS] model=Quest3 rates=[72.0, 90.0, 120.0] runtime=true')
        p=plan(caps,repeats=1)
        self.assertEqual([r['requested_hz'] for r in p['skipped']],[144,207,240])
        self.assertEqual(len(p['cells']),45)
        self.assertTrue(all(r['status']=='not_confirmed' for r in p['skipped']))
        self.assertTrue(all(c['requested_hz'] in (72,90,120) for c in p['cells']))
        baseline=[c for c in p['cells'] if c['codec']=='PyroWave'
                  and c['requested_hz']==72 and c['mbps']==400]
        self.assertEqual({c['decode_path'] for c in baseline},{'Compute','Fragment'})
        self.assertTrue(all(c['chroma']=='420' and c['transport']=='Tcp' for c in baseline))
    def test_probe_can_confirm_non_enumerated_rates(self):
        caps=parse_capabilities('[Q3PW_CAPS] model=Quest3 rates=[90.0,120.0] runtime=true\n'
            '[Q3PW_PROBE] request=207 confirmed=true runtime_hz=Some(207.0) period_ns=4830918\n'
            '[Q3PW_CAPS] model=Quest3 rates=[90.0,120.0,207.0] runtime=true source=probe')
        self.assertEqual(caps['source'],'request_and_frame_period')
        self.assertEqual(caps['probe_results'],[{'requested_hz':207,'confirmed':True}])
        self.assertIn(207,{c['requested_hz'] for c in plan(caps,1)['cells']})
    def test_newest_capability_record_wins(self):
        caps=parse_capabilities('[Q3PW_CAPS] model=Quest3 rates=[90.0] runtime=true\n[Q3PW_CAPS] model=Quest3 rates=[90.0, 144.0] runtime=true')
        self.assertEqual(caps['rates_hz'],[90,144])
    def test_missing_and_fallback_capabilities_refused(self):
        with self.assertRaises(ValueError):parse_capabilities('debug.oculus.refreshRate=240')
        with self.assertRaises(ValueError):plan({'rates_hz':[90], 'refresh_extension':False})
    def test_no_frames_is_failure_not_zero_latency(self):
        r=summarise([])
        self.assertEqual(r['status'],'no_stream_frames');self.assertIsNone(r['metrics']['encoder_ms'])
    def test_pipeline_units_and_counter_delta(self):
        events=[{'event_type':{'id':'GraphStatistics','data':{'encoder_s':.002,'client_fps':90,'target_timestamp_ns':100}}},
                {'event_type':{'id':'StatisticsSummary','data':{'packets_lost_total':100}}},
                {'event_type':{'id':'StatisticsSummary','data':{'packets_lost_total':105}}}]
        r=summarise(events,90)
        self.assertEqual(r['metrics']['encoder_ms']['p50'],2);self.assertEqual(r['packet_loss_delta'],5)
        self.assertIsNone(r['optical_motion_to_photon_ms'])
    def test_percentiles_filter_invalid_numbers(self):
        self.assertEqual(distribution([None,float('nan'),1,3])['p50'],2)

    def test_eye_copy_paths_use_window_deltas_and_wall_timings(self):
        events=[{'event_type':{'id':'HeadsetTelemetry','data':{'pyrowave':p}}}
            for p in [
                {'direct_eye_copies':100,'staging_eye_copies':40,'eye_render_ms':[3.0],
                 'eye_acquire_wait_ms':[0.2],'eye_release_ms':[0.1]},
                {'direct_eye_copies':120,'staging_eye_copies':40,'eye_render_ms':[4.0]}]]
        r=summarise(events)
        self.assertEqual(r['eye_copy_counter_deltas'],{'direct_eye_copies':20,'staging_eye_copies':0,
            'completed_eye_copies':None,'pending_eye_copy_deferrals':None})
        self.assertEqual(r['eye_render_ms']['p50'],3.5)
        self.assertEqual(r['eye_acquire_wait_ms']['p50'],0.2)
        events.append({'event_type':{'id':'HeadsetTelemetry','data':{'pyrowave':{
            'direct_eye_copies':2,'staging_eye_copies':0}}}})
        self.assertIsNone(summarise(events)['eye_copy_counter_deltas']['direct_eye_copies'])
        self.assertIsNone(summarise([])['eye_copy_counter_deltas']['staging_eye_copies'])

    def test_submission_rate_exposes_missed_slots(self):
        from tools.quest3.bench import summarise
        events=[{'capture_elapsed_s':t,'event':{'event_type':{
            'id':'GraphStatistics','data':{'client_fps':fps}}}}
            for t,fps in [(0,120),(1/120,120),(2/120,120),(4/120,60)]]
        report=summarise(events,120)
        self.assertAlmostEqual(report['submitted_frame_rate_fps'],90)
        self.assertEqual(report['metrics']['client_fps']['p50'],120)
        self.assertFalse(report['sustained_requested_fps'])

    def test_nominal_fps_does_not_hide_sparse_submissions(self):
        events=[{'capture_elapsed_s':t,'event':{'event_type':{
            'id':'GraphStatistics','data':{'client_fps':120}}}}
            for t in (0,1/120,4/120)]
        r=summarise(events,120)
        self.assertEqual(r['metrics']['client_fps']['p01'],120)
        self.assertAlmostEqual(r['submitted_frame_rate_fps'],60)
        self.assertFalse(r['sustained_requested_fps'])

    def test_reused_tracking_timestamp_is_diagnostic_not_a_rate_failure(self):
        events=[{'capture_elapsed_s':t,'event':{'event_type':{
            'id':'GraphStatistics','data':{'client_fps':90,'target_timestamp_ns':stamp}}}}
            for t,stamp in ((0,1),(1/90,1),(2/90,1))]
        report=summarise(events,90)
        self.assertEqual(report['duplicate_frame_events'], 2)
        self.assertEqual(report['target_timestamp_reuse_events'], 2)
        self.assertEqual(report['distinct_target_timestamp_count'], 1)
        self.assertEqual(report['fresh_frames'], 1) # Legacy distinct-timestamp alias.
        self.assertAlmostEqual(report['selected_submission_event_rate_fps'],90)
        self.assertTrue(report['requested_rate_screen_passed'])
        self.assertFalse(report['fresh_frame_identity_verified'])

    def test_repeated_arrival_timestamps_do_not_fabricate_a_submission_rate(self):
        events=[{'capture_elapsed_s':0,'event':{'event_type':{
                    'id':'GraphStatistics','data':{'client_fps':90,'target_timestamp_ns':1}}}},
                {'capture_elapsed_s':0,'event':{'event_type':{
                    'id':'GraphStatistics','data':{'client_fps':90,'target_timestamp_ns':2}}}}]
        report=summarise(events,90)
        self.assertIsNone(report['selected_submission_event_rate_fps'])
        self.assertFalse(report['requested_rate_screen_passed'])

    def test_queued_copies_cannot_hide_slow_completion(self):
        events=[{'capture_elapsed_s':t,'event':{'event_type':{
            'id':'GraphStatistics','data':{'client_fps':120}}}}
            for t in (0,1/120,2/120)]
        events += [{'capture_elapsed_s':t,'event':{'event_type':{
            'id':'HeadsetTelemetry','data':{'pyrowave':{'completed_eye_copies':n,
                'direct_eye_copies':n+20,'staging_eye_copies':0,
                'pending_eye_copy_deferrals':d,'eye_completion_observed_ms':[8.5]}}}}}
            for t,n,d in [(0,10,1),(1,110,21)]]
        r=summarise(events,120)
        self.assertEqual(r['completed_eye_copy_rate_fps'],100)
        self.assertEqual(r['eye_copy_counter_deltas']['pending_eye_copy_deferrals'],20)
        self.assertFalse(r['sustained_requested_fps'])
        events[-1]['event']['event_type']['data']['pyrowave']['staging_eye_copies']=1
        self.assertIsNone(summarise(events)['completed_eye_copy_rate_fps'])
        events[-1]['event']['event_type']['data']['pyrowave']['staging_eye_copies']=0
        events[-1]['event']['event_type']['data']['pyrowave']['completed_eye_copies']=9
        self.assertIsNone(summarise(events)['completed_eye_copy_rate_fps'])

    def test_producer_and_consumer_rates_have_matching_endpoints(self):
        samples=[(t,{'complete':c,'superseded':s,'completed_eye_copies':e,
            'decode_failures':0}) for t,c,s,e in [(5,500,20,480),(6,620,27,593),(7,740,34,706)]]
        w=pyrowave_counter_window(samples)
        self.assertEqual(w['interval_s'],2)
        self.assertEqual(w['counter_deltas']['complete'],240)
        self.assertEqual(w['counter_rates_per_s']['complete'],120)
        self.assertEqual(w['counter_rates_per_s']['superseded'],7)
        self.assertEqual(w['counter_rates_per_s']['completed_eye_copies'],113)
        self.assertEqual(w['counter_deltas']['decode_failures'],0)
        self.assertIsNone(w['counter_deltas']['partial'])
        # A reset in the middle must not look valid after the counter catches up.
        samples[1][1]['complete']=1
        self.assertIsNone(pyrowave_counter_window(samples)['counter_deltas']['complete'])

    def test_invalid_telemetry_times_cannot_be_silently_excluded(self):
        for middle in (None,True,float('nan'),-1,0,3):
            samples=[(0,{'complete':0}),(middle,{'complete':120}),(2,{'complete':240})]
            w=pyrowave_counter_window(samples)
            self.assertEqual(w['counter_deltas']['complete'],240)
            self.assertIsNone(w['interval_s'])
            self.assertIsNone(w['counter_rates_per_s']['complete'])
        w=pyrowave_counter_window([(0,{'complete':False}),(1,{'complete':120})])
        self.assertIsNone(w['counter_deltas']['complete'])

    def test_short_rate_pass_is_not_sustained_acceptance(self):
        events=[{'capture_elapsed_s':i/120,'event':{'event_type':{
            'id':'GraphStatistics','data':{'client_fps':120}}}}
            for i in range(1801)]
        r=summarise(events,120)
        self.assertEqual(r['submission_rate_window_s'],15)
        self.assertTrue(r['requested_rate_screen_passed'])
        self.assertFalse(r['sustained_requested_fps'])

    def test_sustained_rate_check_needs_five_minutes_of_observed_frames(self):
        events=[{'capture_elapsed_s':i/120,'event':{'event_type':{
            'id':'GraphStatistics','data':{'client_fps':120}}}}
            for i in range(36001)]
        short=summarise(events[:-1],120)
        self.assertTrue(short['requested_rate_screen_passed'])
        self.assertFalse(short['sustained_requested_fps'])
        full=summarise(events,120)
        self.assertEqual(full['submission_rate_window_s'],300)
        self.assertTrue(full['sustained_requested_fps'])
        # A long but sparse submission stream still cannot pass at nominal 120.
        slow=summarise(events[::2],120)
        self.assertFalse(slow['requested_rate_screen_passed'])
        self.assertFalse(slow['sustained_requested_fps'])

    def test_missing_or_invalid_submission_times_invalidate_rate_window(self):
        for middle in (None,True,float('nan'),-1,0,3):
            events=[{'capture_elapsed_s':t,'event':{'event_type':{
                'id':'GraphStatistics','data':{'client_fps':120}}}}
                for t in (0,middle,2)]
            r=summarise(events,120)
            self.assertIsNone(r['submitted_frame_rate_fps'])
            self.assertIsNone(r['submission_rate_window_s'])
            self.assertFalse(r['requested_rate_screen_passed'])
            self.assertFalse(r['sustained_requested_fps'])

    def test_fresh_effective_rate_and_build_version_must_match(self):
        line='[Q3PW_EFFECTIVE] requested=Some(90.0) runtime_hz=Ok(90.0) period_ns=11111111'
        self.assertTrue(fresh_rate_evidence([line], 90))
        self.assertFalse(fresh_rate_evidence([line], 72))
        self.assertFalse(fresh_rate_evidence(['[Q3PW_EFFECTIVE] requested=Some(90.0) runtime_hz=Some(90.0) period_ns=20000000'], 90))
        self.assertFalse(fresh_rate_evidence([line, '[Q3PW_EFFECTIVE] requested=Some(90.0) runtime_hz=Some(72.0) period_ns=13888888'], 90))
        manifest={'schema_version':1,'application_version':'20.13.0-ljk1291.1+abc','protocol_version':'x',
            'client_package_id':'io.github.ljk1291.quest3pyrowave','repository_commit':'a','sources_lock_sha256':'a',
            'dependency_revisions':{'a':'b'},'shader_hashes':{'a':'b'},'artifact_sha256':{'a':'b'},
            'signing_certificate_sha256':'a'}
        self.assertTrue(build_identity_verified(manifest, {'server_version':'20.13.0-ljk1291.1+abc'},
            {'version':'20.13.0-ljk1291.1+abc'}))
        self.assertFalse(build_identity_verified(manifest, {'server_version':'other'},
            {'version':'20.13.0-ljk1291.1+abc'}))

    def test_experiment_properties_record_raw_and_do_not_assume_flip_default(self):
        from tools.quest3.bench import experiment_effective, EXPERIMENT_PROPERTIES
        state={'property:'+name:{'value':'','error':None} for name in EXPERIMENT_PROPERTIES}
        result=experiment_effective(state)
        self.assertTrue(result['verified'])
        self.assertFalse(any(result['enabled'].values()))
        self.assertTrue(result['effective_direct_flip_y'])
        state['property:debug.q3pw.direct_eye_copy']['value']='1'
        self.assertTrue(experiment_effective(state)['enabled']['direct_eye_copy'])
        state['property:debug.q3pw.direct_eye_copy']['value']=''
        state['property:debug.oculus.forceDisplayScaling']['value']='1'
        self.assertTrue(experiment_effective(state)['enabled']['display_scaling'])

    def test_effective_wavelet_prefers_haar_over_cdf53(self):
        from tools.quest3.bench import effective_pyrowave_config
        self.assertEqual(effective_pyrowave_config({'pyrowave_wavelet_haar':True,
            'pyrowave_wavelet_53':True})['wavelet'], 'Haar')

    def test_timestamp_cursor_survives_marker_rotation_without_raw_logs(self):
        log='1710000005.1 1 1 E App: [Q3PW_EFFECTIVE] requested=Some(90.0) runtime_hz=Some(90.0) period_ns=11111111\n'
        self.assertEqual(len(filter_runtime_evidence(log, since_epoch=1710000000.0)),1)
        self.assertEqual(filter_runtime_evidence(log, capture_id='gone'),[])

    def test_runtime_coverage_rejects_missing_or_gapped_polls(self):
        from tools.quest3.bench import runtime_coverage
        self.assertEqual(runtime_coverage([{'elapsed_s':1,'records':1},{'elapsed_s':7,'records':1}],10)['status'],'covered')
        self.assertEqual(runtime_coverage([{'elapsed_s':1,'records':1},{'elapsed_s':20,'records':1}],25)['status'],'incomplete')
        self.assertEqual(runtime_coverage([{'elapsed_s':0.1,'records':0},{'elapsed_s':5,'records':1}],10)['status'],'covered')
        self.assertEqual(runtime_coverage([{'elapsed_s':5,'records':1},{'elapsed_s':10,'records':0}],30)['status'],'incomplete')

    def test_missing_property_readback_cannot_certify_defaults(self):
        from tools.quest3.bench import experiment_effective
        self.assertFalse(experiment_effective({})['verified'])

    def test_negotiated_render_and_stream_dimensions_are_not_reversed(self):
        from unittest.mock import patch
        from tools.quest3.bench import active_settings
        session={'session_settings':{'video':{
            'bitrate':{'mode':{'variant':'ConstantMbps','ConstantMbps':400}},
            'preferred_codec':{'variant':'PyroWave'},'preferred_fps':90,
            'pyrowave':{'decode_path':{'variant':'Compute'},'wavelet':{'variant':'Cdf97'},'transport':{'variant':'Tcp'}},
            'transcoding_view_resolution':{'variant':'Absolute','Absolute':{'width':3200,'height':{'set':True,'content':3200}}},
            'emulated_headset_view_resolution':{'variant':'Absolute','Absolute':{'width':4000,'height':{'set':True,'content':4000}}}},
            'connection':{'stream_protocol':{'variant':'Tcp'}}},
            'openvr_config':{'eye_resolution_width':3200,'eye_resolution_height':3200,
                             'target_eye_resolution_width':4000,'target_eye_resolution_height':4000}}
        with patch('tools.quest3.control.session',return_value=session):
            settings=active_settings()
        self.assertEqual(settings['encoded_resolution'],settings['negotiated_encoded_resolution'])
        self.assertEqual(settings['render_resolution'],settings['negotiated_render_resolution'])

    def test_review_must_be_bound_to_its_capture(self):
        report={'capture_id':'capture-a'}
        self.assertNotIn('image_ok', merge_review(report, {'capture_id':'other','image_ok':True}))
        merged=merge_review(report, {'capture_id':'capture-a','image_ok':True,'controllers_ok':True,
            'audio_ok':True,'tracking_ok':True,'manual_confirmation':True,
            'metro_clarity_ok':True,'metro_motion_ok':True,'no_competing_gpu_workload':True})
        self.assertTrue(merged['image_ok'])
        self.assertTrue(merged['no_competing_gpu_workload'])
        self.assertEqual(merged['operator_review']['capture_id'],'capture-a')

    def test_endurance_windows_report_pending_until_all_six_are_observed(self):
        short=[(i/90,{'client_fps':90}) for i in range(90*300+1)]
        self.assertEqual(rate_stability(short,90)['status'],'pending_or_failed')

if __name__=='__main__':unittest.main()

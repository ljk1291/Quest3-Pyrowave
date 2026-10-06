import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from tempfile import TemporaryDirectory

from tools.quest3.frame_loss_analysis import analyze, COUNTERS, STAGES
from tools.quest3.frame_loss_profiles import install, CELLS, PROPERTIES, PROPERTY_DEFAULTS


class FrameLossAnalysisTests(unittest.TestCase):
    def capture(self, records):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name)
        (path / 'events.jsonl').write_text(''.join(json.dumps(record) + '\n' for record in records))
        return path

    @staticmethod
    def event(time, kind, data):
        return {'capture_elapsed_s': time, 'event': {'event_type': {'id': kind, 'data': data}}}

    def test_counter_windows_and_skip_neighbors(self):
        records = []
        for i, ns in enumerate([0, 11_111_111, 33_333_333, 44_444_444]):
            records.append(self.event(i, 'GraphStatistics', {
                'target_timestamp_ns': ns, **dict.fromkeys(STAGES, i / 1000)}))
        first = dict.fromkeys(COUNTERS, 0)
        last = {**first, 'complete': 90, 'superseded': 5, 'completed_eye_copies': 85}
        records.extend([self.event(0.5, 'HeadsetTelemetry', {'pyrowave': first}),
                        self.event(1.5, 'HeadsetTelemetry', {'pyrowave': last})])
        result = analyze(self.capture(records))
        self.assertEqual(result['gap_multiples'], {1: 2, 2: 1})
        self.assertEqual(result['median_ms']['before_x2']['decoder_queue_s'], 1)
        self.assertEqual(result['median_ms']['after_x2']['decoder_queue_s'], 2)
        self.assertEqual(result['paired_after_minus_before_ms']['vsync_queue_s'], 1)
        self.assertEqual(result['telemetry_span_s'], 1)
        self.assertEqual(result['decoded_minus_superseded_minus_copied'], 0)

    def test_no_graphs_still_accounts_for_decode_and_copy(self):
        records = [self.event(t, 'HeadsetTelemetry', {'pyrowave': {
            **dict.fromkeys(COUNTERS, 0), 'complete': 100 + 110 * t,
            'superseded': 20 * t, 'completed_eye_copies': 90 * t}}) for t in (0, 1)]
        result = analyze(self.capture(records))
        self.assertEqual(result['graph_frames'], 0)
        self.assertEqual(result['counter_deltas']['complete'], 110)
        self.assertEqual(result['decoded_minus_superseded_minus_copied'], 0)

    def test_restart_is_not_a_negative_drop_count(self):
        records = [self.event(t, 'HeadsetTelemetry', {'pyrowave': dict.fromkeys(COUNTERS, n)})
                   for t, n in [(0, 100), (1, 5), (2, 110)]]
        with self.assertRaisesRegex(ValueError, 'split capture'):
            analyze(self.capture(records))


class FrameLossProfilesTests(unittest.TestCase):
    def test_variants_and_snapshot_property_inventory(self):
        def base(name):
            return {'cell': name, 'properties': {'debug.q3pw.runtime_display_time': '0',
                    'debug.q3pw.frame_wait_us': '0'}, 'settings': {
                    'session_settings.video.enforce_server_frame_pacing': name != 'crop-nopace'}}
        harness = SimpleNamespace(profile=base, ORDER=('sanity', 'crop-500', 'crop-nopace'),
                                  MANAGED_PROPERTIES=())
        install(harness)
        for key in PROPERTIES:
            self.assertIn(key, harness.MANAGED_PROPERTIES)
            self.assertEqual(harness.profile('sanity')['properties'][key], PROPERTY_DEFAULTS[key])
        for name in CELLS:
            spec = harness.profile(name)
            self.assertEqual(spec['cell'], name)
            self.assertEqual(spec['properties']['debug.q3pw.frame_loss'], '1')
            self.assertEqual(spec['properties']['debug.q3pw.stats_source_ts'], '1')
        self.assertEqual(harness.profile('loss-runtime500')['properties']['debug.q3pw.runtime_display_time'], '1')
        self.assertEqual(harness.profile('loss-wait500')['properties']['debug.q3pw.frame_wait_us'], '1000')
        nopace = harness.profile('loss-nopace500')['settings']
        self.assertFalse(nopace['session_settings.video.enforce_server_frame_pacing'])
        self.assertEqual(nopace['session_settings.connection.statistics_history_size'], 1024)

    def test_queue_cells_reset_to_control_and_keep_pacing_and_stats_identity(self):
        def base(name):
            return {'cell': name, 'properties': {
                'debug.q3pw.frame_wait_us': '0', 'debug.q3pw.runtime_display_time': '0',
                'debug.q3pw.decode_handoff': '1', 'debug.q3pw.decode_workers': '2',
                'debug.q3pw.output_queue': '3', 'debug.q3pw.output_queue_max_age_us': '1'},
                'settings': {'session_settings.video.enforce_server_frame_pacing': True,
                             'session_settings.video.bitrate.mode.ConstantMbps': 500}}
        harness = SimpleNamespace(profile=base, ORDER=(), MANAGED_PROPERTIES=())
        install(harness)
        for name, depth, wait in [('queue2-500', '2', '0'), ('queue2-wait-500', '2', '1000'),
                                  ('loss-control500', '1', '0'), ('loss-wait500', '1', '1000')]:
            with self.subTest(name=name):
                spec = harness.profile(name)
                props = spec['properties']
                self.assertEqual(props['debug.q3pw.output_queue'], depth)
                self.assertEqual(props['debug.q3pw.output_queue_max_age_us'], '22223')
                self.assertEqual(props['debug.q3pw.frame_wait_us'], wait)
                self.assertEqual(props['debug.q3pw.runtime_display_time'], '0')
                self.assertEqual(props['debug.q3pw.decode_handoff'], '0')
                self.assertEqual(props['debug.q3pw.decode_workers'], '1')
                self.assertEqual(props['debug.q3pw.stats_source_ts'], '1')
                self.assertTrue(spec['settings']['session_settings.video.enforce_server_frame_pacing'])
                self.assertEqual(spec['settings']['session_settings.video.bitrate.mode.ConstantMbps'], 500)


if __name__ == '__main__':
    unittest.main()

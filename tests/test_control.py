import unittest
from unittest.mock import patch
from tools.quest3.control import apply, CLIENT_PACKAGE_ID, experiment_properties


class ControlTests(unittest.TestCase):
    def apply_offline(self, **kwargs):
        current = {}
        def write(values):
            for path, value in values.items():
                node = current
                fields = path.split('.')
                for field in fields[:-1]:
                    node = node.setdefault(field, {})
                node[fields[-1]] = value
        with patch('tools.quest3.control.set_values', side_effect=write), \
                patch('tools.quest3.control.session', return_value=current):
            result = apply('PyroWave', 400, 72, 'Auto',
                           {'refresh_extension': True, 'rates_hz': [72]}, **kwargs)
        return result, current['session_settings']

    def test_default_is_reliable_420_without_performance_claim(self):
        result, settings = self.apply_offline()
        self.assertEqual(settings['video']['pyrowave']['transport']['variant'], 'Tcp')
        self.assertEqual(settings['connection']['stream_protocol']['variant'], 'Tcp')
        self.assertFalse(settings['video']['pyrowave']['chroma_444'])
        self.assertFalse(settings['video']['encoder_config']['hdr']['enable_hdr'])
        self.assertTrue(settings['video']['encoder_config']['hdr']['server_overrides_enable_hdr'])
        self.assertTrue(result['settings_verified'])
        self.assertFalse(result['sustained_performance_verified'])

    def test_udp_requires_explicit_selection(self):
        result, settings = self.apply_offline(transport='Udp')
        self.assertEqual(result['transport'], 'Udp')
        self.assertEqual(settings['video']['pyrowave']['transport']['variant'], 'Udp')

    def test_unknown_transport_rejected_before_mutation(self):
        with self.assertRaises(ValueError):
            self.apply_offline(transport='Unknown')

    def test_wavelet_is_explicit_and_preserved(self):
        result, settings = self.apply_offline(wavelet='Cdf53')
        self.assertEqual(result['wavelet'], 'Cdf53')
        self.assertEqual(settings['video']['pyrowave']['wavelet']['variant'], 'Cdf53')

    def test_fragment_cdf53_rejected_before_mutation(self):
        with patch('tools.quest3.control.set_values') as write:
            with self.assertRaises(ValueError):
                apply('PyroWave', 1000, 120, 'Fragment',
                      {'refresh_extension':True, 'rates_hz':[120]}, wavelet='Cdf53')
            write.assert_not_called()

    def test_haar_is_explicit_without_sustained_performance_claim(self):
        result, settings = self.apply_offline(wavelet='Haar')
        self.assertEqual(settings['video']['pyrowave']['wavelet']['variant'], 'Haar')
        self.assertFalse(result['sustained_performance_verified'])

    def test_fragment_haar_rejected_before_mutation(self):
        with patch('tools.quest3.control.set_values') as write:
            with self.assertRaises(ValueError):
                apply('PyroWave', 1000, 120, 'Fragment',
                      {'refresh_extension':True, 'rates_hz':[120]}, wavelet='Haar')
            write.assert_not_called()

    def test_explicit_render_and_encoded_dimensions_are_verified(self):
        result, settings = self.apply_offline(
            render_resolution={'width': 3000, 'height': 3100},
            encoded_resolution={'width': 3200, 'height': 3300})
        self.assertEqual(result['render_resolution']['width'], 3000)
        self.assertEqual(settings['video']['emulated_headset_view_resolution']['Absolute']['height']['content'], 3100)
        self.assertEqual(settings['video']['transcoding_view_resolution']['Absolute']['width'], 3200)

    def test_one_resolution_is_rejected_before_mutation(self):
        with patch('tools.quest3.control.set_values') as write:
            with self.assertRaises(ValueError):
                apply('PyroWave', 400, 72, 'Compute', {'refresh_extension':True, 'rates_hz':[72]},
                      render_resolution={'width': 1, 'height': 1})
            write.assert_not_called()

    def test_wired_client_package_tracks_fork_metadata(self):
        self.assertEqual(CLIENT_PACKAGE_ID, 'io.github.ljk1291.quest3pyrowave')

    def test_explicit_experiment_reset_never_overwrites_flip_default(self):
        class Run:
            returncode=0
            stdout=''
            stderr=''
        with patch('tools.quest3.control.adb_property_snapshot', return_value={}), \
             patch('tools.quest3.control.subprocess.run', return_value=Run()) as run:
            result=experiment_properties('adb', disable=True, disable_experiments=True)
        values=[call.args[0][-2:] for call in run.call_args_list]
        self.assertTrue(result['changed'])
        self.assertNotIn(['debug.q3pw.direct_flip_y',''], values)
        self.assertIn(['debug.q3pw.direct_eye_copy',''], values)

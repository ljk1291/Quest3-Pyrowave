"""Software-only priority wiring and experiment-evidence checks."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.quest3 import bench, control

ROOT = Path(__file__).resolve().parents[1]
PROP = 'debug.q3pw.decode_priority'


class DecodePriorityContractTests(unittest.TestCase):
    def test_native_creation_uses_cpu_tested_retry_with_persistent_create_info(self):
        source = (ROOT / 'tools/pyroclient/pyroclient.cpp').read_text(encoding='utf-8')
        create = source.split('bool pyroclient::create_device() {', 1)[1].split('// Plain R8 images:', 1)[0]
        self.assertEqual(create.count('__system_property_get("' + PROP + '"'), 1)
        self.assertIn('create_decode_priority_device(requested_priority, available_priority_extension', create)
        self.assertIn('if (requested_priority.priority != DecodeQueuePriority::Default)', create)
        self.assertIn('device_extensions.resize(default_extension_count);', create)
        self.assertIn('queue_info.pNext = nullptr;', create)
        self.assertIn('device_info.ppEnabledExtensionNames = device_extensions.data();', create)
        self.assertIn('queue_info.pNext = &queue_global_priority;', create)
        self.assertIn('VK_QUEUE_GLOBAL_PRIORITY_LOW_KHR', create)
        self.assertIn('VK_QUEUE_GLOBAL_PRIORITY_MEDIUM_KHR', create)
        self.assertIn('VK_QUEUE_GLOBAL_PRIORITY_HIGH_KHR', create)
        self.assertIn('VK_QUEUE_GRAPHICS_BIT) { family = i; break; }', create)
        self.assertIn('vkGetDeviceQueue(device, family, 0, &queue);', create)
        self.assertIn('VkDeviceQueueGlobalPriorityCreateInfoKHR queue_global_priority{};', source)
        self.assertIn('float queue_priority = 1.0f;', source)
        self.assertLess(create.index('[Q3PW_DECODE_PRIORITY] requested='), create.index('VK_TRY(static_cast<VkResult>(priority.result))'))
        for field in ('effective=%s', 'extension=%s', 'fallback=%s', 'applied=%d', 'family=%u',
                      'first_result=%d', 'result=%d', 'proof=vkCreateDevice'):
            self.assertIn(field, create)

    def test_ci_builds_production_client_and_host_policy(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
        self.assertIn('tools/pyroclient/decode_priority_test.cpp', workflow)
        self.assertIn('sh tools/build_alvr_2013.sh', workflow)
        alvr_build = (ROOT / 'tools/build_alvr_2013.sh').read_text(encoding='utf-8')
        self.assertIn('"$workspace_dir/tools/pyroclient/build.sh"', alvr_build)
        build = (ROOT / 'tools/pyroclient/build.sh').read_text(encoding='utf-8')
        self.assertIn('"$HERE/pyroclient.cpp"', build)
        self.assertIn('-I$PW/Granite/third_party/khronos/vulkan-headers/include', build)

    def test_property_readback_records_request_without_claiming_driver_grant(self):
        self.assertIn(PROP, control.EXPERIMENT_PROPERTIES)
        for value in ('', 'default', 'low', 'medium', 'high', 'invalid'):
            state = {'property:' + name: {'value': '', 'error': None} for name in bench.EXPERIMENT_PROPERTIES}
            state['property:' + PROP]['value'] = value
            result = bench.experiment_effective(state)
            self.assertTrue(result['verified'])
            self.assertEqual(result['requested_decode_priority'], value or 'unset')
            self.assertEqual(result['enabled']['decode_priority'], value in ('low', 'medium', 'high'))
            self.assertNotIn('effective_decode_priority', result)

    def test_reset_clears_priority_with_mocked_subprocess_only(self):
        # No ADB executable runs. Verify the existing explicit reset incorporates this flag.
        completed = subprocess.CompletedProcess([], 0, stdout='', stderr='')
        with patch.object(control.subprocess, 'run', return_value=completed) as run:
            control.experiment_properties('mock-adb', disable_experiments=True)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(['mock-adb', 'shell', "setprop " + PROP + " ''"], commands)

    def test_native_cpu_policy(self):
        compiler = shutil.which('g++') or shutil.which('clang++')
        if not compiler:
            self.skipTest('No host C++ compiler on PATH; CI runs the policy test with g++')
        (ROOT / 'ws').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'ws') as directory:
            executable = Path(directory) / 'decode-priority.exe'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            str(ROOT / 'tools/pyroclient/decode_priority_test.cpp'), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    unittest.main()

# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Offline tests for health parsing and the stop-on-fault monitor."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('b1', Path(__file__).with_name('test-vllm-b1.py'))
b1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b1)


class SafetyTests(unittest.TestCase):
    def test_empty_health_is_success(self):
        response = Mock(status=200)
        response.read.return_value = b''
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(b1.urllib.request, 'urlopen', return_value=response):
            self.assertEqual(b1.api(8081, '/health')['http_status'], 200)
            self.assertIsNone(b1.api(8081, '/health')['body'])

    def test_memory_thresholds(self):
        guard = object.__new__(b1.Guard)
        self.assertIsNotNone(guard.check_resources({'linux': {'MemAvailable': 15*b1.GIB}, 'gpu': {}}))
        self.assertIsNotNone(guard.check_resources({'linux': {'MemAvailable': 20*b1.GIB},
                                'gpu': {'/x/mem_info_vram_used': 59*b1.GIB}}))
        self.assertIsNone(guard.check_resources({'linux': {'MemAvailable': 20*b1.GIB},
                                'gpu': {'/x/mem_info_vram_used': 30*b1.GIB}}))

    def fault(self, state_changed=False, kernel_fault=False):
        old = {'running': True, 'health': 'healthy'}
        states = [old, {'running': False}] if state_changed else [old, old]
        journal = '{"MESSAGE":"amdgpu: GPU reset begin"}\n-- cursor: next' if kernel_fault else '-- cursor: next'
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(b1, 'old_state', side_effect=states), \
                patch.object(b1, 'api'), \
                patch.object(b1, 'run', side_effect=['-- cursor: initial', journal]), \
                patch.object(b1, 'sample', return_value={}), \
                patch.object(b1, 'stop_new') as stop:
            guard = b1.Guard(Path(tmp))
            guard.watch()
            self.assertIsNotNone(guard.failed)
            self.assertIn('Kernel safety event' if kernel_fault else 'Existing 30B state changed', guard.failed)
            stop.assert_called_once_with()
            self.assertTrue((Path(tmp)/'safety-stop.json').is_file())

    def test_old_server_fault_stops_new_only(self):
        self.fault(state_changed=True)

    def test_gpu_reset_stops_new_only(self):
        self.fault(kernel_fault=True)

    def test_refuses_running_b1_without_stopping_it(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch('sys.argv', ['test', 'serve', '--run-dir', tmp]), \
                patch.object(b1, 'new_ids', return_value=['existing-b1']), \
                patch.object(b1, 'run', return_value='[{"State":{"Running":true}}]'), \
                patch.object(b1, 'old_state', return_value={}), \
                patch.object(b1, 'existing_api', return_value={}), \
                patch.object(b1, 'stop_new') as stop:
            self.assertEqual(b1.main(), 1)
            stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()

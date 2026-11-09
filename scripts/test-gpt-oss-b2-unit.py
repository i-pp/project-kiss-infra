# KISS Open License Version 1.0 (KOL-v1)
#
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1
#
# Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
# Contributors may add copyright notices for their own original modifications.
# Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
#
# Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
# without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
#
# Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
# KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
#
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
#
# This header is a summary, not a separate license or an amendment to KOL-v1.
# All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.

"""Offline tests for safety gates, protected-container refusal and GGUF parsing."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


ROOT = Path(__file__).resolve().parent.parent
b2 = module('b2', ROOT/'scripts/test-gpt-oss-b2.py')
reader = module('reader', ROOT/'inference/gpt-oss-b2/inspect-gguf.py')


class SafetyTests(unittest.TestCase):
    def record(self, used=20, available=40):
        return {'gpu': {'mem_info_vram_total': 64*b2.GIB, 'mem_info_vram_used': used*b2.GIB},
                'linux': {'MemAvailable': available*b2.GIB}}

    def test_preflight_both_memory_domains(self):
        self.assertIsNone(b2.resource_reason(self.record(), True))
        self.assertIsNotNone(b2.resource_reason(self.record(used=41), True))
        self.assertIsNotNone(b2.resource_reason(self.record(available=23), True))

    def test_pressure_and_emergency(self):
        self.assertIsNone(b2.resource_reason(self.record()))
        self.assertIsNotNone(b2.resource_reason(self.record(used=59)))
        self.assertIsNotNone(b2.resource_reason(self.record(available=15)))
        self.assertTrue(b2.resource_reason(self.record(available=7)).startswith('EMERGENCY'))

    def test_stop_refuses_protected_project(self):
        container = {'Config': {'Labels': {'com.docker.compose.project': 'project-kiss-phase2'}, 'User': '1000:973'},
                     'State': {'Running': True}}
        with patch.object(b2, 'inspect', return_value=container), patch.object(b2.subprocess, 'run') as stop:
            with self.assertRaises(AssertionError):
                b2.stop_owned('protected')
            stop.assert_not_called()

    def test_feedback_withholds_verifier_output(self):
        verdict = {'steps': [{'phase': 'execute_tests', 'returncode': -6,
                             'output': 'secret_expected_reference_value assert failed'}]}
        self.assertNotIn('secret_expected_reference_value', b2.feedback(verdict, 'x.c'))

    def test_gguf_known_descriptor_and_scalar(self):
        def s(value):
            raw = value.encode(); return struct.pack('<Q', len(raw))+raw
        data = b'GGUF'+struct.pack('<IQQ', 3, 1, 1)
        data += s('gpt-oss.block_count')+struct.pack('<II', 4, 24)
        data += s('blk.0.ffn_up_exps.weight')+struct.pack('<IQQQIQ', 3, 32, 64, 2, 39, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'header.gguf'; path.write_bytes(data)
            result = reader.inspect(path)
            self.assertEqual(result['metadata']['gpt-oss.block_count'], 24)
            self.assertEqual(result['tensor_types'], {'39': 1})
            self.assertEqual(result['tensors'][0]['shape'], [32, 64, 2])
            path.write_bytes(b'GGUF'+struct.pack('<IQQ', 99, 0, 0))
            with self.assertRaises(AssertionError):
                reader.inspect(path)


if __name__ == '__main__':
    unittest.main()

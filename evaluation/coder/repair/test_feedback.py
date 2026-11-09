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

import unittest
from feedback import feedback


class FeedbackTests(unittest.TestCase):
    def compile_feedback(self, output, filename='module.S'):
        return feedback({'steps':[{'phase':'compile_candidate','output':output}]},filename)

    def test_candidate_diagnostic_only(self):
        output = ("/candidate/c_parse.c:5:14: error: 'NULL' undeclared\n"
                  "/suite/private.cpp:1:2: error: EXPECTED_SECRET\n"
                  "  1 | assert(result == SECRET_REFERENCE);\n")
        text = feedback({'steps':[{'phase':'compile_candidate','output':output}]},'c_parse.c')
        self.assertIn('NULL',text)
        self.assertNotIn('EXPECTED_SECRET',text)
        self.assertNotIn('SECRET_REFERENCE',text)
        self.assertNotIn('/suite',text)

    def test_runtime_output_never_forwarded(self):
        for output in ["assert(actual == SECRET_REFERENCE)","AddressSanitizer SECRET_REFERENCE", "Segmentation fault SECRET_REFERENCE"]:
            text = feedback({'steps':[{'phase':'execute_tests','output':output,'returncode':-6}]},'answer.c')
            self.assertNotIn('SECRET_REFERENCE',text)
            self.assertNotIn('assert(actual',text)

    def test_linker_output_never_forwarded(self):
        text = feedback({'steps':[{'phase':'link_tests','output':'TEST_ANSWER'}]},'answer.c')
        self.assertNotIn('TEST_ANSWER',text)

    def test_gnu_assembler_error_without_column(self):
        text = self.compile_feedback('/candidate/module.S:12: Error: invalid operand width\n')
        self.assertIn('module.S:12: Error: invalid operand width',text)
        self.assertNotIn('/candidate/',text)

    def test_severity_case_variants(self):
        for severity in ['error','Error','ERROR','eRrOr','warning','WARNING','Note','nOtE',
                         'fatal error','Fatal Error','FATAL ERROR']:
            with self.subTest(severity=severity):
                text = self.compile_feedback(f'module.S:8:2: {severity}: candidate diagnostic\n')
                self.assertIn(f'module.S:8:2: {severity}: candidate diagnostic',text)

    def test_filename_and_candidate_prefix_remain_case_sensitive(self):
        output = ('/candidate/module.S:1: Error: ACCEPT_THIS\n'
                  '/candidate/Module.S:1: ERROR: WRONG_FILENAME_CASE\n'
                  '/candidate/module.s:1: Note: WRONG_EXTENSION_CASE\n'
                  '/Candidate/module.S:1: Error: WRONG_PREFIX_CASE\n'
                  '/candidate/module.S.extra:1: Error: WRONG_SUFFIX\n'
                  '/suite/module.S:1: ERROR: PRIVATE_EXPECTED\n'
                  '/home/private/module.S:1: Note: HOST_SECRET\n'
                  '  1 | assert(value == HIDDEN_REFERENCE);\n')
        text = self.compile_feedback(output)
        self.assertIn('ACCEPT_THIS',text)
        for marker in ['WRONG_','PRIVATE_EXPECTED','HOST_SECRET','HIDDEN_REFERENCE','/suite','/home']:
            self.assertNotIn(marker,text)

    def test_filename_regex_metacharacters_are_literal(self):
        text = self.compile_feedback('unit[1].S:1: ERROR: ACCEPT_LITERAL\n'
                                     'unit1.S:1: ERROR: WRONG_FILE\n','unit[1].S')
        self.assertIn('ACCEPT_LITERAL',text)
        self.assertNotIn('WRONG_FILE',text)

    def test_path_bearing_message_body_is_withheld(self):
        for path in ['/suite/private.hpp','/tmp/build/private.o','/home/private/token',
                     '../private/reference.hpp','private/reference.hpp',r'C:\private\reference.hpp']:
            with self.subTest(path=path):
                text = self.compile_feedback(f'/candidate/module.S:3: ERROR: {path} PRIVATE_VALUE\n')
                self.assertNotIn('PRIVATE_VALUE',text)
                self.assertNotIn(path,text)

    def test_control_bytes_in_message_are_withheld(self):
        for control in ['\x1b','\x00','\x7f']:
            text = self.compile_feedback(f'module.S:3: Error: {control}PRIVATE_CONTROL\n')
            self.assertNotIn('PRIVATE_CONTROL',text)

    def test_rust_error_case_requires_candidate_location(self):
        for severity in ['error[E0308]','Error[E0308]','ERROR[e0308]','eRrOr']:
            text = self.compile_feedback(f'{severity}: mismatched candidate types\n'
                '  --> /candidate/module.rs:5:9\n  | source excerpt PRIVATE_EXCERPT\n','module.rs')
            self.assertIn(severity+': mismatched candidate types',text)
            self.assertNotIn('/candidate/',text)
            self.assertNotIn('PRIVATE_EXCERPT',text)

    def test_rust_non_candidate_or_unlocated_errors_are_withheld(self):
        output = ('ERROR[E0001]: PRIVATE_FIXTURE\n  --> /suite/reference.rs:2:3\n'
                  'error[E0002]: PRIVATE_WRONG_CASE\n  --> /candidate/Module.rs:2:3\n'
                  'Error: PRIVATE_UNLOCATED\n'
                  'error[E0003]: /suite/private.rs PRIVATE_PATH\n  --> /candidate/module.rs:2:3\n')
        self.assertNotIn('PRIVATE_',self.compile_feedback(output,'module.rs'))

    def test_diagnostic_count_and_character_limits(self):
        output = ''.join(f'module.S:{i+1}: Error: message-{i}\n' for i in range(30))
        text = self.compile_feedback(output)
        self.assertIn('message-15',text)
        self.assertNotIn('message-16',text)
        text = self.compile_feedback('module.S:1: Error: '+'Z'*5000+'\n')
        self.assertNotIn('Z'*4001,text)
        self.assertLess(len(text),4300)

    def test_non_basename_filename_is_refused(self):
        for name in ['','..','../module.S','/suite/module.S',r'private\module.S','bad\x00.S']:
            text = self.compile_feedback(f'{name}:1: ERROR: PRIVATE_BAD_FILENAME\n',name)
            self.assertNotIn('PRIVATE_BAD_FILENAME',text)

    def test_uppercase_runtime_and_linker_messages_are_not_forwarded(self):
        for phase in ['execute_tests','link_tests','inspect_instructions']:
            result = {'steps':[{'phase':phase,'returncode':1,
                               'output':'module.S:1: ERROR: PRIVATE_RUNTIME_REFERENCE'}]}
            self.assertNotIn('PRIVATE_RUNTIME_REFERENCE',feedback(result,'module.S'))


if __name__ == '__main__': unittest.main()

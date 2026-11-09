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

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'repair'))
from feedback import feedback
from diagnosis import diagnosis_payload, parse_diagnosis, repair_message
from assessment import assess


def example():
    return {'hypotheses':[{'category':'unknown','claim':'An input path may be missing.',
                           'code_evidence':'return 0;','confidence':'low'}],
            'repair_plan':['Check the specified input paths before changing code.']}


class DiagnosisTests(unittest.TestCase):
    def test_context_has_only_supplied_public_inputs(self):
        payload = diagnosis_payload('PUBLIC_SPEC','CANDIDATE','FILTERED','MODEL')
        self.assertEqual(len(payload['messages']),2)
        self.assertEqual(json.loads(payload['messages'][1]['content']),
                         {'public_specification':'PUBLIC_SPEC','candidate_code':'CANDIDATE','filtered_verification_feedback':'FILTERED'})
        self.assertEqual(payload,diagnosis_payload('PUBLIC_SPEC','CANDIDATE','FILTERED','MODEL'))
        self.assertFalse(payload['cache_prompt'])
        self.assertEqual(payload['temperature'],0)

    def test_schema_rejects_code_or_extra_fields(self):
        good = example()
        self.assertEqual(parse_diagnosis(json.dumps(good)),good)
        for bad in [{**good,'replacement_code':'SECRET_ANSWER'}, {'hypotheses':[],'repair_plan':[]}]:
            with self.assertRaises(ValueError): parse_diagnosis(json.dumps(bad))
        with self.assertRaises(ValueError): parse_diagnosis('```json\n{}\n```')

    def test_repair_message_has_no_verifier_input(self):
        text = repair_message('FILTERED',example())
        self.assertIn('UNVERIFIED',text)
        self.assertNotIn('SECRET_REFERENCE',text)
        self.assertNotIn('/suite/',text)

    def test_legacy_filter_to_diagnosis_does_not_leak_runtime_assert(self):
        raw = {'steps':[{'phase':'execute_tests','returncode':-6,
                        'output':'/suite/private.cpp: Assertion EXPECTED_SECRET_REFERENCE failed'}]}
        sanitized = feedback(raw,'answer.c')
        payload = diagnosis_payload('SPEC','CODE',sanitized,'MODEL')
        self.assertNotIn('EXPECTED_SECRET_REFERENCE',json.dumps(payload))
        self.assertNotIn('/suite/private.cpp',json.dumps(payload))

    def test_builder_does_not_read_analysis_files(self):
        with patch('pathlib.Path.read_text',side_effect=AssertionError('No analysis-file access')):
            payload = diagnosis_payload('SPEC','CODE','FILTERED','MODEL')
        self.assertEqual(json.loads(payload['messages'][1]['content'])['candidate_code'],'CODE')

    def test_assessment_does_not_trust_self_claim(self):
        d = example(); d['hypotheses'][0]['claim']='This definitely fixes every test.'
        before = {'status':'FAIL','failure':'execute_tests','steps':[]}
        result = assess('return 0;','return 0;',before,before,d)
        self.assertFalse(result['code_changed'])
        self.assertEqual(result['hypothesis_assessments'][0]['independent_assessment'],'no_code_change_no_repair_evidence')
        self.assertFalse(result['hypothesis_assessments'][0]['individual_cause_proven'])

    def test_diagnostic_regressions_and_partial_progress(self):
        before = {'status':'FAIL','failure':'compile_candidate','steps':[{'phase':'compile_candidate','returncode':1,'output':'error: old'}]}
        after = {'status':'FAIL','failure':'execute_tests','steps':[{'phase':'compile_candidate','returncode':0,'output':''},{'phase':'execute_tests','returncode':-6,'output':'SECRET_ASSERT'}]}
        result = assess('return 0;','return 1;',before,after,example())
        self.assertEqual(result['cleared_compiler_diagnostics'],['old'])
        self.assertEqual(result['hypothesis_assessments'][0]['independent_assessment'],'compilation_improved_but_independent_verification_still_failed')
        self.assertNotIn('SECRET_ASSERT',json.dumps(result))


if __name__=='__main__': unittest.main()

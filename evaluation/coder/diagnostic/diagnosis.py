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

"""Pure prompt/schema functions. No access to analysis reports or hidden tests."""
import json

SYSTEM = (
    'Independently diagnose a failed candidate from ONLY the supplied public specification, '
    'candidate code and filtered verification feedback. You have no access to test inputs, '
    'assertions, expected values, reference implementations or prior analysis. '
    'Do not claim knowledge of them. Infer causes from the supplied evidence; distinguish '
    'hypotheses from observations. Do not write a replacement implementation or a code block. '
    'Return ONLY JSON with exactly two keys: hypotheses and repair_plan. '
    'hypotheses is a nonempty list of at most 4 objects with exactly these keys: '
    'category (compile, contract, undefined_behavior, bounds, isa, abi, or unknown), '
    'claim (brief cause hypothesis), code_evidence (an exact nonempty short substring copied '
    'from the supplied candidate), confidence (low, medium, or high). '
    'repair_plan is a nonempty list of at most 5 brief textual actions. '
    'Use only the supplied information, state uncertainty, and keep the plan concise.'
)
CATEGORIES = {'compile','contract','undefined_behavior','bounds','isa','abi','unknown'}


def diagnosis_payload(specification, code, filtered_feedback, model):
    # Every diagnosis starts a fresh two-message context; no generator history.
    evidence = {'public_specification':specification,'candidate_code':code,
                'filtered_verification_feedback':filtered_feedback}
    return {'model':model,'messages':[{'role':'system','content':SYSTEM},
            {'role':'user','content':json.dumps(evidence,ensure_ascii=False)}],
            'temperature':0,'seed':42,'max_tokens':1024,'stream':False,'cache_prompt':False}


def parse_diagnosis(text):
    value = json.loads(text)
    if not isinstance(value,dict) or set(value)!={'hypotheses','repair_plan'}:
        raise ValueError('Diagnosis must contain only hypotheses and repair_plan')
    if not isinstance(value['hypotheses'],list) or not 1<=len(value['hypotheses'])<=4:
        raise ValueError('Expected 1 to 4 hypotheses')
    for h in value['hypotheses']:
        if not isinstance(h,dict) or set(h)!={'category','claim','code_evidence','confidence'}:
            raise ValueError('Invalid hypothesis fields')
        if h['category'] not in CATEGORIES or h['confidence'] not in {'low','medium','high'}:
            raise ValueError('Invalid hypothesis category or confidence')
        if not all(isinstance(h[k],str) and 0<len(h[k])<=1000 for k in ['claim','code_evidence']):
            raise ValueError('Hypothesis text missing or too long')
    plan = value['repair_plan']
    if not isinstance(plan,list) or not 1<=len(plan)<=5 or not all(isinstance(s,str) and 0<len(s)<=1000 for s in plan):
        raise ValueError('Expected 1 to 5 textual repair actions')
    if '```' in text: raise ValueError('Diagnosis must not provide a code block')
    return value


def repair_message(filtered_feedback, diagnosis):
    return (filtered_feedback+'\n\nA separate context of the same model proposed the following '
            'UNVERIFIED hypotheses and repair plan. Check them against the public specification '
            'and your code; they are not test answers or an independent verdict.\n'
            +json.dumps(diagnosis,ensure_ascii=False)
            +'\nReturn only the complete corrected implementation in one fenced code block.')

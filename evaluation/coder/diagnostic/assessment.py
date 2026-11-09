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

"""Post-hoc evidence only. Its results must never be sent to either model role."""
import difflib
import hashlib
import re


def compiler_errors(verdict):
    errors = set()
    for step in verdict.get('steps',[]):
        if step['phase']=='compile_candidate':
            errors.update(re.findall(r'\berror: ([^\n]+)',step.get('output','')))
    return sorted(errors)


def passed_stages(verdict):
    return sorted({s['phase'] for s in verdict.get('steps',[]) if s['returncode']==0 and not s.get('limit_reason')})


def assess(before_code, after_code, before, after, diagnosis):
    old = set(compiler_errors(before)); new = set(compiler_errors(after))
    changed = before_code!=after_code
    reviews = []
    for i,h in enumerate(diagnosis['hypotheses']):
        grounded = h['code_evidence'] in before_code
        if not grounded:
            finding = 'quoted_evidence_not_found_in_input'
        elif not changed:
            finding = 'no_code_change_no_repair_evidence'
        elif after['status']=='PASS':
            finding = 'candidate_improved_and_passed_independent_tests'
        elif 'compile_candidate' not in passed_stages(before) and 'compile_candidate' in passed_stages(after):
            finding = 'compilation_improved_but_independent_verification_still_failed'
        else:
            finding = 'repair_not_confirmed_by_independent_verification'
        reviews.append({'hypothesis_index':i,'claim':h['claim'],'category':h['category'],
                        'quoted_evidence_in_before':grounded,
                        'quoted_evidence_retained_in_after':h['code_evidence'] in after_code,
                        'independent_assessment':finding,'individual_cause_proven':False})
    return {'basis':'independent verifier results and exact source diff; no model self-rating',
            'before_status':before['status'],'after_status':after['status'],
            'before_failure':before.get('failure'),'after_failure':after.get('failure'),
            'before_passed_stages':passed_stages(before),'after_passed_stages':passed_stages(after),
            'code_changed':changed,
            'before_sha256':hashlib.sha256(before_code.encode()).hexdigest(),
            'after_sha256':hashlib.sha256(after_code.encode()).hexdigest(),
            'code_diff':''.join(difflib.unified_diff(before_code.splitlines(True),after_code.splitlines(True),fromfile='before',tofile='after')),
            'cleared_compiler_diagnostics':sorted(old-new),
            'new_compiler_diagnostics':sorted(new-old),
            'retained_compiler_diagnostics':sorted(old & new),
            'hypothesis_assessments':reviews,
            'attribution_limit':'A changed candidate passing tests supports the repair as a whole, not the truth of every hypothesis or general correctness.'}

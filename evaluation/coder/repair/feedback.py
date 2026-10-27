"""Deliberately exclude verifier assertions, inputs, expected values and source."""
import re


def feedback(result, filename):
    if result.get('format_error'):
        return 'Output format failed. Return exactly one fenced code block containing the complete implementation, without prose.'
    if result.get('limit_reason'):
        return 'Independent verification failed: '+result['limit_reason']+'. Reduce resource use and review termination. No test data is disclosed.'
    steps = result.get('steps',[])
    failed = steps[-1] if steps else {}
    phase = failed.get('phase','verification')
    if phase == 'compile_candidate':
        # Only diagnostics emitted while compiling the candidate alone. Never
        # include a fixture line, assertion, reference value, or source excerpt.
        pattern = re.compile(r'^(?:/candidate/)?'+re.escape(filename)+r':\d+(?::\d+)?: (?:fatal error|error|warning|note): [^\n]+$')
        lines = [line.replace('/candidate/','') for line in failed.get('output','').splitlines()
                 if pattern.fullmatch(line)]
        if filename.endswith('.rs'):
            lines += re.findall(r'^error(?:\[E\d+\])?: [^\n]+$',failed.get('output',''),re.MULTILINE)
        return ('Candidate compilation failed under the required language/ISA and strict warnings.\n'
                +'\n'.join(lines[:16])[:4000]
                +'\nReturn the complete corrected implementation. Independent test source and answers are withheld.')
    if failed.get('limit_reason'):
        category = failed['limit_reason']
    elif phase == 'execute_tests':
        text = failed.get('output','')
        if 'AddressSanitizer' in text or 'runtime error:' in text:
            category = 'sanitizer reported a memory-safety or undefined-behavior violation'
        elif failed.get('returncode') in [-11,139] or 'Segmentation fault' in text:
            category = 'invalid memory access during independent boundary checks'
        else:
            category = 'independent result or contract check failed'
    elif phase == 'inspect_instructions' or result.get('failure') == 'ISA constraint failed':
        category = 'required scalar/NEON instruction constraint failed'
    else:
        category = 'required interface could not be linked to the independent verifier'
    return (f'Independent verification failed: {category}. '
            'Review the original specification, null/zero-length handling, ranges, arithmetic widths, ABI/ISA rules and termination as applicable. '
            'Test inputs, assertions, expected values and reference implementations are withheld. '
            'Return exactly one fenced block with the complete corrected code.')

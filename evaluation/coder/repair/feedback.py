"""Deliberately exclude verifier assertions, inputs, expected values and source."""
import re


def _candidate_diagnostics(output, filename):
    # Case folding is scoped to severity, never Linux filenames or path prefixes.
    if (not filename or filename in {'.', '..'} or '/' in filename or '\\' in filename
            or any(ord(c) < 32 or ord(c) == 127 for c in filename)):
        return []
    location = r'(?:/candidate/)?'+re.escape(filename)+r':\d+(?::\d+)?'
    pattern = re.compile(r'^'+location+r': (?i:fatal error|error|warning|note): (?P<message>[^\n]+)$')
    selected = []
    for line in output.splitlines():
        match = pattern.fullmatch(line)
        if match:
            selected.append((line.removeprefix('/candidate/'), match['message']))
    if filename.casefold().endswith('.rs'):
        # Rust puts the error header before its location. Accept it only when
        # the immediately following location belongs to this exact candidate.
        rust = re.compile(r'^(?P<diagnostic>(?i:error(?:\[E\d+\])?): (?P<message>[^\n]+))'
                          r'\n[ \t]*-->[ \t]+'+location+r'[ \t]*$', re.MULTILINE)
        selected.extend((m['diagnostic'], m['message']) for m in rust.finditer('\n'.join(output.splitlines())))
    # A candidate location alone does not make paths in the message public.
    # Omit path/control-bearing messages rather than partially disclosing them.
    return [line for line, message in selected
            if '/' not in message and '\\' not in message
            and not any(ord(c) < 32 or ord(c) == 127 for c in message)]


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
        lines = _candidate_diagnostics(failed.get('output',''), filename)
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

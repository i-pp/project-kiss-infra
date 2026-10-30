"""Approved fixed-profile handlers; requires the operator-enabled MCP adapter."""
import json
import sys
from local_llm import LocalError
import model_selection as selected

STATUS = 'aceis_local_model_status'
GENERATE = 'aceis_local_model_generate'
PREPARE = 'aceis_local_model_prepare'


def definitions():
    common = {'profile': {'type': 'string', 'enum': list(selected.SELECTABLE)}}
    return [
        {'name': STATUS, 'description': 'Read fixed model availability; never load a model or generate text.',
         'inputSchema': {'type': 'object', 'properties': common, 'required': ['profile'], 'additionalProperties': False},
         'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}},
        {'name': GENERATE, 'description': 'Ask one explicitly selected, already available allowlisted model for UNVERIFIED advice. No auto-load, commands or fallback.',
         'inputSchema': {'type': 'object', 'properties': {**common,
             'task': {'type': 'string', 'enum': ['draft', 'review']},
             'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 16384},
             'max_tokens': {'type': 'integer', 'minimum': 1, 'maximum': 1024, 'default': 256}},
             'required': ['profile', 'task', 'prompt'], 'additionalProperties': False},
         'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': False, 'openWorldHint': False}},
        {'name': PREPARE, 'description': 'Explicitly unload/load one of three approved models inside the existing router. Temporarily interrupts other profiles; no Docker or commands.',
         'inputSchema': {'type': 'object', 'properties': common, 'required': ['profile'], 'additionalProperties': False},
         'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': False, 'openWorldHint': False}}]


def dispatch(name, arguments, client_factory=None, runtime=None):
    try:
        allowed = {'profile'} if name in [STATUS, PREPARE] else {'profile', 'task', 'prompt', 'max_tokens'}
        required = {'profile'} if name in [STATUS, PREPARE] else {'profile', 'task', 'prompt'}
        if name not in [STATUS, GENERATE, PREPARE] or not isinstance(arguments, dict) or set(arguments)-allowed or not required <= set(arguments):
            raise LocalError('INVALID_INPUT', 'Unsupported operation or arguments')
        identifier = arguments['profile']
        if not isinstance(identifier, str) or identifier not in selected.SELECTABLE:
            raise LocalError('UNKNOWN_PROFILE', 'Select an allowlisted profile')
        from model_runtime import Runtime
        runtime = runtime or (Runtime() if client_factory is None else None)
        kwargs = {'runtime': runtime} if runtime is not None else {'client_factory': client_factory}
        if name == STATUS:
            data = selected.status(identifier, **kwargs)
        elif name == PREPARE:
            data = (runtime or Runtime()).prepare(identifier)
        else:
            task, prompt, tokens = arguments['task'], arguments['prompt'], arguments.get('max_tokens', 256)
            if (not isinstance(task, str) or task not in ['draft', 'review']
                    or not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 16384
                    or type(tokens) is not int or not 1 <= tokens <= 1024):
                raise LocalError('INVALID_INPUT', 'Invalid bounded advisory input')
            data = selected.generate(identifier, task, prompt, tokens, **kwargs)
        data.update(verification_status='NOT_EXECUTED', code_executed=False)
        if name == GENERATE: data['untrusted_advisory'] = True
        return {'structuredContent': data, 'isError': name != STATUS and data.get('status') in ['BLOCKED', 'UNAVAILABLE']}
    except LocalError as exc:
        data = selected.error_result(exc, generation=name in [GENERATE, PREPARE])
        data.update(verification_status='NOT_EXECUTED', code_executed=False)
        return {'isError': True, 'structuredContent': data}


if __name__ == '__main__':
    if not sys.argv[1:]: print(json.dumps(definitions(), ensure_ascii=False, indent=2))
    elif sys.argv[1:] == ['--call']:
        value = None
        try:
            raw = sys.stdin.buffer.read(65537)
            if len(raw) > 65536: raise ValueError('Frame bound')
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {'name', 'arguments'}: raise ValueError('Frame')
            result = dispatch(value['name'], value['arguments'])
        except (ValueError, TypeError, KeyError, OSError):
            mutating = isinstance(value, dict) and value.get('name') in [GENERATE, PREPARE]
            error = LocalError('UNCERTAIN' if mutating else 'INVALID_INPUT', 'Bounded local helper failure')
            result = {'isError': True, 'structuredContent': selected.error_result(error, generation=mutating)}
        print(json.dumps(result, ensure_ascii=False));raise SystemExit(1 if result['isError'] else 0)
    else: raise SystemExit('Use no arguments for schemas or --call with one explicit JSON frame')

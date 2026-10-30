"""Fixed profile CLI; model lifecycle uses only the approved HTTP runtime."""
import argparse
import json
from pathlib import Path
import stat
import sys
from local_llm import Client, LocalError, MAX_INPUT_BYTES

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_FILE = Path(__file__).with_name('model_registry.json')
SELECTABLE = ('qwen-coder-30b', 'gpt-oss-120b', 'qwen-coder-next')
INVENTORY = (*SELECTABLE, 'qwen38-flash-next')


def profile(identifier):
    if not isinstance(identifier, str) or identifier not in INVENTORY:
        raise LocalError('UNKNOWN_PROFILE', 'Select a fixed allowlisted profile ID')
    values = json.loads(REGISTRY_FILE.read_text())['profiles']
    value = next((v for v in values if v['id'] == identifier), None)
    if value is None:
        raise LocalError('REGISTRY_UNAVAILABLE', 'The fixed profile is unavailable')
    # Registry data is descriptive only: no endpoint/command is ever executed from it.
    return value


def assets(identifier):
    value = profile(identifier)
    directory = ROOT/'models' if identifier == 'qwen-coder-30b' else ROOT/'models/large-coder-b3'/identifier
    present = True
    matched = True
    try:
        if any(p.is_symlink() for p in [directory, *directory.parents]):
            raise OSError('Symlink model ancestry')
        for item in value['files']:
            name = item['name']
            if not isinstance(name, str) or Path(name).name != name or name in ('', '.', '..'):
                raise ValueError('Invalid fixed asset name')
            path = directory/name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or path.is_symlink():
                present = False
            if info.st_size != item['bytes']:
                matched = False
    except (OSError, ValueError, TypeError, KeyError):
        present = False
        matched = False
    return {'present': present, 'size_matches_saved_identity': matched,
            'current_full_sha256_recomputed': False,
            'identity_basis': 'fixed filenames and sizes; historical SHA verification evidence'}


def catalog():
    from model_runtime import Runtime
    configured = Runtime().confirmed()
    result = []
    for identifier in INVENTORY:
        value = profile(identifier)
        result.append({k: value[k] for k in ['id', 'model', 'alias', 'quantization', 'context', 'gpu_layers', 'historical_quality']})
        result[-1].update(selectable=identifier in SELECTABLE,
                         route_configured=identifier == 'qwen-coder-30b' or configured,
                         automatic_model_loading=False,
                         assets=assets(identifier))
    return {'profiles': result, 'management_route': 'CONFIRMED_HTTP_ROUTER' if configured else 'ROUTER_DEPLOYMENT_PENDING',
            'published_mcp_tools_unchanged': True, 'code_execution': False}


def status(identifier, client_factory=Client, runtime=None):
    value = profile(identifier)
    result = {'profile': identifier, 'model': value['model'], 'assets': assets(identifier),
              'verification_status': 'NOT_EXECUTED', 'quality_verdict': 'UNASSESSED',
              'automatic_retry': False, 'automatic_model_loading': False}
    if identifier not in SELECTABLE:
        result.update(status='RESEARCH_ONLY', reason='Flash is distinct from Coder Next and is not selected by this interface')
    elif runtime is not None or identifier != 'qwen-coder-30b':
        from model_runtime import Runtime
        result.update((runtime or Runtime()).status(identifier))
    else:
        try:
            result.update(status='READY', runtime=client_factory().status())
        except LocalError as exc:
            result.update(status='UNAVAILABLE', reason=exc.code)
    return result


def generate(identifier, task, prompt, max_tokens=256, client_factory=Client, runtime=None):
    profile(identifier)
    if identifier not in SELECTABLE:
        raise LocalError('RESEARCH_ONLY', 'Flash is not enabled by this selection interface')
    if runtime is not None or identifier != 'qwen-coder-30b':
        from model_runtime import Runtime
        return (runtime or Runtime(client_factory=client_factory)).generate(identifier, task, prompt, max_tokens)
    result = client_factory().generate(task, prompt, max_tokens)
    result['profile'] = identifier
    return result


def error_result(exc, generation=False):
    code = getattr(exc, 'code', 'REGISTRY_UNAVAILABLE')
    known_before_dispatch = code in {'UNKNOWN_PROFILE', 'REGISTRY_UNAVAILABLE',
        'MODEL_MANAGER_NOT_CONFIGURED', 'ROUTER_DEPLOYMENT_PENDING', 'MODEL_NOT_LOADED',
        'BUSY', 'POLICY_UNAVAILABLE', 'RESEARCH_ONLY', 'INVALID_INPUT', 'INPUT_TOO_LARGE',
        'ENDPOINT_INVALID','ENDPOINT_CHANGED'}
    uncertain = generation and not known_before_dispatch
    return {'status': 'UNKNOWN' if uncertain else 'BLOCKED', 'error': code,
            'executed': None if uncertain else False,
            'execution_status': 'UNKNOWN' if uncertain else 'NOT_STARTED',
            'quality_verdict': 'UNASSESSED', 'automatic_retry': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('list')
    inspect = sub.add_parser('status'); inspect.add_argument('--profile', choices=INVENTORY, required=True)
    prepare = sub.add_parser('prepare'); prepare.add_argument('--profile', choices=SELECTABLE, required=True)
    infer = sub.add_parser('generate'); infer.add_argument('--profile', choices=SELECTABLE, required=True)
    infer.add_argument('--task', choices=['draft', 'review'], required=True)
    infer.add_argument('--prompt'); infer.add_argument('--max-tokens', type=int, default=256)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'list': result = catalog()
        elif args.operation == 'status': result = status(args.profile)
        elif args.operation == 'prepare':
            from model_runtime import Runtime
            result = Runtime().prepare(args.profile)
        else:
            prompt = args.prompt if args.prompt is not None else sys.stdin.buffer.read(MAX_INPUT_BYTES+1).decode()
            result = generate(args.profile, args.task, prompt, args.max_tokens)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get('status') not in ['BLOCKED', 'UNAVAILABLE', 'RESEARCH_ONLY'] else 1
    except (LocalError, OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps(error_result(exc, generation=args.operation in ['generate', 'prepare'])))
        return 1


if __name__ == '__main__': raise SystemExit(main())

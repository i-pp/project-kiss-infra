"""Fixed, single-use normal-host tmux launcher; no service or privilege changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SESSION = 'aceis-strata-retry02'


def write_once(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.flush()
        os.fsync(out.fileno())


def private_json(path):
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise RuntimeError('SYMLINK_RECORD_REJECTED')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as source:
        st = os.fstat(source.fileno())
        if st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise RuntimeError('OWNER_ONLY_RECORD_REQUIRED')
        return json.load(source)


def approval_digest(path):
    value = private_json(path)
    if (value.get('approved') is not True
            or value.get('scope') != 'STRATA_RETRY02_AFTER_ACCIDENTAL_INTERRUPT'
            or not str(value.get('approval_reference', '')).startswith('Sentinel_')):
        raise RuntimeError('NEW_SPECIFIC_APPROVAL_REQUIRED')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def layout(script):
    repo = Path(script).resolve().parents[3]
    helpers = repo / 'inference/backend-evaluation/host_trial'
    if Path(script).resolve().parent != helpers:
        raise RuntimeError('FIXED_INSTALLED_LAYOUT_REQUIRED')
    return repo, helpers, repo / 'agents/local_llm/.runtime'


def paths(runtime):
    return {name: runtime / ('strata-retry02-tmux-' + name + '.json')
            for name in ['launch', 'worker', 'result']}


def start(repo, helpers, runtime, run=subprocess.run):
    import host_strata_trial as h
    import assets
    record = assets.private_record(runtime / 'strata-reviewed-assets-20261030.json')
    coordinator = h.Coordinator(repo, record)
    coordinator.guard()  # real normal host + interactive TTY; never bypassed by tmux
    approval = runtime / 'strata-retry02-approval-20261030.json'
    digest = approval_digest(approval)
    if not Path('/usr/bin/tmux').is_file():
        raise RuntimeError('EXISTING_TMUX_REQUIRED_NO_INSTALL')
    p = paths(runtime)
    if any(x.exists() or x.is_symlink() for x in p.values()):
        raise RuntimeError('PRIOR_LAUNCH_EXISTS_INSPECT_NO_RETRY')
    with coordinator.locked():
        coordinator.idle()
        write_once(p['launch'], {'approval_sha256': digest, 'state': 'ONE_LAUNCH_INTENT',
                                'session': SESSION, 'automatic_retry': False})
    # Fixed argv, no shell interpolation, dedicated server, no user's tmux config.
    command = ['/usr/bin/tmux', '-L', SESSION, '-f', '/dev/null',
               'new-session', '-d', '-s', SESSION,
               sys.executable, '-B', str(helpers / Path(__file__).name), '--worker']
    try:
        result = run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     text=True, timeout=10, check=False)
    except BaseException:
        raise RuntimeError('LAUNCH_OUTCOME_UNCERTAIN_INSPECT_NO_RETRY') from None
    if result.returncode:
        raise RuntimeError('TMUX_START_UNCONFIRMED_INSPECT_NO_RETRY')
    return {'status': 'DETACHED_LAUNCHED_NOT_TRIAL_SUCCESS', 'session': SESSION,
            'log': str(runtime / 'strata-retry02-terminal.log'),
            'result': str(p['result']), 'automatic_retry': False}


def worker(repo, helpers, runtime, spawn=subprocess.Popen):
    p = paths(runtime)
    launch = private_json(p['launch'])
    approval = runtime / 'strata-retry02-approval-20261030.json'
    if launch.get('approval_sha256') != approval_digest(approval):
        raise RuntimeError('APPROVAL_CHANGED_NO_TRIAL')
    write_once(p['worker'], {'pid': os.getpid(), 'started_unix': time.time(),
                            'approval_sha256': launch['approval_sha256']})
    log = runtime / 'strata-retry02-terminal.log'
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    started = time.monotonic()
    # Child owns finite trial monitoring/cleanup/recovery. Do not impose an outer
    # kill timeout that could terminate recovery or orphan owned processes.
    observed = []
    def retain_terminal(signum, frame):
        # Terminal-generated SIGINT also reaches the same foreground child,
        # whose controller performs cleanup/restore. Keep its PTY alive while
        # it finishes. A signal to only this wrapper never starts another job.
        observed.append(signum)
    previous = {number: signal.signal(number, retain_terminal)
                for number in [signal.SIGINT, signal.SIGTERM]}
    try:
        with os.fdopen(fd, 'w') as output:
            child = spawn([sys.executable, '-B', str(helpers / 'retry02_strata_host.py'),
                          '--retry-human-approved'], stdout=output, stderr=subprocess.STDOUT)
            while True:
                try:
                    returncode = child.wait()
                    break
                except KeyboardInterrupt:
                    observed.append(int(signal.SIGINT))
                    # Same handle, no kill/re-spawn. Wait through restoration.
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    value = {'status': 'CONTROLLER_EXITED_INSPECT_TRIAL_SUMMARY',
             'controller_exit_code': returncode,
             'elapsed_seconds': time.monotonic() - started,
             'automatic_retry': False, 'log': str(log),
             'wrapper_signals_observed': observed}
    with log.open('rb') as tail:
        tail.seek(max(0, log.stat().st_size - 65536))
        lines = tail.read().decode('utf-8', errors='replace').splitlines()
    for line in reversed(lines):
        try:
            summary = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(summary, dict) and 'run_directory' in summary:
            value['controller_reported_trial'] = {key: summary.get(key) for key in
                ['run_directory', 'status', 'reason', 'environment', 'quality',
                 'generation_requests', 'completed_generations', 'restoration']}
            break
    write_once(p['result'], value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['start', 'status'], default='status')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    arg = parser.parse_args()
    repo, helpers, runtime = layout(__file__)
    if arg.worker:
        result = worker(repo, helpers, runtime)
    elif arg.action == 'start':
        result = start(repo, helpers, runtime)
    else:
        p = paths(runtime)
        result = {'launch': private_json(p['launch']) if p['launch'].exists() else None,
                  'worker': private_json(p['worker']) if p['worker'].exists() else None,
                  'result': private_json(p['result']) if p['result'].exists() else None,
                  'interpretation': 'Missing result means pending or unknown; never retry automatically.'}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if isinstance(exc, SystemExit):
            raise
        print(json.dumps({'status': 'STOPPED_INSPECT_NO_RETRY', 'reason': str(exc),
                          'automatic_retry': False}), file=sys.stderr)
        raise SystemExit(1)

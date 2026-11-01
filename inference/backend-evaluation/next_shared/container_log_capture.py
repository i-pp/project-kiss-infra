"""Read-only whole Docker stdout/stderr capture with explicit per-stream limits."""
import os
import selectors
import subprocess
import time

STREAM_LIMIT = 2 << 20


def collect(proc, timeout, clock=time.monotonic):
    """Keep prefixes from stream start; never pretend a timeout/limit is complete."""
    chunks = {'stdout': bytearray(), 'stderr': bytearray()}
    reason = None
    reaped = False
    release_errors = []
    end = clock() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            for name in chunks:
                selector.register(getattr(proc, name), selectors.EVENT_READ, name)
            while selector.get_map() and reason is None:
                left = end - clock()
                if left <= 0:
                    reason = 'LOG_CAPTURE_TIMEOUT'
                    break
                for key, _ in selector.select(min(.1, left)):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    dest = chunks[key.data]
                    remaining = STREAM_LIMIT - len(dest)
                    dest.extend(data[:remaining])
                    if len(data) > remaining:
                        reason = 'LOG_STREAM_LIMIT'
                        break
        if reason is None:
            try:
                proc.wait(timeout=max(.001, end - clock()))
            except subprocess.TimeoutExpired:
                reason = 'LOG_CAPTURE_TIMEOUT'
    except Exception as exc:
        reason = 'LOG_CAPTURE_ERROR:' + type(exc).__name__
    finally:
        try:
            if proc.poll() is None:
                # Only the local read-only Docker CLI, never the container.
                proc.kill()
        except ProcessLookupError:
            pass
        except Exception as exc:
            release_errors.append('kill_or_poll:' + type(exc).__name__)
        try:
            proc.wait(timeout=1)
            reaped = True
        except Exception as exc:
            release_errors.append('wait:' + type(exc).__name__)
            reason = 'LOG_CLIENT_REAP_UNCONFIRMED'
        for name in chunks:
            try:
                getattr(proc, name).close()
            except Exception as exc:
                release_errors.append(name + '_close:' + type(exc).__name__)
        if release_errors and reason is None:
            reason = 'LOG_CLIENT_RELEASE_ERROR'
    if reason is None and proc.returncode != 0:
        reason = 'LOG_COMMAND_FAILED'
    return {
        'capture_mode': 'whole_stream_bounded',
        'stdout': bytes(chunks['stdout']).decode('utf-8', errors='replace'),
        'stderr': bytes(chunks['stderr']).decode('utf-8', errors='replace'),
        'captured_bytes': {key: len(value) for key, value in chunks.items()},
        'stream_limit_bytes': STREAM_LIMIT,
        'complete_stream': reason is None,
        'truncated': reason is not None,
        'incomplete_reason': reason,
        'cli_exit_code': proc.returncode,
        'cli_reaped': reaped,
        'client_release_errors': release_errors,
        'streams_are_separate_not_chronologically_merged': True,
    }


def capture(driver, cid, timeout):
    driver.guard()
    if driver.deadline is not None:
        timeout = min(timeout, driver.deadline - time.monotonic())
    if timeout <= 0:
        raise TimeoutError('LOG_CAPTURE_DEADLINE')
    proc = subprocess.Popen(
        ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock',
         'container', 'logs', '--timestamps', cid],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    previously_reaped = driver.clients_reaped
    driver.clients_reaped = False
    result = collect(proc, timeout)
    driver.clients_reaped = previously_reaped and result['cli_reaped']
    return result

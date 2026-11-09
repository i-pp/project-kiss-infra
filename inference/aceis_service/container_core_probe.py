"""Throwaway-container test fixture only; never packaged in the Core image."""
import json
import os
from pathlib import Path
import sys
import time
from .core import Job
from .core_backends import CoreBackends, current_pid_namespace
from .lifecycle_client import LifecycleClient
from .lifecycle_uds import FramedExchange, UnixConnector
from .test_core_integration import fake_process


def main():
    runtime = sys.argv[1]
    for path in ['/var/run/docker.sock', '/run/docker.sock']:
        assert not Path(path).exists(), 'Core must not have a Docker socket'
    client = LifecycleClient(FramedExchange(UnixConnector(runtime)),
                             FramedExchange(UnixConnector(runtime, control=True)),
                             timeout=5, read_timeout=2)
    host = client.status()
    backend = CoreBackends({'tokenizer_python': sys.executable}, '/not-used-by-fixture.json',
                           client, process_factory=fake_process)
    try:
        backend.abort()
        backend.start_flash()
        wrapper, engine = backend.flash.pid, backend.engine_pid
        identity = backend._process(engine)
        assert identity['pgid'] == wrapper and identity['sid'] == wrapper
        assert identity['uids'] == {os.getuid()}
        result = backend.generate(Job('flash', [{'role': 'user', 'content': 'fake'}], 8,
                                     time.monotonic() + 3), lambda: None)
        assert result['content'] == 'fake Flash'
        backend.abort()
        remaining = backend._process(engine)
        assert remaining is None or remaining['state'] == 'Z'
        assert backend.flash is None
        print(json.dumps({'result': 'PASS', 'uid': os.getuid(),
                          'core_pid_namespace': current_pid_namespace(),
                          'host_pid_namespace': host['host_pid_namespace'],
                          'separate_pid_namespaces': current_pid_namespace() != host['host_pid_namespace'],
                          'wrapper_local_pid': wrapper, 'engine_local_pid': engine,
                          'fake_flash_generation': True, 'owned_flash_group_stopped': True,
                          'docker_socket_absent': True}), flush=True)
    finally:
        backend.close()


if __name__ == '__main__': main()

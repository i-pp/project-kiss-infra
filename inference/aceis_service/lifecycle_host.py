"""Host-only adapter. Never package this or legacy backends in a Core image."""
from __future__ import annotations
import re
from .backends import Backends
from .core import ServiceError, snapshot
from .lifecycle import HostLifecycle


class OwnedOllama:
    """Reuse fixed image/mount/network/ownership checks from the accepted backend.

    Paths and policy come only from trusted host configuration. There is no
    arbitrary command, container, image, mount or model-import wire operation.
    """
    def __init__(self, config, config_path):
        self.backend = Backends(config, config_path)

    def _reconcile(self):
        if not self.backend.cid:
            cid = self.backend.docker('ps', '-aq', '--filter',
                                      'name=^/' + self.backend.config['container_name'] + '$')
            if cid:
                if not re.fullmatch(r'[0-9a-f]{12,64}', cid):
                    raise ServiceError('owned container identity ambiguous')
                self.backend.cid = cid
                self.backend.inspect_owned()

    def ensure(self, check):
        self.backend.start_ollama(check)

    def running(self):
        self._reconcile()
        if not self.backend.cid:
            return False
        info = self.backend.inspect_owned()
        if type(info['State']['Running']) is not bool:
            raise ServiceError('owned container state unconfirmed')
        return info['State']['Running']

    def stop(self):
        backend = self.backend
        self._reconcile()
        if backend.cid:
            info = backend.inspect_owned()
            if info['State']['Running']:
                backend.docker('stop', '-t', '3', backend.cid, timeout=10)
            # The CLI exit code alone is not this port's stop acknowledgement.
            if backend.inspect_owned()['State']['Running'] is not False:
                raise ServiceError('owned container stop unconfirmed')
        backend.active_model = None
        # Exact legacy two-reading physical GPU-idle barrier. Flash must first
        # have been stopped by its separate owning provider, not by PID guessing.
        backend.wait_idle()


def fixed_host_lifecycle(config, config_path):
    provider = OwnedOllama(config, config_path)
    return HostLifecycle(provider, snapshot, read_endpoint=lambda: provider.backend.address)

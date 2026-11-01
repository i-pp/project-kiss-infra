"""Synchronous local-trust SHA cache. Never loads a model or trusts old receipts."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import time


def identity(s):
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_uid, s.st_mode]


def open_dir(path):
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts:
        raise ValueError('Absolute nontraversing directory required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in p.parts[1:]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def private_fd(fd, directory=False):
    s = os.fstat(fd)
    if (s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
            or (not directory and s.st_nlink != 1)):
        raise ValueError('Private owner cache required')


def verify(directory, spec, cache, *, force=False, check=lambda: None, rate=256 << 20,
           budget=240, after_hash=lambda: None):
    """spec is a trusted pinned manifest. Caller serializes writers through loading.

    Returns metadata evidence, not protection against a privileged/same-owner
    adversary. Recheck with unchanged immediately before/after backend loading.
    """
    started = time.monotonic(); cpu = time.process_time()
    rows = spec['required_files']
    names = [r['name'] for r in rows]
    if (not rows or len(names) != len(set(names)) or any(Path(n).name != n or n in ('.','..') for n in names)
            or any(type(r['bytes']) is not int or r['bytes'] < 0 or len(r['sha256']) != 64
                   or any(c not in '0123456789abcdef' for c in r['sha256']) for r in rows)):
        raise ValueError('Invalid trusted manifest')
    cache = Path(cache)
    cache.mkdir(mode=0o700, exist_ok=True)
    cfd = open_dir(cache); dfd = None; lock = None; fds = {}
    try:
        private_fd(cfd, True)
        lock = os.open('verification.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=cfd)
        private_fd(lock); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dfd = open_dir(directory); root_stat = os.fstat(dfd); root = identity(root_stat)
        if root_stat.st_uid != os.getuid() or root_stat.st_mode & 0o022:
            raise ValueError('Model directory requires trusted owner writes only')
        if set(os.listdir(dfd)) - set(names) - {'acquisition.json'}:
            raise ValueError('Unexpected model directory entries')
        for row in rows:
            fd = os.open(row['name'], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
            fds[row['name']] = fd
            s = os.fstat(fd)
            if (not stat.S_ISREG(s.st_mode) or s.st_size != row['bytes'] or s.st_uid != os.getuid()
                    or s.st_mode & 0o022):
                raise ValueError('Model file size/type/owner/write permissions differ')
        before = {n: identity(os.fstat(fd)) for n, fd in fds.items()}
        binding = {'schema': 1, 'root_path': str(directory), 'root_identity': root,
                   'manifest': spec, 'files': before}
        key = hashlib.sha256(json.dumps({'root':str(directory),'manifest':spec}, sort_keys=True).encode()).hexdigest()+'.json'
        hit = False
        try:
            fd = os.open(key, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=cfd)
        except FileNotFoundError:
            fd = None
        if fd is not None:
            try:
                private_fd(fd)
                if os.fstat(fd).st_size > 1 << 20:
                    raise ValueError('Cache evidence exceeds bounded format')
                with os.fdopen(os.dup(fd), 'rb') as stream:
                    raw = stream.read(1 << 20)
                saved = json.loads(raw)
                hit = (saved.get('binding') == binding and saved.get('method') == 'FULL_SHA256_ALL_FILES'
                       and saved.get('digests') == {r['name']:r['sha256'] for r in rows})
            except (ValueError, TypeError, AttributeError):
                hit = False
            finally:
                os.close(fd)
        read_bytes = 0; next_check = 0
        def guard():
            nonlocal next_check
            now = time.monotonic()
            if now-started > budget: raise TimeoutError('Verification deadline')
            if now >= next_check:
                check(); next_check = now + .2
        guard()
        if force or not hit:
            if rate and sum(r['bytes'] for r in rows)/rate > budget:
                raise TimeoutError('Paced verification exceeds budget')
            for row in rows:
                fd=fds[row['name']]; h=hashlib.sha256()
                if hasattr(os,'POSIX_FADV_NOREUSE'):
                    try: os.posix_fadvise(fd,0,0,os.POSIX_FADV_NOREUSE)
                    except OSError: pass  # Hint only; never evict caches.
                while True:
                    guard(); block=os.read(fd,1<<20)
                    if not block: break
                    h.update(block);read_bytes+=len(block)
                    if rate:
                        target=started+read_bytes/rate
                        while time.monotonic()<target:
                            guard(); time.sleep(min(.05,max(0,target-time.monotonic())))
                if h.hexdigest()!=row['sha256']: raise ValueError('SHA256 mismatch: '+row['name'])
            after_hash()
        def recheck():
            guard()
            live=open_dir(directory)
            try:
                if identity(os.fstat(live)) != root or set(os.listdir(live))-set(names)-{'acquisition.json'}:
                    raise ValueError('Directory changed during verification')
                for n,fd in fds.items():
                    if before[n] != identity(os.fstat(fd)) or before[n] != identity(os.stat(n,dir_fd=live,follow_symlinks=False)):
                        raise ValueError('File changed during verification')
            finally: os.close(live)
        recheck()
        if force or not hit:
            payload={'binding':binding,'method':'FULL_SHA256_ALL_FILES',
                     'digests':{r['name']:r['sha256'] for r in rows},'verified_at_unix':time.time()}
            # Unique same-directory temp + fsync + atomic replace; private lock
            # serializes cache writers. No external receipt is accepted as proof.
            name='.tmp-'+os.urandom(16).hex()
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=cfd)
            try:
                with os.fdopen(fd,'w') as stream:
                    json.dump(payload,stream);stream.flush();os.fsync(stream.fileno())
                recheck();os.rename(name,key,src_dir_fd=cfd,dst_dir_fd=cfd);os.fsync(cfd)
            finally:
                try:os.unlink(name,dir_fd=cfd)
                except FileNotFoundError:pass
        return {'mode':'METADATA_CACHE_HIT' if hit and not force else 'FULL_SHA256',
                'bytes_hashed':read_bytes,'wall_seconds':time.monotonic()-started,
                'cpu_seconds':time.process_time()-cpu,'binding':binding}
    finally:
        for fd in fds.values():os.close(fd)
        if dfd is not None:os.close(dfd)
        if lock is not None:os.close(lock)
        os.close(cfd)


def unchanged(result):
    """Last-moment metadata check; caller must also exclude model writers."""
    b=result['binding'];fd=open_dir(b['root_path'])
    try:
        return (identity(os.fstat(fd))==b['root_identity'] and
                all(identity(os.stat(n,dir_fd=fd,follow_symlinks=False))==v for n,v in b['files'].items()))
    finally:os.close(fd)

"""Read-only verification of operator-reviewed fixed Strata artifacts; no acquisition."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import sys

COMMIT='5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d'
LLAMA_COMMIT='3cf03257f219afbe7334045ff7c6a06ac68c627d'
ENGINE_SHA='8e95a086515face5ce3a4d34d9ac3c485e45be5ff84a614e5b4ed66fc5efe18a'
SHARDS=[('Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf',37623740192),
        ('Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf',28800138432)]


def private_record(path):
    path=Path(path)
    s=path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1 or s.st_size>1048576:
        raise ValueError('Operator record must be owner-only regular file <=1MiB')
    return json.loads(path.read_text())


def safe_root(path):
    p=Path(path)
    if not p.is_absolute() or not p.is_dir() or any(x.is_symlink() for x in [p,*p.parents]):
        raise ValueError('Existing absolute directory without symlink ancestry required')
    return p


def regular(root,relative):
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('Relative reviewed artifact path required')
    p=Path(root)/rel
    if any(x.is_symlink() for x in [p,*p.parents] if x!=Path('/')) or not p.is_file():
        raise ValueError('Reviewed regular artifact required')
    return p


def verify_python_tree(root,manifest,subtree=None):
    root=safe_root(root)
    expected={row['path'] for row in manifest['files']}
    for row in manifest['files']:
        p=regular(root,row['path']);raw=p.read_bytes()
        digest=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if len(raw)!=row['bytes'] or digest!=row['git_blob_sha1']:
            raise ValueError('Pinned Python source differs: '+row['path'])
    search=root/subtree if subtree else root
    actual={str(p.relative_to(root)) for p in search.rglob('*.py') if '.git' not in p.relative_to(root).parts}
    if actual!=expected:raise ValueError('Unreviewed or missing Python modules in source tree')
    if any(p.suffix in {'.so','.pyd','.pth'} for p in search.rglob('*')):
        raise ValueError('Unreviewed extension or Python path hook in source tree')
    return {'commit':manifest['commit'],'python_files_verified':len(expected)}


def verify_bundle(root,record):
    root=safe_root(root)
    if (record.get('archive_sha256')!=ENGINE_SHA or record.get('engine_version')!='0.1.52'
            or record.get('signed_manifest_verified_by_operator') is not True
            or record.get('third_party_notices_reviewed_by_operator') is not True):
        raise ValueError('Exact package and operator manifest/notice review record required')
    if 'notice_review_evidence' in record:
        from notice_review import verify as verify_notice_review
        verify_notice_review(record['notice_review_evidence'],root)
    elif not any(p.is_file() and any(word in p.name.lower() for word in ['license','notice','copying'])
                 for p in root.rglob('*')):
        raise ValueError('Missing bundled notices require bound reviewed primary-source evidence')
    # These acknowledgments record human review; this function does NOT implement publisher signature verification.
    rows=record.get('files')
    if not isinstance(rows,list) or not rows or len(rows)>10000:raise ValueError('Reviewed extracted-file inventory required')
    expected=set()
    for row in rows:
        rel=row['path'];rp=Path(rel)
        if rel in expected or rp.is_absolute() or '..' in rp.parts or not rp.parts:raise ValueError('Duplicate or unsafe artifact')
        expected.add(rel);p=root/rp
        if row.get('type','file')=='symlink':
            target=p.resolve()
            if not p.is_symlink() or os.readlink(p)!=row.get('target') or not target.is_relative_to(root):
                raise ValueError('Reviewed bundle symlink escapes or differs')
            continue
        p=regular(root,rel)
        if p.stat().st_size!=row['bytes']:raise ValueError('Bundle artifact size differs')
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1048576),b''):h.update(b)
        if h.hexdigest()!=row['sha256']:raise ValueError('Bundle artifact digest differs')
    for row in rows:
        if row.get('type')=='symlink':
            target=(root/row['path']).resolve()
            if not target.is_file() or str(target.relative_to(root)) not in expected:
                raise ValueError('Symlink must resolve to a reviewed regular inventory file')
    # No unreviewed preloaded library/file may sit beside the executable.
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=expected:raise ValueError('Bundle has extra/unreviewed files or symlinks')
    exe=regular(root,record.get('entrypoint_relative',''))
    if not os.access(exe,os.X_OK):raise ValueError('Reviewed entrypoint is not executable')
    return exe


def dependencies():
    numpy='2.5.3' if sys.version_info>=(3,12) else '2.4.6' if sys.version_info>=(3,11) else '2.2.6'
    expected={'numpy':numpy,'Jinja2':'3.1.6','regex':'2026.9.10','PyYAML':'6.0.3','tqdm':'4.70.1','MarkupSafe':'3.0.3'}
    actual={}
    for name,version in expected.items():
        try:actual[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:actual[name]=None
        if actual[name]!=version:raise ValueError('Reviewed dependency unavailable/version differs: '+name)
    return actual


def verify(record_path,repo,manifest_root=None):
    record=private_record(record_path)
    allowed={'schema','source_commit','llama_commit','source_root','llama_root','engine_root',
             'engine','approval_reference','coordinator_runtime_relative'}
    if set(record)!=allowed or record['schema']!=1 or record['source_commit']!=COMMIT or record['llama_commit']!=LLAMA_COMMIT:
        raise ValueError('Fixed reviewed operator record schema required')
    if not isinstance(record['approval_reference'],str) or not record['approval_reference'].strip():
        raise ValueError('Record trusted human approval reference; the file itself grants no permission')
    rel=Path(record['coordinator_runtime_relative'])
    if rel.is_absolute() or '..' in rel.parts or len(rel.parts)!=2 or rel.parts[0]!='.runtime':
        raise ValueError('Existing coordinator runtime under .runtime only')
    manifests=Path(manifest_root or Path(__file__).parent)
    source=safe_root(record['source_root']);llama=safe_root(record['llama_root'])
    a=verify_python_tree(source,json.loads((manifests/'strata-source-files.json').read_text()))
    b=verify_python_tree(llama,json.loads((manifests/'gguf-source-files.json').read_text()),'gguf-py')
    from publisher_verify import verify_signed_bundle
    signed=verify_signed_bundle(record['engine_root'])
    if record['engine'].get('entrypoint_relative')!=signed['entrypoint_relative']:
        raise ValueError('Operator entrypoint differs from signed fixed engine')
    exe=verify_bundle(record['engine_root'],record['engine'])
    files=[]
    for name,size in SHARDS:
        p=regular(Path(repo)/'models/large-coder-b3/qwen38-flash-next',name)
        if p.stat().st_size!=size:raise ValueError('Existing fixed model size differs')
        files.append(p)
    return {'record':record,'source':source,'llama':llama,'exe':exe,'shards':files,
            'source_checks':[a,b],'dependencies':dependencies(),'publisher_integrity':signed}

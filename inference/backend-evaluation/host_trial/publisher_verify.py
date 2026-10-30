"""Verify fixed publisher public signatures and data; never execute supplied code."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

KEY_ID='5d1bc23abbeffd0d'
PUBLIC_B64='KjnXZB0T1r3dmBNot8h+c4rTicRtllg1LH9fUlTw4ZY='
MANIFEST_SHA='abd7ecedc07f5dddc1d4f5bd5e5ac0f4912bf279cd6becef4306c5b5d7fad2fa'
BUILD_ID='a42cc3d7df70+rocm'


def verify_payload(payload,signature):
    if not isinstance(signature,dict) or signature.get('alg')!='ed25519' or signature.get('key_id')!=KEY_ID:
        raise ValueError('Fixed publisher signature/key required')
    public=base64.b64decode(PUBLIC_B64,validate=True)
    raw=base64.b64decode(signature.get('value',''),validate=True)
    if len(public)!=32 or len(raw)!=64 or hashlib.sha256(public).digest()[:8].hex()!=KEY_ID:
        raise ValueError('Malformed publisher signature/public key')
    # Standard RFC8410 Ed25519 SubjectPublicKeyInfo wrapping the public bytes.
    with tempfile.TemporaryDirectory(prefix='aceis-public-signature-') as t:
        root=Path(t);(root/'public.der').write_bytes(bytes.fromhex('302a300506032b6570032100')+public)
        (root/'payload').write_bytes(payload);(root/'signature').write_bytes(raw)
        result=subprocess.run(['/usr/bin/openssl','pkeyutl','-verify','-pubin','-inkey',str(root/'public.der'),
            '-keyform','DER','-rawin','-in',str(root/'payload'),'-sigfile',str(root/'signature')],
            capture_output=True,timeout=10,env={'PATH':'/usr/bin:/bin','LANG':'C'})
    if result.returncode:raise ValueError('Publisher signature verification failed')
    return KEY_ID


def verify_signed_bundle(root):
    root=Path(root)
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):raise ValueError('No package symlink ancestry')
    manifest=root/'engine-component.json'
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>1048576:raise ValueError('Fixed manifest required')
    raw=manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA:raise ValueError('Package manifest differs from fixed signed feed')
    data=json.loads(raw)
    if (data.get('schema_version')!=2 or data.get('id')!='strata-engine' or data.get('version')!='0.1.52'
        or data.get('platform')!='linux-x86_64' or data.get('backend')!='hip' or data.get('archs')!=['gfx1151']
        or data.get('build_id')!=BUILD_ID or data.get('entrypoint')!='strata'):
        raise ValueError('Fixed HIP-halo component identity differs')
    payload=json.dumps({k:v for k,v in data.items() if k!='signature'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    verify_payload(payload,data.get('signature'))
    rows=data.get('files')
    if not isinstance(rows,list) or not rows or len(rows)>10000:raise ValueError('Bounded publisher file inventory required')
    seen=set();total=0
    for row in rows:
        rel=Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts or not rel.parts or str(rel) in seen:raise ValueError('Unsafe/duplicate publisher path')
        seen.add(str(rel));p=root/rel
        if any(q.is_symlink() for q in [p,*p.parents]) or not p.is_file():raise ValueError('Publisher regular files only; no symlink bypass')
        if p.stat().st_size!=row['bytes']:raise ValueError('Publisher file length mismatch')
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1048576),b''):h.update(b)
        if h.hexdigest()!=row['sha256']:raise ValueError('Publisher file digest mismatch')
        total+=row['bytes']
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=seen|{'engine-component.json'}:raise ValueError('Unlisted package file or link')
    if not os.access(root/'strata',os.X_OK):raise ValueError('Publisher engine executable mode missing')
    return {'status':'PUBLISHER_MANIFEST_AND_FILES_VERIFIED_NOT_EXECUTED','entrypoint_relative':'strata',
            'key_id':KEY_ID,'manifest_sha256':MANIFEST_SHA,'build_id':BUILD_ID,'file_bytes':total,'file_count':len(rows)}

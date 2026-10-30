"""Bind reviewed primary notice documents to one fixed local trial; no execution."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

from publisher_verify import MANIFEST_SHA


def read_bound(path, digest, private=False):
    path=Path(path)
    if (not path.is_absolute() or any(p.is_symlink() for p in [path,*path.parents])
            or not re.fullmatch('[0-9a-f]{64}',digest or '')):
        raise ValueError('Absolute non-symlink evidence and SHA256 required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        s=os.fstat(f.fileno())
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_nlink!=1
                or s.st_size>1048576 or (private and stat.S_IMODE(s.st_mode)!=0o600)):
            raise ValueError('Bounded owner evidence file required')
        raw=f.read(1048577)
    if len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('Notice evidence digest differs')
    return raw


def verify(reference, bundle):
    """Validate the evidence record, not a legal opinion or a new permission grant."""
    if not isinstance(reference,dict) or set(reference)!={'path','sha256'}:
        raise ValueError('Exact notice evidence reference required')
    data=json.loads(read_bound(reference['path'],reference['sha256'],private=True))
    if (data.get('schema')!=1 or data.get('bundle_manifest_sha256')!=MANIFEST_SHA
            or data.get('scope')!='ONE_INTERNAL_EVALUATION_NO_REDISTRIBUTION'
            or data.get('documents_actually_read') is not True):
        raise ValueError('Fixed bundle, local scope and actual review required')
    if data.get('unresolved_local_execution')!=[]:
        raise ValueError('Local execution terms remain unresolved')
    if not isinstance(data.get('unresolved_redistribution'),list):
        raise ValueError('Redistribution limitations must be recorded separately')
    manifest=json.loads((Path(bundle)/'engine-component.json').read_text())
    actual={row['path'] for row in manifest['files']}
    covered=data.get('covered_bundle_artifacts')
    if not isinstance(covered,list) or len(covered)!=len(set(covered)) or set(covered)!=actual:
        raise ValueError('Every fixed bundle artifact must be in the reviewed coverage')
    docs=data.get('documents')
    if not isinstance(docs,list) or not docs or len(docs)>100:
        raise ValueError('Reviewed primary documents required')
    ids=set()
    for doc in docs:
        if not isinstance(doc,dict) or not isinstance(doc.get('id'),str) or not doc['id'] or doc['id'] in ids:
            raise ValueError('Unique notice document identity required')
        ids.add(doc['id']);url=urlsplit(doc.get('origin_url',''))
        if (url.scheme!='https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or doc.get('actually_read') is not True):
            raise ValueError('Public primary origin and actual reading required')
        text=read_bound(doc['path'],doc['sha256']).decode('utf-8')
        if not text.strip():raise ValueError('Empty notice document')
    components=data.get('components')
    if not isinstance(components,list) or not components:raise ValueError('Artifact-to-document mapping required')
    mapped=[]
    for component in components:
        paths=component.get('artifacts');sources=component.get('document_ids')
        if (not isinstance(paths,list) or not paths or not isinstance(sources,list) or not sources
                or not set(sources)<=ids or component.get('local_execution_review')!='REVIEWED'
                or not isinstance(component.get('provenance_limitations'),str)):
            raise ValueError('Each component needs reviewed sources and honest provenance limitations')
        mapped.extend(paths)
    if len(mapped)!=len(set(mapped)) or set(mapped)!=actual:
        raise ValueError('Component mapping must cover each signed artifact exactly once')
    return {'status':'PRIMARY_NOTICE_EVIDENCE_BOUND','scope':data['scope'],
            'documents':len(docs),'covered_artifacts':len(actual),
            'unresolved_redistribution':data['unresolved_redistribution'],
            'legal_compliance_claimed':False}

"""Record operator-reviewed notices and independently verified signed package contents."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from host_strata_trial import host_guard,private_write
import assets


def inventory(root):
    root=assets.safe_root(root);rows=[]
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            target=p.resolve()
            if not target.is_relative_to(root) or not target.is_file():raise ValueError('Bundle link must target a regular file inside bundle')
            rows.append({'path':str(p.relative_to(root)),'type':'symlink','target':os.readlink(p)})
        elif p.is_file():
            h=hashlib.sha256()
            with p.open('rb') as f:
                for b in iter(lambda:f.read(1048576),b''):h.update(b)
            rows.append({'path':str(p.relative_to(root)),'type':'file','bytes':p.stat().st_size,'sha256':h.hexdigest()})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bootstrap-root',type=Path,required=True);p.add_argument('--engine-root',type=Path,required=True)
    p.add_argument('--entrypoint-relative',default='strata');p.add_argument('--coordinator-runtime-relative',required=True)
    p.add_argument('--approval-reference',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--confirm-publisher-manifest-and-notices-reviewed',action='store_true',required=True)
    p.add_argument('--notice-review-json',type=Path)
    p.add_argument('--notice-review-sha256')
    a=p.parse_args();repo=Path(__file__).resolve().parents[3];sys.path.insert(0,str(repo/'agents/local_llm'))
    from endpoint_config import private_json
    host=private_json(repo/'agents/local_llm/.runtime/router-host-profile.json');host_guard(host['orchestrator_root'])
    root=assets.safe_root(a.bootstrap_root)
    acquisition=json.loads((root/'acquisition.json').read_text())
    if acquisition.get('status')!='ACQUIRED_ENGINE_MANIFEST_AND_NOTICES_REVIEW_PENDING':raise ValueError('Bootstrap did not complete')
    from publisher_verify import verify_signed_bundle
    verified_publisher=verify_signed_bundle(a.engine_root)
    if a.entrypoint_relative!=verified_publisher['entrypoint_relative']:raise ValueError('Publisher entrypoint differs')
    reference=None
    if a.notice_review_json is not None or a.notice_review_sha256 is not None:
        if a.notice_review_json is None or a.notice_review_sha256 is None:
            raise ValueError('Notice evidence path and SHA256 are required together')
        reference={'path':str(a.notice_review_json),'sha256':a.notice_review_sha256}
        from notice_review import verify as verify_notice_review
        verify_notice_review(reference,a.engine_root)
    elif not any(p.is_file() and any(word in p.name.lower() for word in ['license','notice','copying'])
                 for p in a.engine_root.rglob('*')):
        raise ValueError('No bundled notices: provide reviewed primary-source evidence; do not fabricate acknowledgment')
    record={'schema':1,'source_commit':assets.COMMIT,'llama_commit':assets.LLAMA_COMMIT,
            'source_root':str(root/'strata-source'),'llama_root':str(root/'llama-source'),'engine_root':str(a.engine_root),
            'approval_reference':a.approval_reference,'coordinator_runtime_relative':a.coordinator_runtime_relative,
            'engine':{'archive_sha256':assets.ENGINE_SHA,'engine_version':'0.1.52',
                      'signed_manifest_verified_by_operator':True,'third_party_notices_reviewed_by_operator':True,
                      'entrypoint_relative':a.entrypoint_relative,'files':inventory(a.engine_root)}}
    if reference is not None:record['engine']['notice_review_evidence']=reference
    # Human confirmation is a record, not software authorization nor cryptographic signature verification.
    os.umask(0o077);private_write(a.output,record)
    try:verified=assets.verify(a.output,repo)
    except BaseException:
        print('Record retained but NOT_READY: asset verification failed; no execution.',file=sys.stderr);raise
    print(json.dumps({'status':'REVIEW_RECORD_WRITTEN_NO_ENGINE_EXECUTION','output':str(a.output),'dependencies':verified['dependencies']}))


if __name__=='__main__':raise SystemExit(main())

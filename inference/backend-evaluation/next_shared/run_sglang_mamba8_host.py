"""One approved fixed Mamba8/Next trial. Human HOST_CONTEXT only; inert by default."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import uuid
import host_api_trial as h
from paced_assets_v3 import verify as verify_slow, RATE, BUDGET_SECONDS
from total_swap_monitor import TotalSwapMonitor, self_diagnostics
from total_swap_trial import TotalSwapTrial
from owned_memory_telemetry import OwnedMemoryTelemetry

APPROVAL='Sentinel_e30296e71b348191bf2daef6442df3bd'
OPERATOR_SHA='2df4687ba91da7976506b6a6ef2559c6ee3fc3f01698057e52901568bb1918b3'
OPERATOR_REL='agents/local_llm/.runtime/next-sglang-path-inductor-approved-20261031.json'
MAMBA_REL='agents/local_llm/.runtime/backend-runtime/mamba-source-inspection/run-4274e98a095c455abd652569fd386b26/receipt.json'
MAMBA_SHA='31d23bf9ba5abbde76ee79d1b857c9feffbf8c037a925327fe6dc6583ab94c49'
LOADER_REL='agents/local_llm/.runtime/backend-runtime/loader-source-inspection/run-50948c70ab6f436d858d75f8b204492d/receipt.json'
LOADER_SHA='5f95ce6ca4620bf091b31d6cc5b2a1c7539d04211af96367a7f59eda74b6e7ba'
KERNEL_JIT_REL='agents/local_llm/.runtime/backend-runtime/jit-source-inspection/run-4f56c2e52dd249948ef3f6a480fc4a0d/receipt.json'
KERNEL_JIT_SHA='d68389e86a185816235833e0b7ca59dcd0ef5e48165e554aa54d4d3949f84427'
KERNEL_JIT_PROBE_SHA='a086caecb0af9f45de85a17b1154d25cc8019bef770f6c38abe8ab8c5b2d8466'
KERNEL_JIT_SOURCE_HASHES={'/sgl-workspace/sglang/python/sglang/srt/environ.py': '876dc17cf90f642940c8ba014af6cbd6e18eec0b3ae1b04abe3112eaeaa70a7a', '/sgl-workspace/sglang/python/sglang/kernels/jit/utils/compile/cache.py': '3a9c277d676596e467d6a1e700e65ab2fb5ccf91b264ebe1c3cc06659fa470bf', '/sgl-workspace/sglang/python/sglang/kernels/jit/utils/compile/loader.py': 'f0b8341b24a535234b5a91cb1e28c717b260cf4d703c32a114eba5e08926735e', '/sgl-workspace/sglang/python/sglang/kernels/jit/utils/compile/ninja.py': '082dff0b50a890f4987e1fb8caa0e0c6e77edfef766836ee4b17b5d3e514e218', '/sgl-workspace/sglang/python/sglang/kernels/fused_op.py': '2042fb5fb0fca33a93dd32fd05c8adc658bf44323840bd0391ef177e161163a9'}
PREFIX='/sgl-workspace/sglang/python/sglang/srt/'
SOURCE_HASHES={
 'arg_groups/fields/schedule.py':'67aa6f19add93821a0aa758a5d54a42c9c65a9e408a80c3fa4402bac459aaf9e',
 'configs/mamba_utils.py':'659d941b57b6960f1144e7c6a6e0449ea630b273ea69cb4f89312c10e0a8ff11',
 'mem_cache/memory_pool.py':'9017e2466950565ad1bf4ed0948c28ac234f65e39330aac20fb12aba30a41a03',
 'mem_cache/kv_cache_configurator.py':'bc4bc8797470e2d4c9677a1eae939648c888cce7c4e195cc92d0c13d0badd66b',
 'mem_cache/allocation_sizing.py':'c0a757827ab883850058a517629c98b9cfab69a2a9e0d26a3d5b9b4730f2f484',
 'configs/hybrid_arch.py':'0d8a23c8eb88abd930041c417923b0e2f43ad028a04bceced3784454926a33c3',
}


class Mamba8Trial(TotalSwapTrial):
    OPERATOR_SHA=OPERATOR_SHA
    TRIAL_AUTHORIZATION=APPROVAL
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.owned_memory=OwnedMemoryTelemetry()


def installed_project():
    path=Path(__file__).resolve()
    if (path.parent.name!='next_shared' or path.parent.parent.name!='backend-evaluation'
            or path.parent.parent.parent.name!='inference'):
        raise h.Blocked('FIXED_INSTALLED_MAMBA8_LAYOUT_REQUIRED')
    return h.safe_path(path.parents[3])


def validate_profile(record):
    review=record.get('review',{})
    required={
        'aiter_cache_profile':h.AITER_PROFILE,
        'aiter_source_receipt_sha256':h.AITER_RECEIPT_SHA,
        'sglang_sequential_loader_profile':'one-thread-v1',
        'sglang_mamba_cache_profile':'cache8-v1',
        'sglang_mamba_cache_authorization':APPROVAL,
        'sglang_mamba_cache_max_attempts':1,
        'sglang_mamba_source_receipt_sha256':MAMBA_SHA,
    }
    if any(type(review.get(k)) is not type(v) or review[k]!=v for k,v in required.items()):
        raise h.Blocked('FIXED_ONE_MAMBA8_PROFILE_REQUIRED')
    # Historical authorizations in the copied record describe inherited setup,
    # not another use of any old allowance. Only OPERATOR_SHA/APPROVAL is admitted.


def read_large_private(path,digest):
    path=h.safe_path(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        meta=os.fstat(f.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.getuid()
                or stat.S_IMODE(meta.st_mode)!=0o600 or meta.st_size>3*(1<<20)):
            raise h.Blocked('SOURCE_RECEIPT_OWNER_MODE_SIZE')
        raw=f.read(3*(1<<20)+1)
    if len(raw)>3*(1<<20) or hashlib.sha256(raw).hexdigest()!=digest:
        raise h.Blocked('FIXED_SOURCE_RECEIPT_DIGEST_CHANGED')
    return json.loads(raw)


def validate_mamba(receipt,record):
    runtime=record['runtimes']['sglang'];result=receipt.get('result',{})
    if (receipt.get('status')!='ALL_SIX_SOURCES_CAPTURED_NOT_COMPATIBILITY_PASS'
            or receipt.get('image')!=runtime['image_ref']
            or receipt.get('identity',{}).get('image_id')!=runtime['image_id']
            or receipt.get('cpu_container_absence_confirmed') is not True
            or receipt.get('gpu_device_access') is not False
            or any(type(receipt.get(k)) is not int or receipt[k]!=0 for k in ('generation_requests','model_lifecycle_requests'))
            or any(type(result.get(k)) is not int or result[k]!=0 for k in
                   ('source_executions','gpu_operations','generation_requests','model_lifecycle_requests'))
            or set(result.get('files',{}))!={PREFIX+x for x in SOURCE_HASHES}):
        raise h.Blocked('FIXED_MAMBA_SOURCE_EVIDENCE_REQUIRED')
    for name,digest in SOURCE_HASHES.items():
        row=result['files'][PREFIX+name];raw=row.get('source_text','').encode()
        if (row.get('status')!='READ' or row.get('source_executed') is not False
                or row.get('sha256')!=digest or hashlib.sha256(raw).hexdigest()!=digest
                or type(row.get('bytes')) is not int or row['bytes']!=len(raw)):
            raise h.Blocked('FIXED_MAMBA_SOURCE_CONTENT_CHANGED')
        ast.parse(raw)  # syntax only, never import/exec acquired backend code
    return {'receipt_relative':MAMBA_REL,'receipt_sha256':MAMBA_SHA,
            'source_sha256':SOURCE_HASHES,'source_executed':False,
            'runtime_fit_verified':False,'candidate':'cache8-v1'}


def validate_kernel_jit(receipt,record):
    runtime=record['runtimes']['sglang'];result=receipt.get('result',{})
    if (receipt.get('status')!='ALL_FIVE_SOURCES_CAPTURED_NOT_COMPATIBILITY_PASS'
            or receipt.get('image')!=runtime['image_ref']
            or receipt.get('identity',{}).get('image_id')!=runtime['image_id']
            or receipt.get('source_probe_sha256')!=KERNEL_JIT_PROBE_SHA
            or receipt.get('cpu_container_absence_confirmed') is not True
            or receipt.get('gpu_device_access') is not False
            or any(type(receipt.get(k)) is not int or receipt[k]!=0 for k in ('generation_requests','model_lifecycle_requests'))
            or any(type(result.get(k)) is not int or result[k]!=0 for k in
                   ('source_executions','gpu_operations','generation_requests','model_lifecycle_requests'))
            or set(result.get('files',{}))!=set(KERNEL_JIT_SOURCE_HASHES)):
        raise h.Blocked('FIXED_KERNEL_JIT_SOURCE_EVIDENCE_REQUIRED')
    total=0
    for path,digest in KERNEL_JIT_SOURCE_HASHES.items():
        row=result['files'][path];raw=row.get('source_text','').encode()
        if (row.get('status')!='READ' or row.get('source_executed') is not False
                or row.get('sha256')!=digest or hashlib.sha256(raw).hexdigest()!=digest
                or type(row.get('bytes')) is not int or row['bytes']!=len(raw)):
            raise h.Blocked('FIXED_KERNEL_JIT_SOURCE_CONTENT_CHANGED')
        ast.parse(raw);total+=len(raw)  # syntax/data only
    if total!=result.get('total_source_bytes'):raise h.Blocked('FIXED_KERNEL_JIT_SOURCE_SIZE_CHANGED')
    return {'receipt_relative':KERNEL_JIT_REL,'receipt_sha256':KERNEL_JIT_SHA,
            'source_sha256':KERNEL_JIT_SOURCE_HASHES,'source_executed':False,
            'cache_root':'/jit-cache/sglang','shared_exec_tmpfs_bytes':512<<20,
            'actual_image_cache_route_static_verified':True,
            'runtime_generation_or_capacity_pass':False}


def saved_evidence(project,record,driver):
    # No old asset-only run/intent assertions: the old GPU trial was consumed.
    # Source evidence itself is reusable; it is not a fresh trial allowance.
    validate_profile(record)
    mamba=validate_mamba(read_large_private(project/MAMBA_REL,MAMBA_SHA),record)
    kernel_jit=validate_kernel_jit(read_large_private(project/KERNEL_JIT_REL,KERNEL_JIT_SHA),record)
    aiter=h.private_read(project/h.AITER_RECEIPT_RELATIVE,h.AITER_RECEIPT_SHA)
    loader=h.private_read(project/LOADER_REL,LOADER_SHA)
    fixed=record['runtimes']['sglang']
    for receipt in [aiter,loader]:
        if (receipt.get('status')!='STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS'
                or receipt.get('image')!=fixed['image_ref']
                or receipt.get('identity',{}).get('image_id')!=fixed['image_id']
                or receipt.get('cpu_container_absence_confirmed') is not True
                or receipt.get('gpu_device_access') is not False
                or type(receipt.get('generation_requests')) is not int
                or receipt['generation_requests']!=0):
            raise h.Blocked('FIXED_INHERITED_SOURCE_RECEIPT_REQUIRED')
    folder=h.safe_path(project/'inference/backend-evaluation/sglang_content_handoff')
    sys.path.insert(0,str(folder))
    from loader_static_gate import confirm
    confirmation=confirm(loader['result'])
    image=driver.image(fixed['image_ref'])
    if image.get('Id')!=fixed['image_id'] or image.get('Config',{}).get('Volumes'):
        raise h.Blocked('CURRENT_FIXED_IMAGE_ID_OR_VOLUME_CONTRACT_CHANGED')
    return {'mamba':mamba,'kernel_jit':kernel_jit,'loader':{'sha256':LOADER_SHA,'confirmation':confirmation},
            'aiter':{'sha256':h.AITER_RECEIPT_SHA,'cache':'/jit-cache/aiter'},
            'current_image_id':image['Id'],'trial_authorization':APPROVAL,
            'operator_sha256':OPERATOR_SHA,'new_cpu_container_runs':0}


def plan():
    from fixed_trial_assets import manifest
    files=manifest()['required_files'];total=sum(r['bytes'] for r in files)
    if (len(files)!=20 or total/RATE>BUDGET_SECONDS
            or BUDGET_SECONDS+h.STARTUP_SECONDS['sglang']+90+185>h.WHOLE):
        raise h.Blocked('ASSET_SIZE_RATE_AND_WHOLE_BUDGET_INCONSISTENT')
    return {'files':20,'bytes':total,'rate_bytes_per_second':RATE,'nominal_paced_seconds':total/RATE,
            'asset_phase_seconds':BUDGET_SECONDS,'startup_seconds':300,'generation_seconds':90,
            'recovery_reserved_seconds':185,'whole_seconds':h.WHOLE,'baseline_reset':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-human-approved',action='store_true');args=parser.parse_args()
    if not args.run_human_approved:
        print(json.dumps({'status':'PREPARED_MAMBA8_NO_ACTIONS','generation_requests':0}));return 0
    started=time.monotonic()
    if not sys.stdin.isatty() or os.getuid()==0:raise h.Blocked('NONROOT_NORMAL_HOST_TTY_REQUIRED')
    h.install_sigterm_handler();project=installed_project()
    record=h.operator_record(project/OPERATOR_REL,OPERATOR_SHA,backend='sglang')
    if Path(record['project_root'])!=project:raise h.Blocked('FIXED_MAMBA8_PROJECT_MISMATCH')
    validate_profile(record)
    Coordinator,private_dir,write,probe=h.helpers();coordinator=Coordinator(record['project_root'],record)
    coordinator.guard()  # Unchanged real HOST_CONTEXT, pidfd, nonroot and TTY guard.
    root=private_dir(project/'agents/local_llm/.runtime/backend-api-trials')
    marker=h.approved_attempt_path(root,'sglang',OPERATOR_SHA)
    if marker.exists() or marker.is_symlink():raise h.Blocked('APPROVED_ATTEMPT_ALREADY_RESERVED_NO_RETRY')
    run=private_dir(root/('sglang-'+uuid.uuid4().hex))
    from trial_output import capture_run_output
    with capture_run_output(run) as output:
        code=execute_trial(project,record,coordinator,root,run,started,write)
        output.finish(code)
        return code


def execute_trial(project,record,coordinator,root,run,started,write):
    monitor=TotalSwapMonitor();monitor.attach_coordinator(coordinator);driver=h.Docker(coordinator.guard)
    try:
        budget=plan();write(run/'asset-read-plan.json',budget)
        print(json.dumps({'event':'asset_read_plan','candidate':'mamba8',**budget}),flush=True)
        # Lock+idle check before even the saved-evidence/fresh-image read.
        with coordinator.locked():
            coordinator.guard();coordinator.idle()
            write(run/'saved-source-preflight.json',saved_evidence(project,record,driver))
        coordinator.guard()
    except BaseException as exc:
        write(run/'preflight-failure.json',{'reason':type(exc).__name__+':'+str(exc)[:256],
              'generation_requests':0,'model_lifecycle_requests':0,'automatic_retry':False})
        print(json.dumps({'status':'BLOCKED_BEFORE_ASSET_OR_MODEL_ACTION','audit':str(run),'reason':str(exc)[:256]}),flush=True)
        return 1
    def progress(row):
        entry={'elapsed':round(time.monotonic()-started,3),**row,'diagnostic_only':True}
        try:
            entry.update(host_resources=monitor.raw(),native_process=self_diagnostics(),probe_overhead=monitor.sampler.stats())
        except Exception as exc:entry.update(diagnostic_status='UNAVAILABLE',error_class=type(exc).__name__)
        write(run/('asset-read-'+uuid.uuid4().hex+'.json'),entry);print(json.dumps(entry),flush=True)
    trial=None
    def verify(directory,check):return verify_slow(directory,check=check,cheap_check=lambda:trial.remaining(1),report=progress)
    sys.path.insert(0,str(project/'agents/local_llm'));from local_llm import policy_context
    def reserve_attempt():
        trial.safety(start=True,force=True)
        return h.reserve_approved_attempt(root,'sglang',OPERATOR_SHA,run)
    trial=Mamba8Trial(record,'sglang',coordinator,driver,h.LocalHTTP(),monitor.raw,run,write,policy_context,
        monitor=monitor,verify=verify,start_time=started,reserve_attempt=reserve_attempt,operator_sha256=OPERATOR_SHA)
    outcome=trial.execute();print(json.dumps(outcome),flush=True)
    return 0 if outcome['status']=='COMPLETED' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_NO_AUTOMATIC_RETRY','reason':type(exc).__name__+':'+str(exc)[:256]}),file=sys.stderr)
        raise SystemExit(1)

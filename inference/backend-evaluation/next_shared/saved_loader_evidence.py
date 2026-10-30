"""Read-only reuse of one fixed successful static check and zero-lifecycle run."""
import json,sys
from pathlib import Path
from fixed_trial_assets import Blocked,private_read,safe_path
RECEIPT_REL='agents/local_llm/.runtime/backend-runtime/loader-source-inspection/run-50948c70ab6f436d858d75f8b204492d/receipt.json'
RECEIPT_SHA='5f95ce6ca4620bf091b31d6cc5b2a1c7539d04211af96367a7f59eda74b6e7ba'
RUN_REL='agents/local_llm/.runtime/backend-api-trials/sglang-54b722c61d324f34b20bad1f2efb75d6'
SUMMARY_SHA='d961a15f72917cba273a5d2a14f7d9abf2f549fc7daf8cafa86715cb22dcc6f3'
OPERATOR='9f3d6953c389d9bca94020de8b8cdbcaedd4580d458cd78dda57af8073338d96'
PREFLIGHT_SHA='80808646a94656dc4340c6503ead1e94c98462d8b3bd977540492482861b4c12'


def validate(record,driver):
    root=Path(record['project_root']);folder=safe_path(root/'inference/backend-evaluation/sglang_content_handoff')
    sys.path.insert(0,str(folder))
    from inspect_loader_source_host import validate as validate_static
    from loader_static_gate import confirm
    runtime=root/'agents/local_llm/.runtime';trials=runtime/'backend-api-trials'
    for marker in [runtime/'UNCERTAIN.json',trials/('attempt-sglang-'+OPERATOR+'.json')]:
        if marker.exists() or marker.is_symlink():raise Blocked('ATTEMPT_ALREADY_CONSUMED_OR_UNCERTAIN')
    old=private_read(root/RUN_REL/'summary.json',SUMMARY_SHA)
    intent=private_read(trials/('preflight-sglang-'+OPERATOR+'.json'),PREFLIGHT_SHA)
    if (intent.get('run')!=str(root/RUN_REL) or old.get('environment')!='NOT_RUN'
        or old.get('generation_requests')!=0 or old.get('generation_request_intents')!=0
        or old.get('restoration')!='NOT_NEEDED' or old.get('cleanup_confirmed') is not True):
        raise Blocked('PRIOR_ZERO_LIFECYCLE_ASSET_FAILURE_NOT_CONFIRMED')
    receipt=private_read(root/RECEIPT_REL,RECEIPT_SHA);fixed=record['runtimes']['sglang']
    if (receipt.get('status')!='STATIC_SOURCE_CAPTURED_NOT_IMPORT_OR_INFERENCE_PASS'
        or receipt.get('image')!=fixed['image_ref'] or receipt.get('identity',{}).get('image_id')!=fixed['image_id']
        or receipt.get('cpu_container_absence_confirmed') is not True
        or receipt.get('gpu_device_access') is not False or receipt.get('generation_requests')!=0):
        raise Blocked('FIXED_STATIC_RECEIPT_IDENTITY_MISMATCH')
    confirmation=confirm(validate_static(receipt['result']))
    image=driver.image(fixed['image_ref'])  # fresh normal-host read, before any asset scan/unload
    if image.get('Id')!=fixed['image_id'] or image.get('Config',{}).get('Volumes'):
        raise Blocked('CURRENT_IMAGE_ID_OR_VOLUME_CONTRACT_MISMATCH')
    return {'status':'SAVED_STATIC_SOURCE_REUSED_CURRENT_IMAGE_ID_CONFIRMED',
        'receipt_relative':RECEIPT_REL,'receipt_sha256':RECEIPT_SHA,'prior_summary_sha256':SUMMARY_SHA,
        'original_preflight_intent_sha256':PREFLIGHT_SHA,'current_image_id':image['Id'],
        'selected_source_sha256':confirmation['source_sha256'],'prior_attempt_consumed':False,
        'original_evidence_preserved':True,'source_executed':False}

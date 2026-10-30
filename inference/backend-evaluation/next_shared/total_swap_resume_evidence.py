"""Bind the new user total-swap allowance to the same unspent SG trial and old audits."""
from pathlib import Path
import saved_loader_evidence
from fixed_trial_assets import Blocked,private_read
from total_swap_limits import AUTHORIZATION,USER_TOTAL_LIMIT
AUTH_SHA='b15c762d6a99ee6aa6726b0e2fa656851518d2b2a7f6da81af799218605864a2'
LATEST_RUN='agents/local_llm/.runtime/backend-api-trials/sglang-1627dfedc60b4d59a1cabf6dcb26273c'
LATEST_SUMMARY_SHA='eb55207834d5c39949b12ae782973d10b672536970fd790c0d2f714bdc6b522d'
RESUME_INTENT_SHA='d362de29a5e6b2d3372d56d3fc49a36ce0318dcc2c738e8bd3f7f3c282b67733'


def authorization(project):
    p=Path(project)/'agents/local_llm/.runtime/sglang-host-total-swap-8gb-authorization.json'
    value=private_read(p,AUTH_SHA)
    if (value.get('authorization')!=AUTHORIZATION or value.get('original_gpu_operator_sha256')!=saved_loader_evidence.OPERATOR
        or type(value.get('host_swap_total_used_limit_bytes')) is not int
        or value['host_swap_total_used_limit_bytes']!=USER_TOTAL_LIMIT or value.get('new_gpu_allowance') is not False):
        raise Blocked('FIXED_HOST_TOTAL_SWAP_AUTHORIZATION_REQUIRED')
    return {'authorization':AUTHORIZATION,'record_sha256':AUTH_SHA,'total_used_limit_bytes':USER_TOTAL_LIMIT,'new_gpu_allowance':False}


def validate(record,driver):
    project=Path(record['project_root']);auth=authorization(project)
    latest=private_read(project/LATEST_RUN/'summary.json',LATEST_SUMMARY_SHA)
    old_resume=private_read(project/'agents/local_llm/.runtime/backend-api-trials'/('asset-resume-sglang-'+saved_loader_evidence.OPERATOR+'.json'),RESUME_INTENT_SHA)
    if (old_resume.get('run')!=str(project/LATEST_RUN) or latest.get('environment')!='NOT_RUN'
        or latest.get('generation_requests')!=0 or latest.get('generation_request_intents')!=0
        or latest.get('restoration')!='NOT_NEEDED' or latest.get('cleanup_confirmed') is not True):
        raise Blocked('LATEST_ASSET_ONLY_FAILURE_NOT_CONFIRMED')
    original=saved_loader_evidence.validate(record,driver)  # original intent/zero-run/static receipt + fresh image ID
    return {**original,'new_total_swap_authorization':auth,'latest_zero_lifecycle_summary_sha256':LATEST_SUMMARY_SHA,
            'original_asset_resume_intent_sha256':RESUME_INTENT_SHA,'previous_failures_preserved':True}

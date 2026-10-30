"""Offline metadata validation only. No downloads, imports of Strata, launch or HTTP."""
import json
from pathlib import Path

SOURCE_COMMIT = '5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d'
MODEL_REVISION = 'ed59f92082b1e93c0e96d60a8b11aab089b52f09'
SHARDS = (
    ('Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf',37623740192,
     '69820c02ec7d0b45ef2ebb19d6620299db749fe2aded7f39f93c6b88b199b720'),
    ('Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf',28800138432,
     '316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113'),
)
ENGINE = ('strata-engine-0.1.52-linux-x86_64-hip-halo.tar.gz',
          '8e95a086515face5ce3a4d34d9ac3c485e45be5ff84a614e5b4ed66fc5efe18a')


def validate(data,profile='qwen38-flash-next'):
    if profile not in ('qwen38-flash-next','qwen-coder-next','gpt-oss-120b'):
        raise ValueError('Unknown profile')
    if data.get('backend')!='strata' or data.get('source',{}).get('commit')!=SOURCE_COMMIT:
        raise ValueError('Unpinned source')
    package=data['packages'][0]
    if (package.get('name'),package.get('sha256'))!=ENGINE or package.get('arch')!='gfx1151':
        raise ValueError('Wrong engine package')
    if package.get('url')!='https://github.com/Niko1221/Strata/releases/download/v0.2.7/'+ENGINE[0]:
        raise ValueError('Unpinned package origin')
    weights=data['weights']
    actual=tuple((r.get('name'),r.get('bytes'),r.get('sha256')) for r in weights['shards'])
    if weights.get('revision')!=MODEL_REVISION or actual!=SHARDS:
        raise ValueError('Input weights do not match official fixed input')
    prep=data['preparation'];env=data['environment']
    if prep.get('mtp') is not False or prep.get('vision') is not False:
        raise ValueError('This preparation permits neither extra MTP nor vision assets')
    if prep.get('automatic_installer_execution') is not False or env.get('namespace_creation_allowed') is not False or env.get('host_escalated_gpu_execution_allowed') is not False:
        raise ValueError('Launch or isolation escalation is outside this preparation')
    if any(data['scope'].get(k)!=0 for k in ('downloads','new_software_executions','model_loads','generations','host_changes')):
        raise ValueError('Manifest no longer represents offline preparation')
    blockers=[]
    supported=profile=='qwen38-flash-next'
    if not supported:blockers.append('NO_VERIFIED_STRATA_ARCHITECTURE_PATH')
    if not env.get('native_engine_found'):blockers.append('ENGINE_NOT_INSTALLED')
    if not env.get('dev_kfd_available') or not env.get('renderD128_available'):blockers.append('GPU_DEVICES_ABSENT_IN_CODEX_ISOLATION')
    blockers+=['NATIVE_SOFTWARE_EXECUTION_ACTION_TIME_REVIEW_REQUIRED','PACK_AND_MEMORY_BUDGET_NOT_YET_VALIDATED']
    return {'profile':profile,'input_compatibility_supported':supported,
            'large_weight_redownload_required':False if supported else None,
            'status':'BLOCKED','blockers':blockers,'can_execute':False,
            'metadata_check':'PASS','generation_requests':0}


if __name__=='__main__':
    data=json.loads(Path(__file__).with_name('strata-preparation.json').read_text())
    print(json.dumps([validate(data,p) for p in ('qwen38-flash-next','qwen-coder-next','gpt-oss-120b')],indent=2))

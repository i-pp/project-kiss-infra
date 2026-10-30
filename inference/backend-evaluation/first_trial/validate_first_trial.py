"""Validate one inert human-review proposal. Never fetch, launch or send requests."""
import json
from pathlib import Path

ENGINE='strata-engine-0.1.52-linux-x86_64-hip-halo.tar.gz'
SHA='8e95a086515face5ce3a4d34d9ac3c485e45be5ff84a614e5b4ed66fc5efe18a'
COMMIT='5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d'


def validate(data,config):
    if data.get('profile')!='qwen38-flash-next' or data.get('backend')!='strata':raise ValueError('Single fixed candidate only')
    package=data['engine']
    if (package.get('name'),package.get('bytes'),package.get('sha256'))!=(ENGINE,169966238,SHA):raise ValueError('Engine identity differs')
    if package.get('url')!='https://github.com/Niko1221/Strata/releases/download/v0.2.7/'+ENGINE or data.get('source_commit')!=COMMIT:raise ValueError('Unpinned source')
    if data.get('execution_allowed') is not False or data.get('individual_software_execution_approval')!='PENDING':raise ValueError('Inert proposal only; approval cannot be inferred from a file')
    if data.get('new_weight_download_bytes')!=0 or data.get('recompute_existing_model_sha_now') is not False:raise ValueError('Existing input evidence must be reused')
    if any(data['prohibited'].get(k) is not True for k in ['new_namespace','host_escalation_from_codex','docker_from_codex','new_credentials','host_setting_changes','existing_cap_changes']):raise ValueError('Protection changed')
    b=data['budget']
    if (b['expert_cache_slots'],b['context'],b['prefill'],b['max_output_tokens'],b['max_generations'])!=(1024,8192,512,128,1):raise ValueError('Fixed finite trial only')
    if b['mtp'] is not False or b['vision'] is not False or b['generation_retries']!=0:raise ValueError('Extra assets or retries not permitted')
    if (b['native_rss_soft_stop_gib'],b['host_available_after_unload_min_gib'],b['host_available_runtime_min_gib'],b['global_gpu_max_gib'])!=(48,64,16,58):raise ValueError('Unreviewed memory budget')
    if b['hard_memory_guarantee'] is not False or b['existing_router_memory_cap_gib']!=32:raise ValueError('Do not claim or change a hard cap')
    if (b['new_disk_budget_gib'],b['disk_growth_soft_stop_gib'],b['free_disk_before_min_gib'])!=(80,70,100):raise ValueError('Disk budget differs')
    if b['pack_seconds_cap']!=1800 or b['startup_seconds']!=90 or b['generation_seconds']!=90 or b['stop_seconds']!=45 or b['restore_seconds']!=120:raise ValueError('Time bounds differ')
    if set(config)!={'exe','cwd','args','tokenizer','model_name','mtp'} or config['model_name']!='kiss-strata-qwen38-flash-next' or config['mtp'] is not False:raise ValueError('Config contains extra hooks/features')
    expected=['--pack','<NEW_VERIFIED_PACK_DIR>','--native','<EXISTING_FLASH_SHARD1>',
              '--ple-gguf','<EXISTING_FLASH_SHARD2>','--expert-cache','1024','--max-context','8192','--prefill','512']
    if config['args']!=expected or config['exe']!='<VERIFIED_HIP_ENGINE_ENTRYPOINT>' or config['cwd']!='<PINNED_STRATA_SOURCE>' or config['tokenizer']!='<NEW_VERIFIED_PACK_DIR>/tokenizer':raise ValueError('Only the portable inert template is validated')
    return {'validation':'PASS','status':'READY_FOR_ONE_HUMAN_DECISION_NOT_EXECUTION',
            'execution_allowed':False,'individual_approval':'PENDING','human_gpu_bootstrap_required':True,
            'max_trial_generations':1,'actual_generations':0,'actual_downloads':0,
            'unresolved':['Extracted artifact integrity/third-party notices','Measured pack/runtime peak and memory fit','Authorized usable GPU context']}


if __name__=='__main__':
    root=Path(__file__).resolve().parent
    print(json.dumps(validate(json.loads((root/'first-trial.json').read_text()),json.loads((root/'strata-host-config.EXAMPLE.json').read_text())),indent=2))

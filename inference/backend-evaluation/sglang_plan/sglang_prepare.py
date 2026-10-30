"""Offline eligibility only. Never launches/imports an inference runtime."""
import json
from pathlib import Path
import re

GIB=1024**3
PROFILES=('qwen-coder-next','qwen38-flash-next','gpt-oss-120b')
FORMATS=('gguf','safetensors_bf16','safetensors_fp8','safetensors_mxfp4')
KEYS={'weight_format','checkpoint_present','runtime_verified','native_gpu_access',
      'rdna_kernels_verified','projected_min_available_ram_bytes','projected_peak_gpu_bytes',
      'immutable_runtime_ref'}


def evaluate(profile,facts=None):
    if profile not in PROFILES:raise ValueError('Fixed SGLang profile required')
    facts={} if facts is None else dict(facts)
    if set(facts)-KEYS:raise ValueError('Unexpected planning input')
    fmt=facts.get('weight_format','gguf')
    if fmt not in FORMATS:raise ValueError('Fixed weight format required')
    reasons=[]
    if fmt=='gguf':reasons.append('GGUF_HIP_UNSUPPORTED')
    if fmt=='safetensors_mxfp4':reasons.append('MXFP4_REQUIRES_CDNA_NOT_GFX1151')
    for key,code in [('checkpoint_present','COMPATIBLE_CHECKPOINT_NOT_VERIFIED'),
                     ('runtime_verified','SGLANG_RUNTIME_NOT_VERIFIED'),
                     ('native_gpu_access','NO_AUTHORIZED_GPU_EXECUTION_PATH'),
                     ('rdna_kernels_verified','RDNA_KERNELS_NOT_VERIFIED')]:
        if facts.get(key) is not True:reasons.append(code)
    ref=facts.get('immutable_runtime_ref','')
    if not isinstance(ref,str) or re.fullmatch('sha256:[0-9a-f]{64}',ref) is None:
        reasons.append('RUNTIME_DIGEST_NOT_PINNED')
    ram=facts.get('projected_min_available_ram_bytes')
    gpu=facts.get('projected_peak_gpu_bytes')
    if type(ram) is not int or ram<24*GIB:reasons.append('RAM_HEADROOM_NOT_VERIFIED')
    if type(gpu) is not int or not 0<=gpu<=58*GIB:reasons.append('GPU_LIMIT_NOT_VERIFIED')
    manifest=json.loads(Path(__file__).with_name('sglang-readiness.json').read_text())
    return {'profile':profile,'backend':'sglang','source_version':manifest['source_version'],
            'status':'BLOCKED' if reasons else 'READY_FOR_MANUAL_REVIEW',
            'blockers':reasons,'launch_draft':None if reasons else manifest['launch_draft'],
            'execution_allowed':False,'environment_verdict':'NOT_RUN',
            'model_quality_verdict':'UNASSESSED','generation_count':0}


if __name__=='__main__':
    print(json.dumps({'profiles':[evaluate(p) for p in PROFILES]},indent=2))

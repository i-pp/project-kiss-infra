"""vLLM target readiness. Never launch or import vLLM, install a plugin, or download."""
PROFILES=('qwen-coder-next','qwen38-flash-next','gpt-oss-120b')
IMAGE='vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905'
SOURCE='5df63a7203cdb9328d824a27b682e77c7b9928be'


def evaluate(profile):
    if profile not in PROFILES:raise ValueError('Fixed target profile required')
    return {'backend':'vllm','profile':profile,'status':'BLOCKED','execution_allowed':False,
            'environment_verdict':'NOT_RUN','model_quality_verdict':'UNASSESSED','generation_count':0,
            'historical_environment':{'image':IMAGE,'version':'0.32.0+rocm723',
                'small_model':'Qwen2.5-Coder-1.5B BF16','gpu_api_restart':'PASS','long_instruction_following':'FAIL',
                'current_image_presence':'NOT_REINSPECTED_DOCKER_PERMISSION_UNAVAILABLE'},
            'target_weight_format':'existing GGUF; not the historical BF16 checkpoint',
            'blockers':['EXACT_GGUF_PLUGIN_MAPPING_AND_HIP_KERNELS_UNVERIFIED',
                        'FIXED_IMAGE_GGUF_PLUGIN_PRESENCE_UNVERIFIED',
                        'TARGET_LOCAL_HF_CONFIG_AND_TOKENIZER_NOT_PREPARED',
                        'NO_CURRENT_AUTHORIZED_TARGET_SERVER'],
            'native_launch_draft':{'status':'NOT_EXECUTABLE_UNTIL_PREREQUISITES_REVIEWED',
                'argv':['vllm','serve','<EXISTING_TARGET_GGUF>',
                        '--tokenizer','<VERIFIED_LOCAL_TOKENIZER>',
                        '--hf-config-path','<VERIFIED_LOCAL_CONFIG>',
                        '--served-model-name','<FIXED_TARGET_ALIAS>',
                        '--host','127.0.0.1','--port','8081','--max-model-len','8192',
                        '--max-num-seqs','1','--tensor-parallel-size','1','--enforce-eager'],
                'notes':['No B1 small-model rerun is a target-model result.',
                         'Do not run the old B1 Docker runner: it creates isolation and assumes the old30B container is running.',
                         'GPU utilization/KV/offload and exact quantization compatibility require a measured reviewed budget.',
                         'No fallback to another model, dtype or backend; no automatic Hugging Face downloads.']},
            'sources':[{'url':'https://raw.githubusercontent.com/vllm-project/vllm/'+SOURCE+'/docs/features/quantization/gguf.md',
                        'fact':'Pinned source requires out-of-tree GGUF plugin; conversion/tokenizer caveats.'},
                       {'url':'https://github.com/vllm-project/vllm-gguf-plugin',
                        'fact':'General model registry support alone does not prove GGUF tensor mapping or HIP operation.'},
                       {'url':'https://docs.vllm.ai/en/stable/getting_started/installation/gpu/',
                        'fact':'gfx1151 is listed; this is not proof for these model/quantization combinations.'}]}

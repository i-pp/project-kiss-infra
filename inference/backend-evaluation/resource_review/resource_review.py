"""Source-derived lower bounds only. No model/source imports, requests or launcher."""
import json
from pathlib import Path

GIB=1<<30
COMMIT='5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d'


def lower_bounds(mode='arena',context=8192,cache_slots=1024):
    if mode not in ('arena','file_mmap') or context!=8192 or cache_slots!=1024:
        raise ValueError('Only the inspected fixed-source configuration is calculated')
    arena=48*512*1382400
    # Live arrays at pack_layer.py's out.write(blobs.tobytes()):
    # gate/up/down byte backing + interleaved gate/up + concatenated blobs + bytes copy.
    layer_role=512*460800
    pack_arrays=3*layer_role+2*layer_role+3*layer_role+3*layer_role
    gdn_state=36*(128*48*128+10240*(4-1))*4
    kv_fp16=12*context*2*256*2*2
    cache=cache_slots*1382400
    return {
        'source_commit':COMMIT,'mode':mode,
        'pack_expert_live_arrays_lower_bytes':pack_arrays,
        'pack_total_peak_upper_bytes':None,
        'expert_file_or_arena_bytes':arena,
        'host_eager_expert_copy_bytes':arena if mode=='arena' else 0,
        'mmap_virtual_bytes':arena if mode=='file_mmap' else 0,
        'mmap_resident_working_set_bytes':None,
        'gpu_expert_cache_bytes':cache,
        'gpu_gdn_recurrent_state_bytes':gdn_state,
        'gpu_fp16_kv_payload_lower_bytes':kv_fp16,
        'gpu_known_component_lower_bytes':cache+gdn_state+kv_fp16,
        'host_total_peak_upper_bytes':None,
        'gpu_total_peak_upper_bytes':None,
        'missing':['pack dense conversion/verify peak','pack index and native dense allocations',
                   'prefill/staging and allocator/driver overhead','file-cache resident peak',
                   'post-unload usable memory and active workloads','binary/source build correspondence'],
        'can_execute':False,
    }


def review(mode='arena',memtotal_kib=64411456,start_available_min_gib=None):
    if memtotal_kib<=0:raise ValueError('OS memory must be measured and positive')
    result=lower_bounds(mode)
    result['os_memtotal_bytes']=memtotal_kib*1024
    result['host_bytes_left_after_16gib_reserve']=max(0,memtotal_kib*1024-16*GIB)
    if start_available_min_gib is not None and start_available_min_gib*GIB>result['os_memtotal_bytes']:
        result['status']='INFEASIBLE_START_GATE'
    elif result['host_eager_expert_copy_bytes']>result['host_bytes_left_after_16gib_reserve']:
        result['status']='INFEASIBLE_KNOWN_HOST_LOWER_BOUND'
    else:
        result['status']='UNKNOWN_PEAK_NOT_EXECUTION_READY'
    # A lower bound fitting, a mapping or a software approval never supplies missing upper bounds.
    result['can_execute']=False
    return result


if __name__=='__main__':
    print(json.dumps({'old_proposal':review(start_available_min_gib=64),
                      'arena_reconsidered':review(),
                      'mmap_reconsidered':review('file_mmap')},indent=2))

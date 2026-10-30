"""One fixed restoration residual-swap evidence policy.

This module has no file/socket/process/marker access.
The approved continuation separately hash-binds the actual recovery audit, receipt,
state, intent, original UNKNOWN, fixed boot and measured577536-byte baseline.
"""

GIB=1<<30
FIXED_BASELINE=577536
MAX_RESIDUAL=1<<20


class PolicyBlocked(RuntimeError):pass


class FixedSteadySwap:
    def __init__(self,boot_id,baseline):
        if (not isinstance(boot_id,str) or len(boot_id)!=36 or type(baseline) is not int
                or baseline!=FIXED_BASELINE or baseline>MAX_RESIDUAL):
            raise PolicyBlocked('FIXED_MEASURED_BASELINE_REQUIRED')
        self.boot_id=boot_id;self.baseline=baseline;self.samples=[]

    def sample(self,elapsed,boot_id,resource,vmstat):
        if (type(elapsed) not in (int,float) or elapsed<0 or elapsed>30
                or (self.samples and not self.samples[-1]['elapsed']<elapsed<=self.samples[-1]['elapsed']+5)):
            raise PolicyBlocked('FRESH_FINITE_MONOTONIC_SAMPLES_REQUIRED')
        if boot_id!=self.boot_id:raise PolicyBlocked('BOOT_CHANGED')
        if (not isinstance(resource,dict) or any(type(resource.get(k)) is not int or resource[k]<0
                for k in ('available_bytes','gpu_used_bytes','swap_used_bytes'))):
            raise PolicyBlocked('RESOURCE_EVIDENCE_UNAVAILABLE')
        if (resource['available_bytes']<24*GIB or resource['gpu_used_bytes']>58*GIB
                or resource['swap_used_bytes']!=self.baseline):
            raise PolicyBlocked('RESOURCE_OR_FIXED_SWAP_CHANGED')
        if (not isinstance(vmstat,dict) or any(type(vmstat.get(k)) is not int or vmstat[k]<0 for k in ('pswpin','pswpout'))):
            raise PolicyBlocked('SWAP_IO_EVIDENCE_UNAVAILABLE')
        if self.samples and vmstat!=self.samples[0]['vmstat']:
            raise PolicyBlocked('SWAP_IO_CHANGED')
        self.samples.append({'elapsed':elapsed,'boot_id':boot_id,'resources':dict(resource),'vmstat':dict(vmstat)})

    def finish(self):
        if len(self.samples)<3 or self.samples[-1]['elapsed']-self.samples[0]['elapsed']<10:
            raise PolicyBlocked('TEN_SECONDS_OF_STABILITY_REQUIRED')
        return {'status':'FIXED_RESIDUAL_SWAP_STEADY_EVIDENCE_ONLY','baseline':self.baseline,
            'samples':list(self.samples),'archive_authorized':False,'generation_authorized':False}

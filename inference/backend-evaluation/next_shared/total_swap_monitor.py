"""Coherent read-only meminfo+GPU sample shared across monitor threads at5Hz."""
import copy,glob,os,resource,threading,time
from pathlib import Path
from paging_telemetry import read_paging
from sampled_probe import SampledProbe
from total_swap_limits import TotalSwapLimits


def read_global():
    # Total/Free/Used derive from one meminfo buffer, never independently polled.
    fields={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
    total=fields['SwapTotal'];free=fields['SwapFree'];vram=0;gtt=0;devices=set()
    for item in glob.glob('/sys/class/drm/card[0-9]*/device/mem_info_vram_used'):
        p=Path(item);identity=str(p.parent.resolve())
        if identity in devices:continue
        devices.add(identity);vram+=int(p.read_text());g=p.parent/'mem_info_gtt_used'
        if g.exists():gtt+=int(g.read_text())
    value={'mem_available':fields['MemAvailable'],'swap_total':total,'swap_free':free,'swap_used':total-free,
           'gpu_used':vram if devices else None,'gtt_used':gtt,
           'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    try:value['paging']=read_paging()
    except Exception as exc:value['paging']={'status':'UNAVAILABLE','error_class':type(exc).__name__}
    return value


def self_diagnostics():
    result={'scope':'native hasher process; inherited cgroup is not assumed exclusive'}
    try:
        status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in Path('/proc/self/status').read_text().splitlines() if ':' in line}
        result.update(rss_bytes=int(status['VmRSS'].split()[0])*1024,swap_bytes=int(status['VmSwap'].split()[0])*1024)
        result['io']={k:int(v) for k,v in (line.split(':',1) for line in Path('/proc/self/io').read_text().splitlines())}
        ru=resource.getrusage(resource.RUSAGE_SELF);result.update(cpu_user_seconds=ru.ru_utime,cpu_system_seconds=ru.ru_stime,minor_faults=ru.ru_minflt,major_faults=ru.ru_majflt)
        result['inherited_cgroup']=Path('/proc/self/cgroup').read_text()[:4096]
    except Exception as exc:result.update(status='UNAVAILABLE',error_class=type(exc).__name__)
    return result


class TotalSwapMonitor:
    def __init__(self,read=read_global,clock=time.monotonic,cpu_clock=time.thread_time):
        self.sampler=SampledProbe(read,clock=clock,cpu_clock=cpu_clock);self.limits=None;self.lock=threading.Lock();self.first_failure=None
    def record_failure(self,exc,observed,stage):
        with self.lock:
            if self.first_failure is None:
                cause=getattr(exc,'__cause__',None)
                self.first_failure={'reason':type(exc).__name__+':'+str(exc),'observed':copy.deepcopy(observed),
                    'stage':stage,'error_class':type(exc).__name__,'cause_class':type(cause).__name__ if cause else None,
                    'evidence':getattr(exc,'resource_evidence',None)}
    def raw(self,force=False):
        try:frame=self.sampler.sample(force=force)
        except Exception as exc:self.record_failure(exc,None,'PHYSICAL_READ');raise
        value=frame['observed'];value['_sample_id']=frame['sample_id'];value['_sample_monotonic']=frame['monotonic']
        try:
            with self.lock:
                if self.limits is None:self.limits=TotalSwapLimits(value)
        except Exception as exc:self.record_failure(exc,value,'BASELINE_VALIDATION');raise
        return value
    def check_observed(self,value,start=False):
        try:
            with self.lock:self.limits.check(value,start=start)
            return value
        except Exception as exc:self.record_failure(exc,value,'ADMISSION');raise
    def admit(self,start=False,force=False):
        return self.check_observed(self.raw(force=force),start=start)
    def policy(self):
        with self.lock:return self.limits.policy() if self.limits else {'status':'BASELINE_NOT_ESTABLISHED','limit_basis':'HOST_TOTAL_USED_ABSOLUTE_BYTES'}
    def diagnostics(self):
        with self.lock:
            result={'policy':self.limits.policy() if self.limits else None,'sampled_peak_total_used_bytes':self.limits.peak_used if self.limits else None,'first_failure':copy.deepcopy(self.first_failure)}
        return {**result,'sampler':self.sampler.stats()}
    def attach_coordinator(self,coordinator):
        # Only this one local Coordinator Runtime instance; shared services/classes unchanged.
        def threshold(preflight=False):
            v=self.admit(start=preflight,force=preflight)
            return {'available_bytes':v['mem_available'],'gpu_used_bytes':v['gpu_used'],'swap_used_bytes':v['swap_used'],
                    'swap_total_bytes':v['swap_total'],'swap_free_bytes':v['swap_free']}
        coordinator.rt._threshold=threshold

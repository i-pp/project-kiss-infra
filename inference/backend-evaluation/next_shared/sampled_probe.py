"""Offline candidate: coalesced5Hz I/O, explicit forced phase reads, sticky failures."""
import copy,threading,time

class ProbeFailure(RuntimeError):pass

class SampledProbe:
    def __init__(self,read,clock=time.monotonic,cpu_clock=time.thread_time,interval=.2,max_read_seconds=1):
        self.read=read;self.clock=clock;self.cpu_clock=cpu_clock;self.interval=interval;self.max_read_seconds=max_read_seconds
        self.lock=threading.Lock();self.last=None;self.error=None;self.requests=0;self.reads=0;self.wall=0;self.cpu=0;self.cache_hits=0;self.failed_requests=0
    def sample(self,force=False):
        with self.lock:
            self.requests+=1
            if self.error is not None:self.failed_requests+=1;raise self.error
            now=self.clock()
            if self.last is not None and now<self.last['monotonic']:
                self.error=ProbeFailure('MONOTONIC_CLOCK_RESET');raise self.error
            if not force and self.last is not None and now-self.last['monotonic']<self.interval:
                self.cache_hits+=1
                return copy.deepcopy(self.last)
            started=now;cpu=self.cpu_clock();self.reads+=1
            try:
                value=self.read();done=self.clock()
                if not isinstance(value,dict) or done<started or done-started>self.max_read_seconds:raise ProbeFailure('PROBE_MISSING_OR_STALE')
            except Exception as exc:
                self.failed_requests+=1;self.error=ProbeFailure(type(exc).__name__+':PROBE_FAILED_NO_RETRY');raise self.error from exc
            finally:self.wall+=max(0,self.clock()-started);self.cpu+=max(0,self.cpu_clock()-cpu)
            self.last={'sample_id':self.reads,'monotonic':done,'observed':copy.deepcopy(value)}
            return copy.deepcopy(self.last)
    def stats(self):
        with self.lock:return {'logical_requests':self.requests,'physical_reads':self.reads,
            'cached_requests':self.cache_hits,'failed_requests':self.failed_requests,'probe_wall_seconds':self.wall,'probe_thread_cpu_seconds':self.cpu,
            'period_seconds':self.interval,'forced_reads_are_phase_boundaries_only':True}

"""One SGLang-only trial adapter; shared historical runner and other guards unchanged."""
import copy
import host_api_trial as h
from paging_telemetry import PagingTelemetry
from total_swap_limits import AUTHORIZATION
from total_swap_monitor import self_diagnostics

class TotalSwapTrial(h.Trial):
    OPERATOR_SHA=h.SEQUENTIAL_OPERATOR_SHA
    TRIAL_AUTHORIZATION=AUTHORIZATION
    def __init__(self,record,backend,coordinator,driver,http,probe,run,write,policy,*,monitor,**kwargs):
        if backend!='sglang' or kwargs.get('operator_sha256')!=self.OPERATOR_SHA:
            raise h.Blocked('TOTAL_SWAP_SCOPE_FIXED_UNUSED_SGLANG_ONLY')
        self.monitor=monitor;self.original_write=write;self.logical_checks=0;self.last_sample_id=None;self.seen_sample_ids=set();self.releasing=False
        super().__init__(record,backend,coordinator,driver,http,monitor.raw,run,self.scoped_write,policy,**kwargs)
        self.paging=PagingTelemetry(read=lambda:self.monitor.raw()['paging'])
    def scoped_write(self,path,payload):
        if path.name=='resource-policy.json':
            payload.pop('swap_growth_limit_bytes',None)
            payload.update(approval=self.TRIAL_AUTHORIZATION,continuation_authorization=self.TRIAL_AUTHORIZATION,
                operator_scope_sha256=self.OPERATOR_SHA,swap_authorization=AUTHORIZATION,
                host_swap_total_policy=self.monitor.policy(),growth_stop_rule_enabled=False,
                probe_period_seconds=.2,psi_numeric_stops='UNAPPROVED_NOT_ENABLED')
        if path.name=='summary.json':
            after=payload.get('resources_after')
            if isinstance(after,dict) and 'swap_total' in after:
                try:self.monitor.check_observed(after)
                except Exception as exc:
                    payload['final_resource_validation']='FAILED:'+type(exc).__name__+':'+str(exc)
                    if payload.get('status')!='UNKNOWN':
                        payload['status']='FAILED';payload.setdefault('reason','FINAL_RESOURCE_LIMIT:'+str(exc))
            payload.pop('swap_growth_policy',None)
            payload.update(host_swap_total_policy=self.monitor.diagnostics(),
                logical_resource_checks=self.logical_checks,resource_sample_basis='unique physical sample IDs observed by trial',
                native_process_diagnostics=self_diagnostics(),audit_directory=str(self.run),
                original_gpu_operator_sha256=self.OPERATOR_SHA,swap_authorization=AUTHORIZATION,trial_authorization=self.TRIAL_AUTHORIZATION)
            if not self.create_intent and not self.c.mutated:payload.setdefault('cleanup_confirmed',True)
        self.original_write(path,payload)
    def safety(self,start=False,force=False):
        if self.loading_pressure:raise h.Blocked('STARTUP_RESOURCE_MONITOR_ABORT')
        failure=None;new_failure=False
        with self.resource_lock:
            self.logical_checks+=1
            if self.resource_failure is not None:failure=self.resource_failure
        observed=None
        if failure is None:
            try:observed=self.monitor.admit(start=start,force=force)
            except Exception as exc:
                failure={'reason':type(exc).__name__+':'+str(exc),'approval':AUTHORIZATION,
                    'limit_basis':'HOST_TOTAL_USED_ABSOLUTE_BYTES','details':getattr(exc,'resource_evidence',None),
                    'observed':copy.deepcopy((self.monitor.diagnostics().get('first_failure') or {}).get('observed'))}
                with self.resource_lock:
                    if self.resource_failure is None:self.resource_failure=failure;new_failure=True
                    else:failure=self.resource_failure
            if observed is not None:
                sample_id=observed['_sample_id']
                with self.resource_lock:
                    if sample_id not in self.seen_sample_ids:
                        self.seen_sample_ids.add(sample_id);self.last_sample_id=sample_id;self.resource_samples+=1
                        for name in ['mem_available','gpu_used','swap_used']:
                            old=self.resource_extrema.get(name,observed[name])
                            self.resource_extrema[name]=min(old,observed[name]) if name=='mem_available' else max(old,observed[name])
                    self.paging.sample(self.clock())
        if failure is not None:
            if new_failure:self.log('resource_threshold_exceeded',**failure)
            error=h.Blocked('RESOURCE_THRESHOLD_EXCEEDED:'+failure['reason']);error.resource_evidence=failure;raise error
        return observed
    def log(self,event,**values):
        if event in {'create_owned_intent','start_owned_intent'}:self.safety(start=True,force=True)
        if event=='unload30b_intent':self.safety(start=True)
        super().log(event,**values)
    def observed(self,allow_new=False):
        row=super().observed(allow_new=allow_new)
        if self.releasing:return row  # identity checks remain; pressure never blocks release
        state=row.get('State',{})
        if type(state.get('OOMKilled')) is not bool:raise h.Blocked('OWNED_OOM_STATE_MONITOR_UNAVAILABLE')
        if state['OOMKilled']:raise h.Blocked('OWNED_CONTAINER_OOM_KILLED')
        if self.owned_memory and getattr(self.owned_memory,'rows',None):
            value=self.owned_memory.rows[-1].get('value',{});events=value.get('cgroup',{}).get('memory.events',{})
            if any(type(events.get(k)) is int and events[k]>0 for k in ['oom','oom_kill']):
                raise h.Blocked('OWNED_CGROUP_OOM_EVENT')
        return row
    def cleanup(self):
        self.releasing=True
        try:return super().cleanup()
        finally:self.releasing=False
    def generate_once(self):
        self.safety(force=True)
        return super().generate_once()

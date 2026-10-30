"""Approved bounded policy for one fixed SGLang operator only.

Replace zero host-swap growth only for the existing unused SG trial. This is
an engineering guard, not a calibrated OOM guarantee. Other limits unchanged.
"""
GIB=1<<30
MAX_GROWTH=128<<20


class BudgetBlocked(RuntimeError):pass


class SGLangBudget:
    def __init__(self,baseline):
        self._check_types(baseline)
        self._baseline=dict(baseline);self.peak_growth=0;self._failure=None
        self.observe(baseline,start=True)
    @property
    def baseline(self):return dict(self._baseline)
    @staticmethod
    def _check_types(value):
        if (not isinstance(value,dict) or any(type(value.get(k)) is not int or value[k]<0
                for k in ('mem_available','gpu_used','swap_used'))):
            raise BudgetBlocked('RESOURCE_PROBE_UNAVAILABLE_OR_INVALID')
    def observe(self,value,*,start=False):
        if self._failure is not None:raise self._failure
        try:self._check_types(value)
        except BudgetBlocked as exc:
            self._failure=exc;raise
        growth=max(0,value['swap_used']-self._baseline['swap_used'])
        self.peak_growth=max(self.peak_growth,growth)
        evidence={'observed':dict(value),'baseline':self.baseline,'swap_growth_bytes':growth,
            'peak_swap_growth_bytes':self.peak_growth,'swap_growth_limit_bytes':MAX_GROWTH,
            'start_ram_min_bytes':24*GIB,'continue_ram_exclusive_min_bytes':16*GIB,'gpu_max_bytes':58*GIB}
        reason=(('START_RAM_BELOW24GIB' if value['mem_available']<24*GIB else None) if start
            else ('CONTINUE_RAM_AT_OR_BELOW16GIB' if value['mem_available']<=16*GIB else None))
        if value['gpu_used']>58*GIB:reason='GPU_ABOVE58GIB'
        if growth>MAX_GROWTH:reason='HOST_SWAP_GROWTH_ABOVE128MIB'
        if reason:
            exc=BudgetBlocked(reason);exc.resource_evidence=evidence;self._failure=exc;raise exc
        return evidence

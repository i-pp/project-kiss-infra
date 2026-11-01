"""User-authorized HOST TOTAL swap used cap for the coordinated zero-generation warm-cache measurement.
Decimal32GB, notgrowth; no OS/capacity changes; PSIproposal rules remain disabled.
"""
import copy
GIB=1<<30
USER_TOTAL_LIMIT=32_000_000_000
AUTHORIZATION='Sentinel_4165178add388191b0368fe6e0e412d2'

class LimitBlocked(RuntimeError):pass


def validate(value):
    if (not isinstance(value,dict) or any(type(value.get(k)) is not int or value[k]<0
        for k in ['mem_available','gpu_used','swap_total','swap_free','swap_used'])):
        raise LimitBlocked('CORE_RESOURCE_PROBE_UNAVAILABLE_OR_INVALID')
    if (value['swap_free']>value['swap_total'] or value['swap_used']!=value['swap_total']-value['swap_free']):
        raise LimitBlocked('INCOHERENT_SAME_READ_SWAP_VALUES')
    if not isinstance(value.get('boot_id'),str) or not value['boot_id']:raise LimitBlocked('BOOT_ID_UNAVAILABLE')

class TotalSwapLimits:
    def __init__(self,baseline):
        validate(baseline);self._baseline=copy.deepcopy(baseline);self.peak_used=baseline['swap_used']
        self.cap=min(USER_TOTAL_LIMIT,baseline['swap_total'])
    @property
    def baseline(self):return copy.deepcopy(self._baseline)
    def check(self,value,start=False):
        validate(value)
        if value['boot_id']!=self._baseline['boot_id']:raise LimitBlocked('HOST_BOOT_CHANGED')
        if value['swap_total']!=self._baseline['swap_total']:raise LimitBlocked('HOST_SWAP_CAPACITY_CHANGED')
        self.peak_used=max(self.peak_used,value['swap_used'])
        evidence={'limit_basis':'HOST_TOTAL_USED_ABSOLUTE_BYTES','authorization':AUTHORIZATION,
            'user_total_limit_bytes':USER_TOTAL_LIMIT,'actual_swap_total_bytes':self._baseline['swap_total'],
            'effective_total_used_limit_bytes':self.cap,'observed':copy.deepcopy(value),'baseline':self.baseline,
            'growth_is_diagnostic_only_bytes':max(0,value['swap_used']-self._baseline['swap_used'])}
        reason=None
        if value['swap_total']==0:reason='NO_CONFIGURED_SWAP_CAPACITY_NO_AUTOCREATION'
        elif value['swap_free']==0:reason='HOST_SWAP_EXHAUSTED'
        elif value['swap_used']>self.cap:reason='HOST_TOTAL_SWAP_ABOVE_AUTHORIZED_CAP'
        if value['gpu_used']>58*GIB:reason='GPU_ABOVE58GIB'
        if start and value['mem_available']<24*GIB:reason='START_RAM_BELOW24GIB'
        if not start and value['mem_available']<=16*GIB:reason='CONTINUE_RAM_AT_OR_BELOW16GIB'
        if reason:
            exc=LimitBlocked(reason);exc.resource_evidence=evidence;raise exc
        return evidence
    def policy(self):
        return {'authorization':AUTHORIZATION,'limit_basis':'HOST_TOTAL_USED_ABSOLUTE_BYTES',
            'user_total_used_limit_bytes':USER_TOTAL_LIMIT,'actual_swap_total_bytes':self._baseline['swap_total'],
            'effective_total_used_limit_bytes':self.cap,'baseline_fixed_for_audit_only':self.baseline,
            'growth_stop_rule_enabled':False,'baseline_reset_after_assets':False,'capacity_or_boot_change_stops':True,
            'zero_swap_free_stops':True,'required_monitors':['RAM','GPU','same-read SwapTotal/Free/Used','boot and capacity','owned identity/configured limits/Docker OOMKilled'],
            'cgroup_details_optional_positive_oom_stops':True,'psi_numeric_stop_rules':'NOT_AUTHORIZED_DIAGNOSTICS_ONLY',
            'start_ram_min_bytes':24*GIB,'continue_ram_exclusive_min_bytes':16*GIB,'gpu_max_bytes':58*GIB}

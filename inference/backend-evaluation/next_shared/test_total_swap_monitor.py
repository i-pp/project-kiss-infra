import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from total_swap_monitor import TotalSwapMonitor,read_global
from total_swap_limits import LimitBlocked
from test_total_swap_limits import value

class MonitorTests(unittest.TestCase):
    def test_shared_probe_caps_physical_reads_under_many_threads_requests(self):
        now=[0];m=TotalSwapMonitor(read=lambda:value(),clock=lambda:now[0],cpu_clock=lambda:0)
        for i in range(88000):now[0]=i/1000;m.admit(start=True)
        self.assertLessEqual(m.sampler.stats()['physical_reads'],441)
        self.assertGreater(m.sampler.stats()['cached_requests'],87000)
    def test_same_meminfo_read_derives_total_free_used(self):
        count=[]
        def read(path,*args,**kw):
            if str(path)=='/proc/meminfo':count.append(1);return 'MemAvailable: 50331648 kB\nSwapTotal: 67108864 kB\nSwapFree: 66060288 kB\n'
            if str(path).endswith('boot_id'):return 'fixture-boot'
            if str(path).endswith('mem_info_vram_used'):return '22'
            if str(path).endswith('mem_info_gtt_used'):return '2'
            raise AssertionError('foreign read:'+str(path))
        with patch.object(Path,'read_text',read),patch.object(Path,'resolve',lambda p:p),patch.object(Path,'exists',return_value=True),patch('total_swap_monitor.glob.glob',return_value=['/sys/class/drm/card0/device/mem_info_vram_used']),patch('total_swap_monitor.read_paging',return_value={}):v=read_global()
        self.assertEqual(len(count),1);self.assertEqual(v['swap_total'],64*(1<<30));self.assertEqual(v['swap_used'],1<<30)
    def test_instance_scoped_recovery_rechecks_current_total_not_sticky_trial_abort(self):
        current=[value()];m=TotalSwapMonitor(read=lambda:current[0]);a=SimpleNamespace(rt=SimpleNamespace());b=SimpleNamespace(rt=SimpleNamespace(_threshold=lambda:None))
        m.attach_coordinator(a);a.rt._threshold(preflight=True)
        current[0]=value(8_000_000_001)
        with self.assertRaises(LimitBlocked):a.rt._threshold(preflight=True)
        current[0]=value(1_000_000_000);self.assertEqual(a.rt._threshold(preflight=True)['swap_used_bytes'],1_000_000_000)
        self.assertIsNone(b.rt._threshold());self.assertIsNotNone(m.first_failure)
    def test_first_bad_value_and_failed_read_are_saved_without_stale_substitution(self):
        now=[0];raw=[value()];m=TotalSwapMonitor(read=lambda:raw[0],clock=lambda:now[0],cpu_clock=lambda:0);m.admit()
        raw[0]={**value(),'gpu_used':None};now[0]=.3
        with self.assertRaises(LimitBlocked):m.admit()
        self.assertIsNone(m.first_failure['observed']['gpu_used']);self.assertEqual(m.first_failure['stage'],'ADMISSION')
        calls=[]
        def denied():calls.append(1);raise PermissionError('fixture')
        m=TotalSwapMonitor(read=denied)
        for _ in range(2):
            with self.assertRaises(Exception):m.admit(force=True)
        self.assertIsNone(m.first_failure['observed']);self.assertEqual(m.first_failure['cause_class'],'PermissionError');self.assertEqual(len(calls),1)
    def test_unapproved_psi_thresholds_are_not_enabled(self):
        v=value();v['paging']={'memory_psi':{'full':{'avg10':90,'total':999}}}
        m=TotalSwapMonitor(read=lambda:v);m.admit();self.assertEqual(m.policy()['psi_numeric_stop_rules'],'NOT_AUTHORIZED_DIAGNOSTICS_ONLY')

if __name__=='__main__':unittest.main()

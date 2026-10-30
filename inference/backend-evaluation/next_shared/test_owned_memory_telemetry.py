import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import owned_memory_telemetry as t

CID='a'*64

class OwnedMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.proc=self.root/'proc';self.group=self.root/'cgroup';p=self.proc/'42';p.mkdir(parents=True)
        (p/'stat').write_text('42 (fixture process) '+' '.join(['S']+['0']*18+['12345']+['0']*20))
        (p/'cgroup').write_text('0::/system.slice/docker-'+CID+'.scope\n')
        d=self.group/'system.slice'/('docker-'+CID+'.scope');d.mkdir(parents=True);self.cg=d
        for name,value in {'memory.current':'100','memory.peak':'200','memory.max':str(32<<30),
            'memory.swap.current':'0','memory.swap.max':'0','memory.events':'oom 0\noom_kill 0\n',
            'memory.stat':'anon 12\nfile 45\nshmem 8\nignored 900\n','memory.pressure':'some avg10=0.00 total=0\n'}.items():(d/name).write_text(value)
        self.v=lambda _:SimpleNamespace(f_blocks=131072,f_frsize=4096,f_bfree=130000,f_bavail=130000)
    def read(self,**kwargs):return t.snapshot(CID,42,self.proc,self.group,kwargs.pop('statvfs',self.v),**kwargs)
    def test_known_owned_pid_cgroup_and_exact_cache_are_reported_separately(self):
        r=self.read();self.assertEqual(r['cgroup']['memory.current'],100);self.assertEqual(r['jit_cache']['total_bytes'],512<<20)
        self.assertEqual(r['cgroup']['memory.stat'],{'anon':12,'file':45,'shmem':8});self.assertFalse(r['admission_gate'])
    def test_foreign_cgroup_or_invalid_cid_cannot_probe_cache(self):
        (self.proc/'42/cgroup').write_text('0::/system.slice/docker-'+'b'*64+'.scope\n')
        with patch.object(t.os,'statvfs',side_effect=AssertionError('no foreign access')):
            with self.assertRaises(ValueError):self.read()
        with self.assertRaises(ValueError):t.snapshot('../x',42,self.proc,self.group,self.v)
    def test_missing_cgroup_data_is_not_zero_and_does_not_change_gate(self):
        (self.cg/'memory.peak').unlink();r=self.read();self.assertEqual(r['cgroup']['status'],'UNAVAILABLE');self.assertNotIn('memory.peak',r['cgroup'])
        self.assertEqual(r['jit_cache']['status'],'OBSERVED')
    def test_cache_permission_denial_has_no_privilege_or_other_path_fallback(self):
        r=self.read(statvfs=lambda _:(_ for _ in ()).throw(PermissionError()))
        self.assertEqual(r['jit_cache'],{'status':'UNAVAILABLE','error_class':'PermissionError'})
    def test_wrong_cache_size_rejected_as_measurement(self):
        r=self.read(statvfs=lambda _:SimpleNamespace(f_blocks=1,f_frsize=4096))
        self.assertEqual(r['jit_cache']['status'],'UNAVAILABLE')
    def test_pid_generation_change_drops_entire_sample(self):
        with patch.object(t,'process_start',side_effect=['old','new']),self.assertRaisesRegex(ValueError,'IDENTITY_CHANGED'):self.read()
    def test_symlink_cgroup_cannot_escape_fixed_tree(self):
        alt=self.root/'other';self.cg.rename(alt);self.cg.symlink_to(alt,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):self.read()
    def test_bounded_sample_rate_highwater_and_unavailable_semantics(self):
        m=t.OwnedMemoryTelemetry(probe=lambda c,p:{'cgroup':{'memory.current':10},'jit_cache':{'used_bytes':20}})
        for i in range(50):m.observe(CID,42,i);m.observe(CID,42,i+.5)
        r=m.snapshot();self.assertEqual(r['sample_count'],50);self.assertEqual(len(r['samples']),32)
        self.assertEqual(r['sampled_high_water']['jit_cache.used_bytes'],20)
        bad=t.OwnedMemoryTelemetry(probe=lambda c,p:(_ for _ in ()).throw(PermissionError()));bad.observe(CID,42,0)
        self.assertEqual(bad.snapshot()['samples'][0]['value']['status'],'UNAVAILABLE')

if __name__=='__main__':unittest.main()

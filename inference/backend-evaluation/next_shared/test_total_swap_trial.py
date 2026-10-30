import io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout
import host_api_trial as h
import test_host_api_trial as f
from total_swap_monitor import TotalSwapMonitor
from total_swap_trial import TotalSwapTrial
from total_swap_limits import AUTHORIZATION
from test_total_swap_limits import value

class Memory:
    def __init__(self):self.rows=[]
    def observe(self,*a):pass
    def snapshot(self):return {'sample_count':0,'samples':[],'diagnostic_only':True}

class Driver(f.Driver):
    def create(self,ident,r,backend):
        cid=super().create(ident,r,backend);argv=h.server_argv(backend,r)
        self.row['Config'].update(Entrypoint=[argv[0]],Cmd=argv[1:],Env=[k+'='+v for k,v in h.server_environment(backend,r).items()])
        self.row['State']['OOMKilled']=False;return cid
    def start(self,cid):
        super().start(cid);self.row['State']['OOMKilled']=self.mode=='oom'

class TotalTrialTests(unittest.TestCase):
    def execute(self,used=500_000_000,mode=None,verify=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);r=f.record(root)
        r['review'].update(aiter_cache_profile=h.AITER_PROFILE,sglang_sequential_loader_profile='one-thread-v1');c=f.Coordinator();d=Driver();d.mode=mode;http=f.HTTP();clock=f.Clock();run=root/'run';run.mkdir()
        mon=TotalSwapMonitor(read=lambda:value(used),clock=clock.now,cpu_clock=lambda:0);reserved=[]
        with patch.object(h,'OwnedMemoryTelemetry',Memory),patch('total_swap_trial.self_diagnostics',return_value={'scope':'fixture'}):
            t=TotalSwapTrial(r,'sglang',c,d,http,mon.raw,run,f.write,
                lambda _:{'system':'COMMON POLICY FIXTURE','metadata':{'sha256':'fixture'}},monitor=mon,
                verify=verify or (lambda _,**kw:[]),unchanged=lambda _:True,clock=clock.now,sleep=clock.sleep,
                network_profile={'name':h.NETWORK,'id':'c'*64},reserve_attempt=lambda:reserved.append(1),operator_sha256=h.SEQUENTIAL_OPERATOR_SHA)
            with redirect_stdout(io.StringIO()):out=t.execute()
        return t,out,c,d,http,run,reserved
    def test_total_allowance_over_old_growth_one_post_cleanup_and_truthful_audit(self):
        t,out,c,d,http,run,reserved=self.execute(used=2_000_000_000)
        self.assertEqual(out['status'],'COMPLETED',out);self.assertEqual(http.posts,1);self.assertEqual(reserved,[1]);self.assertIsNone(d.row)
        self.assertEqual(c.events.count('restore'),1);self.assertNotIn('swap_growth_policy',out)
        p=json.loads((run/'resource-policy.json').read_text());self.assertNotIn('swap_growth_limit_bytes',p)
        self.assertEqual(p['approval'],AUTHORIZATION);self.assertEqual(p['host_swap_total_policy']['effective_total_used_limit_bytes'],8_000_000_000)
        self.assertEqual(out['host_swap_total_policy']['policy']['limit_basis'],'HOST_TOTAL_USED_ABSOLUTE_BYTES')
        self.assertEqual(out['host_swap_total_policy']['policy']['psi_numeric_stop_rules'],'NOT_AUTHORIZED_DIAGNOSTICS_ONLY')
    def test_initial_total_over8gb_never_reads_assets_or_reserves_or_unloads(self):
        def forbidden(*a,**k):raise AssertionError('no asset read')
        t,out,c,d,http,run,reserved=self.execute(used=8_000_000_001,verify=forbidden)
        self.assertEqual(out['environment'],'NOT_RUN');self.assertNotIn('unload',c.events);self.assertEqual(reserved,[]);self.assertEqual(http.posts,0)
        self.assertEqual(out['host_swap_total_policy']['first_failure']['reason'].split(':')[0],'LimitBlocked')
    def test_owned_oom_is_real_pressure_and_blocks_generation(self):
        t,out,c,d,http,run,reserved=self.execute(mode='oom');self.assertEqual(out['generation_requests'],0)
        self.assertIn('OOM',out['reason']);self.assertTrue(out['cleanup_confirmed']);self.assertIsNone(d.row)
    def test_restore_does_not_override_user_total_cap_to_report_success(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);r=f.record(root)
        r['review'].update(aiter_cache_profile=h.AITER_PROFILE,sglang_sequential_loader_profile='one-thread-v1')
        current=[value()];clock=f.Clock();mon=TotalSwapMonitor(read=lambda:current[0],clock=clock.now,cpu_clock=lambda:0)
        class C(f.Coordinator):
            def restore(self):mon.admit(start=True,force=True);return super().restore()
        class D(Driver):
            def remove(self,cid,timeout=5):super().remove(cid,timeout);current[0]=value(8_000_000_001)
        c=C();d=D();http=f.HTTP();run=root/'run';run.mkdir()
        with patch.object(h,'OwnedMemoryTelemetry',Memory),patch('total_swap_trial.self_diagnostics',return_value={}):
            trial=TotalSwapTrial(r,'sglang',c,d,http,mon.raw,run,f.write,lambda _:{'system':'COMMON POLICY FIXTURE','metadata':{'sha256':'fixture'}},monitor=mon,verify=lambda _,**kw:[],unchanged=lambda _:True,clock=clock.now,sleep=clock.sleep,network_profile={'name':h.NETWORK,'id':'c'*64},operator_sha256=h.SEQUENTIAL_OPERATOR_SHA)
            with redirect_stdout(io.StringIO()):out=trial.execute()
        self.assertEqual(out['status'],'UNKNOWN');self.assertEqual(out['restoration'],'UNKNOWN')
        self.assertTrue(out['cleanup_confirmed']);self.assertIsNone(d.row);self.assertNotIn('restore',c.events)
        self.assertEqual(out['host_swap_total_policy']['first_failure']['observed']['swap_used'],8_000_000_001)
    def test_other_backend_or_operator_cannot_use_adapter(self):
        with self.assertRaisesRegex(h.Blocked,'SCOPE'):TotalSwapTrial({},'vllm',None,None,None,None,None,None,None,monitor=None,operator_sha256=h.SEQUENTIAL_OPERATOR_SHA)

if __name__=='__main__':unittest.main()

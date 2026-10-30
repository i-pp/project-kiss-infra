"""CPU fake tests only; no Strata/source/engine/socket/GPU actions."""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import retry02_strata_host as r
sys.path.append(str(Path(__file__).resolve().parent.parent/'host-trial-prep'))
from test_host_trial import FakeRunner, FakeCoordinator, healthy


class Retry02Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.rt=self.repo/'agents/local_llm/.runtime';self.rt.mkdir(parents=True)
        self.prior=self.rt/'backend-trials'/r.PRIOR_RUN;self.prior.mkdir(parents=True)
        self.pilot=self.prior/'pilot';self.pilot.mkdir()
        for name in r.PILOT_NAMES:(self.pilot/name).write_bytes(('old '+name).encode())
        self.oldfull=self.prior/'full';self.oldfull.mkdir();(self.oldfull/'partial.bin').write_bytes(b'KEEP OLD FULL')
        self.receipt=self.prior/'pilot_verify.json';self.receipt.write_text('{}');self.receipt.chmod(0o600)
        self.identity={'schema':1,'prior_run':r.PRIOR_RUN,'prior_summary_sha256':r.PRIOR_SHA,
            'pilot_relative':'pilot','full_reusable':False,'pilot_verify_sha256':self.sha(self.receipt),
            'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':self.sha(p)} for p in sorted(self.pilot.iterdir())]}
        self.software=self.repo/'.cache/backend-evaluation/strata-v027-e0152';self.software.mkdir(parents=True)
        (self.software/'fixed-software').write_bytes(b'KEEP SOFTWARE')
        self.source=self.root/'source';self.source.mkdir()
        shards=[self.root/'a.gguf',self.root/'b.gguf']
        for p in shards:p.write_bytes(b'KEEP MODEL')
        self.v={'source':self.source,'llama':self.root,'exe':self.root/'NOT_EXECUTED','shards':shards}
        self.c=FakeCoordinator();self.c.guard=lambda:None
        self.approval=json.loads((Path(__file__).parent/'approval-PENDING.json').read_text())
        self.approval.update(approved=True,approval_reference='Sentinel_fixture_NEW_RETRY02',owner_approval_verified_at_utc='fixture')
        old=r.h.RUN_STARTED;r.h.RUN_STARTED=False;self.addCleanup(setattr,r.h,'RUN_STARTED',old)
    @staticmethod
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def prior_data(self):
        return {'status':'FAILED','environment':'NOT_RUN','quality':'UNASSESSED','generation_requests':0,
            'completed_generations':0,'automatic_retry':False,'code_executed':False,'source_metadata_unchanged':True,
            'reason':'Blocked:full_build:INTERRUPTED','restoration':{'status':'RESTORED',
                'model_states':{'kiss-b3-gpt-oss-120b':'unloaded','kiss-b3-qwen-coder-next':'unloaded',r.h.MODEL:'loaded'}}}
    def execute(self,runner=FakeRunner):
        fake=SimpleNamespace(policy_context=lambda _: {'system':'fixture','metadata':{'version':'fixture'}})
        with patch.dict(sys.modules,{'local_llm':fake}),patch('shutil.disk_usage',return_value=SimpleNamespace(free=150*r.GIB)),patch.object(r.h,'validate_pack',return_value={}),redirect_stdout(io.StringIO()):
            trial=r.ReplayTrial(self.repo,self.v,self.c,self.identity,runner_factory=runner,probe=healthy,run_root=self.root/'new-runs')
            result=trial.execute()
        return trial,result
    def test_prior_unknown_or_unrestored_or_generated_refused(self):
        self.assertEqual(r.validate_prior(self.prior_data())['generation_requests'],0)
        for key,value in [('status','UNKNOWN'),('generation_requests',1),('generation_requests',False),('source_metadata_unchanged',False),('reason','other')]:
            data=self.prior_data();data[key]=value
            with self.assertRaises(r.h.Blocked):r.validate_prior(data)
        for restoration in ['UNKNOWN',{'status':'UNKNOWN'},{'status':'RESTORED','model_states':{}}]:
            data=self.prior_data();data['restoration']=restoration
            with self.assertRaises(r.h.Blocked):r.validate_prior(data)
    def test_new_approval_exact_scope_limits_and_identity_required(self):
        r.validate_approval(self.approval)
        for key,value in [('approved',False),('pilot_identity_sha256','0'*64),('scope','RETRY01'),('attempt_limit',2),('generation_limit',True),('whole_seconds',2401),('cumulative_data_limit_bytes',121*r.GIB),('minimum_free_bytes',1),('approval_reference',next(iter(r.CONSUMED_REFS)))]:
            data=dict(self.approval);data[key]=value
            with self.assertRaises(r.h.Blocked):r.validate_approval(data)
    def test_inventory_tamper_extra_and_symlink_fail_closed(self):
        r.verify_inventory(self.pilot,self.identity['files'])
        p=self.pilot/'dense.bin';p.write_bytes(b'X'*p.stat().st_size)
        with self.assertRaisesRegex(r.h.Blocked,'HASH'):r.verify_inventory(self.pilot,self.identity['files'])
        p.unlink();p.symlink_to(self.software/'fixed-software')
        with self.assertRaisesRegex(r.h.Blocked,'SYMLINK'):r.verify_inventory(self.pilot,self.identity['files'])
        p.unlink();p.write_bytes(b'old dense.bin');(self.pilot/'extra').write_bytes(b'x')
        with self.assertRaisesRegex(r.h.Blocked,'INVENTORY'):r.verify_inventory(self.pilot,self.identity['files'])
    def test_tamper_before_replay_never_unloads_or_generates(self):
        (self.pilot/'dense.bin').write_bytes(b'bad')
        trial,result=self.execute()
        self.assertEqual(result['status'],'FAILED');self.assertFalse(self.c.mutated)
        self.assertEqual(result['generation_requests'],0)
        self.assertFalse(any('build' in a for a in trial.runner.calls))
    def test_reuse_verifies_before_unload_builds_only_new_full_old_data_unchanged(self):
        old={p.name:p.read_bytes() for p in self.pilot.iterdir()}
        trial,result=self.execute()
        self.assertEqual(result['status'],'COMPLETED',result)
        self.assertEqual(result['generation_requests'],1)
        builds=[a for a in trial.runner.calls if 'build' in a]
        self.assertEqual(len(builds),1);self.assertEqual(builds[0][builds[0].index('--layers')+1],'48')
        self.assertEqual(Path(builds[0][builds[0].index('--out')+1]),trial.run/'full')
        self.assertEqual({p.name:p.read_bytes() for p in self.pilot.iterdir()},old)
        self.assertEqual((self.oldfull/'partial.bin').read_bytes(),b'KEEP OLD FULL')
        stages=[x['stage'] for x in trial.results]
        self.assertEqual(stages[:3],['imports','pilot_verify','full_build'])
        self.assertEqual(self.c.events,['lock','idle','unload','restore','unlock'])
    def test_reused_pilot_semantic_verify_runs_while_resident_loaded(self):
        c=self.c
        class Observing(FakeRunner):
            def run(self,argv,*args,**kwargs):
                if 'verify' in argv and str(self_pilot) in argv:assert not c.mutated
                return super().run(argv,*args,**kwargs)
        self_pilot=self.pilot
        _,result=self.execute(Observing);self.assertEqual(result['status'],'COMPLETED')
    def test_unknown_owned_cleanup_blocks_restore_and_remains_unknown(self):
        class Unsafe(FakeRunner):
            def run(self,argv,*args,**kwargs):
                if 'build' in argv:return {'status':'FAILED','reason':'INTERRUPTED','cleanup':{'complete':False}}
                return super().run(argv,*args,**kwargs)
        _,result=self.execute(Unsafe)
        self.assertEqual(result['status'],'UNKNOWN');self.assertNotIn('restore',self.c.events)
        self.assertEqual(result['restoration'],'BLOCKED_OWNED_PROCESSES_REMAIN')
    def test_unknown_prior_marker_blocks_constructor(self):
        runs=self.root/'runs';runs.mkdir(mode=0o700);(runs/'strata-UNCERTAIN.json').write_text('{}')
        with self.assertRaisesRegex(r.h.Blocked,'UNKNOWN'):
            r.ReplayTrial(self.repo,self.v,self.c,self.identity,runner_factory=FakeRunner,probe=healthy,run_root=runs)
    def test_budget_combines_old_software_new_and_free_floor(self):
        roots=[self.prior,self.software,self.root/'new'];roots[-1].mkdir()
        sizes={roots[0]:40*r.GIB,roots[1]:11*r.GIB,roots[2]:70*r.GIB}
        free=[150*r.GIB]
        budget=r.CumulativeBudget(roots,self.root,usage=lambda _:SimpleNamespace(free=free[0]),measure=lambda p:sizes[p])
        data,reason=budget.sample();self.assertEqual(data['cumulative_data_bytes'],121*r.GIB)
        self.assertEqual(reason,'CUMULATIVE_DATA_LIMIT')
        sizes[roots[2]]=69*r.GIB;self.assertIsNone(budget.sample()[1])
        free[0]=99*r.GIB;self.assertEqual(budget.sample(start=True)[1],'START_FREE_DISK_BELOW100GIB')
        self.assertIsNone(budget.sample()[1]);free[0]=32*r.GIB;self.assertIsNone(budget.sample()[1])
        free[0]-=1;self.assertEqual(budget.sample()[1],'FREE_DISK_BELOW32GIB')
    def test_monitor_preserves_per_run70_limit_and_reports_cumulative_limit(self):
        budget=SimpleNamespace(sample=lambda:({'cumulative_data_bytes':121*r.GIB},'CUMULATIVE_DATA_LIMIT'))
        runner=r.CumulativeRunner(budget=budget,probe=healthy,run_dir=self.root,disk_baseline_bytes=0)
        with patch('owned_process._directory_bytes',return_value=0):
            sample,reason=runner._sample(None,healthy(),0,{})
        self.assertEqual(reason,'CUMULATIVE_DATA_LIMIT');self.assertEqual(sample['cumulative_data_bytes'],121*r.GIB)
        with patch('owned_process._directory_bytes',return_value=71*r.GIB):
            _,reason=runner._sample(None,healthy(),0,{})
        self.assertEqual(reason,'DISK_GROWTH')
    def test_no_flag_is_prepared_and_duplicate_intent_never_starts(self):
        with patch('sys.argv',['retry02']),patch.object(r.assets,'private_record',side_effect=AssertionError('no read')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(r.main(),0)
        self.assertIn('PREPARED',out.getvalue())
        calls=[]
        class Trial:
            def __init__(self,*args):calls.append('trial')
            def execute(self):return {'status':'COMPLETED'}
        r.run_once(self.repo,{},self.c,self.approval,self.identity,Trial)
        with self.assertRaises(FileExistsError):r.run_once(self.repo,{},self.c,self.approval,self.identity,Trial)
        self.assertEqual(calls,['trial'])
    def test_entry_preflight_elapsed_time_blocks_before_unload_or_pilot_verify(self):
        fake=SimpleNamespace(policy_context=lambda _: {'system':'fixture','metadata':{'version':'fixture'}})
        with patch.dict(sys.modules,{'local_llm':fake}),patch('shutil.disk_usage',return_value=SimpleNamespace(free=150*r.GIB)),redirect_stdout(io.StringIO()):
            trial=r.ReplayTrial(self.repo,self.v,self.c,self.identity,runner_factory=FakeRunner,
                probe=healthy,run_root=self.root/'new-runs',started_at=r.time.monotonic()-2236)
            with patch.object(trial,'before_unload',side_effect=AssertionError('must not verify reused pilot')):
                result=trial.execute()
        self.assertEqual(result['status'],'FAILED')
        self.assertIn('WHOLE_TRIAL_DEADLINE',result['reason'])
        self.assertFalse(self.c.mutated);self.assertEqual(trial.runner.calls,[])
        self.assertEqual(result['generation_requests'],0);self.assertGreaterEqual(result['elapsed_seconds'],2236)

    def test_missing_base_hooks_blocks_before_coordinator(self):
        with patch.object(r.h,'PACK_HOOK_VERSION',None):
            with self.assertRaisesRegex(r.h.Blocked,'PACK_HOOKS'):
                r.run_once(self.repo,{},self.c,self.approval,self.identity)
        self.assertEqual(self.c.events,[])


if __name__=='__main__':unittest.main()

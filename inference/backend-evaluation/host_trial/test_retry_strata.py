"""Read-only/fake retry protocol checks; no socket, service, engine or GPU action."""
from contextlib import contextmanager,redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import retry_strata_host as r


class FakeCoordinator:
    def __init__(self):self.events=[];self.busy=False
    def guard(self):self.events.append('guard')
    @contextmanager
    def locked(self):self.events.append('lock');yield;self.events.append('unlock')
    def idle(self):
        self.events.append('idle')
        if self.busy:raise FileNotFoundError('same socket unavailable')


class RetryTests(unittest.TestCase):
    def prior(self):
        return {'status':'FAILED','environment':'NOT_RUN','quality':'UNASSESSED',
            'generation_requests':0,'completed_generations':0,'restoration':'NOT_NEEDED',
            'code_executed':False,'source_metadata_unchanged':True,
            'reason':"FileNotFoundError:[Errno 2] No such file or directory: '/run/user/1000/agent-orchestrator/365d01e41070dcd00b66f652.sock'"}
    def approval(self):
        return {'approved':True,'scope':r.SCOPE,'prior_summary_sha256':r.PRIOR_SHA,
            'attempt_limit':1,'generation_limit':1,'whole_seconds':2400,
            'approval_reference':'Sentinel_fixture_NEW_RETRY_APPROVAL','owner_approval_verified_at_utc':'fixture'}
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name);(self.repo/'agents/local_llm/.runtime').mkdir(parents=True)
        self.c=FakeCoordinator();self.calls=[]
        old=r.h.RUN_STARTED;r.h.RUN_STARTED=False;self.addCleanup(setattr,r.h,'RUN_STARTED',old)
    def trial(self,*args):
        self.calls.append('trial')
        class Trial:
            def execute(self):return {'status':'COMPLETED'}
        return Trial()
    def test_fixed_prior_and_new_approval_are_accepted(self):
        self.assertEqual(r.validate_prior(self.prior())['generation_requests'],0)
        self.assertTrue(r.validate_approval(self.approval())['approved'])
    def test_original_execution_cli_blocks_before_asset_or_coordinator_access(self):
        summary=self.repo/'agents/local_llm/.runtime/backend-trials'/r.PRIOR_RUN/'summary.json'
        summary.parent.mkdir(parents=True);summary.write_text('{}')
        fake_script=self.repo/'inference/backend-evaluation/host_trial/host_strata_trial.py'
        with patch.object(r.h,'__file__',str(fake_script)),patch('sys.argv',['h','--assets','unused','--run-approved']),patch.object(r.assets,'verify',side_effect=AssertionError('must not verify assets')),patch.object(r.h,'Coordinator',side_effect=AssertionError('must not create coordinator')):
            with self.assertRaisesRegex(r.h.Blocked,'SEPARATE_APPROVED_RETRY'):r.h.main()
    def test_read_only_asset_cli_remains_available_after_prior_failure(self):
        summary=self.repo/'agents/local_llm/.runtime/backend-trials'/r.PRIOR_RUN/'summary.json'
        summary.parent.mkdir(parents=True);summary.write_text('{}')
        fake_script=self.repo/'inference/backend-evaluation/host_trial/host_strata_trial.py'
        with patch.object(r.h,'__file__',str(fake_script)),patch('sys.argv',['h','--assets','unused','--check-assets']),patch.object(r.assets,'verify',return_value={'source_checks':[],'dependencies':{}}),patch.object(r.h,'Coordinator',side_effect=AssertionError('must not construct')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(r.h.main(),0)
        self.assertIn('ASSETS_CHECKED_NO_EXECUTION',out.getvalue())
    def test_unknown_or_executed_prior_cannot_be_retried(self):
        for key,value in [('status','UNKNOWN'),('generation_requests',1),('generation_requests',False),('source_metadata_unchanged',False),('environment','FAIL'),('reason','other failure')]:
            data=self.prior();data[key]=value
            with self.assertRaises(r.h.Blocked):r.validate_prior(data)
    def test_original_or_pending_approval_does_not_authorize_retry(self):
        for key,value in [('approved',False),('approval_reference','Sentinel_710bf418f4948191a099de29ea9adcbc'),('prior_summary_sha256','0'*64),('attempt_limit',2),('generation_limit',2),('whole_seconds',2401)]:
            data=self.approval();data[key]=value
            with self.assertRaises(r.h.Blocked):r.validate_approval(data)
    def test_socket_failure_before_intent_has_no_trial(self):
        self.c.busy=True
        with self.assertRaises(FileNotFoundError):r.run_once(self.repo,{},self.c,self.approval(),self.trial)
        self.assertFalse((self.repo/'agents/local_llm/.runtime'/r.INTENT_NAME).exists())
        self.assertEqual(self.calls,[]);self.assertFalse(r.h.RUN_STARTED)
    def test_one_intent_after_guard_idle_and_duplicate_never_starts(self):
        result=r.run_once(self.repo,{},self.c,self.approval(),self.trial)
        self.assertEqual(result['status'],'COMPLETED');self.assertEqual(self.c.events,['guard','lock','idle','unlock'])
        self.assertEqual(self.calls,['trial'])
        marker=self.repo/'agents/local_llm/.runtime'/r.INTENT_NAME
        self.assertEqual(marker.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):r.run_once(self.repo,{},self.c,self.approval(),self.trial)
        self.assertEqual(self.calls,['trial'])
    def test_no_flag_cli_is_prepared_without_record_or_process_access(self):
        with patch.object(r,'__file__','not installed'),patch.object(r.assets,'private_record',side_effect=AssertionError('must not read')),patch.object(r.h,'Coordinator',side_effect=AssertionError('must not construct')),patch('sys.argv',['retry_strata_host.py']),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(r.main(),0)
        self.assertIn('PREPARED_SEPARATE_RETRY_APPROVAL_REQUIRED',out.getvalue())


if __name__=='__main__':unittest.main()

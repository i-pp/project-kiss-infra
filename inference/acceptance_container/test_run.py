"""Offline failure-path tests. Never invoke host Docker/systemd/HTTP."""
import subprocess,time,unittest
from unittest.mock import Mock,patch
from . import run as m


def healthy():return {'status':'ready','fault':None,'active':None,'queue_depth':0,'gpu':{'flash_resident':True,'ollama_selected':'coder-next'}}
class Tests(unittest.TestCase):
    def runobj(self):
        r=m.Run([]);r.event=Mock();return r
    def test_resource_fault_is_immediate_not_retried_by_waiter(self):
        r=self.runobj();r.fault='memory'
        with self.assertRaises(RuntimeError):m.wait_until(r.check,20,'guard')
    def test_oom_and_diagnostics_do_not_prevent_stop_and_remove(self):
        r=self.runobj();r.core='a'*64;r.policy={};r.sup=Mock();sup=r.sup;r.stop_provider=Mock()
        guard=Mock();guard.inspect.return_value=('short',{'State':{'Running':False,'OOMKilled':True}})
        with patch.object(m,'OwnedCoreStop',return_value=guard),patch.object(m,'write',side_effect=OSError('full')),patch.object(m.subprocess,'run',side_effect=OSError('log error')),patch.object(m,'physical_idle'),patch.object(m,'docker') as dock:
            with self.assertRaisesRegex(m.ServiceError,'OOM'):r.stop_runtime(1)
        guard.stop.assert_called_once();sup.close.assert_called_once();r.stop_provider.assert_called_once();dock.assert_called_once_with('rm','a'*64)
        self.assertIsNone(r.core);self.assertIsNone(r.sup);self.assertEqual(len(r.diagnostic_errors),2)
    def test_uncertain_stop_inactive_requires_restoration(self):
        r=self.runobj();r.stop_intent=True;r.router_stopped=False;r.restore=Mock();r.restore_scheduler=Mock()
        def cmd(*args,**kw):return '0' if 'MainPID' in args else 'inactive'
        with patch.object(m,'command',side_effect=cmd):r.cleanup()
        self.assertTrue(r.router_stopped);r.restore.assert_called_once();r.restore_scheduler.assert_not_called()
    def test_uncertain_stop_active_reconciles_without_restart(self):
        r=self.runobj();r.stop_intent=True;r.restore=Mock();r.restore_scheduler=Mock()
        with patch.object(m,'command',return_value='active'),patch.object(m,'health',return_value=healthy()):r.cleanup()
        self.assertFalse(r.router_stopped);self.assertFalse(r.stop_intent);r.restore.assert_not_called();r.restore_scheduler.assert_called_once()
    def test_failed_known_restore_job_is_not_resubmitted(self):
        r=self.runobj();r.router_stopped=True;r.restore_started=True;r.restore_submission_requested=True;r.restore_job='a'*32;r.restore_deadline=time.monotonic()+30
        with patch.object(m,'production_hashes'),patch.object(m,'health',return_value=healthy()),patch.object(m,'request',return_value={'status':'failed'}) as req:
            for _ in range(2):
                with self.assertRaisesRegex(m.ServiceError,'not replayed'):r.restore()
        self.assertTrue(r.router_stopped);self.assertEqual(req.call_count,2)
        self.assertTrue(all(call.args[1]=='GET' for call in req.call_args_list))
    def test_unknown_restore_submission_never_replayed(self):
        r=self.runobj();r.router_stopped=True;r.restore_started=True;r.restore_submission_requested=True
        with patch.object(m,'production_hashes'),patch.object(m,'health',return_value=healthy()),patch.object(m,'request') as req:
            with self.assertRaisesRegex(m.ServiceError,'no automatic replay'):r.restore()
        req.assert_not_called();self.assertTrue(r.router_stopped)
    def test_final_health_failure_keeps_restore_pending(self):
        r=self.runobj();r.router_stopped=True;r.restore_started=True;r.restore_submission_requested=True;r.restore_job='a'*32;r.restore_deadline=time.monotonic()+30
        bad=healthy();bad['gpu']['ollama_selected']='gpt-oss-120b'
        with patch.object(m,'production_hashes'),patch.object(m,'health',side_effect=[healthy(),bad]),patch.object(m,'request',return_value={'status':'completed'}):
            with self.assertRaisesRegex(m.ServiceError,'not restored'):r.restore()
        self.assertTrue(r.router_stopped)
    def test_committed_pause_resume_timeout_is_reconciled_not_replayed(self):
        r=self.runobj();r.pause_intent=True;r.original_scheduler_paused=False;r.paused_by_us=True;paused=True;resumes=[]
        def orch(method):
            nonlocal paused
            if method=='status':return {'paused':paused}
            resumes.append(method);paused=False;raise subprocess.TimeoutExpired('resume',3)
        with patch.object(m,'health',return_value=healthy()),patch.object(m,'orch',side_effect=orch):r.restore_scheduler()
        self.assertEqual(resumes,['resume_scheduler']);self.assertFalse(r.pause_intent);self.assertFalse(r.paused_by_us)
    def test_diagnostic_error_is_nonfatal(self):
        r=self.runobj();r.diagnostic(lambda:(_ for _ in ()).throw(OSError('full')));self.assertEqual(len(r.diagnostic_errors),1)
    def test_pending_create_lookup_failure_blocks_original_restore(self):
        r=self.runobj();r.provider_create_pending='bridge';r.restore=Mock();r.restore_scheduler=Mock()
        with patch.object(m,'docker',side_effect=OSError('lookup unavailable')):
            with self.assertRaises(OSError):r.cleanup()
        self.assertEqual(r.provider_create_pending,'bridge');r.restore.assert_not_called();r.restore_scheduler.assert_not_called()
    def test_monitor_open_failure_sets_fault_and_ready(self):
        r=self.runobj()
        with patch('builtins.open',side_effect=OSError('resource log unavailable')):r.monitor()
        self.assertTrue(r.monitor_ready.is_set());self.assertIn('unavailable',r.fault)
    def test_logging_failure_before_start_does_not_mark_attempted(self):
        r=m.Run([]);r.router_stopped=True
        with patch.object(m,'production_hashes'),patch.object(m,'physical_idle'),patch.object(m,'write',side_effect=OSError('full')),patch.object(m,'command') as cmd:
            with self.assertRaises(OSError):r.restore()
        self.assertFalse(r.restore_started);self.assertFalse(r.restore_submission_requested);cmd.assert_not_called()
if __name__=='__main__':unittest.main()

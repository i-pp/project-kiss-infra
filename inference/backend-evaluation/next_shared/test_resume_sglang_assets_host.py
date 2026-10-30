from contextlib import redirect_stdout
import io,json,sys,tempfile,unittest,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import resume_sglang_assets_host as r
import host_api_trial as h
import test_host_api_trial as f

class ResumeTests(unittest.TestCase):
    def test_default_no_guard_or_model_action(self):
        with patch.object(sys,'argv',['resume']),patch.object(h,'helpers',side_effect=AssertionError('no host')),redirect_stdout(io.StringIO()) as out:self.assertEqual(r.main(),0)
        self.assertIn('NO_ACTIONS',out.getvalue())
    def test_fixed20size_and_rate_fit240_and900_budgets(self):
        p=r.plan();self.assertEqual(p['files'],20);self.assertAlmostEqual(p['nominal_paced_seconds'],179.8505040295422)
        self.assertLess(p['nominal_paced_seconds'],240);self.assertEqual(sum(p[k] for k in ['asset_phase_seconds','startup_seconds','generation_seconds','recovery_reserved_seconds']),815)
        with patch.object(h,'WHOLE',814),self.assertRaisesRegex(h.Blocked,'BUDGET_INCONSISTENT'):r.plan()
    def test_copied_resume_layout_is_rejected(self):
        with patch.object(r,'__file__','/tmp/copied/resume.py'),self.assertRaisesRegex(h.Blocked,'INSTALLED_RESUME_LAYOUT'):r.installed_project()
    def test_operator_root_mismatch_cannot_create_or_reserve_anything(self):
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)
            with patch.object(sys,'argv',['resume','--resume-human-approved']),patch.object(sys.stdin,'isatty',return_value=True),patch.object(h,'install_sigterm_handler'),patch.object(r,'installed_project',return_value=project),patch.object(h,'operator_record',return_value={'project_root':'/different'}),patch.object(h,'helpers',side_effect=AssertionError('no host action')),self.assertRaisesRegex(h.Blocked,'PROJECT_MISMATCH'):r.main()
            self.assertEqual(list(project.iterdir()),[])
    def test_same_gpu_allowance_single_post_and_second_start_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);record=f.record(root);record['review'].update(aiter_cache_profile=h.AITER_PROFILE,sglang_sequential_loader_profile='one-thread-v1')
            project=Path(record['project_root']);c=f.Coordinator();http=f.HTTP()
            class D(f.Driver):
                def create(self,ident,rec,backend):
                    cid=super().create(ident,rec,backend);argv=h.server_argv(backend,rec)
                    self.row['Config'].update(Entrypoint=[argv[0]],Cmd=argv[1:],Env=[k+'='+v for k,v in h.server_environment(backend,rec).items()]);return cid
            driver=D();real=h.Trial
            def trial(*args,**kw):
                kw['network_profile']={'name':h.NETWORK,'id':'c'*64};kw['unchanged']=lambda _:True
                return real(*args,**kw)
            def directory(p):p.mkdir(parents=True,exist_ok=True);return p
            def verify(path,check,report):check();report({'event':'fixture_fullSHA','phase':'ASSET_VERIFY'});return []
            original_intent=project/'agents/local_llm/.runtime/backend-api-trials'/('preflight-sglang-'+h.SEQUENTIAL_OPERATOR_SHA+'.json')
            original_intent.parent.mkdir(parents=True);original_intent.write_text('original source intent, never replace')
            before=original_intent.read_bytes()
            modules={'local_llm':SimpleNamespace(policy_context=lambda _:{'system':'COMMON POLICY FIXTURE','metadata':{'sha256':'fixture'}})}
            with patch.object(sys,'argv',['resume','--resume-human-approved']),patch.object(sys.stdin,'isatty',return_value=True),patch.object(h,'install_sigterm_handler'),patch.object(r,'installed_project',return_value=project),patch.object(h,'operator_record',return_value=record),patch.object(h,'validate_aiter_retry',return_value={}),patch.object(h,'helpers',return_value=(lambda *a:c,directory,f.write,f.healthy)),patch.object(h,'Docker',return_value=driver),patch.object(h,'LocalHTTP',return_value=http),patch.object(h,'Trial',side_effect=trial),patch.object(r,'reuse_static',return_value={'status':'STATIC_CHECKED'}),patch.object(r,'verify_slow',side_effect=verify),patch.dict(sys.modules,modules),redirect_stdout(io.StringIO()):
                self.assertEqual(r.main(),0)
                with self.assertRaisesRegex(h.Blocked,'ALREADY_RESERVED'):r.main()
            self.assertEqual(http.posts,1);self.assertEqual(c.events.count('restore'),1)
            self.assertEqual(original_intent.read_bytes(),before);self.assertTrue(h.approved_attempt_path(original_intent.parent,'sglang',h.SEQUENTIAL_OPERATOR_SHA).exists())

if __name__=='__main__':unittest.main()

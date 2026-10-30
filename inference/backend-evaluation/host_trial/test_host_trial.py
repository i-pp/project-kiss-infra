"""Coordinator and artifacts fakes only; never loads Strata, a model or Docker."""
from contextlib import contextmanager,redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import assets
import host_strata_trial as h
from owned_process import GIB


def healthy():return {'mem_available':40*GIB,'gpu_used':2*GIB,'gtt_used':0,'swap_used':0}


class FakeCoordinator:
    def __init__(self):self.mutated=False;self.events=[];self.fail_restore=False
    @contextmanager
    def locked(self):
        self.events.append('lock');yield;self.events.append('unlock')
    def idle(self):self.events.append('idle')
    def unload(self):self.events.append('unload');self.mutated=True
    def restore(self):
        self.events.append('restore')
        if self.fail_restore:raise OSError('lost')
        return {'status':'RESTORED'}
    def uncertain(self,reason):self.events.append('unknown:'+reason)


class FakeRunner:
    fail=None;unsafe=False;requests=0
    def __init__(self,**kw):self.run_dir=kw['run_dir'];self.calls=[]
    def run(self,argv,cwd,timeout,**kw):
        self.calls.append(argv)
        script=next((Path(x).name for x in argv if x.endswith('.py')),'')
        ok={'status':'COMPLETED','cleanup':{'complete':True},'reason':None}
        if script==self.fail:return {'status':'FAILED','cleanup':{'complete':not self.unsafe},'reason':'simulated'}
        if script=='strata_pack.py' and 'build' in argv:
            out=Path(argv[argv.index('--out')+1]);out.mkdir();n=int(argv[argv.index('--layers')+1])
            (out/'manifest.json').write_text(json.dumps({'n_layers':n,'n_experts_per_layer':512,'source':{'shard1_sha256':'69820c02ec7d0b45ef2ebb19d6620299db749fe2aded7f39f93c6b88b199b720','shard2_sha256':'316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113'}}))
            with (out/'experts.bin').open('wb') as f:f.truncate(n*512*1382400)
        if script=='strata_shim.py':
            path=Path(argv[argv.index('--output')+1]);mode=argv[3]
            path.write_text(json.dumps({'prompt_ids':[1,2],'stop_ids':[248044,248046]} if mode=='encode' else {'content':h.ACK}))
        return ok
    def rawserve(self,argv,cwd,ids,**kw):
        assert '--mmap-experts' in argv and '--ple-io' in argv and 'direct' in argv
        assert kw['required_startup_marker']=='experts via mmap (--mmap-experts;'
        self.requests+=1
        return {'status':'COMPLETED','cleanup':{'complete':True},'generation_requests':1,
                'token_ids':[4],'done':{'finish':'stop'},'root_identity':{'pid':123,'starttime':456}}


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.source=self.root/'source';self.source.mkdir()
        self.shards=[self.root/'a.gguf',self.root/'b.gguf']
        for p in self.shards:p.write_bytes(b'original')
        self.v={'source':self.source,'llama':self.root,'exe':self.root/'NOT_EXECUTED_ENGINE','shards':self.shards}
        self.c=FakeCoordinator()
    def tearDown(self):self.tmp.cleanup()
    def execute(self,runner=FakeRunner,probe=healthy):
        fake=SimpleNamespace(policy_context=lambda _: {'system':'fixture','metadata':{'version':'fixture'}})
        with patch.dict(sys.modules,{'local_llm':fake}),patch('shutil.disk_usage',return_value=SimpleNamespace(free=150*GIB)),redirect_stdout(io.StringIO()):
            t=h.Trial(self.repo,self.v,self.c,runner_factory=runner,probe=probe,run_root=self.root/'runs')
            r=t.execute()
        return t,r
    def test_success_pilot_full_one_generation_restore_originals(self):
        t,r=self.execute()
        self.assertEqual(r['status'],'COMPLETED',r)
        self.assertEqual(r['quality'],'ACK_ONLY_PASS')
        self.assertEqual(r['generation_requests'],1);self.assertEqual(self.c.events,['lock','idle','unload','restore','unlock'])
        self.assertTrue(r['source_metadata_unchanged']);self.assertEqual([p.read_bytes() for p in self.shards],[b'original']*2)
        builds=[a for a in t.runner.calls if 'build' in a]
        self.assertEqual([a[a.index('--layers')+1] for a in builds],['1','48'])
        self.assertNotEqual(builds[0][builds[0].index('--out')+1],builds[1][builds[1].index('--out')+1])
    def test_pack_failure_restores_without_inference_or_retry(self):
        class Bad(FakeRunner):fail='strata_pack.py'
        t,r=self.execute(Bad)
        self.assertEqual(r['status'],'FAILED');self.assertIn('restore',self.c.events)
        self.assertEqual(r['generation_requests'],0);self.assertEqual(sum('strata_pack.py' in ' '.join(a) for a in t.runner.calls),1)
    def test_surviving_owned_process_blocks_restore_and_preserves_unknown(self):
        class Unsafe(FakeRunner):fail='strata_pack.py';unsafe=True
        t,r=self.execute(Unsafe)
        self.assertEqual(r['status'],'UNKNOWN');self.assertNotIn('restore',self.c.events)
        self.assertTrue(any(x.startswith('unknown:') for x in self.c.events))
    def test_restore_failure_is_unknown_and_never_retried(self):
        self.c.fail_restore=True;t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(self.c.events.count('restore'),1)
        self.assertIn('unknown:STRATA_TRIAL_RESTORE_UNCERTAIN',self.c.events)
    def test_source_change_never_hides_unknown_owned_cleanup(self):
        shard=self.shards[0]
        class UnsafeChanged(FakeRunner):
            fail='strata_pack.py';unsafe=True
            def run(self,*args,**kwargs):
                result=super().run(*args,**kwargs)
                if result['status']=='FAILED':shard.write_bytes(b'changed metadata')
                return result
        t,r=self.execute(UnsafeChanged)
        self.assertEqual(r['status'],'UNKNOWN');self.assertNotIn('restore',self.c.events)
        self.assertEqual(r['restoration'],'BLOCKED_OWNED_PROCESSES_REMAIN')
        self.assertEqual(r['source_integrity_error'],'SOURCE_METADATA_CHANGED')
        self.assertFalse(r['source_metadata_unchanged'])
    def test_source_change_never_hides_unknown_restore(self):
        def restore():
            self.c.events.append('restore');self.shards[0].write_bytes(b'changed metadata')
            raise OSError('restore unconfirmed')
        self.c.restore=restore;t,r=self.execute()
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(r['restoration'],'UNKNOWN')
        self.assertEqual(self.c.events.count('restore'),1)
        self.assertEqual(r['source_integrity_error'],'SOURCE_METADATA_CHANGED')
    def test_bad_initial_memory_never_unloads(self):
        t,r=self.execute(probe=lambda:{**healthy(),'mem_available':23*GIB})
        self.assertEqual(r['status'],'FAILED');self.assertFalse(self.c.mutated);self.assertEqual(t.runner.calls,[])
    def test_busy_coordinator_never_unloads(self):
        self.c.idle=lambda:(_ for _ in ()).throw(h.Blocked('BUSY'))
        t,r=self.execute();self.assertFalse(self.c.mutated);self.assertEqual(t.runner.calls,[])
    def test_partial_pack_geometry_not_accepted(self):
        p=self.root/'bad';p.mkdir();(p/'manifest.json').write_text(json.dumps({'n_layers':1,'n_experts_per_layer':512}))
        (p/'experts.bin').write_bytes(b'partial')
        with self.assertRaises(h.Blocked):h.validate_pack(p,1)
    def test_environment_does_not_inherit_hooks_or_credentials(self):
        with patch.dict(os.environ,{'STRATA_ARENA_MMAP':'1','LD_PRELOAD':'danger','SECRET_KEY':'hidden','PYTHONPATH':'danger'}):
            env=h.environment_for(self.v,self.root)
        self.assertNotIn('LD_PRELOAD',env);self.assertNotIn('SECRET_KEY',env);self.assertNotIn('STRATA_ARENA_MMAP',env)
        self.assertEqual(env['STRATA_KEEP_LEFTOVERS'],'1');self.assertEqual(env['HF_HUB_OFFLINE'],'1')
    def test_unknown_coordinator_status_is_not_idle(self):
        for data in [{},{'paused':False}]:
            with self.assertRaises(h.Blocked):h.require_idle_status(data,self.root)
    def test_coordinator_status_identity_types_and_busy_state(self):
        data={'runtime':str(self.root.resolve()),'paused':False,'stopping':False,'active_tasks':[],
              'blocked':[],'pending_recovery':[],'task_counts':{'COMPLETED':1}}
        self.assertEqual(h.require_idle_status(data,self.root),data)
        for changes in [{'runtime':'/wrong'},{'paused':0},{'active_tasks':['work']},{'task_counts':{'RUNNING':1}}]:
            with self.assertRaises(h.Blocked):h.require_idle_status({**data,**changes},self.root)
    def test_human_guard_rejects_non_tty_before_foreign_import(self):
        with patch('host_strata_trial.sys.stdin.isatty',return_value=False):
            with self.assertRaises(h.Blocked):h.host_guard(self.root/'NOT_IMPORTED')
    def test_human_guard_rejects_root_without_source_import(self):
        with patch('host_strata_trial.sys.stdin.isatty',return_value=True),patch('host_strata_trial.os.getuid',return_value=0):
            with self.assertRaisesRegex(h.Blocked,'NONROOT'):h.host_guard(self.root/'NOT_IMPORTED')
    def test_coordinator_restore_uses_owned_lock_without_recursive_prepare(self):
        calls=[]
        rt=SimpleNamespace(snapshot=lambda _: {h.MODEL:'unloaded','other':'unloaded'},
            _threshold=lambda **_:{},_post=lambda *a:calls.append(a[0]),
            _wait=lambda *a:{h.MODEL:'loaded','other':'unloaded'},
            read=lambda *a:{'model_alias':h.MODEL,'default_generation_settings':{'n_ctx':32768},'total_slots':1},
            _idle=lambda *a:None)
        c=h.Coordinator.__new__(h.Coordinator);c.rt=rt;c.lifecycle_unknown=False;c.post_once=lambda path,deadline:rt._post(path,h.MODEL,deadline)
        self.assertEqual(c.restore()['status'],'RESTORED');self.assertEqual(calls,['/models/load'])

    def test_cpu_runner_exception_never_assumes_previous_cleanup(self):
        class Crashed(FakeRunner):
            def run(self,*a,**kw):raise RuntimeError('unconfirmed runner')
        t,r=self.execute(Crashed)
        self.assertEqual(r['status'],'UNKNOWN');self.assertNotIn('restore',self.c.events)
    def test_unknown_generation_preserved_even_when_cleanup_and_restore_succeed(self):
        class Unknown(FakeRunner):
            def rawserve(self,*a,**kw):return {'status':'UNKNOWN','cleanup':{'complete':True},'generation_requests':1,'token_ids':[],'done':None,'root_identity':{'pid':123},'reason':'MISSING_DONE'}
        t,r=self.execute(Unknown)
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(r['restoration']['status'],'RESTORED')
        self.assertTrue((t.run_root/'strata-UNCERTAIN.json').exists());self.assertEqual(r['generation_requests'],1)
    def test_lifecycle_interrupt_has_no_background_submitter_and_blocks_restore(self):
        import threading,time
        caller=threading.get_ident();observed=[]
        def request(*a,**kw):observed.append(threading.get_ident());raise KeyboardInterrupt()
        c=h.Coordinator.__new__(h.Coordinator);c.lifecycle_unknown=False
        c.rt=SimpleNamespace(api=SimpleNamespace(request=request,abort=lambda:None),_threshold=lambda:None)
        with self.assertRaises(KeyboardInterrupt):c.post_once('/models/unload',time.monotonic()+1)
        self.assertEqual(observed,[caller]);self.assertTrue(c.lifecycle_unknown)
        with self.assertRaises(h.Blocked):c.restore()


class AssetTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_python_source_mismatch_and_extra_module_refused(self):
        p=self.root/'a.py';p.write_bytes(b'pass\n');raw=p.read_bytes()
        m={'commit':'fixture','files':[{'path':'a.py','bytes':len(raw),'git_blob_sha1':hashlib.sha1(b'blob 5\0'+raw).hexdigest()}]}
        self.assertEqual(assets.verify_python_tree(self.root,m)['python_files_verified'],1)
        (self.root/'hook.py').write_text('not executed')
        with self.assertRaises(ValueError):assets.verify_python_tree(self.root,m)
        (self.root/'hook.py').unlink();p.write_text('changed')
        with self.assertRaises(ValueError):assets.verify_python_tree(self.root,m)
    def test_bundle_hash_and_operator_record_required(self):
        p=self.root/'engine';p.write_bytes(b'not executed');p.chmod(0o700)
        notice=self.root/'LICENSE';notice.write_bytes(b'MIT fixture notice')
        record={'archive_sha256':assets.ENGINE_SHA,'engine_version':'0.1.52',
            'signed_manifest_verified_by_operator':True,'third_party_notices_reviewed_by_operator':True,
            'entrypoint_relative':'engine','files':[{'path':'engine','bytes':len(p.read_bytes()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]}
        record['files'].append({'path':'LICENSE','bytes':notice.stat().st_size,'sha256':hashlib.sha256(notice.read_bytes()).hexdigest()})
        self.assertEqual(assets.verify_bundle(self.root,record),p)
        record['files'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):assets.verify_bundle(self.root,record)
    def test_extra_bundle_file_or_symlink_escape_refused(self):
        p=self.root/'engine';p.write_bytes(b'x');p.chmod(0o700)
        r={'archive_sha256':assets.ENGINE_SHA,'engine_version':'0.1.52',
            'signed_manifest_verified_by_operator':True,'third_party_notices_reviewed_by_operator':True,
            'entrypoint_relative':'engine','files':[{'path':'engine','bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}]}
        (self.root/'hook.so').write_bytes(b'never loaded')
        with self.assertRaises(ValueError):assets.verify_bundle(self.root,r)
        (self.root/'hook.so').unlink();(self.root/'escape').symlink_to('/etc/passwd')
        r['files'].append({'path':'escape','type':'symlink','target':'/etc/passwd'})
        with self.assertRaises(ValueError):assets.verify_bundle(self.root,r)
    def test_execution_entrypoint_cannot_differ_from_signed_manifest(self):
        root=self.root
        for name in ['source','llama','engine']: (root/name).mkdir()
        for name in ['strata-source-files.json','gguf-source-files.json']:(root/name).write_text('{"files":[],"commit":"fixture"}')
        record={'schema':1,'source_commit':assets.COMMIT,'llama_commit':assets.LLAMA_COMMIT,
                'source_root':str(root/'source'),'llama_root':str(root/'llama'),'engine_root':str(root/'engine'),
                'engine':{'entrypoint_relative':'strata-vision'},'approval_reference':'fixture',
                'coordinator_runtime_relative':'.runtime/existing'}
        with patch('assets.private_record',return_value=record),patch('assets.verify_python_tree',return_value={}),patch('publisher_verify.verify_signed_bundle',return_value={'entrypoint_relative':'strata'}):
            with self.assertRaisesRegex(ValueError,'entrypoint differs'):assets.verify(root/'not-read',root,root)
    def test_model_path_traversal_refused(self):
        with self.assertRaises(ValueError):assets.regular(self.root,'../etc/passwd')
    def test_private_record_refuses_world_readable_file(self):
        p=self.root/'operator.json';p.write_text('{}');p.chmod(0o644)
        with self.assertRaises(ValueError):assets.private_record(p)


if __name__=='__main__':unittest.main()

"""CPU fakes only. Never opens Docker, registry, GPU, or a real subprocess."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import acquire_sglang_host as m


def image():
    return {'Id':'sha256:'+'a'*64,'RepoDigests':[m.IMAGE],'Os':'linux','Architecture':'amd64',
            'Size':32000000000,'Config':{'Labels':{'org.opencontainers.image.revision':'example'}}}

class FakeDocker:
    clients_reaped=True
    def __init__(self,existing=False,pull_error=None,preflight_error=None):
        self.existing=existing;self.pull_error=pull_error;self.preflight_error=preflight_error;self.calls=[]
    def preflight(self):
        self.calls.append('preflight')
        if self.preflight_error:raise self.preflight_error
        return '29.9.2'
    def inspect(self):
        self.calls.append('inspect')
        if not self.existing:raise m.MissingImage('FIXED_IMAGE_ABSENT')
        return image()
    def pull_once(self):
        self.calls.append('pull')
        if self.pull_error:raise self.pull_error
        self.existing=True

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        disk=patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=128*(1<<30)))
        disk.start();self.addCleanup(disk.stop)
        self.parent=Path(self.temp.name)/'acquisition'
        self.stdout=contextlib.redirect_stdout(io.StringIO());self.stdout.__enter__();self.addCleanup(self.stdout.__exit__,None,None,None)
    def journal(self):
        j=m.Journal(self.parent);self.addCleanup(j.close);return j
    def test_existing_exact_image_no_pull(self):
        j=self.journal();d=FakeDocker(existing=True);r=m.acquire(d,j)
        self.assertEqual(r['pull_requests'],0);self.assertEqual(d.calls,['preflight','inspect'])
        self.assertFalse((j.parent/'pull-intent.json').exists())
    def test_single_pull_and_metadata_receipt(self):
        j=self.journal();d=FakeDocker();r=m.acquire(d,j)
        self.assertEqual(d.calls,['preflight','inspect','pull','inspect']);self.assertEqual(r['pull_requests'],1)
        self.assertEqual(r['metadata']['unpacked_size_bytes'],32000000000)
        self.assertEqual(json.loads((j.run/'receipt.json').read_text())['status'],'ACQUIRED_METADATA_VERIFIED')
    def test_low_project_disk_blocks_before_pull_intent(self):
        j=self.journal();d=FakeDocker()
        with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=63*(1<<30))):
            with self.assertRaisesRegex(m.Blocked,'FREE_BELOW64GIB'):m.acquire(d,j)
        self.assertNotIn('pull',d.calls);self.assertFalse((j.parent/'pull-intent.json').exists())
    def test_preflight_permission_denied_never_pulls(self):
        j=self.journal();d=FakeDocker(preflight_error=PermissionError('denied'))
        with self.assertRaises(PermissionError):m.acquire(d,j)
        self.assertEqual(d.calls,['preflight']);self.assertFalse((j.parent/'pull-intent.json').exists())
    def test_pull_timeout_unknown_intent_retained(self):
        j=self.journal();d=FakeDocker(pull_error=TimeoutError())
        with self.assertRaises(m.Unknown):m.acquire(d,j)
        self.assertEqual(d.calls.count('pull'),1);self.assertTrue((j.parent/'pull-intent.json').exists())
        self.assertEqual(json.loads((j.run/'receipt.json').read_text())['status'],'UNKNOWN_NO_RETRY')
    def test_pull_interrupt_unknown(self):
        j=self.journal();d=FakeDocker(pull_error=KeyboardInterrupt())
        with self.assertRaises(m.Unknown):m.acquire(d,j)
        self.assertEqual(json.loads((j.run/'receipt.json').read_text())['status'],'UNKNOWN_NO_RETRY')
    def test_prior_intent_blocks_second_pull(self):
        j=self.journal();m.exclusive_json(j.parent/'pull-intent.json',{'prior':'unknown'})
        d=FakeDocker()
        with self.assertRaises(FileExistsError):m.acquire(d,j)
        self.assertNotIn('pull',d.calls)
    def test_existing_image_can_be_read_after_unknown(self):
        j=self.journal();m.exclusive_json(j.parent/'pull-intent.json',{'prior':'unknown'})
        d=FakeDocker(existing=True);r=m.acquire(d,j)
        self.assertEqual(r['pull_requests'],0)
        self.assertEqual(json.loads((j.parent/'pull-intent.json').read_text()),{'prior':'unknown'})
    def test_intent_durable_before_pull(self):
        j=self.journal();d=FakeDocker();old=d.pull_once
        def pull():
            self.assertTrue((j.parent/'pull-intent.json').is_file());self.assertTrue((j.run/'intent.json').is_file());old()
        d.pull_once=pull;m.acquire(d,j)
    def test_metadata_identity_platform_and_size_fail_closed(self):
        changes=[('RepoDigests',['rocm/sgl-dev@sha256:'+'b'*64]),('Os','windows'),('Architecture','arm64'),('Id','not-id'),('Size',0),('Size',True)]
        for k,v in changes:
            with self.subTest(k=k,v=v):
                d=image();d[k]=v
                with self.assertRaises(m.Blocked):m.verify_metadata(d)
    def test_labels_preserved_as_metadata_only(self):
        d=image();d['Config']['Labels']['other']='never execute'
        self.assertEqual(m.verify_metadata(d)['labels'],d['Config']['Labels'])
    def test_symlink_receipt_rejected(self):
        j=self.journal();outside=Path(self.temp.name)/'other';outside.write_text('same')
        (j.run/'x.json').symlink_to(outside)
        with self.assertRaises(m.Blocked):j.write('x.json',{'changed':True})
        self.assertEqual(outside.read_text(),'same')
    def test_receipt_and_progress_private(self):
        j=self.journal();m.acquire(FakeDocker(existing=True),j)
        for f in [j.run/'receipt.json',j.run/'progress.jsonl']:
            self.assertEqual(f.stat().st_mode&0o777,0o600)
    def test_default_cli_has_no_guard_or_subprocess(self):
        with patch.object(sys_argv:=m.sys,'argv',['acquire_sglang_host.py']),patch.object(m,'installed_context',side_effect=AssertionError('guard should not run')),patch.object(m.subprocess,'Popen',side_effect=AssertionError('no process')):
            self.assertEqual(m.main(),0)
    def test_task_layout_cannot_be_used_as_human_launcher(self):
        with patch.object(m,'ROOT',Path(self.temp.name)/'task-only/sglang-image-acquisition'),self.assertRaises(m.Blocked):m.installed_context()
    def test_main_guard_before_runtime_creation(self):
        def denied():raise m.Blocked('Codex boundary')
        with patch.object(m.sys,'argv',['x','--acquire-human-approved']),patch.object(m,'installed_context',return_value=(Path(self.temp.name),denied)),patch.object(m,'Journal',side_effect=AssertionError('no files before guard')):
            with self.assertRaises(m.Blocked):m.main()
    def test_sigterm_is_caught_as_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):m.terminate(signal.SIGTERM,None)
    def driver(self,process,clock=lambda:0,sleep=lambda _:None):
        j=self.journal();d=m.Docker(lambda:None,j,clock,sleep)
        factory=patch.object(m.subprocess,'Popen',return_value=process);factory.start();self.addCleanup(factory.stop)
        return d,j
    def test_only_fixed_docker_actions(self):
        d,j=self.driver(object())
        for args in [['run',m.IMAGE],['pull','other:latest'],['context','use','other']]:
            with self.assertRaises(m.Blocked):d.command(args,'pull',m.PULL_SECONDS)
    def test_timeout_kills_reaps_client_only(self):
        class Proc:
            returncode=None;killed=0;waits=0
            def poll(self):return None
            def kill(self):self.killed+=1
            def wait(self,timeout):self.waits+=1;return 137
        p=Proc();times=iter([0,1801]);d,j=self.driver(p,clock=lambda:next(times))
        with self.assertRaises(m.Unknown):d.pull_once()
        self.assertEqual((p.killed,p.waits),(1,1));self.assertTrue(d.clients_reaped)
    def test_interrupt_kills_reaps_client(self):
        class Proc:
            returncode=None;killed=0
            def poll(self):raise KeyboardInterrupt()
            def kill(self):self.killed+=1
            def wait(self,timeout):return 137
        p=Proc();d,j=self.driver(p)
        with self.assertRaises(m.Unknown):d.pull_once()
        self.assertEqual(p.killed,1)
    def test_interrupt_immediately_after_spawn_reaps_client(self):
        class Proc:
            returncode=None;killed=0;waits=0
            def poll(self):return None
            def kill(self):self.killed+=1
            def wait(self,timeout):self.waits+=1;return 137
        proc=Proc();d,j=self.driver(proc)
        source=Path(m.__file__).read_text().splitlines()
        target=next(i+1 for i,line in enumerate(source) if 'next_progress=start+2' in line)
        def trace(frame,event,arg):
            if frame.f_code.co_filename==m.__file__ and event=='line' and frame.f_lineno==target:
                m.sys.settrace(None);raise KeyboardInterrupt()
            return trace
        try:
            m.sys.settrace(trace)
            with self.assertRaises(m.Unknown):d.pull_once()
        finally:m.sys.settrace(None)
        self.assertEqual((proc.killed,proc.waits),(1,1));self.assertTrue(d.clients_reaped)
    def test_interrupt_inside_spawn_has_no_confirmed_reap(self):
        j=self.journal();d=m.Docker(lambda:None,j)
        with patch.object(m.subprocess,'Popen',side_effect=KeyboardInterrupt()),self.assertRaises(m.Unknown):d.pull_once()
        self.assertFalse(d.clients_reaped)
    def test_kill_failure_still_attempts_wait(self):
        class Proc:
            returncode=None;waits=0
            def poll(self):raise KeyboardInterrupt()
            def kill(self):raise PermissionError('client kill denied')
            def wait(self,timeout):self.waits+=1;return 137
        proc=Proc();d,j=self.driver(proc)
        with self.assertRaises(m.Unknown):d.pull_once()
        self.assertEqual(proc.waits,1);self.assertFalse(d.clients_reaped)
    def test_cli_environment_and_endpoint_fixed(self):
        captured={}
        class Proc:
            returncode=0
            def poll(self):return 0
            def wait(self,timeout):return 0
        def popen(argv,**kw):
            captured.update(argv=argv,**kw);os.write(kw['stdout'],b'29.9.2\n');return Proc()
        j=self.journal();d=m.Docker(lambda:None,j)
        with patch.object(m.subprocess,'Popen',side_effect=popen):self.assertEqual(d.preflight(),'29.9.2')
        self.assertEqual(captured['argv'][:3],['/usr/bin/docker','--host','unix:///var/run/docker.sock'])
        self.assertEqual(set(captured['env']),{'PATH','LANG','DOCKER_CONFIG'})
    def test_not_found_does_not_include_permission_denied(self):
        class Proc:
            returncode=1
            def poll(self):return 1
            def wait(self,timeout):return 1
        for stderr,kind in [(('Error response from daemon: No such image: '+m.IMAGE+'\n').encode(),m.MissingImage),(b'permission denied while trying to connect to Docker\n',m.Blocked)]:
            with self.subTest(stderr=stderr):
                j=self.journal();d=m.Docker(lambda:None,j)
                def popen(argv,**kw):os.write(kw['stderr'],stderr);return Proc()
                with patch.object(m.subprocess,'Popen',side_effect=popen),self.assertRaises(kind) as cm:d.inspect()
                if kind is m.Blocked:self.assertNotIsInstance(cm.exception,m.MissingImage)

if __name__=='__main__':unittest.main()

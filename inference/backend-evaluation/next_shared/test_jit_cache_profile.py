"""CPU-only fixed argv/contract checks: no Docker, mounts, GPU or model imports."""
import copy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import host_api_trial as h


def tmpfs_contract():
    return {'/tmp':'rw,noexec,nosuid,nodev,size=2g',
            '/jit-cache':'rw,exec,nosuid,nodev,size=512m,mode=0700,uid='+str(os.getuid())+',gid='+str(os.getgid())}


def fixture():
    record={'model_dir':'/fixture/models/next','runtimes':{'vllm':{'image_ref':'sha256:'+'1'*64}}}
    argv=h.server_argv('vllm')
    row={'Config':{'Entrypoint':[argv[0]],'Cmd':argv[1:],'User':str(os.getuid())+':'+str(os.getgid()),'Healthcheck':{'Test':['NONE']}},
        'HostConfig':{'Memory':32*h.GIB,'MemorySwap':32*h.GIB,'ReadonlyRootfs':True,
            'Tmpfs':tmpfs_contract(),'Privileged':False,'NetworkMode':h.NETWORK,'PidsLimit':512,'NanoCpus':8_000_000_000,
            'Init':True,'IpcMode':'private','CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],'PortBindings':{}},
        'Mounts':[{'Type':'bind','Source':record['model_dir'],'Destination':'/models/next-int4','RW':False},
            {'Type':'tmpfs','Destination':'/tmp'},{'Type':'tmpfs','Destination':'/jit-cache'}]}
    return record,row


class JITCacheProfileTests(unittest.TestCase):
    def test_fixed_create_has_exact_noexec_tmp_and_one_exec_cache(self):
        class Capture(h.Docker):
            def command(self,args,**kw):self.args=args;return 'a'*64
        driver=Capture(lambda:None);r,_=fixture()
        with patch.object(h.os,'stat',return_value=SimpleNamespace(st_gid=44)),patch.object(h.os,'getgroups',return_value=[44]):
            driver.create({'name':'fixed-fixture','token':'fixture','owner':str(os.getuid())},r,'vllm')
        mounts=[driver.args[i+1] for i,x in enumerate(driver.args) if x=='--tmpfs']
        self.assertEqual(mounts,['/tmp:'+tmpfs_contract()['/tmp'],'/jit-cache:'+tmpfs_contract()['/jit-cache']])
        self.assertEqual(sum('exec' in m.split(':',1)[1].split(',') for m in mounts),1)
        for token in ['--cap-drop','--security-opt','--read-only','--no-healthcheck','--ipc','--memory','--memory-swap']:
            self.assertIn(token,driver.args)
        self.assertEqual(driver.args[driver.args.index('--memory')+1],'32g')
        self.assertEqual(driver.args[driver.args.index('--memory-swap')+1],'32g')
    def test_both_backends_use_only_fixed_triton_cache(self):
        for backend in ['vllm','sglang']:
            env=h.server_environment(backend)
            self.assertEqual(env['TRITON_CACHE_DIR'],'/jit-cache/triton')
            self.assertEqual(env['TMPDIR'],'/tmp');self.assertEqual(env['HOME'],'/tmp/aceis-home');self.assertEqual(env['XDG_CACHE_HOME'],'/tmp/aceis-cache')
            self.assertEqual(env['HF_HUB_OFFLINE'],'1');self.assertEqual(env['TRANSFORMERS_OFFLINE'],'1')
    def test_exact_two_tmpfs_contract_is_accepted(self):
        r,row=fixture();h.verify_container_contract(row,r,'vllm')
    def test_general_exec_missing_cache_or_extra_mount_is_rejected(self):
        r,original=fixture()
        mutations=[{'/tmp':'rw,exec,nosuid,nodev,size=2g','/jit-cache':tmpfs_contract()['/jit-cache']},
                   {'/tmp':tmpfs_contract()['/tmp']},
                   {**tmpfs_contract(),'/other':'rw,exec,size=512m'}]
        for mounts in mutations:
            row=copy.deepcopy(original);row['HostConfig']['Tmpfs']=mounts
            with self.assertRaises(h.Blocked):h.verify_container_contract(row,r,'vllm')
    def test_larger_cache_wrong_owner_or_no_nosuid_is_rejected(self):
        r,original=fixture()
        for cache in [tmpfs_contract()['/jit-cache'].replace('size=512m','size=1g'),
                      tmpfs_contract()['/jit-cache'].replace('mode=0700','mode=0777'),
                      tmpfs_contract()['/jit-cache'].replace('nosuid,','')]:
            row=copy.deepcopy(original);row['HostConfig']['Tmpfs']['/jit-cache']=cache
            with self.assertRaises(h.Blocked):h.verify_container_contract(row,r,'vllm')
    def test_extra_bind_cannot_be_hidden_as_cache(self):
        r,row=fixture();row['Mounts'].append({'Type':'bind','Destination':'/jit-cache','Source':'/unreviewed','RW':True})
        with self.assertRaises(h.Blocked):h.verify_container_contract(row,r,'vllm')


if __name__=='__main__':unittest.main()

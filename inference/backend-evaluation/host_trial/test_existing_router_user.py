"""Synthetic existing-container metadata; no Docker, host API or namespace."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
INTEGRATION=HERE if (HERE/'host_router_maintenance.py').exists() else HERE.parents[2]/'agents/local_llm/integration'
sys.path.insert(0,str(INTEGRATION))
hm=importlib.import_module('host_router_maintenance')


class ExistingUserTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name)/'repo';self.llm=self.repo/'agents/local_llm';self.rt=self.llm/'.runtime'
        self.rt.mkdir(parents=True,mode=0o700);self.calls=[]
        self.profile={'project_root':str(self.repo),'image':hm.IMAGE,'router_name':hm.ROUTER,'resident_container_id':'a'*64}
        self.state={'schema':1,'resident_cid':'a'*64,'router_cid':'b'*64,'token':'c'*32,'phase':'DEPLOYED'}
        self.write('router-host-profile.json',self.profile);self.write('router-host-state.json',self.state)
    def write(self,name,value):
        p=self.rt/name;p.write_text(json.dumps(value));p.chmod(0o600)
    def make(self,user=None):
        def no_docker(*args,**kwargs):self.calls.append(args);raise AssertionError('no actual Docker')
        m=hm.Maintenance(self.llm,execute=no_docker,expected_existing_user=user)
        self.addCleanup(m.close);return m
    def router(self,m,user):
        return {'Id':'b'*64,'Name':'/'+hm.ROUTER,'Image':hm.IMAGE,'Path':'/app/llama-server','Args':hm.ROUTER_ARGS,
            'Config':{'User':user,'Labels':{'com.docker.compose.project':hm.PROJECT,'io.aceis.deployment':'c'*32}},
            'HostConfig':{'Memory':34359738368,'MemorySwap':34359738368,'NanoCpus':8000000000,'PidsLimit':512,
                'ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],'CapAdd':None,
                'SecurityOpt':['no-new-privileges:true'],'PortBindings':{'8080/tcp':[{'HostIp':'127.0.0.1','HostPort':'8080'}]}},
            'NetworkSettings':{'Networks':{'project-kiss-large-coder-b3_local':{}}},
            'Mounts':[{'Type':'bind','Destination':k,'Source':str(v),'RW':rw} for k,v,rw in [
                ('/models',self.repo/'models',False),('/cache',self.repo/'.cache/large-coder-b3/runtime',True),
                ('/config/models.ini',self.llm/'integration/router-presets.PROPOSAL.ini',False)]]}
    def test_actual_legacy_gid_failure_and_bound_fix_without_config_change(self):
        with patch.object(hm.os,'getgid',return_value=1000):
            default=self.make();value=self.router(default,str(os.getuid())+':973');default.inspect=lambda identity:value
            with self.assertRaises(hm.Failure) as failure:default.owned_router()
            self.assertEqual(failure.exception.code,'ROUTER_CONTRACT_MISMATCH')
            fixed=self.make(str(os.getuid())+':973');fixed.inspect=lambda identity:value
            before=json.dumps(value,sort_keys=True)
            self.assertIs(fixed.owned_router(),value)
            self.assertEqual(json.dumps(value,sort_keys=True),before)
            self.assertEqual(fixed.env['LOCAL_GID'],'1000');self.assertEqual(self.calls,[])
    def test_override_cannot_deploy_or_compose(self):
        m=self.make(str(os.getuid())+':973')
        for operation in [lambda:m.deploy(),lambda:m.compose('create')]:
            with self.assertRaises(hm.Failure) as failure:operation()
            self.assertEqual(failure.exception.code,'EXISTING_USER_RECOVERY_ONLY')
        self.assertEqual(self.calls,[])
    def test_other_protections_still_rejected_with_user_binding(self):
        m=self.make(str(os.getuid())+':973');value=self.router(m,m.expected_existing_user)
        value['HostConfig']['Privileged']=True;m.inspect=lambda identity:value
        with self.assertRaises(hm.Failure) as failure:m.owned_router()
        self.assertEqual(failure.exception.code,'ROUTER_CONTRACT_MISMATCH');self.assertEqual(self.calls,[])
    def test_root_other_owner_noncanonical_or_missing_cid_rejected(self):
        for value in ['0:973',str(os.getuid())+':0',str(os.getuid()+1)+':973',str(os.getuid())+':0973','user:docker']:
            with self.subTest(user=value),self.assertRaises(hm.Failure) as failure:self.make(value)
            self.assertEqual(failure.exception.code,'EXISTING_ROUTER_USER_UNCONFIRMED')
        self.state['router_cid']=None;self.write('router-host-state.json',self.state)
        with self.assertRaises(hm.Failure):self.make(str(os.getuid())+':973')
        self.assertEqual(self.calls,[])


if __name__=='__main__':unittest.main()

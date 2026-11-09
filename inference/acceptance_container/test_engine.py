import copy,json,unittest
from pathlib import Path
from .engine import FixedContainerHTTP,IMAGE
from inference.local_platform.model_management import ModelError
CID='a'*64

def fixture():
    return {'Id':CID,'Name':'/test-engine','Image':IMAGE,'Config':{'Labels':{'aceis.inference.owner':'/tmp/p'},'User':'1000:1000','Env':['OLLAMA_HOST=0.0.0.0:30000','OLLAMA_MODELS=/store','OLLAMA_MAX_LOADED_MODELS=1','OLLAMA_NUM_PARALLEL=1','OLLAMA_NO_CLOUD=1']},'HostConfig':{'Privileged':False,'ReadonlyRootfs':True,'CapDrop':['ALL'],'CapAdd':None,'SecurityOpt':['no-new-privileges:true'],'PortBindings':{},'PidMode':'','IpcMode':'private','RestartPolicy':{'Name':'no'},'GroupAdd':['990'],'Devices':[{'PathOnHost':p,'PathInContainer':p,'CgroupPermissions':'rwm'} for p in ['/dev/kfd','/dev/dri/renderD128']],'DeviceRequests':None,'Memory':32*2**30,'MemorySwap':32*2**30,'NanoCpus':8*10**9,'PidsLimit':512,'NetworkMode':'test_internal','Tmpfs':{'/tmp':'rw,noexec,nosuid,nodev,size=512m'}},'Mounts':[{'Destination':d,'Source':s,'RW':rw} for d,s,rw in [('/weights','/tmp/w',False),('/input','/tmp/p/input',False),('/store','/tmp/p/store',True)]],'NetworkSettings':{'Ports':{},'Networks':{'test_internal':{'IPAddress':'172.30.1.2'}}},'State':{'Running':True}}
class Tests(unittest.TestCase):
    def adapter(self,info=None,cid=CID):
        info=fixture() if info is None else info
        return FixedContainerHTTP(cid,name='test-engine',owner='/tmp/p',provider_root='/tmp/p',weights='/tmp/w',network='test_internal',references=['qwen2.5:0.5b-instruct-q4_K_M'],cli=lambda *a,**k:json.dumps([info]))
    def test_exact_identity_passes(self):self.assertEqual(self.adapter().inspect()['Id'],CID)
    def test_partial_cid_rejected(self):
        with self.assertRaises(ModelError):self.adapter(cid='a'*12)
    def test_identity_network_and_privilege_mismatches(self):
        for path,value in [('Image','sha256:'+'b'*64),('Name','/other'),('HostConfig.Privileged',True),('HostConfig.NetworkMode','bridge'),('HostConfig.GroupAdd',['990','0']),('HostConfig.SecurityOpt',['seccomp=unconfined']),('HostConfig.MemorySwap',64*2**30)]:
            with self.subTest(path=path):
                f=fixture();parts=path.split('.');x=f
                for p in parts[:-1]:x=x[p]
                x[parts[-1]]=value
                with self.assertRaises(ModelError):self.adapter(f).inspect()
    def test_extra_mount_rejected(self):
        f=fixture();f['Mounts'].append({'Destination':'/docker','Source':'/var/run/docker.sock','RW':True})
        with self.assertRaises(ModelError):self.adapter(f).inspect()
    def test_public_port_rejected(self):
        f=fixture();f['HostConfig']['PortBindings']={'30000/tcp':[{'HostIp':'127.0.0.1','HostPort':'30000'}]}
        with self.assertRaises(ModelError):self.adapter(f).inspect()
    def test_wrong_pull_and_any_delete_rejected_before_http(self):
        for method,path,body in [('POST','/api/pull',{'model':'other:latest','stream':False}),('DELETE','/api/delete',{'model':'qwen2.5:0.5b-instruct-q4_K_M'}),('POST','/api/pull',{'model':'qwen2.5:0.5b-instruct-q4_K_M','stream':True})]:
            with self.assertRaises(ModelError):self.adapter()(method,path,body)
    def test_stable_logical_store_scope_survives_cid_recreation(self):
        f=fixture();f['Id']='b'*64
        a=self.adapter();b=self.adapter(f,cid='b'*64)
        self.assertEqual(a.identity,b.identity)
        f['HostConfig']['NetworkMode']='bridge';f['NetworkSettings']['Networks']={'bridge':{'IPAddress':'172.17.0.2'}}
        b=FixedContainerHTTP('b'*64,name='test-engine',owner='/tmp/p',provider_root='/tmp/p',weights='/tmp/w',network='bridge',references=[],cli=lambda *a,**k:json.dumps([f]))
        self.assertEqual(a.identity,b.identity)
if __name__=='__main__':unittest.main()

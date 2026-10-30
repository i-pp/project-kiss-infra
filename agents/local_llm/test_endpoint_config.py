import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import endpoint_config as ec
import local_llm as llm


def fixture(root,candidate=False):
    root=Path(root);root.mkdir(mode=0o700,parents=True,exist_ok=True)
    (root.parent/'model_registry.json').write_text('{"fixture":"registry"}')
    profile={'image':ec.IMAGE,'resident_container_id':'a'*64,'existing_internal_network':ec.NETWORK,'internal_network_id':'c'*64}
    state={'resident_cid':'a'*64,'router_cid':'b'*64,'token':'d'*32,'original_fingerprint':'e'*64,
           'phase':'START_ROUTER_INTENT' if candidate else 'DEPLOYED','route_ipv4':'172.19.0.2','route_subnet':'172.19.0.0/16',
           'route_network_id':'c'*64,'route_endpoint_id':'f'*64}
    receipt={'schema':2,'mode':'router','human_deployment_confirmed':not candidate,'image':ec.IMAGE,
             'container_id':'b'*64,'deployment_token':'d'*32,'network_name':ec.NETWORK,'network_id':'c'*64,
             'subnet':'172.19.0.0/16','ipv4':'172.19.0.2','port':8080,'endpoint_id':'f'*64,
             'registry_sha256':ec.digest(root),'original_fingerprint':'e'*64,'checked_at':12345.,'contract':dict(ec.CONTRACT)}
    for name,data in [('router-host-profile.json',profile),('router-host-state.json',state),
                      ('router-candidate.json' if candidate else 'router-deployment.json',receipt)]:
        ec.atomic_private(root/name,data)
    return receipt


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'llm/.runtime'
        self.receipt=fixture(self.root)
    def tearDown(self):self.temp.cleanup()
    def replace(self,**changes):
        data=copy.deepcopy(self.receipt);data.update(changes);ec.atomic_private(self.root/'router-deployment.json',data)
    def test_verified_exact_route_is_accepted(self):
        self.assertEqual(ec.route(self.root),self.receipt)
    def test_arbitrary_ip_url_dns_ipv6_or_port_is_rejected(self):
        for ip in ['8.8.8.8','127.0.0.1','169.254.1.1','10.0.0.2','172.19.0.3','http://172.19.0.2','model.local','::1','172.19.0.0','172.19.255.255']:
            self.replace(ipv4=ip)
            with self.assertRaises(ec.EndpointError):ec.route(self.root)
        for port in [80,8081,True,'8080']:
            self.replace(port=port)
            with self.assertRaises(ec.EndpointError):ec.route(self.root)
    def test_wrong_identity_registry_or_contract_is_rejected(self):
        for changes in [{'container_id':'9'*64},{'deployment_token':'9'*32},{'image':'wrong'},
                        {'network_id':'9'*64},{'endpoint_id':'9'*64},{'registry_sha256':'9'*64},
                        {'network_name':'bridge'},{'contract':{}},{'original_fingerprint':'9'*64},
                        {'schema':1},{'human_deployment_confirmed':False},{'extra':'http://arbitrary.invalid'}]:
            self.replace(**changes)
            with self.assertRaises(ec.EndpointError):ec.route(self.root)
    def test_subnet_must_be_the_owned_rfc1918_network(self):
        for subnet in ['0.0.0.0/0','172.19.0.0/24','172.19.0.1/16','169.254.0.0/16']:
            self.replace(subnet=subnet)
            with self.assertRaises(ec.EndpointError):ec.route(self.root)
    def test_changed_host_state_or_profile_prevents_contact(self):
        for name,key,value in [('router-host-state.json','phase','ROLLED_BACK'),
                               ('router-host-state.json','route_ipv4','172.19.0.3'),
                               ('router-host-profile.json','internal_network_id','9'*64)]:
            fixture(self.root)
            data=ec.private_json(self.root/name);data[key]=value;ec.atomic_private(self.root/name,data)
            with self.assertRaises(ec.EndpointError):ec.route(self.root)
    def test_missing_active_receipt_never_falls_back_during_deployment(self):
        (self.root/'router-deployment.json').unlink()
        state=ec.private_json(self.root/'router-host-state.json')
        for phase in ec.BLOCKED_PHASES:
            state['phase']=phase;ec.atomic_private(self.root/'router-host-state.json',state)
            with self.assertRaises(ec.EndpointError):ec.route(self.root)
        state['phase']='ROLLED_BACK'
        ec.atomic_private(self.root/'router-host-state.json',state)
        self.assertEqual(ec.route(self.root)['ipv4'],'127.0.0.1')
    def test_candidate_does_not_enable_active_clients(self):
        (self.root/'router-deployment.json').unlink();receipt=fixture(self.root,candidate=True)
        self.assertEqual(ec.route(self.root,candidate=True),receipt)
        with self.assertRaises(ec.EndpointError):ec.route(self.root)
    def test_invalid_metadata_modes_symlink_and_duplicate_keys_are_rejected(self):
        p=self.root/'router-deployment.json';p.chmod(0o644)
        with self.assertRaises(ec.EndpointError):ec.route(self.root)
        p.chmod(0o600);p.unlink();p.symlink_to(self.root/'missing')
        with self.assertRaises((OSError,ec.EndpointError)):ec.route(self.root)
        p.unlink();p.write_text('{"schema":2,"schema":2}');p.chmod(0o600)
        with self.assertRaises(ec.EndpointError):ec.route(self.root)
    def test_route_is_pinned_for_transport_and_cleanup_fork(self):
        with patch.object(llm.http.client,'HTTPConnection') as connection:
            response=Mock(status=200);response.read.return_value=b'{"status":"ok"}'
            connection.return_value.getresponse.return_value=response
            api=llm.HttpApi(runtime=self.root);api.request('GET','/health');fork=api.fork()
            self.replace(checked_at=12346.)
            for client in [api,fork]:
                with self.assertRaises(llm.LocalError) as caught:client.request('POST','/models/load',{})
                self.assertEqual(caught.exception.code,'ENDPOINT_CHANGED')
            connection.assert_called_once_with('172.19.0.2',8080,timeout=5)
    def test_invalid_receipt_never_opens_a_connection(self):
        self.replace(ipv4='172.19.0.3')
        with patch.object(llm.http.client,'HTTPConnection') as connection:
            with self.assertRaises(llm.LocalError):llm.HttpApi(runtime=self.root).request('GET','/health')
            connection.assert_not_called()
    def test_redirect_does_not_expand_private_destination(self):
        with patch.object(llm.http.client,'HTTPConnection') as connection:
            connection.return_value.getresponse.return_value=Mock(status=302)
            with self.assertRaises(llm.LocalError):llm.HttpApi(runtime=self.root).request('GET','/health')
            connection.assert_called_once_with('172.19.0.2',8080,timeout=5)
            connection.return_value.request.assert_called_once()
    def test_legacy_30b_refuses_when_router_has_120b_loaded(self):
        api=llm.HttpApi(runtime=self.root)
        def request(method,path,payload=None,timeout=5):
            self.assertEqual(method,'GET')
            if path=='/health':return {'status':'ok'}
            if path=='/v1/models':return {'data':[{'id':k} for k in llm.MODEL_LIMITS]}
            if path=='/models':return {'data':[{'id':k,'status':{'value':'loaded' if k=='kiss-b3-gpt-oss-120b' else 'unloaded'}} for k in llm.MODEL_LIMITS]}
            raise AssertionError(path)
        api.request=Mock(side_effect=request)
        client=llm.Client(api=api,runtime=self.root,policy_provider=lambda task:{'system':'fixture','metadata':{}},probe=lambda:{})
        with self.assertRaises(llm.LocalError) as caught:client.generate('draft','fixture')
        self.assertEqual(caught.exception.code,'MODEL_NOT_LOADED')
        self.assertTrue(all(c.args[0]=='GET' for c in api.request.call_args_list))


if __name__=='__main__':unittest.main()

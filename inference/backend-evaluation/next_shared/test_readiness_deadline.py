"""CPU fake readiness limits; never start a backend or send HTTP."""
import time
import unittest
from unittest.mock import patch
import host_api_trial as h
import test_host_api_trial as base_tests


class ReadinessDeadlineTests(unittest.TestCase):
    def test_aborted_get_is_known_failure_post_remains_unknown(self):
        for method,path,expected in [('GET','/v1/models',h.Blocked),('POST','/v1/chat/completions',h.Unknown)]:
            with self.subTest(method=method):
                http=h.LocalHTTP();route={'ipv4':'127.0.0.1'};http.bind_route(route,lambda:route);http.abort()
                with patch.object(h.http.client,'HTTPConnection',side_effect=AssertionError('network forbidden')):
                    with self.assertRaises(expected):http.request(method,path)

    def test_deadline_after_connect_get_known_post_unknown_and_no_send(self):
        for method,path,expected in [('GET','/v1/models',h.Blocked),('POST','/v1/chat/completions',h.Unknown)]:
            with self.subTest(method=method):
                http=h.LocalHTTP();route={'ipv4':'127.0.0.1'};http.bind_route(route,lambda:route);http.deadline=time.monotonic()+10
                class Connection:
                    sock=object()
                    def __init__(self,*a,**k):pass
                    def connect(self):http.deadline=time.monotonic()-1
                    def request(self,*a,**k):raise AssertionError('expired operation sent')
                    def close(self):pass
                with patch.object(h.http.client,'HTTPConnection',Connection),self.assertRaises(expected):http.request(method,path)
                self.assertIsNone(http.connection)

    def test_endpoint_change_keeps_unknown_for_get(self):
        http=h.LocalHTTP();http.bind_route({'ipv4':'127.0.0.1'},lambda:{'ipv4':'127.0.0.2'})
        with self.assertRaises(h.Unknown):http.request('GET','/v1/models')

    def test_expired_readonly_get_is_known_failure_without_send(self):
        http=h.LocalHTTP();route={'ipv4':'127.0.0.1'}
        http.bind_route(route,lambda:route);http.deadline=time.monotonic()-1
        with patch.object(h.http.client,'HTTPConnection',side_effect=AssertionError('network forbidden')):
            with self.assertRaises(h.Blocked):http.request('GET','/v1/models')
        self.assertFalse(http.post_intended)

    def test_expired_post_remains_conservatively_unknown(self):
        http=h.LocalHTTP();route={'ipv4':'127.0.0.1'}
        http.bind_route(route,lambda:route);http.deadline=time.monotonic()-1
        with patch.object(h.http.client,'HTTPConnection',side_effect=AssertionError('network forbidden')):
            with self.assertRaises(h.Unknown):http.request('POST','/v1/chat/completions',{})

    def fixture(self):
        base=base_tests.TrialTests();base.setUp();self.addCleanup(base.tearDown)
        return base

    def test_readonly_deadline_cleanup_and_restore_do_not_poison_shared_state(self):
        base=self.fixture();old=base.http.request
        def expired(method,*args,**kwargs):
            if method=='GET':
                base.clock.n=301
                raise h.Blocked('READINESS_DEADLINE_BEFORE_SEND')
            return old(method,*args,**kwargs)
        base.http.request=expired
        trial,result=base.execute()
        self.assertEqual(result['status'],'FAILED')
        self.assertEqual(result['generation_request_intents'],0)
        self.assertTrue(result['cleanup_confirmed'])
        self.assertIn('restore',base.c.events)
        self.assertFalse(any(e.startswith('uncertain:') for e in base.c.events))

    def test_vllm90_and_sglang300_have_distinct_fixed_start_windows(self):
        for backend,expected in [('vllm',90),('sglang',300)]:
            base=self.fixture();old=base.http.request;seen=[]
            def observe(method,*args,**kwargs):
                if method=='GET':seen.append(base.http.deadline-base.clock.now())
                return old(method,*args,**kwargs)
            base.http.request=observe
            _,result=base.execute(backend)
            self.assertEqual(result['status'],'COMPLETED')
            self.assertEqual(seen[0],expected)
        self.assertEqual(h.WHOLE,900)

    def test_sglang_nonzero_swap_is_fresh_baseline_not_absolutezero(self):
        base=self.fixture()
        _,result=base.execute('sglang',probe=lambda:{**base_tests.healthy(),'swap_used':581632})
        self.assertEqual(result['status'],'COMPLETED');self.assertEqual(base.http.posts,1)
        self.assertEqual(result['resources_before']['swap_used'],581632)
        self.assertEqual(result['startup_budget_seconds'],300)
        base=self.fixture()
        def growth():return {**base_tests.healthy(),'swap_used':581632+(4096 if 'start' in base.d.events else 0)}
        _,result=base.execute('sglang',probe=growth)
        self.assertEqual(result['status'],'FAILED');self.assertEqual(base.http.posts,0)
        self.assertIn('restore',base.c.events)


if __name__=='__main__':unittest.main()

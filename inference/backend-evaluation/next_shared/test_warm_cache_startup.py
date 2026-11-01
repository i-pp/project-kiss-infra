from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cached_next_assets as assets
import warm_cache_startup as w
import test_host_api_trial as f
from test_total_swap_trial import Driver, Memory
from test_total_swap_limits import value


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        mask=os.umask(0o077);self.addCleanup(os.umask,mask)
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.record=f.record(self.root);self.model=Path(self.record['model_dir']);self.model.mkdir(parents=True)
        (self.model/'weights').write_bytes(b'original weights')
        spec={'repo':'fixture','revision':'r1','required_files':[{'name':'weights','bytes':16,'sha256':hashlib.sha256(b'original weights').hexdigest()}]}
        p=patch.object(assets,'manifest',return_value=spec);p.start();self.addCleanup(p.stop)
        self.verifier=assets.CachedNextVerifier(self.root/'cache')
        self.verifier(self.model)
        self.clock=f.Clock();self.c=f.Coordinator();self.d=Driver();self.http=f.HTTP()
        self.monitor=w.Monitor32(read=lambda:value(2_000_000_000),clock=self.clock.now,cpu_clock=lambda:0)
        self.run=self.root/'run';self.run.mkdir();self.reserved=[]
    def trial(self,reservation=None):
        with patch.object(w,'OwnedMemoryTelemetry',Memory):
            t=w.WarmCacheTrial(self.record,self.c,self.d,self.http,self.run,f.write,
                lambda _: {'system':'fixture','metadata':{'sha256':'fixture'}},self.monitor,self.verifier,
                reserve_attempt=reservation or (lambda:self.reserved.append(1)),clock=self.clock.now,sleep=self.clock.sleep,
                network_profile={'name':w.h.NETWORK,'id':'c'*64})
        with redirect_stdout(io.StringIO()):result=t.execute()
        return t,result
    def test_actual_trial_cache_hook_and_zero_post_restores(self):
        t,r=self.trial()
        self.assertEqual(r['status'],'COMPLETED',r);self.assertEqual(self.http.posts,0)
        self.assertEqual(r['generation_requests'],0);self.assertTrue(r['cleanup_confirmed'])
        self.assertEqual(self.c.events.count('restore'),1);self.assertIsNone(self.d.row)
        self.assertEqual(len(self.reserved),1)
        report=json.loads((self.run/'startup-measurement.json').read_text())
        self.assertEqual(report['verification']['mode'],'METADATA_CACHE_HIT')
        self.assertEqual(report['verification']['bytes_hashed'],0)
        events=[p['event'] for p in report['phase_marks']]
        self.assertLess(events.index('verification_complete'),events.index('pre_unload_identity_verified'))
        self.assertLess(events.index('pre_load_identity_verified'),events.index('container_start_requested'))
        self.assertLess(events.index('api_ready'),events.index('post_load_identity_verified'))
        self.assertIsNone(report['server_phases']['gpu_initialization_seconds'])
    def test_cold_cache_primes_but_no_lifecycle_or_reservation(self):
        self.verifier.cache=self.root/'cold'
        _,r=self.trial();self.assertEqual(r['status'],'FAILED')
        self.assertIn('CPU_PRIMING',r['reason']);self.assertEqual(self.reserved,[])
        self.assertNotIn('unload',self.c.events);self.assertNotIn('create',self.d.events)
    def test_changed_after_verify_refuses_unload(self):
        original=self.d.image
        def image(ref):
            (self.model/'weights').write_bytes(b'corrupt! weights')
            return original(ref)
        self.d.image=image
        _,r=self.trial();self.assertEqual(r['status'],'FAILED')
        self.assertNotIn('unload',self.c.events);self.assertNotIn('start',self.d.events)
    def test_changed_after_unload_before_start_cleanup_restores(self):
        original=self.d.create
        def create(*args):
            row=original(*args);(self.model/'weights').write_bytes(b'corrupt! weights');return row
        self.d.create=create
        _,r=self.trial();self.assertEqual(r['status'],'FAILED',r)
        self.assertNotIn('start',self.d.events);self.assertTrue(r['cleanup_confirmed'])
        self.assertIn('restore',self.c.events);self.assertEqual(self.http.posts,0)
    def test_changed_during_readiness_refuses_use_and_restores(self):
        original=self.http.request
        def request(method,path,*a,**kw):
            r=original(method,path,*a,**kw)
            if method=='GET':(self.model/'weights').write_bytes(b'corrupt! weights')
            return r
        self.http.request=request
        _,r=self.trial();self.assertEqual(r['status'],'FAILED',r)
        self.assertEqual(self.http.posts,0);self.assertTrue(r['cleanup_confirmed']);self.assertIn('restore',self.c.events)
    def test_unknown_start_not_retried(self):
        self.d.mode='start_unknown';_,r=self.trial()
        self.assertEqual(r['status'],'UNKNOWN');self.assertEqual(self.d.events.count('start'),1)
        self.assertEqual(self.http.posts,0)
    def test_surviving_owned_process_blocks_restore(self):
        self.d.mode='survivor';_,r=self.trial()
        self.assertEqual(r['status'],'UNKNOWN');self.assertFalse(r['cleanup_confirmed'])
        self.assertNotIn('restore',self.c.events);self.assertEqual(self.http.posts,0)
    def test_new_reservation_single_use_preserves_old_marker(self):
        old=self.root/'old-consumed.json';old.write_text('preserve')
        w.reserve_measurement(self.root,self.run)
        with self.assertRaises(FileExistsError):w.reserve_measurement(self.root,self.run)
        self.assertEqual(old.read_text(),'preserve')
    def test_failed_reservation_fsync_prevents_lifecycle(self):
        with patch.object(w.os,'fsync',side_effect=OSError('fsync failure')):
            _,r=self.trial(reservation=lambda:w.reserve_measurement(self.root,self.run))
        self.assertEqual(r['status'],'FAILED',r)
        self.assertNotIn('unload',self.c.events);self.assertNotIn('create',self.d.events)
        self.assertEqual(self.http.posts,0)
    def test_default_inert(self):
        with patch.object(w.h,'operator_record',side_effect=AssertionError('no host')),redirect_stdout(io.StringIO()):
            self.assertEqual(w.main([]),0)
    def test_missing_timing_is_unavailable_not_zero(self):
        result=w.parse_server_phases({})
        self.assertIsNone(result['weights_load_seconds']);self.assertIsNone(result['engine_profile_kv_warmup_seconds'])
    def test_server_timing_overlap_explicit(self):
        result=w.parse_server_phases({'stdout':'Loading weights took 27.56 seconds\ninit engine (profile, create kv cache, warmup model) took 64.49 s','complete_stream':True})
        self.assertEqual(result['weights_load_seconds'],27.56)
        self.assertEqual(result['engine_profile_kv_warmup_seconds'],64.49)
        self.assertIn('overlap',result)


if __name__=='__main__':unittest.main()

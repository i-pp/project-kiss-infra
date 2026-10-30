import hashlib,os,tempfile,unittest
from pathlib import Path
import low_impact_asset_verify as v

class Clock:
    def __init__(self):self.now=0
    def clock(self):return self.now
    def sleep(self,x):self.now+=x

class LowImpactVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.data=b'abc'*(350000);self.path=self.root/'fixed.bin';self.path.write_bytes(self.data);self.clock=Clock();self.hints=[];self.events=[]
        self.manifest={'required_files':[{'name':'fixed.bin','bytes':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}]}
    def run_verify(self,**kwargs):
        return v.verify(self.root,clock=self.clock.clock,sleep=self.clock.sleep,advise=kwargs.pop('advise',lambda *a:self.hints.append(a)),release=kwargs.pop('release','7.0.0-test'),manifest_fn=lambda:self.manifest,report=kwargs.pop('report',self.events.append),**kwargs)
    def test_full_sha_including_non_aligned_tail_bounded_rate_and_only_noreuse(self):
        result=self.run_verify();self.assertEqual(len(result),1);self.assertGreaterEqual(self.clock.now,len(self.data)/v.RATE)
        self.assertEqual([x[-1] for x in self.hints],[os.POSIX_FADV_NOREUSE])
        self.assertEqual(self.events[-1]['bytes_hashed'],len(self.data));self.assertEqual(self.events[-2]['sha256'],hashlib.sha256(self.data).hexdigest())
    def test_all20_files_are_hashed_not_just_shards_or_metadata(self):
        self.path.unlink();rows=[]
        for i in range(20):
            data=str(i).encode();name=f'{i}.fixture';(self.root/name).write_bytes(data);rows.append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        self.manifest={'required_files':rows};self.assertEqual(len(self.run_verify()),20);self.assertEqual(len(self.hints),20)
    def test_digest_mismatch_is_not_accepted_as_identity_match(self):
        self.manifest['required_files'][0]['sha256']='0'*64
        with self.assertRaisesRegex(v.Blocked,'SHA256'):self.run_verify()
    def test_unavailable_or_rejected_hint_is_recorded_without_other_advice(self):
        self.assertEqual(len(self.run_verify(release='6.2.9')),1);self.assertEqual(self.hints,[])
        self.assertTrue(any(e.get('noreuse_status')=='UNAVAILABLE_NO_EFFECT_ASSUMED' for e in self.events))
        attempts=[]
        def reject(*args):attempts.append(args);raise OSError('fixture')
        self.assertEqual(len(self.run_verify(advise=reject)),1);self.assertEqual(len(attempts),1)
        self.assertTrue(any(e.get('noreuse_status','').startswith('REJECTED_') for e in self.events))
    def test_read_that_returns_after_deadline_stops_before_verification_pass(self):
        original=os.read
        def slow(fd,size):
            data=original(fd,size);self.clock.now+=241;return data
        from unittest.mock import patch
        with patch.object(v.os,'read',side_effect=slow),self.assertRaisesRegex(v.Blocked,'240_SECONDS'):self.run_verify()
        self.assertFalse(any(e.get('event')=='all_verified' for e in self.events))
    def test_rate_estimate_cannot_exceed_asset_phase_budget(self):
        self.manifest['required_files'][0]['bytes']=v.RATE*v.BUDGET_SECONDS+1
        with self.assertRaisesRegex(v.Blocked,'ESTIMATE_EXCEEDS'):self.run_verify()
    def test_cancellation_during_pacing_is_not_ignored_or_rebased(self):
        def check():
            if self.clock.now>0:raise v.Blocked('FIXED_HOST_BUDGET_EXCEEDED')
        with self.assertRaisesRegex(v.Blocked,'HOST_BUDGET'):self.run_verify(check=check)
    def test_check_crossing_pacing_target_never_causes_negative_sleep(self):
        calls=[]
        def check():
            calls.append(1)
            if len(calls)==4:self.clock.now+=.5
        def sleep(value):
            self.assertGreater(value,0);self.clock.sleep(value)
        result=v.verify(self.root,check=check,clock=self.clock.clock,sleep=sleep,
                        advise=lambda *a:None,release='7.0.0',manifest_fn=lambda:self.manifest)
        self.assertEqual(len(result),1)
    def test_finite240second_deadline_does_not_restart_for_next_file(self):
        def check():self.clock.now+=120
        with self.assertRaisesRegex(v.Blocked,'240_SECONDS'):self.run_verify(check=check)
        self.assertFalse(any(e.get('event')=='all_verified' for e in self.events))
    def test_path_replacement_during_hash_does_not_pass_old_fd_identity(self):
        def report(row):
            if row['event']=='file_start':
                alternate=self.root/'new';alternate.write_bytes(self.data);os.replace(alternate,self.path)
        with self.assertRaisesRegex(v.Blocked,'CHANGED'):self.run_verify(report=report)
    def test_symlink_and_unreviewed_extra_file_are_rejected(self):
        self.path.rename(self.root/'other');self.path.symlink_to(self.root/'other')
        with self.assertRaises(v.Blocked):self.run_verify()

if __name__=='__main__':unittest.main()

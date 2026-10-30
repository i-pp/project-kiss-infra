import unittest
from resource_review import GIB,lower_bounds,review


class ResourceReviewTests(unittest.TestCase):
    def test_invalid_64gib_gate_is_rejected_against_actual_os_total(self):
        r=review(start_available_min_gib=64)
        self.assertEqual(r['status'],'INFEASIBLE_START_GATE')
        self.assertFalse(r['can_execute'])
    def test_arena_exact_host_and_gpu_allocations_stay_separate(self):
        r=lower_bounds()
        self.assertEqual(r['host_eager_expert_copy_bytes'],33973862400)
        self.assertEqual(r['gpu_expert_cache_bytes'],1415577600)
        self.assertEqual(r['gpu_gdn_recurrent_state_bytes'],117669888)
        self.assertEqual(r['gpu_fp16_kv_payload_lower_bytes'],201326592)
    def test_pack_arrays_are_per_layer_lower_bound_not_peak_upper(self):
        r=lower_bounds()
        self.assertEqual(r['pack_expert_live_arrays_lower_bytes'],2595225600)
        self.assertIsNone(r['pack_total_peak_upper_bytes'])
    def test_mmap_is_not_zero_rss_or_proof_of_fit(self):
        r=review('file_mmap')
        self.assertEqual(r['host_eager_expert_copy_bytes'],0)
        self.assertEqual(r['mmap_virtual_bytes'],33973862400)
        self.assertIsNone(r['mmap_resident_working_set_bytes'])
        self.assertFalse(r['can_execute'])
    def test_fitting_lower_bound_does_not_authorize_run(self):
        for mode in ['arena','file_mmap']:
            r=review(mode)
            self.assertEqual(r['status'],'UNKNOWN_PEAK_NOT_EXECUTION_READY')
            self.assertIsNone(r['host_total_peak_upper_bytes'])
            self.assertIsNone(r['gpu_total_peak_upper_bytes'])
            self.assertFalse(r['can_execute'])
    def test_too_small_os_memory_and_unreviewed_options_fail_closed(self):
        self.assertEqual(review(memtotal_kib=24*1048576)['status'],'INFEASIBLE_KNOWN_HOST_LOWER_BOUND')
        for kwargs in [{'mode':'streaming_magic'},{'context':128},{'cache_slots':0}]:
            with self.assertRaises(ValueError):lower_bounds(**kwargs)


if __name__=='__main__':unittest.main()

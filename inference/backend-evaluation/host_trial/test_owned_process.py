"""Only stdlib fake processes. Does not import or execute Strata/source tools."""
import dataclasses
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

from owned_process import GIB, Identity, Limits, OwnedProcessRunner, OwnedTree, _stat


def healthy():
    return {"mem_available": 40 * GIB, "swap_used": 0, "gpu_used": 2 * GIB, "gtt_used": 0}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, **kw):
        return OwnedProcessRunner(probe=kw.pop("probe", healthy), run_dir=self.root,
                                  poll_interval=.02, **kw)

    def cpu(self, code, **kw):
        return self.runner().run([sys.executable, "-u", "-c", code], str(self.root),
                                 kw.pop("timeout", 2), stop_timeout=.25, **kw)

    def engine(self, code, *, runner=None, **kw):
        return (runner or self.runner()).rawserve([sys.executable, "-u", "-c", code], str(self.root),
                          [7, 8], start_timeout=.8, generation_timeout=.3,
                          stop_timeout=.25, **kw)

    def test_cpu_success_and_nonzero(self):
        good = self.cpu("print('ok')")
        self.assertEqual(good["status"], "COMPLETED")
        self.assertEqual(good["logs"][0]["line"], "ok")
        bad = self.cpu("raise SystemExit(7)")
        self.assertEqual(bad["exit_code"], 7)
        self.assertEqual(bad["reason"], "NONZERO_EXIT")

    def test_timeout_does_not_kill_our_session(self):
        before = _stat(os.getpid())["starttime"]
        r = self.cpu("import time; time.sleep(60)", timeout=.12)
        self.assertEqual(r["reason"], "RUN_TIMEOUT")
        self.assertTrue(r["cleanup"]["complete"])
        self.assertEqual(_stat(os.getpid())["starttime"], before)
        self.assertLess(r["elapsed_seconds"], 2)

    def test_interrupt_returns_cleanup_result_before_parent_restore(self):
        for interrupt in (KeyboardInterrupt, SystemExit):
            with self.subTest(interrupt=interrupt):
                n=[0]
                def probe():
                    n[0]+=1
                    if n[0]==3: raise interrupt()
                    return healthy()
                restore=mock.Mock()
                r=self.runner(probe=probe).run([sys.executable,"-c","import time;time.sleep(60)"],
                                               self.root,1,stop_timeout=.25)
                self.assertEqual(r["reason"],"INTERRUPTED")
                self.assertTrue(r["cleanup"]["complete"])
                if r["cleanup"]["complete"]: restore()
                restore.assert_called_once()

    def test_ready_gen_once_done_and_quit(self):
        r = self.engine("""import sys
print('diagnostic', file=sys.stderr)
print('READY 8192 stop')
line=sys.stdin.readline()
assert line=='GEN 128 temperature=0 seed=42 ckpt=0 7,8\\n',repr(line)
print('PP 2 2 1.0 2000')
print('T 99')
print('DONE 1 2 1.5 2.0 stop 0 0 chunk=512')
assert sys.stdin.readline()=='QUIT\\n'
""")
        self.assertEqual(r["status"], "COMPLETED", r)
        self.assertEqual(r["generation_requests"], 1)
        self.assertEqual(r["token_ids"], [99])
        self.assertEqual(r["done"]["finish"], "stop")
        self.assertEqual(r["cleanup"]["actions"], ["QUIT"])

    def test_large_stderr_drained_while_stdout_protocol_runs(self):
        r = self.engine("""import sys
for _ in range(50): sys.stderr.write('a'*1000+'\\n')
sys.stderr.flush()
print('READY 8192 stop')
sys.stdin.readline()
print('T 1')
print('DONE 1 2 1 1 length 0 0')
sys.stdin.readline()
""")
        self.assertEqual(r["status"], "COMPLETED", r["reason"])
        self.assertEqual(r["done"]["finish"], "length")

    def test_oversized_line_aborts_without_deadlock(self):
        r = self.cpu("import sys,time; sys.stdout.write('a'*100000); sys.stdout.flush(); time.sleep(60)")
        self.assertEqual(r["reason"], "LINE_LIMIT")
        self.assertTrue(r["cleanup"]["complete"])

    def test_flood_output_is_bounded(self):
        limits = dataclasses.replace(Limits(), log_bytes=4096)
        r = self.runner(limits=limits).run([sys.executable, "-u", "-c",
            "import os; [os.write(1,b'x'*100+b'\\n') for _ in range(20000)]"],
            str(self.root), 2, stop_timeout=.25)
        self.assertIn(r["reason"], {"OUTPUT_LIMIT", "OUTPUT_BACKPRESSURE"})
        self.assertLessEqual(sum(len(x["line"].encode())+1 for x in r["logs"]), 4096)
        self.assertTrue(r["cleanup"]["complete"])

    def test_start_gate_blocks_spawn(self):
        probe = lambda: {**healthy(), "mem_available": 23 * GIB}
        with mock.patch("owned_process.subprocess.Popen") as spawn:
            r = self.runner(probe=probe).run(["not-executed"], self.root, .1)
        spawn.assert_not_called()
        self.assertEqual(r["reason"], "START_RAM_FLOOR")

    def test_runtime_ram_gpu_swap_and_rss_abort(self):
        for field, value, reason in (("mem_available", 16*GIB, "RAM_FLOOR"),
                                     ("gpu_used", 59*GIB, "GPU_LIMIT"),
                                     ("swap_used", 1, "SWAP_GROWTH")):
            with self.subTest(field=field):
                calls = [0]
                def probe():
                    calls[0] += 1
                    return {**healthy(), **({field: value} if calls[0] > 2 else {})}
                r = self.runner(probe=probe).run([sys.executable,"-c","import time;time.sleep(60)"],
                                              self.root, 1, stop_timeout=.25)
                self.assertEqual(r["reason"], reason)
                self.assertTrue(r["cleanup"]["complete"])
        r = self.runner(limits=dataclasses.replace(Limits(), max_rss_bytes=1)).run(
            [sys.executable,"-c","import time;time.sleep(60)"], self.root, 1, stop_timeout=.25)
        self.assertEqual(r["reason"], "RSS_SOFT_LIMIT")

    def test_disk_growth_abort(self):
        limits = dataclasses.replace(Limits(), max_disk_growth_bytes=100)
        r = self.runner(limits=limits).run([sys.executable,"-c",
             "import pathlib,time;pathlib.Path('new').write_bytes(b'x'*200);time.sleep(60)"],
             self.root, 1, stop_timeout=.25)
        self.assertEqual(r["reason"], "DISK_GROWTH")

    def test_disk_budget_carries_across_stages(self):
        runner = self.runner(limits=dataclasses.replace(Limits(), max_disk_growth_bytes=150))
        first = runner.run([sys.executable,"-c","from pathlib import Path;Path('a').write_bytes(b'x'*100)"],
                           self.root,1,stop_timeout=.25)
        self.assertEqual(first["status"], "COMPLETED")
        second = runner.run([sys.executable,"-c",
            "from pathlib import Path;import time;Path('b').write_bytes(b'x'*100);time.sleep(60)"],
            self.root,1,stop_timeout=.25)
        self.assertEqual(second["reason"], "DISK_GROWTH")

    def test_missing_gpu_probe_fails_closed(self):
        r = self.runner(probe=lambda: {**healthy(), "gpu_used":None}).run(["unused"], self.root, 1)
        self.assertEqual(r["reason"], "RESOURCE_PROBE_UNAVAILABLE")
        r = self.runner(probe=lambda: {**healthy(), "gpu_used":float('nan')}).run(["unused"], self.root, 1)
        self.assertEqual(r["reason"], "RESOURCE_PROBE_UNAVAILABLE")

    def test_bad_ready_sends_no_generation(self):
        r = self.engine("import time;print('READY 4096 stop');time.sleep(60)")
        self.assertEqual(r["reason"], "BAD_READY")
        self.assertEqual(r["generation_requests"], 0)

    def test_missing_startup_marker_prevents_generation(self):
        r = self.engine("import time;print('READY 8192 stop');time.sleep(60)",
                        required_startup_marker="experts via mmap (--mmap-experts;")
        self.assertEqual(r["reason"], "STARTUP_CONTRACT_MISSING")
        self.assertEqual(r["generation_requests"], 0)

    def test_marker_after_ready_is_safe_across_separate_streams(self):
        r = self.engine("""import sys,time
print('READY 8192 stop')
time.sleep(.03)
print('strata generate: experts via mmap (--mmap-experts; the A/B arm of R2.1)',file=sys.stderr)
assert sys.stdin.readline().startswith('GEN 128 ')
print('T 8')
print('DONE 1 2 1 1 stop')
sys.stdin.readline()
""", required_startup_marker="experts via mmap (--mmap-experts;")
        self.assertEqual(r["status"], "COMPLETED",r["reason"])
        self.assertTrue(r["startup_marker_confirmed"])
        self.assertEqual(r["generation_requests"],1)

    def test_generation_timeout_stop_then_quit_no_resend(self):
        r = self.engine("""import sys,time
print('READY 8192 stop')
assert sys.stdin.readline().startswith('GEN 128 ')
assert sys.stdin.readline()=='STOP\\n'
assert sys.stdin.readline()=='QUIT\\n'
""")
        self.assertEqual(r["reason"], "GENERATION_TIMEOUT")
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertEqual(r["generation_requests"], 1)
        self.assertEqual(r["cleanup"]["actions"][:2], ["STOP", "QUIT"])

    def test_engine_not_reading_large_gen_cannot_block_writer_forever(self):
        r = self.runner().rawserve([sys.executable,"-u","-c",
              "import time;print('READY 8192 stop');time.sleep(60)"], self.root,
              [12345]*7000, start_timeout=.5,generation_timeout=.3,stop_timeout=.25)
        self.assertEqual(r["status"],"UNKNOWN")
        self.assertIn(r["reason"],{"SUBMISSION_UNCERTAIN","GENERATION_TIMEOUT"})
        self.assertTrue(r["cleanup"]["complete"])
        self.assertLess(r["elapsed_seconds"],2)

    def test_early_exit_after_gen_unknown(self):
        r = self.engine("import sys;print('READY 8192 stop');sys.stdin.readline()")
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertEqual(r["generation_requests"], 1)

    def test_invalid_done_and_nonfinite(self):
        for done, expected in (("DONE 2 2 1 1 stop", "BAD_DONE"),
                               ("DONE 1 2 nan 1 stop", "BAD_DONE"),
                               ("DONE 1 2 1 1 nonfinite", "NONFINITE")):
            with self.subTest(done=done):
                r = self.engine("import sys;print('READY 8192 stop');sys.stdin.readline();print('T 2');"
                                f"print({done!r});sys.stdin.readline()")
                self.assertEqual(r["reason"], expected)

    def test_term_ignoring_child_is_killed_with_parent(self):
        code = """import subprocess,sys,time
p=subprocess.Popen([sys.executable,'-u','-c',
 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'])
print(p.pid,flush=True)
time.sleep(60)
"""
        r = self.cpu(code, timeout=.25)
        self.assertTrue(r["cleanup"]["complete"], r)
        child = int(next(x["line"] for x in r["logs"] if x["stream"]=="stdout"))
        stat = _stat(child)
        self.assertTrue(stat is None or stat["state"] == "Z")
        self.assertTrue(any(isinstance(a,dict) and "KILL" in a for a in r["cleanup"]["actions"]))

    def test_signal_rejects_pid_reuse_and_ancestors(self):
        tree = OwnedTree(os.getpid())
        tree.known[999999] = 12
        with mock.patch("owned_process._stat", return_value={"starttime":13,"state":"S"}), \
             mock.patch.object(tree,"refresh",return_value=[]), \
             mock.patch("owned_process.signal.pidfd_send_signal") as send:
            self.assertEqual(tree.signal(signal.SIGTERM), [])
            send.assert_not_called()

    def test_no_new_session_requested(self):
        real = __import__('subprocess').Popen
        with mock.patch("owned_process.subprocess.Popen", wraps=real) as spawn:
            self.cpu("pass")
        self.assertFalse(spawn.call_args.kwargs["start_new_session"])

    def test_validation_rejects_token_and_output_scope(self):
        for ids, cap in (([],128),([1],129),([-1],128),([True],128),([1]*8190,128)):
            with self.assertRaises(ValueError):
                self.runner().rawserve(["unused"],self.root,ids,max_tokens=cap)


if __name__ == '__main__':
    unittest.main()

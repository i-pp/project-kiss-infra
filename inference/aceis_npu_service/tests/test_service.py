import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from inference.aceis_npu_service import service
from inference.aceis_npu_service.verify_trace import verify


class InputTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(len(service.validate_input({"input": [0.0] * 3072})), 3072)

    def test_float32_normalization(self):
        values = service.validate_input({"input": [1e-100, 1.401298464324817e-45, 3.4028234663852886e38] + [0] * 3069})
        self.assertEqual(values[0], 0)
        self.assertGreater(values[1], 0)
        self.assertEqual(values[2], 3.4028234663852886e38)

    def test_invalid(self):
        for value in (None, [], {"input": []}, {"input": [True] * 3072},
                      {"input": [float("nan")] * 3072}, {"input": [float("inf")] * 3072},
                      {"input": [1e39] * 3072}, {"input": [10**1000] * 3072},
                      {"input": [0] * 3072, "extra": 1}, {"input": [0] * 3072, "model": "other"}):
            with self.subTest(value_type=type(value)), self.assertRaises(ValueError):
                service.validate_input(value)

    def test_profile_requires_real_provider_events(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "profile.json"
            for events in ([], [{"cat": "Node", "args": {"provider": "CPUExecutionProvider"}}],
                           [{"cat": "Node", "args": {"provider": p}} for p in ("VitisAIExecutionProvider", "CPUExecutionProvider")]):
                p.write_text(json.dumps(events))
                with self.assertRaises(ValueError):
                    service.profile_evidence(p, "VitisAI")
            p.write_text(json.dumps([{"cat": "Node", "args": {"provider": "VitisAIExecutionProvider"}}]))
            self.assertTrue(service.profile_evidence(p, "VitisAI")["execution_verified"])

    def test_trace_requires_successful_accel_commands_and_waits(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "trace"
            for text in ("", "ioctl(6</dev/accel/accel0>, DRM_IOCTL_AMDXDNA_EXEC_CMD, 0) = -1 EPERM\n",
                         "ioctl(6</dev/null>, DRM_IOCTL_AMDXDNA_EXEC_CMD, 0) = 0\n",
                         "ioctl(6</dev/accel/accel01>, DRM_IOCTL_AMDXDNA_EXEC_CMD, 0) = 0\n"
                         "ioctl(6</dev/accel/accel01>, DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT, 0) = 0\n") :
                p.write_text(text)
                with self.assertRaises(ValueError):
                    verify(p)
            p.write_text("1 ioctl(6</dev/accel/accel0<char 261:0>>, DRM_IOCTL_AMDXDNA_EXEC_CMD, 0x123) = 0\n"
                         "1 ioctl(6</dev/accel/accel0<char 261:0>>, DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT, 0x456) = 0\n")
            self.assertEqual(verify(p)["successful_exec_commands"], 1)


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=2)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class FakeWorker:
    status = "ready"
    error = None

    def health(self):
        return {"status": self.status, "execution_target": "cpu"}

    def classify(self, _):
        if self.error:
            raise self.error
        return {"logits": [0] * 10, "class_index": 0}


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.path = self.directory / "service.sock"
        self.worker = FakeWorker()
        self.server = service.serve(self.worker, self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, value=None, headers=None):
        conn = UnixConnection(str(self.path))
        data = None if value is None else json.dumps(value)
        conn.request(method, path, body=data, headers=headers or {})
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_socket_private(self):
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(self.request("GET", "/health")[0], 200)

    def test_not_ready(self):
        self.worker.status = "not_ready"
        self.assertEqual(self.request("GET", "/health")[0], 503)

    def test_origin_rejected(self):
        self.assertEqual(self.request("GET", "/health", headers={"Origin": "https://example.test"})[0], 403)
        self.assertEqual(self.request("POST", "/v1/classify", headers={"Origin": "null"})[0], 403)

    def test_classify(self):
        self.assertEqual(self.request("POST", "/v1/classify", {"input": [0] * 3072}, {"Content-Type": "application/json"})[0], 200)

    def test_invalid_body(self):
        self.assertEqual(self.request("POST", "/v1/classify", {"input": []}, {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/v1/classify", {}, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/v1/classify", {}, {"Content-Length": "100001"})[0], 413)

    def test_busy_and_unavailable(self):
        for error, code in ((BlockingIOError(), 429), (RuntimeError("private error"), 503)):
            self.worker.error = error
            status, body = self.request("POST", "/v1/classify", {"input": [0] * 3072}, {"Content-Type": "application/json"})
            self.assertEqual(status, code)
            self.assertNotIn("private", json.dumps(body))

    def test_existing_socket_not_removed(self):
        with self.assertRaises(OSError):
            service.serve(self.worker, self.path)
        self.assertTrue(self.path.exists())

    def test_public_parent_refused(self):
        d = self.directory / "public"
        d.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            service.serve(self.worker, d / "socket")


class WorkerTests(unittest.TestCase):
    def test_early_exit_with_term_ignoring_descendant(self):
        for hold_stdout in (True, False):
            with self.subTest(hold_stdout=hold_stdout), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                model = root / "model"; model.write_bytes(b"fixture")
                child = root / "descendant.py"
                child.write_text("import os,signal,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\n" +
                                 ("" if hold_stdout else "os.close(1)\n") +
                                 f"open({str(root / 'child.ready')!r},'w').write('ready')\n" + "time.sleep(60)\n")
                executable = root / "fake"
                executable.write_text("#!/usr/bin/python3\nimport json,sys,subprocess,os,time\n" +
                    f"child=subprocess.Popen(['/usr/bin/python3',{str(child)!r}])\n" +
                    f"open({str(root / 'child.pid')!r},'w').write(str(child.pid))\n" +
                    f"deadline=time.monotonic()+2\nwhile not os.path.exists({str(root / 'child.ready')!r}):\n if time.monotonic()>deadline: raise RuntimeError('child not ready')\n time.sleep(.001)\np=sys.argv[3]+'.json'\n" +
                    "open(p,'w').write(json.dumps([{'cat':'Node','args':{'provider':'CPUExecutionProvider'}}]))\n" +
                    "print('ACEIS_JSON '+json.dumps({'profile':p,'ort_version':'fixture'}),flush=True)\nos._exit(0)\n")
                executable.chmod(0o700)
                run = root / "run"; run.mkdir()
                with patch.object(service, "MODEL_SHA256", hashlib.sha256(b"fixture").hexdigest()):
                    w = service.Worker(executable, root, root, model, run, "CPU")
                try:
                    time.sleep(.05)
                    self.assertEqual(w.health()["status"], "not_ready")
                    begin = time.monotonic(); w.close()
                    self.assertLess(time.monotonic() - begin, 5.5)
                    pid = int((root / 'child.pid').read_text())
                    time.sleep(.05)
                    status = Path(f"/proc/{pid}/status")
                    if status.exists():
                        self.assertIn("State:\tZ", status.read_text())
                finally:
                    w.close()

    def test_worker_not_reading_stdin_obeys_deadline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "model"; model.write_bytes(b"fixture")
            executable = root / "fake"
            executable.write_text("#!/usr/bin/python3\nimport json,sys,time\np=sys.argv[3]+'.json'\n" +
                "open(p,'w').write(json.dumps([{'cat':'Node','args':{'provider':'CPUExecutionProvider'}}]))\n" +
                "print('ACEIS_JSON '+json.dumps({'profile':p,'ort_version':'fixture'}),flush=True)\ntime.sleep(60)\n")
            executable.chmod(0o700)
            run = root / "run"; run.mkdir()
            with patch.object(service, "MODEL_SHA256", hashlib.sha256(b"fixture").hexdigest()):
                w = service.Worker(executable, root, root, model, run, "CPU", timeout=.05)
            try:
                begin = time.monotonic()
                with self.assertRaises(RuntimeError): w.classify([.123456789] * 3072)
                self.assertLess(time.monotonic() - begin, 4.5)
                self.assertEqual(w.health()["status"], "not_ready")
            finally:
                w.close()

    def test_persistent_child_and_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "model"; model.write_bytes(b"fixture")
            executable = root / "fake"
            executable.write_text('''#!/usr/bin/python3
import json,sys,time,os
assert "SECRET_FIXTURE" not in os.environ
p=sys.argv[3]+".json"
open(p,"w").write(json.dumps([{"cat":"Node","args":{"provider":"CPUExecutionProvider"}}]))
print("ACEIS_JSON "+json.dumps({"ready":True,"profile":p,"ort_version":"fixture"}),flush=True)
for line in sys.stdin:
 if line.startswith("1 "): time.sleep(2)
 print('ACEIS_JSON {"logits":[0,0,0,0,0,0,0,0,0,0],"class_index":0,"latency_ms":1}',flush=True)
''')
            executable.chmod(0o700)
            run = root / "run"; run.mkdir()
            with patch.object(service, "MODEL_SHA256", hashlib.sha256(b"fixture").hexdigest()), patch.dict(os.environ, {"SECRET_FIXTURE": "not_forwarded"}):
                w = service.Worker(executable, root, root, model, run, "CPU", timeout=0.05)
            try:
                pid = w.process.pid
                for _ in range(2):
                    self.assertEqual(w.classify([0] * 3072)["class_index"], 0)
                    self.assertEqual(w.process.pid, pid)
                self.assertTrue(w.lock.acquire(False))
                with self.assertRaises(BlockingIOError): w.classify([0] * 3072)
                w.lock.release()
                with self.assertRaises(RuntimeError): w.classify([1] * 3072)
                self.assertEqual(w.health()["status"], "not_ready")
                self.assertIsNotNone(w.process.poll())
            finally:
                w.close()


if __name__ == "__main__":
    unittest.main()

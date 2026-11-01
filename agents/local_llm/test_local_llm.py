import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

import local_llm as llm
import extension


SAFE = {"available_bytes": 40 * llm.GIB, "gpu_used_bytes": 21 * llm.GIB, "swap_used_bytes": 0}


def fixture_policy(task):
    return {'system': 'FULL VERIFIED FIXTURE POLICY\n'+llm.SYSTEM[task],
            'metadata': {'version': 'fixture-1', 'sha256': 'fixture-sha', 'source': 'fixture'}}


class FakeApi:
    def __init__(self, fail=False, wait=False):
        self.calls, self.posts = [], 0
        self.fail, self.wait = fail, wait
        self.aborted = threading.Event()
        self.context = 32768
        self.alias = llm.MODEL

    def request(self, method, path, payload=None, timeout=5):
        self.calls.append((method, path, payload))
        path = path.split("?", 1)[0]
        if path == "/health": return {"status": "ok"}
        if path == "/v1/models": return {"data": [{"id": llm.MODEL}]}
        if path == "/props": return {"model_alias": self.alias, "total_slots": 1,
                                     "default_generation_settings": {"n_ctx": self.context}}
        self.posts += 1
        if self.wait:
            self.aborted.wait(1)
            raise llm.LocalError("TRANSPORT_ERROR", "cancelled")
        if self.fail: raise llm.LocalError("TRANSPORT_ERROR", "fixture failure")
        return {"model": llm.MODEL, "choices": [{"message": {"content": "advice only",
                    "reasoning_content": "private fixture reasoning"}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 3}}

    def abort(self):
        self.aborted.set()


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp.name) / "state"
        self.api = FakeApi()
        self.client = llm.Client(self.api, lambda: dict(SAFE), self.runtime, monitor_interval=.01,
                                 policy_provider=fixture_policy)

    def tearDown(self): self.temp.cleanup()

    def test_advice_remains_unverified_and_reasoning_is_not_exported(self):
        result = self.client.generate("review", "Review this explicit source")
        self.assertEqual(result["verification_status"], "NOT_EXECUTED")
        self.assertTrue(result["untrusted_advisory"])
        self.assertFalse(result["code_executed"])
        self.assertNotIn("private fixture reasoning", json.dumps(result))
        self.assertEqual(self.api.posts, 1)
        payload = self.api.calls[-1][2]
        self.assertEqual(payload["model"], llm.MODEL)
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["seed"], 42)
        self.assertIn('FULL VERIFIED FIXTURE POLICY', payload['messages'][0]['content'])
        self.assertTrue(result['policy_attached'])

    def test_invalid_requests_never_reach_backend(self):
        for task, prompt, tokens in [("shell", "x", 32), ("draft", "", 32),
                                    ("draft", "x" * 16385, 32), ("draft", "x", True),
                                    ("draft", "x", 1025)]:
            with self.assertRaises(llm.LocalError): self.client.generate(task, prompt, tokens)
        self.assertEqual(self.api.calls, [])

    def test_changed_model_or_context_prevents_inference(self):
        self.api.context = 8192
        with self.assertRaises(llm.LocalError): self.client.generate("draft", "x")
        self.assertEqual(self.api.posts, 0)
        self.api.context = 32768; self.api.alias = "other-model"
        with self.assertRaises(llm.LocalError): self.client.generate("draft", "x")
        self.assertEqual(self.api.posts, 0)

    def test_resource_preflight_refuses_without_post(self):
        for values in [{**SAFE, "available_bytes": 23 * llm.GIB},
                       {**SAFE, "gpu_used_bytes": 59 * llm.GIB}]:
            self.client.probe = lambda: values
            with self.assertRaises(llm.LocalError): self.client.generate("draft", "x")
        self.assertEqual(self.api.posts, 0)

    def test_parallel_clients_are_serialized_without_forcing_lock(self):
        with self.client.locked():
            other = llm.Client(self.api, lambda: SAFE, self.runtime)
            with self.assertRaisesRegex(llm.LocalError, "Another advisory request"):
                other.generate("draft", "x")
        self.assertEqual(self.api.posts, 0)

    def test_runtime_and_lock_symlinks_are_refused(self):
        target = Path(self.temp.name) / "target"; target.mkdir(mode=0o700)
        self.runtime.symlink_to(target)
        with self.assertRaises(llm.LocalError): self.client.generate("draft", "x")
        self.runtime.unlink(); self.runtime.mkdir(mode=0o700)
        (self.runtime / "generation.lock").symlink_to(target / "outside")
        with self.assertRaises(OSError): self.client.generate("draft", "x")
        self.assertFalse((target / "outside").exists())

    def test_transport_failure_blocks_blind_retry_without_prompt_logging(self):
        self.api.fail = True
        with self.assertRaises(llm.LocalError): self.client.generate("draft", "private prompt fixture")
        marker = (self.runtime / "UNCERTAIN.json").read_text()
        self.assertNotIn("private prompt", marker)
        with self.assertRaises(llm.LocalError): self.client.generate("draft", "x")
        self.assertEqual(self.api.posts, 1)

    def test_runtime_pressure_aborts_own_connection_and_does_not_retry(self):
        self.api.wait = True
        samples = iter([SAFE, *[{**SAFE, "available_bytes": 15 * llm.GIB}] * 3])
        self.client.probe = lambda: next(samples)
        with self.assertRaisesRegex(llm.LocalError, "three samples"):
            self.client.generate("draft", "x")
        self.assertTrue(self.api.aborted.is_set())
        self.assertEqual(self.api.posts, 1)
        self.assertTrue((self.runtime / "UNCERTAIN.json").exists())

    def test_deadline_aborts_without_another_generation(self):
        self.api.wait = True
        with patch.object(llm, "TIMEOUT_SECONDS", .03):
            with self.assertRaisesRegex(llm.LocalError, "deadline"):
                self.client.generate("draft", "x")
        self.assertEqual(self.api.posts, 1)
        self.assertTrue(self.api.aborted.is_set())

    def test_tool_rejects_arbitrary_endpoint_and_file_arguments(self):
        for extra in [{"base_url": "https://example.invalid"}, {"file": "/etc/passwd"},
                      {"model": "other-model"}]:
            result = extension.dispatch(extension.NAME, {"task": "review", "prompt": "x", **extra}, self.client)
            self.assertTrue(result["isError"])
        self.assertEqual(self.api.posts, 0)

    def test_tool_handler_preserves_unverified_label(self):
        result = extension.dispatch(extension.NAME, {"task": "draft", "prompt": "x"}, self.client)
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["verification_status"], "NOT_EXECUTED")
        self.assertFalse(extension.definition()["annotations"]["readOnlyHint"])

    def test_policy_failure_prevents_any_backend_contact(self):
        def bad_policy(task):
            raise llm.LocalError('POLICY_UNAVAILABLE', 'fixture policy conflict')
        self.client.policy_provider = bad_policy
        with self.assertRaisesRegex(llm.LocalError, 'policy conflict'):
            self.client.generate('draft', 'x')
        self.assertEqual(self.api.calls, [])

    def test_policy_body_is_counted_in_context_budget(self):
        self.client.policy_provider = lambda task: {'system': 'p' * 32768, 'metadata': {}}
        with self.assertRaisesRegex(llm.LocalError, 'context budget'):
            self.client.generate('draft', 'x')
        self.assertEqual(self.api.posts, 0)

    def test_preflight_consumes_the_same_operation_deadline(self):
        original = self.api.request
        def delayed(method, path, payload=None, timeout=5):
            if path == '/health':
                import time
                time.sleep(.02)
            return original(method, path, payload, timeout)
        self.api.request = delayed
        with patch.object(llm, 'TIMEOUT_SECONDS', .01):
            with self.assertRaisesRegex(llm.LocalError, 'deadline'):
                self.client.generate('draft', 'x')
        self.assertEqual(self.api.posts, 0)


class TransportTests(unittest.TestCase):
    @patch.object(llm.http.client, "HTTPConnection")
    def test_fixed_loopback_no_proxy_or_authorization(self, connection):
        response = Mock(status=200); response.read.return_value = b'{"status":"ok"}'
        connection.return_value.getresponse.return_value = response
        # This test covers resident routing, independently of live router receipts.
        with tempfile.TemporaryDirectory() as runtime, patch.dict(os.environ, {"HTTP_PROXY": "http://unapproved.invalid", "OPENAI_API_KEY": "fixture"}):
            self.assertEqual(llm.HttpApi(runtime=Path(runtime)).request("GET", "/health"), {"status": "ok"})
        connection.assert_called_once_with("127.0.0.1", 8080, timeout=5)
        headers = connection.return_value.request.call_args.args[3]
        self.assertNotIn("Authorization", headers)

    @patch.object(llm.http.client, "HTTPConnection")
    def test_redirect_is_not_followed(self, connection):
        connection.return_value.getresponse.return_value = Mock(status=302)
        with self.assertRaises(llm.LocalError): llm.HttpApi().request("GET", "/health")
        connection.return_value.request.assert_called_once()

    @patch.object(llm.http.client, "HTTPConnection")
    def test_response_size_is_bounded(self, connection):
        response = Mock(status=200); response.read.return_value = b'x' * (llm.MAX_RESPONSE_BYTES + 1)
        connection.return_value.getresponse.return_value = response
        with self.assertRaisesRegex(llm.LocalError, "exceeded"):
            llm.HttpApi().request("GET", "/props")


class CommandProtocolTests(unittest.TestCase):
    def test_schema_output_is_not_a_service_registration(self):
        result = subprocess.run([sys.executable, '-B', str(Path(extension.__file__))],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['name'], extension.NAME)

    def test_invalid_tool_frame_is_rejected_without_inference(self):
        result = subprocess.run([sys.executable, '-B', str(Path(extension.__file__)), '--call'],
                                input=json.dumps({'name': 'not-enabled', 'arguments': {}}),
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['structuredContent']['error'], 'INVALID_INPUT')


if __name__ == "__main__": unittest.main()

import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from .cli import ask, checked_socket, ClientError

JOB='a'*32

class TestCLI(unittest.TestCase):
    def test_ask_submits_once_and_only_polls(self):
        calls=[]
        def call(path,method,route,body=None):
            calls.append((method,route,body))
            if method=='POST':return {'id':JOB,'status':'queued'}
            return {'id':JOB,'model':'gpt-oss-120b','status':'completed',
                    'result':{'content':'advice','thinking':'not exported','finish_reason':'length','completion_tokens':10}}
        out=ask('/unused','gpt-oss-120b','fixture',call=call)
        self.assertEqual([c[0] for c in calls],['POST','GET'])
        self.assertFalse(out['code_executed']);self.assertNotIn('thinking',out)
    def test_submit_timeout_never_retries(self):
        calls=[]
        def call(*args):calls.append(args);raise TimeoutError()
        with self.assertRaises(ClientError):ask('/unused','gpt-oss-120b','fixture',call=call)
        self.assertEqual(len(calls),1)
    def test_invalid_submit_response_never_retries(self):
        calls=[]
        def call(*args):calls.append(args);raise ValueError('invalid JSON')
        with self.assertRaises(ClientError):ask('/unused','gpt-oss-120b','fixture',call=call)
        self.assertEqual(len(calls),1)
    def test_cancel_preserves_id_and_calls_delete_once(self):
        from .cli import ClientCancelled
        calls=[]
        def call(path,method,route,body=None):
            calls.append(method)
            if method=='POST':return {'id':JOB}
            if method=='GET':raise KeyboardInterrupt()
            return {'status':'cancellation_requested'}
        with self.assertRaises(ClientCancelled) as caught:
            ask('/unused','gpt-oss-120b','fixture',call=call)
        self.assertEqual(caught.exception.job_id,JOB)
        self.assertEqual(calls,['POST','GET','DELETE'])
    def test_bad_input_does_not_submit(self):
        for args in [('other','x',512,180),('flash','x'*8193,512,180),('flash','x',True,180),('flash','x',512,301)]:
            with patch('inference.local_platform.cli.request') as call:
                with self.assertRaises(ClientError):ask('/unused',*args)
                call.assert_not_called()
    def test_job_identity_is_fixed(self):
        def call(path,method,route,body=None):
            return {'id':JOB} if method=='POST' else {'id':'b'*32,'model':'gpt-oss-120b','status':'completed'}
        with self.assertRaises(ClientError):ask('/unused','gpt-oss-120b','fixture',call=call)
    def test_private_socket_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'service.sock';s=socket.socket(socket.AF_UNIX);s.bind(str(p));p.chmod(0o600)
            try:
                self.assertEqual(checked_socket(p),p)
                p.chmod(0o666)
                with self.assertRaises(ClientError):checked_socket(p)
            finally:s.close()


class TestKnownOutcome(unittest.TestCase):
    def test_poll_error_preserves_received_job_identifier(self):
        def call(path,method,route,body=None):
            if method=='POST':return {'id':JOB}
            raise TimeoutError()
        with self.assertRaises(ClientError) as caught:
            ask('/unused','gpt-oss-120b','fixture',call=call)
        self.assertEqual(caught.exception.job_id,JOB)


class TestEncodingSafety(unittest.TestCase):
    def test_encoding_cookie_cannot_change_executed_source(self):
        import ast, json, tokenize, io
        from .bounded_patch import validated_replacement
        code='def add(a, b):\n    return a + b\n'
        proposed='# coding: unicode_escape\n# '+chr(92)+'u000aimport os\n'+code
        actual,_=validated_replacement(json.dumps({'replacement':proposed,'explanation':'fixture'}),code)
        encoding,_=tokenize.detect_encoding(io.BytesIO(actual.encode('utf-8')).readline)
        parsed=ast.parse(actual.encode('utf-8').decode(encoding))
        self.assertEqual([type(n).__name__ for n in parsed.body],['FunctionDef'])
        self.assertNotIn('coding:',actual)

if __name__=='__main__':unittest.main()

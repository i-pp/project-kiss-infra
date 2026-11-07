"""Explicit local client for AceIS callers; no fallback or arbitrary URL."""
import argparse
import json
import os
from pathlib import Path
from .server import UnixHTTPConnection


def request(socket_path, method, path, body=None, timeout=310):
    conn = UnixHTTPConnection(socket_path, timeout=timeout)
    try:
        raw = None if body is None else json.dumps(body).encode()
        conn.request(method, path, raw, {'Content-Type':'application/json'})
        response = conn.getresponse()
        payload = response.read(2 * 1024**2 + 1)
        if len(payload) > 2 * 1024**2:
            raise RuntimeError('response too large')
        result = json.loads(payload)
        if response.status >= 400:
            raise RuntimeError(result.get('error') or result.get('fault') or 'service not ready')
        return result
    finally:
        conn.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--socket', default=str(Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid()))) / 'aceis-inference/service.sock'))
    p.add_argument('--health', action='store_true')
    p.add_argument('--model',choices=['flash','coder-next','gpt-oss-120b'])
    p.add_argument('--prompt')
    p.add_argument('--max-tokens',type=int,default=256)
    a=p.parse_args()
    if a.health:
        out=request(a.socket,'GET','/health')
    else:
        if not a.model or not a.prompt:
            p.error('--model and --prompt required')
        out=request(a.socket,'POST','/v1/chat/completions',{'model':a.model,'messages':[{'role':'user','content':a.prompt}],'max_tokens':a.max_tokens})
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

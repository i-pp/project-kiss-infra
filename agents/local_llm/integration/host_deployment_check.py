"""Read-only deployment gates. No POST, Docker, subprocess, model load or generation."""
import argparse
import http.client
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_llm import resources, GIB
import endpoint_config

RESIDENT = 'kiss-qwen3-coder-30b'
EXPECTED = {RESIDENT, 'kiss-b3-gpt-oss-120b', 'kiss-b3-qwen-coder-next'}


class ProbeError(OSError):
    def __init__(self, path, code):
        self.path = path
        self.code = code
        super().__init__(code)


def get(path, deadline, target=None):
    timeout = min(2, deadline-time.monotonic())
    if timeout <= 0: raise ProbeError(path, 'DEADLINE_EXPIRED')
    target=target or {'ipv4':'127.0.0.1','port':8080}
    connection = http.client.HTTPConnection(target['ipv4'],target['port'],timeout=timeout)
    try:
        connection.request('GET',path,headers={'Connection':'close'})
        response=connection.getresponse()
        body=response.read(2*1024**2+1)
        if response.status!=200: raise ProbeError(path, 'HTTP_STATUS_'+str(response.status))
        if len(body)>2*1024**2: raise ProbeError(path, 'HTTP_BODY_LIMIT')
        return json.loads(body)
    except ProbeError: raise
    except TimeoutError as exc: raise ProbeError(path, 'HTTP_TIMEOUT') from exc
    except (OSError, http.client.HTTPException) as exc:
        raise ProbeError(path, 'HTTP_'+type(exc).__name__) from exc
    except ValueError as exc: raise ProbeError(path, 'HTTP_INVALID_JSON') from exc
    finally:connection.close()


def check(mode, read, probe=resources):
    sample=probe()
    minimum=24 if mode=='preflight' else 16
    if sample['available_bytes']<minimum*GIB or sample['gpu_used_bytes']>58*GIB:
        raise ValueError('Existing resource threshold not satisfied')
    if read('/health').get('status')!='ok':raise ValueError('Not healthy')
    suffix='?model='+RESIDENT+'&autoload=false' if mode=='router' else ''
    observed={}
    if mode=='router':
        rows=read('/models').get('data')
        if not isinstance(rows,list) or len(rows)!=3 or {r.get('id') for r in rows}!=EXPECTED:
            raise ValueError('Router catalog differs from fixed three profiles')
        observed={r['id']:r.get('status',{}).get('value') for r in rows}
        if observed.get(RESIDENT)!='loaded' or any(v not in ['unloaded','loaded'] for v in observed.values()) or sum(v=='loaded' for v in observed.values())!=1:
            raise ValueError('Exactly resident30B must be loaded')
    props=read('/props'+suffix)
    if props.get('model_alias')!=RESIDENT or props.get('default_generation_settings',{}).get('n_ctx')!=32768 or props.get('total_slots')!=1:
        raise ValueError('Resident identity/context/slot contract differs')
    slots=read('/slots'+suffix)
    if not isinstance(slots,list) or len(slots)!=1 or slots[0].get('is_processing') is not False:
        raise ValueError('Resident request is active or slot state unconfirmed')
    return {'status':'READONLY_GATE_PASS','mode':mode,'resident_model':RESIDENT,
            'router_models':observed,'resources':sample,'generation_requests':0,
            'lifecycle_operations':0,'code_quality':'UNASSESSED'}


def run_gate(mode, read=None, probe=resources, clock=time.monotonic, sleep=time.sleep, progress=None, target=None):
    started=clock();deadline=started+(5 if mode=='preflight' else 90)
    if read is None:read=lambda p:get(p,deadline,target)
    attempts=0;last_failure={};next_progress=10
    while True:
        attempts+=1
        try:
            result=check(mode,read,probe)
            result.update(elapsed_seconds=round(clock()-started,3),attempts=attempts)
            return result
        except (OSError,ValueError,TypeError,KeyError) as exc:
            # Keep the actual network failure instead of overwriting it with the deadline.
            if not isinstance(exc,ProbeError) or exc.code!='DEADLINE_EXPIRED' or not last_failure:
                last_failure={'reason':getattr(exc,'code',type(exc).__name__)}
                if isinstance(exc,ProbeError):last_failure['endpoint']=exc.path
                else:last_failure['detail']=str(exc)[:200]
            elapsed=clock()-started
            result={'status':'BLOCKED',**last_failure,'elapsed_seconds':round(elapsed,3),
                    'attempts':attempts,'generation_requests':0,'lifecycle_operations':0}
            if mode=='preflight' or clock()>=deadline:return result
            if progress and elapsed>=next_progress:
                progress(result);next_progress=elapsed+10
            sleep(min(.5,max(0,deadline-clock())))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['preflight','router','resident'])
    parser.add_argument('--candidate',action='store_true',help='Read owner-verified router candidate; no address argument')
    args=parser.parse_args()
    try:
        if args.candidate and args.mode!='router':raise ValueError('Router candidate only')
        target=endpoint_config.route(Path(__file__).resolve().parents[1]/'.runtime',
                                     candidate=args.candidate,resident=args.mode!='router')
    except (OSError,ValueError,TypeError,KeyError):
        print(json.dumps({'status':'BLOCKED','reason':'ENDPOINT_INVALID','generation_requests':0,'lifecycle_operations':0}));return 1
    result=run_gate(args.mode,target=target)
    result['endpoint_mode']=target['mode']
    print(json.dumps(result));return 0 if result['status']=='READONLY_GATE_PASS' else 1

if __name__=='__main__':raise SystemExit(main())

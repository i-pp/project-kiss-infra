"""Read bounded GGUF metadata only; no tensor bodies, model imports or hashes."""
import json
from pathlib import Path
import struct

WIDTH={0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1,10:8,11:8,12:8}
CAP=64<<20


def inspect(path):
    with Path(path).open('rb') as f:
        def read(n):
            if n<0 or f.tell()+n>CAP:raise ValueError('Header inspection cap exceeded')
            b=f.read(n)
            if len(b)!=n:raise ValueError('Truncated header')
            return b
        def number(fmt):return struct.unpack('<'+fmt,read(struct.calcsize('<'+fmt)))[0]
        def string(keep=True):
            n=number('Q')
            if n>CAP or f.tell()+n>CAP:raise ValueError('Header string cap exceeded')
            if keep:return read(n).decode('utf-8')
            f.seek(n,1)
        def skip(kind):
            if kind==8:string(False)
            elif kind in WIDTH:read(WIDTH[kind])
            elif kind==9:
                item=number('I');count=number('Q')
                if count>2000000 or item==9:raise ValueError('Unbounded/nested metadata array')
                if item in WIDTH:
                    n=count*WIDTH[item]
                    if f.tell()+n>CAP:raise ValueError('Metadata array cap exceeded')
                    f.seek(n,1)
                elif item==8:
                    for _ in range(count):string(False)
                else:raise ValueError('Unknown array type')
            else:raise ValueError('Unknown GGUF metadata type')
        if read(4)!=b'GGUF':raise ValueError('GGUF magic required')
        version=number('I');tensors=number('Q');count=number('Q')
        if version!=3 or count>200000 or tensors>100000:raise ValueError('Bounded GGUFv3 required')
        result={'version':version,'tensor_count':tensors,'metadata_count':count}
        for _ in range(count):
            key=string();kind=number('I')
            if key in {'general.architecture','general.name'} and kind==8:result[key]=string()
            else:skip(kind)
        result.update(bytes_addressed_through=f.tell(),tensor_bodies_read=False,model_imported=False)
        return result


if __name__=='__main__':
    root=Path(__file__).resolve().parents[3]
    paths={'qwen-coder-next':'qwen-coder-next/Qwen3-Coder-Next-Q4_K_M-00001-of-00004.gguf',
           'qwen38-flash-next':'qwen38-flash-next/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf',
           'gpt-oss-120b':'gpt-oss-120b/gpt-oss-120b-MXFP4.gguf'}
    print(json.dumps({k:inspect(root/'models/large-coder-b3'/v) for k,v in paths.items()},indent=2))

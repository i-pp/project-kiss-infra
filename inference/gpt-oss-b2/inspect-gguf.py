"""Read GGUF V3 metadata/tensor descriptors only; no tensor data or code execution."""
import collections
import json
from pathlib import Path
import struct
import sys


def inspect(path):
    formats = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i',
               6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}
    with Path(path).open('rb') as f:
        def number(fmt):
            return struct.unpack('<'+fmt, f.read(struct.calcsize('<'+fmt)))[0]

        def string(keep=True):
            length = number('Q')
            assert length < 16*1024*1024
            if keep:
                return f.read(length).decode('utf-8')
            f.seek(length, 1)

        def value(kind, keep):
            if kind == 8:
                return string(keep)
            if kind == 9:
                subtype, count = number('I'), number('Q')
                assert count < 10_000_000
                if subtype in formats and not keep:
                    f.seek(struct.calcsize('<'+formats[subtype])*count, 1)
                else:
                    for _ in range(count):
                        value(subtype, False)
                return {'array_length': count, 'element_type': subtype}
            result = number(formats[kind])
            return result if keep else None

        assert f.read(4) == b'GGUF'
        version, tensors, keys = number('I'), number('Q'), number('Q')
        assert version == 3 and tensors < 10000 and keys < 10000
        metadata = {}
        for _ in range(keys):
            key, kind = string(), number('I')
            metadata[key] = value(kind, kind != 9)
        descriptors = []
        for _ in range(tensors):
            name, dims = string(), number('I')
            assert 0 < dims <= 4
            shape = [number('Q') for _ in range(dims)]
            descriptors.append({'name': name, 'shape': shape, 'ggml_type': number('I'), 'offset': number('Q')})
        counts = collections.Counter(str(t['ggml_type']) for t in descriptors)
        return {'version': version, 'tensor_count': tensors, 'metadata': metadata,
                'tensor_types': dict(counts), 'tensors': descriptors,
                'descriptor_end': f.tell(), 'type_names': {'0': 'F32', '8': 'Q8_0', '39': 'MXFP4'}}


if __name__ == '__main__':
    print(json.dumps(inspect(sys.argv[1]), ensure_ascii=False, indent=2))

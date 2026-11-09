# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Small deterministic GPU checks; never downloads or runs generated code."""
import importlib.metadata
import json
import os
from pathlib import Path
import torch

report = {
    'uid': os.getuid(), 'gid': os.getgid(), 'groups': os.getgroups(),
    'torch': torch.__version__, 'hip': torch.version.hip,
    'vllm': importlib.metadata.version('vllm'),
    'rocm_version': {str(p): p.read_text().strip()
                     for p in Path('/opt/rocm/.info').glob('version*')},
    'security': {line.split(':')[0]: line.split(':', 1)[1].strip()
                 for line in Path('/proc/self/status').read_text().splitlines()
                 if line.split(':')[0] in ['CapEff', 'NoNewPrivs', 'Seccomp']},
    'apparmor': Path('/proc/self/attr/current').read_text().strip(),
    'cuda_available': torch.cuda.is_available(), 'tests': [],
}
print(json.dumps(report), flush=True)
assert os.getuid() != 0
assert torch.version.hip and torch.cuda.is_available()
props = torch.cuda.get_device_properties(0)
report['device'] = {'name': props.name, 'gcnArchName': props.gcnArchName,
                    'total_memory': props.total_memory}
assert props.gcnArchName.split(':')[0] == 'gfx1151'
for dtype in [torch.float32, torch.bfloat16]:
    # Integral inputs/reference; floating GPU GEMM may still round intermediate values.
    a = (torch.arange(128*128).reshape(128, 128) % 3 - 1).to(dtype)
    b = (torch.arange(128*128).reshape(128, 128) % 5 - 2).to(dtype)
    expected = a.float() @ b.float()
    result = (a.cuda() @ b.cuda()).float().cpu()
    torch.testing.assert_close(result, expected, rtol=1e-5, atol=1e-5)
    x = torch.arange(1024, device='cuda', dtype=dtype) % 7
    torch.testing.assert_close((x * 2 + 1).cpu(), (x.cpu() * 2 + 1), rtol=0, atol=0)
    torch.cuda.synchronize()
    report['tests'].append({'dtype': str(dtype), 'matmul_and_elementwise': 'PASS',
                            'gemm_rtol': 1e-5, 'gemm_atol': 1e-5,
                            'gemm_max_absolute_error': (result-expected).abs().max().item()})
report['status'] = 'PASS'
report['allocated_bytes'] = torch.cuda.memory_allocated()
report['reserved_bytes'] = torch.cuda.memory_reserved()
print(json.dumps(report), flush=True)

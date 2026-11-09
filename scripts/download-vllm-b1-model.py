#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Download only the approved BF16 model, verified against pinned official metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
LOCK = json.loads((ROOT/'inference/vllm-b1/versions.lock.json').read_text())
FILES = ['LICENSE', 'README.md', 'config.json', 'generation_config.json', 'merges.txt',
         'tokenizer.json', 'tokenizer_config.json', 'vocab.json', 'model.safetensors']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    assert not args.report.exists(), 'Report exists; choose a new filename'
    repo, revision = LOCK['model'], LOCK['revision']
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true', timeout=30) as r:
        metadata = json.load(r)
    assert metadata['sha'] == revision
    entries = {e['rfilename']: e for e in metadata['siblings']}
    assert sum(entries[f]['size'] for f in FILES) < 3_200_000_000
    assert entries[LOCK['model_file']]['lfs']['sha256'] == LOCK['model_sha256']
    assert entries[LOCK['model_file']]['size'] == LOCK['model_file_bytes']
    destination = ROOT/'models/Qwen2.5-Coder-1.5B-Instruct-BF16'
    destination.mkdir(exist_ok=True)
    report = {'repository': repo, 'revision': revision, 'metadata': metadata, 'files': []}
    for name in FILES:
        expected = entries[name]
        path = destination/name
        partial = path.with_name(path.name+'.part')
        if not path.exists():
            with urllib.request.urlopen(f'https://huggingface.co/{repo}/resolve/{revision}/{name}?download=true', timeout=120) as response, partial.open('xb') as f:
                while chunk := response.read(8*1024*1024):
                    f.write(chunk)
            path_to_check = partial
        else:
            path_to_check = path
        assert path_to_check.stat().st_size == expected['size'], name+' size mismatch'
        sha256 = hashlib.sha256()
        git = hashlib.sha1(f"blob {expected['size']}\0".encode())
        with path_to_check.open('rb') as f:
            while chunk := f.read(8*1024*1024):
                sha256.update(chunk); git.update(chunk)
        if 'lfs' in expected:
            assert sha256.hexdigest() == expected['lfs']['sha256'], name+' SHA256 mismatch'
        else:
            assert git.hexdigest() == expected['blobId'], name+' Git blob hash mismatch'
        if path_to_check == partial:
            # Existing data is never overwritten; rename follows an explicit absence check.
            assert not path.exists()
            partial.rename(path)
        report['files'].append({'name': name, 'bytes': expected['size'],
                                'sha256': sha256.hexdigest(), 'status': 'PASS'})
        print(name, 'PASS', flush=True)
    with (destination/LOCK['model_file']).open('rb') as f:
        length = struct.unpack('<Q', f.read(8))[0]
        assert length < 16*1024*1024
        header = json.loads(f.read(length))
    dtypes = sorted({v['dtype'] for k, v in header.items() if k != '__metadata__'})
    assert dtypes == ['BF16'], dtypes
    report.update({'status': 'PASS', 'tensor_dtypes': dtypes,
                   'total_bytes': sum(e['bytes'] for e in report['files'])})
    with args.report.open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')


if __name__ == '__main__':
    main()

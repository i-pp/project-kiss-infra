#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Fetch only the approved GGUF; never replace existing model data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
LOCK = json.loads((ROOT/'inference/gpt-oss-b2/versions.lock.json').read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    assert not args.report.exists(), 'Choose a new report filename'
    started = time.monotonic()
    repo, revision, name = (LOCK[k] for k in ['model_repository', 'model_revision', 'model_file'])
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true', timeout=30) as r:
        meta = json.load(r)
    assert meta['sha'] == revision
    entry = next(e for e in meta['siblings'] if e['rfilename'] == name)
    assert entry['size'] == LOCK['model_bytes']
    assert entry['lfs']['sha256'] == LOCK['model_sha256']
    assert meta['cardData']['license'] == 'apache-2.0'
    dest = ROOT/'models/gpt-oss-20b'
    dest.mkdir(exist_ok=True)
    path = dest/name
    partial = dest/(name+'.part')
    actual = path
    if not path.exists():
        actual = partial
        if partial.exists():
            assert partial.stat().st_size < LOCK['model_bytes'], 'Unexpected partial size'
            with partial.open('rb') as f:
                assert f.read(4) == b'GGUF', 'Partial file is not GGUF'
        url = f'https://huggingface.co/{repo}/resolve/{revision}/{name}?download=true&b2_transfer={time.time_ns()}'
        # The host already provides curl with HTTP/2. Resume only this approved file.
        # The original urllib transfer was abnormally slow; TLS verification stays enabled.
        subprocess.run(['curl', '--fail', '--location', '--continue-at', '-', '--retry', '3',
                        '--retry-delay', '2', '--max-time', '1800', '--speed-limit', '1024',
                        '--speed-time', '60', '--output', str(partial), url], check=True)
    assert actual.stat().st_size == LOCK['model_bytes'], 'Model size mismatch'
    h = hashlib.sha256()
    with actual.open('rb') as f:
        while chunk := f.read(8*1024*1024):
            h.update(chunk)
    assert h.hexdigest() == LOCK['model_sha256'], 'Model SHA-256 mismatch'
    if actual == partial:
        assert not path.exists()
        partial.rename(path)
    result = {'status': 'PASS', 'metadata': meta, 'file': str(path.relative_to(ROOT)),
              'bytes': path.stat().st_size, 'sha256': h.hexdigest(),
              'wall_seconds': time.monotonic()-started}
    with args.report.open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps({k: result[k] for k in ['status', 'file', 'bytes', 'sha256', 'wall_seconds']}))


if __name__ == '__main__':
    main()

"""Fixed asset/operator contract. No network, GPU, service or command actions."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys

ROOT = Path(__file__).resolve().parent
MANIFEST_SHA256 = '6329d7d44fea2260336e2fbfca45e0022fcf60e7b66704f8e137820a066ffd19'
MODEL_BASENAME = 'cyankiwi-Qwen3-Coder-Next-AWQ-4bit-c92cabfad08c'
MODEL_RELATIVE = Path('models/backend-next-int4')/MODEL_BASENAME
NETWORK = 'project-kiss-large-coder-b3_local'
SOURCE = {'vllm':'5df63a7203cdb9328d824a27b682e77c7b9928be',
          'sglang':'baa9befa381511cd4d56f83980951e5a45fffc6d'}
GIB = 1 << 30
# Live operations are supported only after installation in this repository.
FIXED_PROJECT_ROOT = ROOT.parents[2] if ROOT.parent.name=='backend-evaluation' else None


class Blocked(RuntimeError): pass


def manifest():
    raw = (ROOT/'candidate.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise Blocked('FIXED_MANIFEST_CHANGED')
    d = json.loads(raw)
    if (d['repo'] != 'cyankiwi/Qwen3-Coder-Next-AWQ-4bit'
        or d['revision'] != 'c92cabfad08cadb011dc169cabb3e6da621b0719'
        or len(d['required_files']) != 20
        or sum(r['bytes'] for r in d['required_files']) != 48278252061
        or any(not re.fullmatch('[0-9a-f]{64}',r['sha256']) for r in d['required_files'])):
        raise Blocked('FIXED_MANIFEST_INVALID')
    return d


def safe_path(path, must_exist=True):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(x in str(path) for x in [',','\n','\r']):
        raise Blocked('ABSOLUTE_NONTRAVERSING_PATH_REQUIRED')
    if any(x.is_symlink() for x in [path,*path.parents]):
        raise Blocked('SYMLINK_PATH_PROHIBITED')
    if must_exist and not path.exists(): raise Blocked('PATH_MISSING')
    return path


def private_read(path, digest):
    if not re.fullmatch('[0-9a-f]{64}',digest or ''): raise Blocked('OPERATOR_JSON_SHA256_REQUIRED')
    path = safe_path(path)
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        s = os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o600:
            raise Blocked('OPERATOR_JSON_OWNER_MODE0600_REQUIRED')
        raw = f.read(65537)
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=digest:
        raise Blocked('OPERATOR_JSON_DIGEST_MISMATCH')
    return json.loads(raw)


def _require_selected_sglang_be68_profile(r):
    # Reviewed upstream reference and four selected hashes; never a whole-commit claim.
    expected = {'image_ref': 'rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230', 'image_id': 'sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230', 'source_commit': 'ebfbd3ea35acf6e9facbe74e627d37c3542e5fc1', 'source_equivalence_scope': 'four-selected-files-not-whole-commit', 'source_evidence_sha256': 'a89def61d14a5259ee1cbe9835c7c3540c08d0e7d1e4e6e902b293d02eb01d89', 'dependency_versions': {'amd-aiter': '0.0.0', 'triton': '3.7.0+amd.rocm7.2.0.git89002410', 'sglang': '0.5.23.dev1202+gebfbd3ea3', 'transformers': '5.19.0', 'compressed-tensors': '0.15.0', 'safetensors': '0.8.0', 'torch': '2.9.1+rocm7.2.4.lw.git39497456', 'rocm': '7.2.4'}}
    if any(r.get(key) != value for key,value in expected.items()):
        raise Blocked('FIXED_SGLANG_BE68_SELECTED_SOURCE_PROFILE_REQUIRED')


def operator_record(path, digest, purpose='trial', backend=None):
    d = private_read(path,digest)
    selected_backend=backend
    if selected_backend not in (None,'vllm','sglang'):raise Blocked('FIXED_BACKEND_REQUIRED')
    if set(d) != {'schema_version','project_root','model_dir','coordinator_runtime_relative','review','runtimes'} or d['schema_version'] != 1:
        raise Blocked('OPERATOR_RECORD_SCHEMA')
    if purpose not in ('trial','acquire'):raise Blocked('UNKNOWN_OPERATION_PURPOSE')
    keys=['fixed_weight_acquisition_reviewed']
    if purpose=='trial':keys+=['human_host_docker_trial_reviewed','resident30b_unload_restore_reviewed','temporary_owned_internal_api_reviewed','fixed_jit_cache_exec_reviewed']
    for key in keys:
        if d['review'].get(key) is not True: raise Blocked('OPERATOR_REVIEW_MISSING:'+key)
    project=safe_path(d['project_root'])
    if FIXED_PROJECT_ROOT is None or project!=Path(FIXED_PROJECT_ROOT).resolve():
        raise Blocked('FIXED_INSTALLED_PROJECT_REQUIRED_NO_FOREIGN_HELPER_IMPORT')
    if not (project/'agents/local_llm').is_dir():raise Blocked('PROJECT_LOCAL_LLM_DIRECTORY_MISSING')
    model=safe_path(d['model_dir'],must_exist=False)
    if model!=project/MODEL_RELATIVE:raise Blocked('FIXED_MODEL_DIRECTORY_REQUIRED')
    ancestor=model.parent
    while not ancestor.exists():ancestor=ancestor.parent
    if ancestor.stat().st_uid!=os.getuid():raise Blocked('MODEL_PARENT_OWNER_REQUIRED')
    rel=Path(d['coordinator_runtime_relative'])
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:raise Blocked('INVALID_COORDINATOR_RELATIVE_PATH')
    if set(d['runtimes']) != {'vllm','sglang'}:raise Blocked('FIXED_TWO_BACKENDS_REQUIRED')
    for backend,r in d['runtimes'].items():
        selected_sglang = purpose=='trial' and selected_backend=='sglang' and backend=='sglang'
        expected_keys={'image_ref','image_id','source_commit','dependency_versions','source_dependency_match_reviewed','bootstrap_complete_reviewed'}
        if selected_sglang:expected_keys|={'source_equivalence_scope','source_evidence_sha256'}
        if set(r)!=expected_keys:
            raise Blocked('RUNTIME_RECORD_SCHEMA')
        if selected_sglang:
            _require_selected_sglang_be68_profile(r)
        elif r['source_commit']!=SOURCE[backend]:raise Blocked('RUNTIME_SOURCE_MISMATCH')
        if purpose=='acquire' or (selected_backend is not None and selected_backend!=backend):continue
        if r['source_dependency_match_reviewed'] is not True or r['bootstrap_complete_reviewed'] is not True:
            raise Blocked('RUNTIME_BOOTSTRAP_OR_DEPENDENCY_REVIEW_PENDING')
        if (not isinstance(r['image_ref'],str) or not isinstance(r['image_id'],str)
            or not re.fullmatch(r'(?:[a-z0-9][a-z0-9./:_-]*@)?sha256:[0-9a-f]{64}',r['image_ref'])
            or not re.fullmatch(r'sha256:[0-9a-f]{64}',r['image_id'])):raise Blocked('IMMUTABLE_IMAGE_REFERENCE_REQUIRED')
        deps=r['dependency_versions']
        if deps.get('compressed-tensors') != ('0.17.0' if backend=='vllm' else '0.15.0'):
            raise Blocked('COMPRESSED_TENSORS_RUNTIME_MISMATCH')
        if not all(isinstance(deps.get(k),str) and re.fullmatch(r'\d+\.\d+\.\d+(?:[a-zA-Z0-9.+_-]*)?',deps[k]) for k in ['torch','triton','rocm','transformers']):
            raise Blocked('DEPENDENCY_VERSION_RECEIPT_INCOMPLETE')
        if deps['rocm'] != ('7.2.3' if backend=='vllm' else '7.2.4'):
            raise Blocked('ROCM_RUNTIME_MISMATCH')
        numbers=lambda key:tuple(int(x) for x in re.match(r'(\d+)\.(\d+)\.(\d+)',deps[key]).groups())
        if not (3,0,0)<=numbers('triton')<(5,0,0) or not (2,9,0)<=numbers('torch')<(3,0,0):
            raise Blocked('TORCH_TRITON_RANGE_MISMATCH')
        if backend=='sglang' and numbers('torch')!=(2,9,1):raise Blocked('FIXED_SGLANG_BASE_TORCH_MISMATCH')
        if backend=='vllm' and not (5,16,1)<=numbers('transformers')<(5,20,0):raise Blocked('VLLM_TRANSFORMERS_RANGE_MISMATCH')
    return d


def helpers():
    # Fixed sibling preparation module. No operator-selected Python module path.
    candidates=[ROOT.parent/name for name in ['host-trial-prep','host_trial']]
    present=[p for p in candidates if p.is_dir() and (p/'host_strata_trial.py').is_file()]
    if len(present)!=1:raise Blocked('FIXED_COORDINATOR_HELPER_LAYOUT_MISSING_OR_AMBIGUOUS')
    fixed=safe_path(present[0])
    sys.path.insert(0,str(fixed))
    from host_strata_trial import Coordinator, private_dir, private_write
    from owned_process import system_probe
    return Coordinator, private_dir, private_write, system_probe


def verify_weights(directory,check=lambda:None):
    """All twenty SHA256s; bounded CPU buffer, no backend imports."""
    directory=safe_path(directory)
    d=manifest()
    allowed={r['name'] for r in d['required_files']}|{'acquisition.json'}
    if set(x.name for x in directory.iterdir())-allowed:raise Blocked('UNREVIEWED_MODEL_DIRECTORY_FILES')
    result=[]
    for r in d['required_files']:
        check()
        p=directory/r['name']
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        h=hashlib.sha256()
        with os.fdopen(fd,'rb') as f:
            before=os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size!=r['bytes']:raise Blocked('MODEL_FILE_SIZE_MISMATCH')
            for b in iter(lambda:f.read(8<<20),b''):
                h.update(b);check()
            after=os.fstat(f.fileno())
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise Blocked('MODEL_FILE_CHANGED_WHILE_HASHING')
        if h.hexdigest()!=r['sha256']:raise Blocked('MODEL_FILE_SHA256_MISMATCH')
        result.append((str(p),before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns))
    return result


def on_terminate(signum,frame):raise KeyboardInterrupt('TERMINATION_REQUESTED')


def install_sigterm_handler():signal.signal(signal.SIGTERM,on_terminate)


def model_metadata_unchanged(fingerprints):
    for name,dev,ino,size,mtime in fingerprints:
        p=Path(name)
        if p.is_symlink():return False
        try:s=p.stat()
        except OSError:return False
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)!=(dev,ino,size,mtime):return False
    return True

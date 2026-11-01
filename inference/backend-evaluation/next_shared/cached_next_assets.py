"""Opt-in verifier for future trials; existing single-use launchers are unchanged.

Future integration passes Trial(verify=v, unchanged=v.unchanged) and explicitly
calls assert_unchanged before/after loading under the shared lifecycle lock.
Existing Trial calls unchanged only at final cleanup; no load hooks are implied.
"""
from pathlib import Path
from verified_assets_cache import verify, unchanged
from fixed_trial_assets import manifest, MODEL_RELATIVE


class CachedNextVerifier:
    def __init__(self, cache, report=lambda result: None, force=False):
        self.cache = Path(cache)
        self.report = report
        self.force = force
        self.result = None

    def __call__(self, directory, check=lambda: None):
        self.result = verify(directory, manifest(), self.cache, check=check, force=self.force)
        self.report({k:v for k,v in self.result.items() if k != 'binding'})
        return [(str(Path(directory)/name),s[0],s[1],s[2],s[3])
                for name,s in self.result['binding']['files'].items()]

    def unchanged(self, fingerprints):
        if self.result is None: return False
        expected = [(str(Path(self.result['binding']['root_path'])/name),s[0],s[1],s[2],s[3])
                    for name,s in self.result['binding']['files'].items()]
        try: return fingerprints == expected and unchanged(self.result)
        except (OSError, ValueError): return False

    def assert_unchanged(self):
        if self.result is None or not unchanged(self.result):
            raise RuntimeError('Model changed at load boundary; do not use it')


if __name__ == '__main__':
    import argparse, json
    parser=argparse.ArgumentParser(description='CPU-only fixed Next verification; no loading or generation')
    parser.add_argument('--cache-dir',type=Path,required=True)
    parser.add_argument('--force-full',action='store_true')
    args=parser.parse_args()
    # Installed next_shared layout only. No operator-selected model/revision.
    repo=Path(__file__).resolve().parents[3]
    verifier=CachedNextVerifier(args.cache_dir,report=lambda r:print(json.dumps(r)),force=args.force_full)
    fingerprints=verifier(repo/MODEL_RELATIVE)
    if not verifier.unchanged(fingerprints): raise RuntimeError('Model changed after verification')

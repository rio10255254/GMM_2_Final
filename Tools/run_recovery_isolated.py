"""Run a copied recovery script while denying reads from the old research tree.

The audit guard is inherited by Python worker processes. It is a reproducibility
check on these trusted scripts, not a general-purpose security sandbox.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

GUARD = r'''
import json, os, sys
_blocked = [os.path.normcase(os.path.abspath(p)) for p in json.loads(os.environ['GMM_REPLAY_BLOCKED'])]
_allowed = [os.path.normcase(os.path.abspath(p)) for p in json.loads(os.environ['GMM_REPLAY_ALLOWED'])]
def _inside(path, root):
    return path == root or path.startswith(root + os.sep)
def _guard(event, args):
    if event not in ('open','os.listdir','os.scandir') or not args:
        return
    value = args[0]
    if not isinstance(value, (str, bytes, os.PathLike)):
        return
    path = os.path.normcase(os.path.abspath(os.fsdecode(value)))
    if any(_inside(path, root) for root in _allowed):
        return
    if any(_inside(path, root) for root in _blocked):
        print('RECOVERY_DENIED_OLD_SOURCE ' + path, file=sys.stderr, flush=True)
        raise PermissionError('Recovery must not read the old research source: ' + path)
sys.addaudithook(_guard)
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--guard-dir', type=Path, required=True)
    p.add_argument('--allow-root', type=Path, action='append', required=True)
    p.add_argument('--block-root', type=Path, action='append', required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('script', type=Path)
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.report.exists():
        raise FileExistsError(a.report)
    a.guard_dir.mkdir(parents=True, exist_ok=True)
    (a.guard_dir/'sitecustomize.py').write_text(GUARD, encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(a.guard_dir.resolve()), PYTHONUTF8='1',
               PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    env['GMM_REPLAY_BLOCKED'] = json.dumps([str(p.resolve()) for p in a.block_root])
    env['GMM_REPLAY_ALLOWED'] = json.dumps([str(p.resolve()) for p in a.allow_root])
    command = [sys.executable, '-X', 'utf8', '-B', str(a.script.resolve()), *a.arguments]
    started = time.time()
    result = subprocess.run(command, cwd=a.script.resolve().parent, env=env)
    receipt = {'status': 'PASS' if result.returncode == 0 else 'FAIL',
               'returncode': result.returncode, 'command': command,
               'blocked_original_roots': [str(p) for p in a.block_root],
               'allowed_copied_roots': [str(p) for p in a.allow_root],
               'python_workers_inherit_guard': True, 'seconds': time.time()-started}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())

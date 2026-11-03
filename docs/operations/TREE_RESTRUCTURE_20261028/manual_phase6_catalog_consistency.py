"""For each path->sha catalog, count entries whose path is tracked but whose sha differs from the file."""
import gzip, hashlib, json, subprocess, sys
from pathlib import Path

REPO = Path(sys.argv[1]); REV = sys.argv[2] if len(sys.argv) > 2 else None  # REV: read catalogs and files from a commit
CATS = ['docs/reproducibility/REPOSITORY_FILES.json.gz', 'docs/reproducibility/project_completion/curated/CURATED_FILE_MAP.json.gz',
        'docs/reproducibility/lineage/SOURCE_AVAILABILITY.json.gz']


def blob(path):
    if REV:
        r = subprocess.run(['git', '-C', str(REPO), 'show', f'{REV}:{path}'], capture_output=True)
        return r.stdout if r.returncode == 0 else None
    p = REPO / path
    return p.read_bytes() if p.is_file() else None


tracked = set(subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(REPO), 'ls-tree', '-r', '--name-only', '-z',
                              REV or 'HEAD'], capture_output=True, check=True).stdout.decode('utf-8').split('\0'))
cache = {}
for c in CATS:
    d = json.loads(gzip.decompress(blob(c)))
    bad = total = 0; examples = []
    for e in d['files']:
        p = e.get('path')
        if p in tracked and p not in CATS:
            if p not in cache:
                b = blob(p); cache[p] = hashlib.sha256(b).hexdigest() if b is not None else None
            total += 1
            if cache[p] != e['sha256']:
                bad += 1; examples.append(p)
    print(f'{c}: tracked entries {total}, sha differs {bad}', examples[:4])

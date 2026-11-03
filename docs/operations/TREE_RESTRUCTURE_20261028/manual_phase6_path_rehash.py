"""Path-aware rehash for the path->sha catalogs.

Eligible entries: in each catalog on origin/main, entries whose path is a file changed on this branch
and whose sha256 matched that file on origin/main. Each round sets every eligible entry to the file's
current sha256 (and bytes), keeping the catalogs' compact JSON format, until nothing changes. Entries
that were already out of date on main are left as they were.
"""
import gzip, hashlib, json, subprocess, sys
from pathlib import Path

REPO = Path(sys.argv[1])
CATS = ['docs/reproducibility/REPOSITORY_FILES.json.gz', 'docs/reproducibility/project_completion/curated/CURATED_FILE_MAP.json.gz',
        'docs/reproducibility/lineage/SOURCE_AVAILABILITY.json.gz']


def git(*a):
    return subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(REPO), *a], capture_output=True, check=True).stdout


def exists_on_main(p):
    return subprocess.run(['git', '-C', str(REPO), 'cat-file', '-e', f'origin/main:{p}'], capture_output=True).returncode == 0


changed = {p for p in git('diff', '--name-only', '-z', 'origin/main').decode('utf-8').split('\0') if p}
main_sha = {p: hashlib.sha256(git('show', f'origin/main:{p}')).hexdigest() for p in changed if exists_on_main(p)}
eligible = {}
for c in CATS:
    d = json.loads(gzip.decompress(git('show', f'origin/main:{c}')))
    eligible[c] = {i for i, e in enumerate(d['files']) if e.get('path') in main_sha and e.get('path') != c
                   and e.get('sha256') == main_sha[e['path']]}
    print(c.split('/')[-1], 'eligible entries', len(eligible[c]))
for rnd in range(1, 21):
    edits = 0
    for c in CATS:
        p = REPO / c; text = gzip.decompress(p.read_bytes()).decode('utf-8'); d = json.loads(text); touched = False
        for i in eligible[c]:
            e = d['files'][i]; data = (REPO / e['path']).read_bytes(); s = hashlib.sha256(data).hexdigest()
            if s != e['sha256']:
                e['sha256'] = s
                if 'bytes' in e:
                    e['bytes'] = len(data)
                touched = True; edits += 1
        if touched:
            out = json.dumps(d, ensure_ascii=False, separators=(',', ':')) + ('\n' if text.endswith('\n') else '')
            p.write_bytes(gzip.compress(out.encode('utf-8'), mtime=0))
    print('round', rnd, 'edits', edits)
    if not edits:
        break
else:
    print('NOT CONVERGED')

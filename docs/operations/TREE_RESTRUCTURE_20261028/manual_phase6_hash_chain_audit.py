"""Find records where the hash chain replaced a sha256 that still belongs to an unchanged tracked file.

For each phase's hash_changes (old -> new), if some file tracked at HEAD still has content `old`,
then a record that now says `new` may have meant that unchanged file. Report each tracked text file
that contains such a `new` value, with the paths of the unchanged files whose content is `old`.
"""
import gzip, hashlib, json, re, subprocess, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(sys.argv[1]); REC = REPO / 'docs/operations/TREE_RESTRUCTURE_20261028'
env = None
files = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(REPO), 'ls-files', '-z'], capture_output=True,
                       check=True).stdout.decode('utf-8').split('\0')
files = [f for f in files if f]
by_sha = defaultdict(list)
for f in files:
    p = REPO / f
    if p.is_file():
        by_sha[hashlib.sha256(p.read_bytes()).hexdigest()].append(f)
chain = {}
for k in range(1, 7):
    h = REC / f'hash_changes_phase{k}.json'
    if h.exists():
        for old, new in json.loads(h.read_text(encoding='utf-8'))['changes'].items():
            if old in by_sha and old != new:
                chain[new] = old
print('new values whose old content is still a tracked file:', len(chain))
hexre = re.compile(rb'[0-9a-f]{64}')
hits = defaultdict(set)
for f in files:
    p = REPO / f
    if not p.is_file() or p.stat().st_size > 200_000_000:
        continue
    data = p.read_bytes()
    if f.endswith('.gz'):
        try:
            data = gzip.decompress(data)
        except OSError:
            continue
    for m in set(hexre.findall(data)):
        s = m.decode()
        if s in chain:
            hits[f].add(s)
out = []
for f, shas in sorted(hits.items()):
    for s in sorted(shas):
        out.append({'record': f, 'value_now': s, 'old_content': chain[s], 'unchanged_files_with_old_content': by_sha[chain[s]][:5],
                    'files_with_new_content': by_sha.get(s, [])[:5]})
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print('records with such values:', len(hits), 'pairs:', len(out))

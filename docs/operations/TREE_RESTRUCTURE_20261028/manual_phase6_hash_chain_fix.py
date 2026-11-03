"""Classify each suspicious hash-chain value by the path the record pairs it with.

For every occurrence of a suspicious value, take the nearest quoted path before it (within 400
characters) and resolve it against the repo root and every ancestor of the record. If the resolved
file has the old content, the chain replaced the value wrongly ('wrong'); if it has the new content,
the value is right ('right'); otherwise 'unknown'. With --fix, wrong occurrences get the old value.
"""
import gzip, hashlib, json, re, sys
from pathlib import Path

REPO = Path(sys.argv[1]); AUDIT = Path(sys.argv[2]); FIX = '--fix' in sys.argv
pairs = json.loads(AUDIT.read_text(encoding='utf-8'))
by_record = {}
for p in pairs:
    if '/TREE_RESTRUCTURE_20261028/hash_changes_' in '/' + p['record']:
        continue
    by_record.setdefault(p['record'], {})[p['value_now']] = p['old_content']
PATH_RE = re.compile(r"""["']([^"'\n]{3,400}?\.[A-Za-z0-9]{1,8})["']""")


def sha_of(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def resolve(rec, cand):
    cand = cand.replace('\\', '/')
    bases = [REPO] + [REPO / Path(*Path(rec).parts[:i]) for i in range(len(Path(rec).parts) - 1, 0, -1)]
    for b in bases:
        for c in (cand, cand.split('GMM_2_Final/')[-1]):
            q = b / c
            if q.is_file():
                return q
    return None


report = {'wrong': 0, 'right': 0, 'unknown': 0}; details = []
for rec, values in sorted(by_record.items()):
    p = REPO / rec; raw = p.read_bytes(); gz = rec.endswith('.gz')
    text = (gzip.decompress(raw) if gz else raw).decode('utf-8')
    new_text = text
    for new, old in values.items():
        def decide(m):
            start = m.start()
            window = text[max(0, start - 400):start]
            cands = PATH_RE.findall(window)
            q = None
            for c in reversed(cands):
                q = resolve(rec, c)
                if q:
                    break
            s = sha_of(q) if q else None
            kind = 'wrong' if s == old else 'right' if s == new else 'unknown'
            report[kind] += 1
            details.append({'record': rec, 'kind': kind, 'path': str(q.relative_to(REPO)) if q else None, 'value': new[:12]})
            return old if (kind == 'wrong' and FIX) else m.group(0)
        new_text = re.sub(re.escape(new), decide, new_text) if FIX else (re.sub(re.escape(new), decide, text), new_text)[1]
    if FIX and new_text != text:
        data = new_text.encode('utf-8')
        p.write_bytes(gzip.compress(data, mtime=0) if gz else data)
print(report)
Path(AUDIT.with_name('hash_chain_classified.json')).write_text(json.dumps(details, ensure_ascii=False, indent=1), encoding='utf-8')

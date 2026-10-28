"""Build external_map.json: external absolute paths -> where their content restores inside the project.

Run once on the 2026-10-28 machine, before handoff (it reads the external files).
Matching is by content: each external file's sha256 (from the inventory hash cache, hashed
now when missing) is looked up in the cloud index and in the git tree. A name match alone
never counts. When one content restores to several places, the place sharing the longest
path tail with the external path wins. A folder enters "dirs" only when every inventoried
file under it maps, all with the same new folder prefix. Junctions pointing into the
project are recorded under "junctions".

Usage: python build_external_map.py <repo> <external_inventory.tsv> <hash_cache_dir> <out_dir>
"""
import collections, csv, hashlib, json, os, posixpath, re, sqlite3, subprocess, sys
from pathlib import Path

repo, inv_path, cache_dir, out_dir = map(Path, sys.argv[1:5])
sys.path.insert(0, str(repo / 'Tools'))
from restructure_resolve import git_env, norm_abs
from restructure_text import ABS_START, TOKEN

ROOTS = {'NTU': 'D:/NTU_ImageDataset', 'GMM2': 'D:/NonSystemFiles/GMM2', 'thesis13': 'H:/From_2TB_D_disk/13_thesis'}
JUNCTIONS = {'C:/Users/Rio/Downloads/20260902_100MF_uncertainty/20260902_100MF_uncertainty/20260903':
             'Shared_Sources/PI_Repeatability_20260903/raw'}
SCAN_ROOTS = ('C:/Users/Rio/Downloads', 'D:/NTU_ImageDataset', 'D:/NonSystemFiles', 'H:/From_2TB_D_disk')

# content -> restore paths, from the cloud index and the git tree
index = sqlite3.connect(str(repo / '.cache/cloud_locator/index.sqlite'))
by_sha = collections.defaultdict(set)
sizes = set()
for path, sha, size in index.execute('SELECT path, sha256, bytes FROM objects'):
    if sha and not path.startswith(('zip:', '@')):
        by_sha[sha].add(path)
        sizes.add(size)
listing = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), 'ls-files', '-z'],
                         capture_output=True, check=True, env=git_env()).stdout.decode('utf-8')
for name in filter(None, listing.split('\0')):
    p = repo / name
    if p.is_file():
        by_sha[hashlib.sha256(p.read_bytes()).hexdigest()].add(name)
        sizes.add(p.stat().st_size)

hashes = sqlite3.connect(str(cache_dir / 'hashes.sqlite'))
cached = {p: s for p, s in hashes.execute('SELECT path, sha256 FROM hashes') if s}


def tail_len(a, b):
    x, y, n = a.split('/'), b.split('/'), 0
    while n < min(len(x), len(y)) and x[-1 - n] == y[-1 - n]:
        n += 1
    return n


files, unmapped_files, inventoried = {}, 0, collections.defaultdict(int)
with open(inv_path, encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f, delimiter='\t'):
        label, _, rel = row['path'][1:].partition('/')
        if label not in ROOTS:
            continue
        ext = f'{ROOTS[label]}/{rel}'
        for d in [posixpath.dirname(ext)]:
            while len(d) > 3:
                inventoried[d] += 1
                d = posixpath.dirname(d)
        sha = cached.get(row['path'])
        if sha is None and int(row['bytes']) in sizes:
            sha = hashlib.sha256(Path(ext).read_bytes()).hexdigest()
        cands = by_sha.get(sha, ()) if sha else ()
        if not cands:
            unmapped_files += 1
            continue
        files[ext] = sorted(cands, key=lambda c: (-tail_len(ext, c), c))[0]

# folders whose every file maps with one shared prefix
votes = collections.defaultdict(collections.Counter)
for ext, new in files.items():
    d = posixpath.dirname(ext)
    while len(d) > 3:
        rest = ext[len(d) + 1:]
        if new.endswith('/' + rest):
            votes[d][new[:-len(rest) - 1]] += 1
        d = posixpath.dirname(d)
dirs = {}
for d, counter in votes.items():
    prefix, n = counter.most_common(1)[0]
    if len(counter) == 1 and n == inventoried[d]:
        dirs[d] = prefix
# keep only the outermost such folders
dirs = {d: p for d, p in dirs.items() if not any(d.startswith(o + '/') and dirs[o] + d[len(o):] == p for o in dirs if o != d)}

ext_map = {'files': dict(sorted(files.items())), 'dirs': dict(sorted(dirs.items())), 'junctions': JUNCTIONS}
lookup = {**files, **dirs, **JUNCTIONS}

# references in tracked text to external places that do not map
refs = collections.Counter()
lows = sorted(((k.lower(), v) for k, v in lookup.items()), key=lambda kv: -len(kv[0]))
for name in filter(None, listing.split('\0')):
    p = repo / name
    if name.endswith(('.png', '.bmp', '.npz', '.pth', '.onnx', '.zip', '.jpg', '.tif', '.pdf', '.docx', '.xlsx', '.mp4')):
        continue
    try:
        text = p.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        continue
    for m in TOKEN.finditer(text):
        tok = m.group(0)
        if not ABS_START.match(tok):
            continue
        a = norm_abs(tok).rstrip('/.。')
        if not a.lower().startswith(tuple(r.lower() for r in SCAN_ROOTS)):
            continue
        low = a.lower()
        if any(low == k or low.startswith(k + '/') for k, _ in lows):
            continue
        parts = a.split('/')
        refs['/'.join(parts[:min(len(parts), 5)])] += 1

out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / 'external_map.json').write_text(json.dumps(ext_map, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
with open(out_dir / 'external_unmapped.tsv', 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f, delimiter='\t', lineterminator='\n')
    w.writerow(['external_folder', 'references'])
    for k, v in refs.most_common():
        w.writerow([k, v])
print(f'{len(files)} files mapped, {unmapped_files} inventoried files not in the cloud, {len(dirs)} folders, '
      f'{sum(refs.values())} references to unmapped external places in {len(refs)} folders')

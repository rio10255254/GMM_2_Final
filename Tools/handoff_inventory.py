"""Read-only handoff inventory: what exists only on this machine?

Used before the machine was handed over (2026-10-28, and again in the tree restructure's
final check): every file under the given roots is classified as in git, in a Release, or
local only, by content hash. Wraps Tools/cloud_locator.py's cloud index and classification,
but walks without following junctions or symlinks (they are listed in <report>.reparse.tsv),
and accepts roots outside the project (labelled '@<label>/...').

Usage: python Tools/handoff_inventory.py <repo> <report.tsv> <label=path> [<label=path> ...]
  label '' (empty) means the project root itself, so relative paths match git paths.
"""
import collections, csv, importlib.util, os, pathlib, stat as statmod, sys, time

repo, report_path, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
spec = importlib.util.spec_from_file_location('cloud_locator', os.path.join(repo, 'Tools', 'cloud_locator.py'))
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)

REPARSE = 0x400
SKIP = {'.git', '__pycache__', '.pytest_cache'}

def walk_no_reparse(root, reparse_log):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(cl.long_path(d))
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if getattr(st, 'st_file_attributes', 0) & REPARSE or e.is_symlink():
                    target = ''
                    try:
                        target = os.readlink(e.path)
                    except OSError:
                        pass
                    reparse_log.append((e.path.removeprefix('\\\\?\\'), target))
                    continue
                if statmod.S_ISDIR(st.st_mode):
                    if e.name not in SKIP:
                        stack.append(e.path.removeprefix('\\\\?\\'))
                    continue
                yield e.path.removeprefix('\\\\?\\'), st

cloud = cl.Cloud(cl.DEFAULT_CACHE, 'origin/main', True)
# HASH_CACHE lets a second concurrent run keep its own hash cache instead of locking the shared one.
hash_dir = pathlib.Path(os.environ['HASH_CACHE']) if os.environ.get('HASH_CACHE') else cloud.cache
hash_dir.mkdir(parents=True, exist_ok=True)
hashes = cl.open_hashes(hash_dir)
out = open(report_path, 'w', newline='', encoding='utf-8')
w = csv.writer(out, delimiter='\t')
w.writerow(['status', 'bytes', 'path', 'where'])
reparse = []
totals = collections.defaultdict(collections.Counter)
t0 = time.time(); n = 0; last = time.time()
for item in specs:
    label, root = item.split('=', 1)
    root = os.path.abspath(root)
    for full, st in walk_no_reparse(root, reparse):
        relp = os.path.relpath(full, root).replace('\\', '/')
        rel = relp if label == '' else f'@{label}/{relp}'
        if cloud.could_match(st.st_size) or rel in cloud.tree:
            sha, blob = cl.hash_file(hashes, full, rel, st, cloud.needs_blob(rel, st.st_size))
            status, where = cloud.classify(rel, st.st_size, sha, blob)
        else:
            status = 'changed' if cloud.releases_for_path(rel) else 'local-only'
            where = ''
        w.writerow([status, st.st_size, rel, where])
        totals[(label, status)]['files'] += 1
        totals[(label, status)]['bytes'] += st.st_size
        n += 1
        if time.time() - last > 30:
            hashes.commit(); last = time.time()
        if n % 50000 == 0:
            print(f'... {n} files {time.time() - t0:.0f}s', flush=True)
hashes.commit(); out.close()
with open(report_path + '.reparse.tsv', 'w', encoding='utf-8') as f:
    for p, t in reparse:
        f.write(f'{p}\t{t}\n')
print(f'done {n} files in {time.time() - t0:.0f}s; reparse points skipped: {len(reparse)}')
for (label, status), c in sorted(totals.items()):
    print(f'{label or "<project>":<24} {status:<20} {c["files"]:9d} files {c["bytes"] / 2**30:10.2f} GB')

"""Answer "is this file already in the cloud, and where?" for project paths.

The cloud is the GitHub repository tree at one Git ref plus every GitHub release.
Release contents come from each release's own RESEARCH_ASSETS.json.gz (and the PI
acquisition manifest); releases without a manifest are indexed per attachment.
The release manifests stay authoritative: `build` downloads them into a local,
Git-ignored cache and never commits a copy.

A local file counts as preserved only when identical bytes exist in the cloud.
Equal names or sizes never establish identity. This tool only reads files and
writes its own cache and report files; it never deletes, moves or edits project
content, and it does not decide what may be deleted.

Examples:
    python Tools/cloud_locator.py build
    python Tools/cloud_locator.py where Experiments/R152_R148v2_SafeAdaptivePSF/results/comparison
    python Tools/cloud_locator.py scan D:/GMM_2_Final/Experiments/R152_R148v2_SafeAdaptivePSF --git-ref d12dd7e0
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPO = 'rio10255254/GMM_2_Final'
DEFAULT_CACHE = REPO / '.cache' / 'cloud_locator'
PI_TAG = 'shared-pi-20260903-v1'
PI_ROOT = 'Shared_Sources/PI_Repeatability_20260903/'
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', '.cache'}
STATUSES = ['git', 'git-other-path', 'release', 'release-other-path', 'changed', 'local-only']


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True, encoding='utf-8').stdout


def git(*args):
    return subprocess.run(['git', '-C', str(REPO), '-c', 'core.quotepath=off', '-c', 'gc.auto=0', *args],
                          check=True, capture_output=True).stdout.decode('utf-8', 'replace')


def long_path(path):
    """Windows needs the \\\\?\\ prefix for the project's deepest result folders."""
    text = os.path.abspath(path)
    return '\\\\?\\' + text if os.name == 'nt' and not text.startswith('\\\\?\\') else text


def open_index(cache, create=False):
    cache.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(cache / 'index.sqlite')
    if create:
        db.executescript('''
            DROP TABLE IF EXISTS objects; DROP TABLE IF EXISTS assets; DROP TABLE IF EXISTS meta;
            CREATE TABLE objects(path TEXT, sha256 TEXT, bytes INTEGER, tag TEXT, asset TEXT, collection TEXT);
            CREATE TABLE assets(tag TEXT, name TEXT, bytes INTEGER, sha256 TEXT, indexed_by TEXT);
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    db.execute('CREATE TABLE IF NOT EXISTS hashes(path TEXT PRIMARY KEY, bytes INTEGER, mtime_ns INTEGER, sha256 TEXT, git_blob TEXT)')
    return db


def build(args):
    """Download every release manifest and merge them into the local index."""
    cache = Path(args.cache)
    manifests = cache / 'manifests'
    db = open_index(cache, create=True)
    releases = json.loads(gh('api', '--paginate', '--slurp', f'repos/{args.repo}/releases?per_page=100'))
    releases = [r for page in releases for r in page]
    for release in releases:
        tag = release['tag_name']
        names = {a['name'] for a in release['assets']}
        target = manifests / tag
        indexed = set()
        if 'RESEARCH_ASSETS.json.gz' in names:
            fetch(args.repo, tag, 'RESEARCH_ASSETS.json.gz', target)
            with gzip.open(target / 'RESEARCH_ASSETS.json.gz', 'rt', encoding='utf-8-sig') as stream:
                data = json.load(stream)
            db.executemany('INSERT INTO objects VALUES (?,?,?,?,?,?)',
                           ((r['path'], r['sha256'], r['bytes'], tag, r.get('asset'), r.get('collection'))
                            for r in data.get('files', [])))
            indexed = {r.get('asset') for r in data.get('files', [])}
        if tag == PI_TAG and 'ORIGINAL_ACQUISITION_MANIFEST.json' in names:
            fetch(args.repo, tag, 'ORIGINAL_ACQUISITION_MANIFEST.json', target)
            data = json.loads((target / 'ORIGINAL_ACQUISITION_MANIFEST.json').read_text(encoding='utf-8'))
            db.executemany('INSERT INTO objects VALUES (?,?,?,?,?,?)',
                           ((PI_ROOT + r['path'], r['sha256'], r['bytes'], tag, data['archive_name'], 'pi-acquisition')
                            for r in data['files']))
            indexed.add(data['archive_name'])
        for asset in release['assets']:
            digest = (asset.get('digest') or '').removeprefix('sha256:') or None
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?)',
                       (tag, asset['name'], asset['size'], digest, 'manifest' if asset['name'] in indexed else 'asset-only'))
        print(f'{tag}: {len(release["assets"])} assets', flush=True)
    db.execute('CREATE INDEX IF NOT EXISTS objects_path ON objects(path)')
    db.execute('CREATE INDEX IF NOT EXISTS objects_sha ON objects(sha256)')
    db.execute('CREATE INDEX IF NOT EXISTS objects_bytes ON objects(bytes)')
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built_utc', ?)", (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),))
    db.commit()
    total = db.execute('SELECT COUNT(*), COUNT(DISTINCT path), COUNT(DISTINCT sha256) FROM objects').fetchone()
    print(f'indexed {total[0]} release entries, {total[1]} paths, {total[2]} distinct contents from {len(releases)} releases')


def fetch(repo, tag, name, target):
    target.mkdir(parents=True, exist_ok=True)
    if not (target / name).exists():
        subprocess.run(['gh', 'release', 'download', tag, '--repo', repo, '--pattern', name, '--dir', str(target)],
                       check=True, capture_output=True)


class Cloud:
    """Lookups against the release index and one Git tree."""

    def __init__(self, cache, git_ref):
        self.db = open_index(Path(cache))
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='objects'").fetchone():
            raise SystemExit('No index yet. Run: python Tools/cloud_locator.py build')
        self.git_ref = git_ref
        self.tree, self.git_sizes, self.blobs = {}, set(), set()
        for line in git('ls-tree', '-r', '-l', '-z', git_ref).split('\0'):
            if not line:
                continue
            meta, path = line.split('\t', 1)
            _mode, kind, blob, size = meta.split()
            if kind == 'blob' and size.isdigit():
                self.tree[path] = blob
                self.git_sizes.add(int(size))
                self.blobs.add(blob)
        self.release_sizes = {row[0] for row in self.db.execute('SELECT DISTINCT bytes FROM objects')}

    def could_match(self, size):
        return size in self.git_sizes or size in self.release_sizes

    def releases_for_path(self, path):
        return self.db.execute('SELECT sha256, tag, asset FROM objects WHERE path=?', (path,)).fetchall()

    def releases_for_sha(self, sha):
        return self.db.execute('SELECT path, tag, asset FROM objects WHERE sha256=? LIMIT 3', (sha,)).fetchall()

    def classify(self, rel, size, sha, blob):
        """Return (status, where) for one local file whose project-relative path is rel."""
        if rel in self.tree and blob == self.tree[rel]:
            return 'git', f'{self.git_ref}:{rel}'
        same_path = self.releases_for_path(rel)
        if any(row[0] == sha for row in same_path):
            row = next(row for row in same_path if row[0] == sha)
            return 'release', f'{row[1]} / {row[2]}'
        if blob and blob in self.blobs:
            return 'git-other-path', f'{self.git_ref} (identical content at another path)'
        if sha:
            other = self.releases_for_sha(sha)
            if other:
                return 'release-other-path', f'{other[0][1]} / {other[0][2]} as {other[0][0]}'
        if rel in self.tree or same_path:
            return 'changed', 'cloud has this path with different bytes'
        return 'local-only', ''


def hash_file(db, full, rel, stat):
    """SHA-256 and Git blob id in one read; cached by size and last-write time."""
    row = db.execute('SELECT bytes, mtime_ns, sha256, git_blob FROM hashes WHERE path=?', (rel,)).fetchone()
    if row and row[0] == stat.st_size and row[1] == stat.st_mtime_ns:
        return row[2], row[3]
    sha, blob = hashlib.sha256(), hashlib.sha1(b'blob %d\0' % stat.st_size)
    with open(long_path(full), 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            sha.update(chunk)
            blob.update(chunk)
    result = sha.hexdigest(), blob.hexdigest()
    db.execute('INSERT OR REPLACE INTO hashes VALUES (?,?,?,?,?)', (rel, stat.st_size, stat.st_mtime_ns, *result))
    return result


def walk(root):
    for base, dirs, files in os.walk(long_path(root)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            yield os.path.join(base, name)


def relative(full, project_root):
    text = full.removeprefix('\\\\?\\')
    return PurePosixPath(Path(os.path.relpath(text, project_root)).as_posix()).as_posix()


def where(args):
    cloud = Cloud(args.cache, args.git_ref)
    for query in args.paths:
        rel = PurePosixPath(Path(query).as_posix()).as_posix().strip('/')
        in_git = [p for p in cloud.tree if p == rel or p.startswith(rel + '/')]
        rows = cloud.db.execute('SELECT path, tag, asset, bytes FROM objects WHERE path=? OR path LIKE ?',
                                (rel, rel + '/%')).fetchall()
        print(f'== {rel}')
        print(f'   git {args.git_ref}: {len(in_git)} files')
        groups = collections.defaultdict(lambda: [0, 0, set()])
        for _path, tag, asset, size in rows:
            groups[tag][0] += 1
            groups[tag][1] += size
            groups[tag][2].add(asset)
        for tag, (count, size, assets) in sorted(groups.items()):
            total = sum(r[0] or 0 for r in cloud.db.execute(
                f"SELECT bytes FROM assets WHERE tag=? AND name IN ({','.join('?' * len(assets))})", (tag, *assets)))
            print(f'   release {tag}: {count} files, {size / 2**20:.1f} MB; in {len(assets)} attachment(s), '
                  f'{total / 2**30:.2f} GB to download')
        local = Path(args.project_root) / rel
        if not in_git and not rows:
            print('   not in the cloud index' + (' (exists locally)' if os.path.exists(long_path(local)) else ''))
        # Name lookup only; `scan` compares contents before anything counts as preserved.
        known = set(in_git) | {r[0] for r in rows}
        missing = []
        candidates = [long_path(local)] if os.path.isfile(long_path(local)) else walk(local)
        for full in candidates:
            path = relative(full, os.path.abspath(args.project_root))
            if path not in known:
                missing.append((os.stat(full).st_size, path))
        if missing:
            print(f'   local files with no cloud entry at the same path: {len(missing)}, '
                  f'{sum(s for s, _ in missing) / 2**20:.1f} MB (run scan to compare contents)')
            for size, path in sorted(missing, reverse=True)[:args.list]:
                print(f'     {size / 2**20:9.1f} MB  {path}')


def scan(args):
    cloud = Cloud(args.cache, args.git_ref)
    project_root = os.path.abspath(args.project_root)
    totals = collections.defaultdict(lambda: collections.Counter())
    by_dir = collections.defaultdict(lambda: collections.Counter())
    report = open(args.report, 'w', newline='', encoding='utf-8') if args.report else None
    writer = csv.writer(report, delimiter='\t') if report else None
    if writer:
        writer.writerow(['status', 'bytes', 'path', 'where'])
    started, count = time.time(), 0
    for root in args.roots:
        for full in walk(root):
            try:
                stat = os.stat(full)
            except OSError:
                continue
            rel = relative(full, project_root)
            if cloud.could_match(stat.st_size) or rel in cloud.tree:
                sha, blob = hash_file(cloud.db, full, rel, stat)
                status, location = cloud.classify(rel, stat.st_size, sha, blob)
            else:
                # No cloud object has this size, so the bytes cannot be there; hashing is unnecessary.
                status = 'changed' if cloud.releases_for_path(rel) else 'local-only'
                location = 'cloud has this path with different bytes' if status == 'changed' else ''
            totals[status]['files'] += 1
            totals[status]['bytes'] += stat.st_size
            key = '/'.join(rel.split('/')[:args.depth])
            by_dir[key][status] += stat.st_size
            if writer:
                writer.writerow([status, stat.st_size, rel, location])
            count += 1
            if count % 20000 == 0:
                cloud.db.commit()
                print(f'... {count} files, {time.time() - started:.0f}s', flush=True)
    cloud.db.commit()
    if report:
        report.close()
    print(f'\nscanned {count} files against {args.git_ref} and the release index')
    for status in STATUSES:
        t = totals[status]
        print(f'{status:<20} {t["files"]:9d} files {t["bytes"] / 2**30:10.2f} GB')
    print('\nnot yet in the cloud (local-only + changed), by folder:')
    rows = sorted(by_dir.items(), key=lambda kv: -(kv[1]['local-only'] + kv[1]['changed']))
    for key, c in rows[:args.top]:
        pending = c['local-only'] + c['changed']
        if pending:
            print(f'{pending / 2**30:9.2f} GB  {key}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cache', default=str(DEFAULT_CACHE))
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build', help='download release manifests and build the index')
    p.add_argument('--repo', default=DEFAULT_REPO)
    p.set_defaults(func=build)
    for name, func, help_text in [('where', where, 'show where project paths are kept'),
                                  ('scan', scan, 'classify every file under local folders')]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument('--git-ref', default='HEAD', help='Git tree treated as the cloud (e.g. origin/main)')
        p.add_argument('--project-root', default=str(REPO), help='root that project-relative paths start from')
        p.set_defaults(func=func)
    sub.choices['where'].add_argument('paths', nargs='+', help='project-relative paths')
    sub.choices['where'].add_argument('--list', type=int, default=10, help='how many uncovered local files to show')
    s = sub.choices['scan']
    s.add_argument('roots', nargs='+', help='local folders to scan')
    s.add_argument('--depth', type=int, default=2, help='folder depth for the summary')
    s.add_argument('--top', type=int, default=40)
    s.add_argument('--report', help='write every file and its status to this TSV')
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    sys.exit(main())

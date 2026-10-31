"""Release manifests follow the 2026-10-28 folder restructure.

Each release keeps its content as objects named by sha256; its RESEARCH_ASSETS.json.gz says where
each object restores to in the project. After folders moved (phases 2-4) and git files were rewritten
(phases 1-4), a manifest that is not updated restores files to old places, and the cloud index cannot
find them under their new paths.

plan    downloads every release's manifest and writes, for each affected release, the new manifest:
        each path mapped by the phase 2-4 move rules. A record whose content is exactly what git held
        at that path before the restructure, and which git has since rewritten, now points at the
        rewritten content, packed as an added object in <tag>.restructure-20261028.zip. Content git
        never had keeps its bytes. Which records change is decided path by path from the two git
        trees; the hash chain of the phase records is only a cross-check, reported, because one old
        content rewritten two ways at two paths is one entry there.
apply   renames the release's manifest, BUNDLE_SUMMARY.json and SHA256SUMS.txt to *.pre-restructure-
        20261028.* (bytes unchanged), uploads the added zip and the new files, and checks GitHub's
        sha256 of each. Any failure deletes what this run uploaded and renames the originals back.
verify  downloads the new manifest, restores a sample (every added object plus moved paths from the
        smallest attachments) and checks each file lands at its new path with its recorded sha256.

Every GitHub call goes through `run`, so tests replace it. Nothing here deletes a file that this tool
did not upload in the same run.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from restructure_rules import compose, load_rules  # noqa: E402
import research_asset_bundle as bundle  # noqa: E402
from research_recovery import write_json  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RECORDS = REPO / 'docs' / 'operations' / 'TREE_RESTRUCTURE_20261028'
BASE_REF = '20b0d56d62a8c70854ffb11b396d171110d0d9e4'   # main just before phase 1
MOVE_PHASES = (2, 3, 4)
REWRITE_PHASES = (1, 2, 3, 4)
MANIFEST, SUMMARY, SUMS = 'RESEARCH_ASSETS.json.gz', 'BUNDLE_SUMMARY.json', 'SHA256SUMS.txt'
RENAMED = {MANIFEST: 'RESEARCH_ASSETS.pre-restructure-20261028.json.gz',
           SUMMARY: 'BUNDLE_SUMMARY.pre-restructure-20261028.json',
           SUMS: 'SHA256SUMS.pre-restructure-20261028.txt'}
COLLECTION = 'restructure-20261028'
MISSING = object()


class UploadFailed(RuntimeError):
    pass


def added_zip(tag):
    return f'{tag}.restructure-20261028.zip'


READ_TIMEOUT = 600
WRITE_TIMEOUT = 3600
READ_ATTEMPTS = 3


def _is_read(args):
    return (args[:2] == ['release', 'download'] or args[:2] == ['release', 'view']
            or (args[:1] == ['api'] and '-X' not in args))


def gh(args, runner=subprocess.run):
    """Run gh with a timeout. A 2026-10-30 plan sat fifteen hours on one download that never answered,
    so reads are retried; writes are not, because a repeated upload could meet its own half-finished
    copy, and apply_one's rollback already handles a failed write."""
    read = _is_read(args)
    attempts = READ_ATTEMPTS if read else 1
    for attempt in range(attempts):
        try:
            result = runner(['gh', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=READ_TIMEOUT if read else WRITE_TIMEOUT)
            break
        except subprocess.TimeoutExpired:
            if attempt == attempts - 1:
                raise RuntimeError('gh ' + ' '.join(args[:3]) + f' timed out {attempts} time(s)')
    if result.returncode:
        raise RuntimeError('gh ' + ' '.join(args[:3]) + ' failed: ' + result.stderr.decode('utf-8', 'replace')[-300:])
    return result.stdout.decode('utf-8')


def git_env():
    """The environment without GIT_* variables. git runs hooks with GIT_DIR and GIT_INDEX_FILE set, and
    `git -C <repo>` follows them, so a call meant for one repository would act on another."""
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# ---------- plan ----------
def plan_one(tag, manifest, rules, rewritten, chain=None):
    """The new manifest for one release. `rewritten(old_path, new_path, sha)` returns (sha, bytes) when
    git held this content at old_path before the restructure and rewrote it, MISSING when the rewritten
    file is not in the new tree, else None. `chain(sha)` is the phase records' final sha, or None."""
    zip_name = added_zip(tag)
    files, added, seen = [], {}, {}
    paths_changed = replaced = 0
    disagreements = []
    for row in manifest['files']:
        old = row['path']
        new = rules.map(old) or old
        res = rewritten(old, new, row['sha256'])
        if res is MISSING:
            raise ValueError(f'{tag}: {old}: git held this content and rewrote it, but {new} is not in the new tree')
        rec = dict(row, path=new)
        if res:
            rec.update(sha256=res[0], bytes=res[1], asset=zip_name)
            added.setdefault(res[0], new)
            replaced += 1
        if chain is not None and chain(row['sha256']) != (res[0] if res else None):
            disagreements.append(old)
        key = new.casefold()
        if key in seen:
            raise ValueError(f'{tag}: {seen[key]} and {old} land on the same path {new}')
        seen[key] = old
        paths_changed += new != old
        files.append(rec)
    out = {'tag': tag, 'paths': len(files), 'paths_changed': paths_changed, 'records_replaced': replaced,
           'objects_added': len(added), 'hash_chain_disagreements': disagreements}
    if not paths_changed and not added:
        return {**out, 'status': 'unchanged'}
    old_shas = {r['sha256'] for r in manifest['files']}
    equal = all(n['sha256'] == o['sha256'] or n['sha256'] in added for n, o in zip(files, manifest['files']))
    equal = equal and {r['sha256'] for r in files} - set(added) <= old_shas
    return {**out, 'status': 'changed', 'sha_sets_equal_except_added': equal,
            'manifest': {**manifest, 'files': files}, 'added': added}


def new_sha256sums(old_text, new, old_sums_sha):
    """SHA256SUMS.txt after apply: old lines, the renamed originals, the new files and the added zip."""
    sums = {}
    for line in old_text.splitlines():
        if not line.strip():
            continue
        h, name = line.split('  ', 1)
        if name in RENAMED:
            sums[RENAMED[name]] = h
        sums[name] = new.get(name, h)
    for name, h in new.items():
        if name != SUMS:
            sums[name] = h
    sums[RENAMED[SUMS]] = old_sums_sha
    sums.pop(SUMS, None)
    return ''.join(f'{h}  {n}\n' for n, h in sorted(sums.items(), key=lambda kv: kv[0].casefold()))


def write_plan(plan_dir, tag, s, old_assets, read_new):
    """Write the new files of one changed release into plan_dir/tag. `old_assets`: {name: bytes} of the
    release's current manifest files; `read_new(path)`: the rewritten content git now holds there."""
    d = Path(plan_dir) / tag
    d.mkdir(parents=True)
    manifest = json.loads(json.dumps(s['manifest']))
    if s['added']:
        name = added_zip(tag)
        with zipfile.ZipFile(d / name, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
            for h, path in sorted(s['added'].items()):
                data = read_new(path)
                if sha256(data) != h:
                    raise ValueError(f'{tag}: {path} no longer holds {h}')
                z.writestr('objects/' + h, data)
        manifest['assets'].append({'name': name, 'bytes': (d / name).stat().st_size, 'sha256': bundle.digest(d / name),
                                   'objects': len(s['added']), 'collection': COLLECTION})
    unique = {r['sha256']: r['bytes'] for r in manifest['files']}
    manifest.update(paths=len(manifest['files']), unique_objects=len(unique), unique_bytes=sum(unique.values()),
                    original_bytes=sum(r['bytes'] for r in manifest['files']),
                    packed_bytes=sum(a['bytes'] for a in manifest['assets']))
    with gzip.GzipFile(d / MANIFEST, 'wb', mtime=0) as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    new = {MANIFEST: bundle.digest(d / MANIFEST)}
    if s['added']:
        new[added_zip(tag)] = bundle.digest(d / added_zip(tag))
    if SUMMARY in old_assets:
        write_json(d / SUMMARY, {k: v for k, v in manifest.items() if k != 'files'})
        new[SUMMARY] = bundle.digest(d / SUMMARY)
    if SUMS in old_assets:
        text = new_sha256sums(old_assets[SUMS].decode('utf-8'), new, sha256(old_assets[SUMS]))
        (d / SUMS).write_bytes(text.encode('utf-8'))
        new[SUMS] = bundle.digest(d / SUMS)
    report = {k: v for k, v in s.items() if k not in ('manifest', 'added')}
    report['hash_chain_disagreements'] = {'count': len(s['hash_chain_disagreements']),
                                          'first': s['hash_chain_disagreements'][:50]}
    report['added'] = [{'sha256': h, 'path': p} for h, p in sorted(s['added'].items(), key=lambda kv: kv[1])]
    report['old_assets'] = {n: sha256(v) for n, v in old_assets.items()}
    report['new_assets'] = new
    write_json(d / 'summary.json', report)
    return report


class GitTree:
    """sha1 of every blob in one commit, and sha256/bytes of blobs read on demand."""

    def __init__(self, ref, repo=REPO):
        self.repo = repo
        out = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), 'ls-tree', '-r', '-z', ref],
                             capture_output=True, check=True, env=git_env()).stdout.decode('utf-8')
        self.blobs = {}
        for item in filter(None, out.split('\0')):
            meta, path = item.split('\t', 1)
            if meta.split()[1] == 'blob':
                self.blobs[path] = meta.split()[2]
        self._sha256 = {}

    def read(self, path):
        return subprocess.run(['git', '-C', str(self.repo), 'cat-file', 'blob', self.blobs[path]],
                              capture_output=True, check=True, env=git_env()).stdout

    def sha256_of(self, paths):
        """Fill the sha256 cache for these paths with one `git cat-file --batch`."""
        todo = sorted({self.blobs[p] for p in paths if p in self.blobs} - set(self._sha256))
        if not todo:
            return
        proc = subprocess.Popen(['git', '-C', str(self.repo), 'cat-file', '--batch'],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=git_env())
        proc.stdin.write(''.join(s + '\n' for s in todo).encode())
        proc.stdin.close()
        for s in todo:
            header = proc.stdout.readline().split()
            size = int(header[2])
            data = proc.stdout.read(size)
            proc.stdout.read(1)
            self._sha256[s] = (sha256(data), size)
        proc.wait()

    def content(self, path):
        return self._sha256[self.blobs[path]]


def hash_chain():
    """sha before phase 1 -> sha after phase 4, from the phase records."""
    steps = [json.loads((RECORDS / f'hash_changes_phase{n}.json').read_text(encoding='utf-8'))['changes']
             for n in REWRITE_PHASES]

    def final(h):
        start = h
        for changes in steps:
            h = changes.get(h, h)
        return None if h == start else h
    return final


def git_rewritten(base, head, manifest, rules):
    """The `rewritten` function plan_one takes, backed by the two git trees."""
    pairs = [(r['path'], rules.map(r['path']) or r['path']) for r in manifest['files']]
    pairs = [(o, n) for o, n in pairs if o in base.blobs and base.blobs[o] != head.blobs.get(n)]
    base.sha256_of(o for o, _ in pairs)
    head.sha256_of(n for _, n in pairs)
    candidates = {o for o, _ in pairs}

    def rewritten(old, new, sha):
        if old not in candidates or base.content(old)[0] != sha:
            return None
        if new not in head.blobs:
            return MISSING
        return head.content(new)
    return rewritten


def download_meta(repo, release, folder, run):
    """The release's manifest files, checked against GitHub's sha256: {name: bytes}."""
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for asset in release['assets']:
        if asset['name'] in (MANIFEST, SUMMARY, SUMS):
            run(['release', 'download', release['tag_name'], '--repo', repo, '--pattern', asset['name'],
                 '--dir', str(folder), '--clobber'])
            data = (folder / asset['name']).read_bytes()
            if asset.get('digest') and asset['digest'] != 'sha256:' + sha256(data):
                raise ValueError(f"{release['tag_name']}: downloaded {asset['name']} differs from GitHub's sha256")
            out[asset['name']] = data
    return out


def plan_all(repo, out, run=gh, head_ref='HEAD'):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('Use a new plan folder')
    releases = json.loads(run(['api', f'repos/{repo}/releases?per_page=100']))
    if len(releases) >= 100:
        raise ValueError('More than one page of releases; extend the listing first')
    rules = compose([load_rules(RECORDS / f'moves_phase{n}.json') for n in MOVE_PHASES])
    base, head, chain = GitTree(BASE_REF), GitTree(head_ref), hash_chain()
    table = []
    for rel in sorted(releases, key=lambda r: r['tag_name']):
        tag = rel['tag_name']
        if rel['draft'] or not any(a['name'] == MANIFEST for a in rel['assets']):
            table.append({'tag': tag, 'status': 'draft' if rel['draft'] else 'no manifest'})
            continue
        meta = download_meta(repo, rel, out / '_current' / tag, run)
        manifest = json.loads(gzip.decompress(meta[MANIFEST]))
        s = plan_one(tag, manifest, rules, git_rewritten(base, head, manifest, rules), chain)
        if s['status'] == 'changed':
            report = write_plan(out, tag, s, meta, head.read)
            table.append({k: report[k] for k in ('tag', 'status', 'paths', 'paths_changed', 'records_replaced',
                                                 'objects_added', 'sha_sets_equal_except_added')}
                         | {'hash_chain_disagreements': report['hash_chain_disagreements']['count']})
        else:
            table.append({k: v for k, v in s.items() if k != 'hash_chain_disagreements'})
        print(json.dumps(table[-1], ensure_ascii=False), flush=True)
    write_json(out / 'PLAN.json', {'repo': repo, 'base': BASE_REF,
                                   'head': subprocess.run(['git', '-C', str(REPO), 'rev-parse', head_ref],
                                                          capture_output=True, text=True, env=git_env()).stdout.strip(),
                                   'releases': table})
    return table


# ---------- apply ----------
def _release(repo, tag, run):
    return json.loads(run(['api', f'repos/{repo}/releases/tags/{tag}']))


def _rename(repo, asset_id, name, run):
    run(['api', '-X', 'PATCH', f'repos/{repo}/releases/assets/{asset_id}', '-f', f'name={name}'])


def apply_one(repo, tag, plan_dir, run=gh):
    d = Path(plan_dir) / tag
    s = json.loads((d / 'summary.json').read_text(encoding='utf-8'))
    if s['status'] != 'changed':
        return {'tag': tag, 'status': 'unchanged'}
    rel = _release(repo, tag, run)
    by_name = {a['name']: a for a in rel['assets']}
    if any(n in by_name for n in RENAMED.values()):
        raise ValueError(f'{tag}: already holds a pre-restructure copy; apply ran before')
    for name, h in s['old_assets'].items():
        if name not in by_name or by_name[name].get('digest') != 'sha256:' + h:
            raise ValueError(f'{tag}: {name} changed since the plan; plan again')
    if added_zip(tag) in by_name:
        raise ValueError(f'{tag}: {added_zip(tag)} already exists')
    original_ids = {a['id'] for a in rel['assets']}
    renamed = []
    order = sorted(s['new_assets'], key=lambda n: (n != added_zip(tag), n == SUMS))
    try:
        for name in s['old_assets']:
            _rename(repo, by_name[name]['id'], RENAMED[name], run)
            renamed.append((by_name[name]['id'], name))
        for name in order:
            run(['release', 'upload', tag, str(d / name), '--repo', repo])
        now = {a['name']: a for a in _release(repo, tag, run)['assets']}
        for name, h in s['new_assets'].items():
            if now.get(name, {}).get('digest') != 'sha256:' + h:
                raise UploadFailed(f'{tag}: GitHub sha256 of {name} does not match')
        for name, h in s['old_assets'].items():
            if now.get(RENAMED[name], {}).get('digest') != 'sha256:' + h:
                raise UploadFailed(f'{tag}: renamed {RENAMED[name]} changed')
    except Exception as e:
        now = _release(repo, tag, run)['assets']
        for a in now:
            if a['id'] not in original_ids and a['name'] in s['new_assets']:
                run(['api', '-X', 'DELETE', f"repos/{repo}/releases/assets/{a['id']}"])
        for asset_id, name in reversed(renamed):
            _rename(repo, asset_id, name, run)
        raise UploadFailed(f'{tag}: {e}; this run\'s uploads deleted and original names restored') from e
    result = {'tag': tag, 'status': 'applied', 'renamed': {n: RENAMED[n] for n in s['old_assets']},
              'uploaded': s['new_assets']}
    write_json(d / 'applied.json', result)
    return result


# ---------- verify ----------
def choose_sample(old_files, new_files, assets, size, seed):
    """Every record pointing at the added zip, plus up to `size` moved records taken from the smallest
    attachments that hold moved records."""
    picked = [i for i, r in enumerate(new_files) if r['asset'].endswith('.restructure-20261028.zip')]
    moved = [i for i, (o, n) in enumerate(zip(old_files, new_files)) if o['path'] != n['path'] and i not in picked]
    by_asset = {}
    for i in moved:
        by_asset.setdefault(new_files[i]['asset'], []).append(i)
    rng = random.Random(seed)
    chosen = []
    for name in sorted(by_asset, key=lambda n: assets[n]['bytes']):
        if len(chosen) >= size:
            break
        pool = by_asset[name]
        chosen += rng.sample(pool, min(len(pool), size - len(chosen)))
    return sorted(set(picked + chosen))


def verify_one(repo, tag, plan_dir, sample, work, run=gh):
    d = Path(plan_dir) / tag
    s = json.loads((d / 'summary.json').read_text(encoding='utf-8'))
    work = Path(work) / tag
    if work.exists():
        raise FileExistsError('Use a new verify folder')
    dl = work / 'download'
    dl.mkdir(parents=True)
    now = {a['name']: a for a in _release(repo, tag, run)['assets']}
    problems = []
    for name, h in s['new_assets'].items():
        if now.get(name, {}).get('digest') != 'sha256:' + h:
            problems.append(f'{name} on GitHub is not the planned file')
    for name, h in s['old_assets'].items():
        if now.get(RENAMED[name], {}).get('digest') != 'sha256:' + h:
            problems.append(f'{RENAMED[name]} is missing or changed')
    run(['release', 'download', tag, '--repo', repo, '--pattern', MANIFEST, '--dir', str(dl)])
    if bundle.digest(dl / MANIFEST) != s['new_assets'][MANIFEST]:
        problems.append('downloaded manifest differs from the plan')
    new = json.loads(gzip.decompress((dl / MANIFEST).read_bytes()))
    old = json.loads(gzip.decompress((Path(plan_dir) / '_current' / tag / MANIFEST).read_bytes()))
    rules = compose([load_rules(RECORDS / f'moves_phase{n}.json') for n in MOVE_PHASES])
    for o, n in zip(old['files'], new['files']):
        if n['path'] != (rules.map(o['path']) or o['path']):
            problems.append(f"{o['path']} restores to {n['path']}")
            break
    assets = {a['name']: a for a in new['assets']}
    picked = choose_sample(old['files'], new['files'], assets, sample, tag)
    rows = [new['files'][i] for i in picked]
    needed = sorted({r['asset'] for r in rows})
    for name in needed:
        run(['release', 'download', tag, '--repo', repo, '--pattern', name, '--dir', str(dl)])
    sub = {**new, 'files': rows, 'assets': [assets[n] for n in needed]}
    with gzip.open(work / 'sample.json.gz', 'wt', encoding='utf-8') as stream:
        json.dump(sub, stream, ensure_ascii=False)
    restored = bundle.restore(work / 'sample.json.gz', dl, work / 'restored')
    for r in rows:
        target = work / 'restored' / r['path']
        if not target.is_file() or bundle.digest(target) != r['sha256']:
            problems.append(f"{r['path']} did not restore with its sha256")
    report = {'tag': tag, 'status': 'PASS' if not problems else 'FAIL', 'problems': problems,
              'sampled': len(rows), 'added_objects_sampled': sum(r['asset'] == added_zip(tag) for r in rows),
              'attachments_downloaded': needed, 'restore': restored}
    write_json(d / 'verify.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('plan'); a.add_argument('--repo', required=True); a.add_argument('--out', required=True)
    a = sub.add_parser('apply'); a.add_argument('--repo', required=True); a.add_argument('--tag', required=True)
    a.add_argument('--plan-dir', required=True)
    a = sub.add_parser('verify'); a.add_argument('--repo', required=True); a.add_argument('--tag', required=True)
    a.add_argument('--plan-dir', required=True); a.add_argument('--sample', type=int, default=20)
    a.add_argument('--work', required=True)
    args = p.parse_args()
    if args.cmd == 'plan':
        plan_all(args.repo, args.out)
    elif args.cmd == 'apply':
        print(json.dumps(apply_one(args.repo, args.tag, args.plan_dir), ensure_ascii=False, indent=1))
    else:
        report = verify_one(args.repo, args.tag, args.plan_dir, args.sample, args.work)
        print(json.dumps({k: v for k, v in report.items() if k != 'restore'}, ensure_ascii=False, indent=1))
        sys.exit(report['status'] != 'PASS')


if __name__ == '__main__':
    main()

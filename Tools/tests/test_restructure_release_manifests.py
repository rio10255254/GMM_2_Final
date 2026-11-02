"""Release manifests follow the folder restructure: paths move, rewritten git files become added objects."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restructure_rules import Rule, RuleSet
import research_asset_bundle as bundle
import restructure_release_manifests as rm

RULES = RuleSet([Rule('Validations', 'Deliverables/Validations'), Rule('Traing_Progress', 'Experiments/Legacy')])
OLD, NEW, OTHER = 'a' * 64, 'b' * 64, 'c' * 64


def manifest(*rows):
    files = [{'path': p, 'bytes': n, 'sha256': s, 'asset': 'research-x-001.zip'} for p, s, n in rows]
    return {'schema': 1, 'state': 'complete', 'files': files,
            'assets': [{'name': 'research-x-001.zip', 'bytes': 99, 'sha256': 'd' * 64, 'objects': len(files), 'collection': 'x'}],
            'paths': len(files), 'unique_objects': len({s for _, s, _ in rows}),
            'original_bytes': sum(n for _, _, n in rows), 'unique_bytes': 0, 'packed_bytes': 99}


def rewritten_from(table):
    """table: {(old_path, new_path): (sha, bytes) or rm.MISSING} for files git had with the release's content"""
    return lambda old, new, sha: table.get((old, new))


def test_plan_maps_paths_and_adds_rewritten_objects():
    m = manifest(('Validations/a.json', OLD, 800), ('Validations/b.bin', OTHER, 5), ('Model/x.py', OTHER, 5))
    s = rm.plan_one('T', m, RULES, rewritten_from({('Validations/a.json', 'Deliverables/Validations/a.json'): (NEW, 812)}))
    assert s['status'] == 'changed'
    assert s['paths_changed'] == 2 and s['objects_added'] == 1 and s['sha_sets_equal_except_added']
    rec = next(r for r in s['manifest']['files'] if r['path'] == 'Deliverables/Validations/a.json')
    assert (rec['sha256'], rec['bytes'], rec['asset']) == (NEW, 812, 'T.restructure-20261028.zip')
    assert s['added'] == {NEW: 'Deliverables/Validations/a.json'}
    assert next(r for r in s['manifest']['files'] if r['path'] == 'Deliverables/Validations/b.bin')['sha256'] == OTHER


def test_release_version_that_git_never_had_keeps_its_bytes():
    m = manifest(('Traing_Progress/run/log.txt', OLD, 10))
    s = rm.plan_one('T', m, RULES, rewritten_from({}))
    assert s['paths_changed'] == 1 and s['objects_added'] == 0
    assert s['manifest']['files'][0] == {**m['files'][0], 'path': 'Experiments/Legacy/run/log.txt'}


def test_unaffected_release_untouched():
    s = rm.plan_one('T', manifest(('Model/x.py', OTHER, 5)), RULES, rewritten_from({}))
    assert s['status'] == 'unchanged' and 'manifest' not in s


def test_two_records_landing_on_one_path_are_refused():
    m = manifest(('Validations/a.json', OLD, 1), ('Deliverables/Validations/A.json', OTHER, 1))
    with pytest.raises(ValueError, match='same path'):
        rm.plan_one('T', m, RULES, rewritten_from({}))


def test_rewritten_file_gone_from_the_new_tree_is_refused():
    m = manifest(('Validations/a.json', OLD, 1))
    with pytest.raises(ValueError, match='not in the new tree'):
        rm.plan_one('T', m, RULES, rewritten_from({('Validations/a.json', 'Deliverables/Validations/a.json'): rm.MISSING}))


def test_hash_chain_disagreement_is_reported_not_hidden():
    m = manifest(('Validations/a.json', OLD, 800), ('Model/copy.json', OLD, 800))
    rew = rewritten_from({('Validations/a.json', 'Deliverables/Validations/a.json'): (NEW, 812)})
    s = rm.plan_one('T', m, RULES, rew, chain=lambda sha: NEW if sha == OLD else None)
    assert s['hash_chain_disagreements'] == ['Model/copy.json']


def test_new_manifest_restores_at_new_paths(tmp_path):
    # a real bundle made by the packer, then the restructure, then a restore from the new manifest
    src = tmp_path / 'src'
    (src / 'Validations').mkdir(parents=True)
    (src / 'Validations/a.json').write_bytes(b'{"p": "Validations/b.bin"}\n')
    (src / 'Validations/b.bin').write_bytes(b'\x00\x01')
    sel = tmp_path / 'sel.json'
    sel.write_text(json.dumps({'reviewed': True, 'files': [{'path': 'Validations/a.json'}, {'path': 'Validations/b.bin'}]}))
    out = tmp_path / 'bundle'
    bundle.pack(src, sel, out, 10_000_000)
    old = json.loads(gzip.open(out / 'RESEARCH_ASSETS.json.gz').read())
    now = b'{"p": "Deliverables/Validations/b.bin"}\n'
    sha_a = hashlib.sha256((src / 'Validations/a.json').read_bytes()).hexdigest()
    new_sha = hashlib.sha256(now).hexdigest()
    rew = rewritten_from({('Validations/a.json', 'Deliverables/Validations/a.json'): (new_sha, len(now))})
    s = rm.plan_one('T', old, RULES, rew)
    assert s['added'] == {new_sha: 'Deliverables/Validations/a.json'} and sha_a != new_sha
    plan = tmp_path / 'plan'
    rm.write_plan(plan, 'T', s, {}, read_new=lambda path: now)
    report = bundle.restore(plan / 'T' / 'RESEARCH_ASSETS.json.gz', out_assets(out, plan / 'T'), tmp_path / 'restored')
    assert report['files_restored_and_verified'] == 2
    assert (tmp_path / 'restored/Deliverables/Validations/a.json').read_bytes() == now
    assert (tmp_path / 'restored/Deliverables/Validations/b.bin').read_bytes() == b'\x00\x01'


def out_assets(bundle_dir, plan_tag_dir):
    """One folder holding the release's original zips plus the added one, as a download would."""
    d = plan_tag_dir / 'all_assets'
    d.mkdir()
    for z in list(bundle_dir.glob('*.zip')) + list(plan_tag_dir.glob('*.zip')):
        (d / z.name).write_bytes(z.read_bytes())
    return d


def test_sha256sums_keep_old_lines_and_list_new_and_renamed_assets():
    old = f"{'1' * 64}  BUNDLE_SUMMARY.json\n{'2' * 64}  research-x-001.zip\n{'3' * 64}  RESEARCH_ASSETS.json.gz\n"
    new = rm.new_sha256sums(old, {'RESEARCH_ASSETS.json.gz': '4' * 64, 'BUNDLE_SUMMARY.json': '5' * 64,
                                  'T.restructure-20261028.zip': '6' * 64}, old_sums_sha='7' * 64)
    lines = dict(reversed(line.split('  ', 1)) for line in new.splitlines())
    assert lines['RESEARCH_ASSETS.json.gz'] == '4' * 64 and lines['RESEARCH_ASSETS.pre-restructure-20261028.json.gz'] == '3' * 64
    assert lines['BUNDLE_SUMMARY.pre-restructure-20261028.json'] == '1' * 64
    assert lines['SHA256SUMS.pre-restructure-20261028.txt'] == '7' * 64
    assert lines['research-x-001.zip'] == '2' * 64 and lines['T.restructure-20261028.zip'] == '6' * 64
    assert new.endswith('\n') and 'SHA256SUMS.txt' not in lines


class FakeGH:
    """A release's assets as GitHub holds them; `fail_upload` makes that upload fail."""

    def __init__(self, assets, fail_upload=None):
        self.assets = {i: dict(a, id=i) for i, a in enumerate(assets, 1)}
        self.next_id = 100
        self.fail_upload = fail_upload
        self.calls = []

    def asset_names(self):
        return sorted(a['name'] for a in self.assets.values())

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ['api', 'repos/o/r/releases/tags/T']:
            return json.dumps({'assets': list(self.assets.values()), 'draft': False})
        if args[:3] == ['api', '-X', 'PATCH']:
            i = int(args[3].rsplit('/', 1)[1])
            new = args[5].split('=', 1)[1]
            if any(a['name'] == new for a in self.assets.values()):
                raise RuntimeError('name taken')
            self.assets[i]['name'] = new
            return '{}'
        if args[:3] == ['api', '-X', 'DELETE']:
            del self.assets[int(args[3].rsplit('/', 1)[1])]
            return ''
        if args[:2] == ['release', 'upload']:
            path = Path(args[3])
            if path.name == self.fail_upload:
                raise RuntimeError('upload failed')
            self.next_id += 1
            self.assets[self.next_id] = {'id': self.next_id, 'name': path.name, 'size': path.stat().st_size,
                                         'digest': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()}
            return ''
        raise AssertionError(args)


def planned_release(tmp_path):
    """A plan folder for tag T and the release it was planned from."""
    old_files = {'RESEARCH_ASSETS.json.gz': b'old manifest', 'BUNDLE_SUMMARY.json': b'old summary',
                 'SHA256SUMS.txt': b'old sums', 'research-x-001.zip': b'zip'}
    gh = FakeGH([{'name': n, 'size': len(d), 'digest': 'sha256:' + hashlib.sha256(d).hexdigest()} for n, d in old_files.items()])
    d = tmp_path / 'plan' / 'T'
    d.mkdir(parents=True)
    new_files = {'RESEARCH_ASSETS.json.gz': b'new manifest', 'BUNDLE_SUMMARY.json': b'new summary',
                 'SHA256SUMS.txt': b'new sums', 'T.restructure-20261028.zip': b'added'}
    for n, data in new_files.items():
        (d / n).write_bytes(data)
    summary = {'tag': 'T', 'status': 'changed',
               'old_assets': {n: hashlib.sha256(v).hexdigest() for n, v in old_files.items() if n != 'research-x-001.zip'},
               'new_assets': {n: hashlib.sha256(v).hexdigest() for n, v in new_files.items()}}
    (d / 'summary.json').write_text(json.dumps(summary))
    return gh, tmp_path / 'plan', old_files, new_files


def test_apply_renames_old_and_uploads_new(tmp_path):
    gh, plan, old, new = planned_release(tmp_path)
    rm.apply_one('o/r', 'T', plan, run=gh)
    names = gh.asset_names()
    assert set(new) <= set(names)
    assert {'RESEARCH_ASSETS.pre-restructure-20261028.json.gz', 'BUNDLE_SUMMARY.pre-restructure-20261028.json',
            'SHA256SUMS.pre-restructure-20261028.txt', 'research-x-001.zip'} <= set(names)
    kept = {a['name']: a['digest'] for a in gh.assets.values()}
    assert kept['RESEARCH_ASSETS.pre-restructure-20261028.json.gz'] == 'sha256:' + hashlib.sha256(old['RESEARCH_ASSETS.json.gz']).hexdigest()


def test_apply_renames_back_on_upload_failure(tmp_path):
    gh, plan, old, new = planned_release(tmp_path)
    gh.fail_upload = 'RESEARCH_ASSETS.json.gz'
    with pytest.raises(rm.UploadFailed):
        rm.apply_one('o/r', 'T', plan, run=gh)
    assert gh.asset_names() == sorted(old)


def test_apply_refuses_a_release_that_changed_since_the_plan(tmp_path):
    gh, plan, old, new = planned_release(tmp_path)
    next(a for a in gh.assets.values() if a['name'] == 'RESEARCH_ASSETS.json.gz')['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError, match='changed since'):
        rm.apply_one('o/r', 'T', plan, run=gh)
    assert not any(c[:3] == ['api', '-X', 'PATCH'] for c in gh.calls)


def _git(repo, *args):
    import subprocess
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'core.autocrlf=false', *args],
                   check=True, capture_output=True, env=rm.git_env())


def test_git_rewritten_decides_path_by_path(tmp_path):
    repo = tmp_path / 'r'
    (repo / 'Validations').mkdir(parents=True)
    _git(repo, 'init', '-q')
    a, copy = b'see Validations/b.bin\n', b'see Validations/b.bin\n'
    (repo / 'Validations/a.json').write_bytes(a)
    (repo / 'Validations/same.txt').write_bytes(b'unchanged\n')
    (repo / 'copy.json').write_bytes(copy)
    _git(repo, 'add', '-A'); _git(repo, 'commit', '-qm', 'base')
    _git(repo, 'mv', 'Validations', 'Deliverables_tmp'); (repo / 'Deliverables').mkdir()
    _git(repo, 'mv', 'Deliverables_tmp', 'Deliverables/Validations')
    now = b'see Deliverables/Validations/b.bin\n'
    (repo / 'Deliverables/Validations/a.json').write_bytes(now)
    _git(repo, 'add', '-A'); _git(repo, 'commit', '-qm', 'moved')
    base, head = rm.GitTree('HEAD~1', repo), rm.GitTree('HEAD', repo)
    h = lambda b: hashlib.sha256(b).hexdigest()
    m = manifest(('Validations/a.json', h(a), len(a)), ('Validations/same.txt', h(b'unchanged\n'), 10),
                 ('copy.json', h(copy), len(copy)), ('Validations/a.json.bak', h(a), len(a)))
    rew = rm.git_rewritten(base, head, m, RULES)
    assert rew('Validations/a.json', 'Deliverables/Validations/a.json', h(a)) == (h(now), len(now))
    # an older release version of a file git rewrote keeps its bytes
    assert rew('Validations/a.json', 'Deliverables/Validations/a.json', 'f' * 64) is None
    assert rew('Validations/same.txt', 'Deliverables/Validations/same.txt', h(b'unchanged\n')) is None
    # same old content elsewhere, untouched there: not replaced, whatever the hash chain says
    assert rew('copy.json', 'copy.json', h(copy)) is None
    assert rew('Validations/a.json.bak', 'Deliverables/Validations/a.json.bak', h(a)) is None


def test_choose_sample_takes_every_added_record_and_moved_ones_from_small_attachments():
    old = [{'path': f'Validations/{i}', 'asset': 'big' if i < 5 else 'small'} for i in range(10)]
    old.append({'path': 'Model/x', 'asset': 'small'})
    new = [dict(r, path=r['path'].replace('Validations', 'Deliverables/Validations')) for r in old]
    new[0]['asset'] = 'T.restructure-20261028.zip'
    assets = {'big': {'bytes': 10**9}, 'small': {'bytes': 10}, 'T.restructure-20261028.zip': {'bytes': 1}}
    picked = rm.choose_sample(old, new, assets, 3, 'T')
    assert 0 in picked and 10 not in picked
    assert [new[i]['asset'] for i in picked if i] == ['small'] * 3


def test_test_git_ignores_a_git_dir_the_hook_environment_sets(tmp_path, monkeypatch):
    # git runs hooks with GIT_DIR / GIT_INDEX_FILE set; a test repo must not follow them into the real one
    decoy = tmp_path / 'decoy'
    decoy.mkdir()
    import subprocess
    subprocess.run(['git', 'init', '-q', str(decoy)], check=True, env={k: v for k, v in __import__('os').environ.items()
                                                                       if not k.startswith('GIT_')})
    before = (decoy / '.git' / 'config').read_bytes()
    monkeypatch.setenv('GIT_DIR', str(decoy / '.git'))
    monkeypatch.setenv('GIT_INDEX_FILE', str(decoy / '.git' / 'index'))
    (tmp_path / 'r').mkdir()
    _git(tmp_path / 'r', 'init', '-q')
    assert (decoy / '.git' / 'config').read_bytes() == before
    assert (tmp_path / 'r' / '.git').is_dir()


class _FakeRun:
    """Stands in for subprocess.run: raises TimeoutExpired `timeouts` times, then succeeds."""

    def __init__(self, timeouts):
        self.timeouts = timeouts
        self.calls = []
        self.cmds = []

    def __call__(self, cmd, **kwargs):
        import subprocess
        self.calls.append(kwargs.get('timeout'))
        self.cmds.append(cmd)
        if len(self.calls) <= self.timeouts:
            raise subprocess.TimeoutExpired(cmd, kwargs.get('timeout'))
        return subprocess.CompletedProcess(cmd, 0, b'ok', b'')


def test_gh_retries_a_download_that_hangs():
    fake = _FakeRun(timeouts=2)
    assert rm.gh(['release', 'download', 't', '--pattern', 'x'], runner=fake) == 'ok'
    assert len(fake.calls) == 3 and all(fake.calls)


def test_gh_gives_up_on_a_read_after_three_hangs():
    fake = _FakeRun(timeouts=3)
    with pytest.raises(RuntimeError, match='timed out'):
        rm.gh(['api', 'repos/o/r/releases'], runner=fake)
    assert len(fake.calls) == 3


def test_gh_never_repeats_an_upload():
    fake = _FakeRun(timeouts=1)
    with pytest.raises(RuntimeError, match='timed out'):
        rm.gh(['release', 'upload', 't', 'f'], runner=fake)
    assert len(fake.calls) == 1 and fake.calls[0]


def test_gh_retries_a_download_over_its_half_finished_file():
    # a 0.95 GB download timed out, and the retry refused the partial file the first try left behind
    fake = _FakeRun(timeouts=1)
    rm.gh(['release', 'download', 't', '--pattern', 'a.zip', '--dir', 'd'], runner=fake)
    assert '--clobber' not in fake.cmds[0] and fake.cmds[1].count('--clobber') == 1


def test_gh_gives_a_download_longer_than_other_reads():
    fake = _FakeRun(timeouts=0)
    rm.gh(['release', 'download', 't', '--pattern', 'a.zip', '--dir', 'd', '--clobber'], runner=fake)
    rm.gh(['release', 'view', 't'], runner=fake)
    assert fake.calls[0] > fake.calls[1] == rm.READ_TIMEOUT
    assert fake.cmds[0].count('--clobber') == 1


def test_sha256_of_many_objects_does_not_deadlock(tmp_path, monkeypatch):
    # writing every request before reading any answer filled both pipes and hung the plan for two days
    import subprocess
    import threading
    repo = tmp_path / 'r'
    (repo / 'many').mkdir(parents=True)
    _git(repo, 'init', '-q')
    contents = {f'many/{i}.txt': (f'object {i}\n' * 20).encode() for i in range(3000)}
    for path, data in contents.items():
        (repo / path).write_bytes(data)
    _git(repo, 'add', '-A'); _git(repo, 'commit', '-qm', 'many')
    tree = rm.GitTree('HEAD', repo)
    started, real_popen = [], subprocess.Popen
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: started.append(real_popen(*a, **k)) or started[-1])
    worker = threading.Thread(target=tree.sha256_of, args=(list(contents),), daemon=True)
    worker.start()
    worker.join(60)
    hung = worker.is_alive()
    for proc in started:
        proc.kill()
    assert not hung, 'sha256_of hung on a large batch'
    assert all(tree.content(p) == (hashlib.sha256(d).hexdigest(), len(d)) for p, d in contents.items())


class _CutDownload:
    """Stands in for curl: each call appends the next piece to the output file and fails until the last."""

    def __init__(self, pieces, fail_code=92):
        self.pieces = list(pieces)
        self.fail_code = fail_code
        self.cmds = []

    def __call__(self, cmd, **kwargs):
        import subprocess
        self.cmds.append(cmd)
        out = Path(cmd[cmd.index('-o') + 1])
        piece = self.pieces.pop(0) if self.pieces else b''
        with open(out, 'ab') as f:
            f.write(piece)
        return subprocess.CompletedProcess(cmd, 0 if not self.pieces else self.fail_code, b'', b'stream error')


def test_download_attachment_resumes_where_a_cut_connection_stopped(tmp_path):
    body = b'attachment bytes'
    fake = _CutDownload([body[:5], body[5:11], body[11:]])
    rm.download_attachment('o/r', 'tag', 'big.zip', tmp_path, 'sha256:' + hashlib.sha256(body).hexdigest(), runner=fake)
    assert (tmp_path / 'big.zip').read_bytes() == body
    assert len(fake.cmds) == 3 and all(c[c.index('-C') + 1] == '-' for c in fake.cmds)
    assert fake.cmds[0][-1] == 'https://github.com/o/r/releases/download/tag/big.zip'


def test_download_attachment_rejects_bytes_github_does_not_list(tmp_path):
    fake = _CutDownload([b'something else'])
    with pytest.raises(RuntimeError, match='sha256'):
        rm.download_attachment('o/r', 'tag', 'big.zip', tmp_path, 'sha256:' + '0' * 64, runner=fake)


def test_download_attachment_gives_up_after_five_cut_connections(tmp_path):
    fake = _CutDownload([b'x'] * 9)
    with pytest.raises(RuntimeError, match='big.zip'):
        rm.download_attachment('o/r', 'tag', 'big.zip', tmp_path, 'sha256:' + '0' * 64, runner=fake)
    assert len(fake.cmds) == 5

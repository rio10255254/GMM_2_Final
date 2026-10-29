"""Run one phase of the 2026-10-28 tree restructure: plan, apply, verify, or record the baseline.

    python Tools/restructure_tree.py baseline
    python Tools/restructure_tree.py plan   --phase N
    python Tools/restructure_tree.py apply  --phase N
    python Tools/restructure_tree.py verify --phase N

Phase 1 is location mode (no folder moves: absolute project paths, external paths whose
content is in the cloud, interpreter paths). Phases 2-4 are moves mode with
`moves_phaseN.json` from the records folder. Release and local paths are seen through the
phases already applied.

plan    writes edits_phaseN.jsonl, unresolved_phaseN.tsv and problems_phaseN.txt; changes nothing else.
apply   refuses while blocking unresolved references remain (not covered by
        decisions_phaseN.json); otherwise moves tracked files, writes the rewrites, runs the
        hash chain (hash_changes_phaseN.json) and stages everything. It does not commit.
verify  compares HEAD (before) with the work tree (after): equivalence, Python
        re-evaluation, residual references, hash consistency, the local virtual tree,
        .gitignore scope, Markdown links against the baseline, py_compile, the structure
        validator and the pytest groups against the baseline. Exit 1 on any new problem.

decisions_phaseN.json: [{"segment": exact source, "target_old": "...", "target_new": "..." or null, "why": "..."}]
null keeps the expression as written. The records folder itself is never rewritten.
reader_hints_phaseN.json: [{"file": "...py", "name": "MANIFEST_PATH", "path": "...", "why": "..."}]: a name whose
path the tool cannot evaluate (built from a data value, or set by the module that loads this one), for following
values read out of data files.
"""
import argparse
import csv
import fnmatch
import hashlib
import io
import json
import os
import posixpath
import re
import subprocess
import sys
import threading
import warnings
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_markdown_links
from restructure_hashes import propagate
from restructure_python import rewrite_python
from restructure_readers import DATA_EXT, DataView, link, read_targets
from restructure_resolve import Universe, git_env
from restructure_rules import compose, load_rules
from restructure_text import Context, Edit, file_class, rewrite_bytes
import restructure_verify as verify

RECORDS = 'docs/operations/TREE_RESTRUCTURE_20261028'
# a data value the tool could not fix is listed for checking by hand; a read it got wrong fails verify
NON_BLOCKING = ('syntax error', 'not UTF-8', 'not gzip', 'data value')
PYTEST_GROUPS = ['Tools/tests', 'Model/tests', 'PSF_Fitting/tests', 'AnalysisLab/tests', 'Analyses/AnalysisLab/tests',
                 'Thesis_MOSR_Evidence/tests']


# ---------- setup ----------
class Phase:
    def __init__(self, args):
        self.args, self.n = args, args.phase
        self.repo = Path(args.repo)
        self.rec = self.repo / RECORDS
        self.mode = 'location' if self.n == 1 else 'moves'
        self.rules = load_rules(self.rec / f'moves_phase{self.n}.json') if self.n >= 2 else None
        earlier = [load_rules(self.rec / f'moves_phase{k}.json') for k in range(2, self.n)
                   if (self.rec / f'moves_phase{k}.json').exists()]
        self.before = compose(earlier) if earlier else None
        self.upto = compose(earlier + ([self.rules] if self.rules else [])) if (earlier or self.rules) else None
        self.external = {}
        ext = self.rec / 'external_map.json'
        if ext.exists():
            data = json.loads(ext.read_text(encoding='utf-8'))
            self.external = {**data.get('files', {}), **data.get('dirs', {}), **data.get('junctions', {})}
        self.hints = {}
        hints = self.rec / f'reader_hints_phase{self.n}.json'
        if hints.exists():
            for h in json.loads(hints.read_text(encoding='utf-8')):
                self.hints.setdefault(h['file'], {})[h['name']] = h['path']
        self.decisions = {}
        dec = self.rec / f'decisions_phase{self.n}.json'
        if dec.exists():
            for d in json.loads(dec.read_text(encoding='utf-8')):
                self.decisions[(d['segment'], d['target_old'])] = d['target_new']

    def universe(self, ref=None, applied='before'):
        a = self.before if applied == 'before' else self.upto
        reparse = [p for p in self.args.reparse if Path(p).exists()]
        return Universe.build(self.repo, self.args.cloud_index, self.args.local_inventory, a, reparse, ref=ref)

    def context(self, uni, rules='phase'):
        hints = self.hints
        if rules != 'phase' and self.rules:
            # the rewritten side: files and paths at their new places
            m = lambda r: self.rules.map(r) or r
            hints = {m(f): {k: m(v) for k, v in h.items()} for f, h in self.hints.items()}
        return Context(uni, self.rules if rules == 'phase' else None, self.external, self.mode, self.decisions,
                       hints=hints)


def tracked(repo, ref=None):
    listing = ['ls-tree', '-r', '--name-only', '-z', ref] if ref else ['ls-files', '-z']
    out = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), *listing],
                         capture_output=True, check=True, env=git_env()).stdout.decode('utf-8')
    return [p for p in out.split('\0') if p]


def rewritable(name):
    return name.lower().endswith('.py') or file_class(name) is not None


def git(repo, *args, data=None):
    return subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'core.quotepath=false',
                           '-C', str(repo), *args], input=data, capture_output=True, check=True, env=git_env())


# ---------- plan ----------
def rewrite_one(name, new_name, data, ctx):
    """(new bytes, edits, unresolved rows, problems) for one file."""
    if name.lower().endswith('.py'):
        bom = data.startswith(b'\xef\xbb\xbf')
        try:
            src = (data[3:] if bom else data).decode('utf-8')
        except UnicodeDecodeError:
            return data, [], [], [f'{name}: not UTF-8, left unchanged']
        out, edits, unresolved = rewrite_python(src, name, new_name, ctx)
        return (b'\xef\xbb\xbf' if bom else b'') + out.encode('utf-8'), edits, unresolved, []
    out, edits, problems = rewrite_bytes(data, name, new_name, ctx)
    return out, edits, [], problems


def blocking(u):
    return not u.reason.startswith(NON_BLOCKING)


def plan(ph, write_reports=True):
    files = tracked(ph.repo)
    ctx = ph.context(ph.universe())
    moves = {f: m for f in files if ph.rules and (m := ph.rules.map(f)) and not verify.is_record(f)}
    changed, edits, unresolved, problems = {}, [], [], []
    todo = [n for n in files if not verify.is_record(n) and rewritable(n)]
    # data files first: rewriting a Python file that reads one back needs its old and new content
    data_old = {}
    for name in sorted(todo, key=lambda n: n.lower().endswith('.py')):
        if name.lower().endswith('.py') and ctx.data is None:
            ctx.data = DataView(data_old, {n: changed[n] for n in data_old}, moves)
            py = {n: (ph.repo / n).read_bytes().decode('utf-8-sig', errors='replace') for n in todo if n.lower().endswith('.py')}
            ctx.seeds = link(py, ctx)
        data = (ph.repo / name).read_bytes()
        if verify.content_addressed(name, data):
            continue                 # stored under its own sha256: rewriting would break its identity
        new_name = moves.get(name, name)
        out, e, u, p = rewrite_one(name, new_name, data, ctx)
        edits += e; unresolved += u; problems += p
        if out != data:
            changed[name] = out
            if name.lower().endswith(DATA_EXT):
                data_old[name] = data
    block = [u for u in unresolved if blocking(u)]
    if write_reports:
        ph.rec.mkdir(parents=True, exist_ok=True)
        with open(ph.rec / f'edits_phase{ph.n}.jsonl', 'w', encoding='utf-8', newline='\n') as f:
            for e in edits:
                f.write(json.dumps(asdict(e), ensure_ascii=False) + '\n')
        with open(ph.rec / f'unresolved_phase{ph.n}.tsv', 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, delimiter='\t', lineterminator='\n')
            w.writerow(['file', 'line', 'segment', 'reason', 'target', 'blocking'])
            for u in unresolved:
                w.writerow([u.file, u.line, u.segment.replace('\n', '\\n'), u.reason, u.target, 'yes' if blocking(u) else 'no'])
        (ph.rec / f'problems_phase{ph.n}.txt').write_text(''.join(p + '\n' for p in problems), encoding='utf-8', newline='\n')
    kinds = {}
    for e in edits:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    print(f'phase {ph.n}: {len(moves)} files move, {len(changed)} files rewritten, {len(edits)} edits, '
          f'{len(unresolved)} unresolved ({len(block)} blocking), {len(problems)} problems')
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f'  {v:8d} {k}')
    return moves, changed, edits, block


# ---------- apply ----------
def local_moves(ph, tracked_moves):
    """Untracked files on disk under a moved place: they move along, but are never staged.

    In this checkout they are copies of local data that tests read; moving them keeps the
    test environment equal to the original project through every phase."""
    out = {}
    if not ph.rules:
        return out
    roots = [ph.repo / r.old for r in ph.rules.rules] + \
        [ph.repo / g.parent / c for g in ph.rules.globs if (ph.repo / g.parent).is_dir()
         for c in os.listdir(ph.repo / g.parent) if fnmatch.fnmatchcase(c, g.pattern)]
    for root in roots:
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = [Path(d) / f for d, _, fs in os.walk(root) for f in fs]
        else:
            continue
        for p in files:
            rel = p.relative_to(ph.repo).as_posix()
            if rel in tracked_moves or verify.is_record(rel) or os.path.islink(p):
                continue
            new = ph.rules.map(rel)
            if new and new != rel:
                out[rel] = new
    return out


def apply(ph):
    moves, changed, edits, block = plan(ph)
    if block:
        print(f'refusing: {len(block)} blocking unresolved references; see {RECORDS}/unresolved_phase{ph.n}.tsv')
        return 2
    old_sha = {name: hashlib.sha256((ph.repo / name).read_bytes()).hexdigest() for name in changed}
    local = local_moves(ph, moves)
    for old, new in {**moves, **local}.items():
        (ph.repo / new).parent.mkdir(parents=True, exist_ok=True)
        os.replace(ph.repo / old, ph.repo / new)
    for name, data in changed.items():
        (ph.repo / moves.get(name, name)).write_bytes(data)
    for old in {**moves, **local}:
        d = (ph.repo / old).parent
        while d != ph.repo and d.exists() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    seeds = {old_sha[n]: hashlib.sha256(d).hexdigest() for n, d in changed.items()}
    sizes = {hashlib.sha256(d).hexdigest(): len(d) for d in changed.values()}
    seeds = {o: n for o, n in seeds.items() if o != n}
    names = [moves.get(f, f) for f in tracked(ph.repo) if rewritable(f) and not verify.is_record(f)]
    names = [n for n in names if (ph.repo / n).exists()]
    rep = propagate(seeds, sizes, names, lambda n: (ph.repo / n).read_bytes(), lambda n, d: (ph.repo / n).write_bytes(d))
    all_sizes = dict(sizes)
    for n in rep.touched_files:
        data = (ph.repo / n).read_bytes()
        all_sizes[hashlib.sha256(data).hexdigest()] = len(data)
    (ph.rec / f'hash_changes_phase{ph.n}.json').write_text(
        json.dumps({'changes': rep.changes, 'bytes': {k: all_sizes[v] for k, v in rep.changes.items() if v in all_sizes},
                    'rounds': rep.rounds}, indent=1) + '\n', encoding='utf-8', newline='\n')
    # explicit file paths only, forced: many tracked files live under ignored folders, and a moved
    # file must stay tracked at its new place even when that place is ignored
    records = {p.relative_to(ph.repo).as_posix() for p in ph.rec.rglob('*') if p.is_file()}
    specs = sorted(set(moves) | set(moves.values()) | {moves.get(n, n) for n in changed} | set(rep.touched_files) | records)
    git(ph.repo, '--literal-pathspecs', 'add', '-A', '-f', '--pathspec-from-file=-', '--pathspec-file-nul',
        data='\0'.join(specs).encode('utf-8'))
    print(f'applied: {len(moves)} moved, {len(changed)} rewritten, hash chain {len(rep.changes)} changes in {rep.rounds} rounds')
    return 0


# ---------- verify ----------
def head_blobs(repo, ref='HEAD'):
    """Yield (path, bytes) for every file in `ref`, streaming through one git cat-file process."""
    out = git(repo, 'ls-tree', '-r', '-z', ref).stdout.decode('utf-8')
    rows = []
    for item in out.split('\0'):
        if item:
            meta, path = item.split('\t', 1)
            mode, kind, sha = meta.split()
            if kind == 'blob':
                rows.append((path, sha))
    proc = subprocess.Popen(['git', '-C', str(repo), 'cat-file', '--batch'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, env=git_env())

    def feed():
        for _, sha in rows:
            proc.stdin.write((sha + '\n').encode())
        proc.stdin.close()

    threading.Thread(target=feed, daemon=True).start()
    for path, _ in rows:
        header = proc.stdout.readline().split()
        size = int(header[2])
        data = proc.stdout.read(size)
        proc.stdout.read(1)
        yield path, data
    proc.wait()


class OnDisk:
    """{path: bytes} view of the work tree, read on demand."""

    def __init__(self, root, names):
        self.root, self.names = Path(root), set(names)

    def __contains__(self, name):
        return name in self.names

    def __getitem__(self, name):
        return (self.root / name).read_bytes()

    def __iter__(self):
        return iter(self.names)

    def items(self):
        return ((n, self[n]) for n in self.names)


def utf8_env():
    """Child Pythons write UTF-8, whatever the console code page is."""
    return {**git_env(), 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}


def run_pytest(repo, groups):
    failed = {}
    for g in groups:
        if not (Path(repo) / g).is_dir():
            continue
        res = subprocess.run([sys.executable, '-m', 'pytest', g, '-q', '-rfE', '-p', 'no:cacheprovider'],
                             cwd=repo, capture_output=True, encoding='utf-8', errors='replace', env=utf8_env())
        failed[g] = sorted(set(re.findall(r'^(?:FAILED|ERROR) (\S+)', res.stdout, re.M)))
        if res.returncode not in (0, 1, 5) and not failed[g]:
            failed[g] = [f'<pytest exit {res.returncode}>']
    return failed


def pytest_groups(repo):
    extra = sorted(str(p.relative_to(repo)).replace('\\', '/') for p in Path(repo).glob('Experiments/*/tests') if p.is_dir())
    return PYTEST_GROUPS + extra


def run_validator(repo):
    v = Path(repo) / 'Tools' / 'validate_project_structure.py'
    if not v.exists():
        return None
    res = subprocess.run([sys.executable, str(v)], cwd=repo, capture_output=True, encoding='utf-8', errors='replace',
                         env=utf8_env())
    return res.returncode, sorted({l for l in (res.stdout + res.stderr).splitlines() if l.strip()})


def do_verify(ph):
    problems = []
    edits = []
    path = ph.rec / f'edits_phase{ph.n}.jsonl'
    if path.exists():
        edits = [Edit(**json.loads(l)) for l in path.read_text(encoding='utf-8').splitlines() if l]
    old_uni, new_uni = ph.universe(ref='HEAD'), ph.universe(applied='upto')
    # before: stream HEAD once
    shas, tokens, old_py, parsed_before = {}, {}, {}, set()
    edited_py = {e.file_old for e in edits if e.file_old.lower().endswith('.py')}
    data_names = {e.file_old for e in edits if e.file_old.lower().endswith(DATA_EXT)}
    data_old, py_old = {}, {}
    for name, data in head_blobs(ph.repo):
        if verify.is_record(name):
            continue
        shas[name] = hashlib.sha256(data).hexdigest()
        if rewritable(name):
            tokens[name] = verify.hex_tokens(name, data)
        if name in edited_py:
            old_py[name] = data.decode('utf-8-sig', errors='replace')
        if name in data_names:
            data_old[name] = data
        if name.lower().endswith('.py') and data_names:
            py_old[name] = data.decode('utf-8-sig', errors='replace')
        if verify.parses(name, data):
            parsed_before.add(name)
    pairs = verify.hash_pairs_from(shas, tokens)
    now = [n for n in tracked(ph.repo) if not verify.is_record(n)]
    after = OnDisk(ph.repo, now)
    rules = ph.rules
    mapped = lambda n: (rules.map(n) if rules else None) or n
    problems += verify.equivalence([e for e in edits if not e.kind.startswith('py:') or e.kind in ('py:string', 'py:comment')],
                                   old_uni, new_uni, rules, ph.external)
    flat_decisions = {k[1]: v for k, v in ph.decisions.items() if v}
    view = DataView({n: d for n, d in data_old.items() if mapped(n) in after},
                    {n: after[mapped(n)] for n in data_old if mapped(n) in after},
                    {n: mapped(n) for n in data_old})
    ctx_old, ctx_new = ph.context(old_uni), ph.context(new_uni, rules=None)
    ctx_old.data, ctx_new.data, ctx_new.data_side = view, view, 'new'
    # every read of a rewritten data value lands where it did, values crossing modules included
    py_new = {mapped(n): after[mapped(n)].decode('utf-8-sig', errors='replace') for n in py_old if mapped(n) in after}
    ctx_old.seeds, ctx_new.seeds = link(py_old, ctx_old), link(py_new, ctx_new)
    for old_name, src in sorted(py_old.items()):
        new_name = mapped(old_name)
        if new_name not in py_new or not (view.mentioned_in(src) or old_name in ctx_old.seeds or new_name in ctx_new.seeds
                                          or old_name in (ctx_old.hints or {})):
            continue
        before = read_targets(src, old_name, ctx_old)
        now_reads = read_targets(py_new[new_name], new_name, ctx_new)
        if before is None or now_reads is None:
            continue
        expect = Counter((d, k, t if ':' in t else verify._expect(t, rules, flat_decisions)) for d, k, t in before)
        got = Counter(now_reads)
        if expect != got:
            show = lambda c: sorted(f"{d}:{'/'.join(map(str, k))} -> {t}" for d, k, t in c.elements())[:4]
            problems.append(f'{new_name}: data values read from other places; expected {show(expect - got)}, '
                            f'got {show(got - expect)}')
    for old_name, src in sorted(old_py.items()):
        new_name = (rules.map(old_name) if rules else None) or old_name
        if new_name in after:
            new_src = after[new_name].decode('utf-8-sig', errors='replace')
            problems += verify.python_equivalence(src, new_src, old_name, new_name, ctx_old, ctx_new, rules, flat_decisions)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                try:
                    compile(new_src, new_name, 'exec')
                except SyntaxError as exc:
                    try:
                        compile(src, old_name, 'exec')
                        problems.append(f'{new_name}: no longer compiles ({exc})')
                    except SyntaxError:
                        pass
    texts = {n: after[n] for n in now if rewritable(n)}
    problems += verify.residual(texts, new_uni, ph.upto, absolute_check=True)
    problems += verify.hash_consistency(pairs, after, rules)
    for name in sorted(parsed_before):
        new = (rules.map(name) if rules else None) or name
        if new in after and verify.parses(new, after[new]) is False:
            problems.append(f'{new}: no longer parses as JSON')
    if rules:
        # the old tree as this machine has it (tracked + Release + local files), moved by this phase
        problems += verify.virtual_tree([e for e in edits if e.old_target], old_uni, rules)
    if rules and ph.args.local_inventory and Path(ph.args.local_inventory).exists():
        old_gi = git(ph.repo, 'show', 'HEAD:.gitignore').stdout if '.gitignore' in shas else b''
        new_gi = (ph.repo / '.gitignore').read_bytes() if (ph.repo / '.gitignore').exists() else b''
        if old_gi != new_gi:
            import tempfile
            local = Universe.build(ph.repo, None, ph.args.local_inventory, ph.before, ref='HEAD')
            local_paths = sorted(p for p in local.files if p not in shas)
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / 'old').write_bytes(old_gi); (Path(d) / 'new').write_bytes(new_gi)
                problems += [f'.gitignore scope changed for {p}'
                             for p in verify.gitignore_scope(Path(d) / 'old', Path(d) / 'new', local_paths, rules)]
    base = ph.rec / 'baseline'
    if (base / 'links.json').exists():
        b = [check_markdown_links.Broken(**x) for x in json.loads((base / 'links.json').read_text(encoding='utf-8'))]
        problems += [f'{x.file}:{x.line}: link broken: {x.target}' for x in check_markdown_links.compare(b, check_markdown_links.scan(ph.repo), ph.upto)]
    if not ph.args.no_tests:
        val = run_validator(ph.repo)
        if val and (base / 'validate.json').exists():
            known = set(json.loads((base / 'validate.json').read_text(encoding='utf-8'))['lines'])
            problems += [f'validator: {l}' for l in val[1] if l not in known and val[0] != 0]
        current = run_pytest(ph.repo, pytest_groups(ph.repo))
        known = json.loads((base / 'pytest_failures.json').read_text(encoding='utf-8')) if (base / 'pytest_failures.json').exists() else {}
        known_all = {t for v in known.values() for t in v}
        for g, fails in current.items():
            problems += [f'pytest {g}: {t}' for t in fails if t not in known_all]
    (ph.rec / f'verify_phase{ph.n}.txt').write_text(''.join(p + '\n' for p in problems), encoding='utf-8', newline='\n')
    print(f'verify phase {ph.n}: {len(problems)} problems')
    for p in problems[:40]:
        print('  ' + p)
    return 1 if problems else 0


def do_rehash(ph):
    """After hand fixes on top of `apply`: carry every changed file's current sha into the records
    that hold its sha, and fold the result into hash_changes_phaseN.json."""
    path = ph.rec / f'hash_changes_phase{ph.n}.json'
    saved = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'changes': {}, 'bytes': {}, 'rounds': 0}
    changes = saved['changes']
    out = git(ph.repo, 'diff', 'HEAD', '--name-status', '-M', '-z').stdout.decode('utf-8').split('\0')
    pairs, i = [], 0
    while i < len(out) and out[i]:
        status = out[i]
        if status.startswith(('R', 'C')):
            pairs.append((out[i + 1], out[i + 2])); i += 3
        else:
            if status != 'D':
                pairs.append((out[i + 1], out[i + 1]))
            i += 2
    seeds, sizes = {}, {}
    for old, new in pairs:
        if verify.is_record(new) or not (ph.repo / new).is_file():
            continue
        head = hashlib.sha256(git(ph.repo, 'show', f'HEAD:{old}').stdout).hexdigest()
        data = (ph.repo / new).read_bytes()
        cur = hashlib.sha256(data).hexdigest()
        expected = changes.get(head, head)
        if cur != expected:
            seeds[expected] = cur
            sizes[cur] = len(data)
    names = [n for n in tracked(ph.repo) if rewritable(n) and not verify.is_record(n) and (ph.repo / n).exists()]
    rep = propagate(seeds, sizes, names, lambda n: (ph.repo / n).read_bytes(), lambda n, d: (ph.repo / n).write_bytes(d))
    for n in rep.touched_files:
        data = (ph.repo / n).read_bytes()
        sizes[hashlib.sha256(data).hexdigest()] = len(data)
    final = {}
    for k, v in changes.items():
        while v in rep.changes:
            v = rep.changes[v]
        final[k] = v
    for k, v in rep.changes.items():
        if k not in changes.values() and k not in final:
            while v in rep.changes:
                v = rep.changes[v]
            final[k] = v
    sizes_all = {**saved.get('bytes', {})}
    for k, v in final.items():
        if v in sizes:
            sizes_all[k] = sizes[v]
    path.write_text(json.dumps({'changes': final, 'bytes': sizes_all, 'rounds': saved.get('rounds', 0) + rep.rounds}, indent=1) + '\n',
                    encoding='utf-8', newline='\n')
    specs = sorted({new for _, new in pairs} | set(rep.touched_files) |
                   {p.relative_to(ph.repo).as_posix() for p in ph.rec.rglob('*') if p.is_file()})
    specs = [s for s in specs if (ph.repo / s).exists()]
    git(ph.repo, '--literal-pathspecs', 'add', '-A', '-f', '--pathspec-from-file=-', '--pathspec-file-nul',
        data='\0'.join(specs).encode('utf-8'))
    print(f'rehash: {len(seeds)} hand-changed files, {len(rep.touched_files)} records updated')
    return 0


def do_baseline(args):
    repo = Path(args.repo)
    base = repo / RECORDS / 'baseline'
    base.mkdir(parents=True, exist_ok=True)
    broken = check_markdown_links.scan(repo)
    (base / 'links.json').write_text(json.dumps([asdict(b) for b in broken], ensure_ascii=False, indent=1) + '\n',
                                     encoding='utf-8', newline='\n')
    val = run_validator(repo)
    if val:
        (base / 'validate.json').write_text(json.dumps({'exit': val[0], 'lines': val[1]}, ensure_ascii=False, indent=1) + '\n',
                                            encoding='utf-8', newline='\n')
    fails = run_pytest(repo, pytest_groups(repo)) if not args.no_tests else {}
    (base / 'pytest_failures.json').write_text(json.dumps(fails, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'baseline: {len(broken)} broken links, validator exit {val[0] if val else "n/a"}, '
          f'{sum(len(v) for v in fails.values())} failing tests across {len(fails)} groups')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('command', choices=['baseline', 'plan', 'apply', 'rehash', 'verify'])
    ap.add_argument('--phase', type=int, default=0)
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--cloud-index', default=None)
    ap.add_argument('--local-inventory', default=None)
    ap.add_argument('--reparse', nargs='*', default=[])
    ap.add_argument('--no-tests', action='store_true')
    args = ap.parse_args(argv)
    if args.cloud_index is None:
        args.cloud_index = str(Path(args.repo) / '.cache' / 'cloud_locator' / 'index.sqlite')
    if args.command == 'baseline':
        return do_baseline(args)
    if args.phase < 1:
        ap.error('--phase is required')
    ph = Phase(args)
    if args.command == 'plan':
        plan(ph)
        return 0
    if args.command == 'apply':
        return apply(ph)
    if args.command == 'rehash':
        return do_rehash(ph)
    return do_verify(ph)


if __name__ == '__main__':
    sys.exit(main())

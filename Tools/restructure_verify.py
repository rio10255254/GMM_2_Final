"""Checks for the 2026-10-28 restructure (design, "驗證" 3-6 and the .gitignore check).

- equivalence: every rewritten text reference, resolved afresh, reaches the old target's
  new place (location mode: the same place, read the way its reader reads it).
- python_equivalence: the new source, evaluated afresh in the new tree, has the same path
  targets as the old source moved by the rules.
- residual: nothing outside the transform records still points into an old place; after
  phase 1, no executable names this machine's project folder or interpreter.
- hash_pairs / hash_consistency: every record of a tracked file's sha256 still records it.
- virtual_tree: a reference that found a local-only file before still finds it after.
- gitignore_scope: the new .gitignore ignores exactly what the old one did, moved.

Functions take {path: bytes} snapshots so they can be tested without a repository; the
CLI in restructure_tree.py builds those from the work tree.
"""
from collections import Counter
import gzip
import hashlib
import posixpath
import re
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

from restructure_hashes import HEX64
from restructure_python import evaluated_targets
from restructure_resolve import PROJECT_ABS, Universe, git_env, norm, resolve
from restructure_text import ABS_START, INTERPRETER, TOKEN, token_starts, token_targets

TRANSFORM_RECORDS = ('docs/operations/TREE_RESTRUCTURE_20261028.md', 'docs/operations/TREE_RESTRUCTURE_20261028/',
                     'docs/superpowers/specs/2026-10-28-tree-restructure-design.md',
                     'docs/superpowers/plans/2026-10-28-tree-restructure.md')
# the transform's own code and tests: their old paths are test inputs and rule text, not references
TRANSFORM_CODE = re.compile(r'^Tools/(?:tests/test_)?(?:restructure_[a-z_]+|check_markdown_links)\.py$')
EXECUTABLE = ('.py', '.m', '.ps1', '.psm1', '.bat', '.cmd', '.sh', '.ipynb')


def is_record(name):
    return any(name == r or (r.endswith('/') and name.startswith(r)) for r in TRANSFORM_RECORDS) or \
        bool(TRANSFORM_CODE.match(name))


def _text(name, data):
    if isinstance(data, str):
        return data
    if name.lower().endswith('.gz'):
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError):
            return None
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return None


def _expect(target, rules, decisions):
    return (decisions or {}).get(target) or (rules.map(target) if rules else None) or target


# ---------- 3. equivalence ----------
def equivalence(edits, old_uni, new_uni, rules, external_map, decisions=None):
    problems = []
    for e in edits:
        cls, _, kind = e.kind.partition(':')
        where = f'{e.file_new}:{e.line}: {e.old!r} -> {e.new!r}'
        if cls == 'py':
            if kind in ('string', 'comment'):
                old = [_expect(t, rules, decisions) for t in token_targets(e.old, e.file_old, old_uni, external_map)]
                new = token_targets(e.new, e.file_new, new_uni, external_map)
                if Counter(old) != Counter(new):
                    problems.append(f'{where}: targets {old} became {new}')
            continue
        if kind == 'interpreter':
            if e.new != 'python':
                problems.append(f'{where}: interpreter not replaced by python')
            continue
        if kind == 'github':
            if urllib.parse.unquote(e.new) != _expect(urllib.parse.unquote(e.old).rstrip('/'), rules, decisions) + \
                    ('/' if e.old.endswith('/') else ''):
                problems.append(f'{where}: GitHub link does not follow the move')
            continue
        if kind in ('matlab_root', 'powershell_root'):
            literal = e.old.strip('\'"')
            res = resolve(literal, e.file_old, old_uni, external_map) if ABS_START.match(literal) else None
            if res is not None and res.target_rel != e.new_target:
                problems.append(f'{where}: {res.target_rel} written as {e.new_target}')
            if e.new_target and e.new_target.replace('/', '\\') not in e.new and e.new_target not in e.new.replace('\\', '/'):
                problems.append(f'{where}: target {e.new_target} missing from the new expression')
            continue
        res = resolve(e.old, e.file_old, old_uni, external_map)
        if res is None:
            problems.append(f'{where}: old reference no longer resolves')
            continue
        want = _expect(res.target_rel, rules, decisions)
        if rules is None:          # location mode: read the new text the way its reader reads it
            new = urllib.parse.unquote(e.new) if kind == 'link' else e.new
            if kind == 'link' or cls == 'notebook':
                got = norm(posixpath.join(posixpath.dirname(e.file_new), new))
            else:
                got = norm(new)
        else:
            r2 = resolve(e.new, e.file_new, new_uni, external_map)
            got = r2.target_rel if r2 else None
        if got != want:
            problems.append(f'{where}: reaches {got}, should reach {want}')
    return problems


def python_equivalence(old_src, new_src, file_old, file_new, ctx_old, ctx_new, rules, decisions=None):
    old = evaluated_targets(old_src, file_old, ctx_old)
    new = evaluated_targets(new_src, file_new, ctx_new)
    if old is None or new is None:
        return [] if (old is None) == (new is None) else [f'{file_new}: parses before/after differ']
    location = ctx_old.mode == 'location'
    fixed_old = Counter(_expect(t, rules, decisions) for t in old if not t.endswith('/<dyn>') and not (location and t == ''))
    fixed_new = Counter(t for t in new if not t.endswith('/<dyn>') and not (location and t == ''))
    problems = []
    if fixed_old != fixed_new:
        lost, extra = fixed_old - fixed_new, fixed_new - fixed_old
        problems.append(f'{file_new}: path targets differ; expected but missing {dict(lost)}, unexpected {dict(extra)}')
    dyn_old = [t[:-6] for t in old if t.endswith('/<dyn>')]
    dyn_new = Counter(t[:-6] for t in new if t.endswith('/<dyn>'))
    if len(dyn_old) != sum(dyn_new.values()):
        problems.append(f'{file_new}: number of dynamic path expressions changed')
    ok = Counter(_expect(t, rules, decisions) for t in dyn_old
                 if not (rules and rules.splits_under(t)) and (decisions or {}).get(t) is None)
    if ok - dyn_new:
        problems.append(f'{file_new}: dynamic prefixes {dict(ok - dyn_new)} not found after rewrite')
    return problems


# ---------- 5. residual ----------
def _interpretations(tok, name):
    for i in token_starts(tok):
        t = tok[i:]
        if ABS_START.match(t):
            m = re.match(r'^(?:\\\\\?\\)?[A-Za-z]:(?:\\\\|\\|/)+([^\\/]+)(.*)$', t)
            if m and m.group(1).lower() in ('gmm_2_final', 'gmm_2_final_restructure'):
                yield [norm(m.group(2))]
            continue
        if t.startswith(('/', '\\')):
            continue
        t = urllib.parse.unquote(re.split(r'[#?]', t, 1)[0])
        yield [p for p in (norm(posixpath.join(posixpath.dirname(name), t)), norm(t)) if p]


def residual(files, uni, rules, absolute_check=False):
    out = []
    for name in sorted(files):
        if is_record(name):
            continue
        text = _text(name, files[name])
        if text is None:
            continue
        if absolute_check and name.lower().endswith(EXECUTABLE):
            m = PROJECT_ABS.search(text) or INTERPRETER.search(text)
            if m:
                out.append(f'{name}:{text.count(chr(10), 0, m.start()) + 1}: names this machine ({m.group(0)})')
        if rules is None:
            continue
        for m in TOKEN.finditer(text):
            tok = m.group(0)
            if '/' not in tok and '\\' not in tok:
                continue
            for cands in _interpretations(tok, name):
                if any(uni.exists(p) for p in cands):
                    break
                stale = next((p for p in cands if rules.map(p) is not None), None)
                if stale:
                    out.append(f'{name}:{text.count(chr(10), 0, m.start()) + 1}: {tok} still points at {stale}')
                    break
    return out


# ---------- 6. hashes ----------
def hex_tokens(name, data):
    """The 64-hex tokens a file holds (empty for binaries)."""
    text = _text(name, data)
    return {m.group(0).lower() for m in HEX64.finditer(text)} if text else set()


def hash_pairs_from(shas, tokens):
    """{(record, old_sha): files that had that content}, from {name: sha} and {name: tokens}."""
    by_sha = {}
    for name, h in shas.items():
        by_sha.setdefault(h, set()).add(name)
    pairs = {}
    for name, toks in tokens.items():
        for h in toks:
            owners = by_sha.get(h, set()) - {name}
            if owners:
                pairs[(name, h)] = frozenset(owners)
    return pairs


def hash_pairs(files):
    return hash_pairs_from({n: hashlib.sha256(d).hexdigest() for n, d in files.items()},
                           {n: hex_tokens(n, d) for n, d in files.items()})


def hash_consistency(pairs, files_after, rules):
    sha_after, tokens = {}, {}
    problems = []
    for (record, _), owners in sorted(pairs.items()):
        rec = (rules.map(record) if rules else None) or record
        if rec not in tokens:
            text = _text(rec, files_after[rec]) if rec in files_after else None
            tokens[rec] = {m.group(0).lower() for m in HEX64.finditer(text or '')}
        ok = False
        for f in owners:
            f2 = (rules.map(f) if rules else None) or f
            if f2 in files_after:
                sha_after.setdefault(f2, hashlib.sha256(files_after[f2]).hexdigest())
                ok = ok or sha_after[f2] in tokens[rec]
        if not ok:
            problems.append(f'{rec} no longer records the sha256 of {", ".join(sorted(owners))}')
    return problems


# ---------- 4. virtual tree ----------
def virtual_tree(edits, local_uni, rules):
    virtual = Universe((rules.map(p) or p) for p in local_uni.files)
    out = []
    for e in edits:
        if e.old_target and local_uni.exists(e.old_target) and not virtual.exists(e.new_target):
            out.append(f'{e.file_new}:{e.line}: {e.old_target} exists here but {e.new_target} will not')
    return out


# ---------- .gitignore ----------
def _ignored(gitignore, paths):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['git', 'init', '-q', d], check=True, env=git_env(), capture_output=True)
        Path(d, '.gitignore').write_bytes(Path(gitignore).read_bytes())
        res = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', d, 'check-ignore', '--no-index', '--stdin', '-z'],
                             input='\0'.join(paths).encode('utf-8'), capture_output=True, env=git_env())
        if res.returncode not in (0, 1):
            raise RuntimeError(res.stderr.decode('utf-8', 'replace'))
        return {p for p in res.stdout.decode('utf-8').split('\0') if p}


def gitignore_scope(old_gitignore, new_gitignore, local_paths, rules):
    paths = list(local_paths)
    mapped = [(rules.map(p) or p) for p in paths]
    old_ign, new_ign = _ignored(old_gitignore, paths), _ignored(new_gitignore, mapped)
    return [p for p, m in zip(paths, mapped) if (p in old_ign) != (m in new_ign)]

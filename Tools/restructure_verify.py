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
import io
import tokenize
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


def parses(name, data):
    """Whether a JSON-family file (.json, .ipynb, .json.gz) parses; None for other files."""
    low = name.lower()
    if not low.endswith(('.json', '.ipynb', '.json.gz')):
        return None
    import json
    try:
        json.loads(_text(name, data) or '')
        return True
    except ValueError:
        return False


def structure(before, after, rules):
    """JSON-family files that parsed before the transform must still parse after it."""
    out = []
    for name, data in sorted(before.items()):
        new = (rules.map(name) if rules else None) or name
        if parses(name, data) and new in after and parses(new, after[new]) is False:
            out.append(f'{new}: no longer parses as JSON')
    return out


def content_addressed(name, data):
    """A file stored under its own sha256 (a folder or file named by it): its identity is its
    content, so the transform never rewrites it."""
    h = hashlib.sha256(data).hexdigest()
    return any(seg.lower() == h for seg in re.split(r'[/.]', name))


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
    # a decision may send a target to the project root itself (''), so test membership, not truth
    if decisions and target in decisions:
        return decisions[target]
    return (rules.map(target) if rules else None) or target


def _one_segment(literal, uni):
    """A string that is one root-level name with no slash ('LabSystem_MOSR'): path tokens need a
    slash, so a folder moved up to the root would otherwise read as no target at all."""
    name = literal.strip().lstrip('rbuRBU').strip('\'"')
    if name and re.fullmatch(r'[\w.\-]+', name) and uni.exists(name):
        return [uni.canon(name)]
    return []


# ---------- 3. equivalence ----------
def equivalence(edits, old_uni, new_uni, rules, external_map, decisions=None):
    problems = []
    for e in edits:
        cls, _, kind = e.kind.partition(':')
        where = f'{e.file_new}:{e.line}: {e.old!r} -> {e.new!r}'
        if cls == 'py':
            if kind in ('string', 'comment'):
                old = [_expect(t, rules, decisions) for t in token_targets(e.old, e.file_old, old_uni, external_map)]
                new = token_targets(e.new, e.file_new, new_uni, external_map) or _one_segment(e.new, new_uni)
                if rules is None:
                    # location mode: the project folder itself is written '.', or kept as written in prose
                    old, new = [t for t in old if t], [t for t in new if t]
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
        elif res.style.kind in ('root_rel', 'file_rel'):
            # the rewrite kept the way the old text was read; read the new text that way too, without
            # guessing again (a folder of the same name beside the file, say docs/x/experiments, would mislead)
            new = urllib.parse.unquote(re.split(r'[#?]', e.new, 1)[0]) if res.style.encoded else re.split(r'[#?]', e.new, 1)[0]
            new = new.replace('\\\\', '/').replace('\\', '/')
            got = norm(new) if res.style.kind == 'root_rel' else norm(posixpath.join(posixpath.dirname(e.file_new), new))
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
    lost, extra = fixed_old - fixed_new, fixed_new - fixed_old
    # a folder that one root became split into needs a new base ('LEGACY_ROOT'); a base that other new
    # targets sit under is no new destination, and a join that went to the wrong base still shows as lost
    for t in list(extra):
        if any(o.startswith(t + '/') for o in fixed_new):
            del extra[t]
    # location mode may gain targets: an external path that maps into the project becomes evaluable;
    # a wrong rewrite still shows as a target that went missing
    if lost or (extra and not location):
        problems.append(f'{file_new}: path targets differ; expected but missing {dict(lost)}, unexpected {dict(extra)}')
    dyn_old = [t[:-6] for t in old if t.endswith('/<dyn>')]
    dyn_new = Counter(t[:-6] for t in new if t.endswith('/<dyn>'))
    # location mode may gain some: an external path that maps into the project becomes evaluable
    if (sum(dyn_new.values()) < len(dyn_old)) if location else (len(dyn_old) != sum(dyn_new.values())):
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


def _notebook_code(text):
    """Only a notebook's code cells run; markdown cells are prose about how it was run."""
    try:
        import json
        cells = json.loads(text).get('cells', [])
    except ValueError:
        return text
    return ''.join(''.join(c.get('source', [])) if isinstance(c.get('source'), list) else c.get('source', '')
                   for c in cells if c.get('cell_type') == 'code')


def _prose_spans(src):
    """Comments, docstrings and multi-line strings of Python source: text where naming the project
    folder itself (no path below it) records where the work was done, and is kept."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    starts = [0]
    for line in src.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    off = lambda pos: starts[pos[0] - 1] + pos[1]
    out, prev = [], None
    for t in toks:
        if t.type == tokenize.COMMENT or (t.type == tokenize.STRING and (
                t.start[0] != t.end[0] or prev in (None, tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT))):
            out.append((off(t.start), off(t.end)))
        if t.type not in (tokenize.COMMENT, tokenize.NL):
            prev = t.type
    return out


def residual(files, uni, rules, absolute_check=False, old_uni=None):
    """Paths still pointing at an old place, and (absolute_check) text naming this machine. With
    `old_uni`, a reading of a token counts as an old place only if it was one: it, or its folder,
    existed before the move."""
    was = (lambda p: old_uni.exists(p) or old_uni.exists(posixpath.dirname(p))) if old_uni is not None else (lambda p: True)
    out = []
    for name in sorted(files):
        if is_record(name):
            continue
        text = _text(name, files[name])
        if text is None:
            continue
        if absolute_check and name.lower().endswith(EXECUTABLE):
            code = _notebook_code(text) if name.lower().endswith('.ipynb') else text
            prose = _prose_spans(code) if name.lower().endswith('.py') else []
            # naming the project folder itself in prose is kept; a path below it, or any name in code, is not
            hits = [m for m in PROJECT_ABS.finditer(code)
                    if re.match(r'[\\/]+[A-Za-z0-9_.\-]', code[m.end():]) or not any(a <= m.start() < b for a, b in prose)]
            m = (hits[0] if hits else None) or INTERPRETER.search(code)
            if m:
                out.append(f'{name}:{code.count(chr(10), 0, m.start()) + 1}: names this machine ({m.group(0)})')
        if rules is None:
            continue
        for m in TOKEN.finditer(text):
            tok = m.group(0)
            if '/' not in tok and '\\' not in tok:
                continue
            for cands in _interpretations(tok, name):
                # a pattern piece (lab_r46_*) does not exist itself; the folder it sits in does
                if any(uni.exists(p) or (uni.exists(posixpath.dirname(p)) and rules.map(p) is None) for p in cands):
                    break
                stale = next((p for p in cands if rules.map(p) is not None and was(p)), None)
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

"""Rewrite path expressions in Python source for the 2026-10-28 restructure.

Each path expression is evaluated in the old tree (as the 2026-10-28 feasibility scan
did): `__file__`, `.parent`, `.parents[N]`, `os.path.dirname`, `/`, `os.path.join`,
`joinpath`, `Path(...)`, and names bound to such values. Its old target T and base B
(where its constant segments start from) give the new target M(T) and new base M(B),
M being the move rules (unmoved paths map to themselves; `__file__` maps to the file's
new location). The expression is then written so it reaches M(T) from M(B):

- a climb chain changes its number of levels (`parents[N]`, `.parent` count, nested
  `dirname` calls), at its outermost climb;
- constant segments after a base are replaced by the segments of relpath(M(T), M(B)),
  one string per segment when the source wrote one per segment, else one string.

What cannot be decided is reported as Unresolved and left as written: a dynamic tail or
a whole folder whose contents go to more than one place (`Traing_Progress`), a bare
moved folder name joined to an unknown base, climbing that cannot reach the new target.

Strings, f-strings and comments that are not part of an evaluated expression go through
the text rewriter; a piece whose target folder splits is reported instead. Location mode
(phase 1) replaces project-absolute literals with an expression on the project root,
reusing a module-level root name when one exists, else inserting PROJECT_ROOT.
"""
import ast
from bisect import bisect_right
from dataclasses import dataclass
import io
import posixpath
import re
import tokenize
import warnings

from restructure_readers import Readers, read_parents
from restructure_resolve import PROJECT_ABS, norm, resolve
from restructure_text import ABS_START, INTERPRETER, Edit, rewrite_fragment

PATH_CALLS = ('Path', 'PurePath', 'PureWindowsPath', 'WindowsPath', 'PosixPath')
PASS_ATTRS = ('resolve', 'absolute', 'expanduser')
PASS_FUNCS = ('abspath', 'realpath', 'normpath')


@dataclass(frozen=True)
class Unresolved:
    file: str
    line: int
    segment: str
    reason: str
    target: str = ''


@dataclass(frozen=True)
class Val:
    rel: str
    is_path: bool
    is_file: bool = False
    dyn: bool = False


def _fname(call):
    fn = call.func
    return fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else None


def _is_str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def rewrite_python(src, file_old, file_new, ctx):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)    # legacy scripts carry invalid escapes
            tree = ast.parse(src)
    except (SyntaxError, ValueError) as exc:
        new, edits, problems = rewrite_fragment(src, file_old, file_new, ctx, 'record')
        why = f'syntax error ({exc.__class__.__name__}): rewritten as plain text, check by hand'
        return new, edits, [Unresolved(file_old, getattr(exc, 'lineno', 0) or 0, '', why)] + \
            [Unresolved(file_old, 0, '', p) for p in problems]
    job = _PyJob(src, tree, file_old, file_new, ctx)
    job.run()
    return job.result()


def evaluated_targets(src, file_rel, ctx):
    """Every path expression's target in `src` as the evaluator sees it ('<prefix>/<dyn>' for a
    dynamic tail), or None when the source does not parse. Constants inside f-strings and
    docstrings are left out: they are text, not expressions."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    job = _PyJob(src, tree, file_rel, file_rel, ctx)
    job.bind_pass(tree, record=False)
    skip = job.docstrings() | read_parents(job)      # a joined data value is checked by read_targets
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip.update(n for n in ast.walk(node))
    out = []
    for node in ast.walk(tree):
        if node in skip:
            continue
        if job.is_top_chain(node) and job.is_join_base(node):
            continue                 # a climb a join starts from: the join's target is the one that counts
        if job.is_top_chain(node) or job.join_parts(node) is not None or \
                (_is_str(node) and ABS_START.match(node.value)):
            v = job.ev(node)
            if v is not None and not v.is_file:
                out.append(v.rel + ('/<dyn>' if v.dyn else ''))
    return out


class _PyJob:
    def __init__(self, src, tree, file_old, file_new, ctx):
        self.src, self.tree, self.file_old, self.file_new, self.ctx = src, tree, file_old, file_new, ctx
        self.lines = src.splitlines(keepends=True)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))
        self.parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
        self.env = {}
        self.consumed = set()
        self.handled = set()
        self.repl, self.edits, self.unresolved = [], [], []
        self.root_uses = []      # location mode: (start, end, kind, rel)

    # ---------- positions ----------
    def off(self, lineno, col):
        line = self.lines[lineno - 1] if lineno - 1 < len(self.lines) else ''
        return self.starts[lineno - 1] + len(line.encode('utf-8')[:col].decode('utf-8', errors='ignore'))

    def span(self, node):
        return self.off(node.lineno, node.col_offset), self.off(node.end_lineno, node.end_col_offset)

    def text(self, node):
        s, e = self.span(node)
        return self.src[s:e]

    def report(self, node, reason, target=''):
        line = getattr(node, 'lineno', 0)
        self.unresolved.append(Unresolved(self.file_old, line, self.text(node) if line else '', reason, target))

    def decision(self, node, target):
        """(True, new target or None) when a recorded decision covers this expression."""
        decisions = self.ctx.decisions or {}
        text = self.text(node)
        for key in ((self.file_old, text, target), (text, target)):     # a decision for this file comes first
            if key in decisions:
                return True, decisions[key]
        return False, None

    def replace(self, start, end, new, kind, old_target='', new_target=''):
        old = self.src[start:end]
        if old == new:
            return
        self.repl.append((start, end, new))
        self.edits.append(Edit(self.file_old, self.file_new, bisect_right(self.starts, start), old, new,
                               f'py:{kind}', old_target, new_target))

    def M(self, val):
        if val.is_file:
            return self.file_new
        return (self.ctx.rules.map(val.rel) if self.ctx.rules else None) or val.rel

    def splits(self, rel):
        """Some of `rel`'s contents move differently from `rel`: a dynamic name below it is ambiguous."""
        return bool(self.ctx.rules) and self.ctx.rules.splits_under(rel)

    def diverges(self, rel):
        """Some of `rel`'s contents end up outside `rel`'s new place: even a fixed reference is ambiguous."""
        return bool(self.ctx.rules) and self.ctx.rules.diverges_under(rel)

    # ---------- evaluation ----------
    def ev(self, node):
        hints = (self.ctx.hints or {}).get(self.file_old)
        if hints and isinstance(node, (ast.Name, ast.Attribute, ast.Call)):
            text = ast.unparse(node)
            if text in hints:                # reader_hints_phaseN.json: what the tool cannot evaluate, given by hand
                return Val(hints[text], True)
        if isinstance(node, ast.Name):
            if node.id == '__file__':
                return Val(self.file_old, False, is_file=True)
            return self.env.get(node.id)
        if _is_str(node):
            if ABS_START.match(node.value):
                res = resolve(node.value, self.file_old, self.ctx.uni, self.ctx.external_map)
                if res is not None and res.style.kind == 'abs_project':
                    return Val(res.target_rel, False)
            return None
        if isinstance(node, ast.Call):
            name = _fname(node)
            fn = node.func
            if name in PATH_CALLS and node.args:
                base = self.ev(node.args[0])
                return self.join(base, node.args[1:], True) if base else None
            if name in PASS_ATTRS and isinstance(fn, ast.Attribute):
                return self.ev(fn.value)
            if name in PASS_FUNCS and node.args:
                return self.ev(node.args[0])
            if name == 'dirname' and node.args:
                return self.climb(self.ev(node.args[0]), 1, False)
            if name == 'join' and node.args and isinstance(fn, ast.Attribute) and not _is_str(fn.value):
                base = self.ev(node.args[0])
                return self.join(base, node.args[1:], False) if base else None
            if name == 'joinpath' and isinstance(fn, ast.Attribute):
                base = self.ev(fn.value)
                return self.join(base, node.args, True) if base else None
            if name == 'str' and len(node.args) == 1:
                v = self.ev(node.args[0])
                return Val(v.rel, False, v.is_file, v.dyn) if v else None
            return None
        if isinstance(node, ast.Attribute) and node.attr == 'parent':
            return self.climb(self.ev(node.value), 1, True)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'parents':
            k = node.slice
            if isinstance(k, ast.Constant) and isinstance(k.value, int):
                return self.climb(self.ev(node.value.value), k.value + 1, True)
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            base = self.ev(node.left)
            return self.join(base, [node.right], True) if base else None
        return None

    def climb(self, val, n, is_path):
        if val is None or val.dyn:
            return None
        rel = val.rel
        for _ in range(n):
            if rel == '':
                return None
            rel = posixpath.dirname(rel)
        return Val(rel, is_path)

    def join(self, base, parts, is_path):
        if base.dyn:
            return None
        rel = base.rel
        for p in parts:
            if not _is_str(p):
                return Val(rel, is_path, dyn=True)
            rel = norm(rel + '/' + p.value) if rel else norm(p.value)
            if rel is None:
                return None
        return Val(rel, is_path)

    # ---------- chains ----------
    def inner(self, node):
        """The node a climb or pass-through operation applies to, or None when `node` is neither."""
        if isinstance(node, ast.Attribute) and node.attr == 'parent':
            return node.value
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'parents':
            return node.value.value
        if isinstance(node, ast.Call):
            name = _fname(node)
            if name in PASS_ATTRS and isinstance(node.func, ast.Attribute) and not node.args:
                return node.func.value
            if name in PASS_FUNCS + ('dirname',) and len(node.args) == 1:
                return node.args[0]
            if name in PATH_CALLS and len(node.args) == 1:
                return node.args[0]
        return None

    @staticmethod
    def climb_units(node):
        if isinstance(node, ast.Attribute):
            return 1
        if isinstance(node, ast.Subscript):
            return node.slice.value + 1 if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int) else None
        if isinstance(node, ast.Call) and _fname(node) == 'dirname':
            return 1
        return 0

    def is_join_base(self, node):
        """`node` is what a join starts from: X / 'a', os.path.join(X, 'a'), Path(X, 'a'), X.joinpath('a')."""
        p = self.parent.get(node)
        if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div) and p.left is node:
            return True
        if isinstance(p, ast.Call) and len(p.args) > 1 and p.args[0] is node and \
                (_fname(p) in PATH_CALLS or (_fname(p) == 'join' and isinstance(p.func, ast.Attribute))):
            return True
        return isinstance(p, ast.Attribute) and p.attr == 'joinpath' and p.value is node

    def is_top_chain(self, node):
        if self.inner(node) is None:
            return False
        # the operation applied to `node` may sit one level up: X.parents[k] and X.resolve() put an
        # Attribute between X and the Subscript or Call that uses it
        p = self.parent.get(node)
        ups = [p, self.parent.get(p)] if isinstance(p, ast.Attribute) else [p]
        return not any(u is not None and self.inner(u) is node for u in ups)

    def do_chain(self, top):
        members, node = [], top
        while self.inner(node) is not None:
            members.append(node)
            node = self.inner(node)
        base = node
        climbs = [m for m in members if self.climb_units(m)]
        self.handled.update(members)
        if not climbs or any(self.climb_units(m) is None for m in climbs):
            return
        bval = self.ev(base)
        if bval is None or bval.dyn:
            return
        self.consumed.update(n for n in ast.walk(top) if _is_str(n))
        total = sum(self.climb_units(m) for m in climbs)
        tval = self.climb(bval, total, True)
        if tval is None:
            return
        new_b, new_t = self.M(bval), self.M(tval)
        if new_t == '' or new_b == new_t or new_b.startswith(new_t + '/'):
            via, tail = new_t, ''
        else:
            # the target is no longer above us: climb to the common ancestor, then go down
            via = posixpath.commonpath([new_b, new_t]) if new_b and new_t else ''
            tail = posixpath.relpath(new_t, via or '.')
        depth = lambda r: len(r.split('/')) if r else 0
        delta = (depth(new_b) - depth(via)) - total
        if delta == 0 and not tail:
            return
        outer = climbs[0]
        new = self.climb_text(top, members, outer, delta)
        if new is None:
            return
        if tail:
            if outer is not top:
                self.report(top, f'climbing from {new_b} cannot reach {new_t}')
                return
            if isinstance(outer, ast.Call):
                callee = self.text(outer.func)
                if '.' not in callee:
                    self.report(top, f'climbing from {new_b} cannot reach {new_t}')
                    return
                new = f"{callee.rsplit('.', 1)[0]}.join({new}, '{tail}')"
            else:
                new = '(' + new + ''.join(f" / '{seg}'" for seg in tail.split('/')) + ')'
        s, e = self.span(outer)
        self.replace(s, e, new, 'climb', tval.rel, new_t)

    def climb_text(self, top, members, outer, delta):
        """Source for `outer` changed by `delta` climbing levels, or None (reported)."""
        s, e = self.span(outer)
        if delta == 0:
            return self.src[s:e]
        if isinstance(outer, ast.Subscript):
            k = outer.slice.value + delta
            if k < 0:
                self.report(top, 'parents index would go below 0')
                return None
            ks, ke = self.span(outer.slice)
            return self.src[s:ks] + str(k) + self.src[ke:e]
        idx, run = members.index(outer), 0
        for m in members[idx:]:
            if isinstance(outer, ast.Attribute) and isinstance(m, ast.Attribute) and m.attr == 'parent':
                run += 1
            elif isinstance(outer, ast.Call) and isinstance(m, ast.Call) and _fname(m) == 'dirname':
                run += 1
            else:
                break
        if delta > 0:
            if isinstance(outer, ast.Attribute):
                return self.src[s:e] + '.parent' * delta
            callee = self.text(outer.func)
            return callee + '(' * delta + self.src[s:e] + ')' * delta
        if run < -delta:
            self.report(top, 'not enough climbing steps to remove')
            return None
        return self.text(members[idx - delta])

    # ---------- joins ----------
    def join_parts(self, node):
        """(base, parts) for a join expression, or None."""
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            p = self.parent.get(node)
            if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div) and p.left is node:
                return None          # only the outermost '/' of a chain
            parts = []
            while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                parts.insert(0, node.right)
                node = node.left
            return node, parts
        if isinstance(node, ast.Call):
            name, fn = _fname(node), node.func
            if name == 'join' and isinstance(fn, ast.Attribute) and not _is_str(fn.value) and len(node.args) > 1:
                return node.args[0], list(node.args[1:])
            if name in PATH_CALLS and len(node.args) > 1:
                return node.args[0], list(node.args[1:])
            if name == 'joinpath' and isinstance(fn, ast.Attribute) and node.args:
                return fn.value, list(node.args)
        return None

    def do_join(self, node, base, parts):
        consts = []
        for p in parts:
            if not _is_str(p):
                break
            consts.append(p)
        bval = self.ev(base)
        if bval is None or bval.dyn:
            self.bare_check(consts)
            return
        self.consumed.update(consts)
        if not consts:
            return
        dyn = len(consts) < len(parts)
        tval = self.join(bval, consts, True)
        if tval is None or any(ABS_START.match(c.value) for c in consts) or self.ctx.mode != 'moves':
            return
        new_b, new_t = self.M(bval), self.M(tval)
        if (self.splits if dyn else self.diverges)(tval.rel):
            decided, target = self.decision(node, tval.rel)
            if not decided:
                self.report(node, f'{tval.rel} holds things that move to different places; decide by hand'
                            + (' (dynamic tail)' if dyn else ''), tval.rel)
                return
            if target is None:
                return
            new_t = target
        old_rel = posixpath.relpath(tval.rel or '.', bval.rel or '.')
        new_rel = posixpath.relpath(new_t or '.', new_b or '.')
        if old_rel == new_rel:
            return
        if new_rel == '.':
            self.report(node, 'segments would vanish')
            return
        first, last = consts[0], consts[-1]
        ftxt = self.text(first)
        q = re.match(r'^([rRuUbB]*)(\'\'\'|"""|\'|")', ftxt)
        prefix, quote = (q.group(1), q.group(2)) if q else ('', "'")
        prefix = prefix.replace('u', '').replace('U', '')
        one_each = all('/' not in c.value and '\\' not in c.value for c in consts)
        if one_each:
            joiner = ' / ' if isinstance(node, ast.BinOp) else ', '
            if len(consts) > 1:
                joiner = self.src[self.span(consts[0])[1]:self.span(consts[1])[0]]
            new = joiner.join(f'{prefix}{quote}{seg}{quote}' for seg in new_rel.split('/'))
        else:
            sep = '\\' if ('\\' in first.value and 'r' in prefix.lower()) else '/'
            new = f'{prefix}{quote}{new_rel.replace("/", sep)}{quote}'
        s, e = self.span(first)[0], self.span(last)[1]
        self.replace(s, e, new, 'join', tval.rel, new_t)

    def bare_check(self, consts):
        if not self.ctx.rules or self.ctx.mode != 'moves':
            return
        tops = {r.split('/')[0] for r in self._rule_olds()}
        for c in consts:
            if c.value.strip('/\\') in tops:
                self.consumed.add(c)
                if not self.decision(c, c.value)[0]:
                    self.report(c, 'moved folder name joined to a base the tool cannot evaluate', c.value)

    def _rule_olds(self):
        sets = getattr(self.ctx.rules, 'rulesets', [self.ctx.rules])
        out = []
        for rs in sets:
            out += [r.old for r in rs.rules] + [g.parent for g in rs.globs]
        return out

    # ---------- passes ----------
    def run(self):
        self.bind_pass(self.tree, record=False)
        self.walk(self.tree)
        self.strings()
        self.comments()
        if self.ctx.data is not None:
            Readers(self, (self.ctx.seeds or {}).get(self.file_old, ())).run().rewrite()
        if self.ctx.mode == 'location':
            self.insert_root()

    def drop_inside(self, start, end):
        """Forget rewrites inside [start, end): that source is being replaced as a whole."""
        keep = [i for i, (s, e, _) in enumerate(self.repl) if not (start <= s and e <= end)]
        self.repl = [self.repl[i] for i in keep]
        self.edits = [self.edits[i] for i in keep]
        self.root_uses = [u for u in self.root_uses if not (start <= u[0] and u[1] <= end)]

    def bind_pass(self, tree, record):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                v = self.ev(node.value)
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        if v:
                            self.env[t.id] = v
                        else:
                            self.env.pop(t.id, None)
            elif isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
                v = self.ev(node.value)
                if v:
                    self.env[node.target.id] = v

    def walk(self, node):
        for child in ast.iter_child_nodes(node):
            if child not in self.handled:
                if self.is_top_chain(child):
                    self.do_chain(child)
                jp = self.join_parts(child)
                if jp is not None:
                    self.do_join(child, *jp)
            self.walk(child)

    def docstrings(self):
        out = set()
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and _is_str(first.value):
                    out.add(first.value)
        return out

    def strings(self):
        docs = self.docstrings()
        in_fstring = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.JoinedStr):
                in_fstring.update(n for n in ast.walk(node) if n is not node)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.JoinedStr):
                if node not in in_fstring:
                    self.fstring(node)
                continue
            if not _is_str(node) or node in in_fstring or node in self.consumed:
                continue
            if node in docs:
                self.fragment(node, cls='doc')      # a docstring is prose, read like a document
            elif self.ctx.mode == 'moves':
                self.fragment(node)
            else:
                self.location_literal(node)

    def fragment(self, node, ambiguous=None, cls='record'):
        s, e = self.span(node)
        new, edits, problems = rewrite_fragment(self.src[s:e], self.file_old, self.file_new, self.ctx, cls)
        ambiguous = ambiguous or self.diverges
        split = [ed for ed in edits if ed.old_target and ambiguous(ed.old_target)]
        if split:
            if not self.decision(node, split[0].old_target)[0]:
                self.report(node, f'{split[0].old_target} holds things that move to different places; decide by hand',
                            split[0].old_target)
            return
        for p in problems:
            self.report(node, p)
        if new != self.src[s:e]:
            self.replace(s, e, new, 'string', edits[0].old_target if edits else '', edits[0].new_target if edits else '')

    def fstring(self, node):
        if self.ctx.mode == 'moves':
            self.fragment(node, self.splits)      # a {name} may follow any path piece
            return
        s, e = self.span(node)
        raw = self.src[s:e]
        if '\n' in raw:
            self.fragment(node, cls='script')    # a multi-line template is text, as for plain strings
            return
        m = re.match(r'^([fFrR]{1,2})(\'\'\'|"""|\'|")', raw)
        if not m:
            return
        body_start = m.end()
        pm = re.match(r'(?:\\\\\?\\)?[A-Za-z]:(?:\\\\|\\|/)+GMM_2_Final(?:_restructure)?(?=[\\/{]|$)', raw[body_start:], re.I)
        if pm:
            self.root_uses.append((s + body_start, s + body_start + pm.end(), 'fstring', ''))
        elif PROJECT_ABS.search(raw):
            self.report(node, 'project path inside an f-string, fix by hand')

    def location_literal(self, node):
        value = node.value
        if '\n' in value:
            # a multi-line template (a generated script or report) is text: paths become project-relative,
            # an interpreter path becomes `python`
            self.fragment(node, cls='script')
            return
        if INTERPRETER.fullmatch(value):
            s, e = self.span(node)
            q = re.match(r'^[rRuUbB]*(\'\'\'|"""|\'|")', self.src[s:e])
            quote = q.group(1) if q else "'"
            self.replace(s, e, f'{quote}python{quote}', 'interpreter')
            return
        if ABS_START.match(value):
            res = resolve(value, self.file_old, self.ctx.uni, self.ctx.external_map)
            if res is not None and res.style.kind in ('abs_project', 'abs_external'):
                s, e = self.span(node)
                self.root_uses.append((s, e, 'literal_sep' if value.endswith(('/', '\\')) else 'literal', res.target_rel))
                return
        if PROJECT_ABS.search(value):
            self.report(node, 'project path inside a string literal, fix by hand')

    def comments(self):
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(self.src).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return
        for tok in toks:
            if tok.type != tokenize.COMMENT:
                continue
            s = self.starts[tok.start[0] - 1] + tok.start[1]
            e = self.starts[tok.end[0] - 1] + tok.end[1]
            new, edits, _ = rewrite_fragment(self.src[s:e], self.file_old, self.file_new, self.ctx, 'doc')
            if new != self.src[s:e]:
                self.replace(s, e, new, 'comment', edits[0].old_target if edits else '', edits[0].new_target if edits else '')

    # ---------- location mode: project root ----------
    def module_root_name(self, before, path_only=False):
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                v = self.ev(stmt.value)
                if v is not None and v.rel == '' and not v.dyn and self.span(stmt)[1] <= before and (v.is_path or not path_only):
                    return stmt.targets[0].id, v.is_path
        return None

    def insert_root(self):
        if not self.root_uses:
            return
        # a path read out of a data file is joined with '/', so it needs a Path-valued root
        groups = {}
        for use in self.root_uses:
            groups.setdefault(use[2].startswith('reader'), []).append(use)
        names, missing = {}, []
        for reader, uses in groups.items():
            first = min(u[0] for u in uses)
            names[reader] = self.module_root_name(first, path_only=reader)
            if names[reader] is None:
                missing.append(first)
        if missing:
            bound = {t.id for n in ast.walk(self.tree) if isinstance(n, (ast.Assign, ast.AnnAssign))
                     for t in (n.targets if isinstance(n, ast.Assign) else [n.target]) if isinstance(t, ast.Name)}
            inserted = '_PROJECT_ROOT' if 'PROJECT_ROOT' in bound else 'PROJECT_ROOT'
            self.insert_definition(inserted, min(missing))
            names = {k: v or (inserted, True) for k, v in names.items()}
        for s, e, kind, rel in self.root_uses:
            name, is_path = names[kind.startswith('reader')]
            # a read is wrapped by text inserted before and after it, so rewrites inside it still apply
            if kind == 'reader_join':
                self.replace(s, s, f'{name} / ', 'root')
                continue
            if kind == 'reader_str':
                self.replace(s, s, f'str({name} / ', 'root')
                self.replace(e, e, ')', 'root')
                continue
            if kind == 'reader_base':
                new = name
            elif kind == 'fstring':
                new = '{' + name + '}'
            elif not rel:
                new = f'str({name})' if is_path else name
            elif is_path:
                new = f"str({name} / '{rel}')"
            else:
                new = f"os.path.join({name}, '{rel}')"
            if kind == 'literal_sep':
                new += " + '/'"
            self.replace(s, e, new, 'root', '', rel)

    def insert_definition(self, name, before):
        """Define the root after the last top-level import that precedes its first use."""
        last = None
        for stmt in self.tree.body:
            if self.span(stmt)[1] > before:
                break
            if isinstance(stmt, (ast.Import, ast.ImportFrom)) or \
                    (stmt is self.tree.body[0] and isinstance(stmt, ast.Expr) and _is_str(stmt.value)):
                last = stmt
        pos = self.starts[last.end_lineno] if last is not None else 0
        if pos == 0:
            while pos < len(self.src) and self.src.startswith('#', pos):     # shebang / coding lines stay first
                nxt = self.src.find('\n', pos)
                pos = len(self.src) if nxt < 0 else nxt + 1
        imported_path = any(isinstance(n, ast.ImportFrom) and n.module == 'pathlib' and self.span(n)[1] <= pos and
                            any(a.name == 'Path' and a.asname is None for a in n.names) for n in self.tree.body)
        path_bound = any(isinstance(n, ast.Name) and n.id == 'Path' and isinstance(n.ctx, ast.Store) for n in ast.walk(self.tree))
        nl = '\r\n' if '\r\n' in self.src else '\n'
        d = posixpath.dirname(self.file_new)
        depth = len(d.split('/')) if d else 0
        root = 'Path(__file__).resolve().parent' if depth == 0 else f'Path(__file__).resolve().parents[{depth}]'
        lines = ''
        if not imported_path:
            if path_bound:
                root = root.replace('Path(', "__import__('pathlib').Path(", 1)
            else:
                lines += 'from pathlib import Path' + nl
        lines += f'{name} = {root}{nl}'
        if pos > 0 and not self.src[:pos].endswith(('\n', '\r')):
            lines = nl + lines
        self.repl.append((pos, pos, lines))

    # ---------- result ----------
    def result(self):
        if not self.repl:
            return self.src, self.edits, self.unresolved
        out, last = [], 0
        for start, end, new in sorted(self.repl, key=lambda r: (r[0], r[1])):
            if start < last:
                self.unresolved.append(Unresolved(self.file_old, bisect_right(self.starts, start), '', 'overlapping rewrites; file left unchanged'))
                return self.src, [], self.unresolved
            out.append(self.src[last:start]); out.append(new); last = end
        out.append(self.src[last:])
        return ''.join(out), self.edits, self.unresolved

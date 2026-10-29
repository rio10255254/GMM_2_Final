"""Path values that Python code reads back out of data files a phase rewrites.

Location mode turns the absolute project paths inside records into project-relative ones.
A record a program reads back (an experiment's config/experiment.json, a manifest) then
hands that program a relative path, which it joins to its own folder or opens from the
working directory: the wrong place. Each value is followed from the call that loads the
file to the expressions that read it with fixed keys, so the reader can be written to join
the project root, and so verification can check that every read lands where it did.

Followed: a call whose first argument (through open(), .open(), .read_text(), or a name
from `with open(...) as f`) evaluates to a rewritten data file; constant subscripts and
.get('key'); names bound to such values, per function scope; `self.attr` within a class;
for-loops and comprehensions over lists, .values() and .items(); same-module functions
that return such a value (their callers are followed) or receive one as an argument. A
value with rewritten paths below it that goes anywhere else is reported for checking by
hand, as is a read the project root cannot fix (a command line, a list mixing absolute
and relative entries) or one reached through a name that also holds other values.
"""
import ast
from collections import defaultdict
from dataclasses import dataclass
import json
import re
import warnings

from restructure_resolve import norm, norm_abs, resolve
from restructure_text import ABS_START

DATA_EXT = ('.json', '.yaml', '.yml', '.toml')
HEX64 = re.compile(r'[0-9a-fA-F]{64}')
DATA_NAME = re.compile(r'[^\s"\'`/\\()\[\]{},;:=+*]+\.(?:json|ya?ml|toml)(?![A-Za-z0-9_])', re.I)
STAR = '*'
PATH_CALLS = ('Path', 'PurePath', 'PureWindowsPath', 'WindowsPath', 'PosixPath')
OPENERS = ('read_text', 'read_bytes', 'open')
FILE_MODULES = ('io', 'codecs', 'gzip', 'builtins')
PARSER_MODULES = ('json', 'yaml', 'toml', 'tomllib', 'tomli', 'orjson', 'ujson', 'simplejson', 'json5', 'hjson')
PARSERS = ('load', 'loads', 'safe_load', 'full_load', 'unsafe_load')
# uses of a loaded value that read no path out of it
HARMLESS = ('len', 'isinstance', 'bool', 'print', 'repr', 'type', 'id', 'dump', 'dumps', 'pprint', 'pformat',
            'keys', 'hash', 'sorted', 'set', 'any', 'all')
NEUTRAL = (None, '', 0, False)
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _fname(call):
    fn = call.func
    return fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else None


# ---------- data ----------
def parse_data(name, data):
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return None
    low = name.lower()
    try:
        if low.endswith('.json'):
            return json.loads(text)
        if low.endswith(('.yaml', '.yml')):
            import yaml
            return yaml.safe_load(text)
        if low.endswith('.toml'):
            import tomllib
            return tomllib.loads(text)
    except Exception:
        return None
    return None


def str_leaves(obj, keys=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from str_leaves(v, keys + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from str_leaves(v, keys + (i,))
    elif isinstance(obj, str):
        yield keys, obj


def matches(pattern, keys):
    return len(pattern) == len(keys) and all(p == STAR or p == k for p, k in zip(pattern, keys))


def below(pattern, keys):
    return len(keys) > len(pattern) and all(p == STAR or p == k for p, k in zip(pattern, keys))


class DataView:
    """Old and new contents of the data files a phase rewrites, keyed by their old names."""

    def __init__(self, old, new, renames=None):
        self.old, self.new = old, new
        self.by_new = {(renames or {}).get(n, n): n for n in old}
        self.basenames = {n.rsplit('/', 1)[-1].lower() for n in old}
        self._objs, self._leaves, self._changed = {}, {}, {}

    def mentioned_in(self, src):
        """A cheap filter: the source names one of these files (a load site always spells its name)."""
        return any(m.group(0).lower() in self.basenames for m in DATA_NAME.finditer(src))

    def find(self, rel, side):
        """The old name of the data file at `rel` as `side` sees it, or None when it is not one of them."""
        name = rel if side == 'old' else self.by_new.get(rel)
        return name if name in self.old and name in self.new and name.lower().endswith(DATA_EXT) else None

    def obj(self, name, side='old'):
        if (name, side) not in self._objs:
            self._objs[(name, side)] = parse_data(name, (self.old if side == 'old' else self.new)[name])
        return self._objs[(name, side)]

    def leaves(self, name):
        """{keys: (old text, new text)} for every string leaf of the old content."""
        if name not in self._leaves:
            o, n = self.obj(name, 'old'), self.obj(name, 'new')
            new = dict(str_leaves(n)) if n is not None else {}
            self._leaves[name] = {k: (v, new.get(k)) for k, v in str_leaves(o)} if o is not None else {}
        return self._leaves[name]

    def changed(self, name):
        """The leaves whose text this phase changed; content hashes are not paths."""
        if name not in self._changed:
            self._changed[name] = {k: v for k, v in self.leaves(name).items()
                                   if v[1] is not None and v[0] != v[1] and not HEX64.fullmatch(v[0])}
        return self._changed[name]

    def kind_at(self, name, pattern):
        node = self.obj(name)
        for k in pattern:
            if k == STAR:
                items = list(node.values()) if isinstance(node, dict) else node if isinstance(node, list) else []
                if not items:
                    return None
                node = items[0]
            elif isinstance(node, dict) and k in node:
                node = node[k]
            elif isinstance(node, list) and isinstance(k, int) and -len(node) <= k < len(node):
                node = node[k]
            else:
                return None
        return 'list' if isinstance(node, list) else 'dict' if isinstance(node, dict) else None


# ---------- following values ----------
@dataclass(frozen=True)
class Read:
    node: ast.AST
    name: str            # data file, old name
    pattern: tuple       # keys, STAR for any element
    via: frozenset       # bindings passed through


class Readers:
    def __init__(self, job):
        self.job, self.ctx = job, job.ctx
        self.view, self.side = job.ctx.data, job.ctx.data_side
        self.parent = job.parent
        self.queue, self.seen = [], set()
        self.reads, self.escapes = [], []
        self.bound = defaultdict(set)        # binding -> store nodes or calls it was bound through
        self._index()

    # ---------- index ----------
    def scope(self, node):
        p = self.parent.get(node)
        while p is not None and not isinstance(p, SCOPES):
            p = self.parent.get(p)
        return p

    def class_of(self, node):
        p = self.parent.get(node)
        while p is not None and not isinstance(p, ast.ClassDef):
            p = self.parent.get(p)
        return p

    def home_store(self, node):
        s = self.scope(node)
        return None if (s, node.id) in self.globals else s

    def home(self, node):
        s = self.scope(node)
        while s is not None:
            if (s, node.id) in self.stores and (s, node.id) not in self.globals:
                return s
            s = self.scope(s)
        return None

    def _index(self):
        tree = self.job.tree
        self.globals = set()
        self.stores = defaultdict(list)      # (scope, name) -> Name/arg nodes that bind it
        self.uses = defaultdict(list)        # (scope, name) -> Name loads
        self.attr_stores = defaultdict(list)
        self.attr_uses = defaultdict(list)   # (class, attr) -> self.attr loads
        self.defs = defaultdict(list)
        self.calls = defaultdict(list)       # function name -> calls by name or self.<name>
        self.opened = {}                     # (scope, name) -> path expression of an opened file
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                for n in node.names:
                    self.globals.add((self.scope(node), n))
        loads = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if not isinstance(node, ast.Lambda):
                    self.defs[node.name].append(node)
                a = node.args
                for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
                    self.stores[(node, arg.arg)].append(arg)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    loads.append(node)
                else:
                    self.stores[(self.home_store(node), node.id)].append(node)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self':
                (self.attr_uses if isinstance(node.ctx, ast.Load) else self.attr_stores)[(self.class_of(node), node.attr)].append(node)
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    self.calls[fn.id].append(node)
                elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == 'self':
                    self.calls[fn.attr].append(node)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for it in node.items:
                    if isinstance(it.optional_vars, ast.Name):
                        self.opened[(self.home_store(it.optional_vars), it.optional_vars.id)] = it.context_expr
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and self.is_opener(node.value):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.opened[(self.home_store(t), t.id)] = node.value
        for node in loads:
            self.uses[(self.home(node), node.id)].append(node)
        self.loader_defs = {name for name, ds in self.defs.items()
                            if any(isinstance(n, ast.Call) and self.is_parser(n, own=False) for d in ds for n in ast.walk(d))}

    def is_opener(self, call):
        fn, name = call.func, _fname(call)
        if isinstance(fn, ast.Name):
            return name == 'open'
        return name in OPENERS

    def is_parser(self, call, own=True):
        fn, name = call.func, _fname(call)
        if isinstance(fn, ast.Attribute):
            v = fn.value
            while isinstance(v, ast.Attribute):
                v = v.value
            return name in PARSERS and isinstance(v, ast.Name) and v.id in PARSER_MODULES
        return isinstance(fn, ast.Name) and (name in PARSERS or (own and name in self.loader_defs))

    # ---------- load sites ----------
    def unwrap(self, node):
        for _ in range(6):
            if isinstance(node, ast.Call) and self.is_opener(node):
                fn = node.func
                if isinstance(fn, ast.Attribute) and not (isinstance(fn.value, ast.Name) and fn.value.id in FILE_MODULES):
                    node = fn.value
                elif node.args:
                    node = node.args[0]
                else:
                    return node
            elif isinstance(node, ast.Name) and (self.home(node), node.id) in self.opened:
                node = self.opened[(self.home(node), node.id)]
            else:
                return node
        return node

    def data_file(self, node):
        try:
            v = self.job.ev(self.unwrap(node))
        except RecursionError:
            return None
        if v is None or v.dyn or v.is_file:
            return None
        return self.view.find(v.rel, self.side)

    def run(self):
        if self.view is None or not self.view.mentioned_in(self.job.src):
            return self
        for node in ast.walk(self.job.tree):
            if not isinstance(node, ast.Call) or self.is_opener(node) or _fname(node) in PATH_CALLS:
                continue
            arg = node.args[0] if node.args else \
                next((k.value for k in node.keywords if k.arg in ('path', 'file', 'fp', 'filename', 'fname')), None)
            name = self.data_file(arg) if arg is not None else None
            if name:
                self.push(node, name, (), frozenset(), self.is_parser(node))
        while self.queue:
            self.follow(*self.queue.pop())
        return self

    def push(self, node, name, pattern, via, certain):
        key = (node, name, pattern, via)
        if key not in self.seen:
            self.seen.add(key)
            self.queue.append(key + (certain,))

    # ---------- following ----------
    def follow(self, node, name, pattern, via, certain):
        changed = self.view.changed(name)
        if any(matches(pattern, k) for k in changed):
            self.reads.append(Read(node, name, pattern, via))
            return
        if not any(below(pattern, k) for k in changed):
            return
        p = self.parent.get(node)

        def escape(why):
            if certain and any(below(pattern, k) and ABS_START.match(v[0]) for k, v in changed.items()):
                self.escapes.append((node, name, pattern, why))

        if isinstance(p, ast.Subscript) and p.value is node:
            if isinstance(p.ctx, ast.Load):
                k = p.slice
                if isinstance(k, ast.Constant) and isinstance(k.value, (str, int)) and not isinstance(k.value, bool):
                    self.push(p, name, pattern + (k.value,), via, certain)
                else:
                    escape('a dynamic key')
            return
        if isinstance(p, ast.Attribute) and p.value is node:
            call = self.parent.get(p)
            is_call = isinstance(call, ast.Call) and call.func is p
            if p.attr == 'get' and is_call:
                k = call.args[0] if call.args else None
                if isinstance(k, ast.Constant) and isinstance(k.value, (str, int)) and not isinstance(k.value, bool):
                    self.push(call, name, pattern + (k.value,), via, certain)
                else:
                    escape('a dynamic key')
            elif p.attr in ('values', 'items') and is_call:
                self.iterate(call, name, pattern, via, certain, pair=p.attr == 'items', escape=escape)
            elif p.attr == 'copy' and is_call:
                self.push(call, name, pattern, via, certain)
            elif p.attr not in HARMLESS:
                escape(f'.{p.attr}')
            return
        if isinstance(p, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and p.value is node:
            for t in (p.targets if isinstance(p, ast.Assign) else [p.target]):
                self.bind(t, name, pattern, via, certain)
            if isinstance(p, ast.NamedExpr):
                self.push(p, name, pattern, via, certain)
            return
        if isinstance(p, ast.Return):
            f = self.scope(p)
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for call in self.calls.get(f.name, []):
                    self.push(call, name, pattern, via, certain)
            return
        if (isinstance(p, ast.IfExp) and node is not p.test) or isinstance(p, ast.BoolOp):
            self.push(p, name, pattern, via, certain)
            return
        if isinstance(p, (ast.For, ast.AsyncFor, ast.comprehension)) and p.iter is node:
            if self.view.kind_at(name, pattern) == 'list':
                self.loop(p, name, pattern, via, certain, pair=False, escape=escape)
            return                                   # iterating a dict yields its keys
        call, kw = (self.parent.get(p), p.arg) if isinstance(p, ast.keyword) else (p, None)
        if isinstance(call, ast.Call) and (node in call.args or kw):
            callee = _fname(call)
            if callee == 'enumerate' and call.args and call.args[0] is node:
                self.iterate(call, name, pattern, via, certain, pair=True, escape=escape)
            elif callee in ('deepcopy', 'copy', 'dict'):
                self.push(call, name, pattern, via, certain)
            elif callee in HARMLESS:
                pass
            elif callee in self.defs and (isinstance(call.func, ast.Name) or
                                          (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                                           and call.func.value.id == 'self')):
                self.argument(call, node, kw, name, pattern, via, certain, escape)
            else:
                escape(f'{callee or "a call"}()')
            return
        if isinstance(p, (ast.Compare, ast.Expr, ast.Assert, ast.If, ast.While)) or p is None:
            return
        escape(type(p).__name__)

    def iterate(self, producer, name, pattern, via, certain, pair, escape):
        loop = self.parent.get(producer)
        if isinstance(loop, (ast.For, ast.AsyncFor, ast.comprehension)) and loop.iter is producer:
            self.loop(loop, name, pattern, via, certain, pair, escape)
        else:
            escape(f'{_fname(producer)}()')

    def loop(self, loop, name, pattern, via, certain, pair, escape):
        t = loop.target
        if pair:
            if not (isinstance(t, (ast.Tuple, ast.List)) and len(t.elts) == 2):
                escape('a loop target')
                return
            t = t.elts[1]
        self.bind(t, name, pattern + (STAR,), via, certain)

    def bind(self, t, name, pattern, via, certain):
        if isinstance(t, ast.Name):
            key = ('name', self.home_store(t), t.id)
            uses = self.uses.get(key[1:], [])
        elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self':
            key = ('attr', self.class_of(t), t.attr)
            uses = self.attr_uses.get(key[1:], [])
        else:
            if certain:
                self.escapes.append((t, name, pattern, 'unpacking or a container'))
            return
        self.bound[key].add(t)
        for u in uses:
            self.push(u, name, pattern, via | {key}, certain)

    def argument(self, call, node, kw, name, pattern, via, certain, escape):
        method = isinstance(call.func, ast.Attribute)
        for d in self.defs[_fname(call)]:
            a = d.args
            params = a.posonlyargs + a.args
            if method:
                params = params[1:]
            if kw is not None:
                target = next((x for x in params + a.kwonlyargs if x.arg == kw), None)
            else:
                i = call.args.index(node)
                target = params[i] if i < len(params) and not any(isinstance(x, ast.Starred) for x in call.args[:i + 1]) else None
            if target is None:
                escape(f'{_fname(call)}()')
                continue
            key = ('name', d, target.arg)
            self.bound[key].add(call)
            for u in self.uses.get((d, target.arg), []):
                self.push(u, name, pattern, via | {key}, certain)

    def ambiguous(self, key):
        """Some way this binding gets its value is not a followed data value."""
        kind, scope, ident = key
        if kind == 'attr':
            stores = self.attr_stores.get((scope, ident), [])
        else:
            stores = [s for s in self.stores.get((scope, ident), []) if not isinstance(s, ast.arg)]
            params = [s for s in self.stores.get((scope, ident), []) if isinstance(s, ast.arg)]
            if params:
                d = scope
                calls = self.calls.get(getattr(d, 'name', None), [])
                if not calls or any(c not in self.bound[key] for c in calls):
                    return True
        for s in stores:
            if s in self.bound[key]:
                continue
            p = self.parent.get(s)
            if isinstance(p, (ast.Assign, ast.AnnAssign)) and self._neutral(p.value):
                continue
            return True
        return False

    @staticmethod
    def _neutral(v):
        if v is None:
            return True
        if isinstance(v, ast.Constant):
            return v.value in NEUTRAL
        return isinstance(v, (ast.Dict, ast.List)) and not (v.keys if isinstance(v, ast.Dict) else v.elts)

    # ---------- where a read lands ----------
    def groups(self):
        """{read node: ([(data file, keys, old text, new text)], bindings passed through)}"""
        out = {}
        for r in self.reads:
            leaves, via = out.setdefault(r.node, (set(), set()))
            for keys, (o, n) in self.view.leaves(r.name).items():
                if n is not None and matches(r.pattern, keys):
                    leaves.add((r.name, keys, o, n))
            via |= r.via
        return out

    def base(self, node):
        """The folder a read value is joined to: a Val, 'cwd' when used as is, None when not evaluable."""
        p = self.parent.get(node)
        ev = self.job.ev
        if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div) and p.right is node:
            return ev(p.left)
        if isinstance(p, ast.Call) and node in p.args:
            name, fn, i = _fname(p), p.func, p.args.index(node)
            if name == 'joinpath' and isinstance(fn, ast.Attribute):
                b, parts = ev(fn.value), p.args[:i]
            elif i > 0 and (name in PATH_CALLS or (name == 'join' and isinstance(fn, ast.Attribute))):
                b, parts = ev(p.args[0]), p.args[1:i]
            else:
                return 'cwd'
            if b is None or b.dyn:
                return None
            return self.job.join(b, parts, True)
        return 'cwd'

    def target(self, node, value, rooted=False):
        if ABS_START.match(value):
            res = resolve(value, self.job.file_old, self.ctx.uni, self.ctx.external_map)
            if res is not None and res.style.kind in ('abs_project', 'abs_external'):
                return res.target_rel
            return 'abs:' + norm_abs(value).lower()
        if rooted:
            t = norm(value)
            return t if t is not None else 'bad:' + value
        b = self.base(node)
        if b == 'cwd':
            return 'cwd:' + value.replace('\\', '/')
        if b is None or b.dyn:
            return 'unknown:' + value.replace('\\', '/')
        t = norm(b.rel + '/' + value) if b.rel else norm(value)
        return t if t is not None else 'bad:' + value

    def mapped(self, t):
        rules = self.ctx.rules
        return (rules.map(t) if rules and ':' not in t else None) or t

    # ---------- rewriting ----------
    def rewrite(self):
        job = self.job
        for node, (leaves, via) in self.groups().items():
            changed = sorted((l for l in leaves if l[2] != l[3] and not HEX64.fullmatch(l[2])), key=repr)
            if not changed:
                continue
            name, keys = changed[0][0], changed[0][1]
            label = f"{name}:{'/'.join(map(str, keys))}"
            expect = {l: self.mapped(self.target(node, l[2])) for l in leaves}
            if all(self.target(node, l[3]) == expect[l] for l in leaves):
                continue
            if job.ctx.mode != 'location' or not all(self.target(node, l[3], rooted=True) == expect[l] for l in leaves):
                job.report(node, f'data value {label} read here would no longer reach {expect[changed[0]]}; '
                                 'the project root does not fix it, check by hand', label)
                continue
            if any(re.search(r'\s', l[2]) and not self.ctx.uni.exists(expect[l]) for l in changed):
                job.report(node, f'data value {label} read here holds more than a path; check by hand', label)
                continue
            amb = sorted(k[2] for k in via if self.ambiguous(k))
            if amb:
                job.report(node, f'data value {label} reaches here through {", ".join(amb)}, which also holds other '
                                 'values; check by hand', label)
                continue
            self.emit(node)
        done = set()
        for node, name, pattern, why in self.escapes:
            if node in done:
                continue
            done.add(node)
            keys = '/'.join(map(str, pattern)) or '(whole file)'
            job.report(node, f'data value {name}:{keys} holds rewritten paths and goes into {why}; '
                             'the tool cannot follow it, check by hand', name)

    def emit(self, node):
        job, p = self.job, self.parent.get(node)
        if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div) and p.right is node:
            s, e = job.span(p.left)
            job.drop_inside(s, e)
            job.root_uses.append((s, e, 'reader_base', ''))
            return
        s, e = job.span(node)
        if isinstance(p, ast.Call) and node in p.args and (_fname(p) in PATH_CALLS or _fname(p) == 'joinpath'):
            job.root_uses.append((s, e, 'reader_join', ''))
        else:
            job.root_uses.append((s, e, 'reader_str', ''))


def read_parents(job):
    """Expressions that join a followed read value: their evaluation belongs to the read check."""
    if job.ctx.data is None or not job.ctx.data.mentioned_in(job.src):
        return set()
    r = Readers(job).run()
    out = set()
    for read in r.reads:
        p = job.parent.get(read.node)
        if isinstance(p, ast.BinOp) or isinstance(p, ast.Call):
            out.add(p)
    return out


def read_targets(src, file_rel, ctx):
    """[(data file, keys, target)] for every read of a changed data value, with the value of
    ctx.data_side, or None when the source does not parse."""
    from restructure_python import _PyJob
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    job = _PyJob(src, tree, file_rel, file_rel, ctx)
    job.bind_pass(tree, record=False)
    if ctx.data is None:
        return []
    r = Readers(job).run()
    out = []
    for node, (leaves, _) in r.groups().items():
        for name, keys, o, n in leaves:
            if o != n and not HEX64.fullmatch(o):
                out.append((name, keys, r.target(node, o if ctx.data_side == 'old' else n)))
    return out

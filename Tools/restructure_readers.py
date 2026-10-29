"""Path values that Python code reads back out of data files a phase rewrites.

Location mode turns the absolute project paths inside records into project-relative ones.
A record a program reads back (an experiment's config/experiment.json, a manifest) then
hands that program a relative path, which it joins to its own folder or opens from the
working directory: the wrong place. Each value is followed from the call that loads the
file to the expressions that read it with fixed keys, so the reader can be written to join
the project root, and so verification can check that every read lands where it did.

Followed: a call whose first argument (through open(), .open(), .read_text(), or a name
from `with open(...) as f`) evaluates to a rewritten data file; constant subscripts and
.get('key'); names bound to such values (the binding that reaches each use, per scope;
comprehensions are scopes of their own); `self.attr` within a class; for-loops and
comprehensions over lists, .values() and .items(); values put into dict and list literals,
dict(key=...), .append() and comprehensions; functions that return such a value (their
callers are followed) or receive one as an argument, in the same module or, through
imports that resolve to a file of the project, in another (link() carries values across
modules until nothing new arrives).

A value with rewritten paths below it that goes anywhere else is reported for checking
by hand, as is a read the project root cannot fix (a command line, a list mixing absolute
and relative entries) or one reached through a name that also holds other values.
"""
import ast
from collections import defaultdict
from dataclasses import dataclass
import json
import posixpath
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
LOADER_NAME = re.compile(r'load|read', re.I)
# uses of a loaded value that read no path out of it
HARMLESS = ('len', 'isinstance', 'bool', 'print', 'repr', 'type', 'id', 'dump', 'dumps', 'pprint', 'pformat',
            'keys', 'hash', 'set', 'any', 'all', 'format')
# library calls that write a value out or test membership: they read no path out of it
WRITERS = ('save', 'savez', 'savez_compressed', 'savemat', 'dump', 'writerow', 'writerows', 'to_csv', 'to_json',
           'isin', 'issubset', 'issuperset', 'intersection', 'union', 'difference')
TYPE_CHECKS = ('isinstance', 'type', 'bool', 'len', 'id', 'hash', 'int', 'float', 'round')
SAME_SHAPE = ('deepcopy', 'copy', 'dict', 'list', 'tuple', 'sorted', 'reversed', 'OrderedDict')
NEUTRAL = (None, '', 0, False)
COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda) + COMPS
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
SELF = ('self', 'cls')


def _fname(call):
    fn = call.func
    return fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else None


def _const_key(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)) and not isinstance(node.value, bool):
        return True, node.value
    return False, None


def _pos(node):
    return node.lineno, node.col_offset


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


@dataclass(frozen=True)
class AnyOf:
    """A computed key: one of `keys` (a loop over constants), or a key matching `regex` (an f-string)."""
    keys: frozenset = None
    regex: str = None

    def accepts(self, k):
        if self.keys is not None:
            return k in self.keys
        return isinstance(k, str) and re.fullmatch(self.regex, k) is not None

    def __str__(self):
        return '{' + ','.join(sorted(map(str, self.keys))) + '}' if self.keys is not None else self.regex


def fits(p, k):
    """Pattern element `p` can be data key `k`."""
    return p == STAR or p == k or (isinstance(p, AnyOf) and p.accepts(k))


def overlap(a, b):
    """Two pattern elements can stand for the same key."""
    if a == STAR or b == STAR or a == b or (isinstance(a, AnyOf) and isinstance(b, AnyOf)):
        return True
    return (isinstance(a, AnyOf) and a.accepts(b)) or (isinstance(b, AnyOf) and b.accepts(a))


def matches(pattern, keys):
    return len(pattern) == len(keys) and all(fits(p, k) for p, k in zip(pattern, keys))


def below(pattern, keys):
    return len(keys) > len(pattern) and all(fits(p, k) for p, k in zip(pattern, keys))


def pathlike(text):
    return ABS_START.match(text) is not None or '/' in text or '\\' in text


def mentions(src, basenames):
    """A cheap filter: the source names one of these files (a load site always spells its name)."""
    return any(m.group(0).lower() in basenames for m in DATA_NAME.finditer(src))


class DataView:
    """Old and new contents of the data files a phase rewrites, keyed by their old names."""

    def __init__(self, old, new, renames=None):
        self.old, self.new = old, new
        self.by_new = {(renames or {}).get(n, n): n for n in old}
        self.basenames = {n.rsplit('/', 1)[-1].lower() for n in old}
        self._objs, self._leaves, self._changed = {}, {}, {}

    def mentioned_in(self, src):
        return mentions(src, self.basenames)

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

    def kinds_at(self, name, pattern):
        """Every kind of value ('dict', 'list', 'str', 'other') the pattern can stand for."""
        nodes = [self.obj(name)]
        for k in pattern:
            nxt = []
            for node in nodes:
                items = list(node.items()) if isinstance(node, dict) else list(enumerate(node)) if isinstance(node, list) else []
                nxt += [v for key, v in items if fits(k, key)]
            nodes = nxt
        return {'dict' if isinstance(n, dict) else 'list' if isinstance(n, list) else 'str' if isinstance(n, str) else 'other'
                for n in nodes}

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
    """One module. `seeds` are values arriving from other modules (see link()):
    ('param', function, position or keyword, data, pattern, prefix, certain)
    ('global', imported name, data, pattern, prefix, certain)
    ('ret', imported function, data, pattern, prefix, certain)

    A followed value is the part `pattern` of data file `data`, wrapped in `prefix`: keys an
    access must go through first (a value put into {'k': value} has prefix ('k',)). Only an
    unwrapped value that is one string leaf is a read. `certain` is False for a value from a
    call that may not parse the file (shutil.copy2(path, ...)): it is followed but never
    reported as escaping."""

    def __init__(self, job, seeds=()):
        self.job, self.ctx = job, job.ctx
        self.view, self.side = job.ctx.data, job.ctx.data_side
        self.parent = job.parent
        self.seeds = seeds
        self.queue, self.seen = [], set()
        self.reads, self.escapes, self.pending = [], [], []
        self.outgoing = set()                 # (file, function, slot, data, pattern, prefix, certain)
        self.globals_out = set()              # (file, module-level name, data, pattern, prefix, certain)
        self.exports = defaultdict(set)       # module-level name -> {(data, pattern, prefix, certain)}
        self.returned = defaultdict(set)      # module-level function -> {(data, pattern, prefix, certain)}
        self.bound = defaultdict(set)         # binding -> store nodes / calls / 'seed' it was bound through
        self._imports = None
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
        self.stores = defaultdict(list)      # (scope, name) -> Name / arg nodes that bind it
        self.uses = defaultdict(list)        # (scope, name) -> Name loads
        self.attr_stores = defaultdict(list)
        self.attr_uses = defaultdict(list)   # (class, attr) -> self.attr loads
        self.defs = defaultdict(list)
        self.calls = defaultdict(list)       # function name -> calls by name or self.<name>
        self.opened = {}                     # (scope, name) -> path expression of an opened file
        self.syspath = []
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
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in SELF:
                (self.attr_uses if isinstance(node.ctx, ast.Load) else self.attr_stores)[(self.class_of(node), node.attr)].append(node)
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    self.calls[fn.id].append(node)
                elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in SELF:
                    self.calls[fn.attr].append(node)
                if isinstance(fn, ast.Attribute) and fn.attr in ('insert', 'append') and \
                        isinstance(fn.value, ast.Attribute) and fn.value.attr == 'path' and \
                        isinstance(fn.value.value, ast.Name) and fn.value.value.id == 'sys' and node.args:
                    v = self.job.ev(node.args[-1])
                    if v is not None and not v.dyn:
                        self.syspath.append(v.rel)
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

    # ---------- imports ----------
    def module_file(self, module, level):
        d = posixpath.dirname(self.job.file_old)
        sub = (module or '').replace('.', '/')
        if level:
            base = d
            for _ in range(level - 1):
                base = posixpath.dirname(base)
            dirs = [base]
        else:
            dirs, a = list(self.syspath) + [d], d
            while a:
                a = posixpath.dirname(a)
                dirs.append(a)
        for b in dirs:
            if not sub:
                continue
            for c in (f'{b}/{sub}.py' if b else f'{sub}.py', f'{b}/{sub}/__init__.py' if b else f'{sub}/__init__.py'):
                c = norm(c)
                if c and c != self.job.file_old and self.ctx.uni.exists(c):
                    return c
        return None

    def imports(self):
        """{local name: (file, name in that file, or None for the module itself)} for project modules."""
        if self._imports is None:
            out = {}
            for node in ast.walk(self.job.tree):
                if isinstance(node, ast.ImportFrom):
                    f = self.module_file(node.module, node.level)
                    for a in node.names:
                        if a.name == '*':
                            for n in module_names(self.ctx, f) if f else ():
                                if not n.startswith('_'):
                                    out.setdefault(n, (f, n))
                            continue
                        local = a.asname or a.name
                        sub = self.module_file(((node.module + '.') if node.module else '') + a.name, node.level)
                        if sub:
                            out[local] = (sub, None)
                        elif f:
                            out[local] = (f, a.name)
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        if a.asname or '.' not in a.name:
                            f = self.module_file(a.name, 0)
                            if f:
                                out[a.asname or a.name] = (f, None)
            assigns = [n for n in ast.walk(self.job.tree) if isinstance(n, ast.Assign) and len(n.targets) == 1
                       and isinstance(n.targets[0], ast.Name)]
            for node in assigns:                       # a module loaded from its file path
                f = self.loaded_module(node.value)
                if f:
                    out[node.targets[0].id] = (f, None)
            for node in assigns:                       # check = common.verify
                v = node.value
                if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id in out and \
                        out[v.value.id][1] is None:
                    out.setdefault(node.targets[0].id, (out[v.value.id][0], v.attr))
            self._imports = out
        return self._imports

    def loaded_module(self, value):
        """The project file a call loads as a module: importlib.util.module_from_spec(spec) for a
        spec_from_file_location(name, PATH), a helper of this module that does that with its first
        argument, or importlib.import_module('name')."""
        if not isinstance(value, ast.Call):
            return None
        name = _fname(value)
        path = None
        if name == 'module_from_spec' and value.args and isinstance(value.args[0], ast.Name):
            for n in ast.walk(self.job.tree):
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == value.args[0].id for t in n.targets) \
                        and isinstance(n.value, ast.Call) and _fname(n.value) == 'spec_from_file_location' and len(n.value.args) > 1:
                    path = n.value.args[1]
        elif name == 'import_module' and value.args and _const_key(value.args[0])[0]:
            return self.module_file(value.args[0].value, 0)
        elif name in self.defs:
            # a helper: the argument it hands to spec_from_file_location as the path
            for d in self.defs[name]:
                for c in ast.walk(d):
                    if isinstance(c, ast.Call) and _fname(c) == 'spec_from_file_location' and len(c.args) > 1 and \
                            isinstance(c.args[1], ast.Name):
                        params = [a.arg for a in d.args.posonlyargs + d.args.args]
                        kw = next((k.value for k in value.keywords if k.arg == c.args[1].id), None)
                        if kw is not None:
                            path = kw
                        elif c.args[1].id in params and params.index(c.args[1].id) < len(value.args):
                            path = value.args[params.index(c.args[1].id)]
        if path is None:
            return None
        v = self.job.ev(path)
        if v is None or v.dyn or not v.rel.endswith('.py') or not self.ctx.uni.exists(v.rel):
            return None
        return v.rel

    def callee_elsewhere(self, call):
        """(file, function) when the call goes to a function of another project module."""
        fn = call.func
        if isinstance(fn, ast.Name) and fn.id not in self.defs:
            f = self.imports().get(fn.id)
            return (f[0], f[1]) if f and f[1] else None
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id not in self.defs:
            f = self.imports().get(fn.value.id)
            return (f[0], fn.attr) if f and f[1] is None else None
        return None

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
        if self.view is None:
            return self
        if self.view.mentioned_in(self.job.src):
            for node in ast.walk(self.job.tree):
                if not isinstance(node, ast.Call) or self.is_opener(node) or _fname(node) in PATH_CALLS:
                    continue
                arg = node.args[0] if node.args else \
                    next((k.value for k in node.keywords if k.arg in ('path', 'file', 'fp', 'filename', 'fname')), None)
                name = self.data_file(arg) if arg is not None else None
                if name:
                    certain = self.is_parser(node) or bool(LOADER_NAME.search(_fname(node) or ''))
                    self.push(node, name, (), (), frozenset(), certain)
        for seed in self.seeds:
            self.seed(seed)
        while self.queue:
            self.follow(*self.queue.pop())
        self.settle()
        return self

    def seed(self, seed):
        kind, ident, slot = seed[0], seed[1], seed[2] if seed[0] == 'param' else None
        name, pattern, prefix, certain = seed[-4:]
        via = frozenset({('import', ident)})
        if kind == 'param':
            for d in self.defs.get(ident, []):
                if isinstance(self.parent.get(d), ast.Module):
                    self.bind_param(d, slot, False, 'seed', name, pattern, prefix, via, certain)
        elif kind == 'global':
            for u in self.uses.get((None, ident), []):
                self.push(u, name, pattern, prefix, via, certain)
        elif kind == 'ret':
            for c in self.calls.get(ident, []):
                if isinstance(c.func, ast.Name):
                    self.push(c, name, pattern, prefix, via, certain)

    def push(self, node, name, pattern, prefix, via, certain):
        key = (node, name, pattern, prefix, via)
        if key not in self.seen and len(pattern) + len(prefix) < 40:
            self.seen.add(key)
            self.queue.append(key + (certain,))

    # ---------- following ----------
    def follow(self, node, name, pattern, prefix, via, certain):
        changed = self.view.changed(name)
        p = self.parent.get(node)
        args = (name, pattern, prefix, via, certain)
        if not prefix:
            hit = any(matches(pattern, k) for k in changed)
            deeper = any(below(pattern, k) for k in changed)
            if hit and not deeper:
                self.string(node, p, args)
                return
            if not hit and not deeper:
                return
        elif not any(matches(pattern, k) or below(pattern, k) for k in changed):
            return

        def escape(why):
            kinds = self.view.kinds_at(name, pattern) if not prefix else set()
            if kinds and all(self.guarded_off(node, k) for k in kinds - {'other'}):
                return
            if certain and any((matches(pattern, k) or below(pattern, k)) and ABS_START.match(v[0])
                               for k, v in changed.items()):
                self.escapes.append((node, name, pattern, why))

        def key(k, to):
            """Go through key `k` (STAR for any key) and push the result at `to`."""
            if prefix:
                if overlap(prefix[0], k):
                    self.push(to, name, pattern, prefix[1:], via, certain)
            else:
                self.push(to, name, pattern + (k,), (), via, certain)

        if isinstance(p, ast.Subscript) and p.slice is node:
            return                                             # used as a key, not as a path
        if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Add):
            self.push(p, *args)                                # [a] + rows: the same entries
            return
        if isinstance(p, ast.Subscript) and p.value is node:
            if not isinstance(p.ctx, ast.Load):
                return
            ok, k = _const_key(p.slice)
            if ok:
                key(k, p)
            elif isinstance(p.slice, ast.Slice):
                self.push(p, *args)
            elif isinstance(p.slice, (ast.List, ast.Tuple)) and all(_const_key(e)[0] for e in p.slice.elts):
                if any(any(matches(pattern + (_const_key(e)[1],), c) or below(pattern + (_const_key(e)[1],), c)
                           for c in changed) for e in p.slice.elts) and not prefix:
                    escape('a selection of several keys')
            else:
                key(self.computed_key(p.slice), p)             # one of the entries, whichever the key picks
            return
        if isinstance(p, ast.Attribute) and p.value is node:
            call = self.parent.get(p)
            is_call = isinstance(call, ast.Call) and call.func is p
            if p.attr == 'get' and is_call:
                ok, k = _const_key(call.args[0]) if call.args else (False, None)
                key(k if ok else (self.computed_key(call.args[0]) if call.args else STAR), call)
            elif p.attr in ('values', 'items') and is_call:
                self.iterate(call, args, pair=p.attr == 'items', escape=escape)
            elif p.attr == 'copy' and is_call:
                self.push(call, *args)
            elif p.attr in ('append', 'add', 'extend', 'insert', 'update', 'setdefault', 'pop', 'clear', 'sort', 'remove'):
                return                                         # changing the followed value itself
            elif p.attr not in HARMLESS:
                escape(f'.{p.attr}')
            return
        if isinstance(p, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and p.value is node:
            for t in (p.targets if isinstance(p, ast.Assign) else [p.target]):
                self.bind(t, *args)
            if isinstance(p, ast.NamedExpr):
                self.push(p, *args)
            return
        if isinstance(p, ast.Return):
            f = self.scope(p)
            if isinstance(f, FUNCS):
                for call in self.calls.get(f.name, []):
                    self.push(call, *args)
                if isinstance(self.parent.get(f), ast.Module):
                    self.returned[f.name].add((name, pattern, prefix, certain))
            return
        if (isinstance(p, ast.IfExp) and node is not p.test) or isinstance(p, (ast.BoolOp, ast.Await)):
            self.push(p, *args)
            return
        if isinstance(p, (ast.For, ast.AsyncFor, ast.comprehension)) and p.iter is node:
            if prefix or self.view.kind_at(name, pattern) == 'list':
                self.loop(p, args, pair=False, escape=escape)
            return                                             # iterating a dict yields its keys
        if isinstance(p, ast.Dict):
            if node in p.values:
                k = p.keys[p.values.index(node)]
                ok, kv = _const_key(k) if k is not None else (False, None)
                if ok:
                    self.push(p, name, pattern, (kv,) + prefix, via, certain)
                elif k is None:
                    self.push(p, *args)                        # {**row, ...}: row's own keys
                else:
                    escape('a dict with computed keys')
            return
        if isinstance(p, ast.Starred) and isinstance(self.parent.get(p), (ast.List, ast.Tuple, ast.Set)):
            self.push(self.parent.get(p), *args)               # [a, *rows]: rows' own entries
            return
        if isinstance(p, ast.AugAssign) and p.value is node and isinstance(p.op, ast.Add):
            if isinstance(p.target, ast.Name):                 # acc += rows: what acc holds from here on
                for u, k in self.uses_of_store(p.target):
                    self.push(u, name, pattern, prefix, via | {k}, certain)
            else:
                self.container(p.target, (), args, escape)
            return
        if isinstance(p, (ast.List, ast.Tuple, ast.Set)) and node in p.elts:
            q = self.parent.get(p)
            if isinstance(p, ast.Tuple) and isinstance(q, ast.Assign) and q.value is p and len(q.targets) == 1 and \
                    isinstance(q.targets[0], (ast.Tuple, ast.List)) and len(q.targets[0].elts) == len(p.elts):
                self.bind(q.targets[0].elts[p.elts.index(node)], *args)
            elif isinstance(p.ctx, ast.Load) if hasattr(p, 'ctx') else True:
                self.push(p, name, pattern, (STAR,) + prefix, via, certain)
            return
        if isinstance(p, COMPS) and (getattr(p, 'elt', None) is node or getattr(p, 'value', None) is node):
            self.push(p, name, pattern, (STAR,) + prefix, via, certain)
            return
        call, kw = (self.parent.get(p), p.arg) if isinstance(p, ast.keyword) else (p, None)
        if isinstance(call, ast.Call) and (kw is not None or node in call.args):
            self.call(call, node, kw, args, escape)
            return
        if isinstance(p, ast.keyword):
            self.double_star(call, args, escape)
            return
        if isinstance(p, (ast.Compare, ast.Expr, ast.Assert, ast.If, ast.While, ast.UnaryOp, ast.FormattedValue,
                          ast.JoinedStr, ast.Delete)) or p is None:
            return
        escape(type(p).__name__)

    def computed_key(self, expr):
        """What a computed key can be: AnyOf for a loop over constants or an f-string, else STAR."""
        if isinstance(expr, ast.Name):
            home = self.home(expr)
            keys = set()
            for st in self.stores.get((home, expr.id), []):
                loop, at = self.parent.get(st), None
                if isinstance(loop, (ast.Tuple, ast.List)) and isinstance(self.parent.get(loop), (ast.For, ast.comprehension)) \
                        and self.parent.get(loop).target is loop:
                    at, loop = loop.elts.index(st), self.parent.get(loop)       # for split, key in (("a", "k1"), ...)
                elif not (isinstance(loop, (ast.For, ast.comprehension)) and loop.target is st):
                    return STAR
                items = loop.iter.elts if isinstance(loop.iter, (ast.Tuple, ast.List, ast.Set)) else None
                if items is None:
                    return STAR
                for e in items:
                    if at is not None:
                        e = e.elts[at] if isinstance(e, (ast.Tuple, ast.List)) and at < len(e.elts) else None
                    ok, k = _const_key(e) if e is not None else (False, None)
                    if not ok:
                        return STAR
                    keys.add(k)
            return AnyOf(keys=frozenset(keys)) if keys else STAR
        rx = self._key_regex(expr)
        return AnyOf(regex=rx) if rx is not None and rx.replace('.*', '') else STAR

    def _key_regex(self, expr):
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return re.escape(expr.value)
        if isinstance(expr, ast.JoinedStr):
            return ''.join(re.escape(v.value) if isinstance(v, ast.Constant) else '.*' for v in expr.values)
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            parts = [self._key_regex(x) for x in (expr.left, expr.right)]
            return ''.join(x if x is not None else '.*' for x in parts)
        return None

    def string(self, node, p, args):
        """A string value: read here, unless it goes to a function of this module. Then the function's
        own uses decide, as long as every call gives it a followed value (settle())."""
        name, pattern, prefix, via, certain = args
        call, kw = (self.parent.get(p), p.arg) if isinstance(p, ast.keyword) else (p, None)
        fn = call.func if isinstance(call, ast.Call) else None
        callee = _fname(call) if fn is not None else None
        if callee in TYPE_CHECKS and isinstance(fn, ast.Name):
            return                                     # isinstance(x, dict): not used as a path
        if self.guarded_off(node):
            return                                     # under `if isinstance(x, dict)`: a string never gets here
        if isinstance(p, ast.Expr):
            return                                     # the value is thrown away
        if (isinstance(p, ast.Attribute) and p.value is node and p.attr in ('values', 'items', 'keys', 'get')) or \
                (isinstance(p, ast.Subscript) and p.value is node):
            return                                     # used as a dict or list: a string never gets here
        into = isinstance(p, (ast.Dict, ast.List, ast.Tuple, ast.Set) + COMPS) or \
            (isinstance(p, ast.keyword) and _fname(call) == 'dict')
        if into and not all(ABS_START.match(o) for k, (o, n) in self.view.leaves(name).items()
                            if matches(pattern, k) and pathlike(o)):
            # mixed values carried in a container (a serializer, a copy): where they are read decides
            self.carry(node, p, args)
            return
        f = self.scope(p) if isinstance(p, ast.Return) else None
        if isinstance(f, FUNCS):
            for c in self.calls.get(f.name, []):       # returned as it is: the caller's use decides
                self.push(c, *args)
            if isinstance(self.parent.get(f), ast.Module):
                self.returned[f.name].add((name, pattern, prefix, certain))
            return
        if fn is not None and (kw is not None or node in call.args) and callee in self.defs and \
                (isinstance(fn, ast.Name) or (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                                              and fn.value.id in SELF)):
            slot = kw if kw is not None else call.args.index(node)
            if kw is not None or not any(isinstance(x, ast.Starred) for x in call.args[:slot + 1]):
                keys = [k for d in self.defs[callee]
                        if (k := self.bind_param(d, slot, isinstance(fn, ast.Attribute), call, *args))]
                if keys:
                    self.pending.append((node, name, pattern, via, keys))
                    return
        self.reads.append(Read(node, name, pattern, via))

    def carry(self, node, p, args):
        """Follow the container a value goes into, wrapping the value in the key it goes under."""
        name, pattern, prefix, via, certain = args
        if isinstance(p, ast.Dict):
            if node in p.values:
                k = p.keys[p.values.index(node)]
                ok, kv = _const_key(k) if k is not None else (False, None)
                if ok:
                    self.push(p, name, pattern, (kv,) + prefix, via, certain)
        elif isinstance(p, ast.keyword):
            self.push(self.parent.get(p), name, pattern, (p.arg,) + prefix, via, certain)
        else:
            self.push(p, name, pattern, (STAR,) + prefix, via, certain)

    def guarded_off(self, node, kind='str'):
        """`node` (a name) sits where an isinstance() test of that name has ruled out its kind of value."""
        if not isinstance(node, ast.Name):
            return False
        allowed = {'str': ('str', 'object'), 'dict': ('dict', 'Mapping', 'MutableMapping', 'object'),
                   'list': ('list', 'tuple', 'Sequence', 'Iterable', 'object')}.get(kind, ())
        if not allowed:
            return False

        def rules_out_str(test):
            if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
                return any(rules_out_str(v) for v in test.values)
            if not (isinstance(test, ast.Call) and _fname(test) == 'isinstance' and len(test.args) == 2 and
                    isinstance(test.args[0], ast.Name) and test.args[0].id == node.id):
                return False
            types = test.args[1].elts if isinstance(test.args[1], ast.Tuple) else [test.args[1]]
            return not any(isinstance(t, (ast.Name, ast.Attribute)) and
                           (t.id if isinstance(t, ast.Name) else t.attr) in allowed for t in types)

        child, p = node, self.parent.get(node)
        while p is not None and not isinstance(p, FUNCS):
            if isinstance(p, (ast.If, ast.IfExp)) and child is not p.test and \
                    (child in p.body if isinstance(p, ast.If) else child is p.body) and rules_out_str(p.test):
                return True
            if isinstance(p, ast.BoolOp) and isinstance(p.op, ast.And) and child in p.values and \
                    any(rules_out_str(v) for v in p.values[:p.values.index(child)]):
                return True
            child, p = p, self.parent.get(p)
        return False

    def settle(self):
        """A string given to a function that other calls give other values is read at the call."""
        dropped = set()
        for node, name, pattern, via, keys in self.pending:
            amb = [k for k in keys if self.ambiguous(k)]
            if amb:
                self.reads.append(Read(node, name, pattern, via))
                dropped.update(amb)
        self.reads = [r for r in self.reads if not (r.via & dropped)]

    def call(self, call, node, kw, args, escape):
        name, pattern, prefix, via, certain = args
        callee, fn = _fname(call), call.func
        first = kw is None and call.args and call.args[0] is node
        if callee == 'enumerate' and first:
            self.iterate(call, args, pair=True, escape=escape)
        elif callee == 'next' and first:
            if prefix:
                self.push(call, name, pattern, prefix[1:], via, certain)
            else:
                self.push(call, name, pattern + (STAR,), (), via, certain)
        elif callee in SAME_SHAPE and first:
            self.push(call, *args)
        elif callee == 'dict' and kw is not None:
            self.push(call, name, pattern, (kw,) + prefix, via, certain)
        elif callee in ('append', 'add', 'insert') and isinstance(fn, ast.Attribute) and \
                (callee != 'insert' or (len(call.args) == 2 and call.args[1] is node)):
            self.container(fn.value, (STAR,), args, escape)
        elif callee == 'get' and isinstance(fn, ast.Attribute) and len(call.args) == 2 and call.args[1] is node:
            self.push(call, *args)                     # cfg.get('sequences', cfg): the default may be what comes back
        elif callee == 'setdefault' and isinstance(fn, ast.Attribute) and len(call.args) == 2 and call.args[1] is node:
            self.container(fn.value, (STAR,), args, escape)
        elif callee == 'update' and isinstance(fn, ast.Attribute) and first:
            self.container(fn.value, (), args, escape)
        elif callee == 'extend' and isinstance(fn, ast.Attribute) and first:
            self.container(fn.value, (), args, escape)
        elif callee in HARMLESS or (callee in WRITERS and isinstance(fn, ast.Attribute) and
                                   not (isinstance(fn.value, ast.Name) and fn.value.id in SELF)):
            pass
        elif callee in self.defs and (isinstance(fn, ast.Name) or
                                      (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in SELF)):
            for d in self.defs[callee]:
                slot = kw if kw is not None else call.args.index(node)
                if kw is None and any(isinstance(x, ast.Starred) for x in call.args[:slot + 1]):
                    escape(f'{callee}()')
                    continue
                if not self.bind_param(d, slot, isinstance(fn, ast.Attribute), call, *args):
                    escape(f'{callee}()')
        elif (target := self.callee_elsewhere(call)) is not None:
            slot = kw if kw is not None else call.args.index(node)
            if kw is None and any(isinstance(x, ast.Starred) for x in call.args[:slot + 1]):
                escape(f'{callee}()')
            else:
                self.outgoing.add((target[0], target[1], slot, name, pattern, prefix, certain))
        else:
            escape(f'{callee or "a call"}()')

    def double_star(self, call, args, escape):
        name, pattern, prefix, via, certain = args
        callee, fn = _fname(call), call.func
        if callee == 'dict':
            self.push(call, *args)
            return
        if callee in self.defs and isinstance(fn, ast.Name):
            for d in self.defs[callee]:
                a = d.args
                for param in a.posonlyargs + a.args + a.kwonlyargs:
                    if prefix:
                        if prefix[0] in (STAR, param.arg):
                            self.bind_param(d, param.arg, False, call, name, pattern, prefix[1:], via, certain)
                    else:
                        self.bind_param(d, param.arg, False, call, name, pattern + (param.arg,), (), via, certain)
            return
        escape('**')

    def iterate(self, producer, args, pair, escape):
        loop = self.parent.get(producer)
        if isinstance(loop, (ast.For, ast.AsyncFor, ast.comprehension)) and loop.iter is producer:
            self.loop(loop, args, pair, escape)
        elif pair:
            escape(f'{_fname(producer)}()')
        else:
            name, pattern, prefix, via, certain = args
            self.push(producer, name, pattern, (STAR,) + prefix, via, certain)     # .values(): a list of them

    def loop(self, loop, args, pair, escape):
        name, pattern, prefix, via, certain = args
        t = loop.target
        if pair:
            if not (isinstance(t, (ast.Tuple, ast.List)) and len(t.elts) == 2):
                escape('a loop target')
                return
            t = t.elts[1]
        if prefix:
            self.bind(t, name, pattern, prefix[1:], via, certain)
        else:
            self.bind(t, name, pattern + (STAR,), (), via, certain)

    # ---------- bindings ----------
    def bind_pos(self, t):
        """Where a binding takes effect: after the value it is given is computed."""
        p = self.parent.get(t)
        while p is not None and not isinstance(p, (ast.stmt, ast.comprehension, ast.withitem, ast.NamedExpr)):
            p = self.parent.get(p)
        if isinstance(p, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and p.value is not None:
            return p.value.end_lineno, p.value.end_col_offset
        if isinstance(p, (ast.For, ast.AsyncFor)):
            return p.iter.end_lineno, p.iter.end_col_offset
        if isinstance(p, ast.withitem):
            return p.context_expr.end_lineno, p.context_expr.end_col_offset
        return _pos(t)

    def uses_of_store(self, t):
        """[(load, binding key)] for the loads that binding `t` reaches."""
        ident = t.arg if isinstance(t, ast.arg) else t.id
        home = self.scope(t) if isinstance(t, ast.arg) else self.home_store(t)
        stores = self.stores.get((home, ident), [])
        out = []
        for u in self.uses.get((home, ident), []):
            if isinstance(home, COMPS) or isinstance(t, ast.arg) and len(stores) == 1:
                out.append((u, ('store', t)))
            elif self.scope(u) is not home:
                out.append((u, ('free', home, ident)))       # read later, from a nested function
            else:
                before = [s for s in stores if (self.bind_pos(s) if not isinstance(s, ast.arg) else (0, 0)) < _pos(u)]
                reach = max(before, key=lambda s: self.bind_pos(s) if not isinstance(s, ast.arg) else (0, 0), default=None)
                if reach is t:
                    out.append((u, ('store', t)))
        return out

    def bind(self, t, name, pattern, prefix, via, certain):
        if isinstance(t, ast.Name):
            home = self.home_store(t)
            self.bound[('free', home, t.id)].add(t)
            if home is None:
                self.exports[t.id].add((name, pattern, prefix, certain))
            for u, k in self.uses_of_store(t):
                self.push(u, name, pattern, prefix, via | {k}, certain)
        elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in SELF:
            k = ('attr', self.class_of(t), t.attr)
            self.bound[k].add(t)
            for u in self.attr_uses.get(k[1:], []):
                self.push(u, name, pattern, prefix, via | {k}, certain)
        elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and \
                (self.imports().get(t.value.id) or (None, 'x'))[1] is None and t.value.id in self.imports():
            self.globals_out.add((self.imports()[t.value.id][0], t.attr, name, pattern, prefix, certain))
        elif isinstance(t, (ast.Tuple, ast.List)) and prefix and prefix[0] == STAR:
            for e in t.elts:
                self.bind(e, name, pattern, prefix[1:], via, certain)
        elif isinstance(t, ast.Subscript) and isinstance(t.ctx, ast.Store):
            ok, k = _const_key(t.slice)
            if ok:
                self.container(t.value, (k,), (name, pattern, prefix, via, certain), None)
            elif certain:
                self.escapes.append((t, name, pattern, 'a dynamic key'))
        elif certain:
            self.escapes.append((t, name, pattern, 'unpacking or a container'))

    def container(self, c, add, args, escape):
        """The value goes into container `c` under keys `add`: follow c's later reads."""
        name, pattern, prefix, via, certain = args
        if isinstance(c, ast.Name):
            home = self.home(c)
            stores = self.stores.get((home, c.id), [])
            before = [s for s in stores if not isinstance(s, ast.arg) and self.bind_pos(s) <= _pos(c)]
            reach = max(before, key=self.bind_pos, default=None)
            if reach is not None:
                for u, k in self.uses_of_store(reach):
                    if u is not c:
                        self.push(u, name, pattern, add + prefix, via | {k}, certain)
                return
        elif isinstance(c, ast.Attribute) and isinstance(c.value, ast.Name) and c.value.id in SELF:
            k = ('attr', self.class_of(c), c.attr)
            for u in self.attr_uses.get(k[1:], []):
                if u is not c:
                    self.push(u, name, pattern, add + prefix, via | {k}, certain)
            return
        if escape:
            escape('a container')
        elif certain:
            self.escapes.append((c, name, pattern, 'a container'))

    def bind_param(self, d, slot, method, through, name, pattern, prefix, via, certain):
        a = d.args
        params = a.posonlyargs + a.args
        if method and params:
            params = params[1:]
        if isinstance(slot, str):
            target = next((x for x in params + a.kwonlyargs if x.arg == slot), None)
        else:
            target = params[slot] if slot < len(params) else None
        if target is None:
            return None
        k = ('param', d, target.arg)
        self.bound[k].add(through)
        for u, sk in self.uses_of_store(target):
            self.push(u, name, pattern, prefix, via | {k, sk}, certain)
        return k

    def ambiguous(self, key):
        """Some way this binding gets its value is not a followed data value."""
        kind = key[0]
        if kind in ('store', 'import'):
            return False
        if kind == 'param':
            d = key[1]
            if 'seed' in self.bound[key]:
                return False
            calls = self.calls.get(d.name, [])
            return not calls or any(c not in self.bound[key] for c in calls)
        stores = self.attr_stores.get(key[1:], []) if kind == 'attr' else \
            [s for s in self.stores.get(key[1:], []) if not isinstance(s, ast.arg)]
        for s in stores:
            if s in self.bound[key]:
                continue
            p = self.parent.get(s)
            if isinstance(p, (ast.Assign, ast.AnnAssign)) and self._neutral(p.value):
                continue
            return True
        return kind == 'free' and any(isinstance(s, ast.arg) for s in self.stores.get(key[1:], []))

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
            # an unchanged value that does not look like a path (a family name) is not what this read opens
            leaves = {l for l in leaves if l in changed or pathlike(l[2])}
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
            amb = sorted({str(k[2]) for k in via if self.ambiguous(k)})
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
        if any(u[2].startswith('reader') and u[0] <= s and e <= u[1] for u in job.root_uses):
            return              # inside a read already joined to the root: item.get('k', roster['default'])
        job.root_uses = [u for u in job.root_uses if not (u[2].startswith('reader') and s <= u[0] and u[1] <= e)]
        if isinstance(p, ast.Call) and node in p.args and (_fname(p) in PATH_CALLS or _fname(p) == 'joinpath'):
            job.root_uses.append((s, e, 'reader_join', ''))
        else:
            job.root_uses.append((s, e, 'reader_str', ''))


# ---------- across modules ----------
_NAMES = {}


def module_names(ctx, f):
    """Top-level names a module defines, read from ctx.modules."""
    src = (ctx.modules or {}).get(f)
    if src is None:
        return set()
    key = (f, hash(src))
    if key not in _NAMES:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree = ast.parse(src)
        except (SyntaxError, ValueError):
            tree = ast.Module(body=[], type_ignores=[])
        out = set()
        for st in tree.body:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(st.name)
            elif isinstance(st, (ast.Assign, ast.AnnAssign)):
                for t in (st.targets if isinstance(st, ast.Assign) else [st.target]):
                    out.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
            elif isinstance(st, (ast.Import, ast.ImportFrom)):
                out.update((a.asname or a.name).split('.')[0] for a in st.names if a.name != '*')
        _NAMES[key] = out
    return _NAMES[key]

def _job(src, rel, ctx):
    from restructure_python import _PyJob
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    job = _PyJob(src, tree, rel, rel, ctx)
    job.bind_pass(tree, record=False)
    return job


def link(sources, ctx, rounds=12):
    """{file: seeds} for values crossing module boundaries. `sources` holds every Python file of
    the side ctx.data_side describes ({name: text}); a round analyses the files with something new."""
    seeds = defaultdict(set)
    ctx.modules = sources              # a star import is resolved against the module's own text
    if ctx.data is None:
        return {}
    results = {}
    todo = {f for f, s in sources.items() if ctx.data.mentioned_in(s)}
    for _ in range(rounds):
        if not todo:
            break
        for f in todo:
            job = _job(sources[f], f, ctx)
            if job is not None:
                results[f] = Readers(job, frozenset(seeds[f])).run()
        new = defaultdict(set)
        for r in results.values():
            for f, func, slot, *val in r.outgoing:
                if f in sources:
                    new[f].add(('param', func, slot, *val))
            for f, var, *val in r.globals_out:
                if f in sources:
                    new[f].add(('global', var, *val))
        names = {n: f for f, r in results.items() for n in list(r.exports) + list(r.returned)}
        if names:
            pat = re.compile(r'\b(?:' + '|'.join(map(re.escape, sorted(names))) + r')\b')
            for f, s in sources.items():
                if 'import' not in s or not pat.search(s):
                    continue
                job = _job(s, f, ctx)
                if job is None:
                    continue
                for local, (tf, attr) in Readers(job).imports().items():
                    r = results.get(tf)
                    if r is None or attr is None:
                        continue
                    for v in r.exports.get(attr, ()):
                        new[f].add(('global', local, *v))
                    for v in r.returned.get(attr, ()):
                        new[f].add(('ret', local, *v))
        todo = set()
        for f, s in new.items():
            if s - seeds[f]:
                seeds[f] |= s
                todo.add(f)
    return {f: frozenset(s) for f, s in seeds.items()}


def read_parents(job):
    """Expressions that join a followed read value: their evaluation belongs to the read check."""
    seeds = (job.ctx.seeds or {}).get(job.file_old, ())
    if job.ctx.data is None or not (seeds or job.ctx.data.mentioned_in(job.src)):
        return set()
    r = Readers(job, seeds).run()
    out = set()
    for read in r.reads:
        p = job.parent.get(read.node)
        if isinstance(p, (ast.BinOp, ast.Call)):
            out.add(p)
    return out


def read_targets(src, file_rel, ctx):
    """[(data file, keys, target)] for every read of a changed data value, with the value of
    ctx.data_side, or None when the source does not parse."""
    job = _job(src, file_rel, ctx)
    if job is None:
        return None
    if ctx.data is None:
        return []
    r = Readers(job, (ctx.seeds or {}).get(file_rel, ())).run()
    out = []
    for node, (leaves, _) in r.groups().items():
        for name, keys, o, n in leaves:
            if o != n and not HEX64.fullmatch(o):
                out.append((name, keys, r.target(node, o if ctx.data_side == 'old' else n)))
    return out

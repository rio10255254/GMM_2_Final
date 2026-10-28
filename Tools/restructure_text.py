"""Rewrite path references in non-Python text files for the 2026-10-28 restructure.

Two modes share one pass structure:
- 'moves' (phases 2-4): every reference that resolves into a moved location, and every
  file-relative reference in a moved file, is written back pointing at the new place,
  in its original style (separators, escaping, %-encoding, anchors).
- 'location' (phase 1): absolute paths into the project, and external paths whose content
  is in the cloud, stop naming this machine. Records and documents get project-relative
  '/' paths; notebooks get paths relative to the notebook (cells run there); MATLAB and
  PowerShell derive the project root from the script's own location.

Bytes outside the rewritten spans are kept as they were: BOM, CRLF, gzip only when
something changed. Files that are not UTF-8 are reported and left alone.
"""
from bisect import bisect_right
from dataclasses import dataclass
import gzip
import posixpath
import re
import urllib.parse

from restructure_resolve import PROJECT_ABS, norm, render, resolve

BOM = b'\xef\xbb\xbf'
DOC_EXT = ('.md', '.markdown', '.html', '.htm', '.txt', '.tex')
RECORD_EXT = ('.json', '.csv', '.tsv', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.log', '.xml')
SCRIPT_EXT = ('.m', '.ps1', '.psm1', '.bat', '.cmd', '.sh')
NOTEBOOK_EXT = ('.ipynb',)

TOKEN = re.compile(r'(?:\\\\\?\\)?[^\s"\'`<>|*?\[\]{}(),;，。、；：（）「」『』《》【】！？]+')
WORD = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-')
MD_LINK = re.compile(r'(\]\(\s*<?)([^)\s>]+)(>?)|((?:href|src)=["\'])([^"\']+)(["\'])')
GITHUB = re.compile(r'(https?://github\.com/rio10255254/GMM_2_Final/(?:blob|tree|raw)/main/)([^\s)"\'\]>#?]+)')
ABS_START = re.compile(r'^(?:\\\\\?\\)?[A-Za-z]:(?:\\\\|\\|/)')
INTERPRETER = re.compile(r'(["\']?)[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)[^\\/\s"\']+(?:\\\\|\\|/)anaconda3'
                         r'(?:(?:\\\\|\\|/)envs(?:\\\\|\\|/)[^\\/\s"\']+)?(?:\\\\|\\|/)pythonw?(?:\.exe)?\1', re.I)
M_LITERAL = re.compile(r"(?:^|(?<=[\s(\[{,=;]))'((?:[^'\n]|'')*)'", re.M)
M_SEGMENTED = re.compile(r"fullfile\(\s*'[A-Za-z]:[\\/]?'\s*,\s*'GMM_2_Final(?:_restructure)?'", re.I)
PS_LITERAL = re.compile(r'"((?:[^"`\n]|`.)*)"|\'((?:[^\'\n]|\'\')*)\'')


@dataclass(frozen=True)
class Edit:
    file_old: str
    file_new: str
    line: int
    old: str
    new: str
    kind: str
    old_target: str
    new_target: str


@dataclass
class Context:
    uni: object
    rules: object          # RuleSet / Composed with .map(rel), or None in location mode
    external_map: dict
    mode: str              # 'moves' | 'location'
    decisions: dict = None  # {(exact source segment, old target): new target, or None to keep as written}


def file_class(name):
    low = name.lower()
    if low.endswith('.json.gz'):
        return 'record_gz'
    for cls, exts in (('doc', DOC_EXT), ('record', RECORD_EXT), ('script', SCRIPT_EXT), ('notebook', NOTEBOOK_EXT)):
        if low.endswith(exts):
            return cls
    return None


def rewrite_bytes(data, file_old, file_new, ctx):
    cls = file_class(file_old)
    if cls is None:
        return data, [], []
    if cls == 'record_gz':
        try:
            inner = gzip.decompress(data)
        except (OSError, EOFError) as exc:
            return data, [], [f'{file_old}: not gzip ({exc})']
        out, edits, problems = _rewrite_decoded(inner, file_old, file_new, ctx, 'record')
        if out == inner:
            return data, [], problems
        return gzip.compress(out, compresslevel=9, mtime=0), edits, problems
    return _rewrite_decoded(data, file_old, file_new, ctx, cls)


def token_starts(tok):
    """Where a path may start inside a token: 0, then after any non-path character (CJK text, '=', ':')."""
    yield 0
    if ABS_START.match(tok) or tok.startswith(('/', '\\')):
        return               # never look inside an absolute path
    for i in range(1, len(tok)):
        if tok[i - 1] not in WORD and tok[i - 1] not in '/\\' and tok[i] not in '/\\':
            yield i


def resolve_token(tok, file_rel, uni, external_map):
    """(offset, Resolved) for the first place in a path-shaped token that resolves, or None."""
    for i in token_starts(tok):
        res = resolve(tok[i:], file_rel, uni, external_map)
        if res is not None:
            return i, res
    return None


def token_targets(text, file_rel, uni, external_map):
    """Targets of every path-shaped token in `text`, in order."""
    out = []
    for m in TOKEN.finditer(text):
        tok = m.group(0)
        if '/' in tok or '\\' in tok:
            found = resolve_token(tok, file_rel, uni, external_map)
            if found:
                out.append(found[1].target_rel)
    return out


def rewrite_fragment(text, file_old, file_new, ctx, cls='record'):
    """Rewrite a piece of already-decoded text (a comment, a string literal's source) as `cls` would be."""
    job = _Job(text, file_old, file_new, ctx, cls)
    job.run()
    return (job.apply() if job.repl else text), job.edits, job.problems


def _rewrite_decoded(data, file_old, file_new, ctx, cls):
    bom = data.startswith(BOM)
    try:
        text = (data[3:] if bom else data).decode('utf-8')
    except UnicodeDecodeError:
        return data, [], [f'{file_old}: not UTF-8, left unchanged']
    job = _Job(text, file_old, file_new, ctx, cls)
    job.run()
    if not job.repl:
        return data, [], job.problems
    out = job.apply()
    return (BOM if bom else b'') + out.encode('utf-8'), job.edits, job.problems


class _Job:
    def __init__(self, text, file_old, file_new, ctx, cls):
        self.text, self.file_old, self.file_new, self.ctx, self.cls = text, file_old, file_new, ctx, cls
        self.repl = []          # (start, end, new)
        self.mask = []          # (start, end) spans already handled
        self._sorted = None
        self.edits, self.problems = [], []
        self.line_starts = [0] + [m.end() for m in re.finditer('\n', text)]
        self.uses_root = False

    # -- bookkeeping --
    def line(self, pos):
        return bisect_right(self.line_starts, pos)

    def masked(self, start, end):
        # handled spans never overlap each other, so only the last one starting before `end` can overlap
        if self._sorted is None:
            self._sorted = sorted(self.mask)
            self._starts = [s for s, _ in self._sorted]
        i = bisect_right(self._starts, end - 1) - 1
        return i >= 0 and self._sorted[i][1] > start

    def hold(self, span):
        self.mask.append(span)
        self._sorted = None

    def add(self, start, end, new, kind, old_target='', new_target='', hold=True):
        old = self.text[start:end]
        if hold:
            self.hold((start, end))
        if new == old:
            return
        self.repl.append((start, end, new))
        self.edits.append(Edit(self.file_old, self.file_new, self.line(start), old, new,
                               f'{self.cls}:{kind}', old_target, new_target))

    def apply(self):
        out, last = [], 0
        for start, end, new in sorted(self.repl):
            out.append(self.text[last:start]); out.append(new); last = end
        out.append(self.text[last:])
        return ''.join(out)

    # -- passes --
    def run(self):
        if self.ctx.mode == 'moves':
            self.github()
            if self.cls == 'doc':
                self.links()
            self.tokens()
        else:
            if self.cls == 'script':
                self.interpreter()
                if self.file_old.lower().endswith('.m'):
                    self.matlab()
                elif self.file_old.lower().endswith(('.ps1', '.psm1')):
                    self.powershell()
            if self.cls == 'doc':
                self.links()
            self.tokens()

    def github(self):
        for m in GITHUB.finditer(self.text):
            raw = m.group(2)
            path = urllib.parse.unquote(raw)
            new = self.ctx.rules.map(path.rstrip('/'))
            self.hold(m.span())
            if new is None:
                continue
            if raw != path:
                new = '/'.join(urllib.parse.quote(s, safe="!$&'()*+,;=:@-._~") for s in new.split('/'))
            self.add(m.start(2), m.end(2), new + ('/' if raw.endswith('/') else ''), 'github', path, new)

    def links(self):
        for m in MD_LINK.finditer(self.text):
            g = 2 if m.group(2) is not None else 5
            start, end = m.span(g)
            if self.masked(start, end):
                continue
            target = m.group(g)
            res = resolve(target, self.file_old, self.ctx.uni, self.ctx.external_map)
            self.hold((start, end))
            if res is None:
                continue
            new = self.new_text(res, link=True)
            if new is not None:
                self.add(start, end, new[0], 'link', res.target_rel, new[1])

    def tokens(self):
        for m in TOKEN.finditer(self.text):
            tok = m.group(0)
            if ('/' not in tok and '\\' not in tok) or self.masked(*m.span()):
                continue
            found = self.resolve_token(tok)
            if found is None:
                continue
            offset, res = found
            new = self.new_text(res)
            if new is not None:
                self.add(m.start() + offset, m.end(), new[0], 'path', res.target_rel, new[1], hold=False)

    def resolve_token(self, tok):
        return resolve_token(tok, self.file_old, self.ctx.uni, self.ctx.external_map)

    def new_text(self, res, link=False):
        """(replacement, new_target) for a resolved reference, or None to leave it."""
        kind = res.style.kind
        if self.ctx.mode == 'moves':
            new_target = self.ctx.rules.map(res.target_rel) or res.target_rel
            if new_target == res.target_rel and (kind != 'file_rel' or self.file_old == self.file_new):
                return None
            return render(new_target, self.file_new, res.style, 'keep'), new_target
        if kind not in ('abs_project', 'abs_external'):
            return None
        if link or self.cls == 'notebook':
            rel = posixpath.relpath(res.target_rel or '.', posixpath.dirname(self.file_new) or '.')
            return rel, res.target_rel
        return res.target_rel, res.target_rel

    # -- location mode, scripts --
    def interpreter(self):
        for m in INTERPRETER.finditer(self.text):
            self.add(m.start(), m.end(), 'python', 'interpreter')

    def depth(self):
        d = posixpath.dirname(self.file_new)
        return len(d.split('/')) if d else 0

    def literal_target(self, content):
        """Absolute path at the start of a literal -> project-relative target, or None."""
        if not ABS_START.match(content):
            return None
        res = resolve(content, self.file_old, self.ctx.uni, self.ctx.external_map)
        if res is None or res.style.kind not in ('abs_project', 'abs_external'):
            return None
        return res

    def matlab(self):
        for m in M_SEGMENTED.finditer(self.text):
            self.add(m.start(), m.end(), 'fullfile(PROJECT_ROOT', 'matlab_root')
            self.uses_root = True
        for m in M_LITERAL.finditer(self.text):
            if self.masked(*m.span()):
                continue
            content = m.group(1)
            res = self.literal_target(content)
            if res is None:
                if PROJECT_ABS.search(content):
                    self.problems.append(f'{self.file_old}:{self.line(m.start())}: project path inside a MATLAB literal, fix by hand')
                    self.hold(m.span())
                continue
            rel = res.target_rel
            if not rel:
                new = 'PROJECT_ROOT'
            elif content.endswith(('/', '\\')):
                new = f"[fullfile(PROJECT_ROOT, '{rel}') filesep]"
            else:
                new = f"fullfile(PROJECT_ROOT, '{rel}')"
            self.add(m.start(), m.end(), new, 'matlab_root', '', rel)
            self.uses_root = True
        if self.uses_root and not re.search(r'^\s*PROJECT_ROOT\s*=', self.text, re.M):
            expr = "mfilename('fullpath')"
            for _ in range(self.depth() + 1):
                expr = f'fileparts({expr})'
            nl = '\r\n' if '\r\n' in self.text else '\n'
            pos, indent = 0, ''
            fm = re.search(r'^[ \t]*function\b[^\n]*\n', self.text, re.M)
            first_code = re.search(r'^[ \t]*[^%\s]', self.text, re.M)
            if fm and first_code and fm.start() == first_code.start():
                pos, indent = fm.end(), '    '
            self.repl.append((pos, pos, f'{indent}PROJECT_ROOT = {expr};{nl}'))

    def powershell(self):
        for m in PS_LITERAL.finditer(self.text):
            double = m.group(1) is not None
            content = m.group(1) if double else m.group(2)
            res = self.literal_target(content)
            if res is None:
                if PROJECT_ABS.search(content):
                    self.problems.append(f'{self.file_old}:{self.line(m.start())}: project path inside a PowerShell string, fix by hand')
                    self.hold(m.span())
                continue
            sep = '/' if res.style.sep == '/' else '\\'
            rel = res.target_rel.replace('/', sep)
            if double:
                pm = re.match(r'^(?:\\\\\?\\)?[A-Za-z]:(?:\\\\|\\|/)+[^\\/]+', content) if res.style.kind == 'abs_project' else None
                if pm:
                    new = '"$ProjectRoot' + content[pm.end():] + '"'
                else:
                    new = '"$ProjectRoot' + (sep + rel if rel else '') + '"'
            else:
                new = f"(Join-Path $ProjectRoot '{rel}')" if rel else '$ProjectRoot'
            self.add(m.start(), m.end(), new, 'powershell_root', '', res.target_rel)
            self.uses_root = True
        if self.uses_root and not re.search(r'^\s*\$ProjectRoot\s*=', self.text, re.M | re.I):
            nl = '\r\n' if '\r\n' in self.text else '\n'
            d = self.depth()
            line = '$ProjectRoot = $PSScriptRoot' if d == 0 else \
                f"$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '{chr(92).join(['..'] * d)}')).Path"
            self.repl.append((self.after_param(), self.after_param(), line + nl))

    def after_param(self):
        m = re.search(r'^\s*param\s*\(', self.text, re.I | re.M)
        if not m:
            return 0
        depth, i = 0, m.end() - 1
        while i < len(self.text):
            c = self.text[i]
            depth += c == '('
            depth -= c == ')'
            if depth == 0:
                nl = self.text.find('\n', i)
                return len(self.text) if nl < 0 else nl + 1
            i += 1
        return 0

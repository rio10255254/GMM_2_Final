"""Hash chain for the 2026-10-28 restructure: when a file is rewritten, every record of its sha256 follows.

`propagate(changed, sizes, files, read, write)` replaces each 64-hex token (on word
boundaries) equal to an old sha in `changed` with the new one, and updates the size
recorded beside it: the `bytes`/`size` key of the same JSON object, or the `bytes`/`size`
column of the same CSV/TSV row. A record that changed this way has a new sha itself, so
the pass repeats with those changes until a round changes nothing. Formatting outside
the replaced values is kept; `.json.gz` is decompressed and recompressed (mtime 0).
git commit and blob ids are never touched: they are sha1 (40 hex), not 64. Neither is a hash
written as a path segment.
"""
from bisect import bisect_right
from dataclasses import dataclass, field
import csv
import gzip
import hashlib
import io
import re

# a hash written as a path segment (objects/<sha>, <sha>/file) names content that exists under that
# name; it is an identity, not a record of a file's current sha, so it is never replaced
HEX64 = re.compile(r'(?<![0-9A-Za-z_/\\])[0-9a-fA-F]{64}(?![0-9A-Za-z_/\\])')
SIZE_KEY = re.compile(r'"(bytes|size)"\s*:\s*(\d+)')
SIZE_COLUMNS = ('bytes', 'size')


class NotConverging(RuntimeError):
    pass


@dataclass
class HashReport:
    changes: dict = field(default_factory=dict)
    touched_files: list = field(default_factory=list)
    rounds: int = 0


def propagate(changed, sizes, files, read, write, max_rounds=50):
    report = HashReport(dict(changed))
    pending, sizes = dict(changed), dict(sizes)
    touched = set()
    while pending:
        if report.rounds >= max_rounds:
            raise NotConverging(f'hash chain still changing after {max_rounds} rounds')
        next_pending = {}
        for name in files:
            data = read(name)
            new = rewrite_record(name, data, pending, sizes)
            if new == data:
                continue
            write(name, new)
            touched.add(name)
            old_sha, new_sha = hashlib.sha256(data).hexdigest(), hashlib.sha256(new).hexdigest()
            next_pending[old_sha] = new_sha
            sizes[new_sha] = len(new)
        if next_pending:
            report.rounds += 1
        report.changes.update(next_pending)
        pending = next_pending
    report.touched_files = sorted(touched)
    return report


def rewrite_record(name, data, changed, sizes):
    if name.lower().endswith('.gz'):
        try:
            inner = gzip.decompress(data)
        except (OSError, EOFError):
            return data
        out = rewrite_record(name[:-3], inner, changed, sizes)
        return data if out == inner else gzip.compress(out, compresslevel=9, mtime=0)
    bom = data.startswith(b'\xef\xbb\xbf')
    try:
        text = (data[3:] if bom else data).decode('utf-8')
    except UnicodeDecodeError:
        return data
    if not any(m.group(0).lower() in changed for m in HEX64.finditer(text)):
        return data
    low = name.lower()
    if low.endswith('.json'):
        new = _json_text(text, changed, sizes)
    elif low.endswith(('.csv', '.tsv')):
        new = _table_text(text, changed, sizes, '\t' if low.endswith('.tsv') else ',')
    else:
        new = _tokens(text, changed)
    return (b'\xef\xbb\xbf' if bom else b'') + new.encode('utf-8')


def _swap(token, changed):
    new = changed.get(token.lower())
    if new is None:
        return token
    return new.upper() if token.isupper() else new


def _tokens(text, changed):
    return HEX64.sub(lambda m: _swap(m.group(0), changed), text)


class _Objects:
    """Every JSON object's span and parent, in order of where it starts; strings skipped."""

    def __init__(self, text):
        self.starts, self.ends, self.parent = [], [], []
        stack, i, n = [], 0, len(text)
        while i < n:
            c = text[i]
            if c == '"':
                i += 1
                while i < n and text[i] != '"':
                    i += 2 if text[i] == '\\' else 1
            elif c == '{':
                self.parent.append(stack[-1] if stack else -1)
                stack.append(len(self.starts))
                self.starts.append(i)
                self.ends.append(n)
            elif c == '}' and stack:
                self.ends[stack.pop()] = i + 1
            i += 1

    def innermost(self, pos):
        """Index of the innermost object containing `pos`, or -1."""
        k = bisect_right(self.starts, pos) - 1
        while k >= 0 and self.ends[k] <= pos:
            k = self.parent[k]
        return k


def _json_text(text, changed, sizes):
    objs = None
    repl = {}
    for m in HEX64.finditer(text):
        new_sha = changed.get(m.group(0).lower())
        if new_sha is None:
            continue
        repl[(m.start(), m.end())] = _swap(m.group(0), changed)
        if new_sha not in sizes:
            continue
        objs = objs or _Objects(text)
        k = objs.innermost(m.start())
        if k < 0:
            continue
        for key in SIZE_KEY.finditer(text, objs.starts[k], objs.ends[k]):
            if objs.innermost(key.start()) == k:
                repl[(key.start(2), key.end(2))] = str(sizes[new_sha])
    out, last = [], 0
    for (s, e), new in sorted(repl.items()):
        out.append(text[last:s]); out.append(new); last = e
    out.append(text[last:])
    return ''.join(out)


def _table_text(text, changed, sizes, delim):
    lines = text.splitlines(keepends=True)
    if not lines:
        return text
    header = next(csv.reader([lines[0].rstrip('\r\n')], delimiter=delim))
    size_col = next((i for i, h in enumerate(header) if h.strip().lower() in SIZE_COLUMNS), None)
    out = [lines[0]]
    for line in lines[1:]:
        body = line.rstrip('\r\n')
        end = line[len(body):]
        found = [m.group(0).lower() for m in HEX64.finditer(body) if m.group(0).lower() in changed]
        if not found:
            out.append(line)
            continue
        body = _tokens(body, changed)
        new_size = next((sizes[changed[h]] for h in found if changed[h] in sizes), None)
        if size_col is not None and new_size is not None:
            row = next(csv.reader([body], delimiter=delim))
            if size_col < len(row) and row[size_col].strip().isdigit():
                row[size_col] = str(new_size)
                buf = io.StringIO()
                csv.writer(buf, delimiter=delim, lineterminator='').writerow(row)
                body = buf.getvalue()
        out.append(body + end)
    return ''.join(out)

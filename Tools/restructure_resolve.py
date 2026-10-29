"""Where does a path string point in the old tree, and how is it written back?

The universe of paths is everything that can be a target: git-tracked files, Release
restore paths (seen through the phases already applied, since manifests are replaced
only in phase 5), and the local inventory of the project folder. A string is judged
by where it resolves, never by its spelling: a package's own `Traing_Progress` is
not the project's.

Resolution order:
1. Absolute: drive + GMM_2_Final (or GMM_2_Final_restructure) is the project; then a
   junction whose link lives outside the project; then the external map built from
   content hashes. Any other absolute path resolves to nothing.
2. Relative: beside the referring file when its first segment exists there, else from
   the project root when its first segment exists at the root.
3. A target that does not exist is still returned (exists=False); callers judge it by
   its longest existing ancestor.
"""
from dataclasses import dataclass, replace
import csv
import os
import posixpath
import re
import sqlite3
import subprocess
import urllib.parse
from pathlib import Path

PROJECT_NAMES = ('gmm_2_final', 'gmm_2_final_restructure')
_ABS = re.compile(r'^(?:\\\\\?\\|//\?/)?([A-Za-z]):[\\/]+')
# the project folder written anywhere in a text; a folder that only starts with the name (GMM_2_Final_Archive) is not it
PROJECT_ABS = re.compile(r'[A-Za-z]:(?:\\\\|\\|/)+GMM_2_Final(?:_restructure)?(?![A-Za-z0-9_])', re.I)


@dataclass(frozen=True)
class Style:
    sep: str = '/'
    escaped: bool = False
    kind: str = 'root_rel'          # file_rel | root_rel | abs_project | abs_external
    prefix: str = ''                # abs_project: drive and project folder exactly as written
    encoded: bool = False           # markdown link with %xx escapes
    dot: bool = False               # written with a leading ./
    trailing: bool = False          # written with a trailing separator
    suffix: str = ''                # #anchor or ?query carried along


@dataclass(frozen=True)
class Resolved:
    target_rel: str
    style: Style
    exists: bool


def git_env():
    """The environment minus GIT_* variables: inside a hook they would point git at the hook's repo."""
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def norm(rel):
    """Collapse '.', '..' and empty segments; None when it climbs above the root."""
    out = []
    for part in rel.replace('\\', '/').split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if not out:
                return None
            out.pop()
        else:
            out.append(part)
    return '/'.join(out)


def norm_abs(text):
    """Absolute Windows path in any spelling -> 'X:/a/b' with '/' separators."""
    t = re.sub(r'^(\\\\\?\\|//\?/)', '', text).replace('\\\\', '/').replace('\\', '/')
    t = re.sub(r'/+', '/', t)
    return t[0].upper() + t[1:] if len(t) > 1 and t[1] == ':' else t


class Universe:
    def __init__(self, files, junctions=None):
        self.files = set(files)
        self.dirs = {''}
        self.kids = {}
        for f in self.files:
            parts = f.split('/')
            for i in range(1, len(parts) + 1):
                parent, name = '/'.join(parts[:i - 1]), parts[i - 1]
                self.kids.setdefault(parent, set()).add(name)
                if i < len(parts):
                    self.dirs.add('/'.join(parts[:i]))
        self.lower = {p.lower(): p for p in self.files | self.dirs}
        self.junctions = dict(junctions or {})

    @classmethod
    def from_paths(cls, paths, junctions=None):
        return cls(paths, junctions)

    @classmethod
    def build(cls, repo, cloud_index=None, local_inventory=None, applied=None, reparse_tsvs=(), ref=None):
        """Tracked files (the index, or `ref`'s tree), Release paths and local inventory paths.

        Release and local paths are recorded in pre-restructure coordinates, so they are seen
        through `applied` (the phases already done)."""
        listing = ['ls-tree', '-r', '--name-only', '-z', ref] if ref else ['ls-files', '-z']
        out = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), *listing],
                             capture_output=True, check=True, env=git_env()).stdout.decode('utf-8')
        files = {p for p in out.split('\0') if p}
        if cloud_index and Path(cloud_index).exists():
            db = sqlite3.connect(str(cloud_index))
            for (p,) in db.execute('SELECT DISTINCT path FROM objects'):
                if p.startswith(('zip:', '@')):
                    continue
                files.add((applied.map(p) if applied else None) or p)
            db.close()
        if local_inventory and Path(local_inventory).exists():
            with open(local_inventory, encoding='utf-8', newline='') as f:
                for row in csv.DictReader(f, delimiter='\t'):
                    if not row['path'].startswith('@'):
                        files.add((applied.map(row['path']) if applied else None) or row['path'])
        junctions = {}
        for tsv in reparse_tsvs:
            for line in Path(tsv).read_text(encoding='utf-8').splitlines():
                link, _, target = line.partition('\t')
                rel = _project_rel(norm_abs(target)) if target else None
                if rel is not None and _project_rel(norm_abs(link)) is None:
                    junctions[norm_abs(link)] = rel
        return cls(files, junctions)

    def canon(self, rel):
        """The path as the universe spells it (case-insensitive fallback), or None."""
        if rel in self.files or rel in self.dirs:
            return rel
        return self.lower.get(rel.lower())

    def exists(self, rel):
        return self.canon(rel) is not None

    def children(self, rel):
        return sorted(self.kids.get(rel, ()))


def _project_rel(abs_norm):
    """'X:/GMM_2_Final/a/b' -> 'a/b'; None when not inside the project."""
    m = re.match(r'^[A-Za-z]:/([^/]+)(?:/(.*))?$', abs_norm)
    if not m or m.group(1).lower() not in PROJECT_NAMES:
        return None
    return norm(m.group(2) or '')


def _longest(mapping, abs_norm):
    low = abs_norm.lower()
    best = None
    for key, rel in mapping.items():
        k = norm_abs(key).lower().rstrip('/')
        if (low == k or low.startswith(k + '/')) and (best is None or len(k) > len(best[0])):
            best = (k, rel)
    if best is None:
        return None
    rest = abs_norm[len(best[0]):].strip('/')
    return norm(best[1] + ('/' + rest if rest else ''))


def resolve(text, source_rel, uni, external_map):
    raw, suffix = text, ''
    escaped = '\\\\' in raw
    sep = '\\' if '\\' in raw else '/'
    m = _ABS.match(raw)
    if m:
        a = norm_abs(raw)
        rel = _project_rel(a)
        if rel is not None:
            # keep drive and folder as written: everything up to the project folder name
            pm = re.match(r'^(?:\\\\\?\\|//\?/)?[A-Za-z]:(?:\\\\|\\|/)+[^\\/]+', raw)
            style = Style(sep, escaped, 'abs_project', pm.group(0), trailing=raw.endswith(('/', '\\')))
            return Resolved(uni.canon(rel) or rel, style, uni.exists(rel))
        rel = _longest(uni.junctions, a)
        if rel is None:
            rel = _longest(external_map, a)
        if rel is None:
            return None
        return Resolved(uni.canon(rel) or rel, Style(sep, escaped, 'abs_external'), uni.exists(rel))
    if raw.startswith(('/', '\\')) or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', raw):
        return None
    for mark in ('#', '?'):
        if mark in raw:
            raw, tail = raw.split(mark, 1)
            suffix = mark + tail + suffix
    decoded = urllib.parse.unquote(raw) if '%' in raw else raw
    encoded = decoded != raw
    p = decoded.replace('\\', '/')
    dot, trailing = p.startswith('./'), p.endswith('/')
    style = Style(sep, escaped, 'file_rel', encoded=encoded, dot=dot, trailing=trailing, suffix=suffix)
    parts = [s for s in p.split('/') if s not in ('', '.')]
    if not parts:
        return None
    ups = 0
    while ups < len(parts) and parts[ups] == '..':
        ups += 1
    first = parts[ups] if ups < len(parts) else None
    base = norm(posixpath.join(posixpath.dirname(source_rel), *(['..'] * ups))) if ups else posixpath.dirname(source_rel)
    if base is not None and first is not None:
        if uni.exists(posixpath.join(base, first) if base else first):
            target = norm(posixpath.join(base, *parts[ups:]) if base else '/'.join(parts[ups:]))
            return Resolved(uni.canon(target) or target, style, uni.exists(target))
    if ups == 0 and uni.exists(parts[0]):
        target = norm('/'.join(parts))
        return Resolved(uni.canon(target) or target, replace(style, kind='root_rel'), uni.exists(target))
    return None


def _join(parts_rel, style):
    sep = '\\\\' if style.escaped else style.sep
    return parts_rel.replace('/', sep)


def render(target_new_rel, source_new_rel, style, mode):
    """Write a new target back. 'keep' keeps the original form; 'root_rel' writes a project-relative '/' path."""
    if mode == 'root_rel' or style.kind == 'abs_external':
        return target_new_rel
    if style.kind == 'abs_project':
        sep = '\\\\' if style.escaped else style.sep
        out = style.prefix + (sep + _join(target_new_rel, style) if target_new_rel else '')
        return out + (sep if style.trailing else '')
    if style.kind == 'file_rel':
        rel = posixpath.relpath(target_new_rel or '.', posixpath.dirname(source_new_rel) or '.')
        if style.dot and not rel.startswith('..'):
            rel = './' + rel if rel != '.' else '.'
    else:
        rel = target_new_rel
    if style.encoded:
        rel = '/'.join(urllib.parse.quote(seg, safe="!$&'()*+,;=:@-._~") for seg in rel.split('/'))
    out = _join(rel, style)
    if style.trailing:
        out += '\\\\' if style.escaped else style.sep
    return out + style.suffix

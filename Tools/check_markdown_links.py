"""Check relative Markdown links against the git tree, and compare against a recorded baseline.

    python Tools/check_markdown_links.py --write-baseline links.json
    python Tools/check_markdown_links.py --compare links.json [--rules moves_phase2.json ...]

A link is broken when its target (relative to the linking file, %-decoded, without
#anchor or ?query) is neither a tracked file nor a folder holding tracked files.
Links with a scheme (https:, mailto:) and pure anchors are skipped. `--compare` maps
the baseline through the given move rules (in order) and exits 1 when a link is broken
now that was not broken before; links already broken stay reported only in the baseline.
"""
import argparse
from dataclasses import asdict, dataclass
import json
import posixpath
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from restructure_resolve import git_env, norm
from restructure_rules import compose, load_rules

LINK = re.compile(r'\]\(\s*<?([^)>\s]+)>?(?:\s+"[^"]*")?\s*\)')


@dataclass(frozen=True)
class Broken:
    file: str
    line: int
    target: str
    resolved: str


def tracked(repo):
    out = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), 'ls-files', '-z'],
                         capture_output=True, check=True, env=git_env()).stdout.decode('utf-8')
    files = {p for p in out.split('\0') if p}
    dirs = {posixpath.dirname(p) for p in files}
    for d in list(dirs):
        while d:
            d = posixpath.dirname(d)
            dirs.add(d)
    return files, dirs


def scan(repo):
    repo = Path(repo)
    files, dirs = tracked(repo)
    out = []
    for name in sorted(f for f in files if f.lower().endswith(('.md', '.markdown'))):
        try:
            text = (repo / name).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        for m in LINK.finditer(text):
            target = m.group(1)
            if target.startswith('#') or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            path = urllib.parse.unquote(re.split(r'[#?]', target, 1)[0])
            if not path:
                continue
            resolved = norm(posixpath.join(posixpath.dirname(name), path)) if not path.startswith('/') else norm(path)
            if resolved is None or (resolved not in files and resolved not in dirs):
                out.append(Broken(name, text.count('\n', 0, m.start()) + 1, target, resolved or ''))
    return out


def compare(baseline, current, rules=None):
    known = set()
    for b in baseline:
        f = (rules.map(b.file) if rules else None) or b.file
        known.add((f, b.resolved))
        known.add((f, (rules.map(b.resolved) if rules and b.resolved else None) or b.resolved))
    return [c for c in current if (c.file, c.resolved) not in known]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--write-baseline')
    ap.add_argument('--compare')
    ap.add_argument('--rules', nargs='*', default=[])
    args = ap.parse_args(argv)
    current = scan(args.repo)
    if args.write_baseline:
        Path(args.write_baseline).write_text(json.dumps([asdict(b) for b in current], ensure_ascii=False, indent=1) + '\n',
                                             encoding='utf-8', newline='\n')
        print(f'{len(current)} broken links recorded')
        return 0
    if args.compare:
        base = [Broken(**b) for b in json.loads(Path(args.compare).read_text(encoding='utf-8'))]
        rules = compose([load_rules(p) for p in args.rules]) if args.rules else None
        new = compare(base, current, rules)
        for b in new:
            print(f'{b.file}:{b.line}: {b.target}')
        print(f'{len(current)} broken now, {len(base)} in baseline, {len(new)} new')
        return 1 if new else 0
    for b in current:
        print(f'{b.file}:{b.line}: {b.target}')
    print(f'{len(current)} broken')
    return 0


if __name__ == '__main__':
    sys.exit(main())

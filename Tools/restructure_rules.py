"""Move rules for the 2026-10-28 tree restructure.

A phase's rules live in docs/operations/TREE_RESTRUCTURE_20261028/moves_phaseN.json:

    {"phase": 3, "moves": [
      {"old": "Step_analysis_20260623", "new": "Analyses/Step_analysis_20260623"},
      {"old": "A/_r61_real_sample_runtime_*", "into": "Analyses/A/_r61_real_sample_runtime"}]}

Paths are repo-relative, '/'-separated, without a trailing slash, and written in the
coordinates of the tree at the start of that phase. A plain rule moves `old` (and
everything under it) to `new`. A glob rule (only the last segment of `old` may carry
`*`) moves every matching child of its parent, under its own name, into `into`; it
matches children that do not exist yet, so folders created at run time land right.
The most specific match wins: a longer matched prefix beats a shorter one.
"""
from dataclasses import dataclass
import fnmatch
import json
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    old: str
    new: str


@dataclass(frozen=True)
class GlobRule:
    parent: str
    pattern: str
    into: str


def _clean(path):
    return path.replace('\\', '/').strip('/')


class RuleSet:
    def __init__(self, rules, globs=()):
        self.rules = [Rule(_clean(r.old), _clean(r.new)) for r in rules]
        self.globs = [GlobRule(_clean(g.parent), g.pattern, _clean(g.into)) for g in globs]

    def map(self, rel):
        """Repo-relative old path -> new path, or None when no rule moves it."""
        rel = _clean(rel)
        best, best_len = None, -1
        for r in self.rules:
            if (rel == r.old or rel.startswith(r.old + '/')) and len(r.old) > best_len:
                best, best_len = r.new + rel[len(r.old):], len(r.old)
        for g in self.globs:
            if not rel.startswith(g.parent + '/'):
                continue
            rest = rel[len(g.parent) + 1:]
            head = rest.split('/', 1)[0]
            length = len(g.parent) + 1 + len(head)
            if fnmatch.fnmatchcase(head, g.pattern) and length > best_len:
                best, best_len = g.into + '/' + rest, length
        return best

    def splits_under(self, rel):
        """True when things under `rel` do not all follow `rel` itself (a rule or glob starts deeper)."""
        rel = _clean(rel)
        inside = (lambda p: p.startswith(rel + '/')) if rel else (lambda p: p != '')
        return any(inside(r.old) for r in self.rules) or any(g.parent == rel or inside(g.parent) for g in self.globs)

    def diverges_under(self, rel):
        """True when something under `rel` ends up outside the place `rel` itself moves to."""
        rel = _clean(rel)
        dest = self.map(rel) or rel
        inside = (lambda p: p.startswith(rel + '/')) if rel else (lambda p: p != '')
        within = (lambda p: p.startswith(dest + '/')) if dest else (lambda p: True)
        return any(inside(r.old) and not within(r.new) for r in self.rules) or \
            any((g.parent == rel or inside(g.parent)) and not within(g.into) for g in self.globs)

    def moved_roots(self):
        """The old locations named by the rules (glob rules give their pattern)."""
        return [r.old for r in self.rules] + [f'{g.parent}/{g.pattern}' for g in self.globs]


def load_rules_from_obj(obj):
    rules, globs = [], []
    for move in obj['moves']:
        old = _clean(move['old'])
        if '*' in old:
            parent, _, pattern = old.rpartition('/')
            if '*' in parent or 'into' not in move:
                raise ValueError(f'glob only allowed in the last segment, with "into": {move}')
            globs.append(GlobRule(parent, pattern, move['into']))
        else:
            rules.append(Rule(old, move['new']))
    return RuleSet(rules, globs)


def load_rules(path):
    return load_rules_from_obj(json.loads(Path(path).read_text(encoding='utf-8')))


class Composed:
    """Phases applied in order; map() gives the final location, or None if never moved."""

    def __init__(self, rulesets):
        self.rulesets = list(rulesets)

    def map(self, rel):
        current, moved = _clean(rel), False
        for rs in self.rulesets:
            new = rs.map(current)
            if new is not None:
                current, moved = new, True
        return current if moved else None

    def splits_under(self, rel):
        current = _clean(rel)
        for rs in self.rulesets:
            if rs.splits_under(current):
                return True
            current = rs.map(current) or current
        return False

    def diverges_under(self, rel):
        current = _clean(rel)
        for rs in self.rulesets:
            if rs.diverges_under(current):
                return True
            current = rs.map(current) or current
        return False


def compose(rulesets):
    return Composed(rulesets)

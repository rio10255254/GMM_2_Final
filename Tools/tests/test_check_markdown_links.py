"""Markdown link check: record a baseline, then report only links broken since then (after the move rules)."""
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_markdown_links import compare, scan
from restructure_rules import Rule, RuleSet


def git(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    subprocess.run(['git', *args], check=True, env=env, capture_output=True)


def make(repo, files):
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    git('-C', str(repo), 'add', '-A')


def test_scan_finds_broken_relative_links(tmp_path):
    git('init', '-q', str(tmp_path))
    make(tmp_path, {'docs/a.md': '[ok](../Model/x.py) [bad](../Model/missing.py) [web](https://x.y) [here](#top) [enc](../%E4%BD%8D/b.md)\n',
                    'Model/x.py': 'x\n', '位/b.md': 'b\n'})
    assert [(b.file, b.line, b.target) for b in scan(tmp_path)] == [('docs/a.md', 1, '../Model/missing.py')]


def test_compare_flags_only_new_breaks(tmp_path):
    git('init', '-q', str(tmp_path))
    make(tmp_path, {'docs/a.md': '[run](../AnalysisLab/run.py) [old](../AnalysisLab/gone.py)\n', 'AnalysisLab/run.py': 'x\n'})
    base = scan(tmp_path)
    rules = RuleSet([Rule('AnalysisLab', 'Analyses/AnalysisLab')])
    git('-C', str(tmp_path), 'mv', 'AnalysisLab', 'Analyses')
    (tmp_path / 'Analyses' / 'AnalysisLab').mkdir()
    git('-C', str(tmp_path), 'mv', 'Analyses/run.py', 'Analyses/AnalysisLab/run.py')
    assert [b.target for b in compare(base, scan(tmp_path), rules)] == ['../AnalysisLab/run.py']
    make(tmp_path, {'docs/a.md': '[run](../Analyses/AnalysisLab/run.py) [old](../Analyses/AnalysisLab/gone.py)\n'})
    assert compare(base, scan(tmp_path), rules) == []

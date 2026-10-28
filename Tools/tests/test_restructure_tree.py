"""End to end on a scratch repo: plan writes reports only, apply moves and rewrites, verify passes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import restructure_tree


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    return subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', *args],
                          check=True, env=env, capture_output=True, text=True).stdout


def write(repo, name, text):
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8', newline='\n')


def make_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    write(repo, 'AnalysisLab/run.py', "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nM = ROOT / 'Model' / 'a.py'\n")
    write(repo, 'Model/a.py', 'x = 1\n')
    write(repo, 'docs/a.md', 'Run [it](../AnalysisLab/run.py).\n')
    sha = hashlib.sha256((repo / 'docs/a.md').read_bytes()).hexdigest()
    write(repo, 'docs/idx.json', json.dumps({'files': [{'path': 'docs/a.md', 'sha256': sha, 'bytes': 33}]}, indent=1) + '\n')
    rec = repo / 'docs/operations/TREE_RESTRUCTURE_20261028'
    write(repo, 'docs/operations/TREE_RESTRUCTURE_20261028/moves_phase2.json',
          json.dumps({'phase': 2, 'moves': [{'old': 'AnalysisLab', 'new': 'Analyses/AnalysisLab'}]}))
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'start')
    return repo, rec


def args(repo, *more):
    return [*more, '--repo', str(repo), '--no-tests']


def test_plan_apply_verify(tmp_path):
    repo, rec = make_repo(tmp_path)
    assert restructure_tree.main(args(repo, 'plan', '--phase', '2')) == 0
    assert (repo / 'AnalysisLab/run.py').exists() and (rec / 'edits_phase2.jsonl').exists()
    assert git(repo, 'status', '--porcelain', '--untracked-files=no') == ''
    assert restructure_tree.main(args(repo, 'apply', '--phase', '2')) == 0
    assert not (repo / 'AnalysisLab').exists()
    assert 'parents[2]' in (repo / 'Analyses/AnalysisLab/run.py').read_text(encoding='utf-8')
    assert '(../Analyses/AnalysisLab/run.py)' in (repo / 'docs/a.md').read_text(encoding='utf-8')
    idx = json.loads((repo / 'docs/idx.json').read_text(encoding='utf-8'))['files'][0]
    assert idx['sha256'] == hashlib.sha256((repo / 'docs/a.md').read_bytes()).hexdigest()
    assert idx['bytes'] == len((repo / 'docs/a.md').read_bytes())
    assert 'R  AnalysisLab/run.py -> Analyses/AnalysisLab/run.py' in git(repo, 'status', '--porcelain')
    assert restructure_tree.main(args(repo, 'verify', '--phase', '2')) == 0


def test_moved_files_stay_tracked_under_ignored_folders(tmp_path):
    repo, rec = make_repo(tmp_path)
    write(repo, '.gitignore', 'AnalysisLab/\nAnalyses/\n')
    git(repo, 'add', '.gitignore'); git(repo, 'commit', '-qm', 'ignore')
    assert restructure_tree.main(args(repo, 'apply', '--phase', '2')) == 0
    files = git(repo, 'ls-files').split()
    assert 'Analyses/AnalysisLab/run.py' in files and 'AnalysisLab/run.py' not in files


def test_untracked_local_files_move_with_their_folder(tmp_path):
    repo, rec = make_repo(tmp_path)
    write(repo, '.gitignore', 'data/\n')
    git(repo, 'add', '.gitignore'); git(repo, 'commit', '-qm', 'ignore')
    write(repo, 'AnalysisLab/data/big.npz', 'local only\n')
    assert restructure_tree.main(args(repo, 'apply', '--phase', '2')) == 0
    assert (repo / 'Analyses/AnalysisLab/data/big.npz').read_text() == 'local only\n'
    assert not (repo / 'AnalysisLab').exists()
    assert 'Analyses/AnalysisLab/data/big.npz' not in git(repo, 'ls-files').split()


def test_pytest_output_with_chinese_is_read(tmp_path, monkeypatch):
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')     # how the phase runs are launched
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_x.py').write_text(
        "def test_a():\n    print('位移序列：所有原始影像與裁切輸入都已核對' * 50)\n    assert False\n", encoding='utf-8')
    assert restructure_tree.run_pytest(tmp_path, ['tests']) == {'tests': ['tests/test_x.py::test_a']}


def test_apply_refuses_while_ambiguous_references_remain(tmp_path):
    repo, rec = make_repo(tmp_path)
    write(repo, 'Traing_Progress/README.md', 'x\n')
    write(repo, 'Model/train.py', "import os\nPROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
                                  "T = os.path.join(PROJECT_ROOT, 'Traing_Progress', name)\n")
    write(repo, 'docs/operations/TREE_RESTRUCTURE_20261028/moves_phase4.json', json.dumps({'phase': 4, 'moves': [
        {'old': 'Traing_Progress/training_progress_*', 'into': 'Experiments/Training_Runs'},
        {'old': 'Traing_Progress', 'new': 'Experiments/Legacy'}]}))
    git(repo, 'add', '-A'); git(repo, 'commit', '-qm', 'p4')
    assert restructure_tree.main(args(repo, 'apply', '--phase', '4')) == 2
    assert (repo / 'Traing_Progress/README.md').exists()
    assert 'Model/train.py\t3\t' in (rec / 'unresolved_phase4.tsv').read_text(encoding='utf-8')


def test_verify_catches_a_bad_rewrite(tmp_path):
    repo, rec = make_repo(tmp_path)
    assert restructure_tree.main(args(repo, 'apply', '--phase', '2')) == 0
    p = repo / 'Analyses/AnalysisLab/run.py'
    p.write_text(p.read_text(encoding='utf-8').replace('parents[2]', 'parents[1]'), encoding='utf-8')
    assert restructure_tree.main(args(repo, 'verify', '--phase', '2')) == 1

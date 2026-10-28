"""Resolving a reference to the place it points to in the old tree, and writing it back in its own style."""
from pathlib import Path
import sqlite3
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
import pytest
from restructure_resolve import Universe, resolve, render
from restructure_rules import Rule, RuleSet, compose

PATHS = [
    '_deployment_package/GeoEdge_R26_正式交付版/app/run.py',
    '_deployment_package/GeoEdge_R26_正式交付版/Reconstruct_Progress/x.txt',
    'Reconstruct_Progress/y.txt',
    'Deliverables/R137_PSF100_V42_Select8_20260923/train_v42.py',
    'Deliverables/R137_PSF100_V42_Select8_20260923/Traing_Progress/.keep',
    'Traing_Progress/organized_20260313/README.md',
    '20260702_100MG_位移_50x/a.bmp',
    'docs/x.md', 'Tools/x.json', 'Tools/x.py',
    'Shared_Sources/PI_Repeatability_20260903/raw/run01/a.bmp',
]
JUNCTIONS = {'C:/Users/Rio/Downloads/20260902_100MF_uncertainty/20260903': 'Shared_Sources/PI_Repeatability_20260903/raw'}


def clean_git(*args):
    """git without the GIT_* variables a hook exports, so a test repo never touches the real one."""
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    subprocess.run(['git', *args], check=True, env=env, capture_output=True)


def make_repo(path, name):
    (path / 'Model').mkdir(parents=True)
    (path / 'Model' / name).write_text('x\n')
    clean_git('init', '-q', str(path))
    clean_git('-C', str(path), 'add', '.')


@pytest.fixture
def uni():
    return Universe.from_paths(PATHS, JUNCTIONS)


def test_package_internal_names_stay_internal(uni):
    r = resolve('../Reconstruct_Progress', '_deployment_package/GeoEdge_R26_正式交付版/app/run.py', uni, {})
    assert r.target_rel == '_deployment_package/GeoEdge_R26_正式交付版/Reconstruct_Progress'
    assert resolve('/app/Traing_Progress', '_deployment_package/GeoEdge_R26_正式交付版/app/run.py', uni, {}) is None
    r = resolve('Traing_Progress', 'Deliverables/R137_PSF100_V42_Select8_20260923/train_v42.py', uni, {})
    assert r.target_rel == 'Deliverables/R137_PSF100_V42_Select8_20260923/Traing_Progress'


def test_root_relative_when_not_beside_the_file(uni):
    r = resolve('Traing_Progress/organized_20260313', 'Tools/x.json', uni, {})
    assert (r.target_rel, r.style.kind, r.exists) == ('Traing_Progress/organized_20260313', 'root_rel', True)


def test_absolute_forms(uni):
    for s in [r'D:\GMM_2_Final\Traing_Progress\organized_20260313', 'd:/gmm_2_final/Traing_Progress/organized_20260313',
              r'D:\\GMM_2_Final\\Traing_Progress\\organized_20260313', r'\\?\D:\GMM_2_Final\Traing_Progress\organized_20260313']:
        assert resolve(s, 'Tools/x.json', uni, {}).target_rel == 'Traing_Progress/organized_20260313'


def test_render_keeps_style(uni):
    r = resolve(r'D:\\GMM_2_Final\\Traing_Progress\\organized_20260313', 'Tools/x.json', uni, {})
    assert render('Experiments/Legacy/organized_20260313', 'Tools/x.json', r.style, 'keep') == r'D:\\GMM_2_Final\\Experiments\\Legacy\\organized_20260313'
    assert render('Experiments/Legacy/organized_20260313', 'Tools/x.json', r.style, 'root_rel') == 'Experiments/Legacy/organized_20260313'


def test_render_relative_recomputed_from_new_source(uni):
    r = resolve('../Traing_Progress/organized_20260313/README.md#批次', 'docs/x.md', uni, {})
    assert r.target_rel == 'Traing_Progress/organized_20260313/README.md'
    assert render('Experiments/Legacy/organized_20260313/README.md', 'docs/x.md', r.style, 'keep') == \
        '../Experiments/Legacy/organized_20260313/README.md#批次'


def test_markdown_encoded_link(uni):
    r = resolve('../20260702_100MG_%E4%BD%8D%E7%A7%BB_50x/a.bmp', 'docs/x.md', uni, {})
    assert r.target_rel == '20260702_100MG_位移_50x/a.bmp'
    assert render('Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x/a.bmp', 'docs/x.md', r.style, 'keep') == \
        '../Shared_Sources/Real_Sample_Captures/20260702_100MG_%E4%BD%8D%E7%A7%BB_50x/a.bmp'


def test_missing_target_judged_by_existing_ancestor(uni):
    r = resolve('Traing_Progress/training_progress_new_run/log.txt', 'Tools/x.py', uni, {})
    assert (r.target_rel, r.exists) == ('Traing_Progress/training_progress_new_run/log.txt', False)


def test_junction_and_external(uni):
    r = resolve(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260903\run01\a.bmp', 'Tools/x.py', uni, {})
    assert r.target_rel == 'Shared_Sources/PI_Repeatability_20260903/raw/run01/a.bmp'
    ext = {'D:/NTU_ImageDataset/Pitch1um_Y_100/Raw': 'Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw'}
    r = resolve(r'D:\NTU_ImageDataset\Pitch1um_Y_100\Raw\VisionTop_1.bmp', 'Tools/x.py', uni, ext)
    assert (r.target_rel, r.style.kind) == ('Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw/VisionTop_1.bmp', 'abs_external')
    assert resolve(r'E:\GmmVisionToolExe\run.exe', 'Tools/x.py', uni, ext) is None


def test_build_reads_tracked_release_and_local(tmp_path):
    repo = tmp_path / 'repo'
    make_repo(repo, 'a.py')
    db = sqlite3.connect(tmp_path / 'index.sqlite')
    db.execute('CREATE TABLE objects(path TEXT, sha256 TEXT, bytes INTEGER, tag TEXT, asset TEXT, collection TEXT)')
    db.executemany('INSERT INTO objects VALUES (?,?,?,?,?,?)', [('Step/1.bmp', 'a' * 64, 1, 't', 'z', 'c'),
                                                               ('zip:p.zip/m.txt', 'b' * 64, 1, 't', 'z', 'c')])
    db.commit(); db.close()
    inv = tmp_path / 'inv.tsv'
    inv.write_text('status\tbytes\tpath\twhere\nlocal-only\t5\tTraing_Progress/organized_x/w.pth\t\nlocal-only\t5\t@NTU/a.bmp\t\n', encoding='utf-8')
    reparse = tmp_path / 'inv.tsv.reparse.tsv'
    reparse.write_text('C:\\Users\\Rio\\Downloads\\20260902_100MF_uncertainty\\20260903\tD:\\GMM_2_Final\\Shared_Sources\\PI\\raw\n', encoding='utf-8')
    applied = compose([RuleSet([Rule('Step', 'Shared_Sources/Real_Sample_Captures/Step')])])
    u = Universe.build(repo, tmp_path / 'index.sqlite', inv, applied, [reparse])
    assert u.exists('Model/a.py') and u.exists('Model')
    assert u.exists('Shared_Sources/Real_Sample_Captures/Step/1.bmp') and not u.exists('Step/1.bmp')
    assert u.exists('Traing_Progress/organized_x/w.pth')
    assert not any(p.startswith(('zip:', '@')) for p in u.files)
    assert u.junctions == {'C:/Users/Rio/Downloads/20260902_100MF_uncertainty/20260903': 'Shared_Sources/PI/raw'}
    assert u.children('Model') == ['a.py']


def test_build_ignores_git_variables_from_a_hook(tmp_path, monkeypatch):
    repo, other = tmp_path / 'repo', tmp_path / 'other'
    make_repo(repo, 'a.py')
    make_repo(other, 'wrong.py')
    monkeypatch.setenv('GIT_DIR', str(other / '.git'))
    monkeypatch.setenv('GIT_INDEX_FILE', str(other / '.git' / 'index'))
    u = Universe.build(repo)
    assert u.exists('Model/a.py') and not u.exists('Model/wrong.py')

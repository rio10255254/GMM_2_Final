"""Verification: rewritten references still reach the same (moved) places; nothing still points at old places."""
import hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restructure_resolve import Universe
from restructure_rules import Rule, RuleSet, load_rules
from restructure_text import Context, Edit
import restructure_verify as v

RULES_DIR = Path(__file__).resolve().parents[2] / 'docs' / 'operations' / 'TREE_RESTRUCTURE_20261028'
RULES = RuleSet([Rule('Validations', 'Deliverables/Validations'), Rule('AnalysisLab', 'Analyses/AnalysisLab')])
OLD = Universe.from_paths(['Validations/a.json', 'docs/x.md', 'AnalysisLab/run.py', 'Model/a.py'])
NEW = Universe.from_paths(['Deliverables/Validations/a.json', 'docs/x.md', 'Analyses/AnalysisLab/run.py', 'Model/a.py'])


def edit(old, new, file_old='docs/x.md', file_new='docs/x.md', kind='doc:link'):
    return Edit(file_old, file_new, 1, old, new, kind, '', '')


def test_text_equivalence_accepts_right_and_flags_wrong():
    good = edit('../Validations/a.json', '../Deliverables/Validations/a.json')
    bad = edit('../Validations/a.json', '../Validations/Deliverables/a.json')
    assert v.equivalence([good], OLD, NEW, RULES, {}) == []
    assert len(v.equivalence([bad], OLD, NEW, RULES, {})) == 1


def test_python_equivalence_reevaluates_new_source():
    old_src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nM = ROOT / 'Model' / 'a.py'\n"
    good = old_src.replace('parents[1]', 'parents[2]')
    ctx_old, ctx_new = Context(OLD, RULES, {}, 'moves'), Context(NEW, None, {}, 'moves')
    assert v.python_equivalence(old_src, good, 'AnalysisLab/run.py', 'Analyses/AnalysisLab/run.py', ctx_old, ctx_new, RULES) == []
    assert v.python_equivalence(old_src, old_src, 'AnalysisLab/run.py', 'Analyses/AnalysisLab/run.py', ctx_old, ctx_new, RULES) != []


def test_evaluated_targets_count_a_climb_chain_once():
    from restructure_python import evaluated_targets
    src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nM = ROOT / 'Model' / 'a.py'\n"
    assert evaluated_targets(src, 'AnalysisLab/run.py', Context(OLD, None, {}, 'moves')) == ['', 'Model/a.py']


def test_residual_finds_paths_into_old_places_but_ignores_records():
    files = {'docs/x.md': 'see Validations/a.json and Deliverables/Validations/a.json\n',
             'docs/operations/TREE_RESTRUCTURE_20261028.md': '`Validations/a.json` → `Deliverables/Validations/a.json`\n',
             'Tools/run.py': "P = r'D:\\GMM_2_Final\\Model\\a.py'\n"}
    found = v.residual(files, NEW, RULES, absolute_check=True)
    assert any('docs/x.md' in f and 'Validations/a.json' in f for f in found)
    assert any('Tools/run.py' in f for f in found)
    assert not any('TREE_RESTRUCTURE' in f for f in found)
    assert len(found) == 2


def test_hash_consistency():
    a_old, a_new = b'old text\n', b'new text\n'
    before = {'docs/a.md': a_old, 'docs/idx.json': ('{"sha256": "%s"}' % hashlib.sha256(a_old).hexdigest()).encode()}
    pairs = v.hash_pairs(before)
    assert pairs == {('docs/idx.json', hashlib.sha256(a_old).hexdigest()): frozenset({'docs/a.md'})}
    after_ok = {'docs/a.md': a_new, 'docs/idx.json': ('{"sha256": "%s"}' % hashlib.sha256(a_new).hexdigest()).encode()}
    after_bad = {'docs/a.md': a_new, 'docs/idx.json': before['docs/idx.json']}
    assert v.hash_consistency(pairs, after_ok, RULES) == []
    assert v.hash_consistency(pairs, after_bad, RULES) == ['docs/idx.json no longer records the sha256 of docs/a.md']


def test_virtual_tree_flags_target_lost_on_this_machine():
    local = Universe.from_paths(['Validations/big.npz', 'Model/a.py'])
    ok = Edit('docs/x.md', 'docs/x.md', 1, 'a', 'b', 'doc:path', 'Validations/big.npz', 'Deliverables/Validations/big.npz')
    lost = Edit('docs/x.md', 'docs/x.md', 1, 'a', 'b', 'doc:path', 'Validations/big.npz', 'Validations/big.npz')
    assert v.virtual_tree([ok], local, RULES) == []
    assert v.virtual_tree([lost], local, RULES) == ['docs/x.md:1: Validations/big.npz exists here but Validations/big.npz will not']


def test_gitignore_scope_detects_widening(tmp_path):
    old, new = tmp_path / 'old', tmp_path / 'new'
    old.write_text('_deployment_package/\n'); new.write_text('Deliverables/Company_Packages/\n')
    paths = ['_deployment_package/GeoEdge_R26_正式交付版/w.onnx', 'Deliverables/MOSR_ONNX/m.onnx']
    rules = load_rules(RULES_DIR / 'moves_phase2.json')
    assert v.gitignore_scope(old, new, paths, rules) == ['Deliverables/MOSR_ONNX/m.onnx']


def test_hash_consistency_with_duplicate_contents():
    same = b'same\n'
    h = hashlib.sha256(same).hexdigest()
    before = {'a/x.txt': same, 'b/y.txt': same, 'r.json': ('{"sha256": "%s"}' % h).encode()}
    after = {'a/x.txt': same, 'b/y.txt': b'rewritten\n', 'r.json': before['r.json']}
    assert v.hash_consistency(v.hash_pairs(before), after, RULES) == []


def test_structure_check_flags_json_that_stopped_parsing():
    before = {'a.json': b'{"p": "x"}', 'b.ipynb': b'{"cells": []}', 'c.json': b'not json'}
    after = {'a.json': b'{"p": "y"}', 'b.ipynb': b'{"cells": [}', 'c.json': b'still not json'}
    assert v.structure(before, after, None) == ['b.ipynb: no longer parses as JSON']


def test_content_addressed_files_are_recognised():
    data = b'{"design": 1}\n'
    h = hashlib.sha256(data).hexdigest()
    assert v.content_addressed(f'Experiments/R94/archive/{h}/experiment_design.json', data)
    assert not v.content_addressed(f'Experiments/R94/archive/{"0" * 64}/experiment_design.json', data)
    assert not v.content_addressed('docs/x.md', data)


def test_location_mode_may_gain_dynamic_expressions():
    old = "from pathlib import Path\nS = Path('H:/Old/SEM') / name\n"
    new = "from pathlib import Path\nPROJECT_ROOT = Path(__file__).resolve().parents[1]\nS = Path(str(PROJECT_ROOT / 'Shared_Sources/SEM')) / name\n"
    ctx = Context(OLD, None, {}, 'location')
    assert v.python_equivalence(old, new, 'Tools/x.py', 'Tools/x.py', ctx, ctx, None) == []


def test_transform_tools_and_their_tests_are_records():
    for name in ['Tools/restructure_python.py', 'Tools/tests/test_restructure_text.py', 'Tools/check_markdown_links.py',
                 'Tools/tests/test_check_markdown_links.py', 'docs/operations/TREE_RESTRUCTURE_20261028/moves_phase2.json']:
        assert v.is_record(name), name
    assert not v.is_record('Tools/cloud_locator.py') and not v.is_record('Tools/tests/test_cloud_locator.py')


def test_residual_reads_only_notebook_code_cells():
    import json as _json
    nb = {'cells': [{'cell_type': 'markdown', 'source': ['Ran with C:/Users/Rio/anaconda3/python.exe\n']},
                    {'cell_type': 'code', 'source': ['x = 1\n']}]}
    assert v.residual({'docs/a.ipynb': _json.dumps(nb)}, NEW, None, absolute_check=True) == []
    nb['cells'][1]['source'] = ["p = 'D:/GMM_2_Final/Model/a.py'\n"]
    assert len(v.residual({'docs/a.ipynb': _json.dumps(nb)}, NEW, None, absolute_check=True)) == 1


def test_residual_ignores_folders_that_only_start_with_the_project_name():
    files = {'Tools/a.py': "A = r'H:\\GMM_2_Final_Archive\\x'\n"}
    assert v.residual(files, NEW, None, absolute_check=True) == []


def test_residual_lets_prose_name_the_project_folder():
    src = ('"""Run from d:/GMM_2_Final/ or anywhere."""\n'
           '# the old home was D:\\GMM_2_Final\n'
           "README = \'\'\'\nKept D:/GMM_2_Final的原模型 as it was.\n\'\'\'\n")
    assert v.residual({'Tools/a.py': src}, NEW, None, absolute_check=True) == []
    code = "ROOT = r'D:\\GMM_2_Final'\n"
    assert len(v.residual({'Tools/a.py': code}, NEW, None, absolute_check=True)) == 1
    tail = '"""Data in D:/GMM_2_Final/Model/a.py."""\n'
    assert len(v.residual({'Tools/a.py': tail}, NEW, None, absolute_check=True)) == 1


def test_location_equivalence_accepts_the_bare_root_as_dot():
    from restructure_text import Edit
    q = chr(39) * 3
    e = Edit('Tools/a.py', 'Tools/a.py', 3, q + "refs to D:/GMM_2_Final; done" + q, q + "refs to .; done" + q, 'py:string', '', '')
    assert v.equivalence([e], NEW, NEW, None, {}) == []


def test_location_equivalence_accepts_the_bare_root_kept_in_prose():
    from restructure_text import Edit
    e = Edit('Tools/a.py', 'Tools/a.py', 1, '"""--root D:/GMM_2_Final scan D:/GMM_2_Final/Model/a.py"""',
             '"""--root D:/GMM_2_Final scan Model/a.py"""', 'py:string', '', '')
    assert v.equivalence([e], NEW, NEW, None, {}) == []


def test_python_equivalence_accepts_a_climb_via_the_common_ancestor():
    old_src = "from pathlib import Path\nT = Path(__file__).resolve().parents[1]\n"
    new_src = "from pathlib import Path\nT = (Path(__file__).resolve().parents[1] / 'Thesis_MOSR_Evidence')\n"
    rules = RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')])
    old = Universe.from_paths(['Thesis_MOSR_Evidence/LabSystem_MOSR/run.py', 'Thesis_MOSR_Evidence/a.png'])
    new = Universe.from_paths(['LabSystem_MOSR/run.py', 'Thesis_MOSR_Evidence/a.png'])
    ctx_old, ctx_new = Context(old, rules, {}, 'moves'), Context(new, None, {}, 'moves')
    assert v.python_equivalence(old_src, new_src, 'Thesis_MOSR_Evidence/LabSystem_MOSR/run.py', 'LabSystem_MOSR/run.py',
                                ctx_old, ctx_new, rules) == []


def test_equivalence_reads_the_new_text_the_way_the_old_one_was_read():
    from restructure_text import Edit
    rules = RuleSet([Rule('_build153', 'Experiments/R153/_build153')])
    old = Universe.from_paths(['_build153/a.py', 'docs/repro/experiments/x.md', 'docs/repro/files.json'])
    new = Universe.from_paths(['Experiments/R153/_build153/a.py', 'docs/repro/experiments/x.md', 'docs/repro/files.json'])
    e = Edit('docs/repro/files.json', 'docs/repro/files.json', 1, '_build153/a.py', 'Experiments/R153/_build153/a.py',
             'record:path', '_build153/a.py', 'Experiments/R153/_build153/a.py')
    assert v.equivalence([e], old, new, rules, {}) == []


def test_residual_accepts_a_pattern_whose_folder_exists_where_the_file_reads_it():
    rules = RuleSet([Rule('Reconstruct_Progress', 'Analyses/Reconstruct_Progress')])
    new = Universe.from_paths(['Lab/Reconstruct_Progress/prep/gmf_cases/a.bmp', 'Analyses/Reconstruct_Progress/README.md'])
    files = {'Lab/MANIFEST.md': 'outputs in `Reconstruct_Progress/prep/gmf_cases/lab_r46_*/`\n'}
    assert v.residual(files, new, rules) == []


def test_residual_ignores_a_reading_that_never_existed_before_the_move():
    rules = RuleSet([Rule('Reconstruct_Progress', 'Analyses/Reconstruct_Progress')])
    old = Universe.from_paths(['Reconstruct_Progress/README.md', 'Lab/archive/MANIFEST.csv', 'Docs/a.md'])
    new = Universe.from_paths(['Analyses/Reconstruct_Progress/README.md', 'Lab/archive/MANIFEST.csv', 'Docs/a.md'])
    files = {'Lab/archive/MANIFEST.csv': 'relative_path\nReconstruct_Progress/prep/gone/a.bmp\n',
             'Docs/a.md': 'see Reconstruct_Progress/README.md\n'}
    found = v.residual(files, new, rules, old_uni=old)
    assert len(found) == 1 and found[0].startswith('Docs/a.md')


def test_equivalence_accepts_a_moved_folder_written_as_one_segment():
    # 'Thesis_MOSR_Evidence/LabSystem_MOSR' moved to the root: the new string has no slash left
    rules = RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')])
    old = Universe.from_paths(['Thesis_MOSR_Evidence/LabSystem_MOSR/run.py', 'Tools/a.py'])
    new = Universe.from_paths(['LabSystem_MOSR/run.py', 'Tools/a.py'])
    good = Edit('Tools/a.py', 'Tools/a.py', 1, "'Thesis_MOSR_Evidence/LabSystem_MOSR'", "'LabSystem_MOSR'", 'py:string', '', '')
    bad = Edit('Tools/a.py', 'Tools/a.py', 1, "'Thesis_MOSR_Evidence/LabSystem_MOSR'", "'LabSystem'", 'py:string', '', '')
    assert v.equivalence([good], old, new, rules, {}) == []
    assert len(v.equivalence([bad], old, new, rules, {})) == 1


def test_python_equivalence_takes_a_kept_climb_to_where_it_now_reaches():
    # the code is kept as written; after the move the same climb reaches the project root
    src = "from pathlib import Path\nT = Path(__file__).resolve().parents[1]\n"
    rules = RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')])
    old = Universe.from_paths(['Thesis_MOSR_Evidence/LabSystem_MOSR/run.py', 'Thesis_MOSR_Evidence/a.png'])
    new = Universe.from_paths(['LabSystem_MOSR/run.py', 'Thesis_MOSR_Evidence/a.png'])
    ctx_old, ctx_new = Context(old, rules, {}, 'moves'), Context(new, None, {}, 'moves')
    args = (src, src, 'Thesis_MOSR_Evidence/LabSystem_MOSR/run.py', 'LabSystem_MOSR/run.py', ctx_old, ctx_new, rules)
    assert v.python_equivalence(*args, {'Thesis_MOSR_Evidence': ''}) == []
    assert v.python_equivalence(*args) != []


def test_python_equivalence_does_not_count_a_new_base_folder_as_a_destination():
    # one root that held both kinds of folder becomes two roots; the new one is only joined onto
    old_src = ("from pathlib import Path\nP = Path(__file__).resolve().parents[1]\nT = P / 'Traing_Progress'\n"
               "S = T / 'organized_1' / 'a.json'\n")
    new_src = ("from pathlib import Path\nP = Path(__file__).resolve().parents[1]\nT = P / 'Experiments' / 'Training_Runs'\n"
               "L = P / 'Experiments' / 'Legacy'\nS = L / 'organized_1' / 'a.json'\n")
    wrong = new_src.replace("S = L /", "S = T /")
    rules = RuleSet([Rule('Traing_Progress', 'Experiments/Legacy')])
    old = Universe.from_paths(['Traing_Progress/organized_1/a.json', 'Model/a.py'])
    new = Universe.from_paths(['Experiments/Legacy/organized_1/a.json', 'Experiments/Training_Runs/README.md', 'Model/a.py'])
    ctx_old, ctx_new = Context(old, rules, {}, 'moves'), Context(new, None, {}, 'moves')
    dec = {'Traing_Progress': 'Experiments/Training_Runs'}
    assert v.python_equivalence(old_src, new_src, 'Model/a.py', 'Model/a.py', ctx_old, ctx_new, rules, dec) == []
    assert v.python_equivalence(old_src, wrong, 'Model/a.py', 'Model/a.py', ctx_old, ctx_new, rules, dec) != []

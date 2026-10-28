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

"""Move rules: longest prefix, path-segment boundaries, glob expansion, phase composition."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restructure_rules import Rule, RuleSet, compose, load_rules, load_rules_from_obj

RULES_DIR = Path(__file__).resolve().parents[2] / 'docs' / 'operations' / 'TREE_RESTRUCTURE_20261028'


def test_longest_prefix_wins():
    rs = RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR'),
                  Rule('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages', 'Deliverables/Standalone_Models')])
    assert rs.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_x/README.md') == 'Deliverables/Standalone_Models/R129_x/README.md'
    assert rs.map('Thesis_MOSR_Evidence/LabSystem_MOSR/README.md') == 'LabSystem_MOSR/README.md'


def test_segment_boundary():
    rs = RuleSet([Rule('Step', 'Shared_Sources/Real_Sample_Captures/Step'),
                  Rule('20260704_20x', 'Shared_Sources/Real_Sample_Captures/20260704_20x')])
    assert rs.map('Step_analysis_20260623/a.py') is None
    assert rs.map('20260704_20x_5x_analysis/x.csv') is None
    assert rs.map('Step') == 'Shared_Sources/Real_Sample_Captures/Step'
    assert rs.map('Step/134822.bmp') == 'Shared_Sources/Real_Sample_Captures/Step/134822.bmp'


def test_phase4_traing_split():
    rs = load_rules(RULES_DIR / 'moves_phase4.json')
    assert rs.map('Traing_Progress/training_progress_20260410/log.txt') == 'Experiments/Training_Runs/training_progress_20260410/log.txt'
    assert rs.map('Traing_Progress/organized_20260313/round01/a.py') == 'Experiments/Legacy/organized_20260313/round01/a.py'
    assert rs.map('Traing_Progress/README.md') == 'Experiments/Legacy/README.md'
    assert rs.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/x') == 'LabSystem_MOSR/Traing_Progress/x'


def test_glob_into_matches_children_even_unseen():
    rs = load_rules_from_obj({'moves': [{'old': 'A', 'new': 'Analyses/A'},
                                        {'old': 'A/_r61_real_sample_runtime_*', 'into': 'Analyses/A/_r61_real_sample_runtime'}]})
    assert rs.map('A/_r61_real_sample_runtime_001/x.json') == 'Analyses/A/_r61_real_sample_runtime/_r61_real_sample_runtime_001/x.json'
    assert rs.map('A/report.md') == 'Analyses/A/report.md'
    assert rs.map('A/_r61_real_sample_runtime_999') == 'Analyses/A/_r61_real_sample_runtime/_r61_real_sample_runtime_999'


def test_compose_runs_phases_in_order():
    c = compose([RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages', 'Deliverables/Standalone_Models')]),
                 RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')])])
    assert c.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/p/a') == 'Deliverables/Standalone_Models/p/a'
    assert c.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R47/x') == 'LabSystem_MOSR/Experiments/R47/x'
    assert c.map('Model/x.py') is None


def test_moved_roots_lists_rule_sources():
    rs = RuleSet([Rule('Validations', 'Deliverables/Validations'), Rule('AnalysisLab', 'Analyses/AnalysisLab')])
    assert sorted(rs.moved_roots()) == ['AnalysisLab', 'Validations']


def test_phase_rule_files_cover_design_table():
    phase2 = load_rules(RULES_DIR / 'moves_phase2.json')
    phase3 = load_rules(RULES_DIR / 'moves_phase3.json')
    assert phase2.map('Validations/x.json') == 'Deliverables/Validations/x.json'
    assert phase2.map('trial_README.md') == 'Experiments/R128_SourceOnlyFullTraining/trial/trial_README.md'
    assert phase2.map('.history/a.py') == 'Archive/.history/a.py'
    assert phase2.map('Deliverables/MOSR_ONNX/m.onnx') == 'Deliverables/Company_Packages/MOSR_ONNX/m.onnx'
    assert phase3.map('_build153/a.py') == 'Experiments/R153_MeanExternalBenchmark/_build153/a.py'
    assert phase3.map('20260924/134822.bmp') == 'Shared_Sources/PSF_Camera_Acquisitions/20260924/134822.bmp'
    assert phase3.map('20260704_20x_5x_analysis/r.md') == 'Analyses/20260704_20x_5x_analysis/r.md'


def test_splits_under_detects_folders_with_several_destinations():
    rs = load_rules(RULES_DIR / 'moves_phase4.json')
    assert rs.splits_under('Traing_Progress')
    assert not rs.splits_under('Traing_Progress/organized_20260313')
    assert not rs.splits_under('Model')
    rs2 = load_rules(RULES_DIR / 'moves_phase2.json')
    assert rs2.splits_under('Deliverables') and not rs2.splits_under('Validations')
    c = compose([rs2, rs])
    assert c.splits_under('Traing_Progress') and c.splits_under('Thesis_MOSR_Evidence/LabSystem_MOSR')


def test_diverges_only_when_contents_leave_the_folders_new_place():
    p2, p3, p4 = (load_rules(RULES_DIR / f'moves_phase{n}.json') for n in (2, 3, 4))
    assert p3.splits_under('20260702_100MG_displacement_analysis')
    assert not p3.diverges_under('20260702_100MG_displacement_analysis')
    assert p4.diverges_under('Traing_Progress')
    assert p2.splits_under('Deliverables') and not p2.diverges_under('Deliverables')
    assert compose([p2, p3, p4]).diverges_under('Thesis_MOSR_Evidence/LabSystem_MOSR')
    assert not compose([p2, p3, p4]).diverges_under('Model')

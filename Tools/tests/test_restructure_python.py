"""Python path expressions: evaluated in the old tree, rewritten to reach the same (moved) target from the new file."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from restructure_python import rewrite_python
from restructure_resolve import Universe
from restructure_rules import GlobRule, Rule, RuleSet
from restructure_text import Context

PATHS = ['Model/a.py', 'Model/w.pth', 'Model/train.py', 'AnalysisLab/run.py', 'AnalysisLab/helper.py',
         'Traing_Progress/organized_20260313/README.md', 'Traing_Progress/training_progress_x/log.txt',
         'Tools/x.py', 'Validations/a.json', 'Experiments/R61_x/scripts/run.py',
         'Deliverables/R137_PSF100_V42_Select8_20260923/train_v42.py',
         'Deliverables/R137_PSF100_V42_Select8_20260923/Traing_Progress/.keep']
RULES = RuleSet([Rule('AnalysisLab', 'Analyses/AnalysisLab'), Rule('Validations', 'Deliverables/Validations'),
                 Rule('Traing_Progress', 'Experiments/Legacy'),
                 Rule('Deliverables/R137_PSF100_V42_Select8_20260923', 'Deliverables/Standalone_Models/R137_PSF100_V42_Select8_20260923')],
                [GlobRule('Traing_Progress', 'training_progress_*', 'Experiments/Training_Runs')])


@pytest.fixture
def ctx_moves():
    return Context(Universe.from_paths(PATHS), RULES, {}, 'moves')


@pytest.fixture
def ctx_location():
    return Context(Universe.from_paths(PATHS), None, {}, 'location')


def test_parents_level_changes_when_file_moves_deeper(ctx_moves):
    src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nX = ROOT / 'Model' / 'a.py'\n"
    out, edits, _ = rewrite_python(src, 'AnalysisLab/run.py', 'Analyses/AnalysisLab/run.py', ctx_moves)
    assert out == src.replace('parents[1]', 'parents[2]')


def test_parent_of_moved_folder_moves_with_it(ctx_moves):
    src = "from pathlib import Path\nHERE = Path(__file__).parent\nROOT = HERE.parent\nH = HERE / 'helper.py'\n"
    out, _, _ = rewrite_python(src, 'AnalysisLab/run.py', 'Analyses/AnalysisLab/run.py', ctx_moves)
    assert out == "from pathlib import Path\nHERE = Path(__file__).parent\nROOT = HERE.parent.parent\nH = HERE / 'helper.py'\n"


def test_dirname_chain_grows(ctx_moves):
    src = "import os\nROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
    out, _, _ = rewrite_python(src, 'AnalysisLab/run.py', 'Analyses/AnalysisLab/run.py', ctx_moves)
    assert out == "import os\nROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"


def test_segments_split_to_new_prefix(ctx_moves):
    src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nB = ROOT / 'Traing_Progress' / 'organized_20260313'\n"
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_moves)
    assert "B = ROOT / 'Experiments' / 'Legacy' / 'organized_20260313'\n" in out


def test_single_string_segment_stays_single(ctx_moves):
    src = "import os\nROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nV = os.path.join(ROOT, 'Validations/a.json')\n"
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_moves)
    assert "V = os.path.join(ROOT, 'Deliverables/Validations/a.json')\n" in out


def test_dynamic_tail_is_reported(ctx_moves):
    src = "import os\nPROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nP = os.path.join(PROJECT_ROOT, 'Traing_Progress', name)\n"
    out, edits, unresolved = rewrite_python(src, 'Model/train.py', 'Model/train.py', ctx_moves)
    assert out == src and [u.line for u in unresolved] == [3]


def test_folder_with_split_destinations_is_reported(ctx_moves):
    src = "import os\nPROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nT = os.path.join(PROJECT_ROOT, 'Traing_Progress')\n"
    out, _, unresolved = rewrite_python(src, 'Model/train.py', 'Model/train.py', ctx_moves)
    assert out == src and [u.line for u in unresolved] == [3]


def test_package_internal_folder_untouched(ctx_moves):
    src = "from pathlib import Path\nHERE = Path(__file__).parent\nOUT = HERE / 'Traing_Progress'\n"
    old, new = 'Deliverables/R137_PSF100_V42_Select8_20260923/train_v42.py', \
        'Deliverables/Standalone_Models/R137_PSF100_V42_Select8_20260923/train_v42.py'
    out, edits, unresolved = rewrite_python(src, old, new, ctx_moves)
    assert out == src and edits == [] and unresolved == []


def test_plain_string_and_comment_mentions(ctx_moves):
    src = "# results in Validations/a.json\nCFG = {'report': 'Validations/a.json'}\n"
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_moves)
    assert out == "# results in Deliverables/Validations/a.json\nCFG = {'report': 'Deliverables/Validations/a.json'}\n"


def test_fstring_before_split_folder_is_reported(ctx_moves):
    src = "p = f'Traing_Progress/{run}/log.txt'\n"
    out, _, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_moves)
    assert out == src and [u.line for u in unresolved] == [1]


def test_syntax_error_falls_back_to_text_and_is_reported(ctx_moves):
    src = "print 'Validations/a.json'\n"
    out, _, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_moves)
    assert out == "print 'Deliverables/Validations/a.json'\n" and unresolved[0].reason.startswith('syntax')


def test_location_mode_inserts_root(ctx_location):
    src = "import json\nW = r'D:\\GMM_2_Final\\Model\\w.pth'\n"
    out, _, _ = rewrite_python(src, 'Experiments/R61_x/scripts/run.py', 'Experiments/R61_x/scripts/run.py', ctx_location)
    assert out == ("import json\nfrom pathlib import Path\nPROJECT_ROOT = Path(__file__).resolve().parents[3]\n"
                   "W = str(PROJECT_ROOT / 'Model/w.pth')\n")
    compile(out, 'run.py', 'exec')


def test_location_mode_reuses_existing_root(ctx_location):
    src = ("from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
           "W = 'D:/GMM_2_Final/Model/w.pth'\n")
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == src.replace("'D:/GMM_2_Final/Model/w.pth'", "str(ROOT / 'Model/w.pth')")


def test_location_mode_str_root_uses_os_path(ctx_location):
    src = ("import os\nBASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
           "W = 'D:\\\\GMM_2_Final\\\\Model\\\\w.pth'\n")
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert "W = os.path.join(BASE, 'Model/w.pth')\n" in out


def test_location_mode_fstring_and_interpreter(ctx_location):
    src = ("import subprocess\nfrom pathlib import Path\n"
           "p = f'D:\\\\GMM_2_Final\\\\Traing_Progress\\\\{run}'\n"
           "subprocess.run([r'C:\\Users\\Rio\\anaconda3\\python.exe', 'x.py'])\n")
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert "p = f'{PROJECT_ROOT}\\\\Traing_Progress\\\\{run}'\n" in out
    assert "subprocess.run(['python', 'x.py'])\n" in out
    assert "PROJECT_ROOT = Path(__file__).resolve().parents[1]\n" in out


def test_location_mode_comment_and_docstring_become_relative_text(ctx_location):
    src = '"""Reads D:\\GMM_2_Final\\Model\\w.pth."""\n# see D:/GMM_2_Final/Validations/a.json\n'
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == '"""Reads Model/w.pth."""\n# see Validations/a.json\n'


def test_docstrings_and_comments_keep_a_bare_project_root(ctx_location):
    src = '"""Reads from D:/GMM_2_Final and D:/GMM_2_Final/Model/w.pth."""\n# lived in D:\\GMM_2_Final\n'
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == '"""Reads from D:/GMM_2_Final and Model/w.pth."""\n# lived in D:\\GMM_2_Final\n'


def test_location_mode_mid_literal_path_is_reported(ctx_location):
    src = "cmd = 'python D:\\\\GMM_2_Final\\\\Tools\\\\x.py'\n"
    out, _, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == src and [u.line for u in unresolved] == [1]


@pytest.fixture
def ctx_lab_up():
    paths = ['Thesis_MOSR_Evidence/LabSystem_MOSR/scripts/run.py', 'Model/a.py']
    return Context(Universe.from_paths(paths), RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')]), {}, 'moves')


@pytest.mark.parametrize('before,after', [
    ("ROOT = Path(__file__).resolve().parents[3]\n", "ROOT = Path(__file__).resolve().parents[2]\n"),
    ("ROOT = Path(__file__).parent.parent.parent.parent\n", "ROOT = Path(__file__).parent.parent.parent\n"),
    ("ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))\n",
     "ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"),
])
def test_climbs_shrink_when_file_moves_up(ctx_lab_up, before, after):
    head = "import os\nfrom pathlib import Path\n"
    out, _, unresolved = rewrite_python(head + before, 'Thesis_MOSR_Evidence/LabSystem_MOSR/scripts/run.py',
                                        'LabSystem_MOSR/scripts/run.py', ctx_lab_up)
    assert out == head + after and unresolved == []


def test_parsing_legacy_escapes_is_quiet(ctx_moves):
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        rewrite_python('"""D:\\GMM_2_Final\\G"""\n', 'Tools/x.py', 'Tools/x.py', ctx_moves)
    assert [w for w in caught if issubclass(w.category, SyntaxWarning)] == []


@pytest.fixture
def ctx_nested():
    paths = ['A/run.py', 'A/_r61_real_sample_runtime_1/x.json', 'Tools/x.py']
    rules = RuleSet([Rule('A', 'Analyses/A')], [GlobRule('A', '_r61_real_sample_runtime_*', 'Analyses/A/_r61_real_sample_runtime')])
    return Context(Universe.from_paths(paths), rules, {}, 'moves')


def test_fixed_reference_to_nested_split_folder_follows_it(ctx_nested):
    src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nA = ROOT / 'A'\nB = ROOT / 'A' / name\n"
    out, _, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_nested)
    assert "A = ROOT / 'Analyses' / 'A'\n" in out
    assert "B = ROOT / 'A' / name\n" in out and [u.line for u in unresolved] == [4]


@pytest.mark.parametrize('before,after', [
    ("T = Path(__file__).resolve().parents[2]\n", "T = (Path(__file__).resolve().parents[2] / 'Thesis_MOSR_Evidence')\n"),
    ("T = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))\n",
     "T = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Thesis_MOSR_Evidence')\n"),
])
def test_climb_to_former_ancestor_goes_via_common_ancestor(before, after):
    paths = ['Thesis_MOSR_Evidence/LabSystem_MOSR/scripts/run.py', 'Thesis_MOSR_Evidence/Final_Data_Figures/a.png']
    ctx = Context(Universe.from_paths(paths), RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')]), {}, 'moves')
    head = "import os\nfrom pathlib import Path\n"
    out, _, unresolved = rewrite_python(head + before, 'Thesis_MOSR_Evidence/LabSystem_MOSR/scripts/run.py',
                                        'LabSystem_MOSR/scripts/run.py', ctx)
    assert out == head + after and unresolved == []


def test_decisions_keep_or_retarget_ambiguous_expressions():
    ctx = Context(Universe.from_paths(PATHS), RULES, {}, 'moves')
    seg = "os.path.join(PROJECT_ROOT, 'Traing_Progress')"
    src = f"import os\nPROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nT = {seg}\n"
    ctx.decisions = {(seg, 'Traing_Progress'): 'Experiments/Training_Runs'}
    out, _, unresolved = rewrite_python(src, 'Model/train.py', 'Model/train.py', ctx)
    assert "T = os.path.join(PROJECT_ROOT, 'Experiments', 'Training_Runs')\n" in out and unresolved == []
    ctx.decisions = {(seg, 'Traing_Progress'): None}
    out, _, unresolved = rewrite_python(src, 'Model/train.py', 'Model/train.py', ctx)
    assert out == src and unresolved == []
    ctx.decisions = {}
    _, _, unresolved = rewrite_python(src, 'Model/train.py', 'Model/train.py', ctx)
    assert unresolved[0].target == 'Traing_Progress' and unresolved[0].segment == seg


def test_archive_folder_with_project_prefix_is_not_the_project(ctx_location):
    src = "A = r'H:\\GMM_2_Final_Archive\\active_runs'\n"
    out, edits, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == src and edits == [] and unresolved == []


def test_multiline_template_paths_become_relative_text(ctx_location):
    src = "DOC = '''# Report\nSource: D:/GMM_2_Final/Model/w.pth\n'''\n"
    out, _, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == "DOC = '''# Report\nSource: Model/w.pth\n'''\n" and unresolved == []


def test_generated_launcher_template_drops_the_interpreter_path(ctx_location):
    src = "CMD = '@echo off\\r\\n\"C:\\\\Users\\\\Rio\\\\anaconda3\\\\python.exe\" -B run.py\\r\\n'\nDOC = '''Ran with C:/Users/Rio/anaconda3/python.exe\nfrom D:/GMM_2_Final\n'''\n"
    out, _, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert "CMD = '@echo off\\r\\npython -B run.py\\r\\n'\n" in out
    assert "DOC = '''Ran with python\nfrom .\n'''\n" in out and unresolved == []


def test_root_inserted_after_imports_that_follow_a_future_import(ctx_location):
    src = ('from __future__ import annotations\n"""Doc."""\nimport sys\nfrom pathlib import Path\n'
           "W = r'D:\\GMM_2_Final\\Model\\w.pth'\n")
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == ('from __future__ import annotations\n"""Doc."""\nimport sys\nfrom pathlib import Path\n'
                   'PROJECT_ROOT = Path(__file__).resolve().parents[1]\n'
                   "W = str(PROJECT_ROOT / 'Model/w.pth')\n")
    exec(compile(out, 'Tools/x.py', 'exec'), {'__file__': 'D:/x/Tools/x.py', '__name__': 'm'})


def test_path_imported_only_after_the_first_use_is_imported_again(ctx_location):
    src = "W = r'D:\\GMM_2_Final\\Model\\w.pth'\nfrom pathlib import Path\n"
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    exec(compile(out, 'Tools/x.py', 'exec'), {'__file__': 'D:/x/Tools/x.py', '__name__': 'm'})


def test_multiline_fstring_template_paths_become_relative_text(ctx_location):
    src = "DOC = f'''# {name}\nSource: D:/GMM_2_Final/Model/w.pth\n'''\n"
    out, _, unresolved = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_location)
    assert out == "DOC = f'''# {name}\nSource: Model/w.pth\n'''\n" and unresolved == []


def test_a_hint_gives_an_expression_its_path():
    paths = ['Model/auto.py', 'Traing_Progress/organized_20260313/round18/selected/seed.json']
    ctx = Context(Universe.from_paths(paths), RuleSet([Rule('Traing_Progress', 'Experiments/Legacy')]), {}, 'moves',
                  hints={'Model/auto.py': {'train_mod.PROJECT_ROOT': ''}})
    src = ("from pathlib import Path\nimport train_mod\n"
           "M = Path(train_mod.PROJECT_ROOT) / 'Traing_Progress' / 'organized_20260313' / 'round18' / 'selected' / 'seed.json'\n")
    out, _, unresolved = rewrite_python(src, 'Model/auto.py', 'Model/auto.py', ctx)
    assert "M = Path(train_mod.PROJECT_ROOT) / 'Experiments' / 'Legacy' / 'organized_20260313'" in out and unresolved == []


def test_a_decision_can_be_scoped_to_one_file():
    ctx = Context(Universe.from_paths(PATHS), RULES, {}, 'moves')
    seg = "os.path.join(PROJECT_ROOT, 'Traing_Progress')"
    src = f"import os\nPROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nT = {seg}\n"
    ctx.decisions = {('Model/train.py', seg, 'Traing_Progress'): 'Experiments/Training_Runs', (seg, 'Traing_Progress'): None}
    out, _, unresolved = rewrite_python(src, 'Model/train.py', 'Model/train.py', ctx)
    assert "T = os.path.join(PROJECT_ROOT, 'Experiments', 'Training_Runs')\n" in out and unresolved == []
    out, _, unresolved = rewrite_python(src, 'Model/a.py', 'Model/a.py', ctx)
    assert out == src and unresolved == []


def test_a_decision_keeps_a_climb_that_cannot_reach_its_old_target():
    paths = ['Thesis_MOSR_Evidence/LabSystem_MOSR/psf/scripts/run.py', 'Thesis_MOSR_Evidence/a.png']
    ctx = Context(Universe.from_paths(paths), RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')]), {}, 'moves')
    src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nT = ROOT.parents[1].resolve()\n"
    _, _, unresolved = rewrite_python(src, 'Thesis_MOSR_Evidence/LabSystem_MOSR/psf/scripts/run.py', 'LabSystem_MOSR/psf/scripts/run.py', ctx)
    assert unresolved
    ctx.decisions = {('Thesis_MOSR_Evidence/LabSystem_MOSR/psf/scripts/run.py', 'ROOT.parents[1].resolve()', 'Thesis_MOSR_Evidence'): None}
    out, _, unresolved = rewrite_python(src, 'Thesis_MOSR_Evidence/LabSystem_MOSR/psf/scripts/run.py', 'LabSystem_MOSR/psf/scripts/run.py', ctx)
    assert out == src and unresolved == []

"""Values read back out of rewritten data files: the reader must still reach the same place."""
from dataclasses import replace
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from restructure_python import rewrite_python
from restructure_readers import DataView, link, read_targets
from restructure_resolve import Universe
from restructure_text import Context

EXP = 'Experiments/R121_x'
PATHS = [f'{EXP}/config/experiment.json', f'{EXP}/training/base.py', f'{EXP}/data/pkg/manifest.json',
         f'{EXP}/scripts/run.py', 'Shared/out/a.png', 'Shared/out/b.png', 'Model/w.pth']
OLD = {'data': {'package_root': 'D:/GMM_2_Final/Experiments/R121_x/data/pkg', 'seed_name': 'x'},
       'out': 'D:\\GMM_2_Final\\Shared\\out', 'model': 'D:/GMM_2_Final/Model/w.pth',
       'sha256': 'a' * 64,
       'items': [{'path': 'D:/GMM_2_Final/Shared/out/a.png'}, {'path': 'D:/GMM_2_Final/Shared/out/b.png'}],
       'mixed': [{'path': 'D:/GMM_2_Final/Shared/out/a.png'}, {'path': 'local/b.png'}],
       'cmd': 'python D:/GMM_2_Final/Model/x.py --in D:/GMM_2_Final/Shared/out'}
NEW = {'data': {'package_root': 'Experiments/R121_x/data/pkg', 'seed_name': 'x'},
       'out': 'Shared\\out', 'model': 'Model/w.pth', 'sha256': 'b' * 64,
       'items': [{'path': 'Shared/out/a.png'}, {'path': 'Shared/out/b.png'}],
       'mixed': [{'path': 'Shared/out/a.png'}, {'path': 'local/b.png'}],
       'cmd': 'python Model/x.py --in Shared/out'}
CFG = f'{EXP}/config/experiment.json'
FILE = f'{EXP}/training/base.py'
HEAD = "from pathlib import Path\nimport json\nROOT = Path(__file__).resolve().parents[1]\n"
LOAD = "CONFIG = json.loads((ROOT / 'config/experiment.json').read_text())\n"


def view():
    return DataView({CFG: json.dumps(OLD).encode()}, {CFG: json.dumps(NEW).encode()})


@pytest.fixture
def ctx():
    return Context(Universe.from_paths(PATHS), None, {}, 'location', data=view())


def rewrite(src, ctx, name=FILE):
    out, edits, unresolved = rewrite_python(src, name, name, ctx)
    return out, unresolved


def test_data_view_lists_changed_string_leaves():
    v = view()
    changed = v.changed(CFG)
    assert changed[('data', 'package_root')] == ('D:/GMM_2_Final/Experiments/R121_x/data/pkg', 'Experiments/R121_x/data/pkg')
    assert ('data', 'seed_name') not in changed
    assert ('sha256',) not in changed          # a content hash is not a path


def test_join_to_own_folder_becomes_join_to_project_root(ctx):
    src = HEAD + LOAD + "class S:\n    def __init__(self):\n        self.package=ROOT/CONFIG['data']['package_root']\n"
    out, _ = rewrite(src, ctx)
    assert "self.package=PROJECT_ROOT/CONFIG['data']['package_root']\n" in out
    assert "ROOT = Path(__file__).resolve().parents[1]\nPROJECT_ROOT = Path(__file__).resolve().parents[3]\n" not in out
    assert "import json\nPROJECT_ROOT = Path(__file__).resolve().parents[3]\n" in out


def test_direct_path_call_joins_project_root(ctx):
    src = HEAD + LOAD + "OUT = Path(CONFIG['out'])\n"
    out, _ = rewrite(src, ctx)
    assert "OUT = Path(PROJECT_ROOT / CONFIG['out'])\n" in out


def test_string_use_keeps_a_string(ctx):
    src = HEAD + "with open(ROOT / 'config' / 'experiment.json') as f:\n    cfg = json.load(f)\nfh = open(cfg['model'])\n"
    out, _ = rewrite(src, ctx)
    assert "fh = open(str(PROJECT_ROOT / cfg['model']))\n" in out


def test_existing_project_root_name_is_reused(ctx):
    src = HEAD + "REPO = Path(__file__).resolve().parents[3]\n" + LOAD + "M = Path(CONFIG['model'])\n"
    out, _ = rewrite(src, ctx)
    assert "M = Path(REPO / CONFIG['model'])\n" in out
    assert 'PROJECT_ROOT' not in out


def test_value_already_joined_to_project_root_is_left_alone(ctx):
    src = HEAD + "REPO = Path(__file__).resolve().parents[3]\n" + LOAD + "M = REPO / CONFIG['model']\n"
    out, unresolved = rewrite(src, ctx)
    assert out == src and not unresolved


def test_function_returning_the_config_is_followed(ctx):
    src = HEAD + "def load_config():\n    return json.loads((ROOT / 'config/experiment.json').read_text())\n" \
        "def main():\n    cfg = load_config()\n    return Path(cfg['out'])\n"
    out, _ = rewrite(src, ctx)
    assert "return Path(PROJECT_ROOT / cfg['out'])\n" in out


def test_config_passed_to_a_function_is_followed(ctx):
    src = HEAD + LOAD + "def build(cfg):\n    return Path(cfg['data'].get('package_root'))\nbuild(CONFIG)\n"
    out, _ = rewrite(src, ctx)
    assert "return Path(PROJECT_ROOT / cfg['data'].get('package_root'))\n" in out


def test_attribute_on_self_is_followed(ctx):
    src = HEAD + "class T:\n    def __init__(self):\n        self.cfg = json.loads((ROOT / 'config/experiment.json').read_text())\n" \
        "    def out(self):\n        return Path(self.cfg['out'])\n"
    out, _ = rewrite(src, ctx)
    assert "return Path(PROJECT_ROOT / self.cfg['out'])\n" in out


def test_names_in_other_functions_are_separate(ctx):
    src = HEAD + "def a():\n    cfg = json.loads((ROOT / 'config/experiment.json').read_text())\n    return cfg\n" \
        "def b(cfg):\n    return Path(cfg['out'])\n"
    out, unresolved = rewrite(src, ctx)
    assert "return Path(cfg['out'])\n" in out
    assert not [u for u in unresolved if 'out' in u.segment]


def test_loop_over_a_list_of_records(ctx):
    src = HEAD + LOAD + "paths = [Path(r['path']) for r in CONFIG['items']]\nfor r in CONFIG['items']:\n    open(r['path'])\n"
    out, _ = rewrite(src, ctx)
    assert "paths = [Path(PROJECT_ROOT / r['path']) for r in CONFIG['items']]\n" in out
    assert "    open(str(PROJECT_ROOT / r['path']))\n" in out


def test_mixed_list_is_reported_not_rewritten(ctx):
    src = HEAD + LOAD + "for r in CONFIG['mixed']:\n    open(r['path'])\n"
    out, unresolved = rewrite(src, ctx)
    assert "    open(r['path'])\n" in out
    assert any(u.reason.startswith('data value') for u in unresolved)


def test_dynamic_key_is_reported(ctx):
    src = HEAD + LOAD + "for k in ('out', 'model'):\n    open(CONFIG[k])\n"
    out, unresolved = rewrite(src, ctx)
    assert "open(CONFIG[k])" in out
    assert any(u.reason.startswith('data value') and 'dynamic key' in u.reason for u in unresolved)


def test_command_line_value_is_reported(ctx):
    src = HEAD + LOAD + "import subprocess\nsubprocess.run(CONFIG['cmd'], shell=True)\n"
    out, unresolved = rewrite(src, ctx)
    assert "subprocess.run(CONFIG['cmd'], shell=True)" in out
    assert any(u.reason.startswith('data value') for u in unresolved)


def test_written_out_is_not_reported(ctx):
    src = HEAD + LOAD + "print(json.dumps(CONFIG, indent=1))\n"
    out, unresolved = rewrite(src, ctx)
    assert out == src and not unresolved


def test_read_targets_agree_before_and_after(ctx):
    src = HEAD + LOAD + "class S:\n    def __init__(self):\n        self.package=ROOT/CONFIG['data']['package_root']\n" \
        "OUT = Path(CONFIG['out'])\nfor r in CONFIG['items']:\n    open(r['path'])\n"
    out, _ = rewrite(src, ctx)
    before = read_targets(src, FILE, ctx)
    after_unfixed = read_targets(src, FILE, replace(ctx, data_side='new'))
    after = read_targets(out, FILE, replace(ctx, data_side='new'))
    assert sorted(before) == sorted(after)
    assert sorted(before) != sorted(after_unfixed)
    assert (CFG, ('data', 'package_root'), f'{EXP}/data/pkg') in before


def test_dict_keyword_wraps_the_value_under_its_key(ctx):
    src = HEAD + LOAD + "protocol = dict(checkpoint=CONFIG['data'], n=1)\nshown = {k: v for k, v in protocol.items()}\n" \
        "P = Path(protocol['checkpoint']['package_root'])\n"
    out, unresolved = rewrite(src, ctx)
    assert "P = Path(PROJECT_ROOT / protocol['checkpoint']['package_root'])\n" in out
    assert not [u for u in unresolved if 'no longer reach' in u.reason]


def test_recursive_walk_over_everything_is_not_a_read(ctx):
    src = HEAD + LOAD + "def walk(x):\n    if isinstance(x, dict):\n        for y in x.values():\n            walk(y)\nwalk(CONFIG)\n"
    out, unresolved = rewrite(src, ctx)
    assert out == src
    assert not [u for u in unresolved if 'no longer reach' in u.reason]


def test_comprehensions_are_scopes_of_their_own(ctx):
    src = HEAD + LOAD + "a = [x + 1 for x in range(3)]\npaths = [Path(x['path']) for x in CONFIG['items']]\n"
    out, unresolved = rewrite(src, ctx)
    assert "paths = [Path(PROJECT_ROOT / x['path']) for x in CONFIG['items']]\n" in out
    assert not unresolved


def test_a_loop_variable_used_again_later(ctx):
    src = HEAD + LOAD + "for rec in CONFIG['items']:\n    open(rec['path'])\nrec = {'path': 'local'}\nprint(rec['path'])\n"
    out, unresolved = rewrite(src, ctx)
    assert "    open(str(PROJECT_ROOT / rec['path']))\n" in out
    assert "print(rec['path'])\n" in out and not unresolved


def test_string_put_into_a_dict_literal_is_fixed_where_it_goes_in(ctx):
    src = HEAD + LOAD + "src = {'model': CONFIG['model'], 'n': 2}\nM = Path(src['model'])\n"
    out, _ = rewrite(src, ctx)
    assert "src = {'model': str(PROJECT_ROOT / CONFIG['model']), 'n': 2}\nM = Path(src['model'])\n" in out


def test_object_put_into_a_dict_literal_is_followed(ctx):
    src = HEAD + LOAD + "src = {'d': CONFIG['data'], 'n': 2}\nM = Path(src['d']['package_root'])\n"
    out, _ = rewrite(src, ctx)
    assert "M = Path(PROJECT_ROOT / src['d']['package_root'])\n" in out


def test_string_passed_to_a_shared_helper_is_fixed_at_the_call(ctx):
    src = HEAD + LOAD + "def sha(p):\n    return open(p, 'rb').read()\nsha(CONFIG['model'])\nsha('local.bin')\n"
    out, unresolved = rewrite(src, ctx)
    assert "sha(str(PROJECT_ROOT / CONFIG['model']))\n" in out
    assert "    return open(p, 'rb').read()\n" in out and not unresolved


def test_values_appended_to_a_list(ctx):
    src = HEAD + LOAD + "rows = []\nfor r in CONFIG['items']:\n    rows.append(r)\nfor r in rows:\n    open(r['path'])\n"
    out, _ = rewrite(src, ctx)
    assert "    open(str(PROJECT_ROOT / r['path']))\n" in out


MAIN = f'{EXP}/scripts/run.py'
COMMON = f'{EXP}/scripts/common.py'


def linked(ctx, sources):
    ctx = replace(ctx, uni=Universe.from_paths(PATHS + [COMMON]))
    ctx.seeds = link(sources, ctx)
    return ctx


def test_value_passed_to_a_function_of_another_module(ctx):
    common = "from pathlib import Path\ndef check(cfg):\n    return [Path(s['path']) for s in cfg['items']]\n"
    main = "from pathlib import Path\nimport json\nfrom common import check\nROOT = Path(__file__).resolve().parents[1]\n" + LOAD + "check(CONFIG)\n"
    ctx = linked(ctx, {MAIN: main, COMMON: common})
    out, _ = rewrite(common, ctx, COMMON)
    assert "return [Path(PROJECT_ROOT / s['path']) for s in cfg['items']]\n" in out
    _, unresolved = rewrite(main, ctx, MAIN)
    assert not unresolved


def test_config_imported_from_another_module(ctx):
    main = "from pathlib import Path\nimport sys\nsys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'training'))\n" \
           "from base import CONFIG\nOUT = Path(CONFIG['out'])\n"
    base = HEAD + LOAD
    ctx = linked(ctx, {MAIN: main, FILE: base})
    out, _ = rewrite(main, ctx, MAIN)
    assert "OUT = Path(PROJECT_ROOT / CONFIG['out'])\n" in out


def test_loader_function_imported_from_another_module(ctx):
    common = HEAD + "def load_config():\n    return json.loads((ROOT / 'config/experiment.json').read_text())\n"
    main = "from pathlib import Path\nfrom common import load_config\ncfg = load_config()\nM = Path(cfg['model'])\n"
    ctx = linked(ctx, {MAIN: main, COMMON: common.replace('parents[1]', 'parents[1]')})
    out, _ = rewrite(main, ctx, MAIN)
    assert "M = Path(PROJECT_ROOT / cfg['model'])\n" in out

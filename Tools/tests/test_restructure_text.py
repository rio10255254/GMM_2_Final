"""Non-Python text rewriting: links and path mentions follow the move, bytes around them stay as they were."""
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from restructure_resolve import Universe
from restructure_rules import Rule, RuleSet
from restructure_text import Context, rewrite_bytes

PATHS = ['Traing_Progress/organized_20260313/README.md', 'Traing_Progress/organized_20260313/a.csv',
         'Validations/a.json', 'Model/a.pth', 'Shared_Sources/a.bmp', 'docs/x.md', 'Tools/x.py',
         'AnalysisLab/run.m', 'AnalysisLab/notes.md', 'Model/README.md']
RULES = RuleSet([Rule('Traing_Progress/organized_20260313', 'Experiments/Legacy/organized_20260313'),
                 Rule('Validations', 'Deliverables/Validations'), Rule('AnalysisLab', 'Analyses/AnalysisLab')])


@pytest.fixture
def ctx_moves():
    return Context(Universe.from_paths(PATHS), RULES, {}, 'moves')


@pytest.fixture
def ctx_location():
    return Context(Universe.from_paths(PATHS + ['Analyses_dir/sub/run.m', 'Tools/run.ps1']), None, {}, 'location')


def test_markdown_link_rewritten_narrative_kept(ctx_moves):
    src = '原名 `Traing_Progress`（歷史拼字）。見 [批次](../Traing_Progress/organized_20260313/README.md)。\n'.encode()
    out, edits, _ = rewrite_bytes(src, 'docs/x.md', 'docs/x.md', ctx_moves)
    assert out.decode() == '原名 `Traing_Progress`（歷史拼字）。見 [批次](../Experiments/Legacy/organized_20260313/README.md)。\n'
    assert len(edits) == 1


def test_path_mention_after_cjk_text(ctx_moves):
    out, _, _ = rewrite_bytes('結果見Validations/a.json與說明\n'.encode(), 'docs/x.md', 'docs/x.md', ctx_moves)
    assert out.decode() == '結果見Deliverables/Validations/a.json與說明\n'


def test_moved_file_relative_links_recomputed(ctx_moves):
    src = b'[m](../Model/README.md) and [self](run.m)\n'
    out, _, _ = rewrite_bytes(src, 'AnalysisLab/notes.md', 'Analyses/AnalysisLab/notes.md', ctx_moves)
    assert out == b'[m](../../Model/README.md) and [self](run.m)\n'


def test_github_main_links_follow_but_pinned_refs_stay(ctx_moves):
    src = (b'https://github.com/rio10255254/GMM_2_Final/blob/main/Validations/a.json\n'
           b'https://github.com/rio10255254/GMM_2_Final/tree/pre-restructure-20261028/Validations\n')
    out, _, _ = rewrite_bytes(src, 'docs/x.md', 'docs/x.md', ctx_moves)
    assert out == (b'https://github.com/rio10255254/GMM_2_Final/blob/main/Deliverables/Validations/a.json\n'
                   b'https://github.com/rio10255254/GMM_2_Final/tree/pre-restructure-20261028/Validations\n')


def test_unmapped_absolute_path_is_not_rewritten_inside(ctx_moves):
    src = b'{"p": "E:\\\\Old\\\\Validations\\\\a.json"}'
    out, edits, _ = rewrite_bytes(src, 'Tools/r.json', 'Tools/r.json', ctx_moves)
    assert out == src and edits == []


def test_crlf_and_bom_preserved(ctx_moves):
    src = b'\xef\xbb\xbfpath: Traing_Progress/organized_20260313/a.csv\r\nother\r\n'
    out, _, _ = rewrite_bytes(src, 'x.yaml', 'x.yaml', ctx_moves)
    assert out == b'\xef\xbb\xbfpath: Experiments/Legacy/organized_20260313/a.csv\r\nother\r\n'


def test_undecodable_reported_not_touched(ctx_moves):
    src = b'\xff\xfeT\x00r\x00'
    out, edits, problems = rewrite_bytes(src, 'a.txt', 'a.txt', ctx_moves)
    assert out == src and edits == [] and problems


def test_json_gz_roundtrip(ctx_moves):
    data = gzip.compress(json.dumps({'files': [{'path': 'Validations/a.json'}]}).encode(), compresslevel=9)
    out, _, _ = rewrite_bytes(data, 'docs/r/X.json.gz', 'docs/r/X.json.gz', ctx_moves)
    assert json.loads(gzip.decompress(out)) == {'files': [{'path': 'Deliverables/Validations/a.json'}]}


def test_unchanged_file_returns_identical_bytes(ctx_moves):
    data = gzip.compress(b'{"files": [{"path": "Model/a.pth"}]}', mtime=123)
    out, edits, _ = rewrite_bytes(data, 'docs/r/X.json.gz', 'docs/r/X.json.gz', ctx_moves)
    assert out == data and edits == []


def test_location_mode_matlab(ctx_location):
    src = "img = imread('D:\\GMM_2_Final\\Shared_Sources\\a.bmp');\n".encode()
    out, _, _ = rewrite_bytes(src, 'Analyses_dir/sub/run.m', 'Analyses_dir/sub/run.m', ctx_location)
    assert "imread(fullfile(PROJECT_ROOT, 'Shared_Sources/a.bmp'))" in out.decode()
    assert out.decode().startswith("PROJECT_ROOT = fileparts(fileparts(fileparts(mfilename('fullpath'))));\n")


def test_location_mode_matlab_segmented_fullfile(ctx_location):
    src = "p = fullfile('D:', 'GMM_2_Final', 'Model', 'a.pth');\n".encode()
    out, _, _ = rewrite_bytes(src, 'Tools/run.m', 'Tools/run.m', ctx_location)
    assert "p = fullfile(PROJECT_ROOT, 'Model', 'a.pth');" in out.decode()
    assert "PROJECT_ROOT = fileparts(fileparts(mfilename('fullpath')));" in out.decode()


def test_location_mode_powershell(ctx_location):
    src = b"param([string]$x)\r\n$a = 'D:\\GMM_2_Final\\Model\\a.pth'\r\n$b = \"D:\\GMM_2_Final\\Model\\$x\"\r\n"
    out, _, _ = rewrite_bytes(src, 'Tools/run.ps1', 'Tools/run.ps1', ctx_location)
    text = out.decode()
    assert "$a = (Join-Path $ProjectRoot 'Model\\a.pth')\r\n" in text
    assert '$b = "$ProjectRoot\\Model\\$x"\r\n' in text
    assert "param([string]$x)\r\n$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path\r\n" in text


def test_location_mode_record_and_interpreter(ctx_location):
    out, _, _ = rewrite_bytes(b'{"model": "D:\\\\GMM_2_Final\\\\Model\\\\a.pth"}', 'r.json', 'r.json', ctx_location)
    assert json.loads(out) == {'model': 'Model/a.pth'}
    out, _, _ = rewrite_bytes(b'& C:\\Users\\Rio\\anaconda3\\python.exe Tools\\x.py\r\n', 'Tools/run.ps1', 'Tools/run.ps1', ctx_location)
    assert out == b'& python Tools\\x.py\r\n'


def test_location_mode_notebook_paths_relative_to_notebook(ctx_location):
    nb = {'cells': [{'cell_type': 'code', 'source': ["w = r'D:\\GMM_2_Final\\Model\\a.pth'\n"]}]}
    data = json.dumps(nb, indent=1).encode()
    out, _, _ = rewrite_bytes(data, 'docs/nb/a.ipynb', 'docs/nb/a.ipynb', ctx_location)
    assert json.loads(out)['cells'][0]['source'] == ["w = r'../../Model/a.pth'\n"]


def test_large_record_is_linear(ctx_moves):
    import time
    rows = ''.join(f'{{"path": "Validations/a.json", "n": {i}}},\n' for i in range(40000))
    t0 = time.perf_counter()
    out, edits, _ = rewrite_bytes(('[' + rows + '{}]').encode(), 'docs/r.json', 'docs/r.json', ctx_moves)
    assert len(edits) == 40000 and time.perf_counter() - t0 < 5

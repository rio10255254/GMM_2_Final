"""Phase 1 hand fixes for readers of rewritten data values the tool does not rewrite itself:
MATLAB and PowerShell readers, and one recorded command line replayed by R128.
Run after `apply --phase 1`, then `rehash --phase 1`. Every replacement must match exactly."""
import posixpath
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]    # the project root
V42 = 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/scripts'
DRAFT = 'docs/reproducibility/project_completion/curated/draft_cleanup_20261022/editor_sources'
CH62 = [(r"fullfile(sequence.raw_dir,", r"fullfile(PROJECT_ROOT,sequence.raw_dir,"),
        (r"fullfile(sequence.v42_dir,", r"fullfile(PROJECT_ROOT,sequence.v42_dir,")]
FIXES = {
    # R128 replays R61 with the command plan.json recorded; its paths are project-relative now
    'Experiments/R128_SourceOnlyFullTraining/analysis/lsc_comparison/check_r61.py':
        [('stderr=subprocess.STDOUT,env=env,cwd=ROOT)', 'stderr=subprocess.STDOUT,env=env,cwd=REPO)')],
    # R135 runs R61's recorded command line in-process; path arguments it does not replace (--psf-fitted-path)
    # are project-relative now: join them to the root (an absolute one stays as it is)
    'Experiments/R135_UnifiedModelComparison/scripts/adapters.py':
        [("args=info['command'][1:].copy()",
          "args=[a if a.startswith('-') or not ('/' in a or '\\\\' in a) else str(PROJECT_ROOT / a) for a in info['command'][1:]]")],
    'Experiments/R135_UnifiedModelComparison/scripts/adapters_v2.py':
        [("args=info['command'][1:].copy()",
          "args=[a if a.startswith('-') or not ('/' in a or '\\\\' in a) else str(PROJECT_ROOT / a) for a in info['command'][1:]]")],
    'Experiments/R72_R61SyntheticDefectACMContourValidation/scripts/run_acm_extraction.m':
        [('    char(cfg.sources.raw_dir), ...', '    fullfile(PROJECT_ROOT, char(cfg.sources.raw_dir)), ...'),
         ('    char(cfg.sources.combo_dir), ...', '    fullfile(PROJECT_ROOT, char(cfg.sources.combo_dir)), ...'),
         ('    char(cfg.sources.r61_dir) ...', '    fullfile(PROJECT_ROOT, char(cfg.sources.r61_dir)) ...'),
         ('truth_dir = char(cfg.sources.truth_dir);', 'truth_dir = fullfile(PROJECT_ROOT, char(cfg.sources.truth_dir));')],
    'Experiments/R73_R61ExpandedSyntheticACMGeneralization/scripts/pilot_acm_iterations.m':
        [('data_root = char(cfg.dataset.root);', 'data_root = fullfile(PROJECT_ROOT, char(cfg.dataset.root));')],
    'Experiments/R73_R61ExpandedSyntheticACMGeneralization/scripts/run_acm_extraction.m':
        [('data_root = char(cfg.dataset.root);', 'data_root = fullfile(PROJECT_ROOT, char(cfg.dataset.root));')],
    'Experiments/R74_R61HardMicroscopyACMGeneralization/scripts/calibrate_raw_difficulty.m':
        [('data_root = char(cfg.dataset.root);', 'data_root = fullfile(PROJECT_ROOT, char(cfg.dataset.root));')],
    'Experiments/R80_R79E23vsE100GeneralizationValidation/scripts/run_acm_multimethod.m':
        [('data_root = char(cfg.dataset.root);', 'data_root = fullfile(PROJECT_ROOT, char(cfg.dataset.root));')],
    'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts/run_acm_multimethod.m':
        [('data_root = char(cfg.dataset.root);', 'data_root = fullfile(PROJECT_ROOT, char(cfg.dataset.root));')],
    'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts/run_sem_acm_multimethod.m':
        [('raw_dir = char(cfg.sem_acm.raw_input_dir);', 'raw_dir = fullfile(PROJECT_ROOT, char(cfg.sem_acm.raw_input_dir));')],
    'Experiments/R83_R79SevereMicroscopyStrengthening/scripts/run_sem_acm_selected_pillars.m':
        [('raw_dir = char(cfg.sem_acm.raw_input_dir);', 'raw_dir = fullfile(PROJECT_ROOT, char(cfg.sem_acm.raw_input_dir));')],
    f'{V42}/build_wiener_baseline_dataset.m':
        [("imagePath = fullfile(sequence.raw_dir, sprintf(", "imagePath = fullfile(PROJECT_ROOT, sequence.raw_dir, sprintf(")],
    f'{V42}/build_wiener_three_way_chapter62_figures.m': CH62,
    f'{DRAFT}/.codex_docx_work/build_wiener_three_way_chapter62_figures_zh.m': CH62,
    f'{DRAFT}/.codex_docx_work/v18/scripts/build_wiener_three_way_chapter62_figures_clean.m': CH62,
    f'{DRAFT}/.codex_tmp/oral_defense_english_20260727/matlab/build_english_wiener_figures.m': CH62,
    f'{DRAFT}/.codex_work/matlab_ch6_revision/build_wiener_three_way_chapter62_figures.m': CH62,
    f'{DRAFT}/.codex_work/matlab_mosr/build_wiener_three_way_chapter62_figures.m': CH62,
    # the monitor reads latest.json, which a running training writes with absolute paths: Combine keeps both
    'Experiments/R148v2_HybridContextNativePSF/scripts/monitor_training.ps1':
        [('(Test-Path -LiteralPath $Latest.path)', '(Test-Path -LiteralPath ([System.IO.Path]::Combine($ProjectRoot, $Latest.path)))')],
    'Thesis_MOSR_Evidence/Research_Design_Effect_Review_20260926/04_Current_Optimization/R148v2_HybridContextNativePSF/architecture/scripts/monitor_training.ps1':
        [('(Test-Path -LiteralPath $Latest.path)', '(Test-Path -LiteralPath ([System.IO.Path]::Combine($ProjectRoot, $Latest.path)))')],
}


def depth(rel):
    d = posixpath.dirname(rel)
    return len(d.split('/')) if d else 0


def matlab_root(text, rel):
    """Define PROJECT_ROOT in every part that uses it and lacks it, as the phase 1 MATLAB pass does:
    the script part and each function (local functions have workspaces of their own)."""
    expr = "mfilename('fullpath')"
    for _ in range(depth(rel) + 1):
        expr = f'fileparts({expr})'
    nl = '\r\n' if '\r\n' in text else '\n'
    funcs = list(re.finditer(r'^[ \t]*function\b[^\n]*\n', text, re.M))
    first = re.search(r'^[ \t]*[^%\s]', text, re.M)
    script = not (funcs and first and funcs[0].start() == first.start())
    parts = [(0, funcs[0].start() if funcs else len(text), 0, '')] if script else []
    for i, m in enumerate(funcs):
        parts.append((m.end(), funcs[i + 1].start() if i + 1 < len(funcs) else len(text), m.end(), '    '))
    inserts = []
    for start, end, pos, indent in parts:
        body = text[start:end]
        used = re.search(r'PROJECT_ROOT', re.sub(r'^\s*PROJECT_ROOT\s*=.*$', '', body, flags=re.M))
        if used and not re.search(r'^\s*PROJECT_ROOT\s*=', body, re.M):
            inserts.append((pos, f'{indent}PROJECT_ROOT = {expr};{nl}'))
    for pos, line in sorted(inserts, reverse=True):
        text = text[:pos] + line + text[pos:]
    return text


def ps_root(text, rel):
    if re.search(r'^\s*\$ProjectRoot\s*=', text, re.M | re.I):
        return text
    nl = '\r\n' if '\r\n' in text else '\n'
    d = depth(rel)
    line = '$ProjectRoot = $PSScriptRoot' if d == 0 else \
        f"$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '{chr(92).join(['..'] * d)}')).Path"
    m = re.search(r'^\s*param\s*\(', text, re.I | re.M)
    pos = 0
    if m:
        level, i = 0, m.end() - 1
        while i < len(text):
            level += text[i] == '('
            level -= text[i] == ')'
            if level == 0:
                nxt = text.find('\n', i)
                pos = len(text) if nxt < 0 else nxt + 1
                break
            i += 1
    return text[:pos] + line + nl + text[pos:]


for rel, pairs in FIXES.items():
    p = REPO / rel
    raw = p.read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw[3:].decode('utf-8') if bom else raw.decode('utf-8')
    for old, new in pairs:
        n = text.count(old)
        assert n >= 1, (rel, old)
        text = text.replace(old, new)
    if rel.endswith('.m'):
        text = matlab_root(text, rel)
    elif rel.endswith('.ps1'):
        text = ps_root(text, rel)
    p.write_bytes((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))
    print('fixed', rel)

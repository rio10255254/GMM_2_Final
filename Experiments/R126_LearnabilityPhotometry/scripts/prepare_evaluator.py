"""Derive a separately retained evaluator; archived readout calculations unchanged."""
from common import *

def main():
    src=R125/'scripts/evaluate_real_pilot_v2.py';text=src.read_text(encoding='utf-8')
    # Only round output paths and the declared2x2 final128 comparison change.
    replacements=[
        ('EXPS = ROOT.parent','EXPS = ROOT.parent\nR125 = EXPS / "R125_DataAlignedPilot"'),
        ('PROFILE = ROOT / "config"','PROFILE = R125 / "config"'),
        ('PREVIOUS_PANEL = ROOT / "results"','PREVIOUS_PANEL = R125 / "results"'),
        ('PANEL = ROOT / "results"','PANEL = R125 / "results"'),
        ('str(ROOT)', 'str(R125)'),
        ('ROOT / "prototype"','R125 / "prototype"'),
        ('inside R125/results/real_*','inside R126/results/real_*'),
        ('len(evaluations) != 12 or len(combinations) != 6 or {arm for arm, _ in combinations} != {"A", "B", "C"}', 'len(evaluations) != 8 or len(combinations) != 4 or {arm for arm, _ in combinations} != {"P", "Q"}'),
        ('all three arms, two seeds, each initial and step64 separately (12 evaluations)', 'both photometry arms, two seeds, each initial and step128 separately (8 evaluations)'),
        ('{0, 64}', '{0, 128}'),('seed, 64]', 'seed, 128]'),
        ('step64','step128'),('all12','all8'),
        ('colors = {"A": "#32638a", "B": "#d98b27", "C": "#6b8b3d"}', 'colors = {"P": "#32638a", "Q": "#d98b27"}'),
        ('[0, 64], ["Initial", "64 updates"]','[0, 128], ["Initial", "128 updates"]'),
        ('R125 bounded exploratory pilot','R126 matched photometry pilot'),
    ]
    applied=[]
    for old,new in replacements:
        count=text.count(old)
        if not count:raise ValueError(f'Expected adaptation absent: {old}')
        text=text.replace(old,new);applied.append(dict(old=old,new=new,count=count))
    # Prevent accidentally creating a new panel in the immutable source round.
    text=text.replace('    if args.freeze_panel:\n        freeze_panel()', '    if args.freeze_panel:\n        raise ValueError("R126 reuses the existing R125 frozen panel; cannot regenerate it")')
    target=ROOT/'scripts/evaluate_real.py'
    with target.open('x',encoding='utf-8') as f:f.write(text)
    save(ROOT/'config/evaluator_adaptation.json',dict(source_path=str(src),source_sha256=sha(src),adapted_path=str(target),adapted_sha256=sha(target),replacements=applied,archived_sem_and_phase_calculation_functions_changed=False,panel= str(R125/'results/real_panel_v2/frozen_panel.json')))

if __name__=='__main__':main()

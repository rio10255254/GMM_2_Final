"""Verify this review's references and selected arithmetic, never old verdicts."""
from pathlib import Path
import csv
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
EXP=HERE.parents[2]
REPORT=EXP/'R130_CleanV42Comparison/reports/R61_R130_DESIGN_REVIEW.md'

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

text=REPORT.read_text(encoding='utf-8')
ledger=rows(HERE/'reading_ledger.csv')
changed=[]
for row in ledger:
    p=Path(row['path'])
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
        changed.append(str(p))
links=[]
for target in re.findall(r'\]\(([^\n)]+)\)',text):
    if target.startswith(('http:','https:')): continue
    p=(REPORT.parent/target).resolve()
    links.append({'target':target,'exists':p.exists()})
comparison=rows(EXP/'R130_CleanV42Comparison/results/comparison.csv')
numeric=[]
for row in comparison:
    for key in ('diameter_error_nm','centered_shape_nm','step_sd_nm','within_grid_nm','forward_seconds'):
        expected=f'{float(row[key]):.4f}'
        numeric.append({'model':row['model'],'metric':key,'expected':expected,'in_report':expected in text})
motion=rows(EXP/'R129_OpticalPriorHybrid/results/continuous_lsc/comparison_summary.csv')
aggregate=[r for r in motion if r['scope']=='all_four_sequences' and r['population']=='locked120']
checks=[]
for a in aggregate:
    parts=[r for r in motion if r['scope']=='per_sequence' and r['population']=='locked120' and r['method']==a['method']]
    if not parts: continue
    derived=sum(float(r['step_sd_nm']) for r in parts)/len(parts)
    checks.append({'method':a['method'],'n_sequences':len(parts),'n_pairs':sum(int(r['n_pairs']) for r in parts),
                   'mean_step_sd_nm':derived,'saved_step_sd_nm':float(a['step_sd_nm']),
                   'agreement':abs(derived-float(a['step_sd_nm']))<1e-10})
result={'kind':'review_validation_only','protected_scope':'592 catalogued source files captured before report drafting; not a whole-project or before-turn claim',
        'unchanged_source_count':len(ledger)-len(changed),'changed_sources':changed,
        'links_checked':len(links),'missing_links':[r for r in links if not r['exists']],
        'rounded_source_table_checks':numeric,'motion_aggregate_checks':checks,
        'runtime_ratio_r129_over_v42':float(comparison[0]['forward_seconds'])/float(comparison[1]['forward_seconds']),
        'limitations':['No training or historical imaging experiment rerun.',
                      'Arithmetic agreement does not certify SEM scale or true stage motion.',
                      'Reading scope is manually declared; inventory/hashes do not prove comprehension.']}
assert not changed,changed
assert not result['missing_links'],result['missing_links']
assert all(x['in_report'] for x in numeric)
assert checks and all(x['agreement'] and x['n_sequences']==4 and x['n_pairs']==120 for x in checks)
(HERE/'review_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'source_files_unchanged':len(ledger),'links':len(links),'table_values_checked':len(numeric),'motion_summaries_recomputed':len(checks),'result':'pass'},ensure_ascii=False))

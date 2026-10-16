"""Inventory and reading scope for a document review, not experiment certification."""
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess

ROOT = Path(r'D:\GMM_2_Final\Experiments')
OUT = Path(__file__).resolve().parent
REPORT = ROOT / 'R130_CleanV42Comparison/reports/R61_R130_DESIGN_REVIEW.md'

# Full report bodies actually displayed and read in this review. Repeated generic
# README names are restricted by round below. Inventory alone never counts as read.
FULL_NAMES = set('''R63_RESULTS.md R67_RESULTS.md R68_RESULTS.md R69_RESULTS_TW.md
R70_RESULTS_TW.md R71_RESULTS_TW.md R72_RESULTS_TW.md R73_RESULTS_TW.md R74_RESULTS_TW.md
R75_DESIGN.md R75V2_DESIGN.md COMPLETED_TRAINING_ANALYSIS_TW.md R76_FINAL_SYNTHESIS_TW.md
R77_RESULTS_TW.md R78_RESULTS_TW.md R75V3_DESIGN.md R80_RESULTS_TW.md R81_RESULTS.md
R82_RESULTS_TW.md R83_RESULTS.md R79_ROOT_REPAIR_CLOSEOUT.md R84_FINAL_VERDICT.md
R87_RESULTS.md R88_PROBLEM_LEDGER.md R88_EXPERIMENT_DESIGN.md R88_ABORTED_AT_E87.md
R89_PREFLIGHT_SUMMARY.md R89_FINAL_VALIDATION_TW.md R89_STAGE_WEIGHT_FINDINGS_TW.md
root_cause_matrix.md R98_RESULTS.md R98_METHODOLOGY.md EXPERIMENT_RESULTS.md
R105A_FINAL_FINDINGS_ZH.md R105B_FINAL_FINDINGS_ZH.md R105C_PAIR_AUDIT_ZH.md
R106A_FINAL_FINDINGS_ZH.md R108A_RESULTS_ZH.md R108B_RESULTS_ZH.md
R108C_TO_R109_DECISION_CHAIN_ZH.md R109_FINAL_SELECTION_ZH.md R110_RESULTS_ZH.md
MODEL_IMPROVEMENT_DESIGN.md R113_FINDINGS_ZH.md MEASUREMENT_QA_FINDINGS.md
DEEP_AUDIT_FINDINGS_ZH.md R114_EXECUTION_LEDGER_ZH.md R115_DESIGN_AND_PROBE_ZH.md
R116_ARCHITECTURE_DECISION_ZH.md REPAIR_MAP.md R119_CAUSAL_AUDIT.md
R121_RESULTS.md R122_RESULTS.md R123_DESIGN.md R123_DATA_AND_VALIDATION.md
R124_RESULTS.md R125_RESULTS.md R126_RESULTS.md R127_RESULTS.md R128_RESULTS.md
R128_METHODOLOGY.md R128_APPLICATION_SCOPE.md R128_STRUCTURE_CHECK.md
R129_ARCHITECTURE.md R129_RESULTS.md R129_LONG_TRAINING_RESULTS.md
R129_CONTINUOUS_LSC_RESULTS.md R130_DESIGN.md R130_RESULTS.md
R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md R128_LSC_R61_COMPARISON.md
R129_STANDALONE_TRAINING.md
DISPLACEMENT_LSC_READOUT_TW.md SEM36_READOUT_TW.md STATIC_CENTER9_READOUT_TW.md
BOUNDARY_GATE_SUMMARY.md'''.split())
README_PREFIXES = {'R61_', 'R85_', 'R86_', 'R90_', 'R91_', 'R92_', 'R93_', 'R94_',
                   'R95_', 'R96_Localized', 'R99_', 'R100_Causal', 'R102_', 'R103_',
                   'R104_', 'R107A_', 'R108C_', 'R108D_', 'R108E_', 'R108F_',
                   'R108G_', 'R111_', 'R117_', 'R120_'}
# R117 README was only catalogued, not read; keep it unreviewed.
README_PREFIXES.discard('R117_')
EXTRA = {
 'R61_STEP_Generalization_20260623/runs/R61_stepguard_v16_dpv96_matched_20260623/diverse_phantom_validation_20260623_220416/BOUNDARY_GATE_SUMMARY.md': 'full',
 'R89_MeasurementNativeScratch/reports/final_validation/R89_FINAL_VALIDATION_TW.md': 'full',
 'R89_MeasurementNativeScratch/reports/final_validation/stage_weight_analysis/R89_STAGE_WEIGHT_FINDINGS_TW.md': 'full',
 'R113_CausalStructureDissection/deep_audit/DEEP_AUDIT_FINDINGS_ZH.md': 'full',
 **{f'R80_InflectionReferenceCircleSEMValidation/results/{name}.md': 'full' for name in ('DISPLACEMENT_LSC_READOUT_TW','SEM36_READOUT_TW','STATIC_CENTER9_READOUT_TW')},
 'R61_STEP_Generalization_20260623/R61_RUN_INDEX.csv': 'full',
 'R64_IsocontourDisplacementReanalysis_20260724/run_isocontour_reanalysis.py': 'lines 1-85; purpose and output locations',
 'R64_IsocontourDisplacementReanalysis_20260724/improvement_final_stdout.log': 'full',
 'R65_V19_OldMethodFigurePackage_20260724/v19_build_audit.json': 'full',
 'R66_V20_TraceabilityFigures_20260725/figure_manifest.csv': 'full',
 'R91_DetailDecoupledScratch/results/capability_diagnosis_20260811/capability_summary.json': 'findings and r92_decision fields',
 'R95_CounterfactualGateRepairScratch/reports/model_internal_analysis_epoch40/verified_summary.json': 'field inventory only',
 'R96_LocalizedEvidenceProtectedScratch/results/deep_diagnosis/internal_causes.json': 'capacity_recommendation and field inventory',
 'R97_DirectCausalPhaseScratch/results/posttraining_validation/synthesis/summary.json': 'fixed_endpoint, training_dynamics, claim_boundary',
 'R100_CausalOperatorScratch/results/posttraining_validation/model_internal/summary.json': 'field inventory only',
 'R103_RecoverableDetailScratch/results/posttraining_validation/final_summary.json': 'final_assessment; other content partly displayed',
 'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/candidate_selection/summary.json': 'full',
 'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/sem_contour/summary.json': 'method_summary and field inventory',
 'R117_CenterLockedSubpixelScratch/analysis/design_audit_20260905/FINDINGS.md': 'full',
 'R119_SequenceGeometryValidation/reports/CLOSEOUT.md': 'full; superseded historical claim',
 'R120_PhysicalSequenceRepair/MANIFEST.md': 'full',
 'R120_PhysicalSequenceRepair/results/probe_matrix.json': 'full',
 'R120_PhysicalSequenceRepair/results/probe_audit.json': 'full',
 'R120_PhysicalSequenceRepair/results/motion_diagnostic/summary.json': 'status, profile, models; hashes not reviewed as evidence',
 'R122_OperatorPrinciples/reports/MODEL_DESIGN.md': 'partial; full R122/R123 reports govern synthesis',
 'R128_SourceOnlyFullTraining/reports/R128_FULL_CONTOUR_SEM.md': 'partial; opening, table and final limitations reviewed',
 **{f'R129_OpticalPriorHybrid/model/organized/{name}.py': 'full' for name in ('hybrid','reconstruction','optics','output_policy')},
}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

def build():
    dirs = sorted((p for p in ROOT.iterdir() if p.is_dir() and
                   (m := re.match(r'^R(\d+)', p.name)) and 61 <= int(m[1]) <= 130),
                  key=lambda p: (int(re.match(r'^R(\d+)',p.name)[1]),p.name))
    rows = []
    for d in dirs:
        proc = subprocess.run(['rg','--files','--hidden','--no-ignore',str(d),'-g','*.md'],
                              capture_output=True, text=True, encoding='utf-8', check=False)
        if proc.returncode not in (0,1): raise RuntimeError(proc.stderr)
        paths = set(Path(x) for x in proc.stdout.splitlines())
        paths |= {ROOT / k for k in EXTRA if k.split('/')[0] == d.name}
        # Historical run fields checked to disambiguate stale README states.
        if int(re.match(r'^R(\d+)',d.name)[1]) in (92,93,94,95,98,99,102):
            paths |= set(d.glob('runs/training*/run_summary.json'))
            paths |= set(d.glob('runs/training*/run_progress.json'))
        for p in sorted(paths):
            if p == REPORT or OUT in p.parents: continue
            rel = p.relative_to(ROOT).as_posix()
            scope = EXTRA.get(rel, 'catalogued only')
            if p.name in FULL_NAMES and p.parent in (d, d/'reports'): scope = 'full'
            if p.name == 'README.md' and p.parent == d and any(d.name.startswith(x) for x in README_PREFIXES): scope = 'full'
            if p.name in ('run_summary.json','run_progress.json') and 'runs' in p.parts:
                scope = 'status and run_id fields only; not a current process check'
            rows.append(dict(round=d.name, path=str(p), scope=scope, bytes=p.stat().st_size, sha256=sha(p)))
    write_csv(OUT/'reading_ledger.csv', rows, ['round','path','scope','bytes','sha256'])
    per_round=[]
    for d in dirs:
        rr=[r for r in rows if r['round']==d.name]
        per_round.append(dict(round=d.name, full_reads=sum(r['scope'].startswith('full') for r in rr),
                              partial_reads=sum(r['scope']!='catalogued only' and not r['scope'].startswith('full') for r in rr),
                              catalogued_only=sum(r['scope']=='catalogued only' for r in rr)))
    write_csv(OUT/'round_inventory.csv',per_round,list(per_round[0]))
    summary = dict(kind='document_review_scope_not_experiment_certificate', round_directories=len(dirs),
                   absent_numbers=sorted(set(range(61,131))-{int(re.match(r'^R(\d+)',d.name)[1]) for d in dirs}),
                   files=len(rows), full_reads=sum(r['scope'].startswith('full') for r in rows),
                   partial_reads=sum(r['scope']!='catalogued only' and not r['scope'].startswith('full') for r in rows),
                   catalogued_only=sum(r['scope']=='catalogued only' for r in rows))
    (OUT/'scope.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    build()

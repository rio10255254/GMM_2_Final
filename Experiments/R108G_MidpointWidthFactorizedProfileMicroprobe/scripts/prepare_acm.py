"""Prepare locked R73/R74 ACM roots for R108G."""
from __future__ import annotations
import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1];EXP=Path(str(PROJECT_ROOT / 'Experiments'));OUT=ROOT/'results/locked_inference'
TEMPLATES={'R73':EXP/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json','R74':EXP/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json'}
def main():
 for suite,template in TEMPLATES.items():
  cfg=json.loads(template.read_text(encoding='utf-8'));cfg['experiment_id']=f'R108G_midpoint_width_{suite}';run=ROOT/'results/acm'/suite;(run/'config').mkdir(parents=True,exist_ok=True);(run/'results').mkdir(parents=True,exist_ok=True);(run/'config/experiment.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8');dirs={family['name']:str(OUT/suite/family['stage']) for family in cfg['dataset']['families']};(run/'results/inference_manifest.json').write_text(json.dumps({'experiment_id':cfg['experiment_id'],'methods':['R108G_midpoint_width'],'output_dirs':dirs,'status':'complete'},indent=2),encoding='utf-8');print(run)
 return 0
if __name__=='__main__':raise SystemExit(main())

"""Prepare R74 ACM roots for per-stage ablation."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TEMPLATE=Path(r'D:\GMM_2_Final\Experiments\R104_PhotometricInvariantCausalGateScratch\results\posttraining_validation\external_acm\R74_hard_microscopy\config\experiment.json');ORDER=['denoise','radiometry','edge']
def main():
 cfg0=json.loads(TEMPLATE.read_text(encoding='utf-8'))
 for index,name in enumerate(ORDER,1):
  cfg=dict(cfg0);cfg['experiment_id']=f'R108C_R74_stage{index:02d}_{name}';run=ROOT/f'results/acm/R74_stage{index:02d}_{name}';(run/'config').mkdir(parents=True,exist_ok=True);(run/'results').mkdir(parents=True,exist_ok=True);(run/'config/experiment.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8');output=ROOT/f'results/stage_ablation/R74/{index:02d}_{name}';dirs={family['name']:str(output/family['stage']) for family in cfg['dataset']['families']};(run/'results/inference_manifest.json').write_text(json.dumps({'experiment_id':cfg['experiment_id'],'methods':[name],'output_dirs':dirs,'status':'complete'},ensure_ascii=False,indent=2),encoding='utf-8');print(run)
 return 0
if __name__=='__main__':raise SystemExit(main())


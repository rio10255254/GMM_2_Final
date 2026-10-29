from __future__ import annotations
import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1];EXP=Path(str(PROJECT_ROOT / 'Experiments'))
def main():
 for guard in (.12,.25):
  suffix='' if abs(guard-.12)<1e-9 else '_g0p25'
  for suite,template in [('R73',EXP/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json'),('R74',EXP/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json')]:
   data_name=f'{suite}_no_radiometry{suffix}';cfg=json.loads(template.read_text(encoding='utf-8'));cfg['experiment_id']=f'R108C_{suite}_no_radiometry_guard{guard:.2f}';run=ROOT/f'results/acm/{data_name}';(run/'config').mkdir(parents=True,exist_ok=True);(run/'results').mkdir(parents=True,exist_ok=True);(run/'config/experiment.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8');out=ROOT/f'results/external_reconstruction/{data_name}';dirs={family['name']:str(out/family['stage']) for family in cfg['dataset']['families']};(run/'results/inference_manifest.json').write_text(json.dumps({'experiment_id':cfg['experiment_id'],'methods':['R108C_no_radiometry'],'output_dirs':dirs,'status':'complete'},indent=2),encoding='utf-8');print(run)
 return 0
if __name__=='__main__':raise SystemExit(main())

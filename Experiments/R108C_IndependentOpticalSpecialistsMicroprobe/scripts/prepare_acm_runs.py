"""Prepare isolated R73/R74 ACM runner roots for the frozen R108C probe."""
from __future__ import annotations

import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT=Path(__file__).resolve().parents[1]
EXPERIMENTS=Path(str(PROJECT_ROOT / 'Experiments'))
SUITES={
 'R73':{
  'template':EXPERIMENTS/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json',
  'output':ROOT/'results/external_reconstruction/R73',
 },
 'R74':{
  'template':EXPERIMENTS/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json',
  'output':ROOT/'results/external_reconstruction/R74',
 },
}


def main():
 for guard in (.12,.18):
  tag=f'{guard:.2f}'.replace('.','p')
  for suite,item in SUITES.items():
   cfg=json.loads(item['template'].read_text(encoding='utf-8'));cfg['experiment_id']=f'R108C_{suite}_calibrated_{tag}';run=ROOT/f'results/acm/{suite}_g{tag}';(run/'config').mkdir(parents=True,exist_ok=True);(run/'results').mkdir(parents=True,exist_ok=True);(run/'config/experiment.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
   output_root=ROOT/f'results/external_reconstruction/{suite}_g{tag}';output_dirs={family['name']:str(output_root/family['stage']) for family in cfg['dataset']['families']};manifest={'experiment_id':cfg['experiment_id'],'methods':[f'R108C_g{tag}'],'output_dirs':output_dirs,'checkpoint':f'frozen R108C specialists plus guard-{guard:.2f} denoise adoption','status':'complete'};(run/'results/inference_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({'suite':suite,'guard':guard,'run':str(run),'families':len(output_dirs)}))
 return 0


if __name__=='__main__':raise SystemExit(main())

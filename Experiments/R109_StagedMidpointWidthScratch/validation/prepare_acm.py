from __future__ import annotations
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];EXP=ROOT.parent
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);args=parser.parse_args();templates={'R73':EXP/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json','R74':EXP/'R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json'};source=ROOT/'results/posttraining'/args.tag
 for suite,template in templates.items():cfg=json.loads(template.read_text(encoding='utf-8'));cfg['experiment_id']=f'R109_{args.tag}_{suite}';run=ROOT/'results/posttraining_acm'/args.tag/suite;(run/'config').mkdir(parents=True,exist_ok=True);(run/'results').mkdir(parents=True,exist_ok=True);(run/'config/experiment.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8');dirs={family['name']:str(source/suite/family['stage']) for family in cfg['dataset']['families']};(run/'results/inference_manifest.json').write_text(json.dumps({'experiment_id':cfg['experiment_id'],'methods':[f'R109_{args.tag}'],'output_dirs':dirs,'status':'complete'},indent=2),encoding='utf-8')
 return 0
if __name__=='__main__':raise SystemExit(main())

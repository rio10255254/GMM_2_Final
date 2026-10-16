from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,torch
from sklearn.metrics import roc_auc_score
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'model'));sys.path.insert(0,str(ROOT/'training'));from r109_model import build_model;from r109_dataset import R109Dataset;from losses import need_target
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);args=parser.parse_args();device=torch.device('cuda:0');checkpoint=Path(args.checkpoint);model=build_model().to(device);model.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=False)['model']);model.eval();data=R109Dataset('validation',epoch=0,limit=128);rows=[];pixel_prediction=[];pixel_target=[]
 with torch.inference_mode():
  for item in data:
   source=item['source'].to(device);target=item['target'].to(device);edge=item['edge'].to(device);identity=item['identity'].to(device);details=model.forward_details(source);need,boundary=need_target(source,target,edge,identity)
   for index in range(2):
    band=boundary[index]>.1;positive=need[index]>.1;rows.append({'identity':bool(identity[index]),'global_prediction':float(details.necessity[index].mean()),'boundary_prediction':float(details.necessity[index][band].mean()) if bool(band.any()) else 0.0,'positive_prediction':float(details.necessity[index][positive].mean()) if bool(positive.any()) else 0.0,'target_mean':float(need[index].mean()),'target_positive_fraction':float(positive.float().mean())});selection=band.flatten();pixel_prediction.extend(details.necessity[index].flatten()[selection].cpu().tolist());pixel_target.extend((need[index].flatten()[selection]>.1).cpu().tolist())
 labels=np.asarray([not row['identity'] for row in rows]);boundary_score=np.asarray([row['boundary_prediction'] for row in rows]);global_score=np.asarray([row['global_prediction'] for row in rows]);result={'status':'complete','views':len(rows),'global_identity_mean':float(np.mean([row['global_prediction'] for row in rows if row['identity']])),'global_degraded_mean':float(np.mean([row['global_prediction'] for row in rows if not row['identity']])),'boundary_identity_mean':float(np.mean([row['boundary_prediction'] for row in rows if row['identity']])),'boundary_degraded_mean':float(np.mean([row['boundary_prediction'] for row in rows if not row['identity']])),'scene_auc_global':float(roc_auc_score(labels,global_score)),'scene_auc_boundary':float(roc_auc_score(labels,boundary_score)),'pixel_auc_on_boundary':float(roc_auc_score(pixel_target,pixel_prediction)),'degraded_target_mean':float(np.mean([row['target_mean'] for row in rows if not row['identity']])),'degraded_target_positive_fraction':float(np.mean([row['target_positive_fraction'] for row in rows if not row['identity']]))}
 (ROOT/'validation/need_probe_analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())

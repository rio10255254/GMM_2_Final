"""Read-only audit of the completed R152 checkpoint against frozen R148v2."""
from __future__ import annotations
import hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from losses import objective
from model import Model
from utils import load,model_config,now,save,setup,sha,train_config
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
 setup(1522801);done=load(ROOT/'runs/formal_8192/training_complete.json');rec=done['deployed_checkpoint'];assert sha(str(PROJECT_ROOT / rec['path']))==rec['sha256'];mc=model_config();cfg=train_config();model=Model(mc,ROOT).cuda().eval();cp=torch.load(str(PROJECT_ROOT / rec['path']),map_location='cpu',weights_only=False);model.load_state_dict(cp['model'],strict=True);bank=Bank(cfg)
 scores={}
 for scale in (0.0,1.0):
  model.set_deployment_scale(scale);rows=[]
  with torch.inference_mode():
   for index in range(128):
    batch=bank.batch('test',index,'cuda');output,parts=model(batch['source'],batch['operator_psf_indices'],True);loss,terms=objective(output,parts,batch,model,cfg);task=sum(cfg['loss'][k]*terms[k] for k in ('image','gradient','pair_output','boundary'))+cfg['loss']['observation']*terms['observation'];rows.append(dict(task=float(task),image=float(terms['image']),gradient=float(terms['gradient']),pair_output=float(terms['pair_output']),boundary=float(terms['boundary']),observation=float(terms['observation'])))
  scores[str(scale)]={k:float(np.mean([r[k] for r in rows])) for k in rows[0]}
 frames=[
  Path(str(PROJECT_ROOT / 'Shared_Sources/PI_Repeatability_20260903/raw/001804_XY_0/1.bmp')),
  Path(str(PROJECT_ROOT / 'Shared_Sources/PI_Repeatability_20260903/raw/004246_XY_0/1.bmp')),
  Path(str(PROJECT_ROOT / 'Shared_Sources/PI_Repeatability_20260903/raw/005143_XY_0/31.bmp')),
 ]
 real=[]
 for path in frames:
  raw=cv2.imread(str(path),cv2.IMREAD_UNCHANGED);assert raw is not None and raw.shape==(1544,2064);x=torch.from_numpy(raw.astype(np.float32)[None,None]/255).cuda()
  with torch.inference_mode():
   model.set_deployment_scale(0);base=model.forward_tiled(x);model.set_deployment_scale(1);new,parts=model.forward_tiled(x,True);weights=model.psf_fusion.last_weights.detach().cpu().numpy()[0];delta=(new-base).abs();relative=float(delta.double().square().mean().sqrt()*255);maxgray=float(delta.max()*255);finite=bool(torch.isfinite(new).all());tiled_base_diff=float((base-parts['base']).abs().max()*255)
  real.append(dict(path=str(path),rms_change_gray=relative,max_change_gray=maxgray,base_exact_max_gray=tiled_base_diff,finite=finite,weight_min=float(weights.min()),weight_max=float(weights.max()),weight_entropy=float(-(weights*np.log(np.maximum(weights,1e-12))).sum())))
 result=dict(status='passed',completed_utc=now(),checkpoint=rec,model_base_sha256=mc['base_checkpoint_sha256'],test=scores,test_delta={k:scores['1.0'][k]-scores['0.0'][k] for k in scores['0.0']},real_frames=real)
 save(ROOT/'results/completed_audit.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

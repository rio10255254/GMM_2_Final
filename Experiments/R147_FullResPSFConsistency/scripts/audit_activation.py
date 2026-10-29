"""Check the R139 saturation failure mode in the frozen R147 model."""
from pathlib import Path
import sys
import cv2,numpy as np,pandas as pd,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import load,save,sha,setup,model_config
from model import Model
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
 setup(1309001);rec=load(ROOT/'runs/formal_8192/training_complete.json')['checkpoint'];assert sha(str(PROJECT_ROOT / rec['path']))==rec['sha256'];m=Model(model_config(),ROOT).cuda().eval();m.load_state_dict(torch.load(str(PROJECT_ROOT / rec['path']),map_location='cpu',weights_only=False)['model']);plan=load(ROOT/'evaluation/capture_plan.json');tracking=pd.read_csv(ROOT/'evaluation/tracking.csv');rows=[];context={}
 def hook(module,args,logits):
  yy=logits[0,0][context['roi']];t=torch.tanh(yy);rows.append(dict(frame=context['frame'],iteration=1+len([r for r in rows if r['frame']==context['frame']]),tanh_saturation_fraction=float((t.abs()>.999).float().mean()),tanh_derivative_mean=float((1-t.square()).mean()),max_abs_logit=float(yy.abs().max())))
 h=m.refiner.register_forward_hook(hook)
 for n in (0,155,310,465,620,899):
  f=plan['frames'][n];im=cv2.imread(f['source']['path'],0).astype(np.float32)/255;seeds=tracking[(tracking.run==f['run'])&(tracking['index']==f['index'])][['seed_x_px','seed_y_px']].to_numpy();context.update(frame=n,roi=(slice(int(seeds[:,1].min())-24,int(seeds[:,1].max())+25),slice(int(seeds[:,0].min())-24,int(seeds[:,0].max())+25)))
  with torch.inference_mode():m(torch.from_numpy(im)[None,None].cuda())
 h.remove();out=ROOT/'results/internal_audit';pd.DataFrame(rows).to_csv(out/'activation.csv',index=False);save(out/'activation_complete.json',dict(rows=len(rows),frames=6,checkpoint_sha256=rec['sha256'],script_sha256=sha(__file__),maximum_saturated_fraction=max(r['tanh_saturation_fraction'] for r in rows),minimum_average_derivative=min(r['tanh_derivative_mean'] for r in rows)))
 print('ACTIVATION_COMPLETE',max(r['tanh_saturation_fraction'] for r in rows),flush=True)
if __name__=='__main__':main()

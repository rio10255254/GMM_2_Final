"""Same-photo controls for blur, contrast, intensity and sensor noise."""
from pathlib import Path
import argparse,sys
import cv2,numpy as np,pandas as pd,torch
from scipy.ndimage import gaussian_filter
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--model',choices=['r140','r146','r147'],required=True);a=p.parse_args()
 root={'r147':ROOT,'r146':ROOT.parent/'R146_SEMCoreHaloPSF25_MatchedPairs','r140':ROOT.parent/'R140v2_StableUNet'}[a.model];sys.path.insert(0,str(root))
 from model import Model
 from utils import load,save,sha,setup,model_config
 from evaluation.measurement_interface import measure_image
 setup(1309001);cv2.setNumThreads(1);complete=load(root/'runs/formal_8192/training_complete.json');cp=complete['final_checkpoint' if a.model=='r140' else 'checkpoint'];assert sha(cp['path'])==cp['sha256'];cfg=model_config();m=Model(cfg,root).cuda().eval();m.load_state_dict(torch.load(cp['path'],map_location='cpu',weights_only=False)['model'],strict=True)
 plan=load(ROOT/'evaluation/capture_plan.json');tracking=pd.read_csv(ROOT/'evaluation/tracking.csv');reader=load(ROOT/'evaluation/measurement_config.json');out=ROOT/'results/internal_audit';rows=[];parity=[]
 def values(im,seeds):
  rr,_=measure_image(im.astype(np.float64),seeds,reader);return np.array([[r['center_x_px'],r['center_y_px'],r['radius_px']] for r in rr])
 def predict(im):
  with torch.inference_mode():return m(torch.from_numpy(np.ascontiguousarray(im))[None,None].cuda()).cpu().numpy()[0,0]
 for n in [0,155,310,465,620,899]:
  f=plan['frames'][n];assert sha(f['source']['path'])==f['source']['sha256'];im=cv2.imread(f['source']['path'],0).astype(np.float32)/np.float32(255);seeds=tracking[(tracking.run==f['run'])&(tracking['index']==f['index'])].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy();rawv=values(im,seeds)
  with np.load(root/'results/reconstruction'/f['run']/f"{f['index']+1:02d}.npz") as z:base=z['output']
  bv=values(base,seeds)
  if n==0:
   err=float(np.abs(predict(im)-base).max());assert err<1e-6;parity.append(err)
  noise=np.random.default_rng(1472600+n).normal(0,1/255,im.shape).astype(np.float32)
  cases=[('blur_0p25',gaussian_filter(im,.25,mode='reflect')),('blur_0p5',gaussian_filter(im,.5,mode='reflect')),('contrast_0p8',im.mean()+.8*(im-im.mean())),('contrast_1p2',im.mean()+1.2*(im-im.mean())),('brightness_plus10',im+10/255),('brightness_minus10',im-10/255),('noise_sigma1',im+noise)]
  for label,t in cases:
   clip=float(((t<0)|(t>1)).mean());t=t.clip(0,1).astype(np.float32);rv=values(t,seeds);yv=values(predict(t),seeds)
   for k in range(9):
    dc=(yv[k,:2]-bv[k,:2])*172.5;rc=(rv[k,:2]-rawv[k,:2])*172.5
    rows.append(dict(model=a.model,frame=n,condition=label,pillar=k+1,center_change_nm=float(np.linalg.norm(dc)),raw_center_change_nm=float(np.linalg.norm(rc)),diameter_change_nm=float((yv[k,2]-bv[k,2])*345),raw_diameter_change_nm=float((rv[k,2]-rawv[k,2])*345),clipped_fraction=clip))
  pd.DataFrame(rows).to_csv(out/f'nuisance_{a.model}.csv',index=False);print('NUISANCE',a.model,n,flush=True)
 save(out/f'nuisance_{a.model}_complete.json',dict(model=a.model,checkpoint_sha256=cp['sha256'],source_script_sha256=sha(__file__),frames=6,rows=len(rows),baseline_full_output_max_error=max(parity),note='Perturbing already sampled photographs is a diagnostic, not new optical acquisition or material truth.'))
if __name__=='__main__':main()

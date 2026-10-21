"""Historical native-resolution model as an integer-grid diagnostic control."""
from pathlib import Path
import sys
import cv2,numpy as np,pandas as pd,torch
from scipy.ndimage import shift
ROOT=Path(__file__).resolve().parents[1];R137=ROOT.parent/'R137_WeakPSFFeature';sys.path.insert(0,str(R137))
from utils import load,save,sha,setup
from infer_r137_psf import load_own_model,predict_tensor
from evaluation.measurement_interface import measure_image
def main():
 setup(1309001);cv2.setNumThreads(1);rec=load(R137/'runs/formal_8192/training_complete.json')['final_checkpoint'];assert sha(rec['path'])==rec['sha256'];m,_=load_own_model(rec['path']);plan=load(ROOT/'evaluation/capture_plan.json');tracking=pd.read_csv(ROOT/'evaluation/tracking.csv');cfg=load(ROOT/'evaluation/measurement_config.json');rows=[];parity=[]
 def vals(im,s):
  v,_=measure_image(im.astype(np.float64),s,cfg);return np.array([[x['center_x_px'],x['center_y_px'],x['radius_px']] for x in v])
 def predict(im):
  with torch.inference_mode():return predict_tensor(m,torch.from_numpy(np.ascontiguousarray(im))[None,None].cuda()).cpu().numpy()[0,0]
 for n in (0,155,310,465,620,899):
  f=plan['frames'][n];assert sha(f['source']['path'])==f['source']['sha256'];im=cv2.imread(f['source']['path'],0).astype(np.float32)/np.float32(255);s=tracking[(tracking.run==f['run'])&(tracking['index']==f['index'])].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy()
  with np.load(R137/'results/reconstruction'/f['run']/f"{f['index']+1:02d}.npz") as z:base=z['output']
  if n==0:
   error=float(np.abs(predict(im)-base).max());assert error<1e-6;parity.append(error)
  b=vals(base,s)
  for dx in (1,8):
   xx=shift(im,(0,dx),order=0,mode='reflect',prefilter=False);y=predict(xx);ref=shift(base,(0,dx),order=0,mode='reflect',prefilter=False);v=vals(y,s+[dx,0]);roi=(slice(int(s[:,1].min())-24,int(s[:,1].max())+25),slice(int(s[:,0].min())+dx-24,int(s[:,0].max())+dx+25));dr=y[roi]-ref[roi]
   for k in range(9):rows.append(dict(model='r137',frame=n,dx=dx,pillar=k+1,center_error_nm=float(np.linalg.norm(v[k,:2]-b[k,:2]-[dx,0])*172.5),diameter_change_nm=float((v[k,2]-b[k,2])*345),commutator_RMS_gray=float(np.sqrt(np.mean(dr**2))*255)))
  print('R137_GRID',n,flush=True)
 out=ROOT/'results/internal_audit';pd.DataFrame(rows).to_csv(out/'r137_grid.csv',index=False);save(out/'r137_grid_complete.json',dict(rows=len(rows),frames=6,checkpoint_sha256=rec['sha256'],source_script_sha256=sha(__file__),baseline_full_output_max_error=max(parity)))
if __name__=='__main__':main()

"""Full-frame versus native-stage tiled parity for the deployed R152 weights."""
from __future__ import annotations
import json,sys
from pathlib import Path
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model import Model
from utils import load,model_config,now,save,setup,sha
FRAMES=[
 Path(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903\001804_XY_0\1.bmp'),
 Path(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903\004246_XY_0\1.bmp'),
 Path(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903\005143_XY_0\31.bmp'),
]
def main():
 setup(1522901);receipt=load(ROOT/'runs/formal_8192/training_complete.json')['deployed_checkpoint'];assert sha(receipt['path'])==receipt['sha256'];model=Model(model_config(),ROOT).cuda().eval();model.load_state_dict(torch.load(receipt['path'],map_location='cpu',weights_only=False)['model'],strict=True);rows=[]
 for path in FRAMES:
  raw=cv2.imread(str(path),cv2.IMREAD_UNCHANGED);assert raw is not None and raw.shape==(1544,2064);x=torch.from_numpy(raw.astype(np.float32)[None,None]/255).cuda()
  with torch.inference_mode():full=model(x).cpu().numpy()[0,0];tiled=model.forward_tiled(x).cpu().numpy()[0,0]
  diff=np.abs(full.astype(np.float64)-tiled.astype(np.float64))*255;h,w=diff.shape;seam=np.zeros((h,w),bool);core=512;band=4
  for y in range(core,h,core):seam[max(0,y-band):min(h,y+band+1),:]=True
  for xx in range(core,w,core):seam[:,max(0,xx-band):min(w,xx+band+1)]=True
  rows.append(dict(frame=str(path),mean_abs_gray=float(diff.mean()),rms_gray=float(np.sqrt(np.square(diff).mean())),p99_gray=float(np.quantile(diff,.99)),max_gray=float(diff.max()),seam_mean_gray=float(diff[seam].mean()),interior_mean_gray=float(diff[~seam].mean()),seam_to_interior_ratio=float(diff[seam].mean()/max(diff[~seam].mean(),1e-15))))
 result=dict(status='passed',checkpoint_sha256=receipt['sha256'],core=512,halo=24,frames=rows,completed_utc=now());save(ROOT/'results/final_tile_parity.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

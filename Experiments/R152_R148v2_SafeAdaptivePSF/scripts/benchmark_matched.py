"""Same-process FP32 timing of frozen R148v2 and deployed R152 on real frames."""
from __future__ import annotations
import json,statistics,sys,time
from pathlib import Path
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];BASE=Path(r'D:\GMM_2_Final\Experiments\R148v2_HybridContextNativePSF');sys.path.insert(0,str(ROOT))
from base_model import Model as BaseModel
from model import Model as ExtensionModel
from utils import load,model_config,now,save,sha
FRAMES=[
 Path(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903\001804_XY_0\1.bmp'),
 Path(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903\004246_XY_0\1.bmp'),
 Path(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903\005143_XY_0\31.bmp'),
]
def main():
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 config=load(BASE/'config/model.json');reference=BaseModel(config,BASE).cuda().eval();old=load(BASE/'runs/formal_8192/training_complete.json')['checkpoint'];assert sha(old['path'])==old['sha256'];reference.load_state_dict(torch.load(old['path'],map_location='cpu',weights_only=False)['model'],strict=True)
 deployed=load(ROOT/'runs/formal_8192/training_complete.json')['deployed_checkpoint'];assert sha(deployed['path'])==deployed['sha256'];extension=ExtensionModel(model_config(),ROOT).cuda().eval();extension.load_state_dict(torch.load(deployed['path'],map_location='cpu',weights_only=False)['model'],strict=True)
 rows=[]
 for frame in FRAMES:
  raw=cv2.imread(str(frame),cv2.IMREAD_UNCHANGED);x=torch.from_numpy(raw.astype(np.float32)[None,None]/255).cuda()
  for name,model in [('R148v2',reference),('R152',extension)]:
   with torch.inference_mode():
    model.forward_tiled(x);torch.cuda.synchronize()
    times=[];peaks=[];increments=[]
    for _ in range(5):
     torch.cuda.reset_peak_memory_stats();idle=int(torch.cuda.memory_allocated());start=time.perf_counter();output=model.forward_tiled(x);torch.cuda.synchronize();times.append(time.perf_counter()-start);peak=int(torch.cuda.max_memory_allocated());peaks.append(peak);increments.append(peak-idle);del output
   rows.append(dict(frame=str(frame),model=name,median_seconds=statistics.median(times),times=times,peak_allocated_bytes=max(peaks),peak_incremental_bytes=max(increments)))
 result=dict(status='passed',device=torch.cuda.get_device_name(0),precision='FP32',warmup=1,repeats_per_frame=5,frames=rows,median_of_frame_medians={name:statistics.median([r['median_seconds'] for r in rows if r['model']==name]) for name in ('R148v2','R152')},peak_incremental_bytes={name:max(r['peak_incremental_bytes'] for r in rows if r['model']==name) for name in ('R148v2','R152')},memory_note='Both models are resident in one process; compare incremental temporary memory, not peak allocated across the entire process.',completed_utc=now());save(ROOT/'results/matched_runtime.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

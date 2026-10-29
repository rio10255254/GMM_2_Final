"""Measure one model per process to avoid persistent cross-model allocations."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
import cv2,numpy as np,torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1];BASE=Path(str(PROJECT_ROOT / 'Experiments/R148v2_HybridContextNativePSF'));sys.path.insert(0,str(ROOT))
from base_model import Model as BaseModel
from model import Model as ExtensionModel
from utils import load,model_config,now,save,sha
FRAME=Path(str(PROJECT_ROOT / 'Shared_Sources/PI_Repeatability_20260903/raw/001804_XY_0/1.bmp'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--model',choices=['R148v2','R152'],required=True);a=p.parse_args();torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 if a.model=='R148v2':
  config=load(BASE/'config/model.json');model=BaseModel(config,BASE).cuda().eval();record=load(BASE/'runs/formal_8192/training_complete.json')['checkpoint']
 else:
  model=ExtensionModel(model_config(),ROOT).cuda().eval();record=load(ROOT/'runs/formal_8192/training_complete.json')['deployed_checkpoint']
 assert sha(str(PROJECT_ROOT / record['path']))==record['sha256'];model.load_state_dict(torch.load(str(PROJECT_ROOT / record['path']),map_location='cpu',weights_only=False)['model'],strict=True);raw=cv2.imread(str(FRAME),cv2.IMREAD_UNCHANGED);x=torch.from_numpy(raw.astype(np.float32)[None,None]/255).cuda()
 with torch.inference_mode():
  model.forward_tiled(x);torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();idle=int(torch.cuda.memory_allocated());start=time.perf_counter();y=model.forward_tiled(x);torch.cuda.synchronize();seconds=time.perf_counter()-start;peak=int(torch.cuda.max_memory_allocated());reserved=int(torch.cuda.max_memory_reserved())
 result=dict(model=a.model,frame=str(FRAME),seconds=seconds,idle_allocated_bytes=idle,peak_allocated_bytes=peak,incremental_bytes=peak-idle,peak_reserved_bytes=reserved,checkpoint_sha256=record['sha256'],completed_utc=now());save(ROOT/'results'/('memory_'+a.model+'.json'),result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

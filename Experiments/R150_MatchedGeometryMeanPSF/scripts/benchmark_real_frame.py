"""Benchmark one frozen real frame before the fixed 930-frame evaluation."""
from __future__ import annotations
import time
from pathlib import Path
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT))
from model import Model
from utils import load,model_config,save,sha,now,setup
from verify_package import verify_source_lock

def main():
 verify_source_lock();setup(1482101);done=load(ROOT/'runs/formal_8192/training_complete.json');rec=done['checkpoint'];assert rec['step']==8192 and sha(rec['path'])==rec['sha256']
 plan=load(ROOT/'evaluation/capture_plan.json');frame=plan['frames'][0];assert sha(frame['source']['path'])==frame['source']['sha256'];raw=cv2.imread(frame['source']['path'],cv2.IMREAD_UNCHANGED);assert raw is not None and raw.dtype==np.uint8 and raw.shape==(1544,2064)
 device='cuda' if torch.cuda.is_available() else 'cpu';cp=torch.load(rec['path'],map_location='cpu',weights_only=False);cfg=model_config();model=Model(cfg,ROOT).to(device).eval();model.load_state_dict(cp['model'],strict=True);x=torch.from_numpy(raw.astype(np.float32)[None,None]/255).to(device)
 if device=='cuda':torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
 started=time.perf_counter()
 with torch.inference_mode():y=model.forward_tiled(x)
 if device=='cuda':torch.cuda.synchronize()
 elapsed=time.perf_counter()-started;a=y.detach().cpu().numpy()[0,0];assert a.shape==raw.shape and np.isfinite(a).all()
 result=dict(frame=frame['run'],index=frame['index'],shape=list(a.shape),device=device,seconds=elapsed,peak_gpu_bytes=torch.cuda.max_memory_allocated() if device=='cuda' else None,minimum=float(a.min()),maximum=float(a.max()),mean=float(a.mean()),standard_deviation=float(a.std()),checkpoint_sha256=rec['sha256'],source_sha256=frame['source']['sha256'],completed_utc=now())
 save(ROOT/'results/real_frame_benchmark.json',result);print(result)
if __name__=='__main__':main()

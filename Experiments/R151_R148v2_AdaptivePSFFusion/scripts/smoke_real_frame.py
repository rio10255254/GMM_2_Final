"""Full-size real-frame smoke test for the untrained R151 architecture."""
from __future__ import annotations
import json,sys,time
from pathlib import Path
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model import Model
from utils import model_config,now,save,setup,verify_bank_lock
PROJECT_ROOT = Path(__file__).resolve().parents[3]

IMAGE=Path(str(PROJECT_ROOT / 'Shared_Sources/PI_Repeatability_20260903/raw/001804_XY_0/1.bmp'))
def main():
 setup(1512701);verify_bank_lock();raw=cv2.imread(str(IMAGE),cv2.IMREAD_UNCHANGED);x=torch.from_numpy(raw.astype(np.float32)[None,None]/255).cuda();model=Model(model_config(),ROOT).cuda().eval();generator=torch.Generator(device='cuda').manual_seed(1512702)
 with torch.no_grad():
  for stage in model.stages:stage.head.weight.copy_(torch.randn(stage.head.weight.shape,generator=generator,device='cuda')*1e-4);stage.head.bias.zero_()
 torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
 with torch.inference_mode():full=model(x)
 torch.cuda.synchronize();full_time=time.perf_counter()-start;full_peak=torch.cuda.max_memory_allocated();weights=model.psf_fusion.last_weights.cpu().numpy()[0]
 torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
 with torch.inference_mode():tiled=model.forward_tiled(x)
 torch.cuda.synchronize();tiled_time=time.perf_counter()-start;tiled_peak=torch.cuda.max_memory_allocated();difference=(full-tiled).abs()
 result=dict(status='passed',untrained_architecture_smoke_test=True,image=str(IMAGE),shape=list(raw.shape),device=torch.cuda.get_device_name(0),full_seconds=full_time,tiled_seconds=tiled_time,full_peak_allocated_bytes=full_peak,tiled_peak_allocated_bytes=tiled_peak,tiled_full_rms_gray=float(difference.double().square().mean().sqrt()*255),tiled_full_max_gray=float(difference.max()*255),output_min=float(tiled.min()),output_max=float(tiled.max()),weight_min=float(weights.min()),weight_max=float(weights.max()),weight_entropy=float(-(weights*np.log(np.maximum(weights,1e-12))).sum()),top5_indices=np.argsort(weights)[-5:][::-1].tolist(),beta=float(model.psf_fusion.beta_value()),completed_utc=now());save(ROOT/'results/real_frame_smoke.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

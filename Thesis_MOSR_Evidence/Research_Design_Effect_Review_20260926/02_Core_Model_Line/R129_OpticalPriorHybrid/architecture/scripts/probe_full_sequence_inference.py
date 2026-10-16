"""Try a complete source field before fixing the continuous inference execution path."""
import os,sys,time,traceback,json
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import load,save,record,sha,now,REPO
import cv2,numpy as np,torch
def main():
    out=ROOT/'results/continuous_lsc';out.mkdir(exist_ok=False)
    pkg=Path(load(ROOT/'config/standalone_build.json')['path']);sys.path.insert(0,str(pkg));import runtime
    from model.inference_policy import guard
    cp=pkg/'results/training/r129_long_01/checkpoints/step08192.pth'
    assert sha(cp)=='086608339c6418b9dfd650f6809b1f7b45e65b6eb11452afe7df45c5b24ff1fd'
    old=load(REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/plan.json');frame=old['frames'][0]
    save(out/'direct_probe_plan.json',dict(created_utc=now(),source=record(__file__),frame=frame['source'],checkpoint=record(cp),method='Exact full-field original organized forward; no tiling/ROI substitution',alternative_if_memory_failure='Separately validate staged global optics and local reconstruction; preserve failure'))
    m,_=runtime.create('cuda');m.load_state_dict(torch.load(cp,map_location='cuda')['model']);m.eval()
    raw=cv2.imread(frame['source']['path'],0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
    torch.cuda.reset_peak_memory_stats();tick=time.perf_counter()
    try:
        with torch.no_grad():d=m.forward_details(x);applied=guard(x,d.output)[0,0].cpu().numpy();neural=d.output[0,0].cpu().numpy()
        np.savez_compressed(out/'direct_probe_output.npz',output=applied,neural_output=neural)
        save(out/'direct_probe_result.json',dict(passed=True,seconds=time.perf_counter()-tick,peak_memory_bytes=torch.cuda.max_memory_allocated(),shape=list(raw.shape),output=record(out/'direct_probe_output.npz'),frame=frame['source']))
        print('Full source field passed',time.perf_counter()-tick,torch.cuda.max_memory_allocated(),flush=True)
    except Exception:
        save(out/'direct_probe_result.json',dict(passed=False,seconds=time.perf_counter()-tick,error=traceback.format_exc(),peak_memory_bytes=torch.cuda.max_memory_allocated()))
        raise
if __name__=='__main__':main()

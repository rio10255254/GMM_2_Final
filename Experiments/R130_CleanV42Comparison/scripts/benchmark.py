"""Same native frame, precision, warmup and repetitions for both existing models."""
import sys,time,argparse,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2
from output_guard import guard
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main(method):
    plan=load(ROOT/'config/final_evaluation_plan.json');source=plan['frames'][0]['source'];assert sha(str(PROJECT_ROOT / source['path']))==source['sha256']
    if method=='V42':
        m,_=create();cp=ROOT/'runs/v42_clean/checkpoints/step04096.pth';m.load_state_dict(torch.load(cp,map_location='cuda')['model']);forward=lambda x:guard(x,m(x))
    else:
        package=REPO/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912';sys.path.insert(0,str(package));import runtime
        m,_=runtime.create();cp=package/'results/training/r129_long_01/checkpoints/step08192.pth';m.load_state_dict(torch.load(cp,map_location='cuda')['model'])
        p=REPO/'Experiments/R129_OpticalPriorHybrid/scripts/sequence_inference.py';spec=importlib.util.spec_from_file_location('r129_benchmark_staged',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        forward=lambda x:guard(x,module.predict(m,x,512))
    m.eval();raw=cv2.imread(str(PROJECT_ROOT / source['path']),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();times=[];torch.cuda.reset_peak_memory_stats()
    with torch.no_grad():
        first=forward(x);torch.cuda.synchronize()
        for _ in range(3):
            tick=time.perf_counter();y=forward(x);torch.cuda.synchronize();times.append(time.perf_counter()-tick);assert torch.equal(y,first)
    save(ROOT/'results'/f'benchmark_{method}.json',dict(created_utc=now(),source=record(__file__),method=method,checkpoint=record(cp),input=source,shape=list(raw.shape),warmups=1,repetitions=3,seconds=times,median_seconds=float(np.median(times)),peak_memory_bytes=torch.cuda.max_memory_allocated(),arithmetic='FP32,TF32off,deterministic,oneimage,noIO',scope='One representative full native field, not a broad hardware benchmark'))
    print(method,'median seconds',float(np.median(times)),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--method',choices=['V42','R129'],required=True);a=p.parse_args();main(a.method)

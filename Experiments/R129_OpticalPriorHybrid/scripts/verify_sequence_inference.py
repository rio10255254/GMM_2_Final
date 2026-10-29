"""Validate the staged path before any continuous-sequence outcome is measured."""
import os,sys,time
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,cv2,torch
from sequence_inference import predict
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    out=ROOT/'results/continuous_lsc';pkg=Path(PROJECT_ROOT / load(ROOT/'config/standalone_build.json')['path']);sys.path.insert(0,str(pkg));import runtime
    from model.inference_policy import guard
    save(out/'staged_inference_plan.json',dict(created_utc=now(),source=record(__file__),implementation=record(ROOT/'scripts/sequence_inference.py'),reason='Direct full field failed in depthwise operator32bit index limit; original failure retained',native_core=512,native_halo=16,prior_support_upper_bound_feature_pixels=22,halo_feature_pixels=32,global_operations=['optics','native statistics/features','state updates','Raw output anchor','quality score','FOV guard'],tests='Known full forward on three real SEM fields plus random odd-sized image; full-field split/core consistency',acceptance=dict(float_max_abs=1e-6,real_saved_png_max_gray_difference=1),no_model_weight_change=True))
    m,_=runtime.create('cuda');cp=pkg/'results/training/r129_long_01/checkpoints/step08192.pth';m.load_state_dict(torch.load(cp,map_location='cuda')['model']);m.eval();rows=[]
    with torch.no_grad():
        sources=[pkg/f'validation/inputs/sem{i}.png' for i in [13,14,15]]
        for index,path in enumerate(sources+[None]):
            raw=cv2.imread(str(path),0).astype(np.float32)/255 if path else np.random.default_rng(12913).random((197,233),dtype=np.float32)
            x=torch.from_numpy(raw)[None,None].cuda();d=m.forward_details(x)
            for core in ([256,512] if path else [64,128]):
                value,latent=predict(m,x,core=core,return_latent=True)
                diff=float(abs(value-d.output).max());ldiff=float(abs(latent-d.latent).max());assert max(diff,ldiff)<1e-6
                a=np.rint(guard(x,value)[0,0].cpu().numpy()*255).clip(0,255).astype(np.uint8);b=np.rint(guard(x,d.output)[0,0].cpu().numpy()*255).clip(0,255).astype(np.uint8)
                pdiff=int(abs(a.astype(int)-b.astype(int)).max());assert pdiff<=1
                rows.append(dict(input=str(path) if path else 'random197x233',core=core,output_float_difference=diff,latent_float_difference=ldiff,changed_uint8_pixels=int(np.count_nonzero(a!=b)),maximum_gray_difference=pdiff))
            print('Staged direct parity',index,rows[-1],flush=True)
        source=load(REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/plan.json')['frames'][0]['source']
        x=torch.from_numpy(cv2.imread(str(PROJECT_ROOT / source['path']),0).astype(np.float32)/255)[None,None].cuda();tick=time.perf_counter();torch.cuda.reset_peak_memory_stats()
        value=predict(m,x,512);torch.cuda.synchronize();elapsed=time.perf_counter()-tick
        second=predict(m,x,384);diff=float(abs(value-second).max());assert diff<1e-6
        a=np.rint(guard(x,value)[0,0].cpu().numpy()*255).clip(0,255).astype(np.uint8);b=np.rint(guard(x,second)[0,0].cpu().numpy()*255).clip(0,255).astype(np.uint8);assert abs(a.astype(int)-b.astype(int)).max()<=1
        np.savez_compressed(out/'staged_full_probe.npz',output=guard(x,value)[0,0].cpu().numpy(),neural_output=value[0,0].cpu().numpy())
    save(out/'staged_inference_verification.json',dict(passed=True,completed_utc=now(),plan=record(out/'staged_inference_plan.json'),rows=rows,full_field_source=source,full_core512_vs384_max_float=diff,full_changed_uint8_pixels=int(np.count_nonzero(a!=b)),full_core512_seconds=elapsed,peak_memory_bytes=torch.cuda.max_memory_allocated(),probe=record(out/'staged_full_probe.npz'),scope='Mathematically same local operator with declared halo; finite-precision equivalence checked, not alternate model'))
    print('Full staged field passed',elapsed,'seconds',diff,'difference',flush=True)
if __name__=='__main__':main()

"""Check native-resolution inference without reading any real validation image."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import torch
from model import Model
from training_policy import apply_epoch_policy
from utils import ROOT,model_config,config,setup,save,now

def main():
    cfg=config();setup(cfg['model_seed']);model=Model(model_config(),ROOT).cuda().eval()
    generator=torch.Generator(device='cuda').manual_seed(cfg['model_seed']+42)
    source=torch.rand((1,1,1544,2064),generator=generator,device='cuda')
    records=[]
    with torch.inference_mode():
        for epoch in (0,2):
            apply_epoch_policy(model,epoch)
            torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
            prediction=model(source)
            torch.cuda.synchronize()
            difference=float((prediction-source).abs().max())
            records.append(dict(epoch=epoch,psf_scale=float(model.refiner.optics.beta_scale),
                                shape=list(prediction.shape),max_initial_difference=difference,
                                peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
                                inference_seconds=time.perf_counter()-start))
            assert torch.isfinite(prediction).all() and difference==0.0
    result=dict(exact_initial_identity=True,shape=[1544,2064],synthetic_only=True,
                peak_gpu_allocated_bytes=max(v['peak_gpu_allocated_bytes'] for v in records),
                checks=records,completed_utc=now())
    save(ROOT/'results/full_size_preflight.json',result)
    print('FULL_SIZE_PREFLIGHT_PASS',result,flush=True)
if __name__=='__main__':main()

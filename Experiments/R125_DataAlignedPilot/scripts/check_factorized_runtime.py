"""Bounded acceleration qualification before learned real outputs."""
import pathlib,sys,json,time,traceback
import numpy as np,torch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'R124_RealFirstPrototype'))
from model.calibration import observation_from_profile
from prototype.factorized_observation import from_observation
from prototype.network import build_model
from inference.tiling import tiled_forward
def main():
    out=ROOT/'results/factorized_runtime.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(2);torch.manual_seed(1259001);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    profile=json.loads((ROOT/'config/real_observation_v2.json').read_text());axis=torch.arange(-64,65,dtype=torch.float64);row=torch.exp(-axis.square()/(2*(3.2*4)**2));row/=row.sum();profile['kernel']={'type':'explicit','values':(row[:,None]*row[None,:]).tolist()};profile['calibration_id']='maximum_support_acceleration_test'
    rec={'status':'running','optimizer_updates':0,'original_kernel_refit':False,'kernel_L1_tolerance':1e-6}
    try:
        base=observation_from_profile(profile);fast=from_observation(base).cuda();m=build_model({'checkpoint_blocks':True},fast).cuda().train()
        with torch.no_grad():m.prior.head.weight.normal_(0,.02)
        x=.2+.6*torch.rand(2,1,640,640,device='cuda');weights=[p.detach().clone() for p in m.parameters()];torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();t=time.perf_counter()
        d=m.forward_details(x);loss=d.output[...,256:384,256:384].square().mean()+.001*d.geometry['sdf'][...,256:384,256:384].square().mean();loss.backward();torch.cuda.synchronize()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters());assert all(torch.equal(a,p.detach()) for a,p in zip(weights,m.parameters()))
        rec.update(backward_elapsed_seconds=time.perf_counter()-t,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,factorization=fast.factorization_metadata(),native_shape=list(x.shape),latent_shape=list(d.latent.shape))
        del m,d,loss,x,weights,fast;torch.cuda.empty_cache()
        # Default64-channel nonneutral tile parity, not an identity shortcut.
        profile=json.loads((ROOT/'config/real_observation_v2.json').read_text());fast=from_observation(observation_from_profile(profile)).cuda();m=build_model(observation=fast).cuda().eval()
        with torch.no_grad():m.prior.head.weight.normal_(0,.02)
        x=.2+.6*torch.rand(1,1,321,377,device='cuda')
        with torch.inference_mode():full=m(x)
        tiled=tiled_forward(m,x,core=173,origin=(17,31));err=float((full-tiled).abs().max());assert err<=2e-6
        # Actual stored trainingPSFs all obey original-kernel error/centroid bounds.
        records=[]
        for p in sorted((ROOT/'data/package_v2/scenes').glob('*.metadata.json')):
            meta=json.loads(p.read_text());obs=from_observation(observation_from_profile(meta['profile']));f=obs.factorization_metadata();assert f['measured_kernel_L1_error']<=1e-6
            records.append({'scene_id':meta['scene_id'],'rank':f['rank'],'kernel_L1_error':f['measured_kernel_L1_error'],'centroid_difference_native_xy':f['centroid_difference_native_xy']})
        assert len(records)==64
        rec.update(status='passed',nonneutral_tile_max_error=err,all64_training_kernel_factor_checks=records,real_profile_factorization=fast.factorization_metadata(),scope='Finite-domain arithmetic acceleration andruntime; notphysicalcalibration orlearnedefficacy')
    except BaseException as e:rec.update(status='failed',error=repr(e),traceback=traceback.format_exc());raise
    finally:out.write_text(json.dumps(rec,indent=2));print(json.dumps({k:v for k,v in rec.items() if k!='all64_training_kernel_factor_checks'}),flush=True)
if __name__=='__main__':main()

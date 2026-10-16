"""Verify4x optical state/2xprior resource and gradients, zero optimizer updates."""
import pathlib,sys,json,time,traceback
import numpy as np,torch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'R124_RealFirstPrototype'))
from prototype.network import build_model
from model.calibration import observation_from_profile
def main():
    out=ROOT/'results/representation_v2_runtime_retry.json'
    if out.exists():raise FileExistsError(out)
    torch.set_num_threads(2);torch.manual_seed(1259001);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    profile=json.loads((ROOT/'config/real_observation_v2.json').read_text())
    # Actual training uses explicit4xPSFs. R124's Gaussian convenience loader
    # deliberately capped its own original2x helper at32internal cells.
    axis=torch.arange(-64,65,dtype=torch.float64);row=torch.exp(-axis.square()/(2*(3.2*4)**2));row/=row.sum()
    profile['kernel']={'type':'explicit','values':(row[:,None]*row[None,:]).tolist()}
    profile['calibration_id']='maximum16native_support_arithmetic_only'
    rec={'status':'running','optimizer_updates':0,'scope':'worst planned Gaussian support engineeringbackward, not data or real efficacy'}
    try:
        m=build_model({'checkpoint_blocks':True},observation_from_profile(profile,'cuda')).cuda().train()
        with torch.no_grad():m.prior.head.weight.normal_(0,.02)
        x=.2+.6*torch.rand(2,1,640,640,device='cuda');weights=[p.detach().clone() for p in m.parameters()];torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();t=time.perf_counter()
        d=m.forward_details(x);loss=d.output[...,256:384,256:384].square().mean()+.001*d.geometry['sdf'][...,256:384,256:384].square().mean();loss.backward();torch.cuda.synchronize()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters());assert all(torch.equal(a,p.detach()) for a,p in zip(weights,m.parameters()))
        rec.update(status='passed',native_shape=list(x.shape),latent_shape=list(d.latent.shape),prior_head_channels=4,parameters=sum(p.numel() for p in m.parameters()),elapsed_seconds=time.perf_counter()-t,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,halo=m.required_halo,weights_unchanged=True)
    except BaseException as e:rec.update(status='failed',error=repr(e),traceback=traceback.format_exc());raise
    finally:out.write_text(json.dumps(rec,indent=2));print(json.dumps(rec),flush=True)
if __name__=='__main__':main()

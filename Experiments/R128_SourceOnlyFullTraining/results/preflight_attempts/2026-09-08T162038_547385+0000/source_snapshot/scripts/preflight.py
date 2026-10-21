"""Executed tests of semantics, numerical operators, learning, and recovery."""
import sys,time,inspect,traceback,shutil
from pathlib import Path
from common import *
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from torch.nn import functional as F
from model.network import Model,boundary_guard
from model.observation import Observation
from training.data import make_batch
from training.objectives import objective,sensor_nll,observation_prediction,translated
from training.engine import create,update,checkpoint,restore,state_digest
import importlib.util
spec=importlib.util.spec_from_file_location('r124_tiling',R124/'inference/tiling.py');tiling=importlib.util.module_from_spec(spec);spec.loader.exec_module(tiling)

def main():
    cfg=load(ROOT/'config/study.json');stamp=now().replace(':','').replace('.','_')
    out=ROOT/'results/preflight_attempts'/stamp;out.mkdir(parents=True)
    sources=[p for folder in ['model','training','scripts'] for p in (ROOT/folder).glob('*.py')]
    save(out/'source_identity.json',{str(p):sha(p) for p in sources})
    for p in sources:
        dest=out/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    rows=[];start=time.perf_counter()
    def done(name,**values):
        rows.append(dict(name=name,passed=True,**values));atomic(out/'progress.json',dict(checks=rows,seconds=time.perf_counter()-start))
        print(json.dumps(rows[-1]),flush=True)
    try:
        assert list(inspect.signature(Model.forward_details).parameters)==['self','raw','trace']
        assert not any(x in n for n in Model().state_dict() for x in ['observation','geometry','confidence'])
        try:Model()(torch.full((1,1,16,16),float('nan')))
        except ValueError:pass
        else:raise AssertionError('Invalid image was accepted')
        done('image_only_input_contract')
        torch.manual_seed(12);x=torch.randn(2,1,64,68,dtype=torch.float64,requires_grad=True)
        k=torch.rand(5,5,dtype=torch.float64);k/=k.sum()
        fft=Observation(k)(x);dense=F.avg_pool2d(F.conv2d(x,k.flip((0,1))[None,None],padding=2),4)
        error=float((fft-dense).abs().max());assert error<1e-12
        direction=torch.randn_like(x);grad=torch.autograd.grad(fft.square().sum(),x)[0];eps=1e-6
        finite=((Observation(k)(x+eps*direction).square().sum()-Observation(k)(x-eps*direction).square().sum())/(2*eps)).detach()
        derivative=float((grad*direction).sum());rel=abs(float(finite)-derivative)/max(1,abs(derivative));assert rel<1e-7
        impulse=torch.zeros(1,1,64,68,dtype=torch.float64);impulse[...,0,0]=1
        assert float(Observation(k)(impulse)[...,-2:,-2:].abs().max())<1e-14
        done('linear_physical_convolution_and_gradient',dense_max_error=error,finite_difference_relative_error=rel,asymmetric_kernel=True)
        mean=torch.tensor([.1,.9],requires_grad=True);source=torch.tensor([0.,1.])
        nll=sensor_nll(mean,source,1);nll.backward()
        assert torch.isfinite(nll) and mean.grad[0]>0 and mean.grad[1]<0
        done('censored_saturation_likelihood',loss=float(nll),gradient=mean.grad.tolist())
        from scipy.ndimage import shift as scipy_shift
        sample=np.random.default_rng(7).normal(size=(13,17))
        shifted=translated(torch.from_numpy(sample)[None,None],[.37,-.63])[0,0].numpy()
        reference=scipy_shift(sample,[-.63,.37],order=1,mode='grid-constant',cval=0,prefilter=False)
        translation_error=float(np.max(np.abs(shifted-reference)))
        assert translation_error<1e-12
        done('translation_matches_independent_bilinear_reference',maximum_error=translation_error)
        device='cuda'
        assert torch.cuda.is_available()
        model,opt=create(1285999,device,cfg);torch.cuda.reset_peak_memory_stats()
        with np.load(ROOT/'data/preflight/train/0000.npz') as f:a={k:f[k] for k in f.files}
        meta=load(ROOT/'data/preflight/train/0000.json');entry={'arrays_sha256':sha(ROOT/'data/preflight/train/0000.npz')}
        batch=make_batch(a,meta,entry,device,0)
        model.eval()
        with torch.no_grad():
            d=model.forward_details(batch['source'],trace=True)
            assert torch.equal(d.output,batch['source'])
            assert len(d.traces)==4 and all(torch.count_nonzero(t['learned_correction'])==0 for t in d.traces)
        done('exact_neutral_initialization',parameters=sum(p.numel() for p in model.parameters()),required_halo=model.required_halo)
        del d
        # A nonneutral model is essential: a Raw-copy model cannot test tiling.
        with torch.no_grad():model.prior.head.weight.normal_(0,.0005)
        model.eval();small=torch.rand(1,1,193,211,device=device)
        with torch.no_grad():
            full=model(small);tiled=tiling.tiled_forward(model,small,core=83,origin=(17,29))
            tile_error=float((full-tiled).abs().max());assert tile_error<2e-6
            g,w=boundary_guard(small,tiled,model.required_halo,16)
            assert torch.equal(g[...,w==0],small[...,w==0]) and torch.allclose(g[...,w==1],tiled[...,w==1])
        done('nonneutral_tiling_and_global_boundary',maximum_error=tile_error)
        del full,tiled,g,w,small
        # Compare identical physical core through full384 and cropped320.
        full_batch={**batch,'source':torch.from_numpy(a['source'][:,None].astype(np.float32)/255).to(device),'target':torch.from_numpy(a['target'][:,None]).to(device),'latent_target':torch.from_numpy(a['latent_target'][:,None]).to(device),'core':(128,256)}
        cropped=make_batch(a,meta,entry,device,None)
        model.train();opt.zero_grad(set_to_none=True)
        df=model.forward_details(full_batch['source']);lf,tf=objective(df,full_batch,cfg['loss_weights'],.02)
        output_full=df.output[...,128:256,128:256].detach().clone()
        lf.backward();grads=[p.grad.detach().clone() for p in model.parameters()];loss_full=float(lf.detach())
        del df,lf,tf,full_batch
        opt.zero_grad(set_to_none=True)
        dc=model.forward_details(cropped['source']);lc,tc=objective(dc,cropped,cfg['loss_weights'],.02);lc.backward()
        out_error=float((dc.output[...,96:224,96:224]-output_full).abs().max())
        grad_abs=max(float((p.grad-v).abs().max()) for p,v in zip(model.parameters(),grads))
        grad_rel=max(float((p.grad-v).abs().max())/max(1.,float(v.abs().max())) for p,v in zip(model.parameters(),grads))
        assert out_error<2e-6 and abs(float(lc)-loss_full)<1e-4 and grad_rel<2e-4
        done('full_physical_context_output_loss_gradient',maximum_output_error=out_error,loss_difference=abs(float(lc)-loss_full),gradient_maximum_absolute_difference=grad_abs,gradient_relative_bound=grad_rel)
        del dc,lc,tc,grads,output_full,model,opt
    except BaseException:
        save(out/'failure.json',dict(error=traceback.format_exc(),checks=rows,seconds=time.perf_counter()-start));raise
    # New initialization: numerical test weights never seed learning.
    try:
        model,opt=create(1285999,device,cfg);model.eval()
        with torch.no_grad():initial=float(objective(model.forward_details(batch['source']),batch,cfg['loss_weights'],.02)[0])
        timings=[]
        for step in range(1,129):
            tick=time.perf_counter();row=update(model,opt,batch,step,'P',cfg);torch.cuda.synchronize();timings.append(time.perf_counter()-tick)
            if step%16==0:print(json.dumps(dict(smoke_update=step,loss=row['loss'],seconds_per_update=timings[-1])),flush=True)
        model.eval()
        with torch.no_grad():final=float(objective(model.forward_details(batch['source']),batch,cfg['loss_weights'],.02)[0])
        assert final<initial*.95
        done('actual_128_update_learning',initial_loss=initial,final_loss=final,relative_improvement=1-final/initial,median_update_seconds=float(np.median(timings[8:])),peak_GPU_allocated_GiB=torch.cuda.max_memory_allocated()/2**30,preflight_weights_not_used_for_full_training=True)
        checkpoint(out/'resume_test.pth',model,opt,128,'P',1285999,{'role':'preflight_only'})
        row_a=update(model,opt,batch,129,'P',cfg);state_a={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        model2,opt2=create(1285999,device,cfg);step=restore(out/'resume_test.pth',model2,opt2,{'role':'preflight_only'},'P',1285999);assert step==128
        row_b=update(model2,opt2,batch,129,'P',cfg)
        resume_error=max(float((v-model2.state_dict()[k].detach().cpu()).abs().max()) for k,v in state_a.items())
        save(out/'resume_comparison.json',dict(maximum_parameter_difference=resume_error,loss_a=row_a['loss'],loss_b=row_b['loss']))
        assert resume_error==0 and row_a['loss']==row_b['loss']
        done('checkpoint_next_update_exact_resume',maximum_parameter_difference=resume_error,next_loss_difference=row_a['loss']-row_b['loss'])
        result=dict(passed=True,checks=rows,seconds=time.perf_counter()-start,source_identity=record(out/'source_identity.json'),full_training_updates=0)
        save(out/'verification.json',result);save(ROOT/'results/engineering_preflight.json',dict(**result,attempt=str(out)))
    except BaseException:
        save(out/'failure.json',dict(error=traceback.format_exc(),checks=rows,seconds=time.perf_counter()-start));raise

if __name__=='__main__':main()

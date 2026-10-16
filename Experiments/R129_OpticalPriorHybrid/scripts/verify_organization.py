"""Exact forward/backward, real-image and trace checks for the organized R129."""
import os,sys,traceback
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from common import *
import cv2,numpy as np,torch
from model.hybrid_v2 import Hybrid as Original
from model.organized import Hybrid as Organized
from model.organized.inference_policy import guard
from evaluate_real import guard as original_guard
from run_pilot import setup

def main():
    out=ROOT/'results/organization';out.mkdir(exist_ok=False)
    plan=load(ROOT/'config/organization_plan.json');pilot=load(ROOT/'config/plan.json')
    for item in plan['original_files']+plan['organized_files']:assert sha(item['path'])==item['sha256'],item['path']
    save(out/'started.json',dict(created_utc=now(),plan=record(ROOT/'config/organization_plan.json'),script=record(__file__)))
    kernels=np.load(ROOT/'data/measured_psf_bank.npz');setup(pilot['common_seed'])
    def model(cls,arm,step,device='cuda'):
        m=cls(torch.from_numpy(kernels['mean']),torch.from_numpy(kernels['candidates']),**pilot['arms'][arm]).to(device)
        path=ROOT/'runs'/arm/('initial.pth' if step==0 else 'step24.pth')
        m.load_state_dict(torch.load(path,map_location=device)['model'],strict=True)
        return m
    rows=[]
    # Include both batch size >1 and unequal/odd dimensions; check input gradients too.
    for arm in 'ABCD':
        for step in [0,24]:
            a=model(Original,arm,step);b=model(Organized,arm,step)
            assert a.state_dict().keys()==b.state_dict().keys()
            assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())
            base=torch.rand(2,1,65,73,device='cuda');xa=base.clone().requires_grad_();xb=base.clone().requires_grad_()
            a.train();b.train();ya=a(xa);yb=b(xb)
            assert torch.equal(ya,yb),(arm,step,'forward')
            ya.square().mean().backward();yb.square().mean().backward()
            assert torch.equal(xa.grad,xb.grad),(arm,step,'input gradient')
            ga=dict(a.named_parameters());gb=dict(b.named_parameters())
            for k in ga:
                assert (ga[k].grad is None)==(gb[k].grad is None),(k,'gradient presence')
                if ga[k].grad is not None:assert torch.equal(ga[k].grad,gb[k].grad),(arm,step,k)
            rows.append(dict(arm=arm,step=step,forward_exact=True,input_gradient_exact=True,all_parameter_gradients_exact=True,parameters_checked=len(ga)))
            print('Exact training behavior:',arm,step,flush=True)
            del a,b;torch.cuda.empty_cache()
    a=model(Original,'D',24);b=model(Organized,'D',24);a.eval();b.eval()
    boundary=[]
    with torch.no_grad():
        for value in [0.,.5,1.]:
            x=torch.full((1,1,64,66),value,device='cuda');assert torch.equal(a(x),b(x));boundary.append(value)
    panel=load(ROOT/'config/real_panel.json');real=[]
    cases=[dict(kind='sem',name=f"sem{x['exposure']}",source=x['source'],box=None) for x in panel['sem']]
    cases +=[dict(kind='motion',name=f"{x['sequence']}_{x['frame_index']:04d}",source=x['source'],box=x['box']) for x in panel['motion']]
    for case in cases:
        assert sha(case['source']['path'])==case['source']['sha256']
        raw=cv2.imread(case['source']['path'],0)
        if case['box']:
            x0,y0,x1,y1=case['box'];raw=raw[y0:y1,x0:x1]
        x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
        with torch.no_grad():
            old=original_guard(x,a(x));new=guard(x,b(x))
        assert torch.equal(old,new),case['name']
        arr=new[0,0].cpu().numpy();png=np.rint(arr*255).clip(0,255).astype(np.uint8)
        saved=ROOT/'results/real/D_24'/(case['name']+'.png')
        assert np.array_equal(png,cv2.imread(str(saved),0)),case['name']
        if case['kind']=='sem':assert np.array_equal(arr,np.load(saved.with_suffix('.npz'))['output'])
        real.append(dict(name=case['name'],shape=list(raw.shape),source=case['source'],old_new_float_exact=True,historical_png_exact=True,output_float_sha256=__import__('hashlib').sha256(arr.tobytes()).hexdigest()))
        print('Exact real output:',case['name'],flush=True)
    # Independently reconstruct old step states from its actual learned corrections.
    observed=[];corrections=[];conditioned=[]
    h1=a.prior.register_forward_hook(lambda module,args,result:corrections.append(result.detach().clone()))
    h2=a.optics.register_forward_hook(lambda module,args,result:conditioned.append(result[0].detach().clone()))
    raw=cv2.imread(panel['sem'][1]['source']['path'],0)[300:497,300:493]
    x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
    with torch.no_grad():
        old=a(x)
        details=b.forward_details(x,trace=True,step_observer=lambda step,state:observed.append((step,state)))
    h1.remove();h2.remove();assert torch.equal(old,details.output) and len(observed)==len(corrections)==4
    state=conditioned[0].repeat_interleave(4,-2).repeat_interleave(4,-1)
    trace=[];arrays={'input':raw.astype(np.float32)/255,'output':details.output[0,0].cpu().numpy()}
    for i,((step,current),correction) in enumerate(zip(observed,corrections)):
        before=state;state=(state+.25*torch.sigmoid(a.step_logits[i])*correction).clamp(0,1)
        assert step==i+1 and torch.equal(state,current)
        trace.append(dict(step=step,max_abs_update=float(abs(state-before).max()),mean_abs_update=float(abs(state-before).mean()),exact_original_state=True))
        arrays[f'step{step}']=current[0,0].cpu().numpy()
    with torch.no_grad():
        def mutate_copy(step,state):state.zero_()
        mutated=b.forward_details(x,step_observer=mutate_copy).output
        assert torch.equal(mutated,old)
    np.savez_compressed(out/'example_step_trace.npz',**arrays)
    for item in plan['original_files']+plan['organized_files']:assert sha(item['path'])==item['sha256']
    result=dict(completed_utc=now(),passed=True,source=record(__file__),plan=record(ROOT/'config/organization_plan.json'),new_training_updates=0,checkpoints=rows,constant_inputs=boundary,real_images=real,real_count=len(real),trace=trace,observer_mutation_does_not_change_output=True,original_files_unchanged=True,organized_module_hashes_unchanged=True,performance_improvement_not_claimed=True,scope='Exact equality on tested inputs and gradients; structural reorganization only, not new scientific qualification')
    save(out/'verification.json',result)
    print('All organization checks passed',flush=True)

if __name__=='__main__':
    try:main()
    except Exception:
        folder=ROOT/'results/organization'
        if folder.exists():
            with (folder/'failure.txt').open('x',encoding='utf-8') as f:f.write(traceback.format_exc())
        raise

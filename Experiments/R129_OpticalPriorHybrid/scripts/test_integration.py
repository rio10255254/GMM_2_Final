import os,sys,ast
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,torch
from torch import nn
from torch.nn import functional as F
from model.hybrid import Hybrid,MeasuredOptics
def main():
    p=load(ROOT/'config/plan.json');a=np.load(ROOT/'data/measured_psf_bank.npz');torch.manual_seed(p['common_seed']);torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
    mean=torch.from_numpy(a['mean']);bank=torch.from_numpy(a['candidates']);device='cuda';m=Hybrid(mean,bank).to(device);state=torch.load(p['source_checkpoint']['path'],map_location='cpu')['model'];m.initialize_from_r128(state);m.eval()
    results={};x=torch.rand(2,1,128,128,device=device)
    with torch.no_grad():
        opt,trace=m.optics(x,True,True);off,_=m.optics(x,False);assert torch.equal(off,x)
        assert (opt-x).abs().mean()>1e-5;assert torch.allclose(trace['weights'].sum(1),torch.ones(2,device=device));assert float(trace['beta'])>=.005
        const=torch.full_like(x,.4);c,_=m.optics(const,True);err=float((c-const).abs().max());assert err<1e-5
        k=torch.zeros(101,101,device=device);k[50,50]=1;unit=MeasuredOptics(k,k[None].repeat(4,1,1)).to(device);u,_=unit(x,True);deltaerr=float((u-x).abs().max());assert deltaerr<2e-5
        results.update(optical_active_change=float((opt-x).abs().mean()),constant_error=err,delta_psf_identity_error=deltaerr,weights=trace['weights'].cpu().tolist())
        legacy_path=Path(load(ROOT/'data/PSF_PROVENANCE.json')['source_model']['path']);tree=ast.parse(legacy_path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ShiftSafeUpsample'];scope=dict(torch=torch,nn=nn,F=F)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(legacy_path),'exec'),scope)
        aa=scope['ShiftSafeUpsample'](64,1).to(device);aa.conv.load_state_dict(m.prior.head.state_dict());h=torch.rand(2,64,16,16,device=device)
        actual=m.prior.head(F.conv2d(F.pad(F.interpolate(h,scale_factor=2,mode='bilinear',align_corners=False),(1,1,1,1),mode='reflect'),m.prior.blur_kernel,groups=64));expected=aa(h);aaerr=float((actual-expected).abs().max());assert aaerr==0
        results['AA_operator_exact_legacy_parity']=aaerr
        d=m.forward_details(x,True);assert d.output.shape==x.shape and torch.isfinite(d.output).all();m.prior.aa=False;b=m(x);m.prior.aa=True
        aadiff=float((b-d.output).abs().mean());assert aadiff>1e-7;results['AA_active_output_difference']=aadiff
    m.train();loss=m(x).square().mean();loss.backward();grads={name:float(param.grad.abs().sum()) for name,param in m.named_parameters() if param.grad is not None}
    assert all(torch.isfinite(param.grad).all() for param in m.parameters() if param.grad is not None)
    assert grads['optics.alpha']>0 and grads['optics.beta']>0 and grads['optics.gating.2.weight']>0 and grads['prior.head.weight']>0
    results['nonzero_gradients']={k:v for k,v in grads.items() if k.startswith('optics.') or k.startswith('prior.head')}
    ck=ROOT/'results/test_checkpoint.pth';ck.parent.mkdir(exist_ok=True);torch.save(m.state_dict(),ck);n=Hybrid(mean,bank).to(device);n.load_state_dict(torch.load(ck,map_location=device));m.eval();n.eval()
    with torch.no_grad():reloaderr=float((m(x)-n(x)).abs().max());assert reloaderr==0
    results['reload_exact']=True;results['test_scope']='mechanical/functional tests,notphysicalcalibrationorusefulness';results['passed']=True;results['source']=record(__file__)
    save(ROOT/'results/integration_tests.json',results);print(results)
if __name__=='__main__':main()

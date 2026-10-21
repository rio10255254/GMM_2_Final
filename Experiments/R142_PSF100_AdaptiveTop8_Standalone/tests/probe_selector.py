"""Controlled mechanical tests for 25->4 and 100->8 adaptive selection."""
from __future__ import annotations
import json,sys,tempfile
from pathlib import Path
import numpy as np,torch
from torch import nn
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from optical.adaptive_psf import AdaptivePSFCue

def bank(path,n):
    yy,xx=np.mgrid[-50:51,-50:51]
    kernels=[]
    for i in range(n):
        angle=(i/n)*np.pi
        ca,sa=np.cos(angle),np.sin(angle)
        u=ca*xx+sa*yy;v=-sa*xx+ca*yy
        major=1.0+3.0*((i%11)/10)
        minor=.75+1.25*((i//11)%9)/8
        k=np.exp(-.5*((u/major)**2+(v/minor)**2))
        kernels.append((k/k.sum()).astype('float32'))
    np.savez_compressed(path,all_kernels=np.stack(kernels))

def run(n,k,work):
    torch.manual_seed(147+n)
    p=work/f'synthetic_{n}.npz';bank(p,n)
    cue=AdaptivePSFCue(4,p,n,k,regularization=.03,beta_init=.08)
    cue.set_beta_scale(.6)
    x=torch.rand(2,4,160,160,requires_grad=True)
    y=cue(x)
    assert y.shape==x.shape and torch.isfinite(y).all()
    w=cue.last_sparse_weights.detach()
    assert (w>0).sum(1).tolist()==[k,k]
    assert torch.allclose(w.sum(1),torch.ones(2),atol=1e-6)
    cue.last_logits.retain_grad()
    loss=y.square().mean();loss.backward()
    unselected=~(w>0)
    unselected_grad=float(cue.last_logits.grad[unselected].abs().max())
    first_grad=float(cue.selector[0].weight.grad.abs().max())
    last_grad=float(cue.selector[-1].weight.grad.abs().max())
    assert unselected_grad>0 and first_grad>0 and last_grad>0

    # A separate supervised fixture proves a nonzero-initialized selector can
    # learn different choices for different image features. It is not a model
    # quality claim for measured PSFs.
    learner=AdaptivePSFCue(4,p,n,k,regularization=.03)
    labels=torch.tensor([0,n//3,2*n//3,n-1]*4,dtype=torch.long)
    templates=torch.eye(4)[torch.arange(16)%4].view(16,4,1,1)
    features=templates.expand(16,4,32,32).clone()+.03*torch.rand(16,4,32,32)
    opt=torch.optim.AdamW(learner.selector.parameters(),lr=.01)
    initial=None
    for step in range(151):
        opt.zero_grad(set_to_none=True)
        learner.select(features)
        l=learner.selector_loss(labels)
        if initial is None:initial=float(l)
        l.backward();opt.step()
    learner.select(features)
    predicted=learner.last_logits.argmax(1)
    topk=learner.last_indices
    accuracy=float((predicted==labels).float().mean())
    coverage=float((topk==labels[:,None]).any(1).float().mean())
    assert accuracy>=.95 and coverage==1.0
    return dict(bank_count=n,top_k=k,hard_nonzero_per_image=(w>0).sum(1).tolist(),
                unselected_logit_gradient=unselected_grad,first_layer_gradient=first_grad,
                last_layer_gradient=last_grad,supervised_initial_loss=initial,
                supervised_final_loss=float(l),fixture_accuracy=accuracy,
                fixture_topk_coverage=coverage,synthetic_bank_only=True)

def main():
    torch.set_num_threads(2)
    with tempfile.TemporaryDirectory(prefix='mosr_adaptive_psf_test_') as d:
        results=[run(25,4,Path(d)),run(100,8,Path(d))]
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()

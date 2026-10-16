"""Full R140-style network forward/backward for 25->4 and 100->8."""
import json,sys,tempfile
from pathlib import Path
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from model import Model
from utils import model_config
from probe_selector import bank

def run(n,k,work):
    torch.manual_seed(449+n)
    path=work/f'full_{n}.npz';bank(path,n)
    cfg=dict(model_config());cfg['psf_count']=n;cfg['psf_topk']=k
    cfg['psf_bank']=str(path);cfg['initial_prior_indices']=list(np.linspace(0,n-1,k,dtype=int))
    cfg['psf_regularization']=.03
    model=Model(cfg,ROOT).cuda().eval()
    seed=torch.load(ROOT/'weights/backbone_seed_from_R140v2.pth',map_location='cpu',weights_only=False)['backbone']
    state=model.state_dict()
    for name,value in seed.items():
        assert name in state and state[name].shape==value.shape
        state[name]=value
    model.load_state_dict(state,strict=True)
    model.refiner.optics.set_beta_scale(.5)
    x=torch.rand((2,1,320,320),device='cuda')
    out=model(x)
    cue=model.refiner.optics
    cue.last_logits.retain_grad()
    y=(out-x).square().mean();y.backward()
    chosen=cue.last_indices.detach().cpu().tolist()
    weights=cue.last_sparse_weights
    mask=(weights>0)
    other_grad=cue.last_logits.grad[~mask]
    result=dict(psf_count=n,top_k=k,output_shape=list(out.shape),finite=bool(torch.isfinite(out).all()),
                chosen=chosen,nonzero_per_image=mask.sum(1).cpu().tolist(),
                unselected_gradient_max=float(other_grad.abs().max()),
                selector_first_gradient=float(cue.selector[0].weight.grad.abs().max()),
                gradient_reached_all_candidates=bool(other_grad.abs().max()>0),
                synthetic_test_bank_only=True)
    assert result['finite'] and result['nonzero_per_image']==[k,k]
    assert result['gradient_reached_all_candidates'] and result['selector_first_gradient']>0
    return result

def main():
    torch.set_num_threads(4)
    with tempfile.TemporaryDirectory(prefix='mosr_psf_full_integration_') as d:
        result=[run(25,4,Path(d)),run(100,8,Path(d))]
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

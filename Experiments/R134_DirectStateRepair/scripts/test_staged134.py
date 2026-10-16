from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
from tiled import tiled_prior

def main():
    cfg=load(ROOT/'config/study.json');rows=[]
    for arm in ['A','C']:
        m=create(arm,cfg['seeds'][0]);torch.nn.init.normal_(m.prior.head.weight,0,.01);torch.nn.init.normal_(m.prior.head.bias,0,.01);m.eval()
        for shape in [(193,201),(221,227)]:
            x=torch.rand(1,1,*shape,device='cuda')
            with torch.no_grad():a=m(x);b=m(x,prior_runner=lambda prior,f:tiled_prior(prior,f,64,16))
            err=float((a-b).abs().max());assert err<1e-6;rows.append(dict(arm=arm,shape=shape,max_difference=err,nonzero_output_change=float((a-x).abs().mean())))
    save(ROOT/'results/staged_verification.json',dict(passed=True,cases=rows,scope='Nonzero randomized prior, full versus finite-context localprior. Keep optics/features/state global for realfullfields.',source=record(__file__)))
    print('StagedA/C parity verified',flush=True)
if __name__=='__main__':main()

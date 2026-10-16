"""Select the classical regularization on synthetic validation PSNR only."""
from pathlib import Path
import sys,time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from study import save
from benchmark_core import prepare,evaluate
from inference_methods import Wiener


def main():
    cfg,bank,optics=prepare()
    candidates=sorted(set([0.,.0565,*np.logspace(-6,0,25).tolist()]))
    scores={str(v):[] for v in candidates}
    models=[Wiener(v).cuda().eval() for v in candidates]
    with torch.inference_mode():
        for index in range(128):
            batch=bank.batch('dev',index,'cuda');truth=batch['target'][...,144:240,144:240].cpu().numpy().astype(np.float64)
            for value,model in zip(candidates,models):
                pred=model(batch['source'],None,optics)[...,144:240,144:240].cpu().numpy().astype(np.float64)
                mse=((pred-truth)**2).mean((1,2,3))
                scores[str(value)].append(float(np.mean(-10*np.log10(np.maximum(mse,1e-30)))))
            if (index+1)%16==0:print('WIENER SYNTHETIC VALIDATION',index+1,'/128',flush=True)
    rows=[{'regularization':value,'mean_PSNR_dB':float(np.mean(scores[str(value)]))} for value in candidates]
    best=max(rows,key=lambda r:r['mean_PSNR_dB'])
    result={**best,'method':'Wiener','selection_set':'128 fixed synthetic validation scenes, 512 images',
            'operator':'fixed mean of the measured 25 PSFs','formula':'conj(H)/(abs(H)^2 + regularization)',
            'boundary':'50-pixel reflection','extra_contrast_normalization':False,'output_clipping':False,
            'candidates':rows,'real_data_used_for_selection':False}
    save(ROOT/'config/wiener_selected.json',result)
    test=evaluate(Wiener(best['regularization']).cuda(),bank,optics,'test',with_image_metrics=True)
    save(ROOT/'results/synthetic/Wiener.json',test)
    print('WIENER_SELECTED',best,flush=True)


if __name__=='__main__':main()

"""Shared original data/loss definitions and FP32 benchmark execution."""
from pathlib import Path
import sys,math,time
import numpy as np
import torch
from study import ROOT,PACK,TRAIN_SEED,training_config
if str(PACK) not in sys.path:sys.path.insert(0,str(PACK))
from core.dataset import Bank
from core.losses import stage_terms,robust_gray
from core.runtime import setup
from models.fullres_psf import FullResPSF


def prepare():
    setup(TRAIN_SEED)
    cfg=training_config()
    bank=Bank(cfg)
    optics=FullResPSF(PACK/'calibration/psf25_bank.npz').cuda()
    return cfg,bank,optics


def objective(output,batch,optics):
    terms=stage_terms(output,batch)
    lo,hi=batch['observation_core']
    terms['observation']=robust_gray((optics.blur(output,batch['operator_psf_indices'])-batch['source'])[...,lo:hi,lo:hi])
    total=terms['image']+.2*terms['gradient']+.2*terms['pair_output']+.2*terms['boundary']+.01*terms['observation']
    return total,terms


def lr_for(step,cfg):
    opt=cfg['optimizer'];warm=cfg['warmup'];total=cfg['updates']
    if step<=warm:return opt['max_lr']*step/warm
    return opt['min_lr']+.5*(opt['max_lr']-opt['min_lr'])*(1+math.cos(math.pi*(step-warm)/(total-warm)))


def batch_for_step(bank,step):
    # The user selected an appropriate common epoch budget: 16 full data epochs.
    epoch=((step-1)//512)%16
    index=int(bank.order(epoch)[(step-1)%512])
    return bank.batch('train',index,'cuda',epoch),epoch,index


def losses_as_numbers(total,terms):
    return {'task':float(total.detach()),**{key:float(value.detach()) for key,value in terms.items()}}


@torch.inference_mode()
def evaluate(model,bank,optics,split,limit=None,with_image_metrics=False):
    from skimage.metrics import structural_similarity
    model.eval();rows=[]
    count=bank.cfg['splits'][split] if limit is None else limit
    for index in range(count):
        batch=bank.batch(split,index,'cuda')
        output=model(batch['source'],batch['operator_psf_indices'],optics)
        total,terms=objective(output,batch,optics)
        row={'index':index,**losses_as_numbers(total,terms)}
        if not all(np.isfinite(v) for v in row.values()):raise FloatingPointError('Nonfinite synthetic evaluation')
        if with_image_metrics:
            p=output.detach().cpu().numpy()[:,0];target=batch['target'].cpu().numpy()[:,0]
            lo,hi=batch['core'];psnr=[];ssim=[];full=[]
            for image,truth in zip(p,target):
                a=image[lo:hi,lo:hi].astype(np.float64);b=truth[lo:hi,lo:hi].astype(np.float64)
                mse=np.mean((a-b)**2)
                psnr.append(float(-10*np.log10(max(mse,1e-30))))
                ssim.append(float(structural_similarity(a,b,data_range=1,gaussian_weights=True,sigma=1.5,use_sample_covariance=False)))
                full.append(float(-10*np.log10(max(np.mean((image.astype(np.float64)-truth.astype(np.float64))**2),1e-30))))
            row.update(PSNR_core_dB=float(np.mean(psnr)),SSIM_core=float(np.mean(ssim)),PSNR_full_dB=float(np.mean(full)))
        rows.append(row)
    keys=[k for k in rows[0] if k!='index']
    return {'split':split,'parents':count,'mean':{k:float(np.mean([r[k] for r in rows])) for k in keys},'parents_detail':rows}

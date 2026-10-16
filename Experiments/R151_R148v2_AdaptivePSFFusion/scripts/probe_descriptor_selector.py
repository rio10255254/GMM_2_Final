"""Test whether the input can predict physically relevant PSF width/halo descriptors."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,torch
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from model import Model
from optical.adaptive_fourier_psf import WeightEstimator
from utils import model_config,now,save,setup,train_config

def predict(model,estimator,images):
 logits=estimator(images);weights=torch.softmax(logits/model.psf_fusion.temperature,1);return weights@model.psf_fusion.psf_descriptors

def evaluate(model,estimator,bank,device):
 model.eval();predicted=[];target=[]
 with torch.inference_mode():
  for index in range(128):
   batch=bank.batch('dev',index,device);labels=batch['actual_psf_indices'];valid=(labels>=0)&(labels<25);predicted.append(predict(model,estimator,batch['source'])[valid].cpu());target.append(model.psf_fusion.psf_descriptors[labels[valid]].cpu())
 p=torch.cat(predicted).double();t=torch.cat(target).double();mse=float(F.mse_loss(p,t));mae=float((p-t).abs().mean());corr=[]
 for i in range(3):
  a=p[:,i]-p[:,i].mean();b=t[:,i]-t[:,i].mean();corr.append(float((a*b).sum()/torch.sqrt(a.square().sum()*b.square().sum()).clamp_min(1e-12)))
 return dict(samples=len(p),standardized_mse=mse,standardized_mae=mae,descriptor_correlations=corr,predicted_std=p.std(0).tolist(),target_std=t.std(0).tolist())

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--updates',type=int,default=1024);parser.add_argument('--seed',type=int,default=1512401);parser.add_argument('--lr',type=float,default=.001);a=parser.parse_args();setup(a.seed);cfg=train_config();bank=Bank(cfg);device='cuda' if torch.cuda.is_available() else 'cpu';model=Model(model_config(),ROOT).to(device);estimator=WeightEstimator(25,24,1,raw_input=True).to(device);opt=torch.optim.AdamW(estimator.parameters(),lr=a.lr,weight_decay=1e-5);initial=evaluate(model,estimator,bank,device);logs=[]
 for step in range(1,a.updates+1):
  epoch=(step-1)//512;index=int(bank.order(epoch)[(step-1)%512]);batch=bank.batch('train',index,device,epoch);labels=batch['actual_psf_indices'];valid=(labels>=0)&(labels<25);p=predict(model,estimator,batch['source'])[valid];target=model.psf_fusion.psf_descriptors[labels[valid]];loss=F.mse_loss(p,target);opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(estimator.parameters(),1.0,error_if_nonfinite=True);opt.step()
  if step%64==0:logs.append(dict(step=step,loss=float(loss)));print('DESCRIPTOR',step,float(loss),flush=True)
 final=evaluate(model,estimator,bank,device);result=dict(status='complete',seed=a.seed,updates=a.updates,lr=a.lr,initial=initial,final=final,not_a_model_checkpoint=True,log=logs,completed_utc=now());save(ROOT/'results/descriptor_selector_learnability_probe.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

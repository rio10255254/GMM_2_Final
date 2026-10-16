"""Test PSF estimation from the R148v2 multi-scale context features."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import torch
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from model import Model
from utils import model_config,now,save,setup,train_config

def logits_and_descriptor(model,images):
 unknown=torch.full((images.shape[0],),-1,dtype=torch.long,device=images.device)
 _,_,context=model.base_context(images,unknown);logits=model.psf_fusion.estimator(context,images);weights=torch.softmax(logits/model.psf_fusion.temperature,1);return logits,weights@model.psf_fusion.psf_descriptors

def evaluate(model,bank,device):
 model.eval();losses=[];descriptor_losses=[];correct1=correct5=count=0;predicted=[];targets=[]
 with torch.inference_mode():
  for index in range(128):
   batch=bank.batch('dev',index,device);labels=batch['actual_psf_indices'];valid=(labels>=0)&(labels<25);logits,desc=logits_and_descriptor(model,batch['source']);logits=logits[valid];desc=desc[valid];labels=labels[valid];target=model.psf_fusion.psf_descriptors[labels];losses.append(float(F.cross_entropy(logits,labels)));descriptor_losses.append(float(F.mse_loss(desc,target)));order=logits.topk(5,1).indices;correct1+=int((order[:,0]==labels).sum());correct5+=int((order==labels[:,None]).any(1).sum());count+=len(labels);predicted.append(desc.cpu());targets.append(target.cpu())
 p=torch.cat(predicted).double();t=torch.cat(targets).double();corr=[]
 for i in range(3):
  a=p[:,i]-p[:,i].mean();b=t[:,i]-t[:,i].mean();corr.append(float((a*b).sum()/torch.sqrt(a.square().sum()*b.square().sum()).clamp_min(1e-12)))
 return dict(samples=count,cross_entropy=sum(losses)/len(losses),top1_accuracy=correct1/count,top5_accuracy=correct5/count,descriptor_mse=sum(descriptor_losses)/len(descriptor_losses),descriptor_correlations=corr,predicted_descriptor_std=p.std(0).tolist())

def main():
 p=argparse.ArgumentParser();p.add_argument('--updates',type=int,default=512);p.add_argument('--seed',type=int,default=1512501);p.add_argument('--lr',type=float,default=.001);p.add_argument('--identity-weight',type=float,default=.25);a=p.parse_args();setup(a.seed);cfg=train_config();bank=Bank(cfg);device='cuda' if torch.cuda.is_available() else 'cpu';model=Model(model_config(),ROOT).to(device);params=list(model.context.parameters())+list(model.psf_fusion.estimator.parameters());opt=torch.optim.AdamW(params,lr=a.lr,weight_decay=1e-5);initial=evaluate(model,bank,device);logs=[]
 for step in range(1,a.updates+1):
  epoch=(step-1)//512;index=int(bank.order(epoch)[(step-1)%512]);batch=bank.batch('train',index,device,epoch);labels=batch['actual_psf_indices'];valid=(labels>=0)&(labels<25);logits,desc=logits_and_descriptor(model,batch['source']);logits=logits[valid];desc=desc[valid];labels=labels[valid];target=model.psf_fusion.psf_descriptors[labels];identity=F.cross_entropy(logits,labels);descriptor=F.mse_loss(desc,target);loss=a.identity_weight*identity+descriptor;opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0,error_if_nonfinite=True);opt.step()
  if step%64==0:logs.append(dict(step=step,loss=float(loss),identity=float(identity),descriptor=float(descriptor),top1=float((logits.argmax(1)==labels).float().mean())));print('CONTEXT_SELECTOR',step,float(loss),float(identity),float(descriptor),logs[-1]['top1'],flush=True)
 final=evaluate(model,bank,device);result=dict(status='complete',seed=a.seed,updates=a.updates,lr=a.lr,identity_weight=a.identity_weight,initial=initial,final=final,not_a_model_checkpoint=True,log=logs,completed_utc=now());save(ROOT/'results/context_selector_learnability_probe.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

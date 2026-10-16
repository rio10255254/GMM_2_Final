"""Train the selector on matched clean-scene views blurred by known PSFs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import torch
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from model import Model
from utils import model_config,now,save,setup,train_config

def selector_logits(model,images):
 unknown=torch.full((images.shape[0],),-1,dtype=torch.long,device=images.device);_,_,context=model.base_context(images,unknown);return model.psf_fusion.estimator(context,images)

def metrics(logits,labels):
 order=logits.topk(5,1).indices;return int((order[:,0]==labels).sum()),int((order==labels[:,None]).any(1).sum()),len(labels)

def evaluate_controlled(model,bank,device,parents=16):
 model.eval();ce=[];top1=top5=count=0
 with torch.inference_mode():
  for parent in range(parents):
   target=bank.batch('dev',parent,device)['target'][0:1]
   for start in range(0,25,5):
    labels=torch.arange(start,min(25,start+5),device=device);clean=target.repeat(len(labels),1,1,1);blurred=model.optics.blur(clean,labels);logits=selector_logits(model,blurred);ce.append(float(F.cross_entropy(logits,labels)));a,b,n=metrics(logits,labels);top1+=a;top5+=b;count+=n
 return dict(samples=count,cross_entropy=sum(ce)/len(ce),top1_accuracy=top1/count,top5_accuracy=top5/count)

def evaluate_existing(model,bank,device):
 model.eval();ce=[];top1=top5=count=0
 with torch.inference_mode():
  for parent in range(128):
   batch=bank.batch('dev',parent,device);labels=batch['actual_psf_indices'];valid=(labels>=0)&(labels<25);labels=labels[valid];logits=selector_logits(model,batch['source'])[valid];ce.append(float(F.cross_entropy(logits,labels)));a,b,n=metrics(logits,labels);top1+=a;top5+=b;count+=n
 return dict(samples=count,cross_entropy=sum(ce)/len(ce),top1_accuracy=top1/count,top5_accuracy=top5/count)

def main():
 p=argparse.ArgumentParser();p.add_argument('--updates',type=int,default=512);p.add_argument('--seed',type=int,default=1512601);p.add_argument('--lr',type=float,default=.001);p.add_argument('--noise-gray',type=float,default=.5);a=p.parse_args();setup(a.seed);cfg=train_config();bank=Bank(cfg);device='cuda' if torch.cuda.is_available() else 'cpu';model=Model(model_config(),ROOT).to(device);params=list(model.context.parameters())+list(model.psf_fusion.estimator.parameters());opt=torch.optim.AdamW(params,lr=a.lr,weight_decay=1e-5);initial_controlled=evaluate_controlled(model,bank,device,8);initial_existing=evaluate_existing(model,bank,device);logs=[]
 for step in range(1,a.updates+1):
  epoch=(step-1)//512;parent=int(bank.order(epoch)[(step-1)%512]);target=bank.batch('train',parent,device,epoch)['target'];labels=(torch.arange(4,device=device)+(step-1)*4)%25;blurred=model.optics.blur(target,labels)
  if a.noise_gray>0:
   generator=torch.Generator(device=device).manual_seed(a.seed*100000+step);blurred=(blurred+torch.randn(blurred.shape,generator=generator,device=device)*(a.noise_gray/255)).clamp(0,1)
  logits=selector_logits(model,blurred);weights=torch.softmax(logits/model.psf_fusion.temperature,1);predicted=weights@model.psf_fusion.psf_descriptors;desired=model.psf_fusion.psf_descriptors[labels];identity=F.cross_entropy(logits,labels);descriptor=F.mse_loss(predicted,desired);loss=identity+.25*descriptor;opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0,error_if_nonfinite=True);opt.step()
  if step%64==0:logs.append(dict(step=step,loss=float(loss),identity=float(identity),descriptor=float(descriptor),top1=float((logits.argmax(1)==labels).float().mean())));print('MATCHED_SELECTOR',step,float(loss),float(identity),float(descriptor),logs[-1]['top1'],flush=True)
 final_controlled=evaluate_controlled(model,bank,device,16);final_existing=evaluate_existing(model,bank,device);result=dict(status='complete',seed=a.seed,updates=a.updates,lr=a.lr,noise_gray=a.noise_gray,initial_controlled=initial_controlled,final_controlled=final_controlled,initial_existing=initial_existing,final_existing=final_existing,not_a_formal_model=True,log=logs,completed_utc=now());save(ROOT/'results/matched_selector_pretrain_probe.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

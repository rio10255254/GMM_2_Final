"""Check whether four diverse PSF basis groups are identifiable."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import torch
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from optical.adaptive_fourier_psf import WeightEstimator
from utils import now,save,setup,train_config

LABELS=torch.tensor([0,0,0,0,0,2,3,3,3,2,3,3,3,3,2,3,1,3,3,3,1,1,1,1,3],dtype=torch.long)

def mapped(labels,device):
 valid=(labels>=0)&(labels<25);return valid,LABELS.to(device)[labels[valid].long()]

def evaluate(estimator,bank,device,class_weight=None):
 estimator.eval();losses=[];correct=0;count=0;matrix=torch.zeros(4,4,dtype=torch.long)
 with torch.inference_mode():
  for index in range(128):
   batch=bank.batch('dev',index,device);valid,target=mapped(batch['actual_psf_indices'],device);logits=estimator(batch['source'])[valid];losses.append(float(F.cross_entropy(logits,target,weight=class_weight)));pred=logits.argmax(1);correct+=int((pred==target).sum());count+=len(target)
   for a,b in zip(target.cpu(),pred.cpu()):matrix[a,b]+=1
 recall=[float(matrix[i,i]/matrix[i].sum()) for i in range(4)]
 return dict(samples=count,cross_entropy=sum(losses)/len(losses),top1_accuracy=correct/count,balanced_accuracy=sum(recall)/4,per_class_recall=recall,confusion=matrix.tolist())

def main():
 p=argparse.ArgumentParser();p.add_argument('--updates',type=int,default=512);p.add_argument('--seed',type=int,default=1512301);p.add_argument('--lr',type=float,default=.001);p.add_argument('--balanced',action='store_true');a=p.parse_args();setup(a.seed);cfg=train_config();bank=Bank(cfg);device='cuda' if torch.cuda.is_available() else 'cpu';estimator=WeightEstimator(4,24).to(device);opt=torch.optim.AdamW(estimator.parameters(),lr=a.lr,weight_decay=1e-5);class_weight=torch.tensor([1/5,1/5,1/3,1/12],device=device) if a.balanced else None;initial=evaluate(estimator,bank,device,class_weight);logs=[]
 for step in range(1,a.updates+1):
  epoch=(step-1)//512;index=int(bank.order(epoch)[(step-1)%512]);batch=bank.batch('train',index,device,epoch);valid,target=mapped(batch['actual_psf_indices'],device);logits=estimator(batch['source'])[valid];loss=F.cross_entropy(logits,target,weight=class_weight);opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(estimator.parameters(),1.0,error_if_nonfinite=True);opt.step()
  if step%64==0:logs.append(dict(step=step,loss=float(loss),accuracy=float((logits.argmax(1)==target).float().mean())));print('BASIS4',step,float(loss),logs[-1]['accuracy'],flush=True)
 final=evaluate(estimator,bank,device,class_weight);result=dict(status='complete',balanced_loss=a.balanced,basis_medoids=[2,23,5,13],basis_members=[[0,1,2,3,4],[16,20,21,22,23],[5,9,14],[6,7,8,10,11,12,13,15,17,18,19,24]],initial=initial,final=final,updates=a.updates,lr=a.lr,seed=a.seed,not_a_model_checkpoint=True,log=logs,completed_utc=now());save(ROOT/'results'/('basis4_selector_balanced_probe.json' if a.balanced else 'basis4_selector_learnability_probe.json'),result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

"""Isolate whether the frozen 25-PSF data contain learnable PSF identity cues."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch.nn import functional as F

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from optical.adaptive_fourier_psf import WeightEstimator
from utils import now,save,setup,train_config,verify_bank_lock


def evaluate(estimator,bank,device,limit=128):
    estimator.eval();losses=[];correct1=0;correct5=0;count=0;entropies=[]
    with torch.inference_mode():
        for index in range(limit):
            batch=bank.batch("dev",index,device);labels=batch["actual_psf_indices"]
            valid=(labels>=0)&(labels<25);logits=estimator(batch["source"])[valid];labels=labels[valid]
            if not len(labels):continue
            losses.append(float(F.cross_entropy(logits,labels)))
            order=logits.topk(5,dim=1).indices
            correct1+=int((order[:,0]==labels).sum());correct5+=int((order==labels[:,None]).any(1).sum());count+=len(labels)
            weights=torch.softmax(logits,1);entropies.extend((-(weights*torch.log(weights.clamp_min(1e-8))).sum(1)).cpu().tolist())
    return {"samples":count,"cross_entropy":sum(losses)/len(losses),"top1_accuracy":correct1/count,"top5_accuracy":correct5/count,"mean_entropy":sum(entropies)/len(entropies)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--updates",type=int,default=512);parser.add_argument("--seed",type=int,default=1512201);parser.add_argument("--lr",type=float,default=0.001);args=parser.parse_args()
    setup(args.seed);verify_bank_lock();tc=train_config();bank=Bank(tc);device="cuda" if torch.cuda.is_available() else "cpu";estimator=WeightEstimator(25,24,1,raw_input=True).to(device)
    optimizer=torch.optim.AdamW(estimator.parameters(),lr=args.lr,weight_decay=1e-5)
    initial=evaluate(estimator,bank,device);logs=[];estimator.train()
    for step in range(1,args.updates+1):
        epoch=(step-1)//512;index=int(bank.order(epoch)[(step-1)%512]);batch=bank.batch("train",index,device,epoch);labels=batch["actual_psf_indices"]
        valid=(labels>=0)&(labels<25);logits=estimator(batch["source"])[valid];labels=labels[valid];loss=F.cross_entropy(logits,labels)
        optimizer.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(estimator.parameters(),1.0,error_if_nonfinite=True);optimizer.step()
        if step%64==0 or step==args.updates:
            top1=float((logits.argmax(1)==labels).float().mean());logs.append({"step":step,"loss":float(loss),"top1":top1});print("SELECTOR",step,args.updates,float(loss),top1,flush=True)
    final=evaluate(estimator,bank,device)
    result={"status":"complete","not_a_model_checkpoint":True,"seed":args.seed,"updates":args.updates,"lr":args.lr,"initial":initial,"final":final,"log":logs,"completed_utc":now()}
    save(ROOT/"results/selector_learnability_probe.json",result);print(json.dumps(result,indent=2))


if __name__=="__main__":main()

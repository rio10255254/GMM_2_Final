"""CPU audit of weighted objective gradient sizes and conflicts on two fixed dev scenes."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys
import numpy as np,pandas as pd,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from dataset import Bank
from losses import stage_terms,robust_gray
from model import Model
from utils import load,save,sha,model_config,train_config
from verify_package import verify_source_lock
OUT=ROOT/'results/training_deep_dive';NAMES=('image','gradient','pair_output','boundary','observation')
def dot(a,b):return sum(float((x.double()*y.double()).sum()) for x,y in zip(a,b))
def main():
 verify_source_lock();torch.set_num_threads(6);cfg=train_config();mc=model_config();latest=load(ROOT/'runs/formal_8192/latest.json');cp=torch.load(latest['path'],map_location='cpu',weights_only=False);model=Model(mc,ROOT).eval();model.load_state_dict(cp['model']);bank=Bank(cfg);params=[p for p in model.parameters() if p.requires_grad];rows=[];cos=[]
 for index in (3,4):
  b=bank.batch('dev',index,'cpu');_,states=model(b['source'],b['operator_psf_indices'],True);parts={k:states[0].sum()*0 for k in NAMES[:-1]}
  for weight,state in zip(cfg['stage_weights'],states):
   terms=stage_terms(state,b)
   for k in parts:parts[k]=parts[k]+weight*terms[k]*cfg['loss'][k]
  predicted=model.optics.blur(states[-1],b['operator_psf_indices']);lo,hi=b['observation_core'];parts['observation']=robust_gray((predicted-b['source'])[...,lo:hi,lo:hi])*cfg['loss']['observation'];grads={}
  for n,name in enumerate(NAMES):
   values=torch.autograd.grad(parts[name],params,retain_graph=n<len(NAMES)-1,allow_unused=True);values=[torch.zeros_like(p) if g is None else g.detach() for g,p in zip(values,params)];grads[name]=values;norm=dot(values,values)**.5;rows.append(dict(index=index,category=b['category'],component=name,weighted_value=float(parts[name]),gradient_L2=norm))
  for i,a in enumerate(NAMES):
   for bb in NAMES[i+1:]:
    denom=(dot(grads[a],grads[a])*dot(grads[bb],grads[bb]))**.5;cos.append(dict(index=index,category=b['category'],left=a,right=bb,cosine=dot(grads[a],grads[bb])/denom if denom else None))
  print('GRADIENT_AUDIT',index,b['category'],flush=True)
 pd.DataFrame(rows).to_csv(OUT/'objective_gradient_norms.csv',index=False);pd.DataFrame(cos).to_csv(OUT/'objective_gradient_cosines.csv',index=False);result=dict(snapshot_utc=datetime.now(timezone.utc).isoformat(),checkpoint_step=latest['step'],checkpoint_sha256=latest['sha256'],samples=[dict(index=3,category='irregular_curved'),dict(index=4,category='dense_close_structures')],norms=rows,cosines=cos,scope='Two fixed synthetic dev parents, CPU frozen-checkpoint diagnostic; not a full-training gradient census.');save(OUT/'objective_gradient_audit.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

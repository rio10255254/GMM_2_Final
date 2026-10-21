"""Fair frozen R148v2/R150 comparison on the exact R150 dev and test banks."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
import numpy as np,pandas as pd,torch
ROOT=Path(__file__).resolve().parents[1];R148=Path(r'D:\GMM_2_Final\Experiments\R148v2_HybridContextNativePSF');sys.path.insert(0,str(ROOT))
from dataset import Bank
from losses import objective,boundary_coordinates
from model import Model
from utils import load,save,sha,setup,model_config,train_config,verify_data_lock
def checkpoint(root):
 done=load(root/'runs/formal_8192/training_complete.json');p=Path(done['checkpoint']['path']);assert done['updates']==8192 and sha(p)==done['checkpoint']['sha256'];return p,done['checkpoint']
def assess(name,path,bank,cfg,split):
 cp=torch.load(path,map_location='cpu',weights_only=False);m=Model(model_config(),ROOT).cuda().eval();m.load_state_dict(cp['model'],strict=True);rows=[]
 with torch.inference_mode():
  for index in range(cfg['splits'][split]):
   b=bank.batch(split,index,'cuda');_,states=m(b['source'],b['operator_psf_indices'],True);loss,t=objective(states,b,m,cfg,'global');lo,hi=b['core'];pred=states[-1][...,lo:hi,lo:hi];target=b['target'][...,lo:hi,lo:hi];ps,pr=boundary_coordinates(pred,b['sdf'],b['geometry_valid']);ts,tr=boundary_coordinates(target,b['sdf'],b['geometry_valid']);v=b['geometry_valid'];rows.append(dict(model=name,split=split,index=index,parent_id=b['parent_id'],category=b['category'],loss=float(loss),**{k:float(x) for k,x in t.items()},signed_boundary_delta_px=float((ps[v]-ts[v]).mean()) if v.any() else None,spread_boundary_delta_px=float((pr[v]-tr[v]).mean()) if v.any() else None))
 return rows
def main():
 setup(1500999);data=verify_data_lock();cfg=train_config();bank=Bank(cfg);p150,r150=checkpoint(ROOT);p148,r148=checkpoint(R148);rows=[]
 for split in ('dev','test'):
  rows+=assess('R148v2',p148,bank,cfg,split);rows+=assess('R150',p150,bank,cfg,split)
 df=pd.DataFrame(rows);out=ROOT/'results/training_analysis';out.mkdir(parents=True,exist_ok=True);df.to_csv(out/'common_bank_rows.csv',index=False);metrics=['loss','image','gradient','pair_output','boundary_global','boundary_local','observation','signed_boundary_delta_px','spread_boundary_delta_px'];summary=df.groupby(['split','model','category'])[metrics].mean().reset_index();summary.to_csv(out/'common_bank_category_summary.csv',index=False)
 comparison=[]
 for split in ('dev','test'):
  for scope,indices in [('all',None),('matched',set(df[(df.split==split)&(df.category=='matched_nine_circles')].index))]:
   part=df[df.split==split]
   if scope=='matched':part=part[part.category=='matched_nine_circles']
   else:part=part[part.category!='matched_nine_circles'] if scope=='unchanged' else part
   pivot=part.pivot(index='index',columns='model',values=metrics)
   row=dict(split=split,scope=scope,parents=len(pivot))
   for metric in metrics:
    a=pivot[(metric,'R148v2')];b=pivot[(metric,'R150')];row['R148v2_'+metric]=float(a.mean());row['R150_'+metric]=float(b.mean());row['R150_minus_R148v2_'+metric]=float((b-a).mean())
   comparison.append(row)
  part=df[(df.split==split)&(df.category!='matched_nine_circles')];pivot=part.pivot(index='index',columns='model',values=metrics);row=dict(split=split,scope='unchanged',parents=len(pivot))
  for metric in metrics:
   a=pivot[(metric,'R148v2')];b=pivot[(metric,'R150')];row['R148v2_'+metric]=float(a.mean());row['R150_'+metric]=float(b.mean());row['R150_minus_R148v2_'+metric]=float((b-a).mean())
  comparison.append(row)
 comp=pd.DataFrame(comparison);comp.to_csv(out/'common_bank_comparison.csv',index=False)
 updates=(ROOT/'runs/formal_8192/updates.jsonl').read_bytes();u=[json.loads(x) for x in updates.splitlines()];assert [x['step'] for x in u]==list(range(1,8193));dev=[]
 for p in [ROOT/'runs/formal_8192/dev_initial.json']+sorted(ROOT.glob('runs/formal_8192/dev_[0-9][0-9][0-9][0-9][0-9].json')):
  d=load(p);dev.append(dict(step=0 if p.name=='dev_initial.json' else int(p.stem.split('_')[1]),mean_loss=d['mean_loss']))
 pd.DataFrame(dev).to_csv(out/'dev_curve.csv',index=False);result=dict(status='complete',snapshot_utc=datetime.now(timezone.utc).isoformat(),checkpoint_R150=r150,checkpoint_R148v2=r148,data_manifest_sha256=data['manifest_sha256'],updates=8192,updates_sha256=hashlib.sha256(updates).hexdigest(),steps_contiguous=True,dev_curve=dev,common_bank=comparison)
 save(out/'summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

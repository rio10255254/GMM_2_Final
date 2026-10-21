"""Inspectable scratch-only training, with matching probe and formal paths."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.network import build_model
from training.dataset import Scenes,FamilyOrder,flatten
from training.objectives import objective,location_xy,gradient,per_scene
from inference.run import tiled,read,write
CONFIG=json.loads((ROOT/'config/experiment.json').read_text())

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(payload,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)
def history_csv(path,rows):
    columns=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
def schedule(epoch,mode,epochs):
    if mode=='formal':
        matches=[s for s in CONFIG['training']['stages'] if s['epochs'][0]<=epoch<=s['epochs'][1]]
        if len(matches)!=1:raise ValueError(f'Expected one configured stage for epoch {epoch}')
        return matches[0]['active'][-1]
    warm=max(1,epochs//3)
    return 'geometry' if epoch<=warm else 'action' if epoch<=2*warm else 'detail'
def workers_init(_):
    cv2.setNumThreads(1);torch.set_num_threads(1)
def loader(dataset,batch,workers,train,seed):
    kw={'dataset':dataset,'batch_size':batch,'num_workers':workers,'pin_memory':True,'worker_init_fn':workers_init}
    if train:kw['sampler']=FamilyOrder(dataset,seed)
    if workers:kw.update(persistent_workers=True,prefetch_factor=2)
    return DataLoader(**kw)

@torch.inference_mode()
def validate(model,device,limit=96):
    ds=Scenes('validation',epoch=0,limit=limit);rows=[]
    for raw in loader(ds,4,0,False,0):
        b=flatten(raw,device);d=model.forward_details(b['source'])
        raw_xy,position_confidence=location_xy(b['source'],b['target']);out_xy,_=location_xy(d.output,b['target'])
        rg=gradient(b['source']-b['target']);og=gradient(d.output-b['target'])
        per={'raw_mae_gray':per_scene((b['source']-b['target']).abs())*255,
             'output_mae_gray':per_scene((d.output-b['target']).abs())*255,
             'raw_gradient_error':per_scene(rg[0].abs()+rg[1].abs()),
             'output_gradient_error':per_scene(og[0].abs()+og[1].abs()),
             'raw_xy_error_px':raw_xy.norm(dim=1),'output_xy_error_px':out_xy.norm(dim=1),
             'output_change_gray':per_scene((d.output-b['source']).abs())*255,
             'sdf_error_px':per_scene((d.sdf-b['sdf'].clamp(-16,16)).abs(),torch.exp(-b['sdf'].abs()/3))}
        for i in range(b['source'].shape[0]):
            row={'role':raw['role'][i//2],'family':raw['family'][i//2],**{k:float(v[i]) for k,v in per.items()}}
            if bool(b['flat'][i]):
                row['raw_xy_error_px']=None;row['output_xy_error_px']=None
            rows.append(row)
    grouped={}
    for role in ('all','edge','textured_edge','identity','flat_negative'):
        selected=rows if role=='all' else [r for r in rows if r['role']==role]
        if selected:
            grouped[role]={'views':len(selected)}
            for key in rows[0]:
                if key in ('role','family'):continue
                values=[r[key] for r in selected if r[key] is not None]
                grouped[role][key]=float(np.mean(values)) if values else None
    return {'status':'complete','development_validation':True,'groups':grouped,'rows':rows}

@torch.inference_mode()
def preview(model,device,run,epoch):
    panels=[];manifest=[]
    for item in CONFIG['validation']['real_raw_inputs']:
        source=ROOT/Path(item['path'])
        if sha(source)!=item['sha256']:raise ValueError('real Raw source checksum mismatch')
        raw=read(source);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(device)
        out=tiled(model,x)[0,0].cpu().numpy()
        output=np.rint(out.clip(0,1)*255).astype(np.uint8)
        write(run/'previews'/f'e{epoch:03d}_{item["name"]}.png',output)
        row=np.concatenate([cv2.resize(v,(224,224),interpolation=cv2.INTER_AREA) for v in (raw,output,np.rint(np.clip(.5+(out-raw/255)*5,0,1)*255).astype(np.uint8))],axis=1)
        panels.append(row)
        manifest.append({'name':item['name'],'input':str(source),'input_sha256':sha(source),'already_reconstructed':False,
                         'output_change_gray':float(np.abs(output.astype(float)-raw).mean())})
    write(run/'previews'/f'epoch_{epoch:03d}_real.png',np.concatenate(panels,0))
    atomic(run/'previews'/f'epoch_{epoch:03d}_sources.json',manifest)

def train(args):
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    torch.set_num_threads(4);cv2.setNumThreads(1);random.seed(CONFIG['seed']);np.random.seed(CONFIG['seed']);torch.manual_seed(CONFIG['seed'])
    if device.type=='cuda':torch.cuda.manual_seed_all(CONFIG['seed']);torch.backends.cudnn.benchmark=True
    manifest=ROOT/CONFIG['data']['package_root']/'manifest.json';data=json.loads(manifest.read_text())
    if args.mode=='formal' and data['status']!='complete':raise ValueError('formal data incomplete')
    epochs=args.epochs or CONFIG['training']['formal_epochs']
    if args.mode=='formal' and epochs!=CONFIG['training']['formal_epochs']:raise ValueError('formal epoch plan mismatch')
    if args.mode=='formal':
        for e in range(1,epochs+1):schedule(e,'formal',epochs)
    if args.mode=='formal' and not (ROOT/'READY.json').exists():raise ValueError('design repair validation is not complete')
    name=args.run_id or f'r118_{args.mode}_{time.strftime("%Y%m%d_%H%M%S")}'
    run=ROOT/'runs'/name;run.mkdir(parents=True,exist_ok=False)
    lock=ROOT/'runs/active_run.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,name.encode());os.close(fd)
    model=build_model().to(device)
    groups=model.groups();t=CONFIG['training'];weights=t['weights']
    optimizer=torch.optim.AdamW([
        {'params':groups['geometry'],'lr':t['learning_rate']*t['geometry_lr_multiplier'],'group':'geometry'},
        {'params':groups['action'],'lr':t['learning_rate'],'group':'action'},
        {'params':groups['detail'],'lr':t['learning_rate']*t['detail_lr_multiplier'],'group':'detail'}],weight_decay=t['weight_decay'])
    state={'status':'running','run_id':name,'mode':args.mode,'scratch':True,'checkpoint_loaded':False,'epochs':epochs,
           'dataset_sha256':sha(manifest),'config_sha256':sha(ROOT/'config/experiment.json'),
           'data_limit':args.limit,'batch_size':args.batch,'detail_arm':not args.no_detail,'pid':os.getpid(),
           'distance_orientation':CONFIG['data']['distance_orientation'],
           'code_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'model/network.py',ROOT/'training/objectives.py',ROOT/'training/dataset.py',ROOT/'training/train.py']}}
    atomic(run/'state.json',state);atomic(ROOT/'runs/active_run.json',{'run_id':name,'path':str(run),'status':'running'})
    history=[];started=time.perf_counter();step=0
    try:
        for epoch in range(1,epochs+1):
            stage=schedule(epoch,args.mode,epochs)
            active={'geometry'} if stage=='geometry' else {'geometry','action'}
            if stage=='detail' and not args.no_detail:active.add('detail')
            model.detail_enabled=stage=='detail' and not args.no_detail
            for group,parameters in groups.items():
                for p in parameters:p.requires_grad_(group in active)
            progress=(epoch-1)/max(epochs-1,1);factor=.25+.75*.5*(1+math.cos(math.pi*progress))
            # Newly enabled detail receives its own useful learning rate.
            for group in optimizer.param_groups:
                multiplier=t['geometry_lr_multiplier'] if group['group']=='geometry' else t['detail_lr_multiplier'] if group['group']=='detail' else 1
                group['lr']=t['learning_rate']*factor*multiplier
            ds=Scenes('train',epoch=epoch,limit=args.limit)
            dl=loader(ds,args.batch,args.workers,True,CONFIG['seed']+epoch)
            model.train();totals={};count=0;epoch_started=time.perf_counter()
            if device.type=='cuda':torch.cuda.reset_peak_memory_stats()
            for index,raw in enumerate(dl,1):
                b=flatten(raw,device);optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device.type,dtype=torch.bfloat16,enabled=device.type=='cuda'):
                    d=model.forward_details(b['source']);loss,terms=objective(model,d,b,weights,stage=='geometry')
                if not torch.isfinite(loss):raise FloatingPointError('loss')
                loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),t['gradient_clip'])
                if not torch.isfinite(norm):raise FloatingPointError('gradient')
                optimizer.step();count+=1;step+=1
                totals['total']=totals.get('total',0)+float(loss.detach())
                for key,value in terms.items():totals[key]=totals.get(key,0)+float(value.detach())
                if index==1 or index%10==0:
                    elapsed=time.perf_counter()-epoch_started
                    live={'epoch':epoch,'epochs':epochs,'stage':stage,'step':index,'steps':len(dl),'loss':float(loss.detach()),
                          'epoch_remaining_seconds':elapsed/index*(len(dl)-index),
                          'estimated_total_remaining_seconds':elapsed/index*(len(dl)-index)+(np.median([r['duration_seconds'] for r in history[-3:]]) if history else elapsed/index*len(dl))*(epochs-epoch)}
                    if device.type=='cuda':live['gpu_free_gib']=torch.cuda.mem_get_info()[0]/2**30
                    if device.type=='cuda':live['low_free_memory_warning']=live['gpu_free_gib']<t['minimum_free_gpu_gib']
                    atomic(run/'live.json',live)
            elapsed=time.perf_counter()-epoch_started
            model.eval();evaluation=validate(model,device,args.validation_limit)
            atomic(run/'validation'/f'epoch_{epoch:03d}.json',evaluation)
            row={'epoch':epoch,'stage':stage,'steps':count,'duration_seconds':elapsed,**{k:v/count for k,v in totals.items()},
                 **{f'val_{k}':v for k,v in evaluation['groups']['all'].items()}}
            if device.type=='cuda':row['peak_reserved_gib']=torch.cuda.max_memory_reserved()/2**30
            history.append(row);history_csv(run/'training_log.csv',history)
            print(json.dumps({'epoch':epoch,'stage':stage,'loss':row['total'],'seconds':elapsed,'validation':evaluation['groups']['all']}),flush=True)
            if epoch%t['preview_every_epochs']==0 or epoch==epochs:
                preview(model,device,run,epoch)
            if epoch%t['save_every_epochs']==0 or epoch==epochs:
                dest=run/'weights'/f'epoch_{epoch:03d}.pth';dest.parent.mkdir(parents=True,exist_ok=True)
                torch.save({'model':model.state_dict(),'model_config':model.config,'scratch':True,'checkpoint_loaded':False,
                            'epoch':epoch,'run_id':name,'detail_enabled':model.detail_enabled,'validation':evaluation['groups'],
                            'distance_orientation':CONFIG['data']['distance_orientation'],'config_snapshot':CONFIG,'source_state':state},dest)
        state.update(status='complete',epochs_completed=epochs,steps=step,elapsed_seconds=time.perf_counter()-started,last_validation=evaluation['groups'])
        atomic(run/'SUMMARY.json',state)
    except BaseException as e:
        state.update(status='failed',error=repr(e),steps=step)
        atomic(run/'failure.json',state)
        raise
    finally:
        atomic(run/'state.json',state);atomic(ROOT/'runs/active_run.json',{'run_id':name,'path':str(run),'status':state['status']})
        if lock.exists() and lock.read_text()==name:lock.unlink()
    return 0

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['probe','formal'],default='probe');p.add_argument('--run-id',default='')
    p.add_argument('--epochs',type=int,default=12);p.add_argument('--limit',type=int,default=512)
    p.add_argument('--batch',type=int,default=None);p.add_argument('--workers',type=int,default=None);p.add_argument('--validation-limit',type=int,default=96);p.add_argument('--no-detail',action='store_true')
    args=p.parse_args()
    if args.batch is None:args.batch=CONFIG['training']['batch_size_scenes']
    if args.workers is None:args.workers=CONFIG['training']['workers']
    if args.mode=='formal':args.epochs=CONFIG['training']['formal_epochs'];args.limit=0
    return train(args)
if __name__=='__main__':raise SystemExit(main())

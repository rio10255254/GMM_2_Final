"""Bounded scratch A/B probes using locked inputs and stage checkpoints."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.factorial_dataset import Scenes,FamilyOrder,flatten
from training.base import CONFIG
from training.position_loss import objective
from model.network import build_model


def digest_state(model):
    h=hashlib.sha256()
    for key,value in sorted(model.state_dict().items()):
        h.update(key.encode());h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8');temporary.replace(path)


def initialize_worker(_):cv2.setNumThreads(1);torch.set_num_threads(1)


@torch.inference_mode()
def evaluate(model,device):
    ds=Scenes('validation',0,96,arm='A')
    loader=DataLoader(ds,batch_size=4,num_workers=0)
    source_hash=hashlib.sha256();target_hash=hashlib.sha256();values=[]
    model.eval()
    for b in loader:
        source_hash.update(b['source'].numpy().tobytes());target_hash.update(b['target'].numpy().tobytes())
        batch=flatten(b,device);out=model(batch['source'])
        mae=(out-batch['target']).abs().mean((1,2,3))*255
        raw=(batch['source']-batch['target']).abs().mean((1,2,3))*255
        for i in range(len(mae)):
            values.append({'scene_index':int(b['scene_index'][i//2]),'view':i%2,'role':b['role'][i//2],
                           'mae_gray':float(mae[i]),'Raw_mae_gray':float(raw[i])})
    return {'mae_gray':float(np.mean([r['mae_gray'] for r in values])),
            'Raw_mae_gray':float(np.mean([r['Raw_mae_gray'] for r in values])),
            'source_sha256':source_hash.hexdigest(),'target_sha256':target_hash.hexdigest(),'rows':values}


def run(args):
    if not re.fullmatch(r'[A-Za-z0-9_]+',args.run_id):raise ValueError('invalid run id')
    if not (ROOT/'results/preflight.json').is_file():raise RuntimeError('preflight required')
    if not json.loads((ROOT/'results/preflight.json').read_text())['behavioral_checks_complete']:raise RuntimeError('behavior checks incomplete')
    root=ROOT/'runs';root.mkdir(exist_ok=True)
    lock=root/'active.lock'
    # Exclusive file creation before any run output is allocated.
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd,args.run_id.encode());os.close(fd)
    run_dir=root/args.run_id;created=False
    started=time.monotonic();history=[];state={'status':'initializing','run_id':args.run_id,'arm':args.arm,'model_seed':args.seed,
        'data_seed':CONFIG['seed'],'sampler_seed':1197001,'scratch':True,'checkpoint_loaded':False,'epochs':args.epochs,
        'scenes':args.scenes,'batch':args.batch,'pid':os.getpid(),'workers':args.workers,
        'config':CONFIG,'source_sha256':{str(p.relative_to(ROOT)):file_sha(p) for p in [ROOT/'training/train.py',ROOT/'training/dataset.py',ROOT/'training/base.py',ROOT/'model/network.py',ROOT/'training/objectives.py',ROOT/'training/factorial_dataset.py',ROOT/'training/position_loss.py']}}
    try:
        run_dir.mkdir(exist_ok=False);created=True
        random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
        torch.set_num_threads(4);cv2.setNumThreads(1)
        device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        if device.type=='cuda':torch.cuda.manual_seed_all(args.seed);torch.backends.cudnn.benchmark=True
        model=build_model().to(device);state['initialization_sha256']=digest_state(model)
        groups=model.groups();t=CONFIG['training']
        optimizer=torch.optim.AdamW([{'params':params,'group':name,'lr':t['learning_rate']} for name,params in groups.items()],weight_decay=t['weight_decay'])
        state['status']='running';atomic(run_dir/'state.json',state)
        stage_length=args.epochs//3
        for epoch in range(1,args.epochs+1):
            stage='geometry' if epoch<=stage_length else 'action' if epoch<=2*stage_length else 'detail'
            active={'geometry'} if stage=='geometry' else {'geometry','action'} if stage=='action' else set(groups)
            for name,params in groups.items():
                for param in params:param.requires_grad_(name in active)
            model.detail_enabled=stage=='detail'
            for group in optimizer.param_groups:
                multiplier=t['geometry_lr_multiplier'] if group['group']=='geometry' else t['detail_lr_multiplier'] if group['group']=='detail' else 1
                group['lr']=t['learning_rate']*multiplier*(.25+.75*.5*(1+math.cos(math.pi*(epoch-1)/(args.epochs-1))))
            ds=Scenes('train',epoch,args.scenes,arm=args.arm,data_seed=CONFIG['seed'])
            kwargs=dict(dataset=ds,batch_size=args.batch,sampler=FamilyOrder(ds,1197001+epoch),num_workers=args.workers,
                        worker_init_fn=initialize_worker,pin_memory=device.type=='cuda')
            if args.workers:kwargs.update(prefetch_factor=2)
            loader=DataLoader(**kwargs);model.train();total=0.;count=0;epoch_start=time.monotonic()
            term_totals={}
            active_gradient_seen={name:False for name in active}
            if device.type=='cuda':torch.cuda.reset_peak_memory_stats()
            for step,b in enumerate(loader,1):
                batch=flatten(b,device);optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device.type,dtype=torch.bfloat16,enabled=device.type=='cuda'):
                    details=model.forward_details(batch['source']);loss,terms=objective(model,details,batch,t['weights'],stage=='geometry',args.arm)
                if not torch.isfinite(loss):raise FloatingPointError('nonfinite loss')
                loss.backward()
                for name in active:
                    if not active_gradient_seen[name]:active_gradient_seen[name]=any(p.grad is not None and bool(p.grad.detach().abs().sum()>0) for p in groups[name])
                norm=torch.nn.utils.clip_grad_norm_(model.parameters(),t['gradient_clip'])
                if not torch.isfinite(norm):raise FloatingPointError('nonfinite gradient')
                optimizer.step();total+=float(loss.detach());count+=1
                for key,value in terms.items():term_totals[key]=term_totals.get(key,0.)+float(value.detach())
                if step==1 or step%16==0 or step==len(loader):
                    seconds=time.monotonic()-epoch_start
                    atomic(run_dir/'live.json',{'run_id':args.run_id,'epoch':epoch,'epochs':args.epochs,'stage':stage,
                        'step':step,'steps':len(loader),'epoch_remaining_seconds':seconds/step*(len(loader)-step),
                        'free_gpu_gib':torch.cuda.mem_get_info()[0]/2**30 if device.type=='cuda' else None})
            if not all(active_gradient_seen.values()):raise RuntimeError(f'dead stage: {active_gradient_seen}')
            ev=evaluate(model,device)
            row={'epoch':epoch,'stage':stage,'steps':count,'loss':total/count,'mae_gray':ev['mae_gray'],
                'Raw_mae_gray':ev['Raw_mae_gray'],'seconds':time.monotonic()-epoch_start,
                'peak_reserved_gib':torch.cuda.max_memory_reserved()/2**30 if device.type=='cuda' else None}
            row.update({key:value/count for key,value in term_totals.items()})
            history.append(row)
            atomic(run_dir/'validation'/f'e{epoch:03d}.json',ev)
            with (run_dir/'training_log.csv').open('w',newline='') as stream:
                keys=list(dict.fromkeys(key for record in history for key in record));writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(history)
            if epoch%stage_length==0:
                dest=run_dir/'weights'/f'epoch_{epoch:03d}.pth';dest.parent.mkdir(exist_ok=True)
                temp=dest.with_suffix('.tmp')
                torch.save({'model':model.state_dict(),'model_config':model.config,'detail_enabled':model.detail_enabled,
                            'epoch':epoch,'scratch':True,'checkpoint_loaded':False,'run_id':args.run_id,
                            'arm':args.arm,'model_seed':args.seed,'initialization_sha256':state['initialization_sha256']},temp)
                temp.replace(dest)
            print(json.dumps({'run':args.run_id,**row}),flush=True)
        state.update(status='complete',completed_epochs=args.epochs,steps=sum(r['steps'] for r in history),
                     elapsed_seconds=time.monotonic()-started,last_validation=ev['mae_gray'])
        atomic(run_dir/'SUMMARY.json',state)
    except BaseException as exc:
        state.update(status='failed',error=repr(exc))
        if created:atomic(run_dir/'failure.json',{'error':repr(exc),'run_id':args.run_id,'completed_epochs':len(history)})
        raise
    finally:
        if created:atomic(run_dir/'state.json',state)
        if lock.exists() and lock.read_text()==args.run_id:lock.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=['A','B','C','D'],required=True)
    parser.add_argument('--seed',type=int,required=True);parser.add_argument('--run-id',required=True)
    parser.add_argument('--epochs',type=int,choices=[3,12],default=12);parser.add_argument('--scenes',type=int,default=512)
    parser.add_argument('--batch',type=int,default=8);parser.add_argument('--workers',type=int,default=2)
    run(parser.parse_args())

"""Standalone scratch/derived training with explicit PSF-label admission."""
from __future__ import annotations
import argparse,json,math,os,time
from pathlib import Path
import torch
from utils import ROOT,load,save,sha,now,setup,model_config,train_config,verify_bank_lock
from model import Model
from dataset import Bank
from losses import objective
from training_policy import optimizer,apply_epoch_policy,project_beta_after_step

def lr_for(step,cfg):
    o=cfg['optimizer']
    if step<=cfg['warmup']:return o['max_lr']*step/cfg['warmup']
    return o['min_lr']+.5*(o['max_lr']-o['min_lr'])*(1+math.cos(math.pi*(step-cfg['warmup'])/(cfg['updates']-cfg['warmup'])))

def dataset_labels(bank):
    seen=0
    for e in bank.manifest['entries']:
        if e['split']=='train':
            m=load(bank.root/e['metadata'])
            if 'psf_index' in m:seen+=1
    return seen

def assess(model,bank,split,device,limit=None):
    model.eval();values=[]
    count=bank.cfg['splits'][split] if limit is None else min(limit,bank.cfg['splits'][split])
    with torch.inference_mode():
        for i in range(count):
            batch=bank.batch(split,i,device);y=model(batch['source']);loss,_=objective(y,batch)
            values.append(float(loss))
    return dict(split=split,parents=count,mean_loss=sum(values)/count,individual_loss=values)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-name',required=True)
    parser.add_argument('--init',choices=['scratch','derived'],default='scratch')
    parser.add_argument('--allow-unlabeled-psf',action='store_true')
    parser.add_argument('--data-root',help='Optional new labeled 512/128/128 dataset; bundled data stay untouched')
    parser.add_argument('--smoke',action='store_true',help='Only 4 updates; never a trained model')
    args=parser.parse_args()
    if not args.run_name.replace('-','').replace('_','').isalnum():raise ValueError('Use an alphanumeric run name')
    cfg=train_config();mc=model_config();setup(cfg['model_seed'])
    device=cfg['device']
    if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('Configured CUDA device unavailable')
    bank_path=ROOT/mc['psf_bank']
    bank_lock=verify_bank_lock()
    if bank_lock.get('test_only',False) and not args.smoke:
        raise RuntimeError('Synthetic test bank may be used only for smoke tests, never full training')
    bank=Bank(cfg,args.data_root);data_manifest_hash=sha(bank.root/'manifest.json')
    if args.data_root and bank.root.resolve()==(ROOT/'data').resolve():
        raise ValueError('For bundled data, omit --data-root; do not replace the original dataset')
    label_count=dataset_labels(bank)
    if label_count not in (0,512):raise RuntimeError('Mixed labeled and unlabeled training parents')
    if not label_count and not args.allow_unlabeled_psf:
        raise RuntimeError('Adaptive PSF training requires per-image psf_index labels. Existing shared synthetic data have none. Use --allow-unlabeled-psf only for an explicitly nonadaptive experiment.')
    run=ROOT/'runs'/args.run_name
    if run.exists() and not (run/'latest.json').exists():raise FileExistsError('Run folder exists without resumable checkpoint')
    run.mkdir(parents=True,exist_ok=True);(run/'checkpoints').mkdir(exist_ok=True)
    model=Model(mc,ROOT).to(device)
    opt=optimizer(model,base_lr=cfg['optimizer']['max_lr'],weight_decay=cfg['optimizer']['weight_decay'],optical_lr_multiplier=mc['psf_lr_multiplier'])
    latest=run/'latest.json';log=run/'updates.jsonl';start_step=0
    if latest.exists():
        rec=load(latest)
        if sha(rec['path'])!=rec['sha256']:raise RuntimeError('Resume checkpoint hash mismatch')
        checkpoint=torch.load(rec['path'],map_location='cpu',weights_only=False)
        if checkpoint['bank_sha256']!=sha(bank_path) or checkpoint['model_config']!=mc or checkpoint['data_manifest_sha256']!=data_manifest_hash:
            raise RuntimeError('Resume model/bank identity mismatch')
        model.load_state_dict(checkpoint['model'],strict=True);opt.load_state_dict(checkpoint['optimizer'])
        torch.set_rng_state(checkpoint['torch_rng']);
        if device=='cuda':torch.cuda.set_rng_state_all(checkpoint['cuda_rng'])
        start_step=checkpoint['step']
        if log.exists() and len(log.read_text().splitlines())!=start_step:
            raise RuntimeError('Log/checkpoint mismatch; inspect before resuming')
    elif args.init=='derived':
        p=ROOT/'weights/derived_from_R140v2.pth'
        if not p.is_file():p=ROOT/'weights/backbone_seed_from_R140v2.pth'
        if not p.is_file():raise FileNotFoundError('No derived initializer in this package')
        initial=torch.load(p,map_location='cpu',weights_only=False)
        if initial['checkpoint_kind']=='backbone_seed_no_bank':
            state=model.state_dict()
            for key,value in initial['backbone'].items():
                if key not in state or state[key].shape!=value.shape:raise RuntimeError('Backbone seed/model mismatch: '+key)
                state[key]=value
            model.load_state_dict(state,strict=True)
        else:
            if initial['bank_sha256']!=sha(bank_path):raise RuntimeError('Initializer/bank mismatch')
            model.load_state_dict(initial['model'],strict=True)
    save(run/'run_config.json',dict(model_config=mc,train_config=cfg,init=args.init,
                                    adaptive_labels=label_count,allow_unlabeled=args.allow_unlabeled_psf,
                                    data_root=str(bank.root.resolve()),bank_sha256=sha(bank_path),
                                    source_data_manifest_sha256=data_manifest_hash,started_utc=now()))
    total=4 if args.smoke else cfg['updates'];begin=time.perf_counter()
    if start_step==0:
        apply_epoch_policy(model,0)
        save(run/'dev_initial.json',assess(model,bank,'dev',device,limit=2 if args.smoke else None))
    def checkpoint(step):
        path=run/'checkpoints'/f'step{step:05d}.pth';tmp=path.with_suffix('.tmp')
        torch.save(dict(model_name=mc['model_name'],model={k:v.detach().cpu() for k,v in model.state_dict().items()},
                        optimizer=opt.state_dict(),step=step,model_config=mc,train_config=cfg,
                        bank_sha256=sha(bank_path),adaptive_labels=label_count,
                        data_manifest_sha256=data_manifest_hash,
                        checkpoint_kind='trained_model' if step==cfg['updates'] and not args.smoke else 'incomplete_training',
                        selector_trained=bool(label_count),selector_adaptivity_validated=False,
                        torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all() if device=='cuda' else None),tmp)
        os.replace(tmp,path);save(latest,dict(path=str(path),step=step,sha256=sha(path)))
    with log.open('a',encoding='utf-8',buffering=1) as handle:
        for step in range(start_step+1,total+1):
            epoch=(step-1)//512;idx=int(bank.order(epoch)[(step-1)%512]);policy=apply_epoch_policy(model,epoch)
            rate=lr_for(step,cfg)
            for group in opt.param_groups:
                group['lr']=rate*(mc['psf_lr_multiplier'] if group['name']=='optical' else 1.0)
            batch=bank.batch('train',idx,device,epoch)
            model.train();opt.zero_grad(set_to_none=True)
            output=model(batch['source']);loss,parts=objective(output,batch)
            selector_loss=None
            if policy['optical_active'] and 'psf_index' in batch:
                selector_loss=model.refiner.optics.selector_loss(batch['psf_index'])
                loss=loss+cfg['loss']['selector_label']*selector_loss
            if not torch.isfinite(loss):raise FloatingPointError(f'Nonfinite loss at {step}')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True)
            opt.step();project_beta_after_step(model)
            selected=model.refiner.optics.last_indices
            row=dict(step=step,epoch=epoch,parent_id=batch['parent_id'],loss=float(loss),
                     image=float(parts['image']),gradient=float(parts['gradient']),pair=float(parts['pair']),
                     selector_label_loss=None if selector_loss is None else float(selector_loss),
                     selected_psf=None if selected is None or not policy['optical_active'] else selected[0].cpu().tolist(),
                     psf_active=policy['optical_active'],learning_rate=rate,utc=now())
            handle.write(json.dumps(row)+'\n')
            if step%32==0 or step==total:
                save(run/'status.json',dict(state='training',step=step,total=total,loss=float(loss),
                                            elapsed_seconds=time.perf_counter()-begin,updated_utc=now()))
                print('TRAIN',step,'/',total,'loss',float(loss),flush=True)
            if step%cfg['save_every']==0 or step==total:checkpoint(step)
            if step%cfg['dev_every']==0 and not args.smoke:
                save(run/f'dev_{step:05d}.json',assess(model,bank,'dev',device))
    if args.smoke:
        save(run/'smoke_complete.json',dict(updates=4,not_a_trained_model=True,completed_utc=now()))
    else:
        save(run/'test_final.json',assess(model,bank,'test',device))
        save(run/'training_complete.json',dict(updates=total,checkpoint=load(latest),
                                               selector_supervised=bool(label_count),
                                               real_validation_complete=False,completed_utc=now()))
    print('FINISHED',args.run_name,flush=True)
if __name__=='__main__':main()

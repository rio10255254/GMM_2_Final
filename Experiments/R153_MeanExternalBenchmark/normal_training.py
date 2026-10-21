"""Ordinary author objectives; common image data, valid region and validation stopping."""
from pathlib import Path
import argparse,copy,json,math,os,shutil,signal,sys,time,traceback
import numpy as np
import torch
from torch import nn
from study import ROOT,PACK,save,sha,read,training_config
from normal_protocol import COMMON,NORMAL
from normal_data import ImagePairs
from benchmark_models import SPECS,make_model,load_module
from benchmark_core import evaluate,prepare
from core.runtime import save_checkpoint,setup


def loss_function(method):
    spec=NORMAL[method]
    if spec['loss']=='L1':return nn.L1Loss()
    if spec['loss']=='author_PSNRLoss':
        module=load_module('naf_pixel_loss','NAFNet/basicsr/models/losses/losses.py',selected_classes=('PSNRLoss',))
        return module.PSNRLoss()
    if spec['loss']=='author_Charbonnier':
        module=load_module('swin_pixel_loss','KAIR/models/loss.py',selected_classes=('CharbonnierLoss',))
        return module.CharbonnierLoss(spec['charbonnier_eps'])
    raise ValueError(spec['loss'])


def initialize(method,model):
    if NORMAL[method].get('initialization')=='author_orthogonal_gain_0.2':
        for module in model.modules():
            if isinstance(module,(nn.Conv2d,nn.ConvTranspose2d,nn.Linear)):
                nn.init.orthogonal_(module.weight,gain=.2)
                if module.bias is not None:nn.init.zeros_(module.bias)


@torch.inference_mode()
def validation(model,bank,optics,limit=None):
    model.eval();rows=[]
    for index in range(128 if limit is None else limit):
        batch=bank.batch('dev',index,'cuda')
        prediction=model(batch['source'],batch['operator_psf_indices'],optics)
        p=prediction[...,144:240,144:240].cpu().numpy().astype(np.float64)
        t=batch['target'][...,144:240,144:240].cpu().numpy().astype(np.float64)
        if not np.isfinite(p).all():raise FloatingPointError('Nonfinite validation output')
        mse=np.mean((p-t)**2,axis=(1,2,3))
        rows.append({'scene':index,'mean_PSNR_dB':float(np.mean(-10*np.log10(np.maximum(mse,1e-30)))),
                     'mean_L1':float(np.mean(np.abs(p-t)))})
    return {'parents':len(rows),'images':4*len(rows),'mean_PSNR_dB':float(np.mean([r['mean_PSNR_dB'] for r in rows])),
            'mean_L1':float(np.mean([r['mean_L1'] for r in rows])),'per_scene':rows}


@torch.no_grad()
def update_ema(ema,model,decay):
    for target,source in zip(ema.parameters(),model.parameters()):target.mul_(decay).add_(source,alpha=1-decay)
    for target,source in zip(ema.buffers(),model.buffers()):target.copy_(source)


def run(method,out,max_updates=None,assessment_limit=None):
    formal=max_updates is None and assessment_limit is None
    cfg,bank,optics=prepare()
    setup(COMMON['seed'])
    model=make_model(method);initialize(method,model);model=model.cuda().train()
    spec=NORMAL[method]
    ema=None
    if spec['ema']:
        # Construct separately: deepcopy would retain checkpoint closures bound to the training model.
        with torch.random.fork_rng(devices=[0]):ema=make_model(method,checkpoint_training=False).cuda().eval()
        ema.load_state_dict(model.state_dict(),strict=True)
        for parameter in ema.parameters():parameter.requires_grad_(False)
    criterion=loss_function(method).cuda()
    optimizer_class=torch.optim.AdamW if spec['optimizer']=='AdamW' else torch.optim.Adam
    optimizer=optimizer_class([p for p in model.parameters() if p.requires_grad],lr=spec['lr'],betas=tuple(spec['betas']),weight_decay=spec['weight_decay'])
    scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode='max',factor=COMMON['lr_reduction_factor'],
                patience=COMMON['lr_plateau_patience_epochs'],threshold=COMMON['meaningful_PSNR_improvement_dB'],
                threshold_mode='abs',min_lr=COMMON['minimum_lr'])
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    signature={'common':COMMON,'method':spec,'architecture':SPECS[method],
               'factory_sha256':sha(ROOT/'benchmark_models.py'),'normal_training_sha256':sha(__file__),
               'normal_data_sha256':sha(ROOT/'normal_data.py')}
    step=0;completed_epochs=0;history=[];dev=[];best=-math.inf;best_epoch=None;progress_best=-math.inf;bad_epochs=0
    latest=out/'last.pth'
    if (out/'training_complete.json').exists():
        done=read(out/'training_complete.json');assert sha(out/'selected.pth')==done['checkpoint_sha256'];return done
    if latest.exists():
        saved=torch.load(latest,map_location='cpu',weights_only=False)
        assert saved['signature']==signature,'Resume recipe differs from its saved source'
        model.load_state_dict(saved['model'],strict=True)
        if ema is not None:ema.load_state_dict(saved['ema'],strict=True)
        optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
        step=saved['step'];completed_epochs=saved['completed_epochs'];history=saved['history'];dev=saved['dev']
        best=saved['best'];best_epoch=saved['best_epoch'];progress_best=saved['progress_best'];bad_epochs=saved['bad_epochs']
        torch.set_rng_state(saved['torch_rng']);torch.cuda.set_rng_state_all(saved['cuda_rng'])
    save(out/'status.json',{'state':'loading_data','method':method,'pid':os.getpid(),'step':step,'epochs_completed':completed_epochs,
                           'maximum_epochs':COMMON['max_epochs'],'formal':formal,'training_recipe':spec})
    data=ImagePairs(preload=formal)
    stopped=False
    def interrupt(_signal,_frame):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGINT,interrupt)
    def checkpoint_state():
        save_checkpoint(latest,{'method':method,'signature':signature,'step':step,'completed_epochs':completed_epochs,
            'model':{k:v.detach().cpu() for k,v in model.state_dict().items()},
            'ema':None if ema is None else {k:v.detach().cpu() for k,v in ema.state_dict().items()},
            'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),'history':history,'dev':dev,
            'best':best,'best_epoch':best_epoch,'progress_best':progress_best,'bad_epochs':bad_epochs,
            'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),'is_formal_run':formal})
    def status(state):
        recent=float(np.mean([r['seconds'] for r in history[-128:]])) if history else None
        save(out/'status.json',{'state':state,'method':method,'pid':os.getpid(),'step':step,
             'epochs_completed':completed_epochs,'current_epoch_fraction':step/512,'maximum_epochs':COMMON['max_epochs'],
             'minimum_epochs':COMMON['min_epochs'],'best_validation_PSNR_dB':best if np.isfinite(best) else None,
             'selected_epoch':best_epoch,'epochs_without_meaningful_improvement':bad_epochs,
             'recent_update_seconds':recent,'last_training_loss':history[-1]['native_loss'] if history else None,
             'learning_rate':optimizer.param_groups[0]['lr'],'formal':formal,'training_recipe':spec})
    start=time.perf_counter()
    try:
        if not dev:
            status('initial_validation')
            initial=validation(ema if ema is not None else model,bank,optics,assessment_limit)
            dev.append({'epoch':0,'step':0,**initial});save(out/'validation_history.json',dev)
            checkpoint_state();print(method,'INITIAL VALIDATION PSNR',initial['mean_PSNR_dB'],flush=True)
        reason=('synthetic_validation_plateau' if completed_epochs>=COMMON['min_epochs'] and bad_epochs>=COMMON['early_stop_patience_epochs']
                else 'predeclared_epoch_cap' if completed_epochs>=COMMON['max_epochs'] else None)
        for epoch in range(completed_epochs,COMMON['max_epochs']):
            if reason is not None:break
            order=data.order(epoch)
            first_batch=min(512,max(0,step-epoch*512))
            model.train()
            for batch_index in range(first_batch,512):
                if max_updates is not None and step>=max_updates:break
                if step%128==0 and shutil.disk_usage(ROOT).free<50*2**30:raise OSError('D free space below 50 GiB reserve')
                ids=order[batch_index*4:(batch_index+1)*4]
                batch=data.batch(ids,epoch)
                optimizer.zero_grad(set_to_none=True)
                torch.cuda.synchronize();tick=time.perf_counter()
                prediction=model(batch['source'],batch['actual_psf_indices'],optics,batch['noise_sigma'])
                loss=criterion(prediction[...,144:240,144:240],batch['target'][...,144:240,144:240])
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite native training loss')
                loss.backward()
                norm=torch.nn.utils.clip_grad_norm_(model.parameters(),spec['clip_norm'] if spec['clip_norm'] is not None else float('inf'),error_if_nonfinite=True)
                optimizer.step()
                if ema is not None:update_ema(ema,model,spec['ema'])
                torch.cuda.synchronize();step+=1
                history.append({'step':step,'epoch':epoch+1,'batch_in_epoch':batch_index+1,'native_loss':float(loss.detach()),
                                'gradient_norm':float(norm),'seconds':time.perf_counter()-tick,'lr':optimizer.param_groups[0]['lr'],
                                'image_indices':batch['flat_indices'],'source_input_sha256':batch['source_input_sha256']})
                if step%16==0:
                    status('training');print(method,f'EPOCH {epoch+1} BATCH {batch_index+1}/512',f'LOSS {float(loss):.7f}',flush=True)
                if step%128==0 or stopped or (max_updates is not None and step>=max_updates):
                    checkpoint_state();save(out/'training_history.json',history)
                if stopped:break
            if stopped or (max_updates is not None and step>=max_updates and step%512!=0):break
            if step!=(epoch+1)*512:break
            status('validation')
            val=validation(ema if ema is not None else model,bank,optics,assessment_limit)
            score=val['mean_PSNR_dB'];completed_epochs=epoch+1
            dev.append({'epoch':completed_epochs,'step':step,**val})
            if score>best:
                best=score;best_epoch=completed_epochs
                selected=ema if ema is not None else model
                save_checkpoint(out/'best_validation.pth',{'method':method,'signature':signature,'selected_epoch':best_epoch,
                     'selected_step':step,'validation_PSNR_dB':best,'model':{k:v.detach().cpu() for k,v in selected.state_dict().items()},
                     'public_pretrained_weights_used':False,'selected_parameters':'EMA' if ema is not None else 'trained_network'})
            if score>progress_best+COMMON['meaningful_PSNR_improvement_dB']:
                progress_best=score;bad_epochs=0
            else:bad_epochs+=1
            scheduler.step(score)
            save(out/'validation_history.json',dev);checkpoint_state();status('epoch_complete')
            print(method,'EPOCH_COMPLETE',completed_epochs,'VALIDATION_PSNR',score,'BEST_EPOCH',best_epoch,flush=True)
            if completed_epochs>=COMMON['min_epochs'] and bad_epochs>=COMMON['early_stop_patience_epochs']:
                reason='synthetic_validation_plateau';break
            if completed_epochs==COMMON['max_epochs']:reason='predeclared_epoch_cap';break
            if max_updates is not None and step>=max_updates:break
        if reason is not None and formal:
            best_checkpoint=torch.load(out/'best_validation.pth',map_location='cpu',weights_only=False)
            model.load_state_dict(best_checkpoint['model'],strict=True)
            shutil.copy2(out/'best_validation.pth',out/'selected.pth')
            status('synthetic_test')
            test=evaluate(model,bank,optics,'test',with_image_metrics=True)
            save(out/'synthetic_test.json',test)
            done={'state':'complete','method':method,'epochs_trained':completed_epochs,'updates':step,
                  'selected_epoch':best_epoch,'selected_step':best_checkpoint['selected_step'],'stopping_reason':reason,
                  'validation_PSNR_dB':best,'checkpoint':'selected.pth','checkpoint_sha256':sha(out/'selected.pth'),
                  'total_parameters':sum(p.numel() for p in model.parameters()),
                  'training_recipe':spec,'common_validation_protocol':COMMON,'synthetic_test':test['mean'],
                  'real_data_used_in_training_or_selection':False,'elapsed_this_process_seconds':time.perf_counter()-start}
            save(out/'training_complete.json',done);save(out/'status.json',done)
            print('TRAINING_COMPLETE',method,'epochs',completed_epochs,'selected',best_epoch,flush=True)
            return done
        checkpoint_state();status('saved_partial');print('SAVED_PARTIAL',method,step,flush=True)
    except BaseException as error:
        save(out/'failure.json',{'method':method,'step':step,'completed_epochs':completed_epochs,'error':repr(error),'traceback':traceback.format_exc()})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('method',choices=list(NORMAL));parser.add_argument('--output-dir')
    parser.add_argument('--max-updates',type=int);parser.add_argument('--assessment-limit',type=int)
    args=parser.parse_args()
    return run(args.method,Path(args.output_dir) if args.output_dir else ROOT/'runs'/args.method,args.max_updates,args.assessment_limit)


if __name__=='__main__':main()

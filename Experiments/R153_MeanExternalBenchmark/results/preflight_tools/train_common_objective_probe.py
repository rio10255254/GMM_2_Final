"""Common 16-epoch from-scratch training; final checkpoint fixed before real evaluation."""
from pathlib import Path
import argparse,copy,json,os,signal,sys,time,traceback,shutil
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import *
from benchmark_core import *
from benchmark_models import make_model,SPECS
from core.runtime import save_checkpoint


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('method',choices=list(SPECS))
    parser.add_argument('--output-dir')
    parser.add_argument('--max-updates',type=int)
    parser.add_argument('--assessment-limit',type=int)
    args=parser.parse_args(argv)
    method=args.method
    # Explicit artifact identity required by the project launcher contract.
    MODEL_NAME_BASE=method
    out=Path(args.output_dir) if args.output_dir else ROOT/'runs'/method
    out.mkdir(parents=True,exist_ok=True)
    cfg,bank,optics=prepare()
    formal=args.max_updates is None and args.assessment_limit is None
    model=make_model(method).cuda().train()
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                                lr=cfg['optimizer']['max_lr'],weight_decay=cfg['optimizer']['weight_decay'])
    signature={'training':cfg,'model':SPECS[method],
               'factory_sha256':sha(ROOT/'benchmark_models.py'),
               'common_math_sha256':sha(ROOT/'benchmark_core.py'),
               'data_reader_sha256':sha(PACK/'core/dataset.py'),
               'loss_definitions_sha256':sha(PACK/'core/losses.py')}
    current=0;history=[];dev_history=[]
    latest=out/'last.pth'
    if latest.exists():
        saved=torch.load(latest,map_location='cpu',weights_only=False)
        assert saved['method']==method and saved['signature']==signature,'Changed resumed recipe'
        model.load_state_dict(saved['model'],strict=True);optimizer.load_state_dict(saved['optimizer'])
        torch.set_rng_state(saved['torch_rng']);torch.cuda.set_rng_state_all(saved['cuda_rng'])
        current=int(saved['step']);history=saved['history'];dev_history=saved['dev_history']
    stop=cfg['updates'] if args.max_updates is None else min(args.max_updates,cfg['updates'])
    if stop<current:raise ValueError('Requested update count precedes saved training')
    if (out/'training_complete.json').exists():
        done=read(out/'training_complete.json')
        assert done['step']==cfg['updates'] and sha(out/'final.pth')==done['checkpoint_sha256']
        print('ALREADY COMPLETE',method,flush=True);return done
    requested_stop=False
    def signal_stop(_number,_frame):
        nonlocal requested_stop
        requested_stop=True
    signal.signal(signal.SIGINT,signal_stop)
    def checkpoint_at(step):
        value={'method':MODEL_NAME_BASE,'step':step,'epochs_completed':step/512,
               'model':{k:v.detach().cpu() for k,v in model.state_dict().items()},
               'optimizer':optimizer.state_dict(),'signature':signature,'history':history,
               'dev_history':dev_history,'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),
               'public_pretrained_weights_used':False,'checkpoint_selection':'fixed_final_update',
               'is_formal_run':formal}
        save_checkpoint(latest,value)
    started=time.perf_counter();initial_step=current
    try:
        if current==0 and not dev_history:
            initial=evaluate(model,bank,optics,'dev',args.assessment_limit)
            dev_history.append({'step':0,'epoch':0,**initial})
            save(out/'dev_history.json',dev_history)
            print(method,'INITIAL_DEV',initial['mean']['task'],flush=True)
        model.train()
        for step in range(current+1,stop+1):
            if step%128==1 and shutil.disk_usage(ROOT).free<50*2**30:raise OSError('D free space below reserved 50 GiB')
            batch,epoch,index=batch_for_step(bank,step)
            rate=lr_for(step,cfg)
            for group in optimizer.param_groups:group['lr']=rate
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.synchronize();t=time.perf_counter()
            prediction=model(batch['source'],batch['operator_psf_indices'],optics)
            loss,terms=objective(prediction,batch,optics)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite common loss')
            loss.backward()
            norm=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True)
            optimizer.step();torch.cuda.synchronize()
            row={'step':step,'epoch':epoch+1,'scene_index':index,'source_input_sha256':batch['input_sha256'],
                 'lr':rate,'gradient_norm':float(norm),'seconds':time.perf_counter()-t,
                 **losses_as_numbers(loss,terms)}
            history.append(row);current=step
            if step%16==0 or step==stop:
                elapsed=time.perf_counter()-started
                average=float(np.mean([r['seconds'] for r in history[-128:]]))
                status={'state':'training','method':method,'pid':os.getpid(),'step':step,'total_updates':cfg['updates'],
                        'epochs_completed':step/512,'total_epochs':cfg['epochs'],'elapsed_seconds':elapsed,
                        'recent_seconds_per_update':average,'remaining_update_seconds_estimate':average*(cfg['updates']-step),
                        'last_loss':row,'formal':formal}
                save(out/'status.json',status)
                print(method,f'EPOCH {step/512:.3f}/{cfg["epochs"]}',f'UPDATE {step}/{cfg["updates"]}',f'LOSS {row["task"]:.6f}',flush=True)
            if step%cfg['save_every']==0 or step==stop or requested_stop:
                checkpoint_at(step)
                save(out/'training_history.json',history)
            if step%512==0:
                evaluated=evaluate(model,bank,optics,'dev',args.assessment_limit)
                dev_history.append({'step':step,'epoch':step//512,**evaluated})
                save(out/'dev_history.json',dev_history)
                model.train()
                checkpoint_at(step)
                print(method,'DEV_EPOCH',step//512,evaluated['mean']['task'],flush=True)
            if requested_stop:break
        if current==cfg['updates']:
            checkpoint_at(current)
            shutil.copy2(latest,out/'final.pth')
            test=evaluate(model,bank,optics,'test',args.assessment_limit,with_image_metrics=True)
            save(out/'synthetic_test.json',test)
            done={'state':'complete' if formal else 'short_test_complete','method':method,'step':current,
                  'epochs':cfg['epochs'],'complete_training_scenes_per_epoch':512,'views_per_scene':4,
                  'checkpoint':'final.pth','checkpoint_sha256':sha(out/'final.pth'),
                  'synthetic_test':test['mean'],'real_results_used_for_selection':False,
                  'total_parameters':sum(p.numel() for p in model.parameters()),
                  'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),
                  'train_runtime_seconds':time.perf_counter()-started}
            save(out/'training_complete.json',done);save(out/'status.json',done)
            print('TRAINING_COMPLETE',method,current,flush=True);return done
        save(out/'status.json',{'state':'saved_partial','method':method,'step':current,'total_updates':cfg['updates'],'checkpoint':str(latest)})
        print('SAVED_PARTIAL',method,current,flush=True)
    except BaseException as error:
        save(out/'failure.json',{'method':method,'step':current,'error':repr(error),'traceback':traceback.format_exc()})
        raise


if __name__=='__main__':main()

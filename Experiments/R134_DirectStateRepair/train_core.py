from rt import *
from dataset134 import Bank
import math,traceback
from objectives import robust_gray,translated
MODEL_NAME_BASE=None
def objective(model,b):
    output=model(b['source']);r=output-b['target'];lo,hi=b['core'];crop=lambda x:x[...,lo:hi,lo:hi];v=crop(r)
    image=robust_gray(v);gradient=.5*(robust_gray(v[...,1:]-v[...,:-1])+robust_gray(v[...,1:,:]-v[...,:-1,:]));pair=robust_gray(crop(r[1:2]-translated(r[0:1],b['metadata']['shift_xy']))) if b['metadata']['motion_observable'] else r.sum()*0
    return image+.2*gradient+.2*pair,dict(image=image,gradient=gradient,pair=pair),output
def evaluate(model,bank,out,step):
    model.eval();rows=[]
    with torch.no_grad():
        for index in range(128):
            b=bank.batch('dev',index);loss,terms,p=objective(model,b);a,z=b['core'];target=b['target'][...,a:z,a:z];src=b['source'][...,a:z,a:z];pred=p[...,a:z,a:z]
            rows.append(dict(index=index,category=b['metadata']['category'],loss=float(loss),mae_gray=float(abs(pred-target).mean()*255),Raw_mae_gray=float(abs(src-target).mean()*255),input_sha256=b['input_sha256']))
    result=dict(step=step,rows=rows,mean_loss=float(np.mean([r['loss'] for r in rows])),mean_mae_gray=float(np.mean([r['mae_gray'] for r in rows])),Raw_mae_gray=float(np.mean([r['Raw_mae_gray'] for r in rows])))
    save(out/f'dev_{step:04d}.json',result);print('dev',step,round(result['mean_mae_gray'],4),flush=True)
def run(arm,seed):
    assert MODEL_NAME_BASE==f'R134_{arm}_s{seed}';verify();cfg=load(ROOT/'config/study.json');m=create(arm,seed);bank=Bank();out=ROOT/f'runs/{MODEL_NAME_BASE}';out.mkdir(exist_ok=False);start=time.perf_counter();order=bank.order(0)
    save(out/'started.json',dict(utc=now(),pid=os.getpid(),arm=arm,seed=seed,model_name=MODEL_NAME_BASE,initial_state_digest=model_digest(m),source=record(__file__),cfg=record(ROOT/'config/study.json')))
    torch.save(dict(model=m.state_dict(),arm=arm,seed=seed,step=0),out/'initial.pth');opt=torch.optim.AdamW(m.parameters(),lr=.001,weight_decay=1e-5);evaluate(m,bank,out,0)
    try:
        with (out/'updates.jsonl').open('x',encoding='utf-8') as log:
            for step in range(1,cfg['updates']+1):
                m.train();epoch=(step-1)//512;index=int(order[(step-1)%512]);b=bank.batch('train',index,epoch=epoch);peak=cfg['optimizer']['peak_lr'];minimum=cfg['optimizer']['minimum_lr'];warm=cfg['optimizer']['warmup_updates'];lr=peak*step/warm if step<=warm else minimum+.5*(peak-minimum)*(1+math.cos(math.pi*(step-warm)/(cfg['updates']-warm)))
                for g in opt.param_groups:g['lr']=lr
                opt.zero_grad(set_to_none=True);loss,terms,_=objective(m,b);assert torch.isfinite(loss);loss.backward();norm=torch.nn.utils.clip_grad_norm_(m.parameters(),5,error_if_nonfinite=True);opt.step()
                row=dict(step=step,parent=index,parent_id=b['metadata']['parent_id'],input_sha256=b['input_sha256'],noise_seed=b['noise_seed'],loss=float(loss.detach()),terms={k:float(v.detach()) for k,v in terms.items()},lr=lr,gradient_norm=float(norm));log.write(json.dumps(row)+'\n');log.flush()
                if step%128==0:torch.save(dict(model=m.state_dict(),optimizer=opt.state_dict(),arm=arm,seed=seed,step=step,model_name=MODEL_NAME_BASE),out/f'step{step:04d}.pth')
                if step in cfg['dev_steps']:evaluate(m,bank,out,step)
                if step%16==0:atomic(out/'status.json',dict(status='training',step=step,total=cfg['updates'],seconds=time.perf_counter()-start,pid=os.getpid()));print(MODEL_NAME_BASE,step,'/512',round(time.perf_counter()-start,1),flush=True)
        verify();save(out/'complete.json',dict(step=512,updates=512,model_name=MODEL_NAME_BASE,checkpoint=record(out/'step0512.pth'),final_state_digest=model_digest(m),seconds=time.perf_counter()-start));atomic(out/'status.json',dict(status='complete',step=512,total=512));print(MODEL_NAME_BASE,'complete',flush=True)
    except BaseException:
        save(out/f'failure_{time.time_ns()}.json',dict(utc=now(),error=traceback.format_exc()));raise

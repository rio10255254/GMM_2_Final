"""The pilot's output loss, durable checkpoints and exact continuation state."""
import math,random,os
import numpy as np,torch
from runtime import *
from objectives import robust_gray,translated
def objective(model,batch):
    pred=model(batch['source']);r=pred-batch['target'];lo,hi=batch['core'];crop=lambda x:x[...,lo:hi,lo:hi];v=crop(r)
    image=robust_gray(v);gradient=.5*(robust_gray(v[...,1:]-v[...,:-1])+robust_gray(v[...,1:,:]-v[...,:-1,:]))
    pair=robust_gray(crop(r[1:2]-translated(r[0:1],batch['metadata']['shift_xy']))) if batch['metadata']['motion_observable'] else r.sum()*0
    return image+.2*gradient+.2*pair,dict(image=image,gradient=gradient,pair=pair)
def update(model,opt,batch,step,cfg):
    model.train();opt.zero_grad(set_to_none=True)
    for group in opt.param_groups:group['lr']=lr_at(step,cfg)
    assert digest(batch['source'].detach().cpu().numpy())==batch['cpu_input_sha256']
    loss,terms=objective(model,batch)
    if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
    loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True);opt.step()
    if any(not torch.isfinite(x).all() for x in model.parameters()):raise FloatingPointError('Nonfinite parameters')
    return dict(step=step,loss=float(loss.detach()),learning_rate=lr_at(step,cfg),gradient_norm=float(norm),terms={k:float(v.detach()) for k,v in terms.items()},parent_id=batch['metadata']['parent_id'],actual_input_sha256=batch['cpu_input_sha256'],parent_arrays_sha256=batch['parent']['arrays_sha256'],noise_seed=batch['noise_seed'])
def checkpoint(folder,model,opt,step,bind):
    path=folder/'checkpoints'/f'step{step:05d}.pth';path.parent.mkdir(exist_ok=True)
    if path.exists():
        saved=torch.load(path,map_location='cpu')
        if saved['parameter_sha256']!=state_digest(model) or saved['binding']!=bind:raise RuntimeError('Existing checkpoint is different')
        return path
    state=dict(model=model.state_dict(),optimizer=opt.state_dict(),step=step,binding=bind,parameter_sha256=state_digest(model),python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [])
    temp=path.with_suffix('.writing')
    if temp.exists():raise RuntimeError('Incomplete checkpoint retained for inspection')
    with temp.open('xb') as f:torch.save(state,f);f.flush();os.fsync(f.fileno())
    os.replace(temp,path);return path
def restore(path,model,opt,bind):
    p=torch.load(path,map_location='cpu')
    if p['binding']!=bind:raise RuntimeError('Resume configuration/source mismatch')
    model.load_state_dict(p['model'],strict=True);opt.load_state_dict(p['optimizer'])
    if state_digest(model)!=p['parameter_sha256']:raise RuntimeError('Checkpoint parameter mismatch')
    random.setstate(p['python_rng']);np.random.set_state(p['numpy_rng']);torch.set_rng_state(p['torch_rng'])
    if p['cuda_rng']:torch.cuda.set_rng_state_all(p['cuda_rng'])
    return p['step']
def evaluate_generated(model,bank,split,folder,step,device):
    path=folder/f'{split}.json'
    if path.exists():return load(path)
    model.eval();rows=[]
    with torch.no_grad():
        for i in range(bank.cfg['splits'][split]):
            value,terms=objective(model,bank.batch(split,i,device));rows.append(dict(index=i,loss=float(value),**{k:float(v) for k,v in terms.items()}))
    result=dict(step=step,split=split,mean_loss=float(np.mean([x['loss'] for x in rows])),rows=rows,used_for_automatic_checkpoint_selection=False)
    save(path,result);return result

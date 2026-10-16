"""Common native-image/gradient/pair objectives; no real-image or teacher target."""
from common import *
from objectives_base import robust_gray,translated
def objective(model,batch):
    output=model(batch['source']);r=output-batch['target'];lo,hi=batch['core'];crop=lambda x:x[...,lo:hi,lo:hi];v=crop(r)
    image=robust_gray(v);gradient=.5*(robust_gray(v[...,1:]-v[...,:-1])+robust_gray(v[...,1:,:]-v[...,:-1,:]))
    terms=[]
    for i,m in enumerate(batch['metadata']):
        terms.append(robust_gray(crop(r[2*i+1:2*i+2]-translated(r[2*i:2*i+1],m['shift_xy']))) if m['motion_observable'] else r[2*i:2*i+2].sum()*0)
    pair=torch.stack(terms).mean()
    return image+.2*gradient+.2*pair,dict(image=image,gradient=gradient,pair=pair)
def learning_rate(step,cfg):
    o=cfg['optimizer'];warm=o['warmup_updates']
    if step<=warm:return o['peak_lr']*step/warm
    return o['minimum_lr']+.5*(o['peak_lr']-o['minimum_lr'])*(1+math.cos(math.pi*(step-warm)/(cfg['updates']-warm)))
def update(m,opt,batch,step,cfg):
    m.train();opt.zero_grad(set_to_none=True)
    for group in opt.param_groups:group['lr']=learning_rate(step,cfg)
    value,terms=objective(m,batch)
    if not torch.isfinite(value):raise FloatingPointError('Nonfinite loss')
    value.backward();norm=torch.nn.utils.clip_grad_norm_(m.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True);opt.step()
    if any(not torch.isfinite(p).all() for p in m.parameters()):raise FloatingPointError('Nonfinite parameter')
    return dict(step=step,loss=float(value.detach()),terms={k:float(v.detach()) for k,v in terms.items()},gradient_norm=float(norm),learning_rate=learning_rate(step,cfg),parents=batch['ledger'])
def checkpoint(out,m,opt,step,binding):
    path=out/'checkpoints'/f'step{step:05d}.pth';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError(path)
    temporary=path.with_suffix('.writing');assert not temporary.exists()
    payload=dict(model=m.state_dict(),optimizer=opt.state_dict(),step=step,epoch=step/128,binding=binding,parameter_sha256=digest(m),python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all())
    torch.save(payload,temporary);os.replace(temporary,path);return path
def restore(path,m,opt,binding):
    p=torch.load(path,map_location='cpu');assert p['binding']==binding;m.load_state_dict(p['model'],strict=True);opt.load_state_dict(p['optimizer']);assert digest(m)==p['parameter_sha256']
    random.setstate(p['python_rng']);np.random.set_state(p['numpy_rng']);torch.set_rng_state(p['torch_rng']);torch.cuda.set_rng_state_all(p['cuda_rng']);return p['step']
def evaluate(m,bank,split,path,device='cuda'):
    if path.exists():return load(path)
    m.eval();rows=[]
    with torch.no_grad():
        for i in range(0,128,4):
            b=bank.batch(split,range(i,i+4),device);value,terms=objective(m,b);rows.append(dict(indices=list(range(i,i+4)),loss=float(value),**{k:float(v) for k,v in terms.items()}))
    result=dict(split=split,parents=128,mean_loss=float(np.mean([r['loss'] for r in rows])),batches=rows);save(path,result);return result

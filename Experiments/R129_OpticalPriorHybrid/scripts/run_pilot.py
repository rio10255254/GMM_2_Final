"""Four matched short runs; every actually consumed source is logged."""
import os,sys,ast,math,time,importlib.util
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import torch,numpy as np
from torch.nn import functional as F
from model.hybrid_v2 import Hybrid

MODEL_NAME_BASE='R129_OpticalPriorHybrid'

def setup(seed):
    torch.manual_seed(seed);np.random.seed(seed);torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)

def create(arm,plan):
    setup(plan['common_seed']);d=np.load(ROOT/'data/measured_psf_bank.npz');m=Hybrid(torch.from_numpy(d['mean']),torch.from_numpy(d['candidates']),**plan['arms'][arm]).to('cuda')
    m.initialize_from_r128(torch.load(plan['source_checkpoint']['path'],map_location='cpu')['model']);return m

def digest(m):
    import hashlib
    h=hashlib.sha256()
    for k,v in m.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

def loss(m,b,helpers):
    pred=m(b['source']);r=pred-b['target'];lo,hi=b['core'];crop=lambda a:a[...,lo:hi,lo:hi];v=crop(r);robust=helpers['robust_gray'];translate=helpers['translated']
    image=robust(v);gradient=.5*(robust(v[...,1:]-v[...,:-1])+robust(v[...,1:,:]-v[...,:-1,:]));pair=robust(crop(r[1:2]-translate(r[0:1],b['metadata']['shift_xy']))) if b['metadata']['motion_observable'] else r.sum()*0
    return image+.2*gradient+.2*pair,dict(image=float(image.detach()),gradient=float(gradient.detach()),pair=float(pair.detach()))

def main():
    plan=load(ROOT/'config/plan.json');impl=load(ROOT/'config/implementation_v2.json');assert sha(impl['active_implementation']['path'])==impl['active_implementation']['sha256'];assert load(ROOT/'results/integration_tests_v2.json')['passed']
    assert sha(plan['source_checkpoint']['path'])==plan['source_checkpoint']['sha256'] and sha(plan['calibration']['path'])==plan['calibration']['sha256']
    datafile=R128/'training/data.py';spec=importlib.util.spec_from_file_location('r129_shared_data',datafile);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);bank=module.Bank()
    objective=R128/'training/objectives.py';nodes=[n for n in ast.parse(objective.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ['robust_gray','translated']];helpers=dict(torch=torch,F=F,math=math);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(objective),'exec'),helpers)
    save(ROOT/'runs/pilot_started.json',dict(started_utc=now(),plan=record(ROOT/'config/plan.json'),implementation=record(ROOT/'config/implementation_v2.json'),source=record(__file__),data_source=record(datafile),loss_helper=record(objective),expected_updates=96,MODEL_NAME_BASE=MODEL_NAME_BASE))
    completed=[];initial=None;reference_hashes=None
    for arm in plan['arms']:
        m=create(arm,plan);folder=ROOT/'runs'/arm;folder.mkdir(parents=True,exist_ok=False);state=digest(m)
        if initial is None:initial=state
        assert state==initial
        torch.save(dict(model=m.state_dict(),arm=arm,step=0),folder/'initial.pth')
        dev=[]
        for step in [0,24]:
            if step==24:
                opt=torch.optim.AdamW(m.parameters(),lr=plan['learning_rate'],weight_decay=plan['weight_decay']);m.train();hashes=[];start=time.perf_counter();ledger=[]
                for update,index in enumerate(plan['train_indices'],1):
                    b=bank.batch('train',index,'cuda',epoch=0);hashes.append(b['cpu_input_sha256']);opt.zero_grad(set_to_none=True);value,terms=loss(m,b,helpers);assert torch.isfinite(value);value.backward()
                    g=torch.nn.utils.clip_grad_norm_(m.parameters(),5.,error_if_nonfinite=True);opt.step();assert all(torch.isfinite(x).all() for x in m.parameters())
                    row=dict(arm=arm,update=update,parent_id=b['metadata']['parent_id'],actual_input_sha256=b['cpu_input_sha256'],source_arrays_sha256=b['parent']['arrays_sha256'],noise_seed=b['noise_seed'],loss=float(value.detach()),gradient_norm=float(g),terms=terms)
                    ledger.append(row)
                    with (folder/'updates.jsonl').open('a',encoding='utf-8') as f:f.write(__import__('json').dumps(row)+'\n')
                    if update%6==0:print(__import__('json').dumps(dict(arm=arm,update=update,total=24,loss=row['loss'],seconds=round(time.perf_counter()-start,1))),flush=True)
                if reference_hashes is None:reference_hashes=hashes
                assert hashes==reference_hashes
                torch.save(dict(model=m.state_dict(),optimizer=opt.state_dict(),arm=arm,step=24,source_checkpoint=plan['source_checkpoint']),folder/'step24.pth')
                assert digest(m)!=initial
            m.eval();values=[]
            with torch.no_grad():
                for index in plan['dev_indices']:
                    b=bank.batch('dev',index,'cuda');value,terms=loss(m,b,helpers);values.append(dict(index=index,loss=float(value),**terms))
            dev.append(dict(step=step,rows=values,mean_loss=float(np.mean([v['loss'] for v in values]))))
        save(folder/'summary.json',dict(arm=arm,initial_parameter_digest=initial,final_parameter_digest=digest(m),updates=24,development=dev,checkpoint=record(folder/'step24.pth')));completed.append(load(folder/'summary.json'))
        del m;torch.cuda.empty_cache()
    assert sum(x['updates'] for x in completed)==96
    save(ROOT/'results/pilot_training.json',dict(completed_utc=now(),arms=completed,all4same_initial_tensors=True,all4same_consumed_inputs=True,total_updates=96,source=record(__file__),limited_short_pilot=True,not_model_promotion=True))
    print('All4matched24-updatepilotscomplete',flush=True)
if __name__=='__main__':main()

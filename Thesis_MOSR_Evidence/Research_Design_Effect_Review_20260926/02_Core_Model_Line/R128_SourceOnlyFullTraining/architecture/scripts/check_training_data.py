"""Independently exercise actual consumer, observation supervision and arm contrast."""
import sys,time,json
from common import *
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from collections import Counter
from training.data import Bank,digest
from training.engine import create,update,state_digest
from training.objectives import objective,observation_prediction

def main():
    start=time.perf_counter();cfg=load(ROOT/'config/study.json');bank=Bank()
    manifest=bank.manifest;entries=manifest['entries'];allmeta=[load(bank.root/e['metadata_path']) for e in entries]
    assert len({m['parent_id'] for m in allmeta})==768
    assert all(not m['real_or_SEM_answers_used'] and not m['external_source_inputs'] and m['native_field']==384 and m['core_slice']==[128,256,128,256] for m in allmeta)
    nonflat=[m['geometry_sha256'] for m in allmeta if m['category']!='flat_negative']
    assert len(set(nonflat))==len(nonflat)
    # Independently hash all loaded arrays on representatives chosen by input
    # metadata, including every family and largest physical support.
    train=[m for m in allmeta if m['split']=='train'];indices={next(m['index'] for m in train if m['category']==c) for c in cfg['categories']}
    indices.add(max(train,key=lambda m:m['psf']['radius_native'])['index'])
    selected=sorted(indices);checks=[]
    for index in selected:
        arrays,m,e=bank.read('train',index)
        with np.load(bank.root/e['arrays_path']) as f:
            assert all(digest(f[k])==m['array_sha256'][k] for k in f.files)
        b=bank.batch('train',index,'cuda',0);b2=bank.batch('train',index,'cuda',0);b3=bank.batch('train',index,'cuda',1)
        assert torch.equal(b['source'],b2['source'])
        if m['noise_sigma_gray']>0:assert b['cpu_input_sha256']!=b3['cpu_input_sha256']
        else:assert torch.equal(b['source'],b3['source'])
        with torch.no_grad():
            prediction=observation_prediction(b['latent_target'],b['kernel'],b['core'])[0,0].cpu().numpy()
        noiseless=arrays['noiseless'][0,128:256,128:256];delta=(prediction-noiseless)*255
        scale=(max(m['noise_sigma_gray'],.5)**2+1/12)**.5
        rms=float(np.sqrt(np.mean(delta.astype(float)**2))/scale);p99=float(np.quantile(np.abs(delta),.99)/scale)
        assert rms<=cfg['data_admission']['model_render_rms_noise_units_max'] and p99<=cfg['data_admission']['model_render_p99_noise_units_max']
        if m['category']=='clean_identity':assert torch.equal(b['source'],b['target'])
        checks.append(dict(index=index,category=m['category'],rms_noise_units=rms,p99_noise_units=p99,noise_repeat_exact=True,noise_epoch_change=m['noise_sigma_gray']>0))
    # Full16-pass ordering has no duplication within a pass, and matches all arms.
    orders=[]
    for epoch in range(16):
        order=bank.order(epoch)
        assert sorted(order.tolist())==list(range(512))
        orders.append(digest(order))
    assert len(set(orders))==16
    try:bank.batch('test',0,'cpu',0)
    except ValueError:pass
    else:raise AssertionError('Test was accepted as training')
    # One actual update for each category, with no old weights. These diagnostic
    # weights are separate from both declared full-training seeds.
    model,opt=create(1285998,'cuda',cfg);initial=state_digest(model);updates=[]
    for step,index in enumerate(selected,1):
        b=bank.batch('train',index,'cuda',0)
        updates.append(update(model,opt,b,step,'P',cfg))
    assert state_digest(model)!=initial
    # At the exact same learned state the sole contrast is the observation term.
    b=bank.batch('train',selected[0],'cuda',0);model.train();d=model.forward_details(b['source'])
    li,ti=objective(d,b,cfg['loss_weights'],0.);lp,tp=objective(d,b,cfg['loss_weights'],.02)
    assert all(float(ti[k])==float(tp[k]) for k in cfg['loss_weights'])
    contrast_error=abs(float((lp-li)-.02*tp['observation_noise_units']))
    assert contrast_error<1e-5
    parameters=list(model.parameters())
    gi=torch.autograd.grad(li,parameters,retain_graph=True)
    gp=torch.autograd.grad(lp,parameters,retain_graph=True)
    go=torch.autograd.grad(.02*tp['observation_noise_units'],parameters)
    gradient_error=max(float((p-i-o).abs().max())/max(1.,float(p.abs().max())) for p,i,o in zip(gp,gi,go))
    assert gradient_error<2e-5 and all(p.requires_grad for p in model.parameters())
    result=dict(passed=True,manifest=record(bank.root/'manifest.json'),parents=768,unique_nonflat_geometries=len(nonflat),semantic_checks=checks,epoch_order_sha256=orders,diagnostic_optimizer_updates=len(updates),diagnostic_weights_not_used_for_full_training=True,updates=updates,arm_loss_difference_error=contrast_error,arm_gradient_difference_error=gradient_error,only_arm_difference='0.02 times true-simulator observation supervision after forward',train_photometry=dict(low_gray_range=[min(m['photometry']['low_gray'] for m in train),max(m['photometry']['low_gray'] for m in train)],contrast_range=[min(m['photometry']['high_gray']-m['photometry']['low_gray'] for m in train),max(m['photometry']['high_gray']-m['photometry']['low_gray'] for m in train)]),seconds=time.perf_counter()-start,source_sha256={str(p):sha(p) for folder in ['training','model'] for p in (ROOT/folder).glob('*.py')})
    save(ROOT/'results/training_data_consumer_preflight.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['updates','source_sha256','epoch_order_sha256']}),flush=True)

if __name__=='__main__':main()

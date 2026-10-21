"""Check fresh initialization, arithmetic parity, real backward and exact resume."""
import sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from data_bank import Bank
from engine import update,checkpoint,restore,objective
def main():
    out=ROOT/'results/preflight';out.mkdir(exist_ok=False);cfg=load(ROOT/'config/training.json');prov=load(ROOT/'config/provenance.json')
    save(out/'started.json',dict(utc=now(),source=record(__file__)))
    for item in prov['protected']:assert sha(item['path'])==item['sha256']
    bank=Bank();groups={s:set() for s in cfg['splits']};counts={s:0 for s in groups}
    for (split,index),e in bank.entries.items():
        a,meta,_=bank.read(split,index);groups[split].add(meta['geometry_sha256']);counts[split]+=1
        assert a['source'].shape==(2,384,384) and a['target'].shape==(2,384,384)
    assert counts==cfg['splits'];assert all(not(groups[a]&groups[b]) for a in groups for b in groups if a!=b)
    m,opt=create();old,_=create(original=True)
    assert m.state_dict().keys()==old.state_dict().keys() and all(torch.equal(v,old.state_dict()[k]) for k,v in m.state_dict().items())
    assert not np.array_equal(m.network.e1[0].conv.weight.detach().cpu().flatten()[:8].numpy(),np.array(prov['legacy_neural_probe']['e1.0.conv.weight']))
    b=bank.batch('train',[0,1,2,3],'cuda',0);m.eval();old.eval()
    with torch.no_grad():a=m(b['source']);reference=old(b['source'])
    maximum=float(abs(a-reference).max());assert maximum<1e-6
    del old;torch.cuda.empty_cache()
    m.train();value,_=objective(m,b);value.backward()
    gradients={n:float(p.grad.norm()) for n,p in m.named_parameters() if p.grad is not None}
    assert gradients['network.e1.0.conv.weight']>0 and gradients['network.out.weight']>0 and gradients['network.boundary_adapter.delta.weight']>0
    assert m.network.weak_psf_block.last_beta>0
    initial=digest(m);rows=[];timer=time.perf_counter()
    for step in range(1,5):rows.append(update(m,opt,bank.batch('train',bank.order(0)[(step-1)*4:step*4],'cuda',0),step,cfg))
    seconds=time.perf_counter()-timer;final=digest(m);assert initial!=final
    m2,o2=create()
    for step in range(1,3):update(m2,o2,bank.batch('train',bank.order(0)[(step-1)*4:step*4],'cuda',0),step,cfg)
    cp=checkpoint(out,m2,o2,2,'preflight_only')
    m3,o3=create();assert restore(cp,m3,o3,'preflight_only')==2
    for step in range(3,5):update(m3,o3,bank.batch('train',bank.order(0)[(step-1)*4:step*4],'cuda',0),step,cfg)
    assert digest(m3)==final
    # Native field feasibility without creating a scientifically scored evaluation.
    fresh,_=create();fresh.eval();sample=np.zeros((1,1,1536,2048),np.float32)+.5;torch.cuda.reset_peak_memory_stats();tick=time.perf_counter()
    with torch.no_grad():full=fresh(torch.from_numpy(sample).cuda())
    assert full.shape==(1,1,1536,2048) and torch.isfinite(full).all();torch.cuda.synchronize()
    result=dict(passed=True,completed_utc=now(),source=record(__file__),source_counts=counts,geometry_overlap=0,fresh_constructor_state_digest=initial,original_vs_deterministic_forward_max_difference=maximum,gradients=gradients,active_weak_beta=float(fresh.network.weak_psf_block.last_beta),parameters=sum(p.numel() for p in fresh.parameters()),probe_updates=8,probe_weights_discarded=True,optimizer_resume_model_exact=True,update_seconds=seconds/4,estimated_training_minutes_excluding_evaluation=seconds/4*cfg['updates']/60,full_native_inference_seconds=time.perf_counter()-tick,full_peak_memory_bytes=torch.cuda.max_memory_allocated(),rows=rows)
    save(out/'complete.json',result);print('Preflight passed',result['parameters'],'parameters',result['update_seconds'],'seconds/update',flush=True)
if __name__=='__main__':
    try:main()
    except BaseException:
        save(ROOT/'results/preflight/failure.json',dict(utc=now(),error=traceback.format_exc()));raise

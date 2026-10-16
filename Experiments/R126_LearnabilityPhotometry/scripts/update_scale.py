"""One preregistered update-scale intervention, preserving all four initial runs."""
from fixed_example import fixture,tensors,metrics
from common import *

def main():
    setup()
    if not (ROOT/'results/fixed_example_summary.json').exists():raise RuntimeError('Initial four controls must complete first')
    cfg=json.loads((ROOT/'config/update_scale_followup.json').read_text());arrays,meta,dh=fixture();source,a=tensors(arrays)
    summaries=[]
    for arm in cfg['arms']:
        run_id=f'fixed_{arm}_full_lr001';out=ROOT/'runs'/run_id;out.mkdir(parents=True,exist_ok=False)
        m=new_model(arm=='B',cfg['seed'],meta['profile']);initial=out/'step0000.pth'
        checkpoint(initial,pack(m,run_id,cfg['seed'],0,dh))
        p=[v for v in m.parameters() if v.requires_grad];opt=torch.optim.AdamW(p,lr=cfg['learning_rate'],weight_decay=1e-5)
        with torch.no_grad():before=metrics(m,m.forward_details(source),a)
        start=time.perf_counter()
        with (out/'ledger.jsonl').open('x') as f:
            for step in range(1,cfg['updates']+1):
                m.train();opt.zero_grad(set_to_none=True);d=m.forward_details(source)
                loss,terms=objective(m,d,source,a,meta,CFG['loss_weights'],False);loss.backward()
                grad=float(torch.nn.utils.clip_grad_norm_(p,5));opt.step()
                if not np.isfinite(float(loss)) or not np.isfinite(grad):raise FloatingPointError('Nonfinite update')
                f.write(json.dumps(dict(step=step,loss=float(loss.detach()),gradient_norm_before_clip=grad,actual_input_sha256=thash(source),data_manifest_sha256=dh,protocol_sha256=sha(ROOT/'config/update_scale_followup.json'),terms={k:float(v.detach()) for k,v in terms.items()}))+'\n');f.flush()
                if step%32==0:
                    with torch.no_grad():cur=metrics(m,m.forward_details(source),a)
                    print(json.dumps(dict(run_id=run_id,step=step,seconds=time.perf_counter()-start,**cur)),flush=True)
        m.eval()
        with torch.no_grad():dd=m.forward_details(source);after=metrics(m,dd,a)
        checkpoint(out/'step0128.pth',pack(m,run_id,cfg['seed'],cfg['updates'],dh,sha(initial)))
        np.savez_compressed(out/'outputs.npz',source=arrays['source'][...,128:192,128:192],target=arrays['target'][...,128:192,128:192],output=dd.output.cpu().numpy()[:,0,128:192,128:192])
        result=dict(run_id=run_id,completed_updates=128,before=before,after=after,native_reduction_fraction=1-after['native_mae_gray']/before['native_mae_gray'],seconds=time.perf_counter()-start,checkpoint_sha256=sha(out/'step0128.pth'),ledger_sha256=sha(out/'ledger.jsonl'))
        result['learnability_signal']=result['native_reduction_fraction']>=.2
        save(out/'summary.json',result);summaries.append(result)
    save(ROOT/'results/update_scale_summary.json',dict(completed_updates=256,runs=summaries,protocol_sha256=sha(ROOT/'config/update_scale_followup.json')))

if __name__=='__main__':main()

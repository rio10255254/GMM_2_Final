"""Data-only matched comparison after independent learnability diagnosis."""
import argparse
from photometry_data import *

def config():return json.loads((ROOT/'config/photometry_pilot.json').read_text())
def implementation():return {str(p):sha(p) for p in [Path(__file__),ROOT/'scripts/common.py',ROOT/'scripts/photometry_data.py',R125/'prototype/network.py',R125/'training/objectives.py',R125/'training/context.py',R125/'prototype/factorized_observation.py']}

def prepare():
    setup();cfg=config();audit=json.loads((ROOT/'results/photometry_admission.json').read_text())
    assert audit['pilot_admitted'] and audit['slots_sha256']==sha(ROOT/'config/photometry_slots.json')
    for p,h in audit['script_sources'].items():assert sha(p)==h
    out=ROOT/'runs/photometry_initial';out.mkdir(exist_ok=False)
    records=[]
    for seed in cfg['seeds']:
        same=None
        for arm in ['P','Q']:
            m=new_model(True,seed);hashes={n:thash(p) for n,p in m.named_parameters()}
            if same is not None:assert hashes==same
            same=hashes;path=out/f'{arm}_s{seed}_step0000.pth'
            p=pack(m,arm,seed,0,sha(ROOT/'config/photometry_slots.json'));p.update(protocol_sha256=sha(ROOT/'config/photometry_pilot.json'),implementation_sources=implementation())
            checkpoint(path,p);records.append(dict(arm=arm,seed=seed,path=str(path),sha256=sha(path),learned_hashes=hashes))
    save(out/'manifest.json',dict(records=records,shared_initial_tensors_verified=True))

def run(arm,seed):
    setup();cfg=config();assert seed in cfg['seeds'] and arm in ['P','Q']
    audit=json.loads((ROOT/'results/photometry_admission.json').read_text());assert audit['pilot_admitted']
    for p,h in audit['script_sources'].items():assert sha(p)==h
    slots=json.loads((ROOT/'config/photometry_slots.json').read_text());dh=sha(ROOT/'config/photometry_slots.json');assert dh==audit['slots_sha256']
    initial=ROOT/'runs/photometry_initial'/f'{arm}_s{seed}_step0000.pth';p=torch.load(initial,map_location='cpu',weights_only=True)
    assert p['protocol_sha256']==sha(ROOT/'config/photometry_pilot.json') and p['implementation_sources']==implementation()
    out=ROOT/'runs'/f'photo_{arm}_s{seed}';out.mkdir(exist_ok=False)
    m=new_model(True,seed);m.load_state_dict(p['model_state'],strict=True)
    params=[v for v in m.parameters() if v.requires_grad];opt=torch.optim.AdamW(params,lr=cfg['learning_rate'],weight_decay=1e-5)
    hashes={n:thash(v) for n,v in m.named_parameters()};start=time.perf_counter()
    with (out/'ledger.jsonl').open('x') as f:
        for slot in slots:
            source,a,meta,e=batch(m,slot,arm=='Q');m.train();opt.zero_grad(set_to_none=True)
            actual_hash=thash(source);d=m.forward_details(source);loss,terms=objective(m,d,source,a,meta,CFG['loss_weights'],False)
            loss.backward();grad=float(torch.nn.utils.clip_grad_norm_(params,5));opt.step()
            if not np.isfinite(float(loss)) or not np.isfinite(grad) or any(not torch.isfinite(v).all() for v in params):raise FloatingPointError('Invalid training update')
            row=dict(arm=arm,seed=seed,step=slot['step'],slot=slot,scene_id=meta['scene_id'],source_original_arrays_sha256=e['sha256']['arrays'],actual_input_sha256=actual_hash,actual_input_shape=list(source.shape),window=meta['R126_window'],photometry=meta['photometry'],intervention=meta['photometry_intervention'],observation_kernel_sha256=thash(m.observation.kernel),loss=float(loss.detach()),terms={k:float(v.detach()) for k,v in terms.items()},gradient_norm_before_clip=grad,targets_enter_forward=False,qualified_real_optics=False,model_forward_inputs=['source','known_simulation_profile'],seconds=time.perf_counter()-start)
            f.write(json.dumps(row)+'\n');f.flush()
            if slot['step']%16==0:print(json.dumps(dict(arm=arm,seed=seed,step=slot['step'],loss=row['loss'],seconds=row['seconds'])),flush=True)
            del source,a,d,loss,terms
    changed=[n for n,v in m.named_parameters() if thash(v)!=hashes[n]]
    assert changed and not any(n.startswith('geometry_head.') for n in changed)
    final=out/'step0128.pth';payload=pack(m,arm,seed,128,dh,sha(initial));payload.update(protocol_sha256=p['protocol_sha256'],implementation_sources=implementation(),optimizer_state=opt.state_dict())
    checkpoint(final,payload)
    save(out/'summary.json',dict(status='128_updates_complete',arm=arm,seed=seed,completed_updates=len(slots),checkpoint=str(final),checkpoint_sha256=sha(final),ledger_sha256=sha(out/'ledger.jsonl'),initial_sha256=sha(initial),changed_parameters=changed,geometry_frozen=True,seconds=time.perf_counter()-start,formal_promotion=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--arm');p.add_argument('--seed',type=int);args=p.parse_args()
    if args.prepare:prepare()
    else:run(args.arm,args.seed)

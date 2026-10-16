from pathlib import Path
import json,hashlib,torch
P=Path(r'D:\GMM_2_Final\Experiments\R137_WeakPSFFeature');R=P.parent/'R130_Clean';torch.set_num_threads(2)
cpinfo=json.loads((P/'runs/formal_8192/latest_checkpoint.json').read_text());cp=torch.load(cpinfo['path'],map_location='cpu',weights_only=False)
assert hashlib.sha256(Path(cpinfo['path']).read_bytes()).hexdigest()==cpinfo['sha256']
assert cp['model_name']=='R137-WeakPSF' and cp['optical_mode']=='feature_single' and cp['config']['model']['optical_gain']==.02
new=[json.loads(x) for x in (P/'runs/formal_8192/updates.jsonl').read_text().splitlines()][:cp['step']]
old=[json.loads(x) for x in (R/'runs/formal_8192/updates.jsonl').read_text().splitlines()][:cp['step']]
for a,b in zip(new,old):
 for k in ['step','epoch','position','parent_id','parent_sha256','input_sha256','noise_seed','learning_rate']:assert a[k]==b[k],(a['step'],k)
assert all(torch.isfinite(v).all() for v in cp['model'].values())
assert cp['model']['optical_adapter.weight'].abs().max()>0
assert all(int(v['step'])==cp['step'] for v in cp['optimizer']['state'].values())
for rel,h in json.loads((P/'config/source_lock.json').read_text()).items():assert hashlib.sha256((P/rel).read_bytes()).hexdigest()==h,rel
out=dict(step=cp['step'],checkpoint_sha256=cpinfo['sha256'],same_order_noise_source_hashes_and_lr_as_R130=len(new),adapter_weight_absmax=float(cp['model']['optical_adapter.weight'].abs().max()),all_optimizer_steps_match=True,all_frozen_execution_sources_unchanged=True,PSF_gain=.02,formal_completion=False)
(P/'results/independent_early_training_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))

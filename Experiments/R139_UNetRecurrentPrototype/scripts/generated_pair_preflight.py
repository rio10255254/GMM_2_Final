"""Representative R130 synthetic pair with R139 U-Net, disposable two-update probe."""
from pathlib import Path
import json,sys,time,torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT_ROOT / 'Experiments/R130_Clean'))
sys.path.insert(0,str(ROOT))
from model import Model
from training_policy import optimizer,apply_epoch_policy,project_beta_after_step
from dataset_r130_clean import Bank
from losses_r130_clean import objective
from utils import setup
cfg=json.loads((ROOT/'config/model.json').read_text(encoding='utf-8-sig'))
data_cfg=json.loads(Path(str(PROJECT_ROOT / 'Experiments/R130_Clean/config_r130_clean.yaml')).read_text(encoding='utf-8-sig'))
setup(139001);model=Model(cfg,ROOT).cuda();opt=optimizer(model,base_lr=1e-3,optical_lr_multiplier=.05)
bank=Bank(data_cfg);batch=bank.batch('train',0,'cuda',0)
values=[]
for epoch in [0,2]:
    stage=apply_epoch_policy(model,epoch)
    opt.zero_grad(set_to_none=True)
    start=time.perf_counter();pred=model(batch['source']);loss,terms=objective(pred,batch)
    assert torch.isfinite(loss)
    loss.backward()
    optical_grad=model.refiner.optics.gating[-1].weight.grad
    psf_grad_nonzero=optical_grad is not None and bool(torch.isfinite(optical_grad).all()) and float(optical_grad.abs().max())>0
    opt.step();project_beta_after_step(model)
    values.append(dict(epoch=epoch,loss=float(loss),image=float(terms['image']),gradient=float(terms['gradient']),pair=float(terms['pair']),PSF_gate_grad_nonzero=psf_grad_nonzero,PSF_scale=stage['beta_scale'],seconds=time.perf_counter()-start))
assert values[1]['PSF_gate_grad_nonzero']
assert 0 <= model.refiner.optics.beta.item() <= .1
result=dict(status='discarded_real_pair_smoke',source_parent_id=batch['parent_id'],batch_shape=list(batch['source'].shape),core=list(batch['core']),updates=values,trained_checkpoint_created=False)
(ROOT/'results/generated_pair_preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))

"""Data, physics, shift, loss and learned-smoke gates before R148 formal training."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
import numpy as np,torch
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from losses import objective,moments,stage_terms,translated,normalize_view
from model import Model
from utils import load,save,sha,now,setup,model_config,train_config,verify_bank_lock
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=('initial','final'),required=True);a=p.parse_args();cfg=train_config();mc=model_config();setup(cfg['model_seed']);bank_lock=verify_bank_lock();complete=load(ROOT/'results/data_generation_complete.json');manifest=load(ROOT/'data/payload/manifest.json');assert complete['state']=='complete' and complete['parents']==768 and complete['views']==3072 and sha(ROOT/'data/payload/manifest.json')==complete['manifest_sha256'];assert manifest['base_lock']['psf_bank_sha256']==bank_lock['bank_sha256']
 for e in manifest['entries']:
  assert sha(ROOT/'data/payload'/e['arrays'])==e['arrays_sha256'];assert sha(ROOT/'data/payload'/e['metadata'])==e['metadata_sha256']
 counts=np.array(complete['psf_counts_train']);assert counts.max()-counts.min()<=4;assert complete['maximum_photometric_clip_fraction']<.001
 data=Bank(cfg);device='cuda';model=Model(mc,ROOT).to(device).eval();checkpoint=None
 if a.stage=='final':
  rec=load(ROOT/'runs/smoke_64/latest.json');assert rec['step']==64 and sha(rec['path'])==rec['sha256'];checkpoint=torch.load(rec['path'],map_location='cpu',weights_only=False);model.load_state_dict(checkpoint['model'])
 # PSF invariants.
 flat=torch.full((3,1,320,320),.37,device=device);indices=torch.tensor([-2,-1,3],device=device);blur=model.optics.blur(flat,indices);flat_error=float((blur-flat).abs().max());assert flat_error<2e-6
 impulse=torch.zeros((1,1,320,320),device=device);impulse[...,160,160]=1;bi=model.optics.blur(impulse);peak=np.unravel_index(int(bi[0,0].argmax()),(320,320));assert peak==(160,160)
 # Native refiner must preserve all integer phases away from its boundary.
 f=torch.rand((1,9,320,320),device=device);shifted=torch.roll(f,1,-1)
 with torch.inference_mode():r0=model.refiner(f);r1=model.refiner(shifted)
 radius=model.refiner.dependency_radius+2;shift_error=float((r1[...,radius:-radius,radius+1:-radius]-r0[...,radius:-radius,radius:-radius-1]).abs().max());assert shift_error<2e-6
 # Tiled and whole execution are the same on a representative field.
 x=torch.rand((1,1,640,640),device=device)*.7+.15
 with torch.inference_mode():full=model(x);tiled=model.forward_tiled(x)
 tile_error=float((full-tiled).abs().max());assert tile_error<3e-6
 # Every declared objective reaches the trained image output and model parameters.
 b=data.batch('dev',0,device);model.train();_,states=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(states,b,model,cfg);model.zero_grad(set_to_none=True);loss.backward();gradient_norm=float(torch.sqrt(sum((p.grad.square().sum() for p in model.parameters() if p.grad is not None))));assert gradient_norm>0 and torch.isfinite(torch.tensor(gradient_norm));assert all(float(v)>=0 and torch.isfinite(v) for v in terms.values())
 # Direct output-moment contract: a right-shifted/larger soft disk must receive gradients back toward target.
 yy,xx=torch.meshgrid(torch.linspace(-1,1,128,device=device),torch.linspace(-1,1,128,device=device),indexing='ij');target=torch.sigmoid((.35-torch.sqrt(xx.square()+yy.square()))*80)[None,None];cx=torch.tensor(.08,device=device,requires_grad=True);rad=torch.tensor(.42,device=device,requires_grad=True);pred=torch.sigmoid((rad-torch.sqrt((xx-cx).square()+yy.square()))*80)[None,None];geom=(moments(pred)-moments(target)).abs().mean()*100;gc,gr=torch.autograd.grad(geom,(cx,rad));assert float(gc)>0 and float(gr)>0
 # The stored multi-view target follows its declared motion after photometric normalization.
 candidate=next(e for e in manifest['entries'] if e['split']=='dev' and e['category']=='dense_close_structures')
 arrays,meta,_=data.read('dev',candidate['index']);target_t=torch.from_numpy(arrays['target'][:,None]).to(device);norm=normalize_view(target_t);align=[]
 for v in range(1,4):
  aligned=translated(norm[0:1],torch.tensor(meta['views'][v]['shift_xy'],device=device));align.append(float((norm[v:v+1]-aligned)[...,128:256,128:256].abs().mean()))
 target_alignment=max(align);assert target_alignment<.08
 result=dict(passed=True,stage=a.stage,model=mc['model_name'],parents=768,views=3072,train_psf_count_range=[int(counts.min()),int(counts.max())],maximum_clip_fraction=complete['maximum_photometric_clip_fraction'],constant_image_max_error=flat_error,impulse_peak=[int(v) for v in peak],native_refiner_integer_shift_max_error=shift_error,full_tiled_max_error=tile_error,loss=float(loss),loss_terms={k:float(v) for k,v in terms.items()},model_gradient_norm=gradient_norm,moment_center_gradient=float(gc),moment_radius_gradient=float(gr),target_normalized_alignment_max=target_alignment,parameter_count=sum(p.numel() for p in model.parameters()),checkpoint_sha256=None if checkpoint is None else sha(ROOT/'runs/smoke_64/latest.json'),completed_utc=now())
 if a.stage=='final':
  initial=load(ROOT/'runs/smoke_64/dev_initial.json');after=load(ROOT/'runs/smoke_64/dev_00064.json') if (ROOT/'runs/smoke_64/dev_00064.json').exists() else None
  # Smoke does not run scheduled dev; independently evaluate four fixed parents now.
  model.eval();values=[]
  with torch.inference_mode():
   for i in range(4):
    bb=data.batch('dev',i,device);_,ss=model(bb['source'],bb['operator_psf_indices'],True);ll,_=objective(ss,bb,model,cfg);values.append(float(ll))
  result['smoke_dev_initial_mean']=initial['mean_loss'];result['smoke_dev_final_mean']=sum(values)/len(values);result['smoke_updates']=64;result['passed']=result['passed'] and result['smoke_dev_final_mean']<result['smoke_dev_initial_mean'];assert result['passed']
 save(ROOT/('results/preflight.json' if a.stage=='final' else 'results/preflight_initial.json'),result);print('PREFLIGHT_PASS',a.stage,result,flush=True)
if __name__=='__main__':main()

"""Release gates for R150 matched geometry with fixed mean PSF."""
from __future__ import annotations
from pathlib import Path
import argparse,sys
import numpy as np,torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1];R149=Path(str(PROJECT_ROOT / 'Experiments/R149_MatchedGeometryLocalBoundary'));sys.path.insert(0,str(ROOT))
from dataset import Bank
from losses import objective,stage_terms
from model import Model
from utils import load,save,sha,now,setup,model_config,train_config,verify_bank_lock,verify_data_lock
SEEDS=(1490201,1490202)
def edge_center(x):
 p=torch.cat((x[...,1:2].flip(-1),x,x[...,-2:-1].flip(-1)),-1);p=torch.cat((p[...,1:2,:].flip(-2),p,p[...,-2:-1,:].flip(-2)),-2);gx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;gy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5;w=gx.abs()+gy.abs();h,ww=x.shape[-2:];yy=torch.arange(h,device=x.device)[None,None,:,None];xx=torch.arange(ww,device=x.device)[None,None,None,:];m=w.sum((-2,-1))+1e-8;return torch.stack(((w*xx).sum((-2,-1))/m,(w*yy).sum((-2,-1))/m),-1)[:,0]
def inherited_control(path,bank,cfg):
 cp=torch.load(path,map_location='cpu',weights_only=False);assert cp['loss_mode']=='global' and cp['step']==512;m=Model(model_config(),ROOT).cuda().eval();m.load_state_dict(cp['model'],strict=True);matched=[e['index'] for e in bank.manifest['entries'] if e['split']=='dev' and e['category']=='matched_nine_circles'];values=[]
 with torch.inference_mode():
  for index in matched:
   b=bank.batch('dev',index,'cuda');_,states=m(b['source'],b['operator_psf_indices'],True);t=stage_terms(states[-1],b,cfg,'local');values.append({k:float(t[k]) for k in ('image','boundary_local','boundary_global')})
 yy,xx=torch.meshgrid(torch.arange(384,device='cuda'),torch.arange(384,device='cuda'),indexing='ij');clean=torch.sigmoid((30-torch.sqrt((xx-192.)**2+(yy-192.)**2))*2)[None,None];source=m.optics.blur(clean);shift=torch.roll(source,1,-1)
 with torch.inference_mode():a=m(source);c=m(shift);center=float(torch.linalg.vector_norm((edge_center(c[...,128:256,128:256])-edge_center(a[...,128:256,128:256]))-torch.tensor([1.,0.],device='cuda')))
 return dict(matched_image=float(np.mean([x['image'] for x in values])),matched_local_boundary=float(np.mean([x['boundary_local'] for x in values])),matched_global_boundary=float(np.mean([x['boundary_global'] for x in values])),center_error_px=center)
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=('initial','final'),required=True);a=p.parse_args();cfg=train_config();mc=model_config();setup(cfg['model_seed']);verify_bank_lock();data=verify_data_lock();manifest=load(ROOT/'data/manifest.json');assert sha(ROOT/'data/manifest.json')=='e6c02182f74d0e6e9bcd39143dd57c0dc3419f9a54a340db1a7fdfc39ab32972' and data['overlay_entries']==96 and manifest['real_or_SEM_answers_used'] is False;bank=Bank(cfg);b=bank.batch('dev',manifest['replacements']['dev'][0],'cuda');assert b['category']=='matched_nine_circles' and (b['operator_psf_indices']==-1).all()
 model=Model(mc,ROOT).cuda().eval();native_total=max(50+mc['native_stages']*model.stages[0].dependency_radius,model.context.dependency_radius+mc['native_stages']*model.stages[0].dependency_radius);assert native_total<=144;flat=torch.full((3,1,384,384),.4,device='cuda');constant=float((model.optics.blur(flat,torch.tensor([-2,-1,5],device='cuda'))-flat).abs().max());assert constant<2e-6;x=torch.rand((1,1,640,640),device='cuda')*.7+.15
 with torch.inference_mode():parity=float((model(x)-model.forward_tiled(x)).abs().max());assert parity<3e-6
 model.train();_,states=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(states,b,model,cfg,'global');model.zero_grad(set_to_none=True);loss.backward();grad=float(torch.sqrt(sum(q.grad.square().sum() for q in model.parameters() if q.grad is not None)));assert grad>0
 result=dict(passed=True,stage=a.stage,model=mc['model_name'],parameter_count=sum(q.numel() for q in model.parameters()),data_manifest_sha256=data['manifest_sha256'],overlay_parents=data['overlay_entries'],operator_is_mean=True,total_output_dependency_radius_px=native_total,constant_error=constant,full_tiled_max_error=parity,initial_loss=float(loss),initial_terms={k:float(v) for k,v in terms.items()},gradient_norm=grad,completed_utc=now())
 if a.stage=='final':
  controls=[]
  for seed in SEEDS:
   done=load(R149/f'runs/short_global_{seed}/short_complete.json');path=Path(done['checkpoint']['path']);assert done['updates']==512 and done['loss_mode']=='global' and done['dev_final']<done['dev_initial'] and sha(path)==done['checkpoint']['sha256'];controls.append(dict(seed=seed,dev_initial=done['dev_initial'],dev_final=done['dev_final'],checkpoint_sha256=done['checkpoint']['sha256'],**inherited_control(path,bank,cfg)))
  smoke=load(ROOT/'runs/smoke_64/short_complete.json');assert smoke['updates']==64 and smoke['loss_mode']=='global' and smoke['dev_final']<smoke['dev_initial'] and sha(smoke['checkpoint']['path'])==smoke['checkpoint']['sha256'];result['inherited_exact_design_controls']=controls;result['smoke']=smoke;result['control_dev_final_range']=[min(x['dev_final'] for x in controls),max(x['dev_final'] for x in controls)];result['control_matched_local_boundary_range']=[min(x['matched_local_boundary'] for x in controls),max(x['matched_local_boundary'] for x in controls)];result['passed']=result['passed'] and max(x['center_error_px'] for x in controls)<.001 and result['control_matched_local_boundary_range'][1]/result['control_matched_local_boundary_range'][0]<1.05;assert result['passed']
 save(ROOT/('results/preflight_initial.json' if a.stage=='initial' else 'results/preflight.json'),result);print('PREFLIGHT_PASS',a.stage,result,flush=True)
if __name__=='__main__':main()

"""Data, local-boundary, architecture and matched-control gates for R149."""
from __future__ import annotations
from pathlib import Path
import argparse,sys
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from losses import objective,local_boundary_error,stage_terms
from model import Model
from utils import load,save,sha,now,setup,model_config,train_config,verify_bank_lock,verify_data_lock
SEEDS=(1490201,1490202)
def edge_center(x):
 p=torch.cat((x[...,1:2].flip(-1),x,x[...,-2:-1].flip(-1)),-1);p=torch.cat((p[...,1:2,:].flip(-2),p,p[...,-2:-1,:].flip(-2)),-2);gx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;gy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5;w=gx.abs()+gy.abs();h,ww=x.shape[-2:];yy=torch.arange(h,device=x.device)[None,None,:,None];xx=torch.arange(ww,device=x.device)[None,None,None,:];m=w.sum((-2,-1))+1e-8;return torch.stack(((w*xx).sum((-2,-1))/m,(w*yy).sum((-2,-1))/m),-1)[:,0]
def learned_checks(path,loss_mode,bank,cfg):
 cp=torch.load(path,map_location='cpu',weights_only=False);m=Model(model_config(),ROOT).cuda().eval();m.load_state_dict(cp['model']);matched=[e['index'] for e in bank.manifest['entries'] if e['split']=='dev' and e['category']=='matched_nine_circles'];values=[]
 with torch.inference_mode():
  for index in matched:
   b=bank.batch('dev',index,'cuda');_,states=m(b['source'],b['operator_psf_indices'],True);t=stage_terms(states[-1],b,cfg,'local');values.append({k:float(t[k]) for k in ('image','gradient','pair_output','boundary_local','boundary_global')})
 yy,xx=torch.meshgrid(torch.arange(384,device='cuda'),torch.arange(384,device='cuda'),indexing='ij');clean=torch.sigmoid((30-torch.sqrt((xx-192.)**2+(yy-192.)**2))*2)[None,None];source=m.optics.blur(clean);shift=torch.roll(source,1,-1)
 with torch.inference_mode():a=m(source);c=m(shift);center_error=float(torch.linalg.vector_norm((edge_center(c[...,128:256,128:256])-edge_center(a[...,128:256,128:256]))-torch.tensor([1.,0.],device='cuda')))
 return dict(matched_parents=len(matched),matched_image=float(np.mean([x['image'] for x in values])),matched_gradient=float(np.mean([x['gradient'] for x in values])),matched_pair=float(np.mean([x['pair_output'] for x in values])),matched_local_boundary=float(np.mean([x['boundary_local'] for x in values])),matched_global_boundary=float(np.mean([x['boundary_global'] for x in values])),center_error_px=center_error)
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=('initial','final'),required=True);a=p.parse_args();cfg=train_config();mc=model_config();setup(cfg['model_seed']);verify_bank_lock();lock=verify_data_lock();manifest=load(ROOT/'data/manifest.json');complete=load(ROOT/'results/data_complete.json');assert complete['overlay_parents']==96 and complete['matched_counts']=={'train':64,'dev':16,'test':16};assert manifest['real_or_SEM_answers_used'] is False;assert 24<=complete['matched_pitch_range'][0]<=complete['matched_pitch_range'][1]<=36 and 6<=complete['matched_radius_range'][0]<=complete['matched_radius_range'][1]<=12
 bank=Bank(cfg);b=bank.batch('dev',manifest['replacements']['dev'][0],'cuda');assert (b['operator_psf_indices']==-1).all() and b['category']=='matched_nine_circles';model=Model(mc,ROOT).cuda().eval();native_total=max(50+mc['native_stages']*model.stages[0].dependency_radius,model.context.dependency_radius+mc['native_stages']*model.stages[0].dependency_radius);assert native_total<=144
 flat=torch.full((3,1,384,384),.4,device='cuda');constant_error=float((model.optics.blur(flat,torch.tensor([-2,-1,5],device='cuda'))-flat).abs().max());assert constant_error<2e-6;x=torch.rand((1,1,640,640),device='cuda')*.7+.15
 with torch.inference_mode():parity=float((model(x)-model.forward_tiled(x)).abs().max());assert parity<3e-6
 model.train();_,states=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(states,b,model,cfg,'local');model.zero_grad(set_to_none=True);loss.backward();gradient_norm=float(torch.sqrt(sum(q.grad.square().sum() for q in model.parameters() if q.grad is not None)));assert gradient_norm>0
 axis=torch.linspace(-1,1,96,device='cuda');yy,xx=torch.meshgrid(axis,axis,indexing='ij');sdf=(.38-torch.sqrt(xx.square()+yy.square()))[None,None];target=torch.sigmoid(sdf*60);cx=torch.tensor(.08,device='cuda',requires_grad=True);rad=torch.tensor(.46,device='cuda',requires_grad=True);pred=torch.sigmoid((rad-torch.sqrt((xx-cx).square()+yy.square()))*60)[None,None];local=local_boundary_error(pred,target,sdf,torch.tensor([True],device='cuda'),12);gc,gr=torch.autograd.grad(local,(cx,rad));assert float(gc)>0 and float(gr)>0
 result=dict(passed=True,stage=a.stage,model=mc['model_name'],parameter_count=sum(q.numel() for q in model.parameters()),data_manifest_sha256=lock['manifest_sha256'],overlay_parents=lock['overlay_entries'],matched_counts=complete['matched_counts'],matched_pitch_range=complete['matched_pitch_range'],matched_radius_range=complete['matched_radius_range'],operator_is_mean=True,total_output_dependency_radius_px=native_total,constant_error=constant_error,full_tiled_max_error=parity,initial_loss=float(loss),initial_terms={k:float(v) for k,v in terms.items()},gradient_norm=gradient_norm,local_center_gradient=float(gc),local_radius_gradient=float(gr),completed_utc=now())
 if a.stage=='final':
  runs=[]
  for design in ('global','local35'):
   for seed in SEEDS:
    mode='global' if design=='global' else 'local';run=ROOT/'runs'/f'short_{design}_{seed}';done=load(run/'short_complete.json');assert done['updates']==512 and done['loss_mode']==mode and done['dev_final']<done['dev_initial'];checks=learned_checks(done['checkpoint']['path'],mode,bank,cfg);runs.append(dict(design=design,loss_mode=mode,seed=seed,dev_initial=done['dev_initial'],dev_final=done['dev_final'],**checks,checkpoint_sha256=done['checkpoint']['sha256']))
  def mean(design,key):return float(np.mean([r[key] for r in runs if r['design']==design]))
  result['short_runs']=runs;result['global_matched_local_boundary']=mean('global','matched_local_boundary');result['local_matched_local_boundary']=mean('local35','matched_local_boundary');result['local_boundary_change_percent']=100*(result['local_matched_local_boundary']/result['global_matched_local_boundary']-1);result['global_matched_image']=mean('global','matched_image');result['local_matched_image']=mean('local35','matched_image');result['local_image_change_percent']=100*(result['local_matched_image']/result['global_matched_image']-1);result['passed']=result['passed'] and result['local_matched_local_boundary']<=result['global_matched_local_boundary']*.97 and result['local_matched_image']<=result['global_matched_image']*1.05 and max(r['center_error_px'] for r in runs if r['design']=='local35')<.001
  if not result['passed']:save(ROOT/'results/preflight_failed.json',result);print('PREFLIGHT_FAIL',result,flush=True);raise AssertionError('R149 matched-control gate failed')
 save(ROOT/('results/preflight_initial.json' if a.stage=='initial' else 'results/preflight.json'),result);print('PREFLIGHT_PASS',a.stage,result,flush=True)
if __name__=='__main__':main()

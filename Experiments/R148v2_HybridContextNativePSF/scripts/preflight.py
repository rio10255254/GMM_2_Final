"""Architecture, geometry, shift and matched-control gates for R148v2."""
from pathlib import Path
import argparse,sys
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from losses import objective,boundary_coordinates
from model import Model
from utils import load,save,sha,now,setup,model_config,train_config,verify_bank_lock
SEEDS=(1482201,1482202)
def edge_center(x):
 p=torch.cat((x[...,1:2].flip(-1),x,x[...,-2:-1].flip(-1)),-1);p=torch.cat((p[...,1:2,:].flip(-2),p,p[...,-2:-1,:].flip(-2)),-2);gx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;gy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5;w=gx.abs()+gy.abs();h,ww=x.shape[-2:];yy=torch.arange(h,device=x.device)[None,None,:,None];xx=torch.arange(ww,device=x.device)[None,None,None,:];m=w.sum((-2,-1))+1e-8;return torch.stack(((w*xx).sum((-2,-1))/m,(w*yy).sum((-2,-1))/m),-1)[:,0]
def learned_checks(path,context_mode):
 cfg=model_config();cp=torch.load(path,map_location='cpu',weights_only=False);m=Model(cfg,ROOT).cuda().eval();m.load_state_dict(cp['model']);m.context_enabled=context_mode=='hybrid';yy,xx=torch.meshgrid(torch.arange(384,device='cuda'),torch.arange(384,device='cuda'),indexing='ij');clean=torch.sigmoid((30-torch.sqrt((xx-192.)**2+(yy-192.)**2))*2)[None,None];source=m.optics.blur(clean);shift=torch.roll(source,1,-1)
 with torch.inference_mode():a=m(source);b=m(shift);c0=edge_center(a[...,128:256,128:256]);c1=edge_center(b[...,128:256,128:256]);center_error=float(torch.linalg.vector_norm((c1-c0)-torch.tensor([1.,0.],device='cuda')));comm=float((b[...,128:256,129:256]-a[...,128:256,128:255]).square().mean().sqrt()*255)
 return dict(center_error_px=center_error,commutator_RMS_gray=comm)
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=('initial','final'),required=True);a=p.parse_args();tc=train_config();mc=model_config();setup(tc['model_seed']);verify_bank_lock();assert sha(ROOT/'data/payload/manifest.json')==load(ROOT/'data/PAYLOAD_LOCK.json')['manifest_sha256'];geo=load(ROOT/'results/geometry_complete.json');assert geo['parents']==768 and geo['max_native_4x_mismatch']<.04
 model=Model(mc,ROOT).cuda().eval();native_total=max(50+mc['native_stages']*model.stages[0].dependency_radius,model.context.dependency_radius+mc['native_stages']*model.stages[0].dependency_radius);margin=(384-96)//2;observation_dependency=native_total+50;observation_margin=(384-64)//2;assert native_total<=margin and observation_dependency<=observation_margin
 flat=torch.full((3,1,384,384),.4,device='cuda');err=float((model.optics.blur(flat,torch.tensor([-2,-1,5],device='cuda'))-flat).abs().max());assert err<2e-6
 # Initial full/tiled parity and all loss gradients.
 x=torch.rand((1,1,640,640),device='cuda')*.7+.15
 with torch.inference_mode():full=model(x);tiled=model.forward_tiled(x)
 parity=float((full-tiled).abs().max());assert parity<3e-6
 bank=Bank(tc);b=bank.batch('dev',0,'cuda');model.train();_,states=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(states,b,model,tc);model.zero_grad(set_to_none=True);loss.backward();gn=float(torch.sqrt(sum(p.grad.square().sum() for p in model.parameters() if p.grad is not None)));assert gn>0
 # Boundary coordinate loss moves a shifted and oversized soft disk back.
 axis=torch.linspace(-1,1,96,device='cuda');yy,xx=torch.meshgrid(axis,axis,indexing='ij');sdf=(.38-torch.sqrt(xx.square()+yy.square()))[None,None];target=torch.sigmoid(sdf*60);cx=torch.tensor(.08,device='cuda',requires_grad=True);rad=torch.tensor(.46,device='cuda',requires_grad=True);pred=torch.sigmoid((rad-torch.sqrt((xx-cx).square()+yy.square()))*60);pred=pred[None,None];valid=torch.tensor([True],device='cuda');ps,pr=boundary_coordinates(pred,sdf,valid);ts,tr=boundary_coordinates(target,sdf,valid);bl=(ps-ts).abs()+.5*(pr-tr).abs();gc,gr=torch.autograd.grad(bl.mean(),(cx,rad));assert float(gc)>0 and float(gr)>0
 result=dict(passed=True,stage=a.stage,model=mc['model_name'],parameter_count=sum(p.numel() for p in model.parameters()),context_radius_px=model.context.dependency_radius,native_stage_radius_px=model.stages[0].dependency_radius,total_output_dependency_radius_px=native_total,training_margin_px=margin,observation_dependency_radius_px=observation_dependency,observation_margin_px=observation_margin,geometry_mean_native4x_mismatch=geo['mean_native_4x_mismatch'],geometry_max_native4x_mismatch=geo['max_native_4x_mismatch'],constant_error=err,full_tiled_max_error=parity,initial_loss=float(loss),initial_terms={k:float(v) for k,v in terms.items()},gradient_norm=gn,boundary_center_gradient=float(gc),boundary_radius_gradient=float(gr),completed_utc=now())
 if a.stage=='final':
  runs=[]
  for mode in ('native_only','hybrid'):
   for seed in SEEDS:
    root=ROOT/'runs'/f'short_{mode}_{seed}';done=load(root/'short_complete.json');assert done['updates']==512 and done['context_mode']==mode and done['seed']==seed and done['dev_final']<done['dev_initial'];checks=learned_checks(done['checkpoint']['path'],mode);runs.append(dict(mode=mode,seed=seed,dev_initial=done['dev_initial'],dev_final=done['dev_final'],**checks,checkpoint_sha256=done['checkpoint']['sha256']))
  native=np.mean([r['dev_final'] for r in runs if r['mode']=='native_only']);hybrid=np.mean([r['dev_final'] for r in runs if r['mode']=='hybrid']);result['short_runs']=runs;result['native_mean_dev_final']=float(native);result['hybrid_mean_dev_final']=float(hybrid);result['hybrid_vs_native_percent']=float((hybrid/native-1)*100);result['passed']=result['passed'] and hybrid<=native*1.05 and max(r['center_error_px'] for r in runs if r['mode']=='hybrid')<.001;assert result['passed']
 save(ROOT/('results/preflight_initial.json' if a.stage=='initial' else 'results/preflight.json'),result);print('PREFLIGHT_PASS',a.stage,result,flush=True)
if __name__=='__main__':main()

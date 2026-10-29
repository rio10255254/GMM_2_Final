"""Synthetic-only preflight, independent scratch sanity; no historical weights."""
import time,copy,ast,json
import numpy as np,torch
from utils import ROOT,config,setup,save,load,sha,state_digest,now,scratch_declaration
from model_r130_clean import Model,reflect_pad
from dataset_r130_clean import Bank
from losses_r130_clean import objective
from infer_r130_clean import predict_tensor
from train_r130_clean import create,update,learning_rate

def main():
 cfg=config();setup(cfg['model_seed']);model,opt=create(cfg);initial=state_digest(model);bank=Bank(cfg);checks={}
 checks['clean_flags']=cfg['checkpoint'] is None and not cfg['resume'] and not cfg['pretrained'] and cfg['teacher'] is None and cfg['model']['optical_mode']=='off'
 assert checks['clean_flags'];assert model.required_halo==96
 # Verify no hidden stateful normalization or optical parameters exist.
 banned=(torch.nn.BatchNorm2d,torch.nn.GroupNorm,torch.nn.LayerNorm,torch.nn.AdaptiveAvgPool2d)
 checks['no_global_modules']=not any(isinstance(m,banned) for m in model.modules())
 checks['no_optical_parameters']=not any(any(k in n.lower() for k in ['psf','optics','kernel','gate']) for n,_ in model.named_parameters())
 for mode in ['feature_single','feature_field']:
  c=dict(cfg['model'],optical_mode=mode)
  try:Model(c)
  except NotImplementedError:pass
  else:raise AssertionError('Optics unexpectedly enabled')
 for i in [0,1,2]:
  x=torch.full((1,1,17,23),i/2,device='cuda')
  with torch.no_grad():y=model(x)
  assert torch.equal(x,y)
 b=bank.batch('train',0,'cuda',0)
 with torch.no_grad():y=model(b['source'])
 assert torch.equal(y,b['source']);checks['scratch_identity_exact']=True
 # Spatial sizes stay native, including feature maps and residual states.
 sizes=[];handle=model.backbone.stem.register_forward_pre_hook(lambda m,a:sizes.append(list(a[0].shape)))
 out,states=model(b['source'],trace=True);handle.remove()
 assert all(s==[2,7,320,320] for s in sizes) and len(states)==4 and out.shape==b['source'].shape
 checks['native_feature_and_state_shapes']=True
 torch.cuda.reset_peak_memory_stats();tick=time.perf_counter()
 row=update(model,opt,b,learning_rate(1,cfg),cfg);assert all(torch.isfinite(p).all() for p in model.parameters())
 assert state_digest(model)!=initial;checks['GPU_forward_backward_update']=True
 one_batch_seconds=time.perf_counter()-tick;peak=torch.cuda.max_memory_allocated()
 # A deliberately non-neutral synthetic probe tests actual receptive-field safety.
 probe=Model(cfg['model']).cuda().eval()
 with torch.no_grad():torch.nn.init.normal_(probe.backbone.head.weight,0,.002)
 x=torch.rand((1,1,289,317),device='cuda')*.6+.2
 with torch.no_grad():
  full=predict_tensor(probe,x,'full');tiled=predict_tensor(probe,x,'tiled',128,96)
 tile_error=float((full-tiled).abs().max());assert tile_error<=cfg['preflight_tolerances']['full_tile_abs'];checks['full_tiled_parity_non_neutral']=True
 # Same central supervision from384context versus320crop, including all parameter gradients.
 arrays,meta,_=bank.read('train',0);rng=np.random.default_rng(np.random.SeedSequence([cfg['noise_seed'],0,0]));raw=np.rint(np.clip(arrays['noiseless'].astype(float)+rng.normal(0,meta['noise_sigma_gray']/255,arrays['source'].shape),0,1)*255).astype('uint8')
 xf=torch.from_numpy(raw[:,None].astype('float32')/255).cuda();tf=torch.from_numpy(arrays['target'][:,None]).cuda()
 bf=dict(b,source=xf,target=tf,core=(128,256))
 probe.train();probe.zero_grad(set_to_none=True);pf=probe(xf);lf,_=objective(pf,bf);lf.backward();gf={n:p.grad.detach().clone() for n,p in probe.named_parameters()}
 probe.zero_grad(set_to_none=True);pc=probe(b['source']);lc,_=objective(pc,b);lc.backward()
 output_error=float((pf[...,128:256,128:256]-pc[...,96:224,96:224]).abs().max())
 grad_error=max(float((p.grad-gf[n]).norm()/(gf[n].norm()+1e-7)) for n,p in probe.named_parameters())
 assert output_error<=cfg['preflight_tolerances']['context_output_abs'];assert grad_error<=cfg['preflight_tolerances']['context_gradient_relative'];checks['real_context_output_and_gradient']=True
 del probe,pf,pc,gf;torch.cuda.empty_cache()
 # Fresh sanity run. Its learned parameters are never used by the formal run.
 model,opt=create(cfg);assert state_digest(model)==initial;sanity=[];start=time.perf_counter()
 for step,index in enumerate(bank.order(0)[:cfg['sanity_updates']],1):
  b=bank.batch('train',int(index),'cuda',0);r=update(model,opt,b,learning_rate(step,cfg),cfg);r['step']=step;sanity.append(r)
 with torch.no_grad():z=model(b['source']);assert torch.isfinite(z).all() and z.min()>=0 and z.max()<=1;assert (z-b['source']).abs().max()<=cfg['model']['r_max']+1e-7
 checks['32_update_sanity_finite_and_bounded']=True
 for p in bank.files_opened:assert str(ROOT/'data') in p and 'PSF' not in p
 checks['dataset_read_whitelist']=True
 save(ROOT/'results/sanity_updates.json',dict(updates=sanity,initial_parameter_sha256=initial,final_parameter_sha256=state_digest(model),discarded_before_formal=True,seconds=time.perf_counter()-start))
 result=dict(all_required_checks_passed=all(checks.values()),checks=checks,**scratch_declaration(),scratch_initial_parameter_sha256=initial,parameter_count=sum(p.numel() for p in model.parameters()),dependency_radius=82,inference_halo=96,full_tiled_max_abs_error=tile_error,full_context_crop_max_abs_error=output_error,full_context_gradient_relative_error=grad_error,one_batch_seconds=one_batch_seconds,one_batch_peak_allocated_bytes=peak,sanity_updates=32,sanity_seconds=time.perf_counter()-start,real_images_read=0,completed_utc=now())
 save(ROOT/'results/preflight.json',result);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

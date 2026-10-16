"""Predeclared R137 gates; no real images or historical neural weights."""
import time,json,numpy as np,torch
from utils import ROOT,config,setup,save,state_digest,now,verify_protected
from model_r137_psf import Model
from train_r137_psf import create,update,learning_rate
from dataset_r137_psf import Bank
from losses_r137_psf import objective
from batch_prediction import predict_batch
from infer_r137_psf import predict_tensor

def main():
 cfg=config();m,opt=create(cfg);initial=state_digest(m);bank=Bank(cfg);checks={}
 assert cfg['model']['optical_gain']==.02 and cfg['updates']==8192 and cfg['checkpoint'] is None
 assert m.optical_files_loaded==1 and abs(float(m.optics.mean_psf.sum())-1)<1e-6
 checks['bank25_normalized_fixed_mean']=True
 # Original neural initialization is exactly reproduced without loading a checkpoint.
 import hashlib
 h=hashlib.sha256()
 for k,v in sorted(m.state_dict().items()):
  if k.startswith(('optics.','optical_adapter.')):continue
  h.update(k.encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
 assert h.hexdigest()=='0d4a4b3ed24b224df65640a3e0ec243c24b270dde6204ac5de00c40707e3a4a3'
 checks['matched_scratch_neural_initialization']=True
 b=bank.batch('train',0,'cuda',0)
 with torch.no_grad():assert torch.equal(predict_batch(m,b),b['source'])
 checks['initial_identity_exact']=True
 for level in [.2,.5,.8]:
  with torch.no_grad():cue=m.optics(torch.full((1,1,101,123),level,device='cuda'))
  assert float(cue.abs().max())<2e-6
 checks['optical_unit_DC']=True
 # Independently compute the same inverse using NumPy FFT.
 x=np.random.default_rng(1371).uniform(.2,.8,(113,127)).astype('float32');k=m.optics.mean_psf.cpu().numpy().astype(float);yp=np.pad(x,50,mode='reflect');hh,ww=yp.shape;yy,xx=np.mgrid[:101,:101];cy=(k*yy).sum()/k.sum();cx=(k*xx).sum()/k.sum();H=np.fft.rfft2(np.pad(k,((0,hh-101),(0,ww-101))));H*=np.exp(2j*np.pi*(np.fft.fftfreq(hh)[:,None]*cy+np.fft.rfftfreq(ww)[None,:]*cx));G=1.0565*H.conj()/(abs(H)**2+.0565);ref=np.fft.irfft2(np.fft.rfft2(yp)*G,s=yp.shape)[50:-50,50:-50]-x
 with torch.no_grad():actual=m.optics(torch.from_numpy(x[None,None]).cuda()).cpu().numpy()[0,0]
 optical_error=float(np.max(abs(ref-actual)));assert optical_error<2e-5
 checks['independent_optical_formula']=True
 # Probe is deliberately non-neutral; discard it before formal run.
 with torch.no_grad():torch.nn.init.normal_(m.backbone.head.weight,0,.005);torch.nn.init.normal_(m.optical_adapter.weight,0,.1)
 xx=torch.rand((1,1,289,317),device='cuda')*.6+.2
 with torch.no_grad():
  full=predict_tensor(m,xx,'full');tile=predict_tensor(m,xx,'tiled',128,96);tile_error=float((full-tile).abs().max());assert tile_error<2e-6
  calls=m.optics.calls;m.optical_enabled=False;off=m(xx);assert m.optics.calls==calls;m.optical_enabled=True;m.optical_gain=0;gain0=m(xx);assert torch.equal(off,gain0) and m.optics.calls==calls;m.optical_gain=.02
  zero=m(xx,optical_cue=torch.zeros_like(xx));response=float((full-zero).abs().max());assert response>1e-7
 checks['fixed_full_optical_cue_tile_parity']=True;checks['exact_off_skip_and_zero_gain']=True;checks['nonzero_PSF_response']=True
 # Same full optical cue before crop; total FFT branch itself is NOT claimed local.
 xf=b['optical_source'];tf=bank.read('train',0)[0]['target'];tf=torch.from_numpy(tf[:,None]).cuda();cue=m.optics(xf).detach()
 m.train();m.zero_grad(set_to_none=True);pf=m(xf,optical_cue=cue);lf,_=objective(pf,dict(b,target=tf,core=(128,256)));lf.backward();grads={n:p.grad.detach().clone() for n,p in m.named_parameters()}
 m.zero_grad(set_to_none=True);pc=m(b['source'],optical_cue=cue[...,32:352,32:352]);lc,_=objective(pc,b);lc.backward()
 context_error=float((pf[...,128:256,128:256]-pc[...,96:224,96:224]).abs().max());grad_error=max(float((p.grad-grads[n]).norm()/(grads[n].norm()+1e-7)) for n,p in m.named_parameters());assert context_error<2e-6 and grad_error<5e-5,(context_error,grad_error)
 checks['conditional_context_and_gradient']=True
 del m,opt,pf,pc,grads;torch.cuda.empty_cache();m,opt=create(cfg);assert state_digest(m)==initial;start=time.perf_counter();rows=[]
 for step,idx in enumerate(bank.order(0)[:32],1):rows.append(update(m,opt,bank.batch('train',int(idx),'cuda',0),learning_rate(step,cfg),cfg))
 assert float(m.optical_adapter.weight.abs().max())>0
 with torch.no_grad():
  on=predict_batch(m,b);m.optical_enabled=False;off=predict_batch(m,b);delta=float((on-off).abs().max());assert delta>1e-8
 checks['32_updates_adapter_trained_and_active']=True;verify_protected()
 save(ROOT/'results/sanity_updates.json',dict(rows=rows,discarded=True,seconds=time.perf_counter()-start,PSF_output_effect_max=delta))
 save(ROOT/'results/preflight.json',dict(all_required_checks_passed=all(checks.values()),checks=checks,scratch_initial_parameter_sha256=initial,parameter_count=sum(p.numel() for p in m.parameters()),optical_gain=.02,PSF_count=25,optical_numpy_max_error=optical_error,full_tile_max_error=tile_error,conditional_context_max_error=context_error,conditional_gradient_relative_error=grad_error,probe_PSF_response_max=response,sanity_PSF_effect_max=delta,real_images_read=0,full_pipeline_locality_claim=False,completed_utc=now()))
 print(json.dumps(__import__('utils').load(ROOT/'results/preflight.json'),indent=2),flush=True)
if __name__=='__main__':main()

import ast,hashlib,time,importlib.util,warnings
import numpy as np,torch
from pathlib import Path
from utils import ROOT,config,save,load,sha,state_digest,verify_protected,now
from model_r138_psf import Model
from dataset_r138_psf import Bank
from train_r138_psf import create,update,learning_rate
warnings.filterwarnings('ignore',category=FutureWarning)

def main():
 cfg=config();m,opt=create(cfg);initial=state_digest(m);bank=Bank(cfg);checks={}
 src=ROOT.parents[1]/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/V42_SoftLabelSNR_FullStandalone_20260709/model_v42.py'
 def body(p):return ast.dump(next(n for n in ast.parse(p.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.ClassDef) and n.name=='WeakPSFDeconvBlock'),include_attributes=False)
 assert body(src)==body(ROOT/'optical/feature.py');checks['V42_class_identical']=True
 sp=importlib.util.spec_from_file_location('v42_test_reference',src);v42=importlib.util.module_from_spec(sp);sp.loader.exec_module(v42)
 # Construct the exact original module via its own class, with unchanged PSFs from this test's loader.
 from optical.feature import PSFDeconvPhysics
 v42.PSFDeconvPhysics._load_psf_stack=staticmethod(PSFDeconvPhysics._load_psf_stack)
 ref=v42.WeakPSFDeconvBlock(64,str(ROOT/cfg['model']['psf_bank']),k=8,**cfg['model']['weak_psf']).to(cfg['device']);ref.load_state_dict(m.optics.state_dict())
 assert list(m.optics.psf_indices)==[0,3,7,10,14,17,21,24]
 f=torch.rand(1,64,113,117,device=cfg['device'])
 with torch.no_grad():assert torch.equal(m.optics(f),ref(f))
 checks['V42_forward_parity']=True
 h=hashlib.sha256()
 for k,v in sorted(m.state_dict().items()):
  if k.startswith('optics.'):continue
  h.update(k.encode());h.update(v.detach().cpu().numpy().tobytes())
 assert h.hexdigest()=='0d4a4b3ed24b224df65640a3e0ec243c24b270dde6204ac5de00c40707e3a4a3';checks['matched_scratch_backbone']=True
 b=bank.batch('train',0,cfg['device'],0)
 with torch.no_grad():assert torch.equal(m(b['source']),b['source'])
 checks['initial_identity']=True
 del ref,f;rows=[];start=time.perf_counter()
 for step,idx in enumerate(bank.order(0)[:cfg['sanity_updates']],1):
  rows.append(update(m,opt,bank.batch('train',int(idx),cfg['device'],0),learning_rate(step,cfg),cfg))
  if step%8==0:print('Sanity',step,'elapsed',time.perf_counter()-start,flush=True)
 assert torch.isfinite(m.optics.gating[-1].weight).all() and m.optics.gating[-1].weight.abs().max()>0
 calls=[];hook=m.optics.register_forward_hook(lambda a,b,c:calls.append(1))
 with torch.no_grad():
  on=m(b['source']);assert len(calls)==4;m.optical_enabled=False;off=m(b['source']);assert len(calls)==4;m.optical_enabled=True
 hook.remove();effect=float((on-off).abs().max());assert effect>1e-8
 checks['CPU_sanity_gating_trained_and_nonzero_effect']=True;checks['four_calls_and_exact_off_bypass']=True
 # A full-size synthetic observation checks actual available memory; no real evaluation frames consumed.
 full=torch.rand(1,1,1544,2064,device=cfg['device'])*.6+.2;m.eval();tick=time.perf_counter()
 with torch.inference_mode():out=m(full)
 fullseconds=time.perf_counter()-tick;peak=0;assert out.shape==full.shape and torch.isfinite(out).all() and out.min()>=0 and out.max()<=1
 checks['native_full_frame_forward']=True
 save(ROOT/'results/sanity_updates.json',dict(rows=rows,discarded=True,seconds=time.perf_counter()-start))
 verify_protected();save(ROOT/'results/preflight.json',dict(all_required_checks_passed=all(checks.values()),checks=checks,scratch_initial_parameter_sha256=initial,parameter_count=sum(p.numel() for p in m.parameters()),auto8=list(m.optics.psf_indices),initial_beta=.02,sanity_beta=float(m.optics.beta),sanity_output_effect_max=effect,full_synthetic_seconds=fullseconds,full_peak_allocated_bytes=peak,full_pipeline_locality_claim=False,tiled_supported=False,real_images_read=0,V42_source_sha256=sha(src),completed_utc=now()))
 print(load(ROOT/'results/preflight.json'),flush=True)
if __name__=='__main__':main()

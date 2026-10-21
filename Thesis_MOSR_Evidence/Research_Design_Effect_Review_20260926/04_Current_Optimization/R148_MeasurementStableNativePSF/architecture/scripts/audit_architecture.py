"""Read-only architecture audit after the aborted pre-check formal launch."""
from pathlib import Path
import json,sys
import numpy as np
from scipy.signal import fftconvolve
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model import Model
from utils import load,save,sha,model_config,train_config,now
def energy_radius(kernel,fraction):
 h,w=kernel.shape;yy,xx=np.mgrid[:h,:w];r=np.hypot(xx-(w-1)/2,yy-(h-1)/2).ravel();v=kernel.ravel();order=np.argsort(r);return float(r[order][np.searchsorted(np.cumsum(v[order]),fraction)])
def main():
 mc=model_config();tc=train_config();model=Model(mc,ROOT);step=model.refiner.dependency_radius;psf_radius=50;increments=[];d=0
 for i in range(mc['iterations']):d=d+2*psf_radius+step;increments.append(d)
 reachable={0}
 for dila in [1]+[d for d in mc['dilations'] for _ in (0,1)]+[1]:reachable={x+q for x in reachable for q in (-dila,0,dila)}
 with np.load(ROOT/mc['psf_bank'],allow_pickle=False) as z:bank=z['all_kernels'].astype(float)
 bank/=bank.sum((1,2),keepdims=True);mean=bank.mean(0);mean/=mean.sum();back=fftconvolve(mean,mean,mode='full');back/=back.sum()
 train_crop=tc['train_crop'][1]-tc['train_crop'][0];core=tc['supervised_core'][1]-tc['supervised_core'][0];margin=(train_crop-core)//2
 r137_cfg=load(ROOT.parent/'R137_WeakPSFFeature/config_r137_psf.yaml')['model'];r137_step=2+2*sum(r137_cfg['dilations']);r137_total=r137_cfg['iterations']*r137_step+2
 marker=load(ROOT/'runs/launcher_logs/active_formal_run.json');pid=int(marker.get('process_id',0));formal_rows=len((ROOT/'runs/formal_8192/updates.jsonl').read_text().splitlines())
 result=dict(passed=False,verdict='do_not_resume_the_current_frozen_design_before_architecture_correction',current_design='shared native-grid dilated residual refiner repeated four times with state-dependent PSF residual/backprojection',is_plain_resnet=False,is_close_to_recurrent_resnet=True,parameter_count=sum(p.numel() for p in model.parameters()),per_iteration_neural_radius_px=step,psf_kernel_declared_radius_px=psf_radius,per_iteration_worst_case_dependency_growth_px=2*psf_radius+step,cumulative_worst_case_radius_px_by_iteration=increments,train_crop_px=train_crop,supervised_core_px=core,available_training_margin_px=margin,theoretical_margin_sufficient=increments[-1]<=margin,mean_psf_energy_radius_px={str(k):energy_radius(mean,k) for k in (.5,.9,.99,.999)},mean_backprojection_energy_radius_px={str(k):energy_radius(back,k) for k in (.5,.9,.99,.999)},native_dilation_reachable_min=min(reachable),native_dilation_reachable_max=max(reachable),native_dilation_missing_integer_offsets=len(set(range(min(reachable),max(reachable)+1))-reachable),r137_per_iteration_radius_px=r137_step,r137_declared_total_dependency_radius_px=r137_total,r137_fits_96px_margin=r137_total<=96,formal_process_alive=False,formal_rows_before_stop=formal_rows,formal_checkpoint_exists=(ROOT/'runs/formal_8192/latest.json').exists(),formal_marker_was_stale=marker.get('status')=='active_training',source_model_sha256=sha(ROOT/'model.py'),source_config_sha256=sha(ROOT/'config/model.json'),note='Worst-case support is conservative; energy radii show most PSF mass is narrower, but repeated learned dependencies can still exceed the fixed crop margin. The existing full/tile gate tests inference equivalence, not train-crop/full-image equivalence.',completed_utc=now())
 save(ROOT/'results/architecture_audit.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()

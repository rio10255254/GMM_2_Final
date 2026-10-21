"""Recompute summaries from diagnostic measurements; plots use complete cases."""
from pathlib import Path
import sys
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import load,save,sha
def main():
 out=ROOT/'results/internal_audit';d=pd.read_csv(out/'trace_circles.csv');plan=load(ROOT/'evaluation/capture_plan.json');u=np.array(load(ROOT/'evaluation/calibration.json')['axis_unit_vector']);steps=[];summ=[]
 for (mode,it),g in d.groupby(['mode','iteration']):
  if mode.startswith('local_'):continue
  groups=list(g.groupby('run'))
  for run,x in groups:
   xyz={i:y.sort_values('pillar')[['cx','cy','radius']].to_numpy() for i,y in x.groupby('index')};fn={i:int(y.frame.iloc[0]) for i,y in x.groupby('index')}
   for i,j,kind in [(0,1,'adjacent'),(15,16,'adjacent'),(0,30,'start')]:
    delta=np.median(xyz[j][:,:2]-xyz[i][:,:2],axis=0);truth=plan['frames'][fn[j]]['pi_y_um']-plan['frames'][fn[i]]['pi_y_um'];err=np.dot(delta,u)*172.5-truth*1000
    steps.append(dict(mode=mode,iteration=int(it),run=run,kind=kind,i=i,j=j,error_nm=err))
  size=np.stack([x.sort_values(['index','pillar']).radius.to_numpy().reshape(5,9)*345 for _,x in groups]);ss=pd.DataFrame(steps);sg=ss[(ss['mode']==mode)&(ss.iteration==it)]
  adj=sg[sg.kind=='adjacent'];start=sg[sg.kind=='start']
  summ.append(dict(mode=mode,iteration=int(it),short_MAE_nm=adj.error_nm.abs().mean(),short_SD_by_position_nm=adj.groupby('j').error_nm.std(ddof=1).mean(),start_MAE_nm=start.error_nm.abs().mean(),diameter_mean_nm=size.mean(),diameter_repeat_SD_nm=np.sqrt(size.var(0,ddof=1).mean()),scans=len(groups),short_pairs=len(adj)))
 pd.DataFrame(steps).to_csv(out/'stage_displacements.csv',index=False);summary=pd.DataFrame(summ);summary.to_csv(out/'stage_summary.csv',index=False)
 upd=pd.read_csv(out/'trace_updates.csv');upd.groupby('iteration').mean(numeric_only=True).to_csv(out/'update_summary.csv')
 crop=[];shift=[]
 for model in ('r147','r146','r140'):
  for kind,acc in [('crops',crop),('shifts',shift)]:
   path=out/f'{kind}_{model}.csv'
   if not path.exists():continue
   x=pd.read_csv(path)
   if kind=='crops':group=['model','size','origin_phase_x'];keys=['center_error_nm','diameter_change_nm','image_RMS_gray','image_max_gray']
   else:group=['model','method','dx','dy'];keys=['center_error_nm','raw_center_error_nm','diameter_change_nm','raw_diameter_change_nm','commutator_RMS_gray','commutator_max_gray']
   for key,g in x.groupby(group):
    row=dict(zip(group,key));row.update({k:float(g[k].mean()) for k in keys});row['max_center_error_nm']=float(g.center_error_nm.max());row['n']=len(g);acc.append(row)
 if crop:pd.DataFrame(crop).to_csv(out/'crop_summary.csv',index=False)
 if shift:pd.DataFrame(shift).to_csv(out/'shift_summary.csv',index=False)
 nuisance=[]
 for model in ('r147','r146','r140'):
  path=out/f'nuisance_{model}.csv'
  if not path.exists():continue
  x=pd.read_csv(path)
  for label,g in x.groupby('condition'):
   nuisance.append(dict(model=model,condition=label,center_change_nm=float(g.center_change_nm.mean()),max_center_change_nm=float(g.center_change_nm.max()),raw_center_change_nm=float(g.raw_center_change_nm.mean()),diameter_change_nm=float(g.diameter_change_nm.mean()),max_absolute_diameter_change_nm=float(g.diameter_change_nm.abs().max()),raw_diameter_change_nm=float(g.raw_diameter_change_nm.mean()),n=len(g)))
 if nuisance:pd.DataFrame(nuisance).to_csv(out/'nuisance_summary.csv',index=False)
 # Separate physical addition from learned optical-feature response on the same trajectory.
 full=d[d['mode']=='full'];local=[]
 for label in ('local_neural','local_physical'):
  x=d[d['mode']==label].merge(full,on=['frame','iteration','pillar'],suffixes=('_local','_full'))
  if label=='local_neural':effect='adding_physical_at_fixed_neural_update'
  else:effect='adding_neural_at_fixed_physical_update'
  for it,g in x.groupby('iteration'):
   dc=np.c_[g.cx_full-g.cx_local,g.cy_full-g.cy_local]*172.5;dr=(g.radius_full-g.radius_local)*345
   local.append(dict(effect=effect,iteration=int(it),mean_center_change_nm=float(np.linalg.norm(dc,axis=1).mean()),mean_diameter_change_nm=float(dr.mean()),max_absolute_diameter_change_nm=float(np.abs(dr).max())))
 pd.DataFrame(local).to_csv(out/'local_geometry_effect.csv',index=False)
 # Loss-gradient contributions only apply to the sampled frozen-model training batches.
 gradient=pd.read_csv(out/'gradient_terms.csv') if (out/'gradient_terms.csv').exists() else None
 if gradient is not None:
  active=gradient[gradient.motion & (gradient.category!='clean_identity')]
  stats=dict(sampled_parents=len(gradient),motion_parents=len(active),median_weighted_pair_to_image_grad_norm=float(np.median(active.pair_weighted_grad_norm/(active.image_weighted_grad_norm+1e-30))),median_pair_to_image_loss=float(np.median(.2*active.pair/(active.image+1e-30))),mean_image_pair_grad_cosine=float(active.image_pair_gradient_cosine.mean()),negative_cosine_parents=int((active.image_pair_gradient_cosine<0).sum()))
  save(out/'gradient_summary.json',stats)
 figures=ROOT/'reports/figures';figures.mkdir(exist_ok=True)
 fig,axes=plt.subplots(1,3,figsize=(15,4));full=summary[summary['mode']=='full'].sort_values('iteration')
 axes[0].plot(full.iteration,full.short_MAE_nm,'o-');axes[0].set(xlabel='Internal iteration',ylabel='Short-step PI MAE (nm)',title='6 scans, 12 fixed short pairs')
 axes[1].plot(full.iteration,full.diameter_mean_nm,'o-',label='Mean diameter');axes[1].set(xlabel='Internal iteration',ylabel='Diameter (nm)',title='Diameter changes inside model')
 ups=upd.groupby('iteration').mean(numeric_only=True);axes[2].plot(ups.index,ups.observation_RMS_before,'o-',label='Before update');axes[2].plot(ups.index,ups.observation_RMS_after,'o-',label='After update');axes[2].set(xlabel='Internal iteration',ylabel='Reblurred residual (gray)',title='Data consistency');axes[2].legend()
 for ax in axes:ax.grid(alpha=.25)
 fig.tight_layout();fig.savefig(figures/'R147_internal_stages.png',dpi=170);plt.close(fig)
 if shift:
  s=pd.DataFrame(shift);fig,ax=plt.subplots(figsize=(7,4))
  for model,g in s[s.method=='integer'].groupby('model'):g=g.sort_values('dx');ax.plot(g.dx,g.commutator_RMS_gray,'o-',label=model)
  ax.set(xlabel='Known integer shift (pixels)',ylabel='Output shift inconsistency (gray)',title='Same image: translate before vs after model');ax.set_yscale('symlog',linthresh=1e-4);ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(figures/'R147_grid_sensitivity.png',dpi=170);plt.close(fig)
 if nuisance:
  n=pd.DataFrame(nuisance);conditions=['blur_0p5','contrast_0p8','contrast_1p2','brightness_plus10','noise_sigma1'];fig,ax=plt.subplots(figsize=(10,4));xx=np.arange(len(conditions))
  for j,model in enumerate(('r140','r146','r147')):
   g=n[n.model==model].set_index('condition').reindex(conditions)
   ax.bar(xx+(j-1)*.24,g.center_change_nm,width=.24,label=model)
  ax.set_xticks(xx,['Added blur 0.5 px','Contrast 0.8','Contrast 1.2','Intensity +10','Noise 1 gray']);ax.set(ylabel='Mean circle center change (nm)',title='Same-photo sensitivity: six fixed frames');ax.legend();ax.grid(axis='y',alpha=.25);fig.tight_layout();fig.savefig(figures/'R147_nuisance_response.png',dpi=170);plt.close(fig)
 print(summary.round(4).to_string(index=False));print('SUMMARIES_SAVED')
if __name__=='__main__':main()

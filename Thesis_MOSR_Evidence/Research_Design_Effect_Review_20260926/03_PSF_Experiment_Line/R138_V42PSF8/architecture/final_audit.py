from pathlib import Path
import json,time,ast
import numpy as np,pandas as pd,torch,cv2
from utils import ROOT,config,setup,load,save,sha,verify_frozen,verify_protected,now
from infer_r138_psf import load_own_model
from dataset_r138_psf import Bank
from losses_r138_psf import objective

def main():
 cfg=config();setup(cfg['model_seed']);t=load(ROOT/'runs/formal_8192/training_complete.json');assert t['unique_updates']==8192 and sha(t['final_checkpoint']['path'])==t['final_checkpoint']['sha256'];m,cp=load_own_model(t['final_checkpoint']['path']);plan=load(ROOT/'evaluation/capture_plan.json')
 assert cp['step']==8192 and all(torch.isfinite(p).all() for p in m.parameters());assert m.optics.gating[-1].weight.abs().max()>0
 assert all(int(v['step'])==8192 for v in cp['optimizer']['state'].values())
 logs=[json.loads(v) for v in (ROOT/'runs/formal_8192/updates.jsonl').read_text().splitlines()];old=[json.loads(v) for v in (ROOT.parent/'R137_WeakPSFFeature/runs/formal_8192/updates.jsonl').read_text().splitlines()];assert len(logs)==len(old)==8192
 for a,b in zip(logs,old):
  for key in ['step','epoch','position','parent_id','parent_sha256','input_sha256','noise_seed','learning_rate']:assert a[key]==b[key],(a['step'],key)
 runtime=pd.read_csv(ROOT/'results/reconstruction_runtime.csv');assert len(runtime)==930 and not runtime.duplicated(['run','index']).any();weights=[]
 for row in runtime.itertuples():
  assert row.checkpoint_sha256==t['final_checkpoint']['sha256'] and sha(row.output_path)==row.output_sha256
  history=np.array(ast.literal_eval(row.PSF_weights_per_iteration)).reshape(4,8);assert np.isfinite(history).all() and (history>=0).all() and np.allclose(history.sum(1),1,atol=1e-6)
  for iteration,w in enumerate(history,1):weights.append(dict(run=row.run,index=row.index,iteration=iteration,**{f'w{k}':float(v) for k,v in zip(m.optics.psf_indices,w)}))
 pd.DataFrame(weights).to_csv(ROOT/'results/PSF_all930_iteration_weights.csv',index=False)
 audit=[]
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 for idx in [0,30,899,929]:
  f=plan['frames'][idx];image=cv2.imread(f['source']['path'],0).astype('float32')/255;x=torch.from_numpy(image[None,None]).to(cfg['device'])
  with torch.inference_mode():
   on=m(x);m.optical_enabled=False;off=m(x);m.optical_enabled=True
   with np.load(ROOT/'results/reconstruction'/f['run']/f"{f['index']+1:02d}.npz") as z:ref=z['output']
   err=float(np.abs(on.cpu().numpy()[0,0]-ref).max());assert err<=2e-6
   delta=on-off;audit.append(dict(frame=idx,replay_max_error=err,on_off_rms_gray=float(delta.square().mean().sqrt()*255),on_off_max_gray=float(delta.abs().max()*255)))
   if idx==0:
    fig,axs=plt.subplots(1,4,figsize=(14,4),layout='constrained')
    with np.load(ROOT.parent/'R137_WeakPSFFeature/results/reconstruction'/f['run']/'01.npz') as z:oldimg=z['output']
    for ax,img,label in zip(axs,[image,oldimg,on.cpu().numpy()[0,0],off.cpu().numpy()[0,0]],['Raw','R137','R138 V42PSF8','R138 same weights PSF off']):ax.imshow(img[690:820,1555:1685],cmap='gray',vmin=0,vmax=1);ax.set_title(label);ax.axis('off')
    fig.savefig(ROOT/'reports/figures/real_example.png',dpi=180);plt.close(fig)
  del x,on,off,delta
 pd.DataFrame(audit).to_csv(ROOT/'results/PSF_activity_real_examples.csv',index=False)
 bank=Bank(cfg);gen=[]
 with torch.inference_mode():
  for i in range(32):
   b=bank.batch('test',i,cfg['device']);m.optical_enabled=True;on=m(b['source']);lo,_=objective(on,b);m.optical_enabled=False;off=m(b['source']);lf,_=objective(off,b);m.optical_enabled=True;gen.append(dict(index=i,on_loss=float(lo),off_loss=float(lf),rms_gray=float((on-off).square().mean().sqrt()*255)))
 pd.DataFrame(gen).to_csv(ROOT/'results/PSF_on_off_generated32.csv',index=False)
 # Independent displacement arithmetic from all five saved center tables.
 C=pd.read_csv(ROOT/'results/comparison/all_circles.csv');D=pd.read_csv(ROOT/'results/comparison/all_displacements.csv');assert len(C)==41850 and len(D)==9000;u=np.array(load(ROOT/'evaluation/calibration.json')['axis_unit_vector']);errors=[]
 for (name,run),g in C.groupby(['model','run']):
  xy=g.sort_values(['index','pillar_id'])[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2)
  for kind in ['adjacent','start']:
   d=D[(D.model==name)&(D.run==run)&(D.kind==kind)].sort_values('j');delta=xy[1:]-(xy[:-1] if kind=='adjacent' else xy[:1]);pred=(np.median(delta,axis=1)@u*.1725-d.pi_displacement_um.to_numpy())*1000;errors.extend(abs(pred-d.error_nm.to_numpy()))
 assert max(errors)<1e-8
 verify_frozen(load(ROOT/'config/source_lock.json'));verify_protected()
 result=dict(completed_utc=now(),updates=8192,matched_R137_inputs_order_lr=8192,output_hashes_verified=930,PSF_weight_records=len(weights),PSF_indices=list(m.optics.psf_indices),learned_beta=float(m.optics.beta),effective_beta=m.optics.last_beta,PSF_output_effect_max_gray=max(a['on_off_max_gray'] for a in audit),PSF_effect_observed=any(a['on_off_max_gray']>0 for a in audit),gating_weights_range=[float(pd.DataFrame(weights).filter(regex='^w').min().min()),float(pd.DataFrame(weights).filter(regex='^w').max().max())],independent_displacements=9000,displacement_max_difference_nm=max(errors),legacy_PSF_independent_SEM=False,original_sources_unchanged=True,scope='4real and32generated PSF toggle diagnostics, not full off930 or retrained ablation',speed_controlled=False)
 save(ROOT/'results/final_audit.json',result);print(result,flush=True)
if __name__=='__main__':main()

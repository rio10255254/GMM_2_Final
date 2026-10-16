"""Create a reproducible snapshot of R148v2 training dynamics and data coverage."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/training_deep_dive';OUT.mkdir(parents=True,exist_ok=True)
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
 cfg=load(ROOT/'config/train.json');manifest=load(ROOT/'data/payload/manifest.json');log_path=ROOT/'runs/formal_8192/updates.jsonl';raw=log_path.read_bytes();rows=[json.loads(x) for x in raw.splitlines()];df=pd.DataFrame(rows)
 if df.step.tolist()!=list(range(1,len(df)+1)):raise RuntimeError('Training steps are not contiguous')
 df['utc']=pd.to_datetime(df.utc);weights=cfg['loss'];contrib={'image':1.0,'gradient':weights['gradient'],'pair_output':weights['pair_output'],'boundary':weights['boundary'],'observation':weights['observation']}
 for name,w in contrib.items():df['weighted_'+name]=df[name]*w
 weighted_cols=['weighted_'+x for x in contrib];df['recomputed_loss']=df[weighted_cols].sum(1);max_loss_diff=float((df.recomputed_loss-df.loss).abs().max());assert max_loss_diff<5e-5
 df.to_csv(OUT/'updates_snapshot.csv',index=False)
 # Epoch and category patterns.
 epoch=df.groupby('epoch').agg(first_step=('step','min'),last_step=('step','max'),updates=('step','size'),loss_mean=('loss','mean'),loss_median=('loss','median'),loss_p90=('loss',lambda x:x.quantile(.9)),image=('image','mean'),gradient=('gradient','mean'),pair_output=('pair_output','mean'),boundary=('boundary','mean'),observation=('observation','mean'),learning_rate=('learning_rate','mean')).reset_index();epoch.to_csv(OUT/'epoch_summary.csv',index=False)
 recent=df.tail(min(512,len(df)));early=df.head(min(512,len(df)));periods=[]
 for period,g in [('early_first512',early),('recent_last512',recent),('all',df)]:
  means=g[weighted_cols].mean();den=float(means.sum())
  for c in weighted_cols:periods.append(dict(period=period,component=c.removeprefix('weighted_'),weighted_mean=float(means[c]),share_percent=float(100*means[c]/den)))
 pd.DataFrame(periods).to_csv(OUT/'weighted_loss_contributions.csv',index=False)
 cats=[]
 for period,g in [('early_first512',early),('recent_last512',recent)]:
  for category,x in g.groupby('category'):
   cats.append(dict(period=period,category=category,updates=len(x),loss_mean=float(x.loss.mean()),loss_median=float(x.loss.median()),loss_p90=float(x.loss.quantile(.9)),image_mean=float(x.image.mean()),gradient_mean=float(x.gradient.mean()),pair_mean=float(x.pair_output.mean()),boundary_mean=float(x.boundary.mean()),observation_mean=float(x.observation.mean())))
 catdf=pd.DataFrame(cats);catdf.to_csv(OUT/'training_category_summary.csv',index=False)
 # Dev curve and per-category dev distribution.
 dev_entries={e['index']:e['category'] for e in manifest['entries'] if e['split']=='dev'};dev_rows=[];dev_cat=[]
 files=[ROOT/'runs/formal_8192/dev_initial.json']+sorted(ROOT.glob('runs/formal_8192/dev_[0-9][0-9][0-9][0-9][0-9].json'))
 for path in files:
  if not path.exists():continue
  data=load(path);step=0 if path.name=='dev_initial.json' else int(path.stem.split('_')[1]);dev_rows.append(dict(step=step,name=path.name,mean_loss=float(data['mean_loss']),sha256=sha(path)))
  individual=data['individual_loss'];assert len(individual)==128
  t=pd.DataFrame({'index':range(128),'loss':individual});t['category']=t['index'].map(dev_entries)
  for category,g in t.groupby('category'):dev_cat.append(dict(step=step,category=category,count=len(g),loss_mean=float(g.loss.mean()),loss_median=float(g.loss.median()),loss_p90=float(g.loss.quantile(.9)),loss_max=float(g.loss.max())))
 dev=pd.DataFrame(dev_rows).sort_values('step');dev.to_csv(OUT/'dev_curve.csv',index=False);devcats=pd.DataFrame(dev_cat);devcats.to_csv(OUT/'dev_category_curve.csv',index=False)
 # Data formation coverage and actual known-operator sampling used so far.
 meta=[];parent_index={}
 for e in manifest['entries']:
  m=load(ROOT/'data/payload'/e['metadata']);parent_index[e['parent_id']]=(e['split'],e['index'],m)
  for v in m['views']:
   meta.append(dict(split=e['split'],index=e['index'],parent_id=e['parent_id'],category=e['category'],view=v['view'],shift_magnitude_px=float(np.hypot(*v['shift_xy'])),shift_x=v['shift_xy'][0],shift_y=v['shift_xy'][1],psf_index=v['psf_index'],noise_sigma_gray=v['noise_sigma_gray'],contrast=v['contrast'],requested_contrast=v.get('requested_contrast',v['contrast']),brightness_gray=v['brightness_gray'],requested_brightness_gray=v.get('requested_brightness_gray',v['brightness_gray'])))
 metadata=pd.DataFrame(meta);metadata.to_csv(OUT/'data_view_coverage.csv',index=False)
 known=[]
 for r in rows:
  split,index,m=parent_index[r['parent_id']];rng=np.random.default_rng(np.random.SeedSequence([cfg['operator_seed'],r['epoch'],index]));mask=rng.random(4)<cfg['known_operator_probability'];actual=np.array([-2 if v['psf_index']<0 else v['psf_index'] for v in m['views']]);known.append(dict(step=r['step'],category=r['category'],known_views=int(mask.sum()),known_nonidentity_views=int((mask&(actual>=0)).sum()),identity_views=int((actual==-2).sum())))
 known_df=pd.DataFrame(known);known_df.to_csv(OUT/'operator_sampling.csv',index=False)
 # Learned step strengths.
 eta=np.array(df.eta.tolist());eta_df=pd.DataFrame({'step':df.step})
 for i in range(eta.shape[1]):eta_df[f'eta_{i+1}']=eta[:,i]
 eta_df.to_csv(OUT/'eta_curve.csv',index=False)
 # Figures.
 fig,axes=plt.subplots(2,2,figsize=(13,8))
 axes[0,0].plot(dev.step,dev.mean_loss,'o-',color='#2474b5');axes[0,0].set(title='Held-out dev loss',xlabel='Training update',ylabel='Loss');axes[0,0].grid(alpha=.25)
 latest=devcats[devcats.step==dev.step.max()].sort_values('loss_mean');axes[0,1].barh(latest.category,latest.loss_mean,color='#e07a3f');axes[0,1].set(title=f'Dev loss by scene type @ {int(dev.step.max())}',xlabel='Mean loss')
 share=pd.DataFrame(periods);pivot=share.pivot(index='component',columns='period',values='share_percent').reindex(list(contrib));x=np.arange(len(pivot));w=.36;axes[1,0].bar(x-w/2,pivot.early_first512,w,label='First 512');axes[1,0].bar(x+w/2,pivot.recent_last512,w,label='Recent 512');axes[1,0].set_xticks(x,pivot.index,rotation=25,ha='right');axes[1,0].set(title='Weighted objective share',ylabel='% of weighted mean');axes[1,0].legend()
 for i in range(eta.shape[1]):axes[1,1].plot(eta_df.step,eta_df[f'eta_{i+1}'],label=f'Stage {i+1}')
 axes[1,1].set(title='Learned stage step strengths',xlabel='Training update',ylabel='Eta');axes[1,1].legend();axes[1,1].grid(alpha=.25);fig.tight_layout();fig.savefig(OUT/'training_dynamics.png',dpi=170);plt.close(fig)
 initial=float(dev.iloc[0].mean_loss);latest_loss=float(dev.iloc[-1].mean_loss);improvements=[]
 for a,b in zip(dev.itertuples(),dev.iloc[1:].itertuples()):improvements.append(dict(from_step=int(a.step),to_step=int(b.step),absolute_drop=float(a.mean_loss-b.mean_loss),relative_drop_percent=float(100*(a.mean_loss-b.mean_loss)/a.mean_loss)))
 imp=pd.DataFrame(improvements);imp.to_csv(OUT/'dev_interval_improvements.csv',index=False)
 recent_share=pd.DataFrame(periods);recent_share=recent_share[recent_share.period=='recent_last512'].set_index('component').share_percent.to_dict()
 latest_cat=devcats[devcats.step==dev.step.max()].set_index('category').loss_mean.to_dict();initial_cat=devcats[devcats.step==0].set_index('category').loss_mean.to_dict()
 complete_path=ROOT/'runs/formal_8192/training_complete.json';test_path=ROOT/'runs/formal_8192/test_final.json';complete=complete_path.exists();test=load(test_path) if test_path.exists() else None
 result=dict(snapshot_utc=datetime.now(timezone.utc).isoformat(),source_updates_path=str(log_path),source_updates_sha256=hashlib.sha256(raw).hexdigest(),rows=len(df),last_step=int(df.step.max()),latest_checkpoint=load(ROOT/'runs/formal_8192/latest.json'),resume_verified=load(ROOT/'runs/launcher_logs/RESUME_VERIFIED_05888.json'),steps_contiguous=True,max_loss_recompute_difference=max_loss_diff,dev_points=len(dev),dev_initial=initial,dev_latest_step=int(dev.iloc[-1].step),dev_latest=latest_loss,dev_total_improvement_percent=float(100*(initial-latest_loss)/initial),last_three_dev_absolute_drops=imp.absolute_drop.tail(3).tolist(),latest_dev_category_mean={k:float(v) for k,v in latest_cat.items()},initial_dev_category_mean={k:float(v) for k,v in initial_cat.items()},recent_weighted_objective_share_percent={k:float(v) for k,v in recent_share.items()},known_operator_view_rate=float(known_df.known_views.sum()/(4*len(known_df))),known_nonidentity_view_rate=float(known_df.known_nonidentity_views.sum()/(4*len(known_df))),data_counts=metadata.groupby(['split','category']).size().unstack(fill_value=0).to_dict(),shift_magnitudes=sorted(metadata.shift_magnitude_px.unique().tolist()),actual_psf_nonidentity_count=int((metadata.psf_index>=0).sum()),identity_view_count=int((metadata.psf_index<0).sum()),eta_first=eta[0].tolist(),eta_latest=eta[-1].tolist(),formal_training_complete=complete,test_final_mean_loss=float(test['mean_loss']) if test else None,test_final_parents=int(test['parents']) if test else None,status='formal_training_complete_real930_pending' if complete else 'training_in_progress_no_real930_yet')
 save(OUT/'training_snapshot.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

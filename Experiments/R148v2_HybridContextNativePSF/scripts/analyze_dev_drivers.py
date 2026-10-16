"""Explain which generated-scene properties drive current held-out dev loss."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys
import numpy as np,pandas as pd
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import load,save,sha
OUT=ROOT/'results/training_deep_dive';OUT.mkdir(parents=True,exist_ok=True)
def grad_mean(x):return float(.5*(np.abs(np.diff(x,axis=-1)).mean()+np.abs(np.diff(x,axis=-2)).mean())*255)
def main():
 dev_files=sorted(ROOT.glob('runs/formal_8192/dev_[0-9][0-9][0-9][0-9][0-9].json'));path=dev_files[-1];losses=load(path)['individual_loss'];manifest=load(ROOT/'data/payload/manifest.json');entries=sorted((e for e in manifest['entries'] if e['split']=='dev'),key=lambda e:e['index']);assert len(entries)==len(losses)==128;rows=[]
 for e,loss in zip(entries,losses):
  meta=load(ROOT/'data/payload'/e['metadata']);base=load(meta['base_original_metadata']['path']);shape=base['shape']
  with np.load(ROOT/'data/payload'/e['arrays'],allow_pickle=False) as z:target=z['target'].astype(np.float32);noiseless=z['noiseless'].astype(np.float32)
  core=(slice(None),slice(144,240),slice(144,240));difficulty=float(np.sqrt(np.mean((noiseless[core]-target[core])**2))*255);edge=grad_mean(target[:,144:240,144:240]);views=meta['views'];rows.append(dict(index=e['index'],parent_id=e['parent_id'],category=e['category'],loss=float(loss),formation_RMS_gray=difficulty,target_gradient_gray=edge,mean_noise_gray=float(np.mean([v['noise_sigma_gray'] for v in views])),max_shift_px=float(max(np.hypot(*v['shift_xy']) for v in views)),mean_contrast=float(np.mean([v['contrast'] for v in views])),mean_abs_brightness_gray=float(np.mean([abs(v['brightness_gray']) for v in views])),unique_psfs=len(set(v['psf_index'] for v in views if v['psf_index']>=0)),motif=shape.get('motif',''),pitch=shape.get('pitch'),gap=shape.get('gap'),radius=shape.get('radius'),bar_width=shape.get('bar_width'),wave_amplitude=shape.get('wave_amplitude')))
 df=pd.DataFrame(rows);df.to_csv(OUT/'dev_driver_rows.csv',index=False);features=['formation_RMS_gray','target_gradient_gray','mean_noise_gray','max_shift_px','mean_contrast','mean_abs_brightness_gray'];corr=[]
 for scope,g in [('all',df),*[(c,x) for c,x in df.groupby('category')]]:
  for f in features:
   x=g[[f,'loss']].dropna()
   if len(x)>=8 and x[f].nunique()>1:r,p=spearmanr(x[f],x.loss);corr.append(dict(scope=scope,feature=f,n=len(x),spearman=float(r),p_value=float(p)))
 corr_df=pd.DataFrame(corr);corr_df.to_csv(OUT/'dev_driver_correlations.csv',index=False)
 dense=df[df.category=='dense_close_structures'].copy();dense_summary=dense.groupby('motif').loss.agg(['count','mean','median','max']).reset_index();dense_summary.to_csv(OUT/'dense_motif_summary.csv',index=False)
 real_pitch=28.933063776210922;real_radius=8.33015937350939;summary=dict(snapshot_utc=datetime.now(timezone.utc).isoformat(),dev_checkpoint=path.name,dev_checkpoint_sha256=sha(path),rows=len(df),overall_loss_mean=float(df.loss.mean()),dense_loss_share=float(dense.loss.sum()/df.loss.sum()),top20_loss_share=float(df.nlargest(20,'loss').loss.sum()/df.loss.sum()),strongest_absolute_correlations=corr_df.reindex(corr_df.spearman.abs().sort_values(ascending=False).index).head(12).to_dict('records'),dense_motif_summary=dense_summary.to_dict('records'),dense_pitch_range=[float(dense.pitch.min()),float(dense.pitch.max())],dense_gap_range=[float(dense.gap.min()),float(dense.gap.max())],real_evaluation_pitch_px=real_pitch,real_evaluation_radius_px=real_radius,real_evaluation_approx_gap_px=float(real_pitch-2*real_radius),real_pitch_inside_dense_training_range=bool(dense.pitch.min()<=real_pitch<=dense.pitch.max()),scope='Associations within generated dev data; correlations are descriptive and not causal.')
 save(OUT/'dev_driver_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

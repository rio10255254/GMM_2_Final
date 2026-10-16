"""Create the audited objective-specific R150 real-validation readout."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import json
import numpy as np,pandas as pd
from scipy.stats import pearsonr
ROOT=Path(__file__).resolve().parents[1];COMP=ROOT/'results/comparison';OUT=ROOT/'results/real_validation_analysis';OUT.mkdir(parents=True,exist_ok=True);MODEL='R150-MatchedGeometryMeanPSF';R148='R148v2-HybridContextNativePSF'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
 audit=load(ROOT/'results/final_audit.json');assert audit['passed'] and audit['real_images']==930 and audit['real_circles']==8370
 disp=pd.read_csv(COMP/'displacement_summary.csv');geo=pd.read_csv(COMP/'shape_size_summary.csv');sem=pd.read_csv(COMP/'SEM_corrected_size_summary.csv');semc=pd.read_csv(COMP/'SEM_contour_size_summary.csv');paired=pd.read_csv(COMP/'paired_scan_intervals.csv');circles=pd.read_csv(COMP/'all_circles.csv');runtime=pd.read_csv(ROOT/'results/reconstruction_runtime.csv')
 wide=disp.pivot(index='model',columns='kind',values=['mae_nm','repeatability_nm','maximum_error_nm']);rows=[]
 for model in geo.model:
  g=geo[geo.model==model].iloc[0];s=sem[sem.model==model].iloc[0];c=semc[semc.model==model].iloc[0];rows.append(dict(model=model,short_step_mae_nm=wide.loc[model,('mae_nm','adjacent')],short_step_repeatability_nm=wide.loc[model,('repeatability_nm','adjacent')],short_step_max_nm=wide.loc[model,('maximum_error_nm','adjacent')],long_distance_mae_nm=wide.loc[model,('mae_nm','start')],long_distance_repeatability_nm=wide.loc[model,('repeatability_nm','start')],diameter_repeatability_nm=g.diameter_repeat_sd_nm,contour_repeatability_nm=g.contour_repeat_sd_nm,shape_repeatability_nm=g.shape_repeat_sd_nm,worst_diameter_deviation_nm=g.diameter_repeat_absmax_nm,mean_diameter_nm=g.diameter_mean_nm,sem_mean_diameter_error_nm=s.mean_absolute_pillar_difference_nm,sem_max_pillar_error_nm=s.max_absolute_pillar_difference_nm,sem_contour_error_nm=c.mean_absolute_pillar_difference_nm))
 table=pd.DataFrame(rows);metrics=[x for x in table.columns if x!='model']
 for metric in metrics:table[metric.replace('_nm','_rank')]=table[metric].rank(method='min').astype(int)
 table.to_csv(OUT/'objective_rankings.csv',index=False)
 c=circles[circles.model.isin(['Raw',R148,MODEL])];keys=['run','index','pillar_id'];w=c.pivot(index=keys,columns='model',values=['diameter_nm','center_x_px','center_y_px']);delta=w[('diameter_nm',MODEL)]-w[('diameter_nm',R148)];scan=delta.groupby(level='run').mean().rename('R150_minus_R148v2_diameter_nm').reset_index();scan.to_csv(OUT/'scan_diameter_delta.csv',index=False);pillar=delta.groupby(level='pillar_id').mean().rename('R150_minus_R148v2_diameter_nm').reset_index();pillar.to_csv(OUT/'pillar_diameter_delta.csv',index=False)
 sensitivity={}
 for model in [R148,MODEL]:
  y=w[('diameter_nm',model)];x=w[('diameter_nm','Raw')];levels=['index','pillar_id'];xr=x-x.groupby(level=levels).transform('mean');yr=y-y.groupby(level=levels).transform('mean');sensitivity[model]=dict(raw_variation_slope=float(np.dot(xr,yr)/np.dot(xr,xr)),raw_variation_pearson=float(pearsonr(xr,yr).statistic),residual_sd_nm=float(yr.std(ddof=1)))
 current=table[table.model==MODEL].iloc[0];ref148=table[table.model==R148].iloc[0];raw=table[table.model=='Raw'].iloc[0]
 def compare(ref):return {metric:dict(reference=float(ref[metric]),R150=float(current[metric]),difference=float(current[metric]-ref[metric]),percent_better=float(100*(ref[metric]-current[metric])/ref[metric])) for metric in metrics if ref[metric]!=0}
 result=dict(status='complete_and_audited',snapshot_utc=datetime.now(timezone.utc).isoformat(),images=930,circles=8370,models=len(table),checkpoint_sha256=audit['checkpoint_sha256'],R150={m:float(current[m]) for m in metrics},ranks={m:int(current[m.replace('_nm','_rank')]) for m in metrics},vs_Raw=compare(raw),vs_R148v2=compare(ref148),paired_intervals=json.loads(paired[paired.reference.isin(['Raw','R137-WeakPSF','R140v2-StableUNet','R145-Center9PSF25-CorrectedPairs',R148])].to_json(orient='records')),diameter_delta_vs_R148v2=dict(mean_nm=float(delta.mean()),sd_nm=float(delta.std(ddof=1)),median_nm=float(delta.median()),p05_nm=float(delta.quantile(.05)),p95_nm=float(delta.quantile(.95)),scan_mean_min_nm=float(scan.iloc[:,1].min()),scan_mean_max_nm=float(scan.iloc[:,1].max()),pillar_mean_min_nm=float(pillar.iloc[:,1].min()),pillar_mean_max_nm=float(pillar.iloc[:,1].max())),raw_variation_sensitivity=sensitivity,runtime_operational=dict(forward_median_seconds=float(runtime.forward_seconds.median()),end_to_end_median_seconds=float(runtime.end_to_end_seconds.median()),peak_gpu_bytes=int(runtime.peak_gpu_allocated_bytes.max())),limitations=['Same-sample SEM participated in PSF fitting and is not an independent absolute-accuracy validation.','R150 changed matched-geometry coverage and model-side PSF identity policy together; the real-image difference cannot be assigned uniquely to one change.','Runtime is an operational measurement from this run, not a controlled cross-model speed trial.'])
 save(OUT/'summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

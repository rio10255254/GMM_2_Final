"""Build a compact, reproducible readout of the completed real validation."""
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];COMP=ROOT/'results/comparison';MODEL='R148v2-HybridContextNativePSF'
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def pct_better(value,reference):return 100*(reference-value)/reference
def main():
 audit=load(ROOT/'results/final_audit.json');assert audit['passed'] and audit['real_images']==930 and audit['real_circles']==8370
 disp=pd.read_csv(COMP/'displacement_summary.csv');geo=pd.read_csv(COMP/'shape_size_summary.csv');sem=pd.read_csv(COMP/'SEM_corrected_size_summary.csv');sem_contour=pd.read_csv(COMP/'SEM_contour_size_summary.csv');paired=pd.read_csv(COMP/'paired_scan_intervals.csv');runtime=pd.read_csv(ROOT/'results/reconstruction_runtime.csv')
 wide=disp.pivot(index='model',columns='kind',values=['mae_nm','repeatability_nm','maximum_error_nm']);rows=[]
 for model in sorted(geo.model):
  g=geo[geo.model==model].iloc[0];s=sem[sem.model==model].iloc[0];c=sem_contour[sem_contour.model==model].iloc[0]
  rows.append(dict(model=model,short_step_mae_nm=wide.loc[model,('mae_nm','adjacent')],short_step_repeatability_nm=wide.loc[model,('repeatability_nm','adjacent')],long_distance_mae_nm=wide.loc[model,('mae_nm','start')],long_distance_repeatability_nm=wide.loc[model,('repeatability_nm','start')],diameter_repeatability_nm=g.diameter_repeat_sd_nm,contour_repeatability_nm=g.contour_repeat_sd_nm,shape_repeatability_nm=g.shape_repeat_sd_nm,worst_diameter_deviation_nm=g.diameter_repeat_absmax_nm,sem_mean_diameter_error_nm=s.mean_absolute_pillar_difference_nm,sem_max_pillar_error_nm=s.max_absolute_pillar_difference_nm,sem_contour_mean_error_nm=c.mean_absolute_pillar_difference_nm))
 table=pd.DataFrame(rows)
 metrics=[c for c in table.columns if c!='model']
 for c in metrics:table[c.replace('_nm','_rank')]=table[c].rank(method='min').astype(int)
 table.to_csv(ROOT/'results/real_validation_ranking.csv',index=False)
 r=table[table.model==MODEL].iloc[0];raw=table[table.model=='Raw'].iloc[0]
 comparisons={}
 for ref in ['Raw','R137-WeakPSF','R140v2-StableUNet','R145-Center9PSF25-CorrectedPairs','R147-FullResPSFConsistency']:
  b=table[table.model==ref].iloc[0];comparisons[ref]={c:dict(reference=float(b[c]),difference=float(r[c]-b[c]),percent_better=float(pct_better(r[c],b[c]))) for c in metrics}
 paired_selected=json.loads(paired[paired.reference.isin(comparisons)].to_json(orient='records'))
 result=dict(status='complete_and_audited',images=930,circles=8370,model=MODEL,checkpoint_sha256=audit['checkpoint_sha256'],metrics={c:float(r[c]) for c in metrics},ranks={c:int(r[c.replace('_nm','_rank')]) for c in metrics},models_compared=len(table),comparisons=comparisons,paired_scan_intervals=paired_selected,runtime=dict(forward_median_seconds=float(runtime.forward_seconds.median()),forward_mean_seconds=float(runtime.forward_seconds.mean()),end_to_end_median_seconds=float(runtime.end_to_end_seconds.median()),peak_gpu_allocated_bytes=int(runtime.peak_gpu_allocated_bytes.max())),interpretation_boundaries=['SEM size is same-sample reference and is not an independent absolute-accuracy claim.','Runtime was measured while another GPU training process was active, so it is operational timing rather than a controlled speed ranking.','Paired confidence intervals resample complete scans, not individual circles or angles.'])
 save(ROOT/'results/real_validation_summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

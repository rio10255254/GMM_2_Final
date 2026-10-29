"""User-requested hierarchy: one sample SD per 30-step scan, then 30 paired scans."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1]
SRC=Path(str(PROJECT_ROOT / 'Experiments/R152_R148v2_SafeAdaptivePSF'))
OUT=ROOT/'results/scan_repeatability';OUT.mkdir(parents=True,exist_ok=True)
ASSET=ROOT/'poster_build/scan_assets';ASSET.mkdir(parents=True,exist_ok=True)
MODEL='R152-R148v2-SafeAdaptivePSF'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    plan=load(SRC/'evaluation/capture_plan.json');cal=load(SRC/'evaluation/calibration.json');config=load(SRC/'evaluation/measurement_config.json')
    axis=np.asarray(cal['axis_unit_vector'],float);scale=cal['nominal_um_per_px'];assert abs(np.linalg.norm(axis)-1)<1e-12 and scale==.1725
    ref=pd.read_csv(SRC/'results/comparison/all_displacements.csv');ref=ref[ref.kind=='adjacent'];source_summary=load(SRC/'results/comparison/single_scan_step_sd_20260930.json')
    assert len(plan['runs'])==30 and len(plan['frames'])==930
    source_records=[];records=[];steps=[];replay_errors=[]
    for run in plan['runs']:
        name=run['run'];n=run['run_index'];frame_meta=[f for f in plan['frames'] if f['run']==name];assert len(frame_meta)==31
        for label,model,directory in [('Raw','Raw',SRC/'evaluation/baseline_centers/Raw'),('MOSR',MODEL,SRC/'results/centers')]:
            path=directory/(name+'.csv');df=pd.read_csv(path).sort_values(['index','pillar_id']);assert len(df)==279 and not df.duplicated(['index','pillar_id']).any()
            assert df['index'].unique().tolist()==list(range(31)) and df.groupby('index').size().eq(9).all()
            centers=df[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2);delta=np.diff(centers,axis=0);med=np.median(delta,axis=1);measured_um=(med@axis)*scale
            expected=ref[(ref.model==model)&(ref.run==name)].sort_values('j').image_displacement_um.to_numpy();assert expected.shape==(30,)
            error=float(np.max(abs(measured_um-expected)));assert error<1e-10;replay_errors.append(error)
            sd=float(np.std(measured_um*1000,ddof=1));sd_formula=float(np.sqrt(np.sum((measured_um-measured_um.mean())**2)/29)*1000);assert abs(sd-sd_formula)<1e-9
            records.append(dict(scan=n,run=name,method=label,steps=30,step_sd_nm=sd,mean_step_nm=float(measured_um.mean()*1000)))
            for j,value in enumerate(measured_um,1):steps.append(dict(scan=n,run=name,method=label,step=j,displacement_nm=float(value*1000),pi_displacement_nm=float((frame_meta[j]['pi_y_um']-frame_meta[j-1]['pi_y_um'])*1000)))
            source_records.append(dict(path=str(path),sha256=sha(path)))
    stats=pd.DataFrame(records);wide=stats.pivot(index=['scan','run'],columns='method',values='step_sd_nm').reset_index();wide['absolute_reduction_nm']=wide.Raw-wide.MOSR;wide['reduction_pct']=100*(wide.Raw-wide.MOSR)/wide.Raw
    assert len(wide)==30 and (wide.absolute_reduction_nm>0).all()
    assert abs(wide.Raw.mean()-source_summary['model']['Raw']['mean_of_scan_sds_nm'])<1e-8
    assert abs(wide.MOSR.mean()-source_summary['model'][MODEL]['mean_of_scan_sds_nm'])<1e-8
    rng=np.random.default_rng(20260930);ix=rng.integers(0,30,size=(20000,30));gains=wide.reduction_pct.to_numpy();absolute=wide.absolute_reduction_nm.to_numpy()
    ci=np.percentile(gains[ix].mean(axis=1),[2.5,97.5]);aci=np.percentile(absolute[ix].mean(axis=1),[2.5,97.5])
    models={}
    for label in ['Raw','MOSR']:
        v=wide[label].to_numpy();models[label]=dict(mean_scan_sd_nm=float(v.mean()),between_scan_sd_nm=float(v.std(ddof=1)),median_scan_sd_nm=float(np.median(v)),minimum_scan_sd_nm=float(v.min()),maximum_scan_sd_nm=float(v.max()),q1_nm=float(np.percentile(v,25)),q3_nm=float(np.percentile(v,75)))
    summary=dict(unit='nm',definition='sample SD of 30 image-measured adjacent displacements within each scan; then describe 30 independent scan results',n_scans=30,frames_per_scan=31,steps_per_scan=30,total_frames=930,steps_per_method=900,magnification='20x',nominal_step_um=1.0,exposure_us=sorted({f['exposure_us'] for f in plan['frames']}),acquisition_date='2026-09-03',scale_um_per_px=scale,axis_unit_vector=axis.tolist(),circle_reader=dict(core='geometric LSC after normal-gradient boundary refinement',sample_count=config['sample_count'],state_reset_per_pillar=True),models=models,improvement=dict(improved_scans=int((wide.absolute_reduction_nm>0).sum()),mean_paired_reduction_pct=float(gains.mean()),median_paired_reduction_pct=float(np.median(gains)),min_paired_reduction_pct=float(gains.min()),max_paired_reduction_pct=float(gains.max()),p05_p95_pct=np.percentile(gains,[5,95]).tolist(),mean_absolute_reduction_nm=float(absolute.mean()),absolute_gain_range_nm=[float(absolute.min()),float(absolute.max())],mean_paired_reduction_ci95_pct=ci.tolist(),mean_absolute_reduction_ci95_nm=aci.tolist(),ratio_of_mean_sds_reduction_pct=float(100*(wide.Raw.mean()-wide.MOSR.mean())/wide.Raw.mean())),bootstrap=dict(unit='complete paired scan',draws=20000,seed=20260930),primary_uses_pi_residual=False,calibration_scope='Fixed direction estimated from first six Raw scans; shared nominal scale and direction applied to both methods.',verification=dict(center_replay_max_difference_um=max(replay_errors),all_30_steps_present_in_every_scan=True,all_models_have_same_scan_ids=True,alternate_sd_formula_agrees=True))
    stats.to_csv(OUT/'scan_level_sd.csv',index=False);wide.to_csv(OUT/'paired_scan_improvement.csv',index=False);pd.DataFrame(steps).to_csv(OUT/'all_adjacent_steps.csv',index=False);save(OUT/'summary.json',summary)
    for f in ['evaluation/capture_plan.json','evaluation/calibration.json','evaluation/measurement_config.json','results/comparison/all_displacements.csv','results/comparison/single_scan_step_sd_20260930.json','results/final_audit.json']:source_records.append(dict(path=str(SRC/f),sha256=sha(SRC/f)))
    save(OUT/'source_manifest.json',source_records)
    # One prespecified example from scan 1, position 1, from the actual repeated-scan cohort.
    f=plan['frames'][0];assert sha(f['source']['path'])==f['source']['sha256'];raw=np.asarray(Image.open(f['source']['path']),dtype=np.float64)/255
    rp=SRC/f"results/reconstruction/{f['run']}/01.npz";receipt=load(rp.with_suffix('.json'));assert sha(rp)==receipt['output_sha256'];mosr=np.load(rp)['output']
    c=pd.read_csv(SRC/f"evaluation/baseline_centers/Raw/{f['run']}.csv");c=c[c['index']==0];x0=int(np.floor(c.center_x_px.min()))-18;x1=int(np.ceil(c.center_x_px.max()))+19;y0=int(np.floor(c.center_y_px.min()))-18;y1=int(np.ceil(c.center_y_px.max()))+19
    for name,a in [('Raw',raw),('MOSR',mosr)]:Image.fromarray(np.rint(np.clip(a[y0:y1,x0:x1],0,1)*255).astype(np.uint8)).save(ASSET/f'repeat20x_{name}.png')
    save(OUT/'representative_image.json',dict(scan=1,position=0,raw=str(f['source']['path']),mosr=str(rp),crop=[x0,y0,x1,y1],shape=list(raw.shape),display_range=[0,1],scale_um_per_px=.1725))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

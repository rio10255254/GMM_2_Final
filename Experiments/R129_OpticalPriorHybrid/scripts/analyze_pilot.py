"""Faithful fine-contour and limited real-motion comparisons, including every arm."""
import sys,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    meta=load(ROOT/'results/real_inference.json');cases=meta['sem_images'];d=loadmat(ROOT/'results/sem/masks_cells.mat',variable_names=['masks','cells','valid']);assert d['valid'].all(),'Keep failed cases; do not silently remove them'
    r80=ROOT.parent/'R80_InflectionReferenceCircleSEMValidation';sys.path.insert(0,str(r80/'scripts'));import reference_circle_core as core
    src=r80/'scripts/run_sem36_contour_validation.py';nodes=[n for n in ast.parse(src.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name in ['mask_center_radius','radial_signature']];scope=dict(np=np);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src),'exec'),scope)
    old=loadmat(ROOT.parent/'R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat',variable_names=['truth_cells','truth_masks','opt_pitch']);scale=5/float(old['opt_pitch'].item());truth={};points={}
    for i in range(36):
        mask=old['truth_masks'][:,:,i].astype(bool);center,radius=scope['mask_center_radius'](mask);m=core.measure_boundary_and_circles(old['truth_cells'][:,:,i],center,radius,coarse_mask=mask,sample_count=180,normal_half_width_px=3.,polarity='auto');truth[i]=m;points[f'SEM_{i+1}']=m.inflection_points_xy
    rows=[]
    for k,case in enumerate(cases):
        for i in range(36):
            mask=d['masks'][:,:,i,k].astype(bool);center,radius=scope['mask_center_radius'](mask);m=core.measure_boundary_and_circles(d['cells'][:,:,i,k],center,radius,coarse_mask=mask,sample_count=144,normal_half_width_px=3.,polarity='auto');t=truth[i];a=scope['radial_signature'](m);b=scope['radial_signature'](t)
            rows.append(dict(tag=case['tag'],arm=case['arm'],step=case['step'],exposure=case['exposure'],pillar=i+1,radial_nm=float(np.mean(np.abs(a-b))*scale*1000),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),diameter_error_nm=float(abs(m.circles.lsc.radius-t.circles.lsc.radius)*2*scale*1000),MZC_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale*1000),centered_shape_nm=float(np.mean(np.abs((a-a.mean())-(b-b.mean())))*scale*1000)))
            points[f"{case['tag']}_{case['exposure']}_{i+1}"]=m.inflection_points_xy
        print('FineSEM',case['tag'],case['exposure'],flush=True)
    t=pd.DataFrame(rows);assert len(t)==864 and np.isfinite(t.select_dtypes('number')).all().all();t.to_csv(ROOT/'results/sem/per_measurement.csv',index=False);np.savez_compressed(ROOT/'results/sem/boundary_points.npz',**points)
    metrics=['radial_nm','correlation','diameter_error_nm','MZC_error_nm','centered_shape_nm'];by=t.groupby(['tag','arm','step','pillar'],as_index=False)[metrics].median();by.to_csv(ROOT/'results/sem/per_pillar.csv',index=False);summ=by.groupby(['tag','arm','step'],as_index=False)[metrics].median();summ.to_csv(ROOT/'results/sem/summary.csv',index=False)
    contrasts=[]
    for step in [0,24]:
        for a,b,factor in [('B','A','optics_without_AA'),('D','C','optics_with_AA'),('C','A','AA_without_optics'),('D','B','AA_with_optics'),('D','A','combined')]:
            x=by[(by.arm==a)&(by.step==step)].set_index('pillar');y=by[(by.arm==b)&(by.step==step)].set_index('pillar')
            for metric in metrics:
                change=x[metric]-y[metric];gain=change*(1 if metric=='correlation' else -1);contrasts.append(dict(step=step,comparison=factor,candidate=a,control=b,metric=metric,median_candidate_minus_control=float(change.median()),improved=int((gain>1e-7).sum()),worsened=int((gain< -1e-7).sum()),tied=int((gain.abs()<=1e-7).sum())))
    pd.DataFrame(contrasts).to_csv(ROOT/'results/sem/factor_contrasts.csv',index=False)
    # Raw is measured with the exact same source-defined ROI and circle reader.
    panel=load(ROOT/'config/real_panel.json');cfg=load(str(PROJECT_ROOT / panel['sequence_config']['path']));sys.path.insert(0,str(R128/'analysis/lsc_comparison'));from measure import reader
    _,sc=reader(load(R128/'results/lsc_comparison/plan.json'));raw_rows=[]
    for f in panel['motion']:
        s=cfg['sequences'][f['sequence']];im=sc['load_grayscale'](Path(PROJECT_ROOT / f['source']['path']));x0,y0,x1,y1=f['box'];im=im[y0:y1,x0:x1];pred=sc['session_prediction'](f['sequence'],f['frame_index'],np.asarray(s['centers'],float),s['expected_signed_dx_px'])
        for pid,x,y in pred:
            patch,c,origin=core.crop_around(im,(x-x0,y-y0),int(np.ceil(.46*s['pitch_px'])));sc['reset_curvature_cycle']();m=core.measure_inflection_lsc(patch,c,s['radius_px'],sample_count=64 if s['magnification']=='20x' else 96,acm_iterations=13 if s['magnification']=='20x' else 15,normal_half_width_px=2.4 if s['magnification']=='20x' else 4.,polarity='dark')
            raw_rows.append(dict(tag='Raw',sequence=f['sequence'],frame_index=f['frame_index'],pillar_id=int(pid),cx=m.lsc.cx+origin[0]+x0,cy=m.lsc.cy+origin[1]+y0,scale=s['object_um_per_px']))
    centers=pd.concat([pd.read_csv(ROOT/'results/motion_centers.csv'),pd.DataFrame(raw_rows)],ignore_index=True);centers.to_csv(ROOT/'results/motion_centers_with_raw.csv',index=False);pairs=[]
    for tag,g in centers.groupby('tag'):
        idx=g.set_index(['sequence','frame_index','pillar_id'])
        for pair in panel['motion_plan']:
            s=cfg['sequences'][pair['sequence']];ids=sorted(int(x[0]) for x in s['centers']);a=idx.loc[[(pair['sequence'],pair['start'],i) for i in ids],['cx','cy']].to_numpy();b=idx.loc[[(pair['sequence'],pair['end'],i) for i in ids],['cx','cy']].to_numpy();v=(b-a)*s['object_um_per_px'];dx,dy=np.median(v,0)
            pairs.append(dict(tag=tag,sequence=pair['sequence'],start=pair['start'],end=pair['end'],nominal_error_nm=float(abs(abs(dx)-s['nominal_step_um'])*1000),within_grid_nm=float(np.std(v[:,0],ddof=1)*1000),cross_axis_nm=float(abs(dy)*1000)))
    pairs=pd.DataFrame(pairs);pairs.to_csv(ROOT/'results/motion_pairs.csv',index=False);ms=pairs.groupby('tag',as_index=False)[['nominal_error_nm','within_grid_nm','cross_axis_nm']].mean();ms.to_csv(ROOT/'results/motion_summary.csv',index=False)
    save(ROOT/'results/analysis_complete.json',dict(completed_utc=now(),SEM_rows=864,SEM_objects=36,SEM_repeated_exposures=3,motion_pairs_per_method=4,temporal_step_SD_not_estimable_with_one_pair_per_sequence=True,all_failures_retained=True,source=record(__file__),SEM_summary=record(ROOT/'results/sem/summary.csv'),motion_summary=record(ROOT/'results/motion_summary.csv'),pilot_not_full_model_qualification=True))
    print(summ.to_string(index=False));print(ms.to_string(index=False))
if __name__=='__main__':main()

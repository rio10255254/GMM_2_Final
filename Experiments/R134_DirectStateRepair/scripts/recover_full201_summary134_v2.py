"""Recompute failed JSON closeout from retained measurements without changing evidence or gates."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
import pandas as pd
from scipy.optimize import least_squares

def main():
    old=ROOT/'results/full_motion';out=ROOT/'results/full_motion_recovery_v2';out.mkdir(exist_ok=False)
    before=[record(p) for p in old.rglob('*') if p.is_file()]
    save(out/'original_artifacts_before.json',dict(files=before,purpose='Preserve original partial JSON and all images/measurements; this is not a refreshed protected baseline'))
    started=load(old/'started.json');rules=load(ROOT/'config/full_motion_admission.json')['requirements']
    for key in ['checkpoint','rules','source']:assert sha(started[key]['path'])==started[key]['sha256']
    panel=load(ROOT/'config/motion_panel.json');cfg=load(panel['configuration']['path']);plan=load(panel['source_plan']['path']);centers=pd.read_csv(old/'centers.csv');assert len(centers)==1809
    assert not centers.duplicated(['sequence','frame_index','pillar_id']).any();assert np.isfinite(centers[['lsc_center_x_px','lsc_center_y_px']]).all().all()
    errors=[];tables=[]
    for f in plan['frames']:
        d=old/f['sequence']/f"frame_{f['frame_index']:04d}";t=pd.read_csv(d/'centers.csv');points=np.load(d/'points.npz')['inflection_points'];assert len(points)==len(t)==9;tables.append(t)
        for xy,row in zip(points,t.itertuples()):
            origin=xy.mean(0);z=xy-origin
            def residual(c):r=np.linalg.norm(z-c,axis=1);return r-r.mean()
            c=least_squares(residual,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x+origin;e=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px));assert e<1e-4;errors.append(float(e))
    keys=['sequence','frame_index','pillar_id'];a=pd.concat(tables).set_index(keys).sort_index();b=centers.set_index(keys).sort_index();assert a.index.equals(b.index);assert np.allclose(a[['lsc_center_x_px','lsc_center_y_px']].values,b[['lsc_center_x_px','lsc_center_y_px']].values,rtol=0,atol=1e-10) # CSV text roundtrip, observed max4.55e-13px; scientific gates unchanged
    raw=pd.read_csv(ROOT.parent/'R129_OpticalPriorHybrid/results/continuous_lsc/measurements/Raw/centers.csv');checks=[];audit_pairs=0
    for population in ['locked120','within_session194','repositioning3']:
        frames={}
        for name,ct,suffix in [('C',centers,'pairs'),('Raw',raw,'Raw_pairs')]:
            t=pd.read_csv(old/f'{population}_{suffix}.csv');index=ct.set_index(keys)
            for row in t.itertuples():
                spec=cfg['sequences'][row.sequence];ids=[int(v[0]) for v in spec['centers']];x=index.loc[[(row.sequence,row.start_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].values;y=index.loc[[(row.sequence,row.end_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].values;v=(y-x)*spec['object_um_per_px'];dx,dy=np.median(v,axis=0)
                expected=[dx,dy,abs(dx),abs(abs(dx)-spec['nominal_step_um'])*1000,np.std(v[:,0],ddof=1)*1000,abs(dy)*1000];actual=[row.aggregate_dx_um,row.aggregate_dy_um,row.measured_step_um,row.nominal_abs_error_nm,row.within_grid_sd_nm,row.cross_axis_abs_nm];assert np.allclose(expected,actual,rtol=0,atol=1e-7);audit_pairs+=1
            frames[name]=t
        if population=='repositioning3':continue
        c,r=frames['C'],frames['Raw']
        def add(metric,cv,rv,limit,**extra):checks.append(dict(population=population,metric=metric,C=float(cv),Raw=float(rv),ratio=float(cv/rv),limit=float(limit),passed=bool(cv<=limit*rv),**extra))
        for seq,g in c.groupby('sequence'):add('per_sequence_stepSD',g.measured_step_um.std(ddof=1)*1000,r[r.sequence==seq].measured_step_um.std(ddof=1)*1000,rules['each_sequence_step_sd_max_ratio_to_Raw'],sequence=seq)
        for metric,col,stat in [('mean_nominal_abs_error_nm','nominal_abs_error_nm','mean'),('median_within_grid_sd_nm','within_grid_sd_nm','median'),('median_cross_axis_abs_nm','cross_axis_abs_nm','median')]:add(metric,getattr(c[col],stat)(),getattr(r[col],stat)(),rules['aggregate_nominal_within_cross_max_ratio_to_Raw'])
        for col in ['nominal_abs_error_nm','cross_axis_abs_nm']:add('maximum_'+col,c[col].max(),r[col].max(),rules['maximum_nominal_and_cross_error_max_ratio_to_Raw'])
        def wrong(t):return sum(int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][s]['expected_signed_dx_px'])).sum()) for s,g in t.groupby('sequence'))
        checks.append(dict(population=population,metric='wrong_direction',C=wrong(c),Raw=wrong(r),passed=bool(wrong(c)<=wrong(r))))
    assert len(checks)==20 and len(errors)==1809 and audit_pairs==634
    verify();assert all(sha(x['path'])==x['sha256'] for x in before)
    result=dict(frames=201,centers=1809,reused_frames=24,independent_center_refits=len(errors),max_refit_error_px=max(errors),independent_pair_recalculations=audit_pairs,checks=checks,original_artifacts_unchanged=True,original_partial_json=record(old/'complete.json'),source=record(__file__),rules=started['rules'])
    json.dumps(result,allow_nan=False);save(out/'complete.json',result)
    passed=all(c['passed'] for c in checks);save(ROOT/'results/long_admission.json',dict(eligible=passed,selected_seed=started['seed'],arm='C',checkpoint=started['checkpoint'],stage1=record(ROOT/'results/screening_decision.json'),motion12=record(ROOT/'results/motion_screen.json'),motion_audit=record(ROOT/'results/motion_audit.json'),motion201=record(out/'complete.json'),reason='All prospective screens passed after independent closeout recovery' if passed else 'Full201 screen failed; do not start long training',scope='Recovered serialization failure only; original outputs and prospective tolerances unchanged'))
    print(json.dumps(dict(eligible=passed,failed=[c for c in checks if not c['passed']],independent_center_refits=len(errors),independent_pair_recalculations=audit_pairs),indent=2),flush=True)
if __name__=='__main__':main()

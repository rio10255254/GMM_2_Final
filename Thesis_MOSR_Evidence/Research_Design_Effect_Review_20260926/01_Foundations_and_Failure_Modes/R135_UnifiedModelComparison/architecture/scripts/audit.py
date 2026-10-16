import numpy as np
from scipy.optimize import least_squares
def refit(points,table):
    assert len(points)==len(table);errors=[]
    for xy,row in zip(points,table.itertuples()):
        origin=xy.mean(0);z=xy-origin
        def fun(c):r=np.linalg.norm(z-c,axis=1);return r-r.mean()
        c=least_squares(fun,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x+origin;e=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px));assert e<1e-4;errors.append(float(e))
    return errors

def pair_audit(centers,pairs,cfg):
    idx=centers.set_index(['sequence','frame_index','pillar_id'])
    for r in pairs.itertuples():
        s=cfg['sequences'][r.sequence];ids=[int(x[0]) for x in s['centers']];a=idx.loc[[(r.sequence,r.start_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].values;b=idx.loc[[(r.sequence,r.end_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].values;d=(b-a)*s['object_um_per_px'];dx,dy=np.median(d,0)
        assert np.allclose([dx,dy,abs(abs(dx)-s['nominal_step_um'])*1000,np.std(d[:,0],ddof=1)*1000,abs(dy)*1000],[r.aggregate_dx_um,r.aggregate_dy_um,r.nominal_abs_error_nm,r.within_grid_sd_nm,r.cross_axis_abs_nm],rtol=0,atol=1e-7)
    return len(pairs)

def wrong(t,cfg):return sum(int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][s]['expected_signed_dx_px'])).sum()) for s,g in t.groupby('sequence'))

def full_checks(candidate,raw,cfg,rules,population):
    req=rules['requirements'];checks=[]
    def add(metric,c,r,limit,**extra):checks.append(dict(population=population,metric=metric,C=float(c),Raw=float(r),ratio=float(c/r),limit=float(limit),passed=bool(c<=limit*r),**extra))
    for sequence,g in candidate.groupby('sequence'):add('per_sequence_stepSD',g.measured_step_um.std(ddof=1)*1000,raw[raw.sequence==sequence].measured_step_um.std(ddof=1)*1000,req['each_sequence_step_sd_max_ratio_to_Raw'],sequence=sequence)
    for metric,column,fn in [('mean_nominal_abs_error_nm','nominal_abs_error_nm','mean'),('median_within_grid_sd_nm','within_grid_sd_nm','median'),('median_cross_axis_abs_nm','cross_axis_abs_nm','median')]:add(metric,getattr(candidate[column],fn)(),getattr(raw[column],fn)(),req['aggregate_nominal_within_cross_max_ratio_to_Raw'])
    for column in ['nominal_abs_error_nm','cross_axis_abs_nm']:add('maximum_'+column,candidate[column].max(),raw[column].max(),req['maximum_nominal_and_cross_error_max_ratio_to_Raw'])
    checks.append(dict(population=population,metric='wrong_direction',C=wrong(candidate,cfg),Raw=wrong(raw,cfg),passed=wrong(candidate,cfg)<=wrong(raw,cfg)))
    return checks

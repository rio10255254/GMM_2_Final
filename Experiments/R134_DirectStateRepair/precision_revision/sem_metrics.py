"""Same boundary reader, with unrounded normalized optical cells."""
import numpy as np,pandas as pd
from scipy.io import loadmat
from scipy.optimize import least_squares
from validation import reference_circle_core as core
from validation.readout_helpers import mask_center_radius,radial_signature

def score(masks_path,reference_path):
    d=loadmat(masks_path);ref=loadmat(reference_path,variable_names=['truth_cells','truth_masks','opt_pitch']);assert d['valid'].all();assert d['cells'].dtype==np.float64 and d['cells'].min()>=0 and d['cells'].max()<=1
    scale=5000/ref['opt_pitch'].item();truth={};points={};rows=[];errors=[]
    for i in range(36):
        mask=ref['truth_masks'][:,:,i].astype(bool);c,r=mask_center_radius(mask);truth[i+1]=core.measure_boundary_and_circles(ref['truth_cells'][:,:,i],c,r,coarse_mask=mask,sample_count=180,normal_half_width_px=3,polarity='auto');points[f'SEM_{i+1}']=truth[i+1].inflection_points_xy
    def fit(xy):
        o=xy.mean(0);z=xy-o
        def fun(c):r=np.linalg.norm(z-c,axis=1);return r-r.mean()
        c=least_squares(fun,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x;return np.linalg.norm(z-c,axis=1).mean()
    for k,e in enumerate([13,14,15]):
        for i in range(36):
            mask=d['masks'][:,:,i,k].astype(bool);c,r=mask_center_radius(mask);m=core.measure_boundary_and_circles(d['cells'][:,:,i,k],c,r,coarse_mask=mask,sample_count=144,normal_half_width_px=3,polarity='auto');t=truth[i+1];a,b=radial_signature(m),radial_signature(t);signed=2*(m.circles.lsc.radius-t.circles.lsc.radius)*scale
            row=dict(exposure=e,pillar=i+1,radial_nm=float(abs(a-b).mean()*scale),diameter_error_nm=float(abs(signed)),signed_diameter_nm=float(signed),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),MZC_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale));rows.append(row);points[f'{e}_{i+1}']=m.inflection_points_xy;err=abs(2*(fit(m.inflection_points_xy)-fit(t.inflection_points_xy))*scale-signed);assert err<1e-4;errors.append(float(err))
    table=pd.DataFrame(rows);assert len(table)==108 and np.isfinite(table.select_dtypes('number')).all().all();keys=['radial_nm','diameter_error_nm','signed_diameter_nm','centered_shape_nm','correlation','MZC_error_nm'];return table,points,dict(summary=table.groupby('pillar')[keys].median().median().to_dict(),scale_nm_per_px=scale,independent_diameter_refits=108,maximum_refit_error_nm=max(errors),cells_remained_float=True)

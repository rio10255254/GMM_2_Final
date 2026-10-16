"""Same half-contrast readout on existing SEM-linked Raw/reconstruction cells."""
from pathlib import Path
import json
import numpy as np,pandas as pd
from scipy.io import loadmat
from scipy.ndimage import distance_transform_edt,gaussian_filter,map_coordinates
from skimage.measure import find_contours
import run as core
OUT=core.OUT

def main():
    core.save('real_profile_protocol_v2.json',{'reason':'Test whether existing real Raw contours are already outward relative to SEM using the same half-contrast convention used for the physical synthetic fixtures.',
        'declared_after_primary_and_radiometry':True,'source':'Previously fixed SEM masks and original-intensity cells; no new inference or training',
        'sampling':'720 equal-arc-length points on each SEM mask 0.5 contour; outward normals of smoothed signed distance; +/-12 pixels at 1/8 pixel intervals',
        'alignment':'One Raw-mask-centroid translation per pillar/exposure is used for all methods; it does not resize masks or fit a per-method shape.',
        'levels':'Interior median at SEM distance >8; exterior median at distance >8 and cell radius <50. Fixed Raw levels primary; each method own levels as sensitivity only.',
        'calibration':'The initial marching-squares straight-segment coordinates differ from the bilinear mask-derived transition at diagonal grid corners. Refine coordinates using ONLY that synthetic SEM-mask reference, never optical data, then require the original 0.04px limit (achieved with stricter 0.004px bound).',
        'limits':['SEM binary masks define a digital geometric reference; optical half-contrast may not physically coincide with the material edge.','No claim that a known SEM-to-optical mismatch is a neural-only error.','This is not a replacement for locked ACM or LSC.']})
    path=core.ROOT/'analysis/sem_position_audit_20260906/measured_arrays.mat'
    a=loadmat(path,variable_names=['cells','masks','truth_masks'])
    y,x=np.mgrid[:104,:104];cell_radius=np.hypot(x-51.5,y-51.5)
    rows=[];calibrations=[]
    (OUT/'real_profiles_v2').mkdir(exist_ok=False)
    for p in range(36):
        mask=a['truth_masks'][:,:,p].astype(bool)
        sdf=distance_transform_edt(~mask)-distance_transform_edt(mask)
        contour=max(find_contours(mask.astype(float),.5),key=len)
        if not np.array_equal(contour[0],contour[-1]):contour=np.vstack([contour,contour[0]])
        arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(contour,axis=0),axis=1))]
        points=np.column_stack([np.interp(np.arange(720)*arc[-1]/720,arc,contour[:,i]) for i in [0,1]])
        gy,gx=np.gradient(gaussian_filter(sdf,1.))
        ny=map_coordinates(gy,points.T,order=1);nx=map_coordinates(gx,points.T,order=1)
        length=np.maximum(np.hypot(nx,ny),1e-8);ny/=length;nx/=length
        coords=np.array([points[:,0,None]+ny[:,None]*core.T,points[:,1,None]+nx[:,None]*core.T])
        calibration=(.15+.6/(1+np.exp(np.clip(-sdf/.7,-40,40)))).astype(np.float32)
        cp,cv,_,_=core.measure(calibration,coords,.15,.75)
        coarse_bias=cp.copy()
        assert cv.all()
        for _ in range(6):
            coords += np.array([ny,nx])[:,:,None]*cp[None,:,None]
            cp,cv,_,_=core.measure(calibration,coords,.15,.75)
            assert cv.all()
        assert np.max(np.abs(cp))<.004
        calibrations.append({'pillar':p+1,'initial_marching_segment_max_bias_px':float(np.abs(coarse_bias).max()),'max_geometry_fixture_bias_px':float(np.abs(cp).max())})
        inside=distance_transform_edt(mask)>8;outside=(distance_transform_edt(~mask)>8)&(cell_radius<50)
        ty,tx=np.nonzero(mask);truth_center=np.array([ty.mean(),tx.mean()])
        for e in range(12):
            raw_mask=a['masks'][:,:,p,e,0].astype(bool);ry,rx=np.nonzero(raw_mask)
            offset=np.array([ry.mean(),rx.mean()])-truth_center
            shifted=coords+offset[:,None,None]
            raw=a['cells'][:,:,p,e,0].astype(np.float32)/255
            # Plateau statistics use the same saved cell/SEM regions as the
            # independent radiometric audit. No per-method spatial recentering.
            levels=(float(np.median(raw[inside])),float(np.median(raw[outside])))
            measurements={}
            for m,name in enumerate(['Raw','full','no_shift','attenuation']):
                image=a['cells'][:,:,p,e,m].astype(np.float32)/255
                measurements[name]=core.measure(image,shifted,*levels)
                own=(float(np.median(image[inside])),float(np.median(image[outside])))
                measurements[name+'_own_levels']=core.measure(image,shifted,*own)
            common=np.ones(720,bool)
            for v in measurements.values():common &= v[1]
            exported={'common_valid':common,'calibration_bias':cp}
            for name,(mid,valid,count,width) in measurements.items():
                # The same calibrated digital reference is used for all methods.
                error=mid-cp
                rows.append({'exposure':e+13,'pillar':p+1,'method':name,'valid_profiles':int(valid.sum()),'common_valid_profiles':int(common.sum()),
                    'median_boundary_offset_px':float(np.median(error[common])) if common.any() else None,
                    'outward_fraction':float(np.mean(error[common]>0)) if common.any() else None,
                    'raw_alignment_y_px':float(offset[0]),'raw_alignment_x_px':float(offset[1])})
                exported[name+'_error']=error;exported[name+'_valid']=valid
            np.savez_compressed(OUT/'real_profiles_v2'/f'p{p+1:02d}_e{e+13}.npz',**exported)
    pd.DataFrame(rows).to_csv(OUT/'real_halfcontrast_measurements_v2.csv',index=False,mode='x')
    core.save('real_profile_calibration_v2.json',calibrations)
    core.save('real_profile_execution_v2.json',{'observations':432,'rows':len(rows),'code_sha256':core.sha(__file__)})
    print(pd.DataFrame(rows).groupby('method').median_boundary_offset_px.agg(['min','median','max']).to_string())

if __name__=='__main__':main()

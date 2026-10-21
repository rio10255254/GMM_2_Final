"""Independent mask-distance and profile interpolation checks."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from scipy.io import loadmat
from scipy.ndimage import binary_erosion,distance_transform_edt
from scipy.interpolate import RegularGridInterpolator
from scipy.signal import convolve2d
import profiles
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def shift(mask,dx,dy):
    out=np.zeros_like(mask);h,w=mask.shape;x0,x1=max(0,-dx),min(w,w-dx);y0,y1=max(0,-dy),min(h,h-dy)
    if x1>x0 and y1>y0:out[y0+dy:y1+dy,x0+dx:x1+dx]=mask[y0:y1,x0:x1]
    return out
def distance(truth,pred,pitch):
    a=truth^binary_erosion(truth,np.ones((3,3)));b=pred^binary_erosion(pred,np.ones((3,3)))
    return float(np.r_[distance_transform_edt(~a)[b],distance_transform_edt(~b)[a]].mean()*100/pitch)

def main():
    snapshot=json.loads((OUT/'protected_inputs_v2.json').read_text());assert all(sha(p)==h for p,h in snapshot.items())
    a=pd.read_csv(OUT/'acm_measurements.csv');assert len(a)==7776 and a.valid.eq(1).all()
    saved=loadmat(OUT/'acm_arrays.mat',variable_names=['masks','intensity_cells','method_names','truth_historical','truth_pitch_matched','opt_pitch'],squeeze_me=True)
    methods=[str(v) for v in saved['method_names']];pitch=float(saved['opt_pitch'])
    maximum=0.;area_max=0.
    for row in a.itertuples():
        truth=saved['truth_historical' if row.reference=='historical' else 'truth_pitch_matched'][:,:,row.pillar-1].astype(bool)
        mask=saved['masks'][:,:,row.pillar-1,row.exposure-13,methods.index(row.method)].astype(bool)
        value=distance(truth,shift(mask,-int(row.raw_offset_x),-int(row.raw_offset_y)),pitch)
        area=100*(float(mask.sum())-truth.sum())/truth.sum()
        maximum=max(maximum,abs(value-row.common_boundary));area_max=max(area_max,abs(area-row.signed_area))
    assert maximum<2e-6 and area_max<1e-10
    parity=[]
    for method,table in [('R109_full',ROOT.parent/'R109_StagedMidpointWidthScratch/results/posttraining_acm/E048/SEM/results/tables/primary_contour_metrics.csv'),
                         ('R119_full',ROOT/'results/formal_sem/results/tables/primary_contour_metrics.csv')]:
        old=pd.read_csv(table);old=old[old.method!='Raw'];new=a[(a.reference=='historical')&(a.method==method)]
        merged=new.merge(old,left_on=['exposure','pillar'],right_on=['exposure','pillar_id'],validate='one_to_one')
        difference=float((merged.legacy_boundary-merged.mean_boundary_distance_pitch_pct).abs().max());assert difference<2e-6
        parity.append({'method':method,'rows':len(merged),'maximum_historical_metric_difference':difference})
    # A separate interpolation implementation on stored full-intensity profiles.
    p=pd.read_csv(OUT/'profile_measurements.csv');spots=[]
    old=loadmat(ROOT/'results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['raw_masks'])
    for ref in ['historical','global_pitch_matched']:
        for pid,e in [(21,13),(21,24),(6,22)]:
            truth=saved['truth_historical' if ref=='historical' else 'truth_pitch_matched'][:,:,pid-1].astype(bool)
            coords,target=profiles.geometry_profiles(truth)
            row=a[(a.reference==ref)&(a.method=='Raw')&(a.pillar==pid)&(a.exposure==e)].iloc[0]
            offset=np.array([row.raw_offset_y,row.raw_offset_x]);coords=coords+offset[:,None,None]
            inside=distance_transform_edt(truth)>8;yy,xx=np.mgrid[:104,:104];outside=(distance_transform_edt(~truth)>8)&(np.hypot(xx-51.5,yy-51.5)<50)
            raw=saved['intensity_cells'][:,:,pid-1,e-13,methods.index('Raw')].astype(float)/255
            lo,hi=float(np.median(raw[inside])),float(np.median(raw[outside]))
            # Only use samples inside the stored 104px cell for independent
            # comparison; the primary reader retains a wider 128px crop.
            interior_profiles=((coords[0]>=0)&(coords[0]<=103)&(coords[1]>=0)&(coords[1]<=103)).all(1)
            with np.load(OUT/'profile_arrays'/f'{ref}_p{pid:02d}_e{e}.npz') as original:
                for method in ['Raw','R109_full','R119_full']:
                    image=saved['intensity_cells'][:,:,pid-1,e-13,methods.index(method)].astype(float)/255
                    interpolate=RegularGridInterpolator((np.arange(104),np.arange(104)),image,bounds_error=False,fill_value=None)
                    sample=interpolate(np.moveaxis(coords,0,-1).reshape(-1,2)).reshape(720,-1)
                    pos,valid=profiles.crossing((sample-lo)/(hi-lo));mask=valid&original[method+'_half_valid']&interior_profiles
                    difference=float(np.max(np.abs((pos-target['half'][0]-original[method+'_half_error'])[mask])))
                    assert mask.sum()>100 and difference<1e-8
                    spots.append({'reference':ref,'pillar':pid,'exposure':e,'method':method,'profiles':int(mask.sum()),'max_half_position_difference':difference})
    # Independent explicit Gaussian derivative convolution, not the ndimage call.
    source=np.load(OUT/'profile_arrays/historical_p21_e13.npz')['Raw_profile'][:8]
    sigma=.75/profiles.STEP;radius=int(4*sigma+.5);x=np.arange(-radius,radius+1);kernel=np.exp(-x*x/(2*sigma*sigma));kernel/=kernel.sum();kernel=-x/(sigma*sigma)*kernel/profiles.STEP
    explicit=convolve2d(np.pad(source,((0,0),(radius,radius)),mode='edge'),kernel[None],mode='valid')
    from scipy.ndimage import gaussian_filter1d
    library=gaussian_filter1d(source,sigma,order=1,axis=1,mode='nearest')/profiles.STEP
    derivative_difference=float(np.abs(explicit-library).max());assert derivative_difference<1e-12
    record={'protected_inputs_unchanged':len(snapshot),'rendered_images':108,'historical_full_output_pixel_parity':'R109 and R119: all 12 exposures exact',
            'ACM_rows_recomputed':len(a),'maximum_common_ACM_difference_pp':maximum,'maximum_area_difference_pct':area_max,
            'historical_metric_checks':parity,'independent_profile_spots':spots,'explicit_derivative_kernel_max_difference':derivative_difference,
            'no_training':True,'no_confirmation_evaluation':True,'source_sha256':sha(__file__)}
    with (OUT/'verification.json').open('x') as f:json.dump(record,f,indent=2)
    print(json.dumps({k:v for k,v in record.items() if k!='independent_profile_spots'},indent=2))

if __name__=='__main__':main()

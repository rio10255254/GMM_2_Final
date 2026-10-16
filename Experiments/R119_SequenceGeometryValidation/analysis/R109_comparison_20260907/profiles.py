"""Matched half-contrast and strongest-slope readouts, calibrated before data."""
from pathlib import Path
import json,sys,importlib.util
import cv2,numpy as np,pandas as pd
from scipy.io import loadmat
from scipy.ndimage import distance_transform_edt,gaussian_filter,gaussian_filter1d,map_coordinates
from skimage.measure import find_contours
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
T=np.arange(-12,12.00001,.125);STEP=.125;MAIN=['Raw','R109_full','R119_full']

def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
def crossing(u,level=.5):
    hits=(u[:,:-1]<level)&(u[:,1:]>=level);count=hits.sum(1);idx=hits.argmax(1);r=np.arange(len(u))
    lo=u[r,idx];hi=u[r,idx+1];pos=T[idx]+(level-lo)/np.maximum(hi-lo,1e-12)*STEP
    valid=(count==1)&(u[:,0]<level)&(u[:,-1]>level)&np.isfinite(pos)
    return np.where(valid,pos,np.nan),valid

def peak(u,sigma):
    g=gaussian_filter1d(u.astype(float),sigma/STEP,order=1,axis=1,mode='nearest')/STEP
    region=(T>=-6)&(T<=6);idx=np.argmax(np.where(region[None],g,-np.inf),axis=1);r=np.arange(len(u));height=g[r,idx]
    left,right=g[r,idx-1],g[r,idx+1];den=left-2*height+right
    fraction=np.divide(.5*(left-right),den,out=np.zeros_like(den),where=np.abs(den)>1e-12).clip(-1,1)
    pos=T[idx]+fraction*STEP
    maxima=np.zeros_like(g,dtype=bool);maxima[:,1:-1]=(g[:,1:-1]>g[:,:-2])&(g[:,1:-1]>=g[:,2:])
    rivals=(maxima&region[None]&(g>=.8*height[:,None])&(np.abs(T[None]-T[idx,None])>=1.)).any(1)
    valid=np.isfinite(pos)&(height>=.01)&(idx>np.flatnonzero(region)[0])&(idx<np.flatnonzero(region)[-1])&~rivals
    return np.where(valid,pos,np.nan),valid,rivals

def measure(profile,inside,outside):
    u=(profile-inside)/(outside-inside)
    half,hv=crossing(u);low,lv=crossing(u,.1);high,uv=crossing(u,.9)
    width=np.where(lv&uv&(high>low),high-low,np.nan)
    p75,v75,a75=peak(u,.75);p125,v125,a125=peak(u,1.25)
    return {'half':(half,hv),'peak075':(p75,v75),'peak125':(p125,v125)},width,{'peak075':a75,'peak125':a125}

def calibrate():
    rows=[]
    for width in [.7,1.2,3.]:
        for shift in [-.5,0.,.35,.5]:
            u=1/(1+np.exp(-(T-shift)/width))
            for polarity in [-1,1]:
                inside,outside=(.15,.75) if polarity==-1 else (.75,.15)
                measured,_,_=measure((inside+(outside-inside)*u)[None],inside,outside)
                for name,(value,valid) in measured.items():
                    assert valid[0] and abs(value[0]-shift)<.01,(width,shift,polarity,name,value)
                    rows.append({'width':width,'known_shift':shift,'polarity':polarity,'readout':name,'error_px':float(value[0]-shift)})
    flat=np.ones((1,len(T)))*.5
    assert not crossing(flat)[1].any() and not peak(flat,.75)[1].any()
    double=(1/(1+np.exp(-(T+2)/.15))+1/(1+np.exp(-(T-2)/.15)))/2
    assert not peak(double[None],.75)[1].any()
    save('readout_calibration.json',{'cases':rows,'flat_rejected':True,'competing_peaks_rejected':True})

def geometry_profiles(mask):
    sdf=distance_transform_edt(~mask)-distance_transform_edt(mask)
    contour=max(find_contours(mask.astype(float),.5),key=len)
    if not np.array_equal(contour[0],contour[-1]):contour=np.vstack([contour,contour[0]])
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(contour,axis=0),axis=1))]
    p=np.column_stack([np.interp(np.arange(720)*arc[-1]/720,arc,contour[:,i]) for i in [0,1]])
    gy,gx=np.gradient(gaussian_filter(sdf,1.));ny=map_coordinates(gy,p.T,order=1);nx=map_coordinates(gx,p.T,order=1)
    norm=np.maximum(np.hypot(nx,ny),1e-8);nx/=norm;ny/=norm
    coords=np.array([p[:,0,None]+ny[:,None]*T,p[:,1,None]+nx[:,None]*T])
    calibration=(.15+.6/(1+np.exp(np.clip(-sdf/.7,-40,40)))).astype(float)
    for _ in range(6):
        profile=map_coordinates(calibration,coords,order=1,mode='nearest');mid,valid=crossing((profile-.15)/.6);assert valid.all()
        coords+=np.array([ny,nx])[:,:,None]*mid[None,:,None]
    profile=map_coordinates(calibration,coords,order=1,mode='nearest');reference,width,_=measure(profile,.15,.75)
    assert reference['half'][1].all() and np.nanmax(np.abs(reference['half'][0]))<.004
    return coords,reference

def main():
    save('readout_settings.json',{'strongest_slope_sigmas_px':[.75,1.25],'primary_sigma_px':.75,'candidate_search_px':[-6,6],'ambiguity_relative_height':.8,'ambiguity_min_separation_px':1.,
                                'minimum_slope_normalized_per_px':.01,'main_common_min_fraction_for_strong_claim':.9,'intensity_crop_halfsize':64,'ACM_crop_halfsize':52,'no_parameter_selection_from_model_results':True})
    calibrate();methods=json.loads((OUT/'protocol_v2.json').read_text())['methods']
    old=loadmat(ROOT/'results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['truth_masks','raw_masks','global_index','opt_centers'])
    alt=loadmat(ROOT.parent/'R121_BoundaryAnchorFactorial/results/pitch_matched_reference.mat',variable_names=['truth_masks'])
    crops={}
    for e in range(13,25):
        for method in methods:
            image=cv2.imread(str(OUT/'images_v2'/str(e)/f'{method}.png'),0)
            assert image is not None
            for r in range(6):
                for c in range(6):
                    pid=int(old['global_index'][r,c]);cx,cy=np.floor(old['opt_centers'][r*6+c]+.5).astype(int)-1
                    crop=image[cy-64:cy+64,cx-64:cx+64].astype(float)/255;assert crop.shape==(128,128)
                    crops[e,pid,method]=crop
    yy,xx=np.mgrid[:104,:104];rad=np.hypot(xx-51.5,yy-51.5)
    rows=[];cal=[];(OUT/'profile_arrays').mkdir(exist_ok=False)
    for ref,truths in [('historical',old['truth_masks']),('global_pitch_matched',alt['truth_masks'])]:
        for pid in range(1,37):
            mask=truths[:,:,pid-1].astype(bool);coords,reference=geometry_profiles(mask)
            inside=distance_transform_edt(mask)>8;outside=(distance_transform_edt(~mask)>8)&(rad<50)
            ty,tx=np.nonzero(mask);tc=np.array([ty.mean(),tx.mean()])
            cal.append({'reference':ref,'pillar':pid,'half_max_error':float(np.nanmax(np.abs(reference['half'][0]))),'peak075_valid':int(reference['peak075'][1].sum()),'peak125_valid':int(reference['peak125'][1].sum())})
            for e in range(13,25):
                ry,rx=np.nonzero(old['raw_masks'][:,:,pid-1,e-13]);delta=np.array([ry.mean(),rx.mean()])-tc
                offset=(np.sign(delta)*np.floor(np.abs(delta)+.5)).astype(int)
                shifted=coords+(offset+12)[:,None,None]
                raw104=crops[e,pid,'Raw'][12:-12,12:-12];lo=float(np.median(raw104[inside]));hi=float(np.median(raw104[outside]));assert hi>lo
                results={};widths={};ambiguous={};saved={}
                for method in methods:
                    crop=crops[e,pid,method];profile=map_coordinates(crop,shifted,order=1,mode='nearest')
                    values,width,amb=measure(profile,lo,hi);widths[method]=width;ambiguous[method]=amb
                    own=crop[12:-12,12:-12];own_lo,own_hi=float(np.median(own[inside])),float(np.median(own[outside]))
                    own_half,own_valid=crossing((profile-own_lo)/(own_hi-own_lo))
                    values['half_own_levels']=(own_half,own_valid)
                    results[method]={}
                    for readout,(position,valid) in values.items():
                        target_name='half' if readout=='half_own_levels' else readout
                        target,tvalid=reference[target_name]
                        results[method][readout]=(position-target,valid&tvalid)
                        saved[method+'_'+readout+'_error']=position-target;saved[method+'_'+readout+'_valid']=valid&tvalid
                    saved[method+'_width']=width
                    if pid==21 and e in [13,24]:saved[method+'_profile']=profile
                for readout in ['half','half_own_levels','peak075','peak125']:
                    common=np.logical_and.reduce([results[m][readout][1] for m in MAIN])
                    for method in methods:
                        error,valid=results[method][readout]
                        full='Raw' if method=='Raw' else 'R109_full' if method.startswith('R109') else 'R119_full'
                        fe,fv=results[full][readout];paired=valid&fv
                        def val(array,select,fun=np.median):return float(fun(array[select])) if select.any() else None
                        rows.append({'reference':ref,'exposure':e,'pillar':pid,'method':method,'readout':readout,'valid_profiles':int(valid.sum()),
                                     'ambiguous_profiles':int(ambiguous[method][readout].sum()) if readout.startswith('peak') else None,
                                     'median_signed_error_px':val(error,valid),'mean_absolute_error_px':val(np.abs(error),valid,np.mean),
                                     'main_common_profiles':int(common.sum()),'main_common_mae_px':val(np.abs(error),common,np.mean) if method in MAIN else None,
                                     'main_common_bias_px':val(error,common) if method in MAIN else None,
                                     'paired_full_profiles':int(paired.sum()),'paired_mae_change_vs_full_px':val(np.abs(error)-np.abs(fe),paired,np.mean),
                                     'paired_signed_change_vs_full_px':val(error-fe,paired),'median_width_px':float(np.nanmedian(widths[method])) if np.isfinite(widths[method]).any() else None,
                                     'raw_offset_y':int(offset[0]),'raw_offset_x':int(offset[1])})
                np.savez_compressed(OUT/'profile_arrays'/f'{ref}_p{pid:02d}_e{e}.npz',**saved)
            print(json.dumps({'reference':ref,'pillar_done':pid}),flush=True)
    pd.DataFrame(rows).to_csv(OUT/'profile_measurements.csv',index=False,mode='x')
    save('geometry_calibration.json',cal);save('profile_execution.json',{'rows':len(rows),'methods':len(methods),'reference_count':2,'observations_per_method':432})

if __name__=='__main__':main()

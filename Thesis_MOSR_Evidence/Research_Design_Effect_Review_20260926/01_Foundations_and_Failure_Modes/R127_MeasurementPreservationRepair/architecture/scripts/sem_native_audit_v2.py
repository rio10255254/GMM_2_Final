"""Native-source, model-independent relative scale and SEM definition audit."""
import cv2
import pandas as pd
from PIL import Image
from scipy.io import loadmat
from scipy.ndimage import map_coordinates,gaussian_filter1d
from common import *

ANGLE=np.arange(720)*2*np.pi/720;C=np.cos(ANGLE);S=np.sin(ANGLE)

def radial(image,center,radii):
    coords=np.array([center[1]+S[:,None]*radii,center[0]+C[:,None]*radii])
    return map_coordinates(image.astype(float),coords,order=1,mode='nearest')

def refine(image,center,kind):
    rr=np.arange(85,155.00001,.25) if kind=='sem' else np.arange(20,55.00001,.125)
    center=np.asarray(center,dtype=float).copy()
    for _ in range(3):
        p=radial(image,center,rr)
        if kind=='sem':r=rr[np.argmax(gaussian_filter1d(p,4,axis=1),axis=1)]
        else:
            inside=np.median(radial(image,center,np.arange(3,16)),axis=1);outside=np.median(radial(image,center,np.arange(52,59)),axis=1)
            u=(p-inside[:,None])/(outside-inside)[:,None];hits=(u[:,:-1]<.5)&(u[:,1:]>=.5);idx=hits.argmax(1);ii=np.arange(720)
            r=rr[idx]+(.5-u[ii,idx])/np.maximum(u[ii,idx+1]-u[ii,idx],1e-8)*(rr[1]-rr[0])
        basis=np.column_stack([np.ones(720),C,S,np.cos(2*ANGLE),np.sin(2*ANGLE)])
        beta=np.linalg.lstsq(basis,r,rcond=None)[0]
        # First harmonics are center offsets; retain higher-order shape.
        center+=beta[1:3]
    return center

def sem_radii(image,center):
    rr=np.arange(85,155.00001,.25);profiles=gaussian_filter1d(radial(image,center,rr),4,axis=1);n=np.arange(720);idx=profiles.argmax(1)
    peak=rr[idx].copy();left=profiles[n,np.maximum(idx-1,0)];mid=profiles[n,idx];right=profiles[n,np.minimum(idx+1,len(rr)-1)]
    denom=left-2*mid+right;fraction=np.divide(.5*(left-right),denom,out=np.zeros(720),where=np.abs(denom)>1e-10).clip(-1,1);peak+=fraction*.25
    inner_base=np.median(profiles[:,:30],axis=1);outer_base=np.median(profiles[:,-30:],axis=1)
    inner_level=(inner_base+mid)/2;outer_level=(outer_base+mid)/2;inner=np.full(720,np.nan);outer=inner.copy()
    for j in range(720):
        before=np.flatnonzero((profiles[j,:-1]<inner_level[j])&(profiles[j,1:]>=inner_level[j])&(np.arange(len(rr)-1)<idx[j]))
        after=np.flatnonzero((profiles[j,:-1]>=outer_level[j])&(profiles[j,1:]<outer_level[j])&(np.arange(len(rr)-1)>=idx[j]))
        if len(before):
            k=before[-1];inner[j]=rr[k]+.25*(inner_level[j]-profiles[j,k])/(profiles[j,k+1]-profiles[j,k])
        if len(after):
            k=after[0];outer[j]=rr[k]+.25*(outer_level[j]-profiles[j,k])/(profiles[j,k+1]-profiles[j,k])
    return peak,inner,outer

def pitches(centers,rows,cols):
    g=np.asarray(centers).reshape(rows,cols,2);x=np.linalg.norm(np.diff(g,axis=1),axis=2);y=np.linalg.norm(np.diff(g,axis=0),axis=2)
    return np.r_[x.ravel(),y.ravel()]

def main():
    out=ROOT/'results/sem_native_v2';out.mkdir(parents=True,exist_ok=False)
    oldpath=EXPS/'R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat';old=loadmat(oldpath,variable_names=['opt_centers','global_index']);optpath=EXPS/'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/13.bmp';opt=cv2.imread(str(optpath),0)
    orig=old['opt_centers'].astype(float)-1
    optical=np.array([refine(opt,c,'optical') for c in orig]);op=pitches(optical,6,6);opt_pitch=float(np.median(op))
    # Same archived physical-object mapping, not estimated from model scores.
    blocks=[(3,1),(3,2),(3,3),(2,3),(2,2),(2,1),(1,1),(1,2),(1,3)]
    sources=[record(oldpath),record(optpath)];records=[];scale_rows=[];arrays={};centers_sem=[];footers=[]
    for file in range(1,10):
        path=Path(r'H:\From_2TB_D_disk\13_thesis\SEM_data')/f'P-{file:02d}.tiff';im=np.array(Image.open(path))[...,0];sources.append(record(path));crop=im[6:754,141:914]
        found=cv2.HoughCircles(cv2.GaussianBlur(crop,(0,0),3),cv2.HOUGH_GRADIENT,1,220,param1=40,param2=40,minRadius=90,maxRadius=145)
        if found is None or len(found[0])!=4:raise ValueError(f'Native SEM circle initialization failed: {file}, {None if found is None else found[0].tolist()}')
        initial=found[0,:,:2];initial=initial[np.argsort(initial[:,1])];initial=np.vstack([x[np.argsort(x[:,0])] for x in [initial[:2],initial[2:]]])
        centers=np.array([refine(crop,c,'sem') for c in initial]);pp=pitches(centers,2,2);centers_sem.append(centers)
        scale_rows.append(dict(file=file,native_SEM_pitch=float(np.median(pp)),native_SEM_pitch_x=float(np.linalg.norm(centers[1]-centers[0])),native_SEM_pitch_y=float(np.linalg.norm(centers[2]-centers[0])),optical_pitch=opt_pitch,relative_factor_to_historical=opt_pitch/(np.median(pp)/3.23)))
        br,bc=blocks[file-1];ids=old['global_index'][2*br-2:2*br,2*bc-2:2*bc].ravel().astype(int)
        for local,(center,pid) in enumerate(zip(centers,ids)):
            rim,inner,outer=sem_radii(crop,center);valid=np.isfinite(inner)&np.isfinite(outer)&(inner<rim)&(rim<outer)
            arrays[f'p{pid:02d}_rim']=rim;arrays[f'p{pid:02d}_inner']=inner;arrays[f'p{pid:02d}_outer']=outer
            row=dict(pillar=int(pid),file=file,local=local+1,center_x=float(center[0]+141),center_y=float(center[1]+6),valid_rays=int(valid.sum()),rim_radius_native=float(np.sqrt(np.mean(rim**2))),inner_radius_native=float(np.sqrt(np.mean(inner[valid]**2))),outer_radius_native=float(np.sqrt(np.mean(outer[valid]**2))),median_rim_halfwidth_native=float(np.median((outer-inner)[valid])),native_pitch=float(np.median(pp)))
            records.append(row)
        # Save original footer pixels only, for human verification of printed units.
        footer=im[-24:,:240];footers.append(footer)
        print(json.dumps(scale_rows[-1]),flush=True)
    pd.DataFrame(records).to_csv(out/'native_SEM_objects.csv',index=False);pd.DataFrame(scale_rows).to_csv(out/'native_scale.csv',index=False)
    np.savez_compressed(out/'native_references.npz',optical_centers=optical,SEM_centers=np.stack(centers_sem),**arrays)
    montage=np.concatenate(footers,axis=0);Image.fromarray(montage).save(out/'original_scale_bar_footers.png')
    med=np.median([x['native_SEM_pitch'] for x in scale_rows]);ratio=opt_pitch/med;factor=ratio*3.23
    loo=[opt_pitch/np.median([x['native_SEM_pitch'] for x in scale_rows if x['file']!=j])*3.23 for j in range(1,10)]
    result=dict(status='native_scale_and_edge_definition_audit_complete',sources=sources,old_reference_files_modified=False,optical_pitch=opt_pitch,native_SEM_pitch_median=float(med),native_SEM_to_optical_scale=float(ratio),historical_scale=1/3.23,relative_factor_to_historical=float(factor),leave_one_SEM_image_out_factor_range=[float(min(loo)),float(max(loo))],minimum_valid_rays=min(x['valid_rays'] for x in records),median_SEM_edge_definition_width_optical_px=float(np.median([x['median_rim_halfwidth_native'] for x in records])*ratio),neural_outputs_used_for_scale=False,absolute_instrument_calibration_qualified=False,physical_edge_equivalence_qualified=False,profile_role='native SEM rim and sensitivity band; relative center-pitch transfer only')
    save(out/'summary.json',result)

if __name__=='__main__':main()

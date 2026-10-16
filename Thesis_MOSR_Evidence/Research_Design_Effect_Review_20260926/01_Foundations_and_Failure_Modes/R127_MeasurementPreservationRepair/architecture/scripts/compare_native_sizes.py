"""Dimensionless native-size comparison, with SEM edge-definition sensitivity."""
import cv2,pandas as pd
from scipy.io import loadmat
from common import *
from sem_native_audit_v2 import radial,pitches

def crossing_radii(image,centers,plateaus=None):
    rr=np.arange(20,55.00001,.125);radii=[];valids=[];levels=[]
    for i,c in enumerate(centers):
        if plateaus is None:
            inside=np.median(radial(image,c,np.arange(3,16)),axis=1);outside=np.median(radial(image,c,np.arange(52,59)),axis=1)
        else:inside,outside=plateaus[i]
        p=radial(image,c,rr);den=outside-inside;u=(p-inside[:,None])/np.maximum(den[:,None],1e-8);hits=(u[:,:-1]<.5)&(u[:,1:]>=.5);idx=hits.argmax(1);j=np.arange(720)
        v=rr[idx]+.125*(.5-u[j,idx])/np.maximum(u[j,idx+1]-u[j,idx],1e-8);valid=(hits.sum(1)==1)&(den>1/255)&np.isfinite(v)
        radii.append(v);valids.append(valid);levels.append((inside,outside))
    return np.asarray(radii),np.asarray(valids),levels

def main():
    root=ROOT/'results/sem_native_v2';refs=np.load(root/'native_references.npz');sem=pd.read_csv(root/'native_SEM_objects.csv');centers=refs['optical_centers'];mapping=loadmat(EXPS/'R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['global_index'])['global_index']
    rows=[];sources=[];methods=[('Raw',None)]+[(f'{a}_s{s}',R126/'results'/f'real_{a}_s{s}_step0128') for a in ['P','Q'] for s in [1265001,1265002]]
    for exposure in [13,24]:
        path=EXPS/f'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/{exposure}.bmp';raw=cv2.imread(str(path),0).astype(float)/255;sources.append(record(path))
        _,_,levels=crossing_radii(raw,centers);predictions={}
        for name,folder in methods:
            if folder is None:image=raw
            else:
                p=folder/f'full_images/sem_optical_exposure{exposure}/output_float.npz';sources.append(record(p))
                with np.load(p) as d:image=d['output']
            predictions[name]=crossing_radii(image,centers,levels)[:2]
        for _,row in sem.iterrows():
            pid=int(row.pillar);gy,gx=np.argwhere(mapping==pid)[0];idx=gy*6+gx;by,bx=(gy//2)*2,(gx//2)*2;group=centers.reshape(6,6,2)[by:by+2,bx:bx+2].reshape(4,2);opt_pitch=float(np.median(pitches(group,2,2)))
            inner=refs[f'p{pid:02d}_inner'];rim=refs[f'p{pid:02d}_rim'];outer=refs[f'p{pid:02d}_outer'];valid=np.isfinite(inner)&np.isfinite(outer)&(inner<rim)&(rim<outer)
            for value,mask in predictions.values():valid &= mask[idx]
            count=int(valid.sum())
            if count==0:raise ValueError('No shared native-size population')
            ratio=lambda v,pitch:float(2*np.sqrt(np.mean(v[valid]**2))/pitch)
            lo,mid,hi=[ratio(v,row.native_pitch) for v in [inner,rim,outer]];raw_value=ratio(predictions['Raw'][0][idx],opt_pitch)
            for name,(value,_) in predictions.items():
                x=ratio(value[idx],opt_pitch);possible=np.array([lo,hi,np.clip(x,lo,hi),np.clip(raw_value,lo,hi)]);differences=np.abs(x-possible)-np.abs(raw_value-possible)
                result=dict(exposure=exposure,pillar=pid,SEM_file=int(row.file),method=name,common_rays=count,optical_group_pitch=opt_pitch,SEM_native_group_pitch=row.native_pitch,optical_diameter_pitch_ratio=x,SEM_inner_ratio=lo,SEM_rim_ratio=mid,SEM_outer_ratio=hi,Raw_diameter_pitch_ratio=raw_value,minimum_error_ratio=max(lo-x,x-hi,0),maximum_error_ratio=max(abs(x-lo),abs(x-hi)),paired_change_lower=float(differences.min()),paired_change_upper=float(differences.max()),compatible_with_definition_band=bool(lo<=x<=hi))
                result['direction_over_entire_band']='improves' if result['paired_change_upper']<-1e-12 else 'worsens' if result['paired_change_lower']>1e-12 else 'unresolved_or_equal';rows.append(result)
    out=ROOT/'results/native_size_comparison';out.mkdir(exist_ok=False);df=pd.DataFrame(rows);df.to_csv(out/'measurements.csv',index=False)
    summary=[]
    for (exposure,method),d in df.groupby(['exposure','method']):summary.append(dict(exposure=int(exposure),method=method,objects=len(d),minimum_common_rays=int(d.common_rays.min()),compatible_objects=int(d.compatible_with_definition_band.sum()),definitely_improved=int((d.direction_over_entire_band=='improves').sum()),definitely_worsened=int((d.direction_over_entire_band=='worsens').sum()),unresolved_or_equal=int((d.direction_over_entire_band=='unresolved_or_equal').sum()),median_paired_lower=float(d.paired_change_lower.median()),median_paired_upper=float(d.paired_change_upper.median())))
    save(out/'summary.json',dict(rows=len(rows),summary=summary,sources=sources,old_references_changed=False,no_SEM_resampling=True,scale_from_candidate=False,band_is_definition_sensitivity_not_statistical_confidence=True,zero_minimum_error_means_compatibility_not_exactness=True,physical_accuracy_qualified=False))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()

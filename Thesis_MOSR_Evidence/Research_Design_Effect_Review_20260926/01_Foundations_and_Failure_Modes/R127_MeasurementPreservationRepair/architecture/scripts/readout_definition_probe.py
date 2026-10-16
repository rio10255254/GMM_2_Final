"""Explain definition sensitivity without choosing a favorable threshold.

Added after native-size comparisons; exploratory, never a new selection gate.
All three crossing levels and both Raw-derived inside definitions are retained.
"""
import cv2,pandas as pd
from common import *
from sem_native_audit_v2 import radial

def main():
    centers=np.load(ROOT/'results/sem_native_v2/native_references.npz')['optical_centers'];rr=np.arange(20,55.00001,.125);methods=[('Raw',None)]+[(f'{a}_s{s}',R126/'results'/f'real_{a}_s{s}_step0128') for a in ['P','Q'] for s in [1265001,1265002]];rows=[];brightness=[]
    for exposure in [13,24]:
        p=EXPS/f'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/{exposure}.bmp';raw=cv2.imread(str(p),0).astype(float)/255;images={'Raw':raw}
        for name,folder in methods[1:]:
            with np.load(folder/f'full_images/sem_optical_exposure{exposure}/output_float.npz') as d:images[name]=d['output']
        for idx,c in enumerate(centers):
            inside1=np.median(radial(raw,c,np.arange(3,16)),axis=1);inside2=np.median(radial(raw,c,np.arange(24,29)),axis=1);outside=np.median(radial(raw,c,np.arange(52,59)),axis=1)
            brightness.append(dict(exposure=exposure,grid_index=idx,center_gray=float(np.median(inside1)*255),inner_rim_gray=float(np.median(inside2)*255),outside_gray=float(np.median(outside)*255),center_minus_inner_rim_gray=float(np.median(inside1-inside2)*255)))
            profiles={name:radial(im,c,rr) for name,im in images.items()}
            for definition,inside in [('central_3_to15',inside1),('inner_24_to28',inside2)]:
                for level in [.3,.5,.7]:
                    values={};valid=np.ones(720,dtype=bool)
                    for name,pv in profiles.items():
                        u=(pv-inside[:,None])/np.maximum((outside-inside)[:,None],1e-8);hits=(u[:,:-1]<level)&(u[:,1:]>=level);k=hits.argmax(1);j=np.arange(720);r=rr[k]+.125*(level-u[j,k])/np.maximum(u[j,k+1]-u[j,k],1e-8);v=(hits.sum(1)==1)&np.isfinite(r);valid &= v;values[name]=r
                    if not valid.any():raise ValueError('Empty shared definition probe')
                    for name,v in values.items():rows.append(dict(exposure=exposure,grid_index=idx,definition=definition,level=level,method=name,common_rays=int(valid.sum()),mean_radius_change_vs_Raw=float((v-values['Raw'])[valid].mean())))
    out=ROOT/'results/readout_definition_probe';out.mkdir(exist_ok=False);pd.DataFrame(rows).to_csv(out/'profile_changes.csv',index=False);pd.DataFrame(brightness).to_csv(out/'Raw_internal_levels.csv',index=False)
    table=pd.DataFrame(rows).groupby(['exposure','definition','level','method'],as_index=False).mean_radius_change_vs_Raw.median();table.to_csv(out/'summary.csv',index=False)
    photo=pd.DataFrame(brightness).groupby('exposure').center_minus_inner_rim_gray.agg(['min','median','max']).reset_index().to_dict('records')
    save(out/'verification.json',dict(rows=len(rows),Raw_level_rows=len(brightness),brightness_summary=photo,all_definitions_retained=True,model_or_targets_modified=False,SEM_source_used_for_training=False,selected_edge_definition_for_model_success=False,role='Exploratory profile-shape and plateau sensitivity, not independent true-edge calibration'))
    print(json.dumps(photo),flush=True)

if __name__=='__main__':main()

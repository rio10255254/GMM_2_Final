"""Declared follow-up: vary intensity offset and contrast independently."""
from pathlib import Path
import json
import cv2,numpy as np,pandas as pd,torch
from scipy.io import loadmat
from scipy.ndimage import distance_transform_edt
import run as core

OUT=core.OUT
def main():
    torch.set_num_threads(4);cv2.setNumThreads(1)
    assert (OUT/'execution_record.json').exists()
    saved=loadmat(core.ROOT/'analysis/sem_position_audit_20260906/measured_arrays.mat',variable_names=['cells','truth_masks'])
    yy,xx=np.mgrid[:104,:104];radius=np.hypot(xx-51.5,yy-51.5);levels=[]
    for p in range(36):
        truth=saved['truth_masks'][:,:,p].astype(bool)
        inside=distance_transform_edt(truth)>8;outside=(distance_transform_edt(~truth)>8)&(radius<50)
        assert inside.sum()>100 and outside.sum()>100
        for e in range(12):
            image=saved['cells'][:,:,p,e,0].astype(float)/255
            levels.append({'exposure':e+13,'pillar':p+1,'inside':float(np.median(image[inside])),'outside':float(np.median(image[outside]))})
    observed=pd.DataFrame(levels);observed.to_csv(OUT/'observed_intensity_levels.csv',index=False,mode='x')
    median=observed.groupby('exposure')[['inside','outside']].median()
    specs=[]
    for shape in ['line','circle48']:
        for polarity in [-1,1]:
            for midpoint in [.2,.35,.5,.65,.8]:
                for contrast in [.15,.3,.5]:
                    lo,hi=midpoint-contrast/2,midpoint+contrast/2
                    if lo<.02 or hi>.98:continue
                    inside,outside=(lo,hi) if polarity==-1 else (hi,lo)
                    specs.append(dict(shape=shape,polarity=polarity,group='independent_levels',sigma=1.5,dx=0.,dy=0.,midpoint=midpoint,contrast=contrast,inside=inside,outside=outside))
        for exposure,row in median.iterrows():
            for sigma in [1.5,3.]:
                specs.append(dict(shape=shape,polarity=-1,group='observed_levels_only',sigma=sigma,dx=0.,dy=0.,exposure=int(exposure),inside=float(row.inside),outside=float(row.outside),midpoint=float((row.inside+row.outside)/2),contrast=float(row.outside-row.inside)))
    specs=[dict(case_id=i,**r) for i,r in enumerate(specs)]
    core.save('radiometry_protocol.json',{'reason':'Primary fixed-ratio brightness/blur/motion fixtures do not recreate consistent real expansion. Separate offset from contrast before deciding a training change.',
              'declared_after_primary_results':True,'cases':specs,'population':'Synthetic geometry; observed_levels_only borrows only Raw intensity summaries, no real pixels or SEM shape for generation.',
              'readout':'Exactly the same predeclared normal crossing readout and common-profile policy as the primary study.',
              'no_training':True,'no_confirmation':True})
    (OUT/'radiometry_cases').mkdir(exist_ok=False)
    model=core.load(core.ROOT/'runs/formal_B_s1195001/weights/epoch_042.pth','cuda');rows=[]
    for row in specs:
        source,target=core.physical(row['shape'],row['sigma'],0.,0.)
        inside,outside=row['inside'],row['outside']
        raw=(outside+(inside-outside)*source).astype(np.float32);truth=(outside+(inside-outside)*target).astype(np.float32)
        result=core.outputs(model,raw,row);coords,nx,ny=core.samples(row['shape'])
        tp,tvalid,_,tw=core.measure(truth,coords,inside,outside)
        measured={k:core.measure(v,coords,inside,outside) for k,v in result.items()}
        common=tvalid.copy()
        for value in measured.values():common&=value[1]
        profiles={'common_valid':common,'target_position':tp,'target_width':tw}
        for name,(pos,valid,count,width) in measured.items():
            error=pos-tp
            rows.append({**row,'method':name,'valid_profiles':int(valid.sum()),'common_valid_profiles':int(common.sum()),
                         'signed_bias_px':float(np.median(error[common])) if common.any() else None,
                         'boundary_mae_px':float(np.mean(np.abs(error[common]))) if common.any() else None,
                         'median_absolute_boundary_error_px':float(np.median(np.abs(error[common]))) if common.any() else None,
                         'median_transition_width_px':float(np.nanmedian(width[common])) if common.any() else None})
            profiles[name+'_position_error']=error;profiles[name+'_width']=width;profiles[name+'_valid']=valid
        folder=OUT/'radiometry_cases'/f"{row['case_id']:03d}";folder.mkdir()
        np.savez_compressed(folder/'images.npz',reference=truth,**result);np.savez_compressed(folder/'profiles.npz',**profiles)
        print(json.dumps({'radiometry_case':row['case_id'],'total':len(specs),'common_valid':int(common.sum())}),flush=True)
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'radiometry_measurements.csv',index=False,mode='x')
    snapshot=json.loads((OUT/'input_snapshot.json').read_text());assert all(core.sha(p)==h for p,h in snapshot.items())
    core.save('radiometry_execution.json',{'cases':len(specs),'rows':len(frame),'protected_inputs_unchanged':len(snapshot),'source_code_sha256':core.sha(__file__)})

if __name__=='__main__':main()

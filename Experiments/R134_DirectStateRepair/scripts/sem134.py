from pathlib import Path
import sys,time,subprocess,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
import cv2,pandas as pd
from scipy.io import loadmat
from net.inference_policy import guard as oldguard
from validation import reference_circle_core as core
from validation.readout_helpers import mask_center_radius,radial_signature

def guard16(raw,pred):
    h,w=raw.shape[-2:];yy=torch.arange(h,device=raw.device)[:,None];xx=torch.arange(w,device=raw.device)[None,:];d=torch.minimum(torch.minimum(yy,h-1-yy),torch.minimum(xx,w-1-xx));weight=((d-16)/16).clamp(0,1);return raw+(pred-raw)*weight

def evaluate(arm,seed,step):
    run=ROOT/f'runs/R134_{arm}_s{seed}';cp=run/('initial.pth' if step==0 else f'step{step:04d}.pth')
    while not cp.exists():time.sleep(2)
    # Checkpoints are read only after the writer closes them (initial beforedev,
    # final completion marker before final evaluation).
    if step:
        while not (run/'complete.json').exists():time.sleep(2)
    else:time.sleep(2)
    tag=f'{arm}_s{seed}_p{step:04d}';out=ROOT/f'results/real/{tag}';out.mkdir(parents=True,exist_ok=False);model=create(arm,seed);payload=torch.load(cp,map_location='cpu');model.load_state_dict(payload['model'],strict=True);model.eval();records=[]
    with torch.no_grad():
        for e in [13,14,15]:
            src=ROOT/f'validation/inputs/sem{e}.png';raw=cv2.imread(str(src),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();value=guard16(x,model(x))[0,0].cpu().numpy();image=np.rint(value*255).clip(0,255).astype(np.uint8);p=out/f'sem{e}.png';assert cv2.imwrite(str(p),image);np.save(out/f'sem{e}.npy',value);records.append(dict(exposure=e,source=record(src),image=record(p)))
            if arm=='C' and step==0:assert np.array_equal(raw,image)
    del model;torch.cuda.empty_cache()
    cmd=f"addpath('{(ROOT/'validation').as_posix()}');extract_sem('{out.as_posix()}');"
    with (out/'matlab.log').open('xb') as log:ret=subprocess.run([r'C:\Program Files\MATLAB\R2025b\bin\matlab.exe','-batch',cmd],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    assert ret.returncode==0,'Read retainedMATLABlog; no badobjectsremoved'
    d=loadmat(out/'sem_masks.mat');assert d['valid'].all();ref=loadmat(ROOT/'validation/sem_reference.mat',variable_names=['truth_cells','truth_masks','opt_pitch']);scale=5000/ref['opt_pitch'].item();truth={};points={};rows=[]
    for i in range(36):
        mask=ref['truth_masks'][:,:,i].astype(bool);c,r=mask_center_radius(mask);truth[i+1]=core.measure_boundary_and_circles(ref['truth_cells'][:,:,i],c,r,coarse_mask=mask,sample_count=180,normal_half_width_px=3,polarity='auto');points[f'SEM_{i+1}']=truth[i+1].inflection_points_xy
    for k,e in enumerate([13,14,15]):
        for i in range(36):
            mask=d['masks'][:,:,i,k].astype(bool);c,r=mask_center_radius(mask);m=core.measure_boundary_and_circles(d['cells'][:,:,i,k],c,r,coarse_mask=mask,sample_count=144,normal_half_width_px=3,polarity='auto');t=truth[i+1];a,b=radial_signature(m),radial_signature(t)
            rows.append(dict(arm=arm,seed=seed,step=step,exposure=e,pillar=i+1,radial_nm=float(abs(a-b).mean()*scale),diameter_error_nm=float(2*abs(m.circles.lsc.radius-t.circles.lsc.radius)*scale),signed_diameter_nm=float(2*(m.circles.lsc.radius-t.circles.lsc.radius)*scale),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),MZC_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale)))
            points[f'{e}_{i+1}']=m.inflection_points_xy
    table=pd.DataFrame(rows);assert len(table)==108 and np.isfinite(table.select_dtypes('number')).all().all();table.to_csv(out/'measurements.csv',index=False);np.savez_compressed(out/'points.npz',**points);cols=['radial_nm','diameter_error_nm','signed_diameter_nm','centered_shape_nm','correlation','MZC_error_nm'];per=table.groupby('pillar')[cols].median();per.to_csv(out/'per_pillar.csv');summ=per.median().to_dict();save(out/'complete.json',dict(arm=arm,seed=seed,step=step,rows=108,summary=summ,checkpoint=record(cp),records=records,scale_nm_per_px=scale));print(tag,summ,flush=True)

def main():
    cfg=load(ROOT/'config/study.json')
    for seed in cfg['seeds']:
        for arm in cfg['arms']:
            for step in [0,512]:evaluate(arm,seed,step)
    save(ROOT/'results/real_complete.json',dict(runs=4,evaluations=8,SEM_rows=864,B_D_not_evaluated=True))
if __name__=='__main__':
    try:main()
    except BaseException:
        save(ROOT/f'results/sem_failure_{time.time_ns()}.json',dict(utc=now(),error=traceback.format_exc()));raise

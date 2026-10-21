"""Frozen real microscopy panel; explicit boundary coverage and SEM definitions."""
import sys,time,importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import cv2,torch
from scipy.ndimage import map_coordinates
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from model.network import boundary_guard
spec=importlib.util.spec_from_file_location('r128_verified_tiling',R124/'inference/tiling.py');tiling=importlib.util.module_from_spec(spec);spec.loader.exec_module(tiling)
# These R127 modules contain numerical routines only; none writes on import.
sys.path.append(str(R127/'scripts'))
from motion_reader_v3 import measure
ANGLE=np.arange(720)*2*np.pi/720;C=np.cos(ANGLE);S=np.sin(ANGLE)

def radial(image,center,radii):
    return map_coordinates(image.astype(float),np.array([center[1]+S[:,None]*radii,center[0]+C[:,None]*radii]),order=1,mode='nearest')

def pitches(centers):
    g=np.asarray(centers).reshape(2,2,2)
    return np.r_[np.linalg.norm(np.diff(g,axis=1),axis=2).ravel(),np.linalg.norm(np.diff(g,axis=0),axis=2).ravel()]

def crossing_radii(image,centers,plateaus=None,level=.5):
    # Same R127 native readout. The level is additionally reported at .3/.7.
    rr=np.arange(20,55.00001,.125);radii=[];valids=[];levels=[]
    for i,c in enumerate(centers):
        if plateaus is None:
            inside=np.median(radial(image,c,np.arange(3,16)),axis=1);outside=np.median(radial(image,c,np.arange(52,59)),axis=1)
        else:inside,outside=plateaus[i]
        p=radial(image,c,rr);den=outside-inside;u=(p-inside[:,None])/np.maximum(den[:,None],1e-8)
        hits=(u[:,:-1]<level)&(u[:,1:]>=level);idx=hits.argmax(1);j=np.arange(720)
        v=rr[idx]+.125*(level-u[j,idx])/np.maximum(u[j,idx+1]-u[j,idx],1e-8)
        valid=(hits.sum(1)==1)&(den>1/255)&np.isfinite(v)
        radii.append(v);valids.append(valid);levels.append((inside,outside))
    return np.asarray(radii),np.asarray(valids),levels

def bidirectional(a,b):
    f=measure(a,b);r=measure(b,a);cycle=float(np.hypot(f['dx']+r['dx'],f['dy']+r['dy'])) if f['accepted'] and r['accepted'] else None
    return dict(forward=f,reverse=r,cycle_error=cycle,valid=bool(cycle is not None and cycle<=.1))

def read_image(source):
    if sha(source['path'])!=source['sha256']:raise RuntimeError('Real source identity mismatch')
    raw=cv2.imread(source['path'],cv2.IMREAD_GRAYSCALE)
    if raw is None or raw.dtype!=np.uint8:raise ValueError('Frozen real panel requires exact8bit sources')
    return raw.astype(np.float32)/np.float32(255)

@torch.inference_mode()
def predict(model,raw):
    t=torch.from_numpy(raw)[None,None].to(next(model.parameters()).device)
    neural=tiling.tiled_forward(model,t,core=256,halo=model.required_halo)
    application,w=boundary_guard(t,neural,model.required_halo,16)
    return application[0,0].cpu().numpy(),neural[0,0].cpu().numpy(),w.cpu().numpy()

def sem_rows(raw,prediction,exposure):
    root=R127/'results/sem_native_v2'
    with np.load(root/'native_references.npz') as f:refs={k:f[k] for k in f.files}
    table=pd.read_csv(root/'native_SEM_objects.csv');centers=refs['optical_centers']
    mapping=loadmat(EXPS/'R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['global_index'])['global_index']
    rawr,rawvalid,levels=crossing_radii(raw,centers);pr,pvalid,_=crossing_radii(prediction,centers,levels)
    profile={}
    for level in [.3,.5,.7]:
        profile[level]=(crossing_radii(raw,centers,levels,level)[:2],crossing_radii(prediction,centers,levels,level)[:2])
    rows=[]
    for _,row in table.iterrows():
        pid=int(row.pillar);gy,gx=np.argwhere(mapping==pid)[0];idx=gy*6+gx;by,bx=(gy//2)*2,(gx//2)*2
        group=centers.reshape(6,6,2)[by:by+2,bx:bx+2].reshape(4,2);pitch=float(np.median(pitches(group)))
        inner,rim,outer=[refs[f'p{pid:02d}_{k}'] for k in ['inner','rim','outer']]
        # Frozen population depends on source and SEM only, never candidates.
        valid=np.isfinite(inner)&np.isfinite(outer)&(inner<rim)&(rim<outer)&rawvalid[idx]
        fixed=int(valid.sum());lost=int((valid&~pvalid[idx]).sum())
        ratio=lambda v,p:float(2*np.sqrt(np.mean(v[valid]**2))/p)
        lo,mid,hi=[ratio(v,row.native_pitch) for v in [inner,rim,outer]]
        rv=ratio(rawr[idx],pitch);pv=ratio(pr[idx],pitch) if fixed and lost==0 else None
        c=centers[idx];clearance=float(min(c[0],c[1],raw.shape[1]-1-c[0],raw.shape[0]-1-c[1])-58)
        result=dict(exposure=exposure,pillar=pid,SEM_file=int(row.file),fixed_source_SEM_rays=fixed,candidate_invalid_fixed_rays=lost,measurable=bool(pv is not None),context_stratum='all_readout_pixels_fully_neural' if clearance>=80 else 'includes_boundary_retention',minimum_plateau_context=clearance,Raw_diameter_pitch_ratio=rv,candidate_diameter_pitch_ratio=pv,SEM_inner_ratio=lo,SEM_rim_ratio=mid,SEM_outer_ratio=hi,physical_edge_truth=False)
        if pv is not None:
            possible=np.array([lo,hi,np.clip(pv,lo,hi),np.clip(rv,lo,hi)]);change=np.abs(pv-possible)-np.abs(rv-possible)
            lower,upper=float(change.min()),float(change.max())
            result.update(change_vs_Raw_ratio=pv-rv,paired_error_change_lower=lower,paired_error_change_upper=upper,direction='improves' if upper<-1e-12 else 'worsens' if lower>1e-12 else 'unresolved_or_equal')
        else:result['direction']='unmeasurable'
        for level,((r,rvv),(p,pvv)) in profile.items():
            mask=valid&rvv[idx]
            result[f'level_{level}_fixed_rays']=int(mask.sum())
            result[f'level_{level}_median_radius_change_px']=float(np.median(p[idx,mask]-r[idx,mask])) if mask.any() and pvv[idx,mask].all() else None
        rows.append(result)
    if len(rows)!=36:raise ValueError('SEM population must retain all36 objects')
    return rows

@torch.inference_mode()
def evaluate(model,out,checkpoint_record,neutral=False):
    out=Path(out)
    if (out/'verification.json').exists():
        saved=load(out/'verification.json')
        if saved['checkpoint']!=checkpoint_record:raise RuntimeError('Real evaluation binding mismatch')
        for p,h in saved['output_sha256'].items():
            if sha(p)!=h:raise RuntimeError('Changed evaluation output')
        return saved
    out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();model.eval()
    panel=load(R125/'results/real_panel_v2/frozen_panel.json');images=[];rows=[];motions=[]
    def one(raw,path,source):
        path.mkdir(parents=True,exist_ok=False)
        if neutral:
            # The exact-zero final layer has been verified for each checkpoint.
            pred=raw.copy();neural=raw.copy()
            y,x=np.mgrid[:raw.shape[0],:raw.shape[1]];distance=np.minimum(np.minimum(x,raw.shape[1]-1-x),np.minimum(y,raw.shape[0]-1-y));w=np.clip((distance-model.required_halo)/16,0,1)
        else:pred,neural,w=predict(model,raw)
        np.savez_compressed(path/'output_float.npz',output=pred,neural_output=neural)
        cv2.imwrite(str(path/'output.png'),np.rint(pred*255).clip(0,255).astype(np.uint8))
        change=(pred-raw)*255
        rec=dict(source=source,shape=list(raw.shape),output=record(path/'output_float.npz'),Raw_retained_fraction=float(np.mean(w==0)),transition_fraction=float(np.mean((w>0)&(w<1))),fully_neural_fraction=float(np.mean(w==1)),mean_absolute_change_gray=float(np.mean(np.abs(change))),maximum_absolute_change_gray=float(np.max(np.abs(change))))
        images.append(rec)
        atomic(out/'progress.json',dict(images=len(images),motion_pairs=len(motions),seconds=time.perf_counter()-start))
        return pred
    for item in panel['full_images']:
        raw=read_image(item['source']);pred=one(raw,out/'full_images'/item['name'],item['source'])
        if item['name'].startswith('sem_optical_exposure'):rows+=sem_rows(raw,pred,int(item['name'].split('exposure')[-1]))
    for item in panel['motion_pairs']:
        rawpair=[];pair=[]
        for frame,source in enumerate(item['sources']):
            raw=read_image(source);rawpair.append(raw);pair.append(one(raw,out/'motion'/item['sequence']/f'frame{frame}',source))
        # Same global80-pixel border exclusion for Raw and candidate, not a
        # candidate-selected ROI. Uncropped results are retained separately.
        fullraw=bidirectional(*[a.astype(float) for a in rawpair]);fullpred=fullraw if neutral else bidirectional(*[a.astype(float) for a in pair])
        a=bidirectional(*[v[80:-80,80:-80].astype(float) for v in rawpair]);b=a if neutral else bidirectional(*[v[80:-80,80:-80].astype(float) for v in pair])
        change=float(np.hypot(a['forward']['dx']-b['forward']['dx'],a['forward']['dy']-b['forward']['dy'])) if a['valid'] and b['valid'] else None
        motions.append(dict(sequence=item['sequence'],Raw=a,candidate=b,full_Raw=fullraw,full_candidate=fullpred,common_global_border_exclusion=80,change_vs_Raw_px=change,consistent_with_Raw=bool(change is not None and change<=.5),absolute_physical_truth=False))
        print(json.dumps(dict(real_sequence=item['sequence'],change_vs_Raw_px=change,seconds=time.perf_counter()-start)),flush=True)
    # One fixed diagnostic location; store each update's effect, without using
    # it to choose weights or claim the learned filters have physical meaning.
    item=next(x for x in panel['full_images'] if x['name']=='5x_dense')
    raw=read_image(item['source']);t=torch.from_numpy(raw[128:384,128:384])[None,None].to(next(model.parameters()).device)
    detail=model.forward_details(t,trace=True);trace={'source':raw[192:320,192:320]}
    for i,d in enumerate(detail.traces):
        trace[f'after_{i+1}']=d['native_after'][0,0,64:192,64:192].cpu().numpy()
        trace[f'correction_{i+1}']=torch.nn.functional.avg_pool2d(d['learned_correction'],4)[0,0,64:192,64:192].cpu().numpy()
    np.savez_compressed(out/'four_stage_trace.npz',**trace)
    pd.DataFrame(rows).to_csv(out/'SEM_measurements.csv',index=False);save(out/'motion_measurements.json',motions);save(out/'image_coverage.json',images)
    summary=dict(checkpoint=checkpoint_record,completed=True,full_images=6,full_motion_frames=12,motion_pairs=6,SEM_objects_per_exposure=36,SEM_rows=len(rows),SEM_unmeasurable=sum(not r['measurable'] for r in rows),SEM_direction_counts=dict(pd.Series([r['direction'] for r in rows]).value_counts().astype(int).to_dict()),motion_consistent=sum(r['consistent_with_Raw'] for r in motions),maximum_motion_change_vs_Raw_px=max((r['change_vs_Raw_px'] for r in motions if r['change_vs_Raw_px'] is not None),default=None),existing_development_sources=True,unseen_real_confirmation=False,real_calibration_qualified=False,neutral_Raw_equivalence_used=neutral,seconds=time.perf_counter()-start)
    summary['output_sha256']={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='progress.json'}
    save(out/'verification.json',summary)
    return summary

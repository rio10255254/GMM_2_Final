"""Known-geometry factorial diagnosis with physical sampling and frozen E42."""
from pathlib import Path
from datetime import datetime,timezone
from functools import lru_cache
import hashlib,json,sys
import cv2,numpy as np,pandas as pd,torch
from scipy.ndimage import map_coordinates

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load
from model.network import continuous_width
from model.ops import warp_local
SIZE=640;FACTOR=8;CENTER=(SIZE-1)/2;ANGLES=720
T=np.arange(-12,12.00001,.125,dtype=np.float64)
METHODS=['Raw','position_only','geometry','full','width_only','no_shift','oracle_geometry_width']

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)

def cases():
    specs=[]
    for shape in ['line','circle32','circle48']:
        for polarity in [-1,1]:
            for sensor in ['clean_float','noisy_uint8']:
                for sigma in [0.,.5,1.,1.5,2.5,4.]:specs.append(dict(shape=shape,polarity=polarity,sensor=sensor,group='blur',value=sigma,sigma=sigma,gain=.6,dx=0.,dy=0.))
                for gain in [.15,.3,.6,1.,1.2]:specs.append(dict(shape=shape,polarity=polarity,sensor=sensor,group='gain',value=gain,sigma=1.5,gain=gain,dx=0.,dy=0.))
                for dx,dy in [(-1.,0.),(-.5,0.),(-.125,0.),(0.,0.),(.125,0.),(.5,0.),(1.,0.),(0.,.5),(.5,.5)]:
                    specs.append(dict(shape=shape,polarity=polarity,sensor=sensor,group='motion',value=dx,sigma=1.5,gain=.6,dx=dx,dy=dy))
    return [dict(case_id=i,**row) for i,row in enumerate(specs)]

def geometry(shape,dx=0.,dy=0.,high=False):
    n=SIZE*FACTOR if high else SIZE
    axis=(np.arange(n,dtype=np.float32)+.5)/(FACTOR if high else 1)-.5
    x=axis[None,:]-(CENTER+dx);y=axis[:,None]-(CENTER+dy)
    if shape=='line':
        sdf=np.broadcast_to(-x,(n,n)).copy()
        if high:return sdf
        return sdf,np.ones_like(sdf),np.zeros_like(sdf)
    radius=float(shape.replace('circle',''));rad=np.sqrt(x*x+y*y)
    sdf=radius-rad
    if high:return sdf
    return sdf,np.broadcast_to(x,(n,n))/np.maximum(rad,1e-6),np.broadcast_to(y,(n,n))/np.maximum(rad,1e-6)

@lru_cache(maxsize=48)
def physical(shape,sigma,dx,dy):
    sdf=geometry(shape,dx,dy,high=True)
    occupancy=1/(1+np.exp(np.clip(-sdf/.7,-40,40)))
    target=cv2.resize(occupancy,(SIZE,SIZE),interpolation=cv2.INTER_AREA)
    if sigma:
        blurred=cv2.GaussianBlur(occupancy,(0,0),sigmaX=FACTOR*sigma,sigmaY=FACTOR*sigma,borderType=cv2.BORDER_REFLECT_101)
        source=cv2.resize(blurred,(SIZE,SIZE),interpolation=cv2.INTER_AREA)
    else:source=target.copy()
    return source,target

def inputs(row):
    source,target=physical(row['shape'],row['sigma'],row['dx'],row['dy'])
    inside,outside=((.15,.75) if row['polarity']==-1 else (.75,.15))
    inside*=row['gain'];outside*=row['gain']
    raw=(outside+(inside-outside)*source).astype(np.float32)
    reference=(outside+(inside-outside)*target).astype(np.float32)
    if row['sensor']=='noisy_uint8':
        # Same sensor pattern within each geometry/polarity block, across factors.
        seed=202609061+['line','circle32','circle48'].index(row['shape'])*31+(row['polarity']+1)
        rng=np.random.default_rng(seed)
        raw=np.rint(np.clip(raw+rng.normal(0,1.5/255,raw.shape),0,1)*255).astype(np.float32)/255
    return raw,reference,inside,outside

def samples(shape,dx=0.,dy=0.):
    if shape=='line':
        px=np.full(ANGLES,CENTER+dx);py=CENTER+dy+np.linspace(-64,64,ANGLES)
        nx=np.ones(ANGLES);ny=np.zeros(ANGLES)
    else:
        theta=np.arange(ANGLES)*2*np.pi/ANGLES;nx=np.cos(theta);ny=np.sin(theta)
        r=float(shape.replace('circle',''));px=CENTER+dx+r*nx;py=CENTER+dy+r*ny
    coordinates=np.array([py[:,None]+ny[:,None]*T,px[:,None]+nx[:,None]*T])
    return coordinates,nx,ny

def crossings(u,level):
    # Multiple crossings are failures, not cherry-picked using true position.
    hits=(u[:,:-1]<level)&(u[:,1:]>=level)
    counts=hits.sum(1);index=hits.argmax(1);rows=np.arange(len(u))
    left=u[rows,index];right=u[rows,index+1]
    value=T[index]+(level-left)/np.maximum(right-left,1e-12)*(T[1]-T[0])
    valid=(counts==1)&(u[:,0]<level)&(u[:,-1]>level)&np.isfinite(value)
    return np.where(valid,value,np.nan),valid,counts

def measure(image,coords,inside,outside):
    profiles=map_coordinates(image,coords,order=1,mode='nearest')
    u=(profiles-inside)/(outside-inside)
    mid,valid,count=crossings(u,.5);lo,lv,_=crossings(u,.1);hi,hv,_=crossings(u,.9)
    width=np.where(lv&hv&(hi>lo),hi-lo,np.nan)
    return mid,valid,count,width

def calibrate():
    records=[]
    for shape in ['line','circle32','circle48']:
        for polarity in [-1,1]:
            row=dict(shape=shape,sigma=0.,dx=0.,dy=0.,polarity=polarity,sensor='clean_float',gain=.6)
            image,truth,inside,outside=inputs(row);coords,nx,ny=samples(shape)
            pos,valid,_,width=measure(image,coords,inside,outside)
            assert valid.all()
            assert np.max(np.abs(pos))<.04
            moved=dict(row,dx=.5);mi,_,_,_=inputs(moved)
            mp,mvalid,_,_=measure(mi,coords,inside,outside)
            if shape=='line':recovered=np.nanmedian(mp-pos)
            else:
                design=np.stack([np.ones(ANGLES),nx,ny],1)
                recovered=np.linalg.lstsq(design[mvalid],(mp-pos)[mvalid],rcond=None)[0][1]
            assert abs(recovered-.5)<.03
            flat=np.full_like(image,(inside+outside)/2)
            _,flat_valid,_,_=measure(flat,coords,inside,outside);assert not flat_valid.any()
            records.append({'shape':shape,'polarity':polarity,'zero_geometry_max_native_readout_bias_px':float(np.abs(pos).max()),'known_half_pixel_shift_recovered_px':float(recovered),'flat_profiles_rejected':ANGLES})
    # Multiple-boundary profile must be rejected even if one crossing is near truth.
    fixture=np.repeat((.5+.4*np.sin(T))[None],ANGLES,axis=0)
    _,valid,count=crossings(fixture,.5);assert not valid.any() and (count>1).all()
    save('calibration.json',{'fixtures':records,'multi_crossing_profiles_rejected':ANGLES,'calibration_passed':True})

@torch.inference_mode()
def outputs(model,raw,row):
    x=torch.from_numpy(raw)[None,None].cuda();d=model.forward_details(x)
    position=warp_local(x,d.flow)
    width=continuous_width(x,d.width_gain,d.sdf,d.normals,21)
    sdf,nx,ny=geometry(row['shape'],row['dx'],row['dy'])
    # R119 uses photometric distance sign; dark foreground has outward normals.
    ts=torch.from_numpy(sdf*row['polarity'])[None,None].cuda()
    normal=torch.from_numpy(np.stack([-nx*row['polarity'],-ny*row['polarity']]))[None].cuda()
    oracle=continuous_width(x,d.width_gain,ts,normal,21)
    result={'Raw':x,'position_only':position,'geometry':d.geometry_output.clamp(0,1),'full':d.output,
            'width_only':width.clamp(0,1),'no_shift':(width+d.detail).clamp(0,1),'oracle_geometry_width':oracle.clamp(0,1)}
    return {k:v[0,0].cpu().numpy() for k,v in result.items()}

def main():
    torch.set_num_threads(4);cv2.setNumThreads(1)
    previous=ROOT/'analysis/training_position_diagnosis_20260906/input_snapshot.json'
    snapshot=json.loads(previous.read_text());assert all(sha(p)==digest for p,digest in snapshot.items())
    p=ROOT/'reports/R119_TRAINING_POSITION_DIAGNOSIS.md';snapshot[str(p)]=sha(p)
    save('input_snapshot.json',snapshot)
    specs=cases();save('protocol.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'question':'When blur, brightness or true object position changes separately, which frozen model operation introduces unnecessary local edge displacement?',
        'cases':specs,'canvas_px':SIZE,'supersampling_factor':FACTOR,'reference_transition_scale_px':.7,
        'profiles_per_case':ANGLES,'profile_coordinates_px':[-12,12,.125],
        'methods':METHODS,'model':'R119 B E42 frozen','data_scope':'New deterministic diagnostic fixtures, no training or confirmation population',
        'factors':'blur sigma; multiplicative illumination; physical object translation applied before sampling to BOTH reference and observation',
        'sensor_modes':'Primary clean float; robustness block with fixed 1.5-gray sensor noise plus uint8 quantization (a combined stress condition, not a noise-only causal comparison)',
        'readout':'Unique half-contrast normal-profile crossing, compared with the correspondingly moved sampled reference. Multiple crossings and missing brackets are failures. Width uses 10%-90% crossings.',
        'physical_motion_contract':'Preserve true motion; never train or score the model to undo real object displacement. Reference moves with object. Error is relative to each shifted reference; no second displacement subtraction.',
        'primary_comparisons':'Use common valid profiles for all seven variants within a case; keep individual and common validity counts. No pooled claim if clean common validity <95%.',
        'diagnostic_triggers':{'unnecessary_position_correction':'Raw median absolute boundary error <=0.04px, but position-only error rises by >=0.05px',
                               'oracle_width_motion':'Known-geometry width-only adds >=0.05px median boundary error over Raw',
                               'nuisance_bias_change':'Signed boundary bias changes by >=0.10px from its factor baseline with fixed true geometry'},
        'decision_rule':'If known-geometry width-only is stable but position-only fails clean zero-bias cases, prioritize action prediction and direct displacement supervision; if the known-geometry width operator moves correct boundaries, repair that operator before training. Preserve polarity/blur/brightness exceptions. No automatic promotion.',
        'limitations':['Profiles are a controlled half-contrast geometry readout, not the ACM or LSC measurements.','No real texture in these fixtures.','One model, three simple shape geometries; not universal validation.'],
        'payload_budget_gib':2,'no_training':True,'no_confirmation_access':True})
    calibrate();(OUT/'cases').mkdir(exist_ok=False)
    model=load(ROOT/'runs/formal_B_s1195001/weights/epoch_042.pth','cuda');all_rows=[]
    for row in specs:
        raw,reference,inside,outside=inputs(row);result=outputs(model,raw,row)
        coords,nx,ny=samples(row['shape'],row['dx'],row['dy'])
        target_pos,target_valid,_,target_width=measure(reference,coords,inside,outside)
        measured={k:measure(image,coords,inside,outside) for k,image in result.items()}
        common=target_valid.copy()
        for value in measured.values():common &=value[1]
        profile_rows={};record=[]
        for name,(pos,valid,count,width) in measured.items():
            error=pos-target_pos
            if common.any():
                bias=float(np.median(error[common]));mae=float(np.mean(np.abs(error[common])))
                width_ok=common&np.isfinite(width)&np.isfinite(target_width)
                width_value=float(np.median(width[width_ok])) if width_ok.any() else None
                if row['shape']!='line' and common.sum()>=20:
                    design=np.stack([np.ones(ANGLES),nx,ny],1)
                    fitted=np.linalg.lstsq(design[common],error[common],rcond=None)[0]
                    center_x,center_y=float(fitted[1]),float(fitted[2])
                else:center_x=center_y=None
            else:bias=mae=width_value=center_x=center_y=None
            rec={**row,'method':name,'valid_profiles':int(valid.sum()),'common_valid_profiles':int(common.sum()),
                 'multiple_crossing_profiles':int((count>1).sum()),'signed_bias_px':bias,'boundary_mae_px':mae,
                 'median_transition_width_px':width_value,'width_valid_common_profiles':int((common&np.isfinite(width)&np.isfinite(target_width)).sum()),
                 'center_error_x_px':center_x,'center_error_y_px':center_y}
            all_rows.append(rec);record.append(rec)
            profile_rows[name+'_position_error']=error;profile_rows[name+'_valid']=valid;profile_rows[name+'_width']=width
        folder=OUT/'cases'/f"{row['case_id']:03d}";folder.mkdir()
        np.savez_compressed(folder/'images.npz',reference=reference,**result)
        np.savez_compressed(folder/'profiles.npz',target_position=target_pos,target_width=target_width,common_valid=common,**profile_rows)
        with (folder/'rows.json').open('x') as f:json.dump(record,f,indent=2,allow_nan=False)
        print(json.dumps({'case':row['case_id'],'total':len(specs),'shape':row['shape'],'factor':row['group'],'common_valid':int(common.sum())}),flush=True)
    frame=pd.DataFrame(all_rows);frame.to_csv(OUT/'measurements.csv',index=False,mode='x')
    assert all(sha(p)==digest for p,digest in snapshot.items())
    payload=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file());assert payload<2*2**30
    save('execution_record.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),'cases':len(specs),'measurement_rows':len(frame),'protected_files_unchanged':len(snapshot),'optimizer_steps':0,'payload_bytes':payload,'code_sha256':sha(__file__)})

if __name__=='__main__':main()

"""One-change frozen-renderer interventions on the pre-R109 Raw references.

In-memory forward variants are diagnostic interventions, not deployable models.
All source files and weights are unchanged. No network optimization is run.
"""
from __future__ import annotations
import inspect
import json
import hashlib
from pathlib import Path
import sys
import textwrap
import types
import cv2
import numpy as np
import torch
import torch.nn.functional as F

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import model.r117_model as mm
RAW_ROOT=ROOT.parent/'R100_CausalOperatorScratch/data/live_validation'
WEIGHT=ROOT/'runs/r117_formal_scratch_20260905_004452/weights/epoch_042.pth'

def write(path,image):
    path.parent.mkdir(parents=True,exist_ok=True)
    ok,encoded=cv2.imencode('.png',image)
    if not ok:raise ValueError(path)
    encoded.tofile(str(path))

def variant_forward(model,mode):
    source=textwrap.dedent(inspect.getsource(mm.R117Model._forward_aligned))
    if mode=='continuous_width':
        old='transformed = transformed + identity_width.to(transformed.dtype) * (geometry_anchor - transformed).detach()'
        new='transformed = geometry_anchor + transformed - (midpoint + half * unit)'
    elif mode=='no_projection':
        old='center_locked = lock * odd + (1.0 - lock) * pre';new='center_locked = pre'
    elif mode=='normal_sign_consistent':
        old='nx, ny = smooth_gx / magnitude, smooth_gy / magnitude'
        new='''nx, ny = smooth_gx / magnitude, smooth_gy / magnitude
    sx, sy = gradients(sdf.detach())
    orientation = torch.where(nx*sx + ny*sy < 0, -1.0, 1.0)
    nx, ny = nx*orientation, ny*orientation'''
    else:raise ValueError(mode)
    if source.count(old)!=1:raise RuntimeError(f'expected unique source expression for {mode}')
    source=source.replace(old,new)
    namespace={};exec(compile(source,f'<diagnostic_{mode}>','exec'),mm.__dict__,namespace)
    return types.MethodType(namespace['_forward_aligned'],model)

def profile_metrics(image,raw):
    # Center from Raw only; no registration or favorable per-method selection.
    u8=np.rint(np.clip(raw,0,1)*255).astype(np.uint8)
    _,bw=cv2.threshold(u8,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
    n,_,stats,centers=cv2.connectedComponentsWithStats(bw)
    choices=[i for i in range(1,n) if stats[i,cv2.CC_STAT_AREA]>100]
    h,w=raw.shape
    candidate=min(choices,key=lambda i:np.linalg.norm(centers[i]-[w/2,h/2]))
    cx,cy=centers[candidate];r0=np.sqrt(stats[candidate,cv2.CC_STAT_AREA]/np.pi)
    radius=np.linspace(0,r0+12,300,dtype=np.float32)
    angle=np.linspace(0,2*np.pi,128,endpoint=False,dtype=np.float32)
    sx=(cx+np.cos(angle[:,None])*radius[None]).astype(np.float32)
    sy=(cy+np.sin(angle[:,None])*radius[None]).astype(np.float32)
    vals=cv2.remap(image.astype(np.float32),sx,sy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
    profile=np.median(vals,axis=0)
    selected=(radius>max(0,r0-8))&(radius<r0+8)
    diffs=np.diff(profile[selected])
    reversal=np.maximum(-diffs,0).sum()*255
    return {'center_from_raw':[float(cx),float(cy)],'raw_radius_px':float(r0),
            'radial_reversal_gray':float(reversal),'radii_px':radius.tolist(),'profile_gray':(profile*255).tolist()}

def run():
    torch.set_num_threads(4);cv2.setNumThreads(1)
    saved=torch.load(WEIGHT,map_location='cpu',weights_only=False)
    model=mm.build_model().cuda().eval();model.load_state_dict(saved['model']);model.requires_grad_(False)
    original=model._forward_aligned
    results=[];profiles={}
    for path in sorted(RAW_ROOT.glob('*.bmp')):
        raw=cv2.imdecode(np.fromfile(str(path),np.uint8),0).astype(np.float32)/255
        x=torch.from_numpy(raw)[None,None].cuda()
        arrays={'Raw':raw};rows={}
        with torch.inference_mode():
            details=model.forward_details(x)
            arrays['R117']=details.output[0,0].cpu().numpy()
            arrays['geometry_anchor']=details.geometry_anchor[0,0].cpu().numpy()
            arrays['width_proposal']=details.width_proposal[0,0].cpu().numpy()
            sdf,nx,ny=details.predicted_sdf_px,details.normal_x,details.normal_y
            flows=torch.cat((-sdf*nx,-sdf*ny),1)[:,None]+x.new_tensor([-8,8]).view(1,2,1,1,1)*torch.cat((nx,ny),1)[:,None]
            endpoints=mm.warp_many(details.geometry_anchor,flows)[:,:,0]
            lo,hi=endpoints.amin(1,keepdim=True),endpoints.amax(1,keepdim=True)
            active=details.width_gate>0.1
            out_of_range=((details.geometry_anchor<lo)|(details.geometry_anchor>hi))&active
            row={'image':path.name,'active_pixels':int(active.sum()),
                 'active_anchor_outside_endpoint_range_fraction':float(out_of_range.sum()/active.sum().clamp_min(1))}
            for mode in ['continuous_width','no_projection','normal_sign_consistent']:
                model._forward_aligned=variant_forward(model,mode)
                try:arrays[mode]=model(x)[0,0].cpu().numpy()
                finally:model._forward_aligned=original
        columns=[]
        for name,array in arrays.items():
            if not np.isfinite(array).all():raise FloatingPointError(name)
            rows[name]={'change_from_raw_gray':float(np.abs(array-raw).mean()*255),
                        'min':float(array.min()),'max':float(array.max())}
            if path.stem=='pillar_center9_50x_raw':profiles[name]=profile_metrics(array,raw)
            u8=np.rint(np.clip(array,0,1)*255).astype(np.uint8)
            write(HERE/'render_mechanisms'/path.stem/(name+'.png'),u8)
            panel=np.full((288,256,3),245,np.uint8)
            panel[32:]=cv2.cvtColor(cv2.resize(u8,(256,256),interpolation=cv2.INTER_NEAREST if raw.shape[0]<256 else cv2.INTER_AREA),cv2.COLOR_GRAY2BGR)
            cv2.putText(panel,name,(6,21),cv2.FONT_HERSHEY_SIMPLEX,.44,(20,20,20),1,cv2.LINE_AA)
            columns.append(panel)
        write(HERE/'render_mechanisms'/f'{path.stem}_comparison.png',np.concatenate(columns,axis=1))
        results.append({**row,'variants':rows})
    payload={'status':'complete','checkpoint_sha256':hashlib.sha256(WEIGHT.read_bytes()).hexdigest(),
             'rows':results,'pillar_profiles':profiles,
             'limits':'Frozen-path interventions show sensitivity, not results of retraining. Radial reversal is a diagnostic of a pillar crop, not a circle-shape correctness criterion.'}
    (HERE/'render_mechanism_results.json').write_text(json.dumps(payload,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'rows':results,'profile_reversals':{k:v['radial_reversal_gray'] for k,v in profiles.items()}},indent=2))

if __name__=='__main__':run()

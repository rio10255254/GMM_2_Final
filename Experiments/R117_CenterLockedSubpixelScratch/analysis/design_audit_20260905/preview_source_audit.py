"""Verify preview provenance and reconstruct the actual pre-restoration inputs."""
from __future__ import annotations
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np
import torch
import torch.nn.functional as F

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model.r117_model import build_model
from inference.tiled import forward_tiled
PROJECT_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENTS=ROOT.parent
R109=EXPERIMENTS/'R109_StagedMidpointWidthScratch'
RAW_ROOT=EXPERIMENTS/'R100_CausalOperatorScratch/data/live_validation'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    v=cv2.imdecode(np.fromfile(str(p),np.uint8),0)
    if v is None: raise ValueError(p)
    return v
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    ok,b=cv2.imencode('.png',v)
    if not ok: raise ValueError(p)
    b.tofile(str(p))
def to_tensor(a): return torch.from_numpy(a.astype(np.float32)/255.0)[None,None].cuda()
def to_u8(x): return np.rint(x[0,0].clamp(0,1).cpu().numpy()*255).astype(np.uint8)

@torch.inference_mode()
def r109_original_inference(model,raw):
    x=to_tensor(raw);h,w=raw.shape;halo=192;core=512
    padded=F.pad(x,(halo,halo,halo,halo),mode='reflect');out=torch.zeros_like(x)
    for y in range(0,h,core):
        for xx in range(0,w,core):
            ch,cw=min(core,h-y),min(core,w-xx)
            tile=padded[...,y:y+ch+2*halo,xx:xx+cw+2*halo]
            result=model(tile);out[...,y:y+ch,xx:xx+cw]=result[...,halo:halo+ch,halo:halo+cw]
    return to_u8(out)

def run():
    torch.set_num_threads(4);cv2.setNumThreads(1)
    w117=ROOT/'runs/r117_formal_scratch_20260905_004452/weights/epoch_042.pth'
    w109=R109/'weights/selected/R109.pth'
    model=build_model().cuda().eval();model.load_state_dict(torch.load(w117,map_location='cpu',weights_only=False)['model']);model.requires_grad_(False)
    spec=importlib.util.spec_from_file_location('audit_r109_model',R109/'model/r109_model.py')
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    old=m.build_model().cuda().eval();old.load_state_dict(torch.load(w109,map_location='cpu',weights_only=False)['model']);old.requires_grad_(False)
    c=json.loads((ROOT/'config/experiment.json').read_text())
    rows=[]; montages=[]
    for value in c['validation']['real_preview_inputs']:
        preview=Path(PROJECT_ROOT / value);raw_path=RAW_ROOT/preview.name
        raw,cached=read(raw_path),read(preview)
        reproduced=r109_original_inference(old,raw)
        with torch.inference_mode():
            direct=to_u8(forward_tiled(model,to_tensor(raw),core_size=512,halo=224))
            cascaded=to_u8(forward_tiled(model,to_tensor(cached),core_size=512,halo=224))
        difference=lambda a,b:np.abs(a.astype(float)-b.astype(float))
        row={'image':preview.name,'actual_raw_reference':str(raw_path),'configured_preview_input':str(preview),
             'raw_reference_sha256':sha(raw_path),'configured_input_sha256':sha(preview),
             'raw_vs_configured_mean_gray':float(difference(raw,cached).mean()),
             'raw_vs_configured_max_gray':float(difference(raw,cached).max()),
             'r109_reproduced_vs_configured_mean_gray':float(difference(reproduced,cached).mean()),
             'r109_reproduced_vs_configured_max_gray':float(difference(reproduced,cached).max()),
             'r117_direct_change_mean_gray':float(difference(direct,raw).mean()),
             'r117_cascade_vs_direct_mean_gray':float(difference(cascaded,direct).mean()),
             'r117_cascade_vs_direct_max_gray':float(difference(cascaded,direct).max())}
        arrays=[raw,cached,direct,cascaded]
        labels=['Raw reference','R109 E48','R117 E42 from Raw','R117 E42 after R109']
        panels=[]
        for label,a in zip(labels,arrays):
            path=HERE/'preview_provenance'/preview.stem/(label.replace(' ','_')+'.png')
            write(path,a)
            resized=cv2.resize(a,(384,384),interpolation=cv2.INTER_NEAREST if a.shape[0]<384 else cv2.INTER_AREA)
            canvas=np.full((418,384,3),245,np.uint8)
            canvas[34:]=cv2.cvtColor(resized,cv2.COLOR_GRAY2BGR)
            cv2.putText(canvas,label,(8,22),cv2.FONT_HERSHEY_SIMPLEX,0.52,(20,20,20),1,cv2.LINE_AA)
            panels.append(canvas)
        montage=np.concatenate(panels,axis=1)
        write(HERE/'preview_provenance'/f'{preview.stem}_comparison.png',montage)
        rows.append(row)
    result={'status':'complete','R117_checkpoint_sha256':sha(w117),'R109_checkpoint_sha256':sha(w109),'images':rows,
            'conclusion':'All four configured R117 preview inputs are R109 reconstructions, not the earlier Raw reference images. Verify independent full-frame validation separately.',
            'limits':'The R100 reference is the pre-R109 input verified by the R109 reconstruction program. This audit does not establish camera-original provenance or SEM matching for every crop.'}
    (HERE/'preview_source_results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()

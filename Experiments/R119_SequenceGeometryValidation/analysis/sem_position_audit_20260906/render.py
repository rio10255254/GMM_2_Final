"""Frozen cross-exposure path diagnosis. New outputs only; no training."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys
import cv2
import numpy as np
import torch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))
from inference.run import load, read
from model.network import continuous_width
PROJECT_ROOT = Path(__file__).resolve().parents[4]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()

def save_json(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)

def prepare():
    source = ROOT.parent / 'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'
    old = json.loads((ROOT/'analysis/causal_audit_20260905/audit_results.json').read_text())
    protected = set(old['protected_before_after_sha256'])
    for directory in [ROOT/'model', ROOT/'training', ROOT/'inference', ROOT/'reports', ROOT/'analysis/causal_audit_20260905']:
        protected.update(str(p) for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    base = ROOT.parent/'R118_PhysicalCoordinateRepairScratch'
    for rel in ['AGENTS.md','NEXT_STEPS.md','reports/next_design_plan.json','reports/next_design_assets.json','reports/R118_EXECUTION_HANDOFF.md','results/README.md']:
        protected.add(str(base/rel))
    for p in (ROOT/'results/formal_sem').rglob('*'):
        if p.is_file(): protected.add(str(p))
    protected.update(str(source/f'{e}.bmp') for e in range(13,25))
    for p in sorted(protected):
        if not Path(p).is_file(): raise FileNotFoundError(p)
    snapshot = {p:sha(p) for p in sorted(protected)}
    for p,digest in old['protected_before_after_sha256'].items():
        if snapshot[p] != digest: raise RuntimeError('Existing causal-audit evidence changed: '+p)
    save_json(OUT/'input_snapshot.json', snapshot)
    save_json(OUT/'protocol.json', {
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'question':'Does the frozen R119 E42 normal-position path cause contour expansion across all twelve existing SEM-linked exposures?',
        'checkpoint':str(ROOT/'runs/formal_B_s1195001/weights/epoch_042.pth'),
        'exposures':list(range(13,25)), 'pillars':36,
        'experimental_unit':'36 existing pillars, repeated across 12 exposures; one sample and one model, not 432 independent samples',
        'methods':['Raw','base','no_shift','attenuation'],
        'interventions':{'no_shift':'Reuse the identical geometry, normals, width-gain and additive detail tensors; replace only the input warp by identity, then recompute width rendering on that input.',
                        'attenuation':'One scalar per exposure, chosen from [0,1] to match whole-image mean absolute uint8 correction of no_shift. Uses no SEM truth or contour result. Report per-pillar amplitude mismatch.'},
        'measurement':'Exact existing ACM helper functions, saved SEM truth masks, mapping, centers, 104px cells, 200 iterations, smoothing 1, seed radius 40, support 45; translation-only contour comparison.',
        'primary':'Paired boundary-distance change no_shift minus base, within each pillar/exposure; report every exposure and within-pillar median across exposures.',
        'secondary':['signed mask area vs SEM','signed area vs Raw','boundary HD95','per-pillar wins/ties/losses','comparison to equal-total-amplitude attenuation'],
        'detail_scope':'Additive detail tensor kept exactly; fixed SEM-interior image-band differences are observational diagnostics, not proof of recovery of real texture without a corresponding sharp intensity reference.',
        'decision':'Cross-exposure support requires a negative median paired boundary effect in every exposure, a negative median within-pillar effect, and majority pillar improvement. Exceptions and control mismatches remain explicit; no automatic training or promotion.',
        'forbidden':['training','confirmation predictions or image access','changing historical evidence, receipts or protection hashes','selecting a new checkpoint'],
        'outputs':['48 full images','1728 pillar/method/exposure rows including any failures','864 exact Raw/base mask parity checks','paired exposure and pillar summaries','all-exposure visual overview','new report'],
    })
    print(json.dumps({'prepared':True,'protected_files':len(snapshot),'input_snapshot_sha256':sha(OUT/'input_snapshot.json')}),flush=True)

@torch.inference_mode()
def render_pair(model,x):
    height,width=x.shape[-2:];halo=model.minimum_halo_px;core=512
    outputs={k:torch.empty_like(x,dtype=torch.float32) for k in ['base','no_shift','detail']}
    for y in range(0,height,core):
        for z in range(0,width,core):
            y1,z1=min(y+core,height),min(z+core,width)
            sy,sz=max(0,y-halo),max(0,z-halo);ey,ez=min(height,y1+halo),min(width,z1+halo)
            tile=x[...,sy:ey,sz:ez];d=model.forward_details(tile)
            # The exact SAME d.detail is added. No stateful forward hooks.
            neutral=continuous_width(tile,d.width_gain,d.sdf,d.normals,model.config['local_range_window'])
            values={'base':d.output,'no_shift':(neutral+d.detail).clamp(0,1),'detail':d.detail}
            for name,value in values.items():
                outputs[name][...,y:y1,z:z1]=value[...,y-sy:y1-sy,z-sz:z1-sz]
    for value in outputs.values():
        if not torch.isfinite(value).all():raise FloatingPointError('nonfinite render')
    return {k:v[0,0].cpu().numpy() for k,v in outputs.items()}

def quantize(a):return np.rint(np.clip(a,0,1)*255).astype(np.uint8)

def amplitude_control(raw,base,no_shift):
    rf=raw.astype(np.float64);delta=base.astype(np.float64)*255-rf
    target=float(np.abs(no_shift.astype(float)-rf).mean())
    def result(alpha):return np.rint(np.clip(rf+alpha*delta,0,255)).astype(np.uint8)
    def amount(a):return float(np.abs(a.astype(float)-rf).mean())
    lo,hi=0.,1.
    for _ in range(40):
        mid=(lo+hi)/2
        if amount(result(mid))<target:lo=mid
        else:hi=mid
    alpha=min([lo,hi],key=lambda t:abs(amount(result(t))-target));array=result(alpha)
    return array,{'alpha':alpha,'target_mean_absolute_gray':target,'actual_mean_absolute_gray':amount(array),
                  'absolute_mismatch_gray':abs(amount(array)-target),'target_within_attenuation_range':target<=amount(result(1))+1e-12}

def render():
    protocol=json.loads((OUT/'protocol.json').read_text());snapshot=json.loads((OUT/'input_snapshot.json').read_text())
    if any(sha(p)!=h for p,h in snapshot.items()):raise RuntimeError('Input snapshot changed; do not refresh it')
    images=OUT/'images';images.mkdir(exist_ok=False)
    torch.set_num_threads(4);cv2.setNumThreads(1)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    model=load(str(PROJECT_ROOT / protocol['checkpoint']),device)
    rows=[]
    for exposure in protocol['exposures']:
        source=ROOT.parent/f'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/{exposure}.bmp'
        raw=read(source);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(device)
        pair=render_pair(model,x);base=quantize(pair['base']);no_shift=quantize(pair['no_shift'])
        previous=read(ROOT/f'results/formal_sem/reconstructions/{exposure}.bmp')
        parity={'max_gray_difference':int(np.abs(base.astype(int)-previous.astype(int)).max()),'different_pixels':int(np.count_nonzero(base!=previous))}
        if parity['different_pixels']:raise AssertionError('Frozen baseline did not reproduce exposure '+str(exposure))
        attenuation,control=amplitude_control(raw,pair['base'],no_shift)
        folder=images/str(exposure);folder.mkdir()
        for name,array in [('Raw',raw),('base',base),('no_shift',no_shift),('attenuation',attenuation)]:
            assert cv2.imwrite(str(folder/f'{name}.png'),array)
        # Preserve the detail tensor for inspection; never load it into training.
        np.savez_compressed(folder/'detail_component.npz',detail_gray=pair['detail']*255)
        record={'exposure':exposure,'base_reproduction':parity,'attenuation':control,
                'detail_component_shared_exactly':True,'detail_mean_abs_gray':float(np.abs(pair['detail']).mean()*255),
                'files':{p.name:sha(p) for p in folder.iterdir()}}
        save_json(folder/'render_record.json',record);rows.append(record)
        print(json.dumps(record,ensure_ascii=False),flush=True)
    save_json(OUT/'render_audit.json',{'status':'rendered','exposures':rows,'device':device,'source_code_sha256':sha(__file__)})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','render']);args=p.parse_args()
    {'prepare':prepare,'render':render}[args.action]()

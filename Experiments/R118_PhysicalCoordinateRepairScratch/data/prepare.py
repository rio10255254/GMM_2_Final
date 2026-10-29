"""Reuse checked R117 geometry; generate only corrected optical observations.

References remain immutable hardlinks. Optical blur occurs on the same 8x
latent reference before sensor area integration. Real pixels are never loaded.
"""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data.geometry import draw_mask,analytic_texture,translate_high
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG=json.loads((ROOT/'config/experiment.json').read_text())
PACKAGE=ROOT/CONFIG['data']['package_root']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(payload,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(path)

def latent_reference(row):
    """Exactly replay the R117 latent reference using its recorded seed."""
    rng=np.random.default_rng(row['seed']);cfg=CONFIG['data'];size=cfg['canvas_size'];factor=8;high=size*factor
    weights=cfg['role_weights'];names=list(weights);prob=np.array(list(weights.values()),float);prob/=prob.sum()
    role=str(rng.choice(names,p=prob));family='flat_negative' if role=='flat_negative' else str(rng.choice(cfg['families']))
    if (role,family)!=(row['role'],row['family']):raise ValueError('latent provenance mismatch')
    if role=='flat_negative':
        yy,xx=np.mgrid[0:high,0:high].astype(np.float32);xx=(xx+.5)/high-.5;yy=(yy+.5)/high-.5
        image=np.clip(float(rng.uniform(.12,.88))+rng.uniform(-.10,.10)*xx+rng.uniform(-.10,.10)*yy,.03,.97)
    else:
        mask=draw_mask(size,factor,family,rng);binary=(mask>=128).astype(np.uint8)
        sdf=cv2.distanceTransform(binary,cv2.DIST_L2,cv2.DIST_MASK_5)-cv2.distanceTransform(1-binary,cv2.DIST_L2,cv2.DIST_MASK_5)
        width=float(rng.uniform(*cfg['target']['transition_width_px']))
        polarity=1.0 if rng.random()<.5 else -1.0;lo=float(rng.uniform(.10,.42));contrast=float(rng.uniform(*cfg['target']['contrast']))
        inside=float(np.clip(lo+polarity*contrast,.03,.97));p=1/(1+np.exp(-np.clip(sdf/(width*factor),-40,40)))
        image=lo+(inside-lo)*p;coverage=mask.astype(np.float32)/255
        if role=='textured_edge':
            tex=cv2.resize(analytic_texture(size,rng),(high,high),interpolation=cv2.INTER_CUBIC)
            modulation=(.20+.80*coverage) if rng.random()<.5 else (1-.75*coverage)
            image+=float(rng.uniform(*cfg['target']['texture_amplitude']))*tex*modulation
        target=cfg['target'];gamma=float(rng.uniform(*target['shared_gamma']));contrast=float(rng.uniform(*target['shared_contrast']));amplitude=float(rng.uniform(*target['shared_illumination_amplitude']))
        image=np.power(np.clip(image,0,1),gamma).astype(np.float32);mid=float(np.median(image));image=mid+contrast*(image-mid)
        if amplitude>0:
            yy,xx=np.mgrid[0:high,0:high].astype(np.float32);xx=(xx+.5)/high-.5;yy=(yy+.5)/high-.5
            angle=float(rng.uniform(0,2*math.pi));image*=1+2*amplitude*(math.cos(angle)*xx+math.sin(angle)*yy)
        image=np.clip(image,0,1).astype(np.float32)
    return image.astype(np.float32)

def psf_meta(row,view):
    rng=np.random.default_rng(CONFIG['seed']+row['scene_index']*1009+view*7919)
    if row['role']=='identity':return {'sigma_x':0.,'sigma_y':0.,'ghost_x':0.,'ghost_y':0.,'ghost_mix':0.,'broad_mix':0.}
    sx=float(np.exp(rng.uniform(*np.log(CONFIG['data']['blur_sigma_px']))));sy=float(sx*rng.uniform(.7,1.4))
    return {'sigma_x':sx,'sigma_y':sy,'ghost_x':float(rng.uniform(-1.2,1.2)),'ghost_y':float(rng.uniform(-1.2,1.2)),
            'ghost_mix':float(rng.uniform(0,.1)) if rng.random()<.3 else 0.,
            'broad_mix':float(rng.uniform(0,.2)) if rng.random()<.25 else 0.}

def image_formation(high,meta):
    if meta['sigma_x']==0:return high.copy()
    blurred=cv2.GaussianBlur(high,(0,0),sigmaX=8*meta['sigma_x'],sigmaY=8*meta['sigma_y'],borderType=cv2.BORDER_REFLECT_101)
    mix=meta['ghost_mix']
    if mix:blurred=(1-mix)*blurred+mix*translate_high(blurred,meta['ghost_x'],meta['ghost_y'],8,cv2.INTER_LINEAR)
    mix=meta['broad_mix']
    if mix:
        # Broad component is still generated before sensor sampling.
        broad=cv2.GaussianBlur(blurred,(0,0),sigmaX=16,sigmaY=16,borderType=cv2.BORDER_REFLECT_101)
        blurred=(1-mix)*blurred+mix*broad
    return blurred

def process_scene(row):
    cv2.setNumThreads(1)
    stem=f"{row['scene_index']:06d}";record_path=PACKAGE/'records'/f'{stem}.json'
    if record_path.exists():
        previous=json.loads(record_path.read_text())
        complete=all((PACKAGE/previous[k]).is_file() for k in ('source_a','source_b','target_a','target_b','sdf_a','sdf_b'))
        same_optics=previous.get('psf_a')==psf_meta(row,0) and previous.get('psf_b')==psf_meta(row,1)
        if complete and same_optics:return previous
        # Rebuild only this generated observation record. Reference hardlinks
        # remain immutable; changed optical settings do not silently reuse old data.
    source=Path(PROJECT_ROOT / CONFIG['source_package'])
    if not source.exists():source=PACKAGE
    record=dict(row)
    for key in ('target_a','target_b','mask_a','mask_b','sdf_a','sdf_b','mask2_a','mask2_b','sdf2_a','sdf2_b'):
        src=source/row[key];dst=PACKAGE/row[key];dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists():os.link(src,dst)
        if not os.path.samefile(src,dst):raise RuntimeError(f'not the immutable reference link: {dst}')
    high=latent_reference(row)
    size=CONFIG['data']['canvas_size']
    reproduced=np.rint(cv2.resize(high,(size,size),interpolation=cv2.INTER_AREA)*255).astype(np.uint8)
    expected=np.load(source/row['target_a'])
    error=int(np.max(np.abs(reproduced.astype(np.int16)-expected.astype(np.int16))))
    if error:raise RuntimeError(f'reference replay mismatch {stem}: {error}')
    for index,suffix in enumerate(('a','b')):
        view=high if index==0 else translate_high(high,row['pair_dx_px'],row['pair_dy_px'],8,cv2.INTER_LINEAR)
        meta=psf_meta(row,index)
        observation=cv2.resize(image_formation(view,meta),(size,size),interpolation=cv2.INTER_AREA)
        rel=f'sources_{suffix}/{stem}.npy';dst=PACKAGE/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        np.save(dst,observation.astype(np.float16),allow_pickle=False)
        record[f'source_{suffix}']=rel;record[f'psf_{suffix}']=meta
    record['rendered_before_sensor_sampling']=True
    record['source_render_version']=1
    record['reference_replay_max_gray']=error
    atomic_json(record_path,record)
    return record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=6);parser.add_argument('--limit',type=int,default=0);args=parser.parse_args()
    original=Path(PROJECT_ROOT / CONFIG['source_package'])/'manifest.json'
    if original.exists():
        if sha(original)!=CONFIG['source_manifest_sha256']:raise RuntimeError('reference manifest differs')
    else:
        original=PACKAGE/'manifest.json'
        local=json.loads(original.read_text())
        if local.get('reference_source_manifest_sha256')!=CONFIG['source_manifest_sha256']:raise RuntimeError('local reference lineage differs')
    source=json.loads(original.read_text());rows=source['records'];PACKAGE.mkdir(parents=True,exist_ok=True)
    if args.limit:
        # Preserve both official partitions and representative roles for smoke.
        train=[r for r in rows if r['split']=='train'][:args.limit]
        val=[r for r in rows if r['split']=='validation'][:max(48,args.limit//4)]
        rows=train+val
    results=[];started=time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(process_scene,r) for r in rows]
        for done,future in enumerate(as_completed(futures),1):
            results.append(future.result())
            if done%50==0 or done==len(rows):
                print(json.dumps({'prepared':done,'total':len(rows),'elapsed_seconds':time.time()-started}),flush=True)
    results.sort(key=lambda r:r['scene_index'])
    counts={s:sum(r['split']==s for r in results) for s in ('train','validation')}
    manifest={'status':'complete' if counts=={'train':5000,'validation':512} else 'partial_probe',
              'records':results,'counts':counts,'reference_source_manifest_sha256':CONFIG['source_manifest_sha256'],'training_uses_real_pixels':False,
              'geometry_unchanged':True,'reference_labels_hardlinked':True,'source_blurred_at_8x_before_downsampling':True,
              'fixed_optical_views':2,'sensor_noise_resampled_each_epoch':True}
    atomic_json(PACKAGE/'manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='records'}),flush=True)

if __name__=='__main__':main()

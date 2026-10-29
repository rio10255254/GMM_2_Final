"""Physical sequence payload: replay latent at 8x, shift, blur, integrate."""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data.replay import latent_reference, image_formation, CONFIG
from data.geometry import draw_mask, translate_high
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE=Path(PROJECT_ROOT / CONFIG['data']['package_root'])
IDS=ROOT.parent/'R118_PhysicalCoordinateRepairScratch/reports/next_design_selected_ids.json'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def poses():
    result=[(0.,0.)]
    for axis in ('x','y','diag'):
        for k in range(-8,9):
            p=k/8
            xy=(p,0.) if axis=='x' else (0.,p) if axis=='y' else (p,p)
            if xy not in result:result.append(xy)
    return result


def geometry(record):
    rng=np.random.default_rng(record['seed'])
    names=list(CONFIG['data']['role_weights'])
    weights=np.array(list(CONFIG['data']['role_weights'].values()),float);weights/=weights.sum()
    role=str(rng.choice(names,p=weights))
    family='flat_negative' if role=='flat_negative' else str(rng.choice(CONFIG['data']['families']))
    if role!=record['role'] or family!=record['family']:raise ValueError('geometry replay identity')
    if role=='flat_negative':raise ValueError('sequence enrichment excludes flat fields')
    mask=draw_mask(256,8,family,rng)
    binary=(mask>=128).astype(np.uint8)
    sdf=(cv2.distanceTransform(binary,cv2.DIST_L2,5)-cv2.distanceTransform(1-binary,cv2.DIST_L2,5))/8
    return mask,sdf


def render(record, output):
    cv2.setNumThreads(1)
    high=latent_reference(record)
    anchor=np.rint(cv2.resize(high,(256,256),interpolation=cv2.INTER_AREA)*255).astype(np.uint8)
    old=np.load(BASE/record['target_a'])
    if not np.array_equal(anchor,old):raise ValueError('original latent target does not replay exactly')
    mask,sdf=geometry(record)
    # Preserve exactly the original a-view optics at every position. Its possible
    # fixed centroid bias is recorded separately; it is not stage displacement.
    optical=dict(record['psf_a'])
    sources=[];targets=[];masks=[];distances=[]
    for dx,dy in poses():
        shifted=translate_high(high,dx,dy,8,cv2.INTER_LINEAR)
        formed=image_formation(shifted,optical)
        sources.append(cv2.resize(formed,(256,256),interpolation=cv2.INTER_AREA).astype(np.float16))
        targets.append(np.rint(cv2.resize(shifted,(256,256),interpolation=cv2.INTER_AREA)*255).astype(np.uint8))
        coverage=translate_high(mask.astype(np.float32)/255,dx,dy,8,cv2.INTER_LINEAR)
        masks.append(np.rint(cv2.resize(coverage,(256,256),interpolation=cv2.INTER_AREA)*255).astype(np.uint8))
        distances.append(cv2.resize(translate_high(sdf,dx,dy,8,cv2.INTER_LINEAR),(256,256),interpolation=cv2.INTER_AREA).astype(np.float16))
    path=Path(output)/f"{record['scene_index']:06d}.npz"
    if not np.array_equal(sources[0],np.load(BASE/record['source_a'])):
        raise ValueError('original optical a-view does not replay exactly')
    if path.exists():raise FileExistsError(path)
    np.savez_compressed(path,source=np.stack(sources),target=np.stack(targets),mask=np.stack(masks),
                        sdf=np.stack(distances),xy=np.asarray(poses(),np.float32))
    return {'scene_index':record['scene_index'],'split':record['split'],'family':record['family'],
        'role':record['role'],'polarity':record['polarity'],'file':path.name,'sha256':sha(path),
        'bytes':path.stat().st_size,'optics':optical,'poses':len(poses()),'target_anchor_byte_equal':True,
        'render_order':['8x_latent','8x_translation','8x_optical_blur','sensor_area_integration'],
        'sdf_convention':'foreground_positive','base_record_seed':record['seed'],
        'source_anchor_byte_equal':True,
        'fixed_kernel_centroid_px':[optical['ghost_mix']*optical['ghost_x'],optical['ghost_mix']*optical['ghost_y']]}


def main():
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['train','validation'],required=True)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--pilot',type=int,default=0)
    args=p.parse_args()
    selected=json.loads(IDS.read_text());records=json.loads((BASE/'manifest.json').read_text())['records']
    key='short_sequence_enrichment_ids' if args.split=='train' else 'development_bank_scene_ids'
    ids=selected[key][:args.pilot or None]
    chosen=[r for r in records if r['scene_index'] in ids]
    if len(chosen)!=len(ids) or any(r['split']!=args.split for r in chosen):raise ValueError('partition mismatch')
    suffix=f'{args.split}_pilot{args.pilot}' if args.pilot else args.split
    output=ROOT/'data/sequences'/suffix;output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(render,r,str(output)):r['scene_index'] for r in chosen}
        for future in as_completed(jobs):
            results.append(future.result())
            print(json.dumps({'split':suffix,'scenes':len(results),'total':len(chosen),
                              'seconds':round(time.monotonic()-start,1)}),flush=True)
    payload={'status':'complete','split':args.split,'scene_count':len(results),'poses_per_scene':len(poses()),
        'ids_source_sha256':sha(IDS),'base_manifest_sha256':sha(BASE/'manifest.json'),
        'new_payload_bytes':sum(r['bytes'] for r in results),'records':sorted(results,key=lambda r:r['scene_index'])}
    (output/'manifest.json').write_text(json.dumps(payload,indent=2))


if __name__=='__main__':main()

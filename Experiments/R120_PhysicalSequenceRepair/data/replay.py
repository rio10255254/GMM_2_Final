from pathlib import Path
import json
import math
import numpy as np
import cv2
from data.geometry import draw_mask, analytic_texture, translate_high
ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'config/experiment.json').read_text())

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

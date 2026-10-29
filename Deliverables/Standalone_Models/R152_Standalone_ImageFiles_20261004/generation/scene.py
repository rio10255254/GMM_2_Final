"""Unchanged scene parameters/intensity functions from the R128 source."""
import math
import hashlib
import json
import numpy as np
from . import geometry as g
from .recipe import SCENE_CONFIG as CFG

def digest(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

def canonical(d):return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False)

def categories(count,seed):
    exact=np.asarray(CFG['category_weights'])*count;n=np.floor(exact).astype(int)
    for i in np.argsort(-(exact-n),kind='stable')[:count-int(n.sum())]:n[i]+=1
    result=[c for c,k in zip(CFG['categories'],n) for _ in range(int(k))]
    order=np.random.default_rng(seed+77).permutation(count)
    return [result[i] for i in order]

def parameters(split,index):
    count=CFG['splits'][split];category=categories(count,CFG['split_seeds'][split])[index];seed=CFG['split_seeds'][split]+index
    rngs=[np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(7)]
    geom,photo,psf,motion,noise0,noise1,texture=rngs
    identity=category in ['clean_identity','noisy_identity'];flat=category=='flat_negative'
    shape=g._parameters(index,'clean_identity' if identity else category,geom,0,128)
    if identity:
        shape.update(center_xy=geom.integers(-12,13,2).astype(int).tolist(),box_half_width=int(geom.integers(16,49)),box_half_height=int(geom.integers(16,49)),notch_width=int(geom.integers(3,14)))
    elif category=='irregular_curved':shape.update(radius=float(geom.uniform(18,52)))
    elif category=='corners_lines_junctions':shape.update(bar_width=float(geom.uniform(4,16)),arm_length=float(geom.uniform(50,112)),branch_offset=float(geom.uniform(5,24)))
    elif category=='dense_close_structures':shape.update(pitch=float(geom.uniform(10,24)),gap=float(geom.uniform(1.5,6)))
    elif category=='textured_edges':shape.update(wave_amplitude=float(geom.uniform(2,12)),wave_period=float(geom.uniform(24,80)))
    contrast=float(photo.uniform(12,205));low=float(photo.uniform(16,235-contrast));high=low+contrast
    if identity:low=float(round(low));high=float(round(high));high=max(high,low+10)
    ph=dict(low_gray=low,high_gray=high,polarity=1 if photo.random()<.5 else -1,
            texture_amplitude=float(texture.uniform(.025,.10) if category=='textured_edges' else texture.uniform(0,.025)),
            radial_amplitude=float(texture.uniform(0,.10) if category=='irregular_curved' else 0),
            illumination_amplitude=float(texture.uniform(0,.025)),background_amplitude=float(texture.uniform(0,.025)),
            texture_angle=float(texture.uniform(-math.pi,math.pi)),texture_phase=float(texture.uniform(-math.pi,math.pi)),
            texture_period1=float(texture.uniform(4.5,12)),texture_period2=float(texture.uniform(15,50)),
            radial_scale=float(texture.uniform(18,65)),illumination_angle=float(texture.uniform(-math.pi,math.pi)))
    if identity or flat:
        for k in ['texture_amplitude','radial_amplitude','illumination_amplitude','background_amplitude']:ph[k]=0.
    if flat:ph['flat_level_gray']=float(photo.uniform(16,235))
    sigma=float(psf.choice([.6,1.,1.6,2.2]));sy=sigma*float(psf.choice([.8,1.,1.25]));angle=float(psf.uniform(-math.pi,math.pi));components=[dict(weight=1.,sigma_x=sigma,sigma_y=sy,angle=angle)]
    radius=int(math.ceil(4.5*max(sigma,sy)))
    if not identity and psf.random()<.3:
        mass=float(psf.uniform(.03,.12));broad=float(psf.uniform(3.,6.));components[0]['weight']=1-mass;components.append(dict(weight=mass,sigma_x=broad,sigma_y=broad,angle=0.));radius=16
    if identity:components=[];radius=0
    delta=motion.uniform(-.9,.9,2).tolist()
    if category=='clean_identity':delta=[0.,0.]
    if np.hypot(*delta)<.12 and category!='clean_identity':delta[0]+=.25
    noise=float(psf.choice([.5,1.5,3.])) if category!='clean_identity' else 0.
    return dict(parent_id=f'r128_{split}_{index:04d}',split=split,index=index,seed=seed,category=category,shape=shape,photometry=ph,psf=dict(components=components,radius_native=radius,finite_support_declared=True),shift_xy=delta,noise_sigma_gray=noise,motion_observable=not flat,geometry_sha256=hashlib.sha256(canonical(shape).encode()).hexdigest(),external_source_inputs=[],real_or_SEM_answers_used=False),[noise0,noise1]

def optical(x,y,m,shift):
    shape=m['shape'];p=m['photometry'];fg=g.object_score(x,y,shape,shift)>0
    if m['category']=='flat_negative':return np.full(fg.shape,p['flat_level_gray']/255),fg
    tx=x-shift[0]-shape['center_xy'][0];ty=y-shift[1]-shape['center_xy'][1];ca,sa=math.cos(p['texture_angle']),math.sin(p['texture_angle']);u=ca*tx+sa*ty;v=-sa*tx+ca*ty
    wave=.62*np.sin(2*math.pi*u/p['texture_period1']+p['texture_phase'])+.38*np.cos(2*math.pi*v/p['texture_period2']-p['texture_phase'])
    rad=2*np.exp(-(tx*tx+ty*ty)/(2*p['radial_scale']**2))-1
    illumination=np.tanh((math.cos(p['illumination_angle'])*x+math.sin(p['illumination_angle'])*y)/96)
    amp=p['texture_amplitude']+p['radial_amplitude']+p['illumination_amplitude']
    foreground=amp+p['texture_amplitude']*wave+p['radial_amplitude']*rad+p['illumination_amplitude']*illumination
    background=1-p['background_amplitude']+p['background_amplitude']*np.sin(2*math.pi*x/91+2*math.pi*y/117+p['texture_phase'])
    frac=np.where(fg,foreground,background)
    if p['polarity']==1:frac=1-frac
    image=(p['low_gray']+(p['high_gray']-p['low_gray'])*frac)/255
    return image,fg


def render_initial_latent(metadata, native_rows=16):
    """Render the only R128 latent view consumed by the R148/R152 recipe.

    Exactly the original 8x cell coordinates, intensity math, 2x area means
    and float32 rounding. Row chunks only reduce temporary memory. The unused
    old second view, simulated Gaussian blur and diagnostic arrays are omitted.
    """
    n = CFG['native_field']
    axis = (np.arange(n*8, dtype=float)+.5)/8-n/2
    latent = np.empty((n*4,n*4), dtype=np.float32)
    for first in range(0,n,native_rows):
        last = min(n,first+native_rows)
        image, _ = optical(axis[None,:], axis[first*8:last*8,None], metadata, [0.,0.])
        if metadata['category'] == 'clean_identity':
            target = g.area_average(image,8).astype(np.float32)
            target = np.rint(target*255).astype(np.uint8).astype(np.float32)/np.float32(255)
            values = target.repeat(4,0).repeat(4,1)
        else:
            values = g.area_average(image,2).astype(np.float32)
        latent[first*4:last*4] = values
    return latent

"""New disjoint parent scenes; independent8xphysical formation and4xreferences."""
from __future__ import annotations
import sys,math,hashlib,json,importlib.util,time
from pathlib import Path
import numpy as np
from scipy import ndimage,signal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import R125,load,save,sha
spec=importlib.util.spec_from_file_location('r125_stateless_geometry',R125/'data/generator_v2.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
CFG=load(ROOT/'config/study.json')

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

def kernel(psf,factor):
    if not psf['components']:return np.ones((1,1),np.float64)
    axis=np.arange(-psf['radius_native']*factor,psf['radius_native']*factor+1,dtype=np.float64)/factor;x,y=np.meshgrid(axis,axis);out=np.zeros_like(x)
    for c in psf['components']:
        ca,sa=math.cos(c['angle']),math.sin(c['angle']);u=ca*x+sa*y;v=-sa*x+ca*y;k=np.exp(-.5*((u/c['sigma_x'])**2+(v/c['sigma_y'])**2));k/=k.sum();out+=c['weight']*k
    return out/out.sum()
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

def render(m,noise_rngs,native_size=None):
    n=CFG['native_field'] if native_size is None else native_size;f=8;margin=m['psf']['radius_native'];axis=(np.arange((n+2*margin)*f,dtype=float)+.5)/f-n/2-margin;x,y=axis[None,:],axis[:,None];region=slice(margin*f,(margin+n)*f);core0=n//2-64;core1=n//2+64;k8=kernel(m['psf'],8);k4=kernel(m['psf'],4)
    arrays={k:[] for k in ['source','target','latent_target','noiseless','material_core','sdf_core']};checks=[]
    for view,shift in enumerate([[0.,0.],m['shift_xy']]):
        image,fg=optical(x,y,m,shift);inside=image[region,region];target=g.area_average(inside,8).astype(np.float32);latent=g.area_average(inside,2).astype(np.float32)
        if m['category']=='clean_identity':
            target=np.rint(target*255).astype(np.uint8).astype(np.float32)/np.float32(255);latent=target.repeat(4,0).repeat(4,1)
        blurred=signal.fftconvolve(image,k8,mode='same') if k8.size>1 else image
        noiseless=g.area_average(blurred[region,region],8).astype(np.float32)
        if m['category']=='clean_identity':noiseless=target.copy()
        sigma=m['noise_sigma_gray'];source=np.rint(np.clip(noiseless.astype(float)+noise_rngs[view].normal(0,sigma/255,noiseless.shape),0,1)*255).astype(np.uint8)
        material=g.area_average(fg[region,region][core0*8:core1*8,core0*8:core1*8].astype(float),8).astype(np.float32)
        c=n//2;sdf_window=fg[region,region][(c-96)*8:(c+96)*8,(c-96)*8:(c+96)*8];sdf=g._sdf_from_foreground(sdf_window)[32:160,32:160]
        for key,value in dict(source=source,target=target,latent_target=latent,noiseless=noiseless,material_core=material,sdf_core=sdf).items():arrays[key].append(value)
        radius=m['psf']['radius_native']+2;l=core0-radius;h=core1+radius;small=latent[l*4:h*4,l*4:h*4].astype(float);model4=signal.fftconvolve(small,k4,mode='same') if k4.size>1 else small;model_native=g.area_average(model4,4)[radius:radius+128,radius:radius+128]
        diff=(model_native-noiseless[core0:core1,core0:core1])*255;declared=np.sqrt(max(sigma,.5)**2+1/12);cy,cx=np.mgrid[:k4.shape[0],:k4.shape[1]];cr=k4.shape[0]//2
        checks.append(dict(view=view,model_fit_rms_gray=float(np.sqrt(np.mean(diff**2))),model_fit_rms_sigma=float(np.sqrt(np.mean(diff**2))/declared),model_fit_p99_sigma=float(np.quantile(np.abs(diff),.99)/declared),area_target_error=float(np.max(np.abs(g.area_average(latent.astype(float),4)-target))),core_saturation_count=int(np.sum((source[core0:core1,core0:core1]==0)|(source[core0:core1,core0:core1]==255))),foreground_fraction=float(material.mean()),boundary_pixels=int(np.sum(np.abs(sdf)<=1)),target_range=[float(target.min()),float(target.max())],PSF_centroid_xy=[float(np.sum((cx-cr)*k4)/4),float(np.sum((cy-cr)*k4)/4)]))
    arrays={k:np.stack(v) for k,v in arrays.items()};arrays['kernel4']=k4.astype(np.float64)
    return arrays,checks

def generate(args):
    split,index,output=args;out=Path(output)/split;out.mkdir(parents=True,exist_ok=True);m,rngs=parameters(split,index);ap=out/f'{index:04d}.npz';mp=out/f'{index:04d}.json'
    if ap.exists() or mp.exists():raise FileExistsError('Refuse to replace generated parent')
    start=time.perf_counter();arrays,checks=render(m,rngs)
    m.update(native_field=CFG['native_field'],core_slice=[128,256,128,256],render_factor=8,latent_factor=4,world_origin=[-192,-192],model_inputs=['source_only'],formation_order=['continuous_geometry_and_intrinsic_texture_shift','camera_fixed_illumination','fixed_pair_PSF8','sensor_area_integration','independent_sensor_noise','uint8_quantization'],checks=checks,array_sha256={k:digest(v) for k,v in arrays.items()},generator_sha256=sha(__file__),geometry_helper_sha256=sha(R125/'data/generator_v2.py'))
    np.savez_compressed(ap,**arrays);save(mp,m)
    return dict(parent_id=m['parent_id'],split=split,index=index,category=m['category'],geometry_sha256=m['geometry_sha256'],arrays_path=str(ap.relative_to(Path(output))),metadata_path=str(mp.relative_to(Path(output))),arrays_sha256=sha(ap),metadata_sha256=sha(mp),bytes=ap.stat().st_size,seconds=time.perf_counter()-start,checks=checks)

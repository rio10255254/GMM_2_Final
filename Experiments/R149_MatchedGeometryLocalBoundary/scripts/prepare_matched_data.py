"""Replace a fixed subset of dense synthetic parents with real-scale circle geometry.

The replacement geometry is procedural. No real image, SEM diameter, or PI value is
used as a training answer. The measured 25-PSF bank is used only to form blur.
"""
from __future__ import annotations
import concurrent.futures,hashlib,json,sys,time
from pathlib import Path
import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.signal import fftconvolve
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import data_config,load,save,sha,now
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CFG=data_config();BASE_PAYLOAD=Path(PROJECT_ROOT / CFG['base_payload_path']);BASE_GEOMETRY=Path(PROJECT_ROOT / CFG['base_geometry_path']);OVERLAY=ROOT/'data/overlay'
SPLIT_OFFSET={'train':0,'dev':7,'test':13};SPLIT_CODE={'train':0,'dev':1,'test':2};SUB=(.25,.5,.75);LARGE=(2.,4.,6.,8.);DIR=((1,0),(0,1),(-1,0),(0,-1));CONTRAST=(.85,.95,1.,1.15);BRIGHT=(-5.,0.,3.,5.);NOISE=(.5,1.,1.5,3.)
_BANK4=None
def digest(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
def bank4():
 global _BANK4
 if _BANK4 is None:
  with np.load(ROOT/'calibration/measured_psf_bank.npz',allow_pickle=False) as z:bank=z['all_kernels'].astype(np.float64)
  x=np.arange(-50,51,dtype=float);xx=np.linspace(-50,50,401);out=[]
  for kernel in bank:
   k=RectBivariateSpline(x,x,kernel,kx=3,ky=3)(xx,xx);k=np.maximum(k,0);k/=k.sum();out.append(k)
  _BANK4=np.stack(out)
 return _BANK4
def shift4(image,dx,dy):
 ix=int(round(dx*4));iy=int(round(dy*4));assert abs(ix/4-dx)<1e-12 and abs(iy/4-dy)<1e-12;p=40;v=np.pad(image,p,mode='reflect');h,w=image.shape
 return v[p-iy:p-iy+h,p-ix:p-ix+w]
def avg4(x):return x.reshape(384,4,384,4).mean((1,3)).astype(np.float32)
def convolve4(x,kernel):
 p=200;v=np.pad(x,p,mode='reflect');return fftconvolve(v,kernel,mode='same')[p:-p,p:-p]
def specs(split,index):
 off=SPLIT_OFFSET[split];sub=SUB[(index+off)%len(SUB)];large=LARGE[(index+off)%len(LARGE)];d0=DIR[(index+off)%4];d1=DIR[(index+off+1)%4];shifts=[(0.,0.),(d0[0]*sub,d0[1]*sub),(d1[0]*large,d1[1]*large),(d0[0]*large,d1[1]*sub)];rows=[]
 for view,(dx,dy) in enumerate(shifts):
  rotation=(index+off+view)%4;rows.append(dict(view=view,shift_xy=[dx,dy],contrast=1. if view==0 else CONTRAST[rotation],brightness_gray=0. if view==0 else BRIGHT[(rotation+view)%4],noise_sigma_gray=NOISE[(rotation+2*view)%4],psf_index=(index*4+view+off)%25))
 return rows
def geometry_for(split,index,ordinal):
 rng=np.random.default_rng(np.random.SeedSequence([1490301,SPLIT_CODE[split],index]));pitch=float(rng.uniform(*CFG['matched_pitch_px']));base_radius=float(rng.uniform(*CFG['matched_radius_px']));cx=192+float(rng.uniform(-3,3));cy=192+float(rng.uniform(-3,3));motif='nine_grid' if ordinal%4!=3 else 'sparse_five';locations=[]
 for gy in (-1,0,1):
  for gx in (-1,0,1):
   if motif=='sparse_five' and abs(gx)+abs(gy)>1:continue
   locations.append([cx+gx*pitch+float(rng.uniform(-.45,.45)),cy+gy*pitch+float(rng.uniform(-.45,.45)),base_radius*float(rng.uniform(.92,1.08))])
 dark=bool(ordinal%8!=7)
 if dark:bg=float(rng.uniform(.62,.84));fg=float(rng.uniform(.12,.34))
 else:bg=float(rng.uniform(.12,.34));fg=float(rng.uniform(.62,.84))
 return dict(motif=motif,pitch_px=pitch,base_radius_px=base_radius,circles=locations,polarity='dark_on_bright' if dark else 'bright_on_dark',background=bg,foreground=fg,gradient_xy=[float(rng.uniform(-.025,.025)),float(rng.uniform(-.025,.025))])
def latent4(shape):
 h=w=1536;mask=np.zeros((h,w),bool)
 for cx,cy,r in shape['circles']:
  x0=max(0,int(np.floor((cx-r)*4)));x1=min(w,int(np.ceil((cx+r)*4)));y0=max(0,int(np.floor((cy-r)*4)));y1=min(h,int(np.ceil((cy+r)*4)));xs=(np.arange(x0,x1)+.5)/4;ys=(np.arange(y0,y1)+.5)/4;inside=(ys[:,None]-cy)**2+(xs[None,:]-cx)**2<=r*r;mask[y0:y1,x0:x1]|=inside
 yy=(np.arange(h)+.5)/4;xx=(np.arange(w)+.5)/4;gx,gy=shape['gradient_xy'];background=shape['background']+gx*(xx[None,:]-192)/192+gy*(yy[:,None]-192)/192;return np.where(mask,shape['foreground'],background).clip(.002,.998)
def sdf96(circles,shift):
 axis=np.arange(144,240,dtype=np.float32)+.5;y,x=axis[:,None],axis[None,:];fields=[]
 for cx,cy,r in circles:fields.append(r-np.sqrt((x-(cx+shift[0]))**2+(y-(cy+shift[1]))**2))
 return np.maximum.reduce(fields).clip(-8,8).astype(np.float16)
def build(task):
 split,index,ordinal,base_entry=task;shape=geometry_for(split,index,ordinal);latent=latent4(shape);mid=(shape['background']+shape['foreground'])/2;targets=[];noiseless=[];sdfs=[];views=specs(split,index);clips=[];kernels=bank4()
 for v in views:
  requested_contrast=v['contrast'];requested_brightness=v['brightness_gray'];span=float(latent.max()-latent.min());effective=min(requested_contrast,.996/max(span,1e-9));base=mid+effective*(latent-mid);lower=.002-float(base.min());upper=.998-float(base.max());offset=float(np.clip(requested_brightness/255,lower,upper));v['requested_contrast']=requested_contrast;v['requested_brightness_gray']=requested_brightness;v['contrast']=effective;v['brightness_gray']=offset*255;clear=base+offset;clips.append(float(((clear<0)|(clear>1)).mean()));clear=np.clip(clear,0,1);clear=shift4(clear,*v['shift_xy']);targets.append(avg4(clear));noiseless.append(avg4(convolve4(clear,kernels[v['psf_index']])));sdfs.append(sdf96(shape['circles'],v['shift_xy']))
 payload=OVERLAY/'payload'/split/f'{index:04d}.npz';meta_path=OVERLAY/'payload'/split/f'{index:04d}.json';geo=OVERLAY/'geometry'/split/f'{index:04d}.npz';payload.parent.mkdir(parents=True,exist_ok=True);geo.parent.mkdir(parents=True,exist_ok=True)
 if payload.exists() or meta_path.exists() or geo.exists():raise FileExistsError(payload)
 arrays=dict(target=np.stack(targets).astype(np.float16),noiseless=np.stack(noiseless).astype(np.float16));geometry=dict(sdf=np.stack(sdfs),valid=np.ones(4,dtype=np.uint8));np.savez_compressed(payload,**arrays);np.savez_compressed(geo,**geometry)
 parent=f'r149_{split}_{index:04d}';meta=dict(parent_id=parent,split=split,index=index,category='matched_nine_circles',motif=shape['motif'],shape=shape,views=views,formation='procedural_4x_matched_circle_geometry_then_measured_PSF_then_4x_area_integration',latent_factor=4,native_size=384,real_or_SEM_answers_used=False,external_source_inputs=[],maximum_photometric_clip_fraction=max(clips),replaces_parent_id=base_entry['parent_id'],psf_bank_sha256=sha(ROOT/'calibration/measured_psf_bank.npz'),arrays_content_sha256={k:digest(v) for k,v in arrays.items()},geometry_content_sha256={k:digest(v) for k,v in geometry.items()},generator_sha256=sha(__file__),completed_utc=now());save(meta_path,meta)
 return dict(parent_id=parent,split=split,index=index,category='matched_nine_circles',source='overlay',arrays=str(payload.relative_to(ROOT/'data')),metadata=str(meta_path.relative_to(ROOT/'data')),geometry=str(geo.relative_to(ROOT/'data')),arrays_sha256=sha(payload),metadata_sha256=sha(meta_path),geometry_sha256=sha(geo),views=views,motif=shape['motif'],pitch_px=shape['pitch_px'],base_radius_px=shape['base_radius_px'],max_clip=max(clips))
def main():
 if (ROOT/'data/manifest.json').exists() or any(OVERLAY.rglob('*.npz')):raise FileExistsError('R149 data already prepared')
 if sha(BASE_PAYLOAD/'manifest.json')!=CFG['base_payload_manifest_sha256'] or sha(BASE_GEOMETRY/'manifest.json')!=CFG['base_geometry_manifest_sha256']:raise RuntimeError('Base data changed')
 base=load(BASE_PAYLOAD/'manifest.json');gm=load(BASE_GEOMETRY/'manifest.json');gmap={(e['split'],e['index']):e for e in gm['entries']};selected={};tasks=[]
 for split,count in CFG['replacements'].items():
  dense=sorted((e for e in base['entries'] if e['split']==split and e['category']=='dense_close_structures'),key=lambda e:e['index']);rng=np.random.default_rng(np.random.SeedSequence([1490201,SPLIT_CODE[split]]));chosen=sorted(rng.choice(len(dense),size=count,replace=False).tolist());selected[split]={dense[j]['index'] for j in chosen}
  for ordinal,j in enumerate(chosen):tasks.append((split,dense[j]['index'],ordinal,dense[j]))
 start=time.perf_counter();overlay=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  for n,row in enumerate(pool.map(build,tasks),1):overlay.append(row);print('MATCHED_DATA',n,'/',len(tasks),flush=True)
 omap={(e['split'],e['index']):e for e in overlay};combined=[]
 for e in base['entries']:
  key=(e['split'],e['index'])
  if key in omap:combined.append(omap[key]);continue
  g=gmap[key];combined.append(dict(parent_id=e['parent_id'],split=e['split'],index=e['index'],category=e['category'],source='base',arrays=str(Path('base_payload')/e['arrays']),metadata=str(Path('base_payload')/e['metadata']),geometry=str(Path('base_geometry')/g['path']),arrays_sha256=e['arrays_sha256'],metadata_sha256=e['metadata_sha256'],geometry_sha256=g['sha256'],views=e['views']))
 combined.sort(key=lambda z:(SPLIT_CODE[z['split']],z['index']));manifest=dict(schema_version=1,model='R149-MatchedGeometryLocalBoundary',counts={s:sum(e['split']==s for e in combined) for s in SPLIT_CODE},categories={s:{c:sum(e['split']==s and e['category']==c for e in combined) for c in sorted(set(x['category'] for x in combined))} for s in SPLIT_CODE},replacements={s:sorted(selected[s]) for s in selected},base_payload_manifest_sha256=sha(BASE_PAYLOAD/'manifest.json'),base_geometry_manifest_sha256=sha(BASE_GEOMETRY/'manifest.json'),psf_bank_sha256=sha(ROOT/'calibration/measured_psf_bank.npz'),real_or_SEM_answers_used=False,entries=combined,created_utc=now());save(ROOT/'data/manifest.json',manifest);lock=dict(manifest_sha256=sha(ROOT/'data/manifest.json'),entries=len(combined),overlay_entries=len(overlay),base_entries=len(combined)-len(overlay),base_payload_manifest_sha256=manifest['base_payload_manifest_sha256'],base_geometry_manifest_sha256=manifest['base_geometry_manifest_sha256'],psf_bank_sha256=manifest['psf_bank_sha256'],generator_sha256=sha(__file__),created_utc=now());save(ROOT/'data/DATA_LOCK.json',lock);complete=dict(state='complete',parents=len(combined),views=4*len(combined),overlay_parents=len(overlay),matched_counts={s:sum(e['split']==s for e in overlay) for s in SPLIT_CODE},matched_pitch_range=[min(e['pitch_px'] for e in overlay),max(e['pitch_px'] for e in overlay)],matched_radius_range=[min(e['base_radius_px'] for e in overlay),max(e['base_radius_px'] for e in overlay)],maximum_photometric_clip_fraction=max(e['max_clip'] for e in overlay),manifest_sha256=lock['manifest_sha256'],elapsed_seconds=time.perf_counter()-start,completed_utc=now());save(ROOT/'results/data_complete.json',complete);print('MATCHED_DATA_COMPLETE',complete,flush=True)
if __name__=='__main__':main()

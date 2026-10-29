"""Build four deterministic physical views from each locked R147/R128 clear latent."""
from __future__ import annotations
import concurrent.futures,hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.signal import fftconvolve
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import data_config,load,save,sha,now
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CFG=data_config();BASE=Path(PROJECT_ROOT / CFG['base_experiment']);PAYLOAD=ROOT/'data/payload'
SPLIT_OFFSET={'train':0,'dev':7,'test':13};SUB=(.25,.5,.75);LARGE=(2.,4.,6.,8.);DIR=((1,0),(0,1),(-1,0),(0,-1));CONTRAST=(.85,.95,1.,1.15);BRIGHT=(-5.,0.,3.,5.);NOISE=(.5,1.,1.5,3.)
_BANK4=None
def digest_array(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
def bank4():
 global _BANK4
 if _BANK4 is None:
  with np.load(ROOT/'calibration/measured_psf_bank.npz',allow_pickle=False) as z:bank=z['all_kernels'].astype(np.float64)
  x=np.arange(-50,51,dtype=float);xx=np.linspace(-50,50,401);values=[]
  for kernel in bank:
   k=RectBivariateSpline(x,x,kernel,kx=3,ky=3)(xx,xx);k=np.maximum(k,0);k/=k.sum();values.append(k)
  _BANK4=np.stack(values)
 return _BANK4
def shift4(image,dx,dy):
 ix=int(round(dx*4));iy=int(round(dy*4));assert abs(ix/4-dx)<1e-12 and abs(iy/4-dy)<1e-12;p=40;v=np.pad(image,p,mode='reflect');h,w=image.shape
 return v[p-iy:p-iy+h,p-ix:p-ix+w]
def avg4(x):return x.reshape(384,4,384,4).mean((1,3)).astype(np.float32)
def convolve4(x,kernel):
 p=200;v=np.pad(x,p,mode='reflect');return fftconvolve(v,kernel,mode='same')[p:-p,p:-p]
def specs(split,index,category):
 off=SPLIT_OFFSET[split];sub=SUB[(index+off)%len(SUB)];large=LARGE[(index+off)%len(LARGE)];d0=DIR[(index+off)%4];d1=DIR[(index+off+1)%4]
 shifts=[(0.,0.),(d0[0]*sub,d0[1]*sub),(d1[0]*large,d1[1]*large),(d0[0]*large,d1[1]*sub)]
 rows=[]
 for view,(dx,dy) in enumerate(shifts):
  rotation=(index+off+view)%4;c=1. if view==0 else CONTRAST[rotation];b=0. if view==0 else BRIGHT[(rotation+view)%4];noise=NOISE[(rotation+2*view)%4];psf=(index*4+view+off)%25
  if view==0 and category in ('clean_identity','noisy_identity'):psf=-1
  rows.append(dict(view=view,shift_xy=[dx,dy],contrast=c,brightness_gray=b,noise_sigma_gray=noise,psf_index=psf))
 return rows
def build(entry):
 split,index=entry['split'],entry['index'];dest=PAYLOAD/split/f'{index:04d}.npz';meta_path=PAYLOAD/split/f'{index:04d}.json';dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists() or meta_path.exists():raise FileExistsError('Refuse partial replacement: '+str(dest))
 if sha(entry['original_arrays']['path'])!=entry['original_arrays']['sha256'] or sha(entry['original_metadata']['path'])!=entry['original_metadata']['sha256']:raise RuntimeError('Base lineage changed')
 source_meta=load(entry['original_metadata']['path'])
 with np.load(entry['original_arrays']['path'],allow_pickle=False) as z:latent=z['latent_target'][0].astype(np.float64)
 if latent.shape!=(1536,1536):raise ValueError('Expected 4x latent target')
 mid=(source_meta['photometry']['low_gray']+source_meta['photometry']['high_gray'])/(2*255);targets=[];noiseless=[];views=specs(split,index,entry['category']);clips=[]
 kernels=bank4()
 for v in views:
  requested_contrast=v['contrast'];requested_brightness=v['brightness_gray'];span=float(latent.max()-latent.min());effective_contrast=min(requested_contrast,.996/max(span,1e-9));base=mid+effective_contrast*(latent-mid);lower=.002-float(base.min());upper=.998-float(base.max());offset=float(np.clip(requested_brightness/255,lower,upper));v['requested_contrast']=requested_contrast;v['requested_brightness_gray']=requested_brightness;v['contrast']=effective_contrast;v['brightness_gray']=offset*255
  clear=base+offset;clips.append(float(((clear<0)|(clear>1)).mean()));clear=np.clip(clear,0,1);clear=shift4(clear,*v['shift_xy']);targets.append(avg4(clear))
  blurred=clear if v['psf_index']<0 else convolve4(clear,kernels[v['psf_index']]);noiseless.append(avg4(blurred))
 arrays=dict(target=np.stack(targets).astype(np.float16),noiseless=np.stack(noiseless).astype(np.float16));np.savez_compressed(dest,**arrays)
 meta=dict(parent_id=entry['parent_id'],split=split,index=index,category=entry['category'],geometry_sha256=entry['geometry_sha256'],views=views,formation=CFG['formation'],latent_factor=4,native_size=384,real_or_SEM_answers_used=False,external_source_inputs=[],maximum_photometric_clip_fraction=max(clips),base_original_arrays=entry['original_arrays'],base_original_metadata=entry['original_metadata'],base_target_array_sha256=entry['target_array_sha256'],psf_bank_sha256=sha(ROOT/'calibration/measured_psf_bank.npz'),arrays_content_sha256={k:digest_array(v) for k,v in arrays.items()},generator_sha256=sha(__file__),completed_utc=now());save(meta_path,meta)
 return dict(parent_id=entry['parent_id'],split=split,index=index,category=entry['category'],arrays=str(dest.relative_to(PAYLOAD)),metadata=str(meta_path.relative_to(PAYLOAD)),arrays_sha256=sha(dest),metadata_sha256=sha(meta_path),bytes=dest.stat().st_size,views=views,max_clip=max(clips))
def main():
 if PAYLOAD.exists() and any(PAYLOAD.rglob('*.npz')):raise FileExistsError('Payload already contains arrays; use the existing completion receipt')
 base=load(str(PROJECT_ROOT / CFG['base_manifest']));entries=base['entries'];assert len(entries)==768
 lock=dict(base_manifest_path=str(PROJECT_ROOT / CFG['base_manifest']),base_manifest_sha256=sha(str(PROJECT_ROOT / CFG['base_manifest'])),base_entries=768,psf_bank_sha256=sha(ROOT/'calibration/measured_psf_bank.npz'),source_generator=CFG['formation'],created_utc=now());save(ROOT/'data/BASE_DATA_LOCK.json',lock)
 start=time.perf_counter();records=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  for n,record in enumerate(pool.map(build,entries),1):
   records.append(record)
   if n%16==0 or n==768:save(ROOT/'results/data_generation_status.json',dict(state='running',completed=n,total=768,elapsed_seconds=time.perf_counter()-start,updated_utc=now()));print('DATA',n,'/ 768',flush=True)
 records.sort(key=lambda x:({'train':0,'dev':1,'test':2}[x['split']],x['index']))
 manifest=dict(schema_version=1,model='R148-MeasurementStableNativePSF',base_lock=lock,formation=CFG['formation'],counts={s:sum(r['split']==s for r in records) for s in ('train','dev','test')},entries=records,created_utc=now());save(PAYLOAD/'manifest.json',manifest)
 counts=np.bincount([v['psf_index'] for r in records if r['split']=='train' for v in r['views'] if v['psf_index']>=0],minlength=25)
 complete=dict(state='complete',parents=768,views=3072,manifest_sha256=sha(PAYLOAD/'manifest.json'),base_manifest_sha256=lock['base_manifest_sha256'],psf_counts_train=counts.tolist(),maximum_photometric_clip_fraction=max(r['max_clip'] for r in records),bytes=sum(r['bytes'] for r in records),elapsed_seconds=time.perf_counter()-start,completed_utc=now());save(ROOT/'results/data_generation_complete.json',complete);save(ROOT/'results/data_generation_status.json',complete);print('DATA_COMPLETE',complete['bytes'],flush=True)
if __name__=='__main__':main()

"""Extract unchanged supervised arrays only; do not decode any optical kernels."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from utils import ROOT,config,load,save,sha,now
def main():
 cfg=config();src=Path(cfg['dataset_source']);m=load(src/'manifest.json');out=ROOT/'data';out.mkdir(exist_ok=True);entries=[]
 allowed_meta=['parent_id','split','index','category','geometry_sha256','shift_xy','noise_sigma_gray','motion_observable','real_or_SEM_answers_used','external_source_inputs']
 for i,e in enumerate(m['entries']):
  p=src/e['arrays_path'];meta=src/e['metadata_path'];assert sha(p)==e['arrays_sha256'] and sha(meta)==e['metadata_sha256']
  full=load(meta);new={k:full[k] for k in allowed_meta};assert not new['real_or_SEM_answers_used'] and not new['external_source_inputs']
  dest=out/e['split']/f"{e['index']:04d}.npz";dest.parent.mkdir(exist_ok=True)
  # Selective reads never access kernel4, latent_target or stored geometry fields.
  with np.load(p,allow_pickle=False) as z:a={k:z[k] for k in ('source','noiseless','target')}
  if dest.exists():
   with np.load(dest,allow_pickle=False) as z:
    assert set(z.files)==set(a)
    for k,v in a.items():assert np.array_equal(z[k],v)
  else:np.savez_compressed(dest,**a)
  mp=dest.with_suffix('.json')
  if mp.exists():assert load(mp)==new
  else:save(mp,new)
  entries.append(dict(parent_id=e['parent_id'],split=e['split'],index=e['index'],category=e['category'],geometry_sha256=e['geometry_sha256'],arrays=str(dest.relative_to(out)),metadata=str(mp.relative_to(out)),arrays_sha256=sha(dest),metadata_sha256=sha(mp),original_arrays=dict(path=str(p),sha256=e['arrays_sha256']),original_metadata=dict(path=str(meta),sha256=e['metadata_sha256'])))
  if (i+1)%128==0:print('Clean data prepared',i+1,'/768',flush=True)
 groups={k:{e['parent_id'] for e in entries if e['split']==k} for k in cfg['splits']}
 geom={k:{e['geometry_sha256'] for e in entries if e['split']==k} for k in cfg['splits']}
 assert {k:len(v) for k,v in groups.items()}==cfg['splits']
 for a,b in [('train','dev'),('train','test'),('dev','test')]:assert not groups[a]&groups[b] and not geom[a]&geom[b]
 save(out/'manifest.json',dict(created_utc=now(),source_manifest=dict(path=str(src/'manifest.json'),sha256=sha(src/'manifest.json')),array_fields=['source','noiseless','target'],same_array_values_verified=True,PSF_arrays_decoded=0,entries=entries))
 save(ROOT/'results/data_preparation.json',dict(parents=768,splits=cfg['splits'],geometry_overlap=0,arrays_equal_to_existing_sources=True,no_generation=True,stored_optical_arrays_omitted=True,neural_training_inputs='generated observation only',completed_utc=now()))
if __name__=='__main__':main()

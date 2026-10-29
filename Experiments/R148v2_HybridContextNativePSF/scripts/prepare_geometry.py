"""Rebuild material-boundary coordinates from the original procedural geometry."""
from pathlib import Path
import hashlib,importlib.util,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import data_config,load,save,sha,now
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CFG=data_config();PAYLOAD=ROOT/'data/payload';OUT=ROOT/'data/geometry'
def digest(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
def main():
 if sha(PAYLOAD/'manifest.json')!=CFG['shared_payload_manifest_sha256']:raise RuntimeError('Shared payload changed')
 spec=importlib.util.spec_from_file_location('geometry_source',str(PROJECT_ROOT / CFG['geometry_source']));g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
 manifest=load(PAYLOAD/'manifest.json');records=[];mismatches=[];axis=np.arange(144,240,dtype=float)+.5-192;y,x=axis[:,None],axis[None,:]
 sub=(np.arange(384,dtype=float)+.5)/4+144-192;ys,xs=sub[:,None],sub[None,:]
 for n,e in enumerate(manifest['entries'],1):
  meta=load(PAYLOAD/e['metadata']);base=load(meta['base_original_metadata']['path']);shape=base['shape'];sdfs=[];valid=[]
  for view in meta['views']:
   score=g.object_score(x,y,shape,view['shift_xy']);gy,gx=np.gradient(score);distance=np.clip(score/(np.hypot(gx,gy)+1e-4),-8,8);is_valid=base['category']!='flat_negative';sdfs.append(distance.astype(np.float16));valid.append(is_valid)
   fine=g.object_score(xs,ys,shape,view['shift_xy'])>0;coverage=fine.reshape(96,4,96,4).mean((1,3));mismatches.append(float(np.mean((score>0)!=(coverage>.5))))
  dest=OUT/e['split']/f"{e['index']:04d}.npz";dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():raise FileExistsError(dest)
  arrays=dict(sdf=np.stack(sdfs),valid=np.asarray(valid,dtype=np.uint8));np.savez_compressed(dest,**arrays);records.append(dict(split=e['split'],index=e['index'],parent_id=e['parent_id'],path=str(dest.relative_to(OUT)),sha256=sha(dest),content_sha256={k:digest(v) for k,v in arrays.items()}))
  if n%64==0:print('GEOMETRY',n,'/768',flush=True)
 records.sort(key=lambda z:({'train':0,'dev':1,'test':2}[z['split']],z['index']));save(OUT/'manifest.json',dict(entries=records,geometry_source_path=str(PROJECT_ROOT / CFG['geometry_source']),geometry_source_sha256=sha(str(PROJECT_ROOT / CFG['geometry_source'])),payload_manifest_sha256=sha(PAYLOAD/'manifest.json'),native_vs_4x_majority_mismatch_mean=float(np.mean(mismatches)),native_vs_4x_majority_mismatch_max=float(np.max(mismatches)),created_utc=now()));save(ROOT/'data/PAYLOAD_LOCK.json',dict(logical_path=str(PAYLOAD),resolved_path=str(PAYLOAD.resolve()),manifest_sha256=sha(PAYLOAD/'manifest.json'),entries=768,read_only_contract=True,created_utc=now()));save(ROOT/'results/geometry_complete.json',dict(state='complete',parents=768,views=3072,manifest_sha256=sha(OUT/'manifest.json'),mean_native_4x_mismatch=float(np.mean(mismatches)),max_native_4x_mismatch=float(np.max(mismatches)),completed_utc=now()));print('GEOMETRY_COMPLETE',float(np.mean(mismatches)),float(np.max(mismatches)),flush=True)
if __name__=='__main__':main()

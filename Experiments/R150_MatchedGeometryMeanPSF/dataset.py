"""Locked mixed base/overlay bank for R149."""
from functools import lru_cache
import numpy as np,torch
from utils import ROOT,load,sha,digest_array

class Bank:
 def __init__(self,cfg):
  self.cfg=cfg;self.root=ROOT/'data';self.manifest=load(self.root/'manifest.json');lock=load(self.root/'DATA_LOCK.json');assert sha(self.root/'manifest.json')==lock['manifest_sha256'];self.entries={(e['split'],e['index']):e for e in self.manifest['entries']};assert len(self.entries)==768
 @lru_cache(maxsize=48)
 def read(self,split,index):
  e=self.entries[(split,int(index))];a=self.root/e['arrays'];m=self.root/e['metadata'];g=self.root/e['geometry']
  if sha(a)!=e['arrays_sha256'] or sha(m)!=e['metadata_sha256'] or sha(g)!=e['geometry_sha256']:raise RuntimeError('Data identity changed')
  with np.load(a,allow_pickle=False) as z:arrays={k:z[k].astype(np.float32) for k in ('target','noiseless')}
  with np.load(g,allow_pickle=False) as z:geometry={k:z[k] for k in ('sdf','valid')}
  return arrays,geometry,load(m),e
 def order(self,epoch):return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'],epoch])).permutation(512)
 def batch(self,split,index,device,epoch=None):
  a,g,m,e=self.read(split,index);ep=0 if epoch is None else int(epoch);source=[]
  for v,spec in enumerate(m['views']):
   rng=np.random.default_rng(np.random.SeedSequence([self.cfg['noise_seed'],{'train':0,'dev':1,'test':2}[split],ep,int(index),v]));x=a['noiseless'][v].astype(np.float64)+rng.normal(0,spec['noise_sigma_gray']/255,a['noiseless'][v].shape);source.append(np.rint(np.clip(x,0,1)*255).astype(np.uint8))
  x=np.ascontiguousarray(np.stack(source)[:,None].astype(np.float32)/255);y=np.ascontiguousarray(a['target'][:,None]);actual=np.array([-2 if v['psf_index']<0 else v['psf_index'] for v in m['views']],np.int64);operator=np.full_like(actual,-1)
  return dict(source=torch.from_numpy(x).to(device),target=torch.from_numpy(y).to(device),sdf=torch.from_numpy(g['sdf'].astype(np.float32)[:,None]).to(device),geometry_valid=torch.from_numpy(g['valid'].astype(bool)).to(device),shifts_xy=torch.tensor([v['shift_xy'] for v in m['views']],dtype=torch.float32,device=device),actual_psf_indices=torch.from_numpy(actual).to(device),operator_psf_indices=torch.from_numpy(operator).to(device),core=(144,240),observation_core=(160,224),parent_id=e['parent_id'],category=e['category'],source_kind=e['source'],motif=e.get('motif'),input_sha256=digest_array(x),epoch=epoch)

from functools import lru_cache
from pathlib import Path
import numpy as np,torch
from utils import ROOT,load,sha,digest_array
class Bank:
 def __init__(self,cfg):
  self.cfg=cfg;self.root=ROOT/'data/payload';self.manifest=load(self.root/'manifest.json');self.entries={(e['split'],e['index']):e for e in self.manifest['entries']}
  if len(self.entries)!=768:raise ValueError('Incomplete payload')
 @lru_cache(maxsize=48)
 def read(self,split,index):
  e=self.entries[(split,int(index))];a=self.root/e['arrays'];m=self.root/e['metadata']
  if sha(a)!=e['arrays_sha256'] or sha(m)!=e['metadata_sha256']:raise RuntimeError('Payload changed')
  with np.load(a,allow_pickle=False) as z:arrays={k:z[k].astype(np.float32) for k in ('target','noiseless')}
  return arrays,load(m),e
 def order(self,epoch):return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'],epoch])).permutation(512)
 def batch(self,split,index,device,epoch=None):
  arrays,meta,e=self.read(split,index);ep=0 if epoch is None else int(epoch);noisy=[]
  for v,spec in enumerate(meta['views']):
   rng=np.random.default_rng(np.random.SeedSequence([self.cfg['noise_seed'],{'train':0,'dev':1,'test':2}[split],ep,int(index),v]));x=arrays['noiseless'][v].astype(np.float64)+rng.normal(0,spec['noise_sigma_gray']/255,arrays['noiseless'][v].shape);noisy.append(np.rint(np.clip(x,0,1)*255).astype(np.uint8))
  source=np.stack(noisy);lo,hi=32,352;x=np.ascontiguousarray(source[:,None,lo:hi,lo:hi].astype(np.float32)/255);y=np.ascontiguousarray(arrays['target'][:,None,lo:hi,lo:hi]);actual=np.array([-2 if v['psf_index']<0 else v['psf_index'] for v in meta['views']],np.int64)
  if split=='train':
   rng=np.random.default_rng(np.random.SeedSequence([self.cfg['operator_seed'],ep,int(index)]));operator=actual.copy();operator[rng.random(len(operator))>=self.cfg['known_operator_probability']]=-1
  else:operator=np.full_like(actual,-1)
  return dict(source=torch.from_numpy(x).to(device),target=torch.from_numpy(y).to(device),shifts_xy=torch.tensor([v['shift_xy'] for v in meta['views']],dtype=torch.float32,device=device),actual_psf_indices=torch.from_numpy(actual).to(device),operator_psf_indices=torch.from_numpy(operator).to(device),core=(96,224),parent_id=e['parent_id'],category=e['category'],input_sha256=digest_array(x),epoch=epoch)

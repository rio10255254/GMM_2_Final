"""One new parent pair per update; the generator's truths stay outside forward."""
from functools import lru_cache
import hashlib,json,sys
import numpy as np
import torch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import load,sha

def digest(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

class Bank:
    def __init__(self,root=None):
        self.root=Path(root or ROOT/'data/package')
        self.manifest=load(self.root/'manifest.json')
        self.entries={(e['split'],e['index']):e for e in self.manifest['entries']}
        self.cfg=load(ROOT/'config/study.json')
        if len(self.entries)!=sum(self.cfg['splits'].values()):raise ValueError('Missing or duplicate parent')
    @lru_cache(maxsize=32)
    def read(self,split,index):
        e=self.entries[(split,index)];ap=self.root/e['arrays_path'];mp=self.root/e['metadata_path']
        if sha(ap)!=e['arrays_sha256'] or sha(mp)!=e['metadata_sha256']:raise RuntimeError('Data identity mismatch')
        meta=load(mp)
        if meta['split']!=split or meta['index']!=index or meta['real_or_SEM_answers_used'] or meta['external_source_inputs']:raise ValueError('Invalid source lineage')
        with np.load(ap) as d:
            arrays={k:d[k] for k in ['source','noiseless','target','latent_target','kernel4']}
        return arrays,meta,e
    def batch(self,split,index,device,epoch=None):
        if split!='train' and epoch is not None:raise ValueError('Only training may receive new noise')
        a,m,e=self.read(split,index)
        return make_batch(a,m,e,device,epoch,self.cfg['online_noise_seed'])
    def order(self,epoch):
        return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'],epoch])).permutation(self.cfg['splits']['train'])

def make_batch(arrays,meta,entry,device,epoch=None,base_seed=128800000):
    source=arrays['source']
    noise_seed=None
    if epoch is not None:
        noise_seed=[base_seed,int(epoch),int(meta['index'])]
        rng=np.random.default_rng(np.random.SeedSequence(noise_seed))
        noisy=arrays['noiseless'].astype(np.float64)+rng.normal(0,meta['noise_sigma_gray']/255,source.shape)
        source=np.rint(np.clip(noisy,0,1)*255).astype(np.uint8)
    window=slice(32,352);latent_window=slice(128,1408)
    normalized=np.ascontiguousarray(source[:,window,window,None].transpose(0,3,1,2).astype(np.float32)/np.float32(255))
    tensor=lambda a:torch.from_numpy(np.ascontiguousarray(a[:,None])).to(device)
    batch=dict(source=torch.from_numpy(normalized).to(device),
               target=tensor(arrays['target'][:,window,window]),
               latent_target=tensor(arrays['latent_target'][:,latent_window,latent_window]),
               kernel=torch.as_tensor(arrays['kernel4'],device=device,dtype=torch.float32),
               metadata=meta,core=(96,224),parent=entry,noise_seed=noise_seed,
               cpu_input_sha256=digest(normalized),source_uint8_sha256=digest(source[:,window,window]))
    if batch['source'].shape!=(2,1,320,320) or batch['latent_target'].shape!=(2,1,1280,1280):raise ValueError('Physical crop contract failed')
    return batch

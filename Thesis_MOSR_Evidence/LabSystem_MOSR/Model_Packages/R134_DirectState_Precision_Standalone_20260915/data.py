"""Read only package-local supervised pairs; real/SEM evaluation is separate."""
from functools import lru_cache
import numpy as np,torch
from runtime import ROOT,load,sha,digest
class Bank:
    def __init__(self):
        self.root=ROOT/'training_data';self.cfg=load(ROOT/'config/training.json')
        self.entries={(e['split'],e['index']):e for e in load(self.root/'manifest.json')['entries']}
        if len(self.entries)!=sum(self.cfg['splits'].values()):raise ValueError('Missing or duplicate data')
    @lru_cache(maxsize=16)
    def read(self,split,index):
        e=self.entries[(split,index)];ap=self.root/e['arrays_path'];mp=self.root/e['metadata_path']
        if sha(ap)!=e['arrays_sha256'] or sha(mp)!=e['metadata_sha256']:raise RuntimeError('Data content changed')
        meta=load(mp)
        if meta['split']!=split or meta['index']!=index or meta['real_or_SEM_answers_used'] or meta['external_source_inputs']:raise ValueError('Invalid training provenance')
        with np.load(ap) as d:a={k:d[k] for k in ['source','noiseless','target']}
        return a,meta,e
    def order(self,epoch):return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'],epoch])).permutation(self.cfg['splits']['train'])
    def batch(self,split,index,device,epoch=None):
        if split!='train' and epoch is not None:raise ValueError('Evaluation cannot get new noise')
        a,m,e=self.read(split,index);source=a['source'];noise_seed=None
        if epoch is not None:
            noise_seed=[self.cfg['noise_seed'],int(epoch),int(index)];rng=np.random.default_rng(np.random.SeedSequence(noise_seed))
            noisy=a['noiseless'].astype(np.float64)+rng.normal(0,m['noise_sigma_gray']/255,source.shape)
            source=np.rint(np.clip(noisy,0,1)*255).astype(np.uint8)
        w=slice(32,352);normalized=np.ascontiguousarray(source[:,None,w,w].astype(np.float32)/np.float32(255))
        return dict(source=torch.from_numpy(normalized).to(device),target=torch.from_numpy(np.ascontiguousarray(a['target'][:,None,w,w])).to(device),metadata=m,core=(96,224),parent=e,noise_seed=noise_seed,cpu_input_sha256=digest(normalized))

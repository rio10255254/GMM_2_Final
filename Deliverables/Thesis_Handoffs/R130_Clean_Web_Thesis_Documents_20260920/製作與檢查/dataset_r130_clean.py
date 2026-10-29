from functools import lru_cache
import numpy as np,torch
from utils import ROOT,load,sha,digest_array
class Bank:
    def __init__(self,cfg):
        self.cfg=cfg;self.root=ROOT/'data';self.manifest=load(self.root/'manifest.json')
        self.entries={(e['split'],e['index']):e for e in self.manifest['entries']}
        self.files_opened=[]
        if len(self.entries)!=768:raise ValueError('Incomplete or duplicate dataset')
    @lru_cache(maxsize=64)
    def read(self,split,index):
        e=self.entries[(split,int(index))];p=self.root/e['arrays'];m=self.root/e['metadata']
        if sha(p)!=e['arrays_sha256'] or sha(m)!=e['metadata_sha256']:raise RuntimeError('Dataset identity changed')
        meta=load(m)
        if meta['real_or_SEM_answers_used'] or meta['external_source_inputs']:raise ValueError('Disallowed data source')
        with np.load(p,allow_pickle=False) as z:
            if set(z.files)!={'source','noiseless','target'}:raise ValueError('Non-whitelisted data fields')
            a={k:z[k] for k in ('source','noiseless','target')}
        self.files_opened.extend([str(p),str(m)])
        return a,meta,e
    def order(self,epoch):return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'],epoch])).permutation(512)
    def batch(self,split,index,device,epoch=None):
        if split!='train' and epoch is not None:raise ValueError('Noise regeneration only applies to training')
        a,m,e=self.read(split,int(index));source=a['source'];seed=None
        if epoch is not None:
            seed=[self.cfg['noise_seed'],int(epoch),int(index)];rng=np.random.default_rng(np.random.SeedSequence(seed))
            noisy=a['noiseless'].astype(np.float64)+rng.normal(0,m['noise_sigma_gray']/255,source.shape)
            source=np.rint(np.clip(noisy,0,1)*255).astype(np.uint8)
        x=np.ascontiguousarray(source[:,None,32:352,32:352].astype(np.float32)/np.float32(255));y=np.ascontiguousarray(a['target'][:,None,32:352,32:352])
        return dict(source=torch.from_numpy(x).to(device),target=torch.from_numpy(y).to(device),shift_xy=m['shift_xy'],motion_observable=m['motion_observable'],core=(96,224),parent_id=e['parent_id'],parent_sha256=e['arrays_sha256'],input_sha256=digest_array(x),noise_seed=seed)

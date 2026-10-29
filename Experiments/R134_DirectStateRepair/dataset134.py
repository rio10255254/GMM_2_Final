from rt import *
from functools import lru_cache
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
class Bank:
    def __init__(self):
        self.cfg=load(ROOT/'config/study.json');self.root=Path(PROJECT_ROOT / self.cfg['data_root']);self.manifest=load(self.root/'manifest.json');self.entries={(e['split'],e['index']):e for e in self.manifest['entries']}
        assert len(self.entries)==768
    @lru_cache(maxsize=16)
    def read(self,split,index):
        e=self.entries[(split,index)];p=self.root/e['arrays_path'];mp=self.root/e['metadata_path'];assert sha(p)==e['arrays_sha256'] and sha(mp)==e['metadata_sha256'];m=load(mp);assert not m['real_or_SEM_answers_used'] and not m['external_source_inputs']
        with np.load(p) as d:a={k:d[k] for k in ['source','noiseless','target']}
        return a,m,e
    def batch(self,split,index,device='cuda',epoch=None):
        a,m,e=self.read(split,index);source=a['source'];seed=None
        if epoch is not None:
            assert split=='train';seed=[self.cfg['noise_seed'],epoch,index];rng=np.random.default_rng(np.random.SeedSequence(seed));source=np.rint(np.clip(a['noiseless'].astype(np.float64)+rng.normal(0,m['noise_sigma_gray']/255,a['source'].shape),0,1)*255).astype(np.uint8)
        s=np.ascontiguousarray(source[:,None,32:352,32:352].astype(np.float32)/np.float32(255));target=np.ascontiguousarray(a['target'][:,None,32:352,32:352]);return dict(source=torch.from_numpy(s).to(device),target=torch.from_numpy(target).to(device),metadata=m,core=(96,224),parent=e,noise_seed=seed,input_sha256=digest(s))
    def order(self,epoch):return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'],epoch])).permutation(512)

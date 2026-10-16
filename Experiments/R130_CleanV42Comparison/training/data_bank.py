"""Same source-only scene pairs, batch four parents for a quick practical comparison."""
from functools import lru_cache
from common import *
class Bank:
    def __init__(self):
        self.cfg=load(ROOT/'config/training.json');self.root=Path(self.cfg['data_root'])
        self.entries={(e['split'],e['index']):e for e in load(self.root/'manifest.json')['entries']}
    @lru_cache(maxsize=768)
    def read(self,split,index):
        e=self.entries[(split,index)];ap=self.root/e['arrays_path'];mp=self.root/e['metadata_path']
        assert sha(ap)==e['arrays_sha256'] and sha(mp)==e['metadata_sha256']
        m=load(mp);assert m['split']==split and m['index']==index and not m['real_or_SEM_answers_used'] and not m['external_source_inputs']
        with np.load(ap) as d:a={k:d[k] for k in ['source','noiseless','target']}
        return a,m,e
    def order(self,epoch):return np.random.default_rng(np.random.SeedSequence([self.cfg['order_seed'],epoch])).permutation(512)
    def batch(self,split,indices,device,epoch=None):
        if split!='train' and epoch is not None:raise ValueError('Only training receives new noise')
        inputs=[];targets=[];metadata=[];ledger=[]
        for index in indices:
            a,m,e=self.read(split,int(index));source=a['source'];noise_seed=None
            if epoch is not None:
                noise_seed=[self.cfg['noise_seed'],int(epoch),int(index)];rng=np.random.default_rng(np.random.SeedSequence(noise_seed))
                source=np.rint(np.clip(a['noiseless'].astype(np.float64)+rng.normal(0,m['noise_sigma_gray']/255,source.shape),0,1)*255).astype(np.uint8)
            x=np.ascontiguousarray(source[:,None,32:352,32:352].astype(np.float32)/np.float32(255));y=np.ascontiguousarray(a['target'][:,None,32:352,32:352])
            inputs.append(x);targets.append(y);metadata.append(m);ledger.append(dict(parent_id=m['parent_id'],index=int(index),source_arrays_sha256=e['arrays_sha256'],actual_input_sha256=hashlib.sha256(x.tobytes()).hexdigest(),noise_seed=noise_seed))
        return dict(source=torch.from_numpy(np.concatenate(inputs)).to(device),target=torch.from_numpy(np.concatenate(targets)).to(device),metadata=metadata,ledger=ledger,core=(96,224))

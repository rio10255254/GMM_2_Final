"""Control A preserves R118, B consumes actual physical sequence arrays."""
from collections import OrderedDict
from pathlib import Path
import json
import numpy as np
import torch
from training.base import Scenes as BaseScenes, FamilyOrder, flatten, fine_reliability
ROOT=Path(__file__).resolve().parents[1]


class Scenes(BaseScenes):
    def __init__(self,split='train',epoch=0,limit=0,arm='A',data_seed=None,sequence_root=None):
        super().__init__(split,epoch,limit)
        from training.base import CONFIG
        if data_seed is not None and data_seed!=CONFIG['seed']:
            raise ValueError('data seed must match the locked config; never silently ignore it')
        if arm not in ('A','B'):raise ValueError(arm)
        self.arm=arm
        self.sequence_root=Path(sequence_root or ROOT/'data/sequences/train')
        self.entries={}
        self.cache=OrderedDict()
        # Validation always uses the identical baseline view generation.
        if arm=='B' and split=='train':
            manifest=json.loads((self.sequence_root/'manifest.json').read_text())
            if manifest['status']!='complete' or manifest['split']!='train':raise ValueError('sequence bank not training')
            self.entries={r['scene_index']:r for r in manifest['records']}
    def bank(self,record):
        sid=record['scene_index']
        if sid not in self.cache:
            with np.load(self.sequence_root/self.entries[sid]['file']) as saved:
                self.cache[sid]={k:saved[k] for k in saved.files}
            coverage_path=self.sequence_root/'coverage_v2'/self.entries[sid]['file']
            if not coverage_path.is_file():
                raise FileNotFoundError(f'corrected coverage sidecar required: {coverage_path}')
            with np.load(coverage_path) as corrected:
                coverage=corrected['mask']
                if coverage.shape!=self.cache[sid]['mask'].shape or coverage.dtype!=np.uint8:
                    raise ValueError('invalid corrected coverage')
                self.cache[sid]['mask']=coverage
            if len(self.cache)>2:self.cache.popitem(last=False)
        return self.cache[sid]
    def __getitem__(self,i):
        r=self.records[i]
        if self.arm=='A' or self.split!='train' or r['scene_index'] not in self.entries:
            return super().__getitem__(i)
        saved=self.bank(r)
        # Once every fourth epoch, static repetitions at a fixed phase.
        # Other epochs walk known x/y/diagonal subpixel phases deterministically.
        index=1+(self.epoch+r['scene_index'])%(len(saved['xy'])-1)
        indexes=[index,index] if self.epoch%4==0 else [0,index]
        from training.base import CONFIG
        rng=np.random.default_rng(CONFIG['seed']+r['scene_index']*1009+self.epoch*7919)
        gain=float(rng.uniform(.8,1.15));offset=float(rng.uniform(-.03,.03))
        noise=float(rng.uniform(*CONFIG['data']['noise_sigma_gray']))/255
        sources=[];targets=[];reliability=[]
        for n in indexes:
            target=np.clip(gain*saved['target'][n].astype(np.float32)/255+offset,0,1)
            source=np.clip(gain*saved['source'][n].astype(np.float32)+offset,0,1)
            if r['role']=='identity':source=target.copy();weight=np.ones_like(source)
            else:
                weight=fine_reliability(source,target,noise)
                source+=rng.normal(0,noise,source.shape).astype(np.float32)
                source+=rng.normal(0,noise*.15,(source.shape[0],1)).astype(np.float32)
                source+=rng.normal(0,noise*.1,(1,source.shape[1])).astype(np.float32)
            sources.append(np.clip(source,0,1));targets.append(target);reliability.append(weight)
        tensor=lambda a:torch.from_numpy(np.stack(a))[:,None]
        return {'source':tensor(sources),'target':tensor(targets),'fine_reliability':tensor(reliability),
            'sdf':torch.from_numpy(saved['sdf'][indexes].astype(np.float32))[:,None],
            'mask':torch.from_numpy(saved['mask'][indexes].astype(np.float32)/255)[:,None],
            'identity':torch.tensor([r['role']=='identity']*2),'flat':torch.tensor([False]*2),
            'shift_xy':torch.from_numpy(saved['xy'][indexes[1]]-saved['xy'][indexes[0]]),
            'scene_index':r['scene_index'],'role':r['role'],'family':r['family']}

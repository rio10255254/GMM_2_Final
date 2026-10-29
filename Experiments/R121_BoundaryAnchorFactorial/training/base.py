"""Two physical views with dedicated identity scenes; no appended clear view."""
from pathlib import Path
import json
import math
from collections import defaultdict
import numpy as np
import cv2
import torch
from torch.utils.data import Dataset,Sampler
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'config/experiment.json').read_text())

def fine_reliability(clean_observation,target,noise_sigma):
    """Keep denoising supervision; reduce demands for optically erased texture.

    This map is synthetic supervision only, never an input to the deployed model.
    """
    target_fine=target-cv2.GaussianBlur(target,(0,0),.8)
    source_fine=clean_observation-cv2.GaussianBlur(clean_observation,(0,0),.8)
    target_power=cv2.GaussianBlur(target_fine*target_fine,(0,0),1.6)
    source_power=cv2.GaussianBlur(source_fine*source_fine,(0,0),1.6)
    variance=float(noise_sigma)**2+1e-9
    target_present=target_power/(target_power+variance)
    source_visible=source_power/(source_power+variance)
    return np.clip(1-target_present*(1-source_visible),0,1).astype(np.float32)

class Scenes(Dataset):
    def __init__(self,split='train',epoch=0,limit=0,distance_orientation=None):
        self.package=PROJECT_ROOT/CONFIG['data']['package_root']
        self.records=[r for r in json.loads((self.package/'manifest.json').read_text())['records'] if r['split']==split]
        if limit:self.records=self.records[:limit]
        self.epoch=epoch;self.split=split
        self.distance_orientation=distance_orientation or CONFIG['data']['distance_orientation']
    def __len__(self):return len(self.records)
    def __getitem__(self,i):
        r=self.records[i];rng=np.random.default_rng(CONFIG['seed']+r['scene_index']*1009+self.epoch*7919)
        inputs=[];targets=[];sdfs=[];masks=[];reliability=[]
        for suffix in ('a','b'):
            # Exposure can differ across observations; each view's reference
            # shares that exposure, so only geometry is required to agree.
            gain=float(rng.uniform(.8,1.15)) if self.split=='train' else 1.
            offset=float(rng.uniform(-.03,.03)) if self.split=='train' else 0.
            target=np.load(self.package/r['target_'+suffix]).astype(np.float32)/255
            source=np.load(self.package/r['source_'+suffix]).astype(np.float32)
            target=np.clip(gain*target+offset,0,1)
            source=np.clip(gain*source+offset,0,1)
            if r['role']=='identity':
                source=target.copy();reliability.append(np.ones_like(target))
            else:
                noise=float(rng.uniform(*CONFIG['data']['noise_sigma_gray']))/255
                reliability.append(fine_reliability(source,target,noise))
                source+=rng.normal(0,noise,source.shape).astype(np.float32)
                source+=rng.normal(0,noise*.15,(source.shape[0],1)).astype(np.float32)
                source+=rng.normal(0,noise*.1,(1,source.shape[1])).astype(np.float32)
            inputs.append(np.clip(source,0,1));targets.append(target)
            sdf=np.load(self.package/r['sdf_'+suffix]).astype(np.float32)
            # Distance sign and normal orientation change together. A dark
            # object's sign is reversed in supervision, without an oracle
            # polarity input at deployment.
            if self.distance_orientation=='photometric':sdf=sdf*r['polarity']
            sdfs.append(sdf)
            masks.append(np.load(self.package/r['mask_'+suffix]).astype(np.float32)/255)
        to_tensor=lambda v:torch.from_numpy(np.stack(v))[:,None]
        return {'source':to_tensor(inputs),'target':to_tensor(targets),'sdf':to_tensor(sdfs),'mask':to_tensor(masks),'fine_reliability':to_tensor(reliability),
                'identity':torch.tensor([r['role']=='identity']*2),'flat':torch.tensor([r['role']=='flat_negative']*2),
                'shift_xy':torch.tensor([r['pair_dx_px'],r['pair_dy_px']],dtype=torch.float32),
                'scene_index':r['scene_index'],'family':r['family'],'role':r['role']}

class FamilyOrder(Sampler):
    """Consume each scene exactly once, mixing families without duplication."""
    def __init__(self,dataset,seed):self.dataset=dataset;self.seed=seed
    def __len__(self):return len(self.dataset)
    def __iter__(self):
        rng=np.random.default_rng(self.seed);groups=defaultdict(list)
        for i,r in enumerate(self.dataset.records):groups[r['family']].append(i)
        for values in groups.values():rng.shuffle(values)
        while groups:
            names=list(groups);rng.shuffle(names)
            for name in names:
                yield groups[name].pop()
                if not groups[name]:del groups[name]

def flatten(batch,device):
    result={}
    for key in ('source','target','sdf','mask','fine_reliability'):
        result[key]=batch[key].flatten(0,1).to(device,non_blocking=True)
    for key in ('identity','flat'):result[key]=batch[key].flatten().to(device)
    result['shift_xy']=batch['shift_xy'].to(device)
    result['scenes']=batch['source'].shape[0]
    return result

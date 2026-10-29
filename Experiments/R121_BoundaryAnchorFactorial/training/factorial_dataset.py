"""Four-arm dataset: corrected R120 control and independent affine radiometry."""
from pathlib import Path
import numpy as np
import torch
from training.dataset import Scenes as ControlScenes
from training.base import CONFIG,FamilyOrder,flatten,fine_reliability
PROJECT_ROOT = Path(__file__).resolve().parents[3]

class Scenes(ControlScenes):
    def __init__(self,split='train',epoch=0,limit=0,arm='A',**kwargs):
        if arm not in ['A','B','C','D']:raise ValueError(arm)
        self.factorial_arm=arm
        super().__init__(split,epoch,limit,arm='B',**kwargs)

    def __getitem__(self,index):
        if self.factorial_arm in ['A','C'] or self.split!='train':return super().__getitem__(index)
        record=self.records[index];sid=record['scene_index']
        rng=np.random.default_rng(CONFIG['seed']+sid*1009+self.epoch*7919)
        photo=np.random.default_rng(1211001+sid*1013+self.epoch*7927)
        physical=sid in self.entries
        if physical:
            bank=self.bank(record);phase=1+(self.epoch+sid)%(len(bank['xy'])-1)
            indexes=[phase,phase] if self.epoch%4==0 else [0,phase]
            target=[bank['target'][i].astype(np.float32)/255 for i in indexes]
            source=[bank['source'][i].astype(np.float32) for i in indexes]
            sdf=bank['sdf'][indexes].astype(np.float32);mask=bank['mask'][indexes].astype(np.float32)/255
            delta=bank['xy'][indexes[1]]-bank['xy'][indexes[0]]
            # Consume the same original RNG draws; only affine radiometry changes.
            rng.uniform(.8,1.15);rng.uniform(-.03,.03);shared_noise=float(rng.uniform(*CONFIG['data']['noise_sigma_gray']))/255
        else:
            package=Path(PROJECT_ROOT / CONFIG['data']['package_root'])
            target=[np.load(package/record['target_'+side]).astype(np.float32)/255 for side in ['a','b']]
            source=[np.load(package/record['source_'+side]).astype(np.float32) for side in ['a','b']]
            sdf=np.stack([np.load(package/record['sdf_'+s]).astype(np.float32) for s in ['a','b']])
            mask=np.stack([np.load(package/record['mask_'+s]).astype(np.float32)/255 for s in ['a','b']])
            delta=np.array([record['pair_dx_px'],record['pair_dy_px']],np.float32)
        def affine(images):
            minimum=min(float(a.min()) for a in images);maximum=max(float(a.max()) for a in images)
            midpoint=float(photo.uniform(.12,.88))
            upper=min(.70,2*(midpoint-.03),2*(.97-midpoint))
            contrast=float(photo.uniform(.08,max(.081,upper)))
            if maximum-minimum<.02:
                return 1.,midpoint-(minimum+maximum)/2
            gain=contrast/(maximum-minimum)
            return gain,midpoint-gain*(minimum+maximum)/2
        common=affine(target) if physical else None
        inputs=[];targets=[];reliability=[]
        for side in range(2):
            if physical:gain,offset=common;noise=shared_noise
            else:
                rng.uniform(.8,1.15);rng.uniform(-.03,.03)
                gain,offset=affine([target[side]])
                noise=float(rng.uniform(*CONFIG['data']['noise_sigma_gray']))/255 if record['role']!='identity' else 0.
            truth=(gain*target[side]+offset).astype(np.float32)
            clean=(gain*source[side]+offset).astype(np.float32)
            # Affine transform commutes with normalized linear optics. No dilation,
            # target motion change, SEM shape or fitted real-pillar shrink enters.
            if truth.min()<-.00001 or truth.max()>1.00001:raise ValueError('unexpected reference clipping')
            if record['role']=='identity':clean=truth.copy();weight=np.ones_like(clean)
            else:
                weight=fine_reliability(clean,truth,noise)
                clean+=rng.normal(0,noise,clean.shape).astype(np.float32)
                clean+=rng.normal(0,noise*.15,(clean.shape[0],1)).astype(np.float32)
                clean+=rng.normal(0,noise*.1,(1,clean.shape[1])).astype(np.float32)
            inputs.append(np.clip(clean,0,1));targets.append(truth);reliability.append(weight)
        tensor=lambda a:torch.from_numpy(np.stack(a))[:,None]
        return {'source':tensor(inputs),'target':tensor(targets),'fine_reliability':tensor(reliability),
                'sdf':torch.from_numpy(sdf)[:,None],'mask':torch.from_numpy(mask)[:,None],
                'identity':torch.tensor([record['role']=='identity']*2),'flat':torch.tensor([record['role']=='flat_negative']*2),
                'shift_xy':torch.from_numpy(delta),'scene_index':sid,'role':record['role'],'family':record['family']}

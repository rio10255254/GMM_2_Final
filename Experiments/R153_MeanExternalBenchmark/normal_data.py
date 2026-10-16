"""Same TIFF pairs and noise formation, shuffled as ordinary independent images."""
import sys,hashlib
import numpy as np
import torch
from study import PACK,training_config
if str(PACK) not in sys.path:sys.path.insert(0,str(PACK))
from core.dataset import Bank
from normal_protocol import COMMON


class ImagePairs:
    def __init__(self,preload=True):
        self.bank=Bank(training_config())
        self.train=[]
        if preload:
            for i in range(512):
                arrays,_=self.bank.read('train',i)
                self.train.append({k:arrays[k] for k in ('target','noiseless','noise_sigma_gray','psf_index')})
                if (i+1)%128==0:print('TRAINING IMAGES LOADED',4*(i+1),'/2048',flush=True)
            self.bank.read.cache_clear()

    def order(self,epoch):
        return np.random.default_rng(np.random.SeedSequence([COMMON['image_order_seed'],epoch])).permutation(2048)

    def batch(self,indices,epoch,device='cuda'):
        source=[];target=[];psfs=[];noise=[]
        for flat in indices:
            parent,view=divmod(int(flat),4)
            a=self.train[parent] if self.train else self.bank.read('train',parent)[0]
            rng=np.random.default_rng(np.random.SeedSequence([COMMON['noise_seed'],0,epoch,parent,view]))
            value=a['noiseless'][view].astype(np.float64)+rng.normal(0,a['noise_sigma_gray'][view]/255,a['noiseless'][view].shape)
            source.append(np.rint(np.clip(value,0,1)*255).astype(np.uint8).astype(np.float32)/255)
            target.append(a['target'][view]);psfs.append(-2 if a['psf_index'][view]<0 else int(a['psf_index'][view]));noise.append(float(a['noise_sigma_gray'][view])/255)
        values=np.ascontiguousarray(np.stack(source)[:,None])
        return {'source':torch.from_numpy(values).to(device),'target':torch.from_numpy(np.stack(target)[:,None]).to(device),
                'actual_psf_indices':torch.tensor(psfs,device=device,dtype=torch.long),
                'noise_sigma':torch.tensor(noise,device=device,dtype=torch.float32)[:,None,None,None],
                'flat_indices':[int(i) for i in indices],
                'source_input_sha256':hashlib.sha256(values.tobytes()).hexdigest()}

"""A/C matched parameter shapes; C learns the image it actually exports."""
import torch
from torch.nn import functional as F
from .hybrid import Hybrid
from .operators import replicate_one

class Network(Hybrid):
    def __init__(self,mean,candidates,arm):
        super().__init__(mean,candidates,optical=True,aa=True);self.arm=arm
    def forward(self,raw,prior_runner=None,trace=None):
        if self.arm=='A' and prior_runner is None:return super().forward(raw)
        conditioned,_=self.optics(raw,self.optical_enabled,False)
        baseline=conditioned if self.arm=='A' else raw
        lift=lambda x,f:x.repeat_interleave(f,-2).repeat_interleave(f,-1)
        original=lift(baseline,4);state=original;o2=lift(baseline,2);p=replicate_one(baseline)
        dx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;dy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5
        lap=p[...,1:-1,2:]+p[...,1:-1,:-2]+p[...,2:,1:-1]+p[...,:-2,1:-1]-4*baseline
        mean=F.avg_pool2d(baseline,5,1,2,count_include_pad=False);fixed=[lift(v,2) for v in [dx,dy,lap,mean]]
        for i in range(4):
            native=baseline+F.avg_pool2d(state-original,4)
            # A retains old contract. C treats measured optics as a real feature,
            # while zero learned updates still export Raw exactly.
            cue=(baseline-native) if self.arm=='A' else (conditioned-native)
            features=torch.cat([F.avg_pool2d(state,2),o2,lift(cue,2),*fixed],1)
            correction=self.prior(features) if prior_runner is None else prior_runner(self.prior,features)
            state=(state+.25*torch.sigmoid(self.step_logits[i])*correction).clamp(0,1)
            if trace is not None:trace(i,state.detach().clone())
        image=(baseline+F.avg_pool2d(state-original,4)).clamp(0,1)
        return self.anchor(raw,image)[0] if self.arm=='A' else image

from .network import Network
from .staged import tiled_prior
class Hybrid(Network):
    def __init__(self,mean,candidates):super().__init__(mean,candidates,'C')
    def forward(self,raw):
        runner=(lambda p,f:tiled_prior(p,f,512,16)) if not self.training and max(raw.shape[-2:])>1024 else None
        return Network.forward(self,raw,prior_runner=runner)
    def forward_details(self,*args,**kwargs):raise NotImplementedError('Legacy diagnostics do not describe the direct-state output')

"""Synthetic diagnostics for RAW and the unchanged MOSR checkpoint."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from torch import nn
from study import save,read,RECORD
from benchmark_core import prepare,evaluate
from inference_methods import load_method


class FrozenAdapter(nn.Module):
    def __init__(self,method,model):super().__init__();self.method=method;self.model=model
    def forward(self,x,operators=None,optics=None):
        return x if self.method=='RAW' else self.model(x,operators)


def main():
    cfg,bank,optics=prepare()
    for method in ('RAW','MOSR'):
        model,_,identity=load_method(method)
        result=evaluate(FrozenAdapter(method,model),bank,optics,'test',with_image_metrics=True)
        if method=='MOSR':
            reference={'task':1.754515543,'image':1.503325612,'gradient':.989802439,
                       'pair_output':.090337211,'boundary':.114977965,'observation':1.216640898}
            for key,value in reference.items():assert abs(result['mean'][key]-value)<2e-6,(key,result['mean'][key],value)
        result.update(method=method,checkpoint_sha256=identity,original_real_reconstructions_repeated=False)
        save(ROOT/'results/synthetic'/(method+'.json'),result)
        print('FROZEN SYNTHETIC',method,result['mean'],flush=True)


if __name__=='__main__':main()

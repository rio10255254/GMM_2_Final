"""Same V42 arithmetic with deterministic reflection and bilinear backward."""
import torch
from torch import nn
from torch.nn import functional as native
from bilinear_adjoint import Bilinear2x
def pad(x,padding,mode='constant',value=None):
    if mode!='reflect':return native.pad(x,padding,mode=mode,value=value)
    left,right,top,bottom=padding
    if left or right:
        parts=[]
        if left:parts.append(x[...,1:left+1].flip(-1))
        parts.append(x)
        if right:parts.append(x[...,-right-1:-1].flip(-1))
        x=torch.cat(parts,-1)
    if top or bottom:
        parts=[]
        if top:parts.append(x[...,1:top+1,:].flip(-2))
        parts.append(x)
        if bottom:parts.append(x[...,-bottom-1:-1,:].flip(-2))
        x=torch.cat(parts,-2)
    return x
class Functional:
    pad=staticmethod(pad)
    def __getattr__(self,name):return getattr(native,name)
functional=Functional()
class ReflectPad(nn.Module):
    def __init__(self,size):super().__init__();self.size=size
    def forward(self,x):return pad(x,(self.size,)*4,'reflect')
class BilinearUpsample2x(nn.Module):
    def forward(self,x):return Bilinear2x.apply(x)

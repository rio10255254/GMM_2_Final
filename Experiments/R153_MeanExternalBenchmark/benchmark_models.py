"""Author architectures with explicit import, grayscale and x1 adapters only."""
from __future__ import annotations
import ast
from functools import lru_cache
from pathlib import Path
from types import ModuleType,SimpleNamespace,MethodType
import sys,hashlib
import torch
from torch import nn
from torch.utils.checkpoint import checkpoint
from study import ROOT,PACK,read,sha

SPECS={
 'EDSR-x1':{'family':'residual CNN','variant':'author EDSR baseline','n_resblocks':16,'n_feats':64,'res_scale':1},
 'RDN-x1':{'family':'dense feature fusion CNN','variant':'author-linked PyTorch configuration A','G0':64,'D':20,'C':6,'G':32},
 'RCAN-x1':{'family':'channel attention CNN','variant':'author G10R20','n_resgroups':10,'n_resblocks':20,'n_feats':64,'reduction':16},
 'NAFNet':{'family':'image restoration CNN','variant':'author GoPro width32 with TLC','width':32,'enc_blk_nums':[1,1,1,28],'middle_blk_num':1,'dec_blk_nums':[1,1,1,1]},
 'SwinIR':{'family':'window Transformer','variant':'author grayscale denoising','embed_dim':180,'depths':[6,6,6,6,6,6],'num_heads':[6,6,6,6,6,6],'window_size':8,'mlp_ratio':2},
 'Restormer':{'family':'restoration Transformer','variant':'author Gaussian grayscale architecture','dim':48,'num_blocks':[4,6,6,8],'num_refinement_blocks':4,'heads':[1,2,4,8],'ffn_expansion_factor':2.66,'LayerNorm_type':'BiasFree'},
 'USRNet-x1':{'family':'PSF deep unfolding','variant':'author full model','n_iter':8,'h_nc':64,'nc':[64,128,256,512],'nb':2,'sigma_gray':1.5},
}
ADAPTATIONS={
 'EDSR-x1':['Author scale=1 identity upsampler; one input/output channel.','RGB fixed mean is replaced by fixed grayscale mean 0.5; no per-image normalization.'],
 'RDN-x1':['RDN author README links this EDSR-PyTorch implementation.','Enable r=1 in the existing r=2/3 tail branch; PixelShuffle(1) is identity. One input/output channel.'],
 'RCAN-x1':['Author scale=1 identity upsampler; one input/output channel.','RGB fixed mean is replaced by fixed grayscale mean 0.5; no per-image normalization.'],
 'NAFNet':['Author NAFNetLocal, grayscale channels and train_size=(1,1,384,384).','Only package imports are redirected; official LayerNorm and local-pooling implementations retained.'],
 'SwinIR':['Native author grayscale denoising head: scale=1, no upsampler, image range 1.','Official checkpointing is enabled for training memory; full architecture retained.'],
 'Restormer':['Native official grayscale input/output configuration; all blocks retained.'],
 'USRNet-x1':['Use author network_usrnet_v1 for modern torch.fft; scale factor 1 is native.','Grayscale prior has 2 input channels (image and noise map), 1 output channel.','Training kernel follows the common known/mean operator selection; evaluation uses mean PSF.','Sigma input fixed at 1.5 gray / 255; no true test noise metadata or per-image tuning.'],
}


@lru_cache(maxsize=None)
def load_module(name,relative,replacements=(),selected_classes=()):
    path=ROOT/'vendor'/relative
    source=path.read_text(encoding='utf-8')
    if selected_classes:
        nodes={n.name:n for n in ast.parse(source).body if isinstance(n,ast.ClassDef)}
        source='import torch\nimport numpy as np\nfrom torch import nn\n\n'+'\n\n'.join(ast.get_source_segment(source,nodes[n]) for n in selected_classes)
    for before,after in replacements:
        if before not in source:raise RuntimeError('Expected author source text missing: '+before)
        source=source.replace(before,after)
    module=ModuleType('_mosr_benchmark_'+name)
    module.__file__=str(path)
    sys.modules[module.__name__]=module
    exec(compile(source,str(path),'exec'),module.__dict__)
    return module


def checkpoint_module(module):
    original=module.forward
    def forward(*args,**kwargs):
        if module.training and torch.is_grad_enabled():
            return checkpoint(original,*args,use_reentrant=False,**kwargs)
        return original(*args,**kwargs)
    module.forward=forward


def fixed_gray_shift(sign):
    layer=nn.Conv2d(1,1,1)
    with torch.no_grad():layer.weight.fill_(1);layer.bias.fill_(sign*.5)
    for parameter in layer.parameters():parameter.requires_grad_(False)
    return layer


class ImageModel(nn.Module):
    def __init__(self,name,net,checkpoint_training=True):
        super().__init__();self.name=name;self.net=net
        if checkpoint_training:
            classes={'EDSR-x1':{'ResBlock'},'RDN-x1':{'RDB'},'RCAN-x1':{'ResidualGroup'},
                     'NAFNet':{'NAFBlock'},'Restormer':{'TransformerBlock'},'USRNet-x1':{'ResUNet'}}.get(name,set())
            for module in net.modules():
                if type(module).__name__ in classes:checkpoint_module(module)

    def forward(self,image,operators=None,optics=None,noise_sigma=None):
        if self.name=='USRNet-x1':
            if optics is None:raise ValueError('USRNet requires the common PSF operator')
            if operators is None:operators=torch.full((image.shape[0],),-1,device=image.device,dtype=torch.long)
            identity=torch.zeros_like(optics.mean_kernel);identity[...,50,50]=1
            kernels=torch.cat([identity if int(i)==-2 else optics.mean_kernel if int(i)<0 else optics.bank[int(i):int(i)+1] for i in operators],0)
            sigma=noise_sigma if noise_sigma is not None else torch.full((image.shape[0],1,1,1),SPECS[self.name]['sigma_gray']/255,device=image.device,dtype=torch.float32)
            return self.net(image,kernels,1,sigma)
        return self.net(image)


def make_model(name,checkpoint_training=True):
    global edsr_common,rcan_common,naf_norm,naf_local,usr_basicblock
    if name=='EDSR-x1':
        edsr_common=load_module('edsr_common','EDSR/src/model/common.py')
        module=load_module('edsr','EDSR/src/model/edsr.py',(('from model import common','from benchmark_models import edsr_common as common'),))
        cfg=SPECS[name]
        net=module.EDSR(SimpleNamespace(n_resblocks=cfg['n_resblocks'],n_feats=cfg['n_feats'],scale=[1],n_colors=1,rgb_range=1,res_scale=cfg['res_scale']))
        net.sub_mean=fixed_gray_shift(-1);net.add_mean=fixed_gray_shift(1)
    elif name=='RDN-x1':
        edsr_common=load_module('edsr_common','EDSR/src/model/common.py')
        module=load_module('rdn','EDSR/src/model/rdn.py',(('from model import common','from benchmark_models import edsr_common as common'),
                                                       ('if r == 2 or r == 3:','if r in (1, 2, 3):')))
        net=module.RDN(SimpleNamespace(scale=[1],G0=64,RDNkSize=3,RDNconfig='A',n_colors=1))
    elif name=='RCAN-x1':
        rcan_common=load_module('rcan_common','RCAN/RCAN_TrainCode/code/model/common.py')
        module=load_module('rcan','RCAN/RCAN_TrainCode/code/model/rcan.py',(('from model import common','from benchmark_models import rcan_common as common'),))
        cfg=SPECS[name]
        net=module.RCAN(SimpleNamespace(n_resgroups=10,n_resblocks=20,n_feats=64,reduction=16,scale=[1],n_colors=1,rgb_range=1,res_scale=1))
        net.sub_mean=fixed_gray_shift(-1);net.add_mean=fixed_gray_shift(1)
    elif name=='NAFNet':
        naf_norm=load_module('naf_norm','NAFNet/basicsr/models/archs/arch_util.py',selected_classes=('LayerNormFunction','LayerNorm2d'))
        naf_local=load_module('naf_local','NAFNet/basicsr/models/archs/local_arch.py')
        module=load_module('nafnet','NAFNet/basicsr/models/archs/NAFNet_arch.py',(
            ('from basicsr.models.archs.arch_util import LayerNorm2d','from benchmark_models import naf_norm\nLayerNorm2d = naf_norm.LayerNorm2d'),
            ('from basicsr.models.archs.local_arch import Local_Base','from benchmark_models import naf_local\nLocal_Base = naf_local.Local_Base')))
        net=module.NAFNetLocal(img_channel=1,width=32,enc_blk_nums=[1,1,1,28],middle_blk_num=1,dec_blk_nums=[1,1,1,1],train_size=(1,1,384,384),fast_imp=False)
    elif name=='SwinIR':
        module=load_module('swinir','SwinIR/models/network_swinir.py')
        net=module.SwinIR(upscale=1,in_chans=1,img_size=128,window_size=8,img_range=1,
                         depths=[6,6,6,6,6,6],embed_dim=180,num_heads=[6,6,6,6,6,6],
                         mlp_ratio=2,upsampler='',resi_connection='1conv',use_checkpoint=checkpoint_training)
    elif name=='Restormer':
        module=load_module('restormer','Restormer/basicsr/models/archs/restormer_arch.py')
        net=module.Restormer(inp_channels=1,out_channels=1,dim=48,num_blocks=[4,6,6,8],
                            num_refinement_blocks=4,heads=[1,2,4,8],ffn_expansion_factor=2.66,
                            bias=False,LayerNorm_type='BiasFree',dual_pixel_task=False)
    elif name=='USRNet-x1':
        usr_basicblock=load_module('usr_basicblock','USRNet/models/basicblock.py')
        module=load_module('usrnet','USRNet/models/network_usrnet_v1.py',(
            ('import models.basicblock as B','from benchmark_models import usr_basicblock as B'),
            ('from utils import utils_image as util','# Unused author demo/image utility import omitted.')))
        net=module.USRNet(n_iter=8,h_nc=64,in_nc=2,out_nc=1,nc=[64,128,256,512],nb=2,act_mode='R',downsample_mode='strideconv',upsample_mode='convtranspose')
    else:
        raise ValueError('No executable official adapter for '+name)
    return ImageModel(name,net,checkpoint_training)

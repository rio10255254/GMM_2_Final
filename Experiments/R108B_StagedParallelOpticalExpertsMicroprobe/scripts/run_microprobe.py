"""Run the complete R108B two-dimensional microprobe."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from scipy.ndimage import label as component_label
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULT = ROOT / "results"
WEIGHTS = ROOT / "weights"
REPORT = ROOT / "reports" / "R108B_RESULTS_ZH.md"
for folder in (DATA_DIR, RESULT, WEIGHTS, REPORT.parent): folder.mkdir(parents=True, exist_ok=True)
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
SIZE = 128
SUPER = 4
ROLES = ["edge", "texture", "denoise", "illumination", "identity", "mixed"]
TRAIN_FAMILIES = ["circle", "ellipse", "rectangle", "polygon", "lobed", "ring"]
HOLDOUT_FAMILIES = ["crescent", "thin_neck", "rough", "mixed_array"]
REAL_IMAGES = [
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\5x_dense_raw.bmp"),
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\20x_mixed_raw.bmp"),
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\50x_array_raw.bmp"),
    Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\pillar_center9_50x_raw.bmp"),
]


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):h.update(block)
    return h.hexdigest()


def polygon_points(rng: np.random.Generator, center: tuple[float,float], radius: float, count: int, rough: float=0.20):
    angles=np.sort(rng.uniform(0,2*np.pi,count));radii=radius*(1+rng.uniform(-rough,rough,count))
    return np.round(np.stack([center[0]+radii*np.cos(angles),center[1]+radii*np.sin(angles)],axis=1)).astype(np.int32)


def draw_mask(family: str, rng: np.random.Generator, side: int) -> np.ndarray:
    mask=np.zeros((side,side),np.uint8);cx=float(rng.uniform(.32,.68)*side);cy=float(rng.uniform(.32,.68)*side);radius=float(rng.uniform(.15,.28)*side)
    if family=="circle":cv2.circle(mask,(round(cx),round(cy)),round(radius),255,-1,cv2.LINE_AA)
    elif family=="ellipse":cv2.ellipse(mask,(round(cx),round(cy)),(round(radius),round(radius*rng.uniform(.45,.85))),float(rng.uniform(0,180)),0,360,255,-1,cv2.LINE_AA)
    elif family=="rectangle":
        rect=((cx,cy),(radius*2,radius*rng.uniform(1.0,1.8)),float(rng.uniform(0,180)));cv2.fillConvexPoly(mask,np.round(cv2.boxPoints(rect)).astype(np.int32),255,cv2.LINE_AA)
    elif family in ("polygon","rough"):
        points=polygon_points(rng,(cx,cy),radius,int(rng.integers(5,10)),.16 if family=="polygon" else .42);cv2.fillPoly(mask,[points],255,cv2.LINE_AA)
    elif family=="lobed":
        angles=np.linspace(0,2*np.pi,96,endpoint=False);lobes=int(rng.integers(3,7));phase=float(rng.uniform(0,2*np.pi));rad=radius*(1+.18*np.cos(lobes*angles+phase));pts=np.round(np.stack([cx+rad*np.cos(angles),cy+rad*np.sin(angles)],1)).astype(np.int32);cv2.fillPoly(mask,[pts],255,cv2.LINE_AA)
    elif family=="ring":
        cv2.circle(mask,(round(cx),round(cy)),round(radius),255,-1,cv2.LINE_AA);cv2.circle(mask,(round(cx),round(cy)),round(radius*rng.uniform(.42,.68)),0,-1,cv2.LINE_AA)
    elif family=="crescent":
        cv2.circle(mask,(round(cx),round(cy)),round(radius),255,-1,cv2.LINE_AA);cv2.circle(mask,(round(cx+radius*.40),round(cy-radius*.08)),round(radius*.82),0,-1,cv2.LINE_AA)
    elif family=="thin_neck":
        dx=radius*.72;cv2.circle(mask,(round(cx-dx),round(cy)),round(radius*.66),255,-1,cv2.LINE_AA);cv2.circle(mask,(round(cx+dx),round(cy)),round(radius*.66),255,-1,cv2.LINE_AA);cv2.rectangle(mask,(round(cx-dx),round(cy-radius*.18)),(round(cx+dx),round(cy+radius*.18)),255,-1)
    elif family=="mixed_array":
        for row in range(3):
            for col in range(3):
                x=int((.25+col*.25)*side+rng.uniform(-.02,.02)*side);y=int((.25+row*.25)*side+rng.uniform(-.02,.02)*side);cv2.circle(mask,(x,y),int(radius*.28),255,-1,cv2.LINE_AA)
    else:raise ValueError(family)
    return mask


def low_field(rng: np.random.Generator, side: int) -> np.ndarray:
    yy,xx=np.mgrid[0:side,0:side].astype(np.float32);angle=float(rng.uniform(0,2*np.pi));plane=(np.cos(angle)*(xx-side/2)+np.sin(angle)*(yy-side/2))/side
    coarse=rng.normal(0,1,(8,8)).astype(np.float32);field=cv2.resize(coarse,(side,side),interpolation=cv2.INTER_CUBIC);field=cv2.GaussianBlur(field,(0,0),side/18)
    field=.55*plane+.45*field/max(float(field.std()),1e-6);return field/max(float(np.max(np.abs(field))),1e-6)


def render_scene(family: str, role: str, rng: np.random.Generator, severe: bool) -> dict[str,np.ndarray|float|str]:
    high=SIZE*SUPER;mask_hr=draw_mask(family,rng,high).astype(np.float32)/255.0
    background=float(rng.uniform(.10,.88));maximum=max(background-.04,.96-background);sign=1 if rng.random()<.5 else -1
    if (sign<0 and background<.28) or (sign>0 and background>.72):sign=-sign
    available=background-.03 if sign<0 else .97-background;contrast=float(rng.uniform(.18,min(.68,max(.19,available))))
    foreground=background+sign*contrast
    yy,xx=np.mgrid[0:high,0:high].astype(np.float32);texture=np.zeros_like(mask_hr)
    if role in ("texture","mixed"):
        for _ in range(2):
            period=float(rng.uniform(6,22)*SUPER);angle=float(rng.uniform(0,2*np.pi));phase=float(rng.uniform(0,2*np.pi));texture+=np.sin(2*np.pi*(xx*np.cos(angle)+yy*np.sin(angle))/period+phase)
        texture*=float(rng.uniform(.008,.035));texture*=.35+.65*mask_hr
    latent=background+(foreground-background)*mask_hr+texture
    latent=cv2.GaussianBlur(latent,(0,0),.28*SUPER,borderType=cv2.BORDER_REFLECT_101)
    target=cv2.resize(latent,(SIZE,SIZE),interpolation=cv2.INTER_AREA).astype(np.float32)
    mask=cv2.resize(mask_hr,(SIZE,SIZE),interpolation=cv2.INTER_AREA).astype(np.float32)
    if role=="identity":blur=float(rng.uniform(0,.18));noise=float(rng.uniform(0,.0012));illum=ghost=halo=0.0
    elif role=="denoise":blur=float(rng.uniform(0,.35));noise=float(rng.uniform(.008,.030 if not severe else .045));illum=ghost=halo=0.0
    elif role=="edge":blur=float(rng.uniform(.8,2.8 if not severe else 3.8));noise=float(rng.uniform(.001,.012));illum=float(rng.uniform(0,.025));ghost=halo=0.0
    elif role=="texture":blur=float(rng.uniform(.7,2.2 if not severe else 3.0));noise=float(rng.uniform(.003,.020));illum=float(rng.uniform(0,.02));ghost=halo=0.0
    elif role=="illumination":blur=float(rng.uniform(.4,1.6));noise=float(rng.uniform(.002,.012));illum=float(rng.uniform(.04,.16 if not severe else .25));ghost=float(rng.uniform(0,.04));halo=float(rng.uniform(-.05,.05))
    else:blur=float(rng.uniform(.8,3.0 if not severe else 4.0));noise=float(rng.uniform(.005,.028 if not severe else .045));illum=float(rng.uniform(.02,.14 if not severe else .24));ghost=float(rng.uniform(0,.10 if not severe else .18));halo=float(rng.uniform(-.10,.10 if not severe else .18))
    clean=cv2.GaussianBlur(target,(0,0),blur,borderType=cv2.BORDER_REFLECT_101) if blur>0 else target.copy()
    if ghost:
        matrix=np.asarray([[1,0,float(rng.uniform(-1.7,1.7))],[0,1,float(rng.uniform(-1.7,1.7))]],np.float32);shifted=cv2.warpAffine(clean,matrix,(SIZE,SIZE),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101);clean=(1-ghost)*clean+ghost*shifted
    if halo:
        broad=cv2.GaussianBlur(clean,(0,0),4.0,borderType=cv2.BORDER_REFLECT_101);clean=clean+halo*(broad-clean)
    field=low_field(rng,SIZE);base=np.clip(clean+illum*field,0,1)
    source1=np.clip(base+rng.normal(0,noise,(SIZE,SIZE)).astype(np.float32),0,1)
    source2=np.clip(base+rng.normal(0,noise,(SIZE,SIZE)).astype(np.float32),0,1)
    edge=cv2.morphologyEx((mask>.5).astype(np.uint8),cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8)).astype(np.float32);edge=cv2.GaussianBlur(edge,(0,0),1.3);edge=np.clip(edge,0,1)
    return {"source1":source1,"source2":source2,"target":target,"mask":mask,"edge":edge,"midpoint":.5*(background+foreground),"polarity":float(sign),"role":role,"family":family}


def generate_split(count: int, seed: int, families: list[str], severe: bool) -> dict[str,np.ndarray]:
    rng=np.random.default_rng(seed);records=[]
    for index in range(count):records.append(render_scene(families[index%len(families)],ROLES[index%len(ROLES)],rng,severe))
    result={key:np.stack([record[key] for record in records]) for key in ("source1","source2","target","mask","edge")}
    result.update({"midpoint":np.asarray([r['midpoint'] for r in records],np.float32),"polarity":np.asarray([r['polarity'] for r in records],np.float32),"role":np.asarray([ROLES.index(r['role']) for r in records],np.int64),"family":np.asarray([r['family'] for r in records])})
    for key in ("source1","source2","target","mask","edge"):result[key]=np.round(np.clip(result[key],0,1)*255).astype(np.uint8)
    return result


def prepare_data() -> dict[str,dict[str,np.ndarray]]:
    path=DATA_DIR/"microprobe_data.npz"
    if path.exists():
        loaded=np.load(path,allow_pickle=False);splits={}
        for split in ("train","validation","holdout"):splits[split]={key:loaded[f"{split}_{key}"] for key in ("source1","source2","target","mask","edge","midpoint","polarity","role","family")}
        return splits
    splits={"train":generate_split(384,108801,TRAIN_FAMILIES,False),"validation":generate_split(96,108802,TRAIN_FAMILIES,False),"holdout":generate_split(96,108803,HOLDOUT_FAMILIES,True)}
    payload={f"{split}_{key}":value for split,data in splits.items() for key,value in data.items()};np.savez_compressed(path,**payload)
    manifest={"status":"complete","counts":{k:len(v['source1']) for k,v in splits.items()},"train_families":TRAIN_FAMILIES,"holdout_families":HOLDOUT_FAMILIES,"roles":ROLES,"real_training_pixels":False,"old_checkpoint_or_teacher":False,"sha256":sha256(path)};(DATA_DIR/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding='utf-8');return splits


def tensor_data(data: dict[str,np.ndarray]) -> dict[str,torch.Tensor]:
    out={}
    for key in ("source1","source2","target","mask","edge"):out[key]=torch.from_numpy(data[key].astype(np.float32)/255.0).unsqueeze(1).to(DEVICE)
    for key in ("midpoint","polarity"):out[key]=torch.from_numpy(data[key]).to(DEVICE)
    out['role']=torch.from_numpy(data['role']).to(DEVICE);return out


class Blur(nn.Module):
    def __init__(self,sigma:float):
        super().__init__();radius=max(1,int(math.ceil(3*sigma)));axis=torch.arange(-radius,radius+1,dtype=torch.float32);row=torch.exp(-.5*(axis/sigma)**2);row/=row.sum();self.register_buffer('h',row.view(1,1,1,-1));self.register_buffer('v',row.view(1,1,-1,1));self.radius=radius
    def forward(self,x):
        mode='reflect' if x.shape[-1]>self.radius and x.shape[-2]>self.radius else 'replicate';value=F.conv2d(F.pad(x,(self.radius,self.radius,0,0),mode=mode),self.h.to(x.dtype));return F.conv2d(F.pad(value,(0,0,self.radius,self.radius),mode=mode),self.v.to(x.dtype))


class ResBlock(nn.Module):
    def __init__(self,c:int,d:int=1):super().__init__();self.a=nn.Conv2d(c,c,3,padding=d,dilation=d);self.b=nn.Conv2d(c,c,3,padding=d,dilation=d)
    def forward(self,x):return F.silu(x+.15*self.b(F.silu(self.a(x))))


@dataclass
class Details:
    output:torch.Tensor;proposal:torch.Tensor;total_delta:torch.Tensor;denoise_delta:torch.Tensor;edge_delta:torch.Tensor;texture_delta:torch.Tensor;radiometry_delta:torch.Tensor;gate:torch.Tensor;edge_support:torch.Tensor


class ParallelExperts(nn.Module):
    def __init__(self,joint_gate:bool=False):
        super().__init__();self.joint_gate=joint_gate;self.b05=Blur(.55);self.b09=Blur(.90);self.b16=Blur(1.6);self.b32=Blur(3.2);self.b64=Blur(6.4);self.b12=Blur(12.0)
        self.stem=nn.Sequential(nn.Conv2d(10,36,3,padding=1),nn.SiLU(),ResBlock(36),ResBlock(36,2),ResBlock(36,4),ResBlock(36,2),ResBlock(36))
        self.coeff=nn.Conv2d(36,4,1);self.gate_head=nn.Conv2d(36,1,1) if joint_gate else None
        nn.init.zeros_(self.coeff.weight);nn.init.constant_(self.coeff.bias,0.0)
        if self.gate_head is not None:nn.init.zeros_(self.gate_head.weight);nn.init.zeros_(self.gate_head.bias)
    def cues(self,x):
        b05,b09,b16,b32,b64=self.b05(x),self.b09(x),self.b16(x),self.b32(x),self.b64(x);gx=F.pad(x[:,:,:,1:]-x[:,:,:,:-1],(0,1,0,0));gy=F.pad(x[:,:,1:,:]-x[:,:,:-1,:],(0,0,0,1));mag=torch.sqrt(gx.square()+gy.square()+1e-8);scale=torch.sqrt(self.b32((x-b32).square())+(2/255)**2);relative=(mag/(scale+2/255)).clamp(0,4);edge=((relative-.22)/1.1).clamp(0,1)
        features=torch.cat([x,b05,b09,b16,b32,b64,x-b09,b05-b16,mag,(x-b32)/(3*scale+2/255)],1);return features,(b05,b09,b16,b32,b64),edge
    def forward(self,x):
        features,blurs,edge_support=self.cues(x);b05,b09,b16,b32,b64=blurs;hidden=self.stem(features);raw=self.coeff(hidden)
        denoise_strength=torch.sigmoid(raw[:,0:1]);edge_strength=2.2*torch.sigmoid(raw[:,1:2]);texture_strength=1.6*torch.tanh(raw[:,2:3]);radiometry_strength=.8*torch.tanh(raw[:,3:4])
        denoise_delta=denoise_strength*(b09-x);edge_delta=edge_support*edge_strength*(x-b16);texture_support=(1-.75*edge_support).clamp(0,1);texture_delta=texture_support*texture_strength*(b05-b32);radiometry_delta=radiometry_strength*(b64-self.b12(x));total=denoise_delta+edge_delta+texture_delta+radiometry_delta;proposal=(x+total).clamp(0,1)
        gate=torch.sigmoid(self.gate_head(hidden)) if self.gate_head is not None else torch.ones_like(x);output=(x+gate*total).clamp(0,1);return Details(output,proposal,total,denoise_delta,edge_delta,texture_delta,radiometry_delta,gate,edge_support)


class AdoptionSelector(nn.Module):
    def __init__(self):super().__init__();self.body=nn.Sequential(nn.Conv2d(4,32,5,padding=2),nn.SiLU(),ResBlock(32),ResBlock(32,2),ResBlock(32,4),ResBlock(32,2),nn.Conv2d(32,1,1))
    def forward(self,source,proposal):
        delta=proposal-source;local=F.avg_pool2d(source,9,1,4);features=torch.cat([source,proposal,delta,source-local],1);return torch.sigmoid(self.body(features))


def gradients(x):return F.pad(x[:,:,:,1:]-x[:,:,:,:-1],(0,1,0,0)),F.pad(x[:,:,1:,:]-x[:,:,:-1,:],(0,0,0,1))
def highpass(x):return x-F.avg_pool2d(F.pad(x,(2,2,2,2),mode='reflect'),5,1)


def loss_for(details:Details,source,target,edge,role,pair_output=None):
    pixel=F.smooth_l1_loss(details.output,target,beta=2/255);weight=.15+.85*edge;edge_loss=(torch.abs(details.output-target)*weight).sum()/weight.sum();pgx,pgy=gradients(details.output);tgx,tgy=gradients(target);gradient=F.smooth_l1_loss(pgx,tgx,beta=1/255)+F.smooth_l1_loss(pgy,tgy,beta=1/255);texture=F.smooth_l1_loss(highpass(details.output),highpass(target),beta=.5/255);identity_rows=role==ROLES.index('identity');identity=torch.abs(details.output[identity_rows]-source[identity_rows]).mean() if bool(identity_rows.any()) else pixel.new_zeros(());consistency=torch.abs(details.output-pair_output).mean() if pair_output is not None else pixel.new_zeros(());branch=.001*(details.edge_delta.abs().mean()+details.texture_delta.abs().mean()+details.radiometry_delta.abs().mean());total=pixel+.65*edge_loss+.25*gradient+.18*texture+.45*identity+.06*consistency+branch;return total,{"pixel":pixel,"edge":edge_loss,"gradient":gradient,"texture":texture,"identity":identity,"consistency":consistency,"branch":branch}


def train_proposal(name:str,joint_gate:bool,data:dict[str,torch.Tensor],steps:int=900):
    seed_all(108820+int(joint_gate));model=ParallelExperts(joint_gate).to(DEVICE);optimizer=torch.optim.AdamW(model.parameters(),lr=4e-4,weight_decay=2e-5);generator=torch.Generator(device=DEVICE).manual_seed(108830+int(joint_gate));trace=[];batch=18
    for step in range(1,steps+1):
        index=torch.randint(0,len(data['source1']),(batch,),device=DEVICE,generator=generator);source=data['source1'][index];source2=data['source2'][index];target=data['target'][index];edge=data['edge'][index];role=data['role'][index]
        details=model(source);pair=model(source2).output;loss,components=loss_for(details,source,target,edge,role,pair);optimizer.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.0);optimizer.step()
        if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f"{name} step {step}")
        if step==1 or step%100==0:
            row={"step":step,"total":float(loss.detach()),"gate":float(details.gate.mean().detach()),"edge_delta_gray":float(details.edge_delta.abs().mean().detach()*255),"texture_delta_gray":float(details.texture_delta.abs().mean().detach()*255),**{k:float(v.detach()) for k,v in components.items()}};trace.append(row);print(json.dumps({"arm":name,**row}),flush=True)
    torch.save({"model":model.state_dict(),"joint_gate":joint_gate,"steps":steps},WEIGHTS/f"{name}.pth");return model.eval(),trace


def oracle_alpha(source,target,proposal,kernel=9):
    delta=proposal-source;desired=target-source;num=F.avg_pool2d(delta*desired,kernel,1,kernel//2);den=F.avg_pool2d(delta.square(),kernel,1,kernel//2)+1e-8;return (num/den).clamp(0,1)


def train_selector(proposal_model:ParallelExperts,data:dict[str,torch.Tensor],steps:int=700):
    seed_all(108850);selector=AdoptionSelector().to(DEVICE);optimizer=torch.optim.AdamW(selector.parameters(),lr=4e-4,weight_decay=1e-5);generator=torch.Generator(device=DEVICE).manual_seed(108851);trace=[];batch=18
    for parameter in proposal_model.parameters():parameter.requires_grad_(False)
    for step in range(1,steps+1):
        index=torch.randint(0,len(data['source1']),(batch,),device=DEVICE,generator=generator);source=data['source1'][index];target=data['target'][index];edge=data['edge'][index]
        with torch.no_grad():proposal=proposal_model(source).proposal;alpha_target=oracle_alpha(source,target,proposal)
        alpha=selector(source,proposal);output=(source+alpha*(proposal-source)).clamp(0,1);alpha_loss=F.smooth_l1_loss(alpha,alpha_target,beta=.05);pixel=F.smooth_l1_loss(output,target,beta=2/255);edge_loss=(torch.abs(output-target)*(.15+.85*edge)).sum()/(.15+.85*edge).sum();loss=alpha_loss+.20*pixel+.12*edge_loss
        optimizer.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(selector.parameters(),5.0);optimizer.step()
        if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f"selector step {step}")
        if step==1 or step%100==0:
            row={"step":step,"total":float(loss.detach()),"alpha_loss":float(alpha_loss.detach()),"alpha_mean":float(alpha.mean().detach()),"target_mean":float(alpha_target.mean().detach())};trace.append(row);print(json.dumps({"arm":"staged_selector",**row}),flush=True)
    torch.save({"model":selector.state_dict(),"steps":steps,"proposal":"direct_frozen"},WEIGHTS/'staged_selector.pth');return selector.eval(),trace


def component_count(binary:np.ndarray)->int:return int(component_label(binary)[1])


@torch.inference_mode()
def predict(model,data:dict[str,torch.Tensor],selector=None):
    outputs=[];details_rows=[];alphas=[]
    for start in range(0,len(data['source1']),24):
        source=data['source1'][start:start+24];details=model(source)
        if selector is None:output=details.output;alpha=details.gate
        else:alpha=selector(source,details.proposal);output=(source+alpha*(details.proposal-source)).clamp(0,1)
        outputs.append(output.cpu());alphas.append(alpha.cpu());details_rows.append({"denoise":float(details.denoise_delta.abs().mean()*255),"edge":float(details.edge_delta.abs().mean()*255),"texture":float(details.texture_delta.abs().mean()*255),"radiometry":float(details.radiometry_delta.abs().mean()*255)})
    return torch.cat(outputs).numpy(),torch.cat(alphas).numpy(),details_rows


def evaluate(name,model,data_np,data_t,selector=None):
    output,alpha,branches=predict(model,data_t,selector);source=data_np['source1'].astype(np.float32)/255;target=data_np['target'].astype(np.float32)/255;edge=data_np['edge'].astype(np.float32)/255;mask=data_np['mask']>127;mid=data_np['midpoint'][:,None,None];pol=data_np['polarity'][:,None,None]
    raw_err=np.abs(source-target);out_err=np.abs(output[:,0]-target);edge_weight=.15+.85*edge;raw_edge=float((raw_err*edge_weight).sum()/edge_weight.sum()*255);out_edge=float((out_err*edge_weight).sum()/edge_weight.sum()*255)
    pred_binary=np.where(pol>0,output[:,0]>mid,output[:,0]<mid);ious=[];centroids=[];added_topology=0
    for p,t in zip(pred_binary,mask):
        inter=np.logical_and(p,t).sum();union=np.logical_or(p,t).sum();ious.append(inter/max(union,1));py,px=np.nonzero(p);ty,tx=np.nonzero(t);centroids.append(float(np.hypot((px.mean() if len(px) else 0)-(tx.mean() if len(tx) else 0),(py.mean() if len(py) else 0)-(ty.mean() if len(ty) else 0))));added_topology+=component_count(p)>component_count(t)
    identity=data_np['role']==ROLES.index('identity')
    result={"name":name,"images":len(source),"raw_mae_gray":float(raw_err.mean()*255),"model_mae_gray":float(out_err.mean()*255),"mae_improved_fraction":float(np.mean(out_err.reshape(len(source),-1).mean(1)<raw_err.reshape(len(source),-1).mean(1))),"raw_edge_mae_gray":raw_edge,"model_edge_mae_gray":out_edge,"median_iou":float(np.median(ious)),"median_centroid_error_px":float(np.median(centroids)),"added_topology_failures":int(added_topology),"identity_change_gray":float(np.abs(output[identity,0]-source[identity]).mean()*255) if identity.any() else 0.0,"output_change_gray":float(np.abs(output[:,0]-source).mean()*255),"alpha_mean":float(alpha.mean()),"alpha_identity_mean":float(alpha[identity].mean()) if identity.any() else 0.0,"branch_abs_gray":{key:float(np.mean([row[key] for row in branches])) for key in branches[0]}}
    return result,output


@torch.inference_mode()
def tile_parity(model,selector=None):
    rng=np.random.default_rng(108870);image=torch.from_numpy(rng.random((1,1,512,512),dtype=np.float32)).to(DEVICE)
    def apply(x):
        d=model(x)
        if selector is None:return d.output
        a=selector(x,d.proposal);return (x+a*(d.proposal-x)).clamp(0,1)
    full=apply(image);halo=96;core=128;canvas=torch.zeros_like(image)
    padded=F.pad(image,(halo,halo,halo,halo),mode='reflect')
    for y in range(0,512,128):
        for x in range(0,512,128):
            tile=padded[...,y:y+core+2*halo,x:x+core+2*halo];canvas[...,y:y+core,x:x+core]=apply(tile)[...,halo:halo+core,halo:halo+core]
    delta=(full-canvas).abs()*255;interior=delta[...,halo:-halo,halo:-halo]
    seam_mask=torch.zeros_like(delta,dtype=torch.bool)
    for coordinate in (128,256,384):
        seam_mask[...,halo:-halo,max(halo,coordinate-3):min(512-halo,coordinate+4)]=True
        seam_mask[...,max(halo,coordinate-3):min(512-halo,coordinate+4),halo:-halo]=True
    seam=delta[seam_mask]
    return {"global_mean_abs_gray":float(delta.mean()),"global_max_abs_gray":float(delta.max()),"interior_mean_abs_gray":float(interior.mean()),"interior_p99_abs_gray":float(torch.quantile(interior,.99)),"interior_max_abs_gray":float(interior.max()),"seam_mean_abs_gray":float(seam.mean()),"seam_p99_abs_gray":float(torch.quantile(seam,.99)),"seam_max_abs_gray":float(seam.max())}


def read_real(path:Path)->np.ndarray:
    image=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_GRAYSCALE);return image.astype(np.float32)/255


@torch.inference_mode()
def reconstruct_real(model,image:np.ndarray,selector=None,core=256,halo=96)->np.ndarray:
    tensor=torch.from_numpy(image[None,None]).to(DEVICE);h,w=image.shape;out=torch.zeros_like(tensor);padded=F.pad(tensor,(halo,halo,halo,halo),mode='reflect')
    for y in range(0,h,core):
        for x in range(0,w,core):
            ch=min(core,h-y);cw=min(core,w-x);tile=padded[...,y:y+ch+2*halo,x:x+cw+2*halo];d=model(tile);value=d.output if selector is None else (tile+selector(tile,d.proposal)*(d.proposal-tile)).clamp(0,1);out[...,y:y+ch,x:x+cw]=value[...,halo:halo+ch,halo:halo+cw]
    return out[0,0].cpu().numpy()


def real_validation(models):
    rows=[];previews=[]
    for path in REAL_IMAGES:
        raw=read_real(path);outputs={name:reconstruct_real(model,raw,selector) for name,(model,selector) in models.items()};small=[cv2.resize(raw,(384,288),interpolation=cv2.INTER_AREA)]
        gx=cv2.Sobel(raw,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(raw,cv2.CV_32F,0,1,ksize=3);support=np.hypot(gx,gy)>=np.quantile(np.hypot(gx,gy),.90)
        for name,value in outputs.items():
            gx2=cv2.Sobel(value,cv2.CV_32F,1,0,ksize=3);gy2=cv2.Sobel(value,cv2.CV_32F,0,1,ksize=3);rows.append({"image":path.name,"method":name,"mean_abs_change_gray":float(np.mean(np.abs(value-raw))*255),"edge_gain":float(np.hypot(gx2,gy2)[support].mean()/max(np.hypot(gx,gy)[support].mean(),1e-8)),"fine_detail_ratio":float(np.mean(np.abs(value-cv2.GaussianBlur(value,(0,0),1)))/max(np.mean(np.abs(raw-cv2.GaussianBlur(raw,(0,0),1))),1e-8))});small.append(cv2.resize(value,(384,288),interpolation=cv2.INTER_AREA))
        previews.append(np.concatenate(small,axis=1))
    frame=pd.DataFrame(rows);frame.to_csv(RESULT/'real_validation.csv',index=False,encoding='utf-8-sig');canvas=np.concatenate(previews,axis=0);cv2.imencode('.png',np.round(np.clip(canvas,0,1)*255).astype(np.uint8))[1].tofile(str(RESULT/'real_comparison.png'));return {method:{"mean_abs_change_gray":float(group['mean_abs_change_gray'].median()),"edge_gain":float(group['edge_gain'].median()),"fine_detail_ratio":float(group['fine_detail_ratio'].median())} for method,group in frame.groupby('method')}


def main():
    seed_all(108800);splits=prepare_data();train=tensor_data(splits['train']);validation=tensor_data(splits['validation']);holdout=tensor_data(splits['holdout'])
    completed_proposals=(WEIGHTS/'direct_parallel.pth').exists() and (WEIGHTS/'joint_unsupervised_gate.pth').exists()
    if completed_proposals:
        direct=ParallelExperts(False).to(DEVICE);direct.load_state_dict(torch.load(WEIGHTS/'direct_parallel.pth',map_location=DEVICE,weights_only=False)['model']);direct.eval()
        joint=ParallelExperts(True).to(DEVICE);joint.load_state_dict(torch.load(WEIGHTS/'joint_unsupervised_gate.pth',map_location=DEVICE,weights_only=False)['model']);joint.eval()
        direct_trace=[];joint_trace=[]
    else:
        direct,direct_trace=train_proposal('direct_parallel',False,train,900);joint,joint_trace=train_proposal('joint_unsupervised_gate',True,train,900)
    completed_selector=(WEIGHTS/'staged_selector.pth').exists()
    if completed_selector:
        selector=AdoptionSelector().to(DEVICE);selector.load_state_dict(torch.load(WEIGHTS/'staged_selector.pth',map_location=DEVICE,weights_only=False)['model']);selector.eval();selector_trace=[]
    else:
        selector,selector_trace=train_selector(direct,train,700)
    arms={"direct_parallel":(direct,None),"joint_unsupervised_gate":(joint,None),"staged_outcome_selector":(direct,selector)};summary={"status":"complete","device":str(DEVICE),"data_manifest":json.loads((DATA_DIR/'manifest.json').read_text()),"proposal_checkpoints_reused_after_selector_tensor_fix":completed_proposals,"selector_checkpoint_reused_for_halo96_revalidation":completed_selector,"arms":{},"tile":{},"real":{},"traces":{"direct_parallel":direct_trace,"joint_unsupervised_gate":joint_trace,"staged_outcome_selector":selector_trace}}
    for name,(model,select) in arms.items():
        val,_=evaluate(name,model,splits['validation'],validation,select);held,_=evaluate(name,model,splits['holdout'],holdout,select);summary['arms'][name]={"validation":val,"holdout":held};summary['tile'][name]=tile_parity(model,select)
    summary['real']=real_validation(arms);(RESULT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())

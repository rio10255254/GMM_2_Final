"""Image, gradient, photometry-normalized pair and direct boundary-moment losses."""
import math,torch
from torch.nn import functional as F
def robust_gray(r):
 e=.5/255;s=r.square();return (s/(torch.sqrt(s+e*e)+e)).mean()*255
def translated(value,delta):
 h,w=value.shape[-2:];nx=math.floor(-float(delta[0]));ny=math.floor(-float(delta[1]));fx=-float(delta[0])-nx;fy=-float(delta[1])-ny
 def sample(dy,dx):
  out=torch.zeros_like(value);y0=max(0,-dy);y1=min(h,h-dy);x0=max(0,-dx);x1=min(w,w-dx)
  if y1>y0 and x1>x0:out[...,y0:y1,x0:x1]=value[...,y0+dy:y1+dy,x0+dx:x1+dx]
  return out
 return (1-fy)*((1-fx)*sample(ny,nx)+fx*sample(ny,nx+1))+fy*((1-fx)*sample(ny+1,nx)+fx*sample(ny+1,nx+1))
def normalize_view(x):
 mean=x.mean((-2,-1),keepdim=True);std=torch.sqrt((x-mean).square().mean((-2,-1),keepdim=True)+(.5/255)**2);return (x-mean)/std
def gradient(x):
 p=torch.cat((x[...,1:2].flip(-1),x,x[...,-2:-1].flip(-1)),-1);p=torch.cat((p[...,1:2,:].flip(-2),p,p[...,-2:-1,:].flip(-2)),-2);gx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;gy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5;return gx,gy
def moments(x):
 gx,gy=gradient(x);w=torch.sqrt(gx.square()+gy.square()+1e-8);h,ww=x.shape[-2:];yy=torch.linspace(-1,1,h,device=x.device,dtype=x.dtype)[None,None,:,None];xx=torch.linspace(-1,1,ww,device=x.device,dtype=x.dtype)[None,None,None,:];mass=w.sum((-2,-1),keepdim=True)+1e-8;cx=(w*xx).sum((-2,-1),keepdim=True)/mass;cy=(w*yy).sum((-2,-1),keepdim=True)/mass;vx=(w*(xx-cx).square()).sum((-2,-1),keepdim=True)/mass;vy=(w*(yy-cy).square()).sum((-2,-1),keepdim=True)/mass;xy=(w*(xx-cx)*(yy-cy)).sum((-2,-1),keepdim=True)/mass;return torch.cat((cx.flatten(1),cy.flatten(1),vx.flatten(1),vy.flatten(1),xy.flatten(1)),1)
def stage_terms(pred,batch):
 lo,hi=batch['core'];crop=lambda z:z[...,lo:hi,lo:hi];target=batch['target'];r=crop(pred-target);pgx,pgy=gradient(crop(pred));tgx,tgy=gradient(crop(target));terms=dict(image=robust_gray(r),gradient=.5*(robust_gray(pgx-tgx)+robust_gray(pgy-tgy)))
 norm=normalize_view(pred);pair=[]
 for v in range(1,len(pred)):pair.append(robust_gray(crop(norm[v:v+1]-translated(norm[0:1],batch['shifts_xy'][v])))/255)
 terms['pair_output']=torch.stack(pair).mean();terms['moments']=(moments(crop(pred))-moments(crop(target))).abs().mean()*100
 return terms
def objective(states,batch,model,cfg):
 weights=cfg['stage_weights'];totals={k:states[0].sum()*0 for k in ('image','gradient','pair_output','moments')};total=states[0].sum()*0
 for weight,pred in zip(weights,states):
  t=stage_terms(pred,batch);stage=sum(cfg['loss'][k]*t[k] for k in totals);total=total+weight*stage
  for k in totals:totals[k]=totals[k]+weight*t[k]
 predicted=model.optics.blur(states[-1],batch['operator_psf_indices']);lo,hi=batch['core'];observation=robust_gray((predicted-batch['source'])[...,lo:hi,lo:hi]);total=total+cfg['loss']['observation']*observation;totals['observation']=observation
 return total,totals

"""R149 image, motion and non-cancelling local boundary objectives."""
import math,torch
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
 p=torch.cat((x[...,1:2].flip(-1),x,x[...,-2:-1].flip(-1)),-1);p=torch.cat((p[...,1:2,:].flip(-2),p,p[...,-2:-1,:].flip(-2)),-2);return (p[...,1:-1,2:]-p[...,1:-1,:-2])*.5,(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5
def boundary_weight(x,sdf,valid):
 gx,gy=gradient(x);edge=torch.sqrt(gx.square()+gy.square()+1e-8);band=torch.exp(-sdf.abs()/2)*valid[:,None,None,None].to(x.dtype);return edge*band
def boundary_coordinates(x,sdf,valid):
 q=boundary_weight(x,sdf,valid);mass=q.sum((-2,-1))+1e-8;signed=(q*sdf).sum((-2,-1))/mass;spread=(q*sdf.abs()).sum((-2,-1))/mass;return signed[:,0],spread[:,0]
def pool_cells(x,cell):
 b,c,h,w=x.shape;assert h%cell==0 and w%cell==0;return x.reshape(b,c,h//cell,cell,w//cell,cell).sum((3,5))
def local_boundary_error(pred,target,sdf,valid,cell=12):
 qp=boundary_weight(pred,sdf,valid);qt=boundary_weight(target,sdf,valid);pm=pool_cells(qp,cell);tm=pool_cells(qt,cell);eps=1e-8;pr=pool_cells(qp*sdf.abs(),cell)/(pm+eps);tr=pool_cells(qt*sdf.abs(),cell)/(tm+eps);weights=tm/(tm.sum((-2,-1),keepdim=True)+eps);local_spread=(weights*(pr-tr).abs()).sum((-2,-1))[:,0];pred_distance=(qp*sdf.abs()).sum((-2,-1))[:,0]/(qp.sum((-2,-1))[:,0]+eps);target_distance=(qt*sdf.abs()).sum((-2,-1))[:,0]/(qt.sum((-2,-1))[:,0]+eps);per_view=local_spread+.5*(pred_distance-target_distance).abs();active=valid&(tm.sum((-2,-1))[:,0]>1e-6);return per_view[active].mean() if active.any() else pred.sum()*0
def stage_terms(pred,b,cfg,loss_mode):
 lo,hi=b['core'];crop=lambda x:x[...,lo:hi,lo:hi];target=b['target'];r=crop(pred-target);pc=crop(pred);tc=crop(target);pgx,pgy=gradient(pc);tgx,tgy=gradient(tc);terms=dict(image=robust_gray(r),gradient=.5*(robust_gray(pgx-tgx)+robust_gray(pgy-tgy)))
 norm=normalize_view(pred);terms['pair_output']=torch.stack([robust_gray(crop(norm[v:v+1]-translated(norm[0:1],b['shifts_xy'][v])))/255 for v in range(1,4)]).mean();ps,pr=boundary_coordinates(pc,b['sdf'],b['geometry_valid']);ts,tr=boundary_coordinates(tc,b['sdf'],b['geometry_valid']);valid=b['geometry_valid'];global_boundary=((ps[valid]-ts[valid]).abs()+.5*(pr[valid]-tr[valid]).abs()).mean() if valid.any() else pred.sum()*0;local_boundary=local_boundary_error(pc,tc,b['sdf'],valid,int(cfg['local_boundary_cell_px']));mix=float(cfg['local_boundary_mix']) if loss_mode=='local' else 0.;terms['boundary_global']=global_boundary;terms['boundary_local']=local_boundary;terms['boundary']=(1-mix)*global_boundary+mix*local_boundary;return terms
def objective(states,b,model,cfg,loss_mode='local'):
 loss_keys=('image','gradient','pair_output','boundary');diagnostic_keys=loss_keys+('boundary_global','boundary_local');totals={k:states[0].sum()*0 for k in diagnostic_keys};total=states[0].sum()*0
 for weight,pred in zip(cfg['stage_weights'],states):
  t=stage_terms(pred,b,cfg,loss_mode);total+=weight*sum(cfg['loss'][k]*t[k] for k in loss_keys)
  for k in diagnostic_keys:totals[k]+=weight*t[k]
 predicted=model.optics.blur(states[-1],b['operator_psf_indices']);lo,hi=b['observation_core'];observation=robust_gray((predicted-b['source'])[...,lo:hi,lo:hi]);total+=cfg['loss']['observation']*observation;totals['observation']=observation;return total,totals

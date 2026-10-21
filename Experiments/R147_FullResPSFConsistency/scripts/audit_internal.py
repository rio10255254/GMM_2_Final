"""Frozen-model diagnostics. No checkpoint, original output or score is changed."""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import cv2, numpy as np, pandas as pd, torch
from scipy.ndimage import shift as ndshift

AUDIT_ROOT=Path(__file__).resolve().parents[1]
ROOTS={
 'r147':AUDIT_ROOT,
 'r146':AUDIT_ROOT.parent/'R146_SEMCoreHaloPSF25_MatchedPairs',
 'r140':AUDIT_ROOT.parent/'R140v2_StableUNet',
}
RUN_INDEX=(0,5,10,15,20,29)
FRAME_NUMBERS=tuple(s*31+i for s in RUN_INDEX for i in (0,1,15,16,30))
SINGLE_FRAMES=tuple(s*31 for s in RUN_INDEX)

def main():
 p=argparse.ArgumentParser();p.add_argument('--model',choices=ROOTS,default='r147');p.add_argument('--phase',choices=('trace','shifts','crops','gradients'),required=True);a=p.parse_args()
 root=ROOTS[a.model];sys.path.insert(0,str(root))
 from model import Model
 from utils import load,save,sha,setup,model_config
 from evaluation.measurement_interface import measure_image
 setup(1309001);cv2.setNumThreads(1)
 complete=load(root/'runs/formal_8192/training_complete.json')
 rec=complete['final_checkpoint' if a.model=='r140' else 'checkpoint'];assert rec['step']==8192 and sha(rec['path'])==rec['sha256']
 cp=torch.load(rec['path'],map_location='cpu',weights_only=False);cfg=model_config();m=Model(cfg,root).cuda().eval();m.load_state_dict(cp['model'],strict=True)
 plan=load(AUDIT_ROOT/'evaluation/capture_plan.json');tracking=pd.read_csv(AUDIT_ROOT/'evaluation/tracking.csv');reader=load(AUDIT_ROOT/'evaluation/measurement_config.json')
 out=AUDIT_ROOT/'results/internal_audit';out.mkdir(parents=True,exist_ok=True)
 def frame(n):
  f=plan['frames'][n];assert sha(f['source']['path'])==f['source']['sha256'];im=cv2.imread(f['source']['path'],0).astype(np.float32)/np.float32(255)
  seeds=tracking[(tracking.run==f['run'])&(tracking['index']==f['index'])].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy()
  return f,im,seeds
 def values(im,seeds):
  rr,_=measure_image(np.asarray(im,dtype=np.float64),seeds,reader)
  return np.array([[x['center_x_px'],x['center_y_px'],x['radius_px']] for x in rr])
 def circles(n,mode,it,v):
  f=plan['frames'][n]
  return [dict(frame=n,run=f['run'],index=f['index'],mode=mode,iteration=it,pillar=k+1,cx=float(t[0]),cy=float(t[1]),radius=float(t[2])) for k,t in enumerate(v)]
 def region(seeds):
  return (slice(int(seeds[:,1].min())-24,int(seeds[:,1].max())+25),slice(int(seeds[:,0].min())-24,int(seeds[:,0].max())+25))
 def tensor(im):return torch.from_numpy(np.ascontiguousarray(im))[None,None].cuda()
 def predict(im):
  with torch.inference_mode():return m(tensor(im)).cpu().numpy()[0,0]
 def baseline(f):
  with np.load(root/'results/reconstruction'/f['run']/f"{f['index']+1:02d}.npz") as z:return z['output']
 provenance=dict(model=a.model,checkpoint_sha256=rec['sha256'],model_source_sha256=sha(root/'model.py'),script_sha256=sha(__file__),frames=list(SINGLE_FRAMES if a.phase!='trace' else FRAME_NUMBERS),not_retrained=True,reader_sha256=sha(AUDIT_ROOT/'evaluation/measurement_interface.py'))
 start=time.perf_counter()
 if a.phase=='trace':
  assert a.model=='r147';rows=[];updates=[];parity=[]
  with torch.inference_mode():
   for n in FRAME_NUMBERS:
    f,im,seeds=frame(n);x=tensor(im);fixed=m.raw_features(x);roi=region(seeds)
    rows+=circles(n,'full',0,values(im,seeds));r=torch.zeros_like(x);z=x
    for i in range(4):
     obs,bp=m.optics.consistency(z,x);features=torch.cat((z,x,z-x,obs,bp,*fixed),1)
     logits=m.refiner(features);eta=cfg['eta_max']*torch.sigmoid(m.step_logits[i]);alpha=cfg['optical_step_max']*torch.sigmoid(m.optical_step_logits[i]);neural=eta*torch.tanh(logits);physical=alpha*bp
     previous=r;nnr=(r+neural).clamp(-cfg['r_max'],cfg['r_max']);ppr=(r+physical).clamp(-cfg['r_max'],cfg['r_max']);r=(r+neural+physical).clamp(-cfg['r_max'],cfg['r_max']);z=(x+r).clamp(0,1)
     for label,yy in [('full',z),('local_neural',(x+nnr).clamp(0,1)),('local_physical',(x+ppr).clamp(0,1))]:
      rows+=circles(n,label,i+1,values(yy.cpu().numpy()[0,0],seeds))
     q=lambda yy:yy[0,0][roi].double();nv,pv=q(neural),q(physical);zn=q(z);rv=q(r);obsafter=x-m.optics.blur(z)
     updates.append(dict(frame=n,iteration=i+1,eta=float(eta),alpha=float(alpha),neural_RMS_gray=float(nv.square().mean().sqrt()*255),physical_RMS_gray=float(pv.square().mean().sqrt()*255),cosine=float((nv*pv).sum()/(nv.norm()*pv.norm()+1e-20)),observation_RMS_before=float(q(obs).square().mean().sqrt()*255),observation_RMS_after=float(q(obsafter).square().mean().sqrt()*255),residual_clip_fraction=float((rv.abs()>=cfg['r_max']-1e-6).double().mean()),output_clip_fraction=float(((zn<=1e-6)|(zn>=1-1e-6)).double().mean()),update_RMS_gray=float(q(r-previous).square().mean().sqrt()*255)))
    expected=baseline(f);err=float(np.abs(z.cpu().numpy()[0,0]-expected).max());assert err<1e-6;parity.append(err)
    # Separate direct correction from the optical information given to the U-Net.
    for mode,feature_on,direct_on in [('features_only',True,False),('direct_only',False,True),('off',False,False)]:
     rr=torch.zeros_like(x);zz=x
     for i in range(4):
      ob,b=m.optics.consistency(zz,x);zero=torch.zeros_like(x)
      ff=torch.cat((zz,x,zz-x,ob if feature_on else zero,b if feature_on else zero,*fixed),1)
      nn=cfg['eta_max']*torch.sigmoid(m.step_logits[i])*torch.tanh(m.refiner(ff));pp=cfg['optical_step_max']*torch.sigmoid(m.optical_step_logits[i])*b if direct_on else zero
      rr=(rr+nn+pp).clamp(-cfg['r_max'],cfg['r_max']);zz=(x+rr).clamp(0,1)
     rows+=circles(n,mode,4,values(zz.cpu().numpy()[0,0],seeds))
    if n==0:
     native=m(x).cpu().numpy()[0,0];assert np.max(np.abs(native-expected))==0
    pd.DataFrame(rows).to_csv(out/'trace_circles.csv',index=False);pd.DataFrame(updates).to_csv(out/'trace_updates.csv',index=False)
    print('TRACE',n,'parity',err,flush=True)
  save(out/'trace_complete.json',dict(provenance,max_saved_output_difference=max(parity),circles=len(rows),updates=len(updates),elapsed_seconds=time.perf_counter()-start))
 elif a.phase=='crops':
  rows=[]
  for n in SINGLE_FRAMES:
   f,im,seeds=frame(n);base=baseline(f);bv=values(base,seeds);h,w=im.shape
   for size,phase in [(320,0),(320,1),(512,0),(768,0),(1024,0)]:
    ox=max(0,min((int(seeds[:,0].mean())-size//2)//8*8,w-size));oy=max(0,min((int(seeds[:,1].mean())-size//2)//8*8,h-size));ox+=phase
    crop=im[oy:oy+size,ox:ox+size];y=predict(crop);s=seeds-np.array([ox,oy]);v=values(y,s);v[:,:2]+=np.array([ox,oy]);roi=region(s);delta=y[roi]-base[oy:oy+size,ox:ox+size][roi]
    for k,t in enumerate(v):rows.append(dict(model=a.model,frame=n,size=size,origin_phase_x=ox%8,origin_phase_y=oy%8,pillar=k+1,center_error_nm=float(np.linalg.norm(t[:2]-bv[k,:2])*172.5),diameter_change_nm=float((t[2]-bv[k,2])*345),image_RMS_gray=float(np.sqrt(np.mean(delta**2))*255),image_max_gray=float(np.abs(delta).max()*255)))
   pd.DataFrame(rows).to_csv(out/f'crops_{a.model}.csv',index=False);print('CROPS',a.model,n,flush=True)
  save(out/f'crops_{a.model}_complete.json',dict(provenance,rows=len(rows),elapsed_seconds=time.perf_counter()-start))
 elif a.phase=='shifts':
  rows=[]
  cases=[('integer',1,0),('integer',2,0),('integer',4,0),('integer',8,0),('fourier',.5,0),('fourier',0,.5),('linear',.5,0)]
  def move(im,dx,dy,method):
   if method in ('integer','linear'):return ndshift(im,(dy,dx),order=0 if method=='integer' else 1,mode='reflect',prefilter=False).astype(np.float32)
   pad=128;v=np.pad(im,pad,mode='reflect');hh,ww=v.shape;transfer=np.exp(-2j*np.pi*(np.fft.fftfreq(hh)[:,None]*dy+np.fft.fftfreq(ww)[None,:]*dx));return np.fft.ifft2(np.fft.fft2(v)*transfer).real[pad:-pad,pad:-pad].astype(np.float32)
  for n in SINGLE_FRAMES:
   f,im,seeds=frame(n);base=baseline(f);bv=values(base,seeds);rawv=values(im,seeds)
   for method,dx,dy in cases:
    shifted=move(im,dx,dy,method);clip=float(((shifted<0)|(shifted>1)).mean());shifted=shifted.clip(0,1);newseeds=seeds+[dx,dy];y=predict(shifted);v=values(y,newseeds);rv=values(shifted,newseeds);reference=move(base,dx,dy,method);roi=region(newseeds);dr=y[roi]-reference[roi]
    for k in range(9):
     err=(v[k,:2]-bv[k,:2]-[dx,dy])*172.5;rawerr=(rv[k,:2]-rawv[k,:2]-[dx,dy])*172.5
     rows.append(dict(model=a.model,frame=n,method=method,dx=dx,dy=dy,pillar=k+1,center_error_nm=float(np.linalg.norm(err)),center_dx_error_nm=float(err[0]),center_dy_error_nm=float(err[1]),raw_center_error_nm=float(np.linalg.norm(rawerr)),diameter_change_nm=float((v[k,2]-bv[k,2])*345),raw_diameter_change_nm=float((rv[k,2]-rawv[k,2])*345),commutator_RMS_gray=float(np.sqrt(np.mean(dr**2))*255),commutator_max_gray=float(np.abs(dr).max()*255),source_clipped_fraction=clip))
   pd.DataFrame(rows).to_csv(out/f'shifts_{a.model}.csv',index=False);print('SHIFTS',a.model,n,flush=True)
  save(out/f'shifts_{a.model}_complete.json',dict(provenance,rows=len(rows),elapsed_seconds=time.perf_counter()-start))
 else:
  assert a.model=='r147'
  from dataset import Bank
  from losses import objective,translated
  from utils import train_config
  bank=Bank(train_config());entries=[e for e in bank.manifest['entries'] if e['split']=='train'];groups={}
  for e in entries:groups.setdefault(load(bank.root/e['metadata'])['category'],[]).append(e['index'])
  selected=[x for k in sorted(groups) for x in groups[k][:2]];rows=[];params=[v for v in m.parameters() if v.requires_grad]
  for idx in selected:
   b=bank.batch('train',idx,'cuda',epoch=15);m.zero_grad(set_to_none=True);pred=m(b['source']);loss,terms=objective(pred,b);gr={}
   for name,weight in [('image',1),('gradient',.2),('pair',.2)]:
    grad=torch.autograd.grad(terms[name]*weight,params,retain_graph=True,allow_unused=True);vec=torch.cat([t.detach().flatten() if t is not None else torch.zeros_like(p).flatten() for t,p in zip(grad,params)]);gr[name]=vec
   lo,hi=b['core'];targetdiff=(b['target'][1:2]-translated(b['target'][0:1],b['shift_xy']))[...,lo:hi,lo:hi]
   mdata=load(bank.root/bank.entries[('train',idx)]['metadata']);row=dict(index=idx,category=mdata['category'],motion=b['motion_observable'],image=float(terms['image']),gradient=float(terms['gradient']),pair=float(terms['pair']),target_alignment_MAE_gray=float(targetdiff.abs().mean()*255))
   for name,v in gr.items():row[name+'_weighted_grad_norm']=float(v.norm())
   for name in ('gradient','pair'):row['image_'+name+'_gradient_cosine']=float(torch.dot(gr['image'],gr[name])/(gr['image'].norm()*gr[name].norm()+1e-20))
   rows.append(row);print('GRADIENT',idx,mdata['category'],flush=True)
  pd.DataFrame(rows).to_csv(out/'gradient_terms.csv',index=False);save(out/'gradients_complete.json',dict(provenance,sampled_train_parents=selected,epoch=15,rows=len(rows),elapsed_seconds=time.perf_counter()-start))
 print('COMPLETE',a.phase,a.model,flush=True)

if __name__=='__main__':main()

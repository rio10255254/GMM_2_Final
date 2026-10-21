"""Independent fixed physical example; four exact matched learnability controls."""
from __future__ import annotations
import json,time,os
import numpy as np
import torch
from scipy import ndimage
from common import *

def fixture():
    out=ROOT/'data/fixed_example';out.mkdir(parents=True,exist_ok=False)
    n=320;factor=8;radius=3;axis=(np.arange((n+2*radius)*factor,dtype=np.float64)+.5)/factor-radius
    x=axis[None,:];y=axis[:,None];region=slice(radius*factor,(radius+n)*factor)
    def avg(a,f):return a.reshape(a.shape[0]//f,f,a.shape[1]//f,f).mean((1,3),dtype=np.float64)
    def kern(f):
        q=np.arange(-radius*f,radius*f+1)/f;k=np.exp(-.5*(q/.8)**2);return k/k.sum()
    arrays={k:[] for k in ['source','target','latent_target','noiseless','sdf','boundary']}
    shifts=[(0.,0.),(.375,-.25)]
    for i,(dx,dy) in enumerate(shifts):
        xx=x-160-dx;yy=y-160-dy
        # Geometry not derived from any measured image or SEM answer.
        score=np.maximum((xx+.43*yy-3.21)/np.sqrt(1+.43**2),np.minimum(7-np.abs(xx+17),10-np.abs(yy-11)))
        occupancy=score>=0;z=(55+135*occupancy.astype(np.float64))/255
        k=kern(8);blur=ndimage.convolve1d(ndimage.convolve1d(z,k,axis=1,mode='constant'),k,axis=0,mode='constant')
        latent=avg(z[region,region],2).astype(np.float32);target=avg(z[region,region],8).astype(np.float32)
        noiseless=avg(blur[region,region],8).astype(np.float32)
        rng=np.random.default_rng(1261001+i)
        source=np.rint(np.clip(noiseless+rng.normal(0,1.5/255,(n,n)),0,1)*255).astype(np.uint8)
        sdf=avg(np.clip(score[region,region],-16,16),8).astype(np.float32)
        for name,a in dict(source=source,target=target,latent_target=latent,noiseless=noiseless,sdf=sdf,boundary=(np.abs(sdf)<=1).astype(np.float32)).items():arrays[name].append(a)
    arrays={k:np.stack(v) for k,v in arrays.items()};np.savez_compressed(out/'arrays.npz',**arrays)
    k=kern(4);profile=dict(calibration_id='r126_fixed_independent8x',qualification='unqualified_diagnostic',simulation_known_operator=True,kernel_convention='physical_psf',sampling_factor=4,kernel=dict(type='explicit',values=np.outer(k,k).tolist()),gain=1.,bias=0.,noise_variance=(1.5**2+1/12)/255**2)
    meta=dict(scene_id='r126_fixed_2d',source_ancestors=['analytic_halfplane_rectangle_1261001'],training_core_slice=[128,192,128,192],motion_observable=True,shift_xy=list(shifts[1]),photometry=dict(low=55/255,high=190/255),polarity=1,flat=False,profile=profile,external_inputs=[],target_fields_enter_forward=False)
    save(out/'metadata.json',meta)
    save(out/'manifest.json',dict(arrays_sha256=sha(out/'arrays.npz'),metadata_sha256=sha(out/'metadata.json'),generator_sha256=sha(__file__),physical_order='continuous shift, fixed8x convolution, native integration, independent sensor noise, quantization',unseen_evidence=False))
    return arrays,meta,sha(out/'manifest.json')

def tensors(arrays):
    source=torch.from_numpy(arrays['source'].astype(np.float32)/255)[:,None].cuda()
    targets={k:torch.from_numpy(v)[:,None].cuda() for k,v in arrays.items() if k!='source'}
    return source,targets

def metrics(m,d,a):
    c=lambda x:x[...,128:192,128:192]
    return dict(native_mae_gray=float((c(d.output-a['target'])).abs().mean()*255),latent_mae_gray=float((d.latent-a['latent_target'])[...,512:768,512:768].abs().mean()*255),observation_noiseless_mae_gray=float(c(m.observation(d.latent)-a['noiseless']).abs().mean()*255))

def gradient_audit(m,source,a,meta):
    m.train();d=m.forward_details(source,trace=True);loss,terms=objective(m,d,source,a,meta,CFG['loss_weights'],False)
    head=m.prior.head.weight
    gradients={}
    for k,v in terms.items():
        if CFG['loss_weights'][k] and k.startswith('geometry') is False:
            g=torch.autograd.grad(v,head,retain_graph=True)[0].flatten().detach();gradients[k]=g
    total=sum(CFG['loss_weights'][k]*g for k,g in gradients.items());ig=gradients['image_gray']
    data=dict(terms={k:float(v.detach()) for k,v in terms.items()},weighted_gradient_norm=float(total.norm()),components={k:dict(norm=float(g.norm()),weighted_norm=float(g.norm()*CFG['loss_weights'][k]),cosine_to_image=float(torch.dot(g,ig)/(g.norm()*ig.norm()).clamp_min(1e-20))) for k,g in gradients.items()})
    # Finite-difference check along the normalized total gradient, not merely grad presence.
    direction=total.reshape_as(head)/total.norm();analytical=float((total*direction.flatten()).sum());base=head.detach().clone();eps=1e-4;vals=[]
    with torch.no_grad():
        for sign in [1,-1]:
            head.copy_(base+sign*eps*direction);dd=m.forward_details(source);ll,_=objective(m,dd,source,a,meta,CFG['loss_weights'],False);vals.append(float(ll))
        head.copy_(base)
    numeric=(vals[0]-vals[1])/(2*eps)
    data['directional_derivative']=dict(analytic=analytical,numeric=numeric,relative_error=abs(numeric-analytical)/max(abs(analytical),1e-8),epsilon=eps)
    data['initial_steps']=[dict(prior_gray=float(t['prior_correction'].abs().mean()*255),observation_gray=float(t['observation_correction'].abs().mean()*255),projection_gray=float(t['projection_correction'].abs().mean()*255)) for t in d.trace]
    return data

def main():
    setup();protect();arrays,meta,dh=fixture();source,a=tensors(arrays)
    m=new_model(True,1265001,meta['profile'])
    assert 128>=m.required_halo+3+1+2
    with torch.no_grad():
        r=(m.observation(a['latent_target'])-a['noiseless'])[...,128:192,128:192]
        fit=dict(rms_gray=float(r.square().mean().sqrt()*255),p99_gray=float(torch.quantile(r.abs().flatten(),.99)*255),native_area_error=float((m.observation.integrate(a['latent_target'])-a['target']).abs().max()))
    fit['rms_in_noise_units']=fit['rms_gray']/np.sqrt(1.5**2+1/12)
    fit['p99_in_noise_units']=fit['p99_gray']/np.sqrt(1.5**2+1/12)
    fit['admitted']=fit['rms_in_noise_units']<=.25 and fit['p99_in_noise_units']<=1 and fit['native_area_error']<2e-7
    save(ROOT/'results/fixed_data_check.json',fit)
    if not fit['admitted']:raise ValueError('Fixed data incompatible, preserve and diagnose')
    audits={};summary=[]
    for observation_on in [False,True]:
        name='B' if observation_on else 'A'
        audits[name]=gradient_audit(new_model(observation_on,1265001,meta['profile']),source,a,meta)
        save(ROOT/f'results/gradient_{name}.json',audits[name])
        for full in [False,True]:
            run_id=f'fixed_{name}_{"full" if full else "image"}';out=ROOT/'runs'/run_id;out.mkdir(parents=True,exist_ok=False)
            m=new_model(observation_on,1265001,meta['profile']);params=[p for p in m.parameters() if p.requires_grad]
            opt=torch.optim.AdamW(params,lr=1e-4,weight_decay=1e-5)
            init=out/'step0000.pth';checkpoint(init,pack(m,run_id,1265001,0,dh))
            weights=CFG['loss_weights'] if full else {k:float(k=='image_gray') for k in CFG['loss_weights']}
            with torch.no_grad():before=metrics(m,m.forward_details(source),a)
            start=time.perf_counter()
            with (out/'ledger.jsonl').open('x') as log:
                for step in range(1,129):
                    m.train();opt.zero_grad(set_to_none=True);d=m.forward_details(source)
                    loss,terms=objective(m,d,source,a,meta,weights,False);loss.backward()
                    grad=float(torch.nn.utils.clip_grad_norm_(params,5));opt.step()
                    if not np.isfinite(float(loss)) or not np.isfinite(grad):raise FloatingPointError('Nonfinite update')
                    row=dict(run_id=run_id,step=step,actual_input_sha256=thash(source),data_manifest_sha256=dh,loss=float(loss.detach()),gradient_norm_before_clip=grad,terms={k:float(v.detach()) for k,v in terms.items()})
                    log.write(json.dumps(row)+'\n');log.flush()
                    if step%32==0:
                        with torch.no_grad():current=metrics(m,m.forward_details(source),a)
                        print(json.dumps(dict(run_id=run_id,step=step,seconds=time.perf_counter()-start,**current)),flush=True)
            m.eval()
            with torch.no_grad():dd=m.forward_details(source);after=metrics(m,dd,a)
            checkpoint(out/'step0128.pth',pack(m,run_id,1265001,128,dh,sha(init)))
            np.savez_compressed(out/'outputs.npz',source=arrays['source'][...,128:192,128:192],target=arrays['target'][...,128:192,128:192],output=dd.output.detach().cpu().numpy()[:,0,128:192,128:192])
            result=dict(run_id=run_id,completed_updates=128,before=before,after=after,native_reduction_fraction=1-after['native_mae_gray']/before['native_mae_gray'],seconds=time.perf_counter()-start,checkpoint_sha256=sha(out/'step0128.pth'),ledger_sha256=sha(out/'ledger.jsonl'),data_hash=dh)
            result['learnability_signal']=result['native_reduction_fraction']>=.2
            save(out/'summary.json',result);summary.append(result)
    save(ROOT/'results/fixed_example_summary.json',dict(status='four_fixed_controls_complete',updates=512,runs=summary,gradient_derivatives_checked=True,real_usefulness_claim=False))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()

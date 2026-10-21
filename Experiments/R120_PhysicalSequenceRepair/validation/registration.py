"""Independent local registration with enforced coordinate/validity rules."""
from __future__ import annotations
import numpy as np
from scipy.ndimage import shift
from scipy.optimize import least_squares


def estimate(image,reference,max_shift=2.,margin=8):
    image=np.asarray(image,dtype=np.float64);reference=np.asarray(reference,dtype=np.float64)
    invalid=lambda why:{'valid':False,'reason':why,'xy':None}
    if image.shape!=reference.shape or image.ndim!=2:return invalid('shape_mismatch')
    if not np.isfinite(image).all() or not np.isfinite(reference).all():return invalid('nonfinite')
    if min(image.shape)<=2*margin+8:return invalid('insufficient_support')
    if min(np.std(image),np.std(reference))<1e-6:return invalid('flat')
    gy,gx=np.gradient(reference)
    roi=np.zeros_like(reference,dtype=bool);roi[margin:-margin,margin:-margin]=True
    # Saturated samples cannot provide a reliable affine brightness fit.
    roi &= (image>.005)&(image<.995)&(reference>.005)&(reference<.995)
    g=np.stack([gx[roi],gy[roi]],1);a=g.T@g
    eig=np.linalg.eigvalsh(a)
    if len(g)<32 or eig[0]<1e-7 or eig[0]/max(eig[-1],1e-12)<1e-4:return invalid('unobservable_axis')
    # Subsample only the optimization support, not the observation image itself.
    opt=roi.copy();opt[1::2,:]=False;opt[:,1::2]=False
    target=reference[opt]
    matrix=np.stack([target,np.ones_like(target)],1)
    def residual(xy):
        moved=shift(image,(-xy[1],-xy[0]),order=3,mode='reflect',prefilter=True)[opt]
        gain,offset=np.linalg.lstsq(matrix,moved,rcond=None)[0]
        return moved-(gain*target+offset)
    fit=least_squares(residual,np.zeros(2),bounds=(-max_shift,max_shift),diff_step=None,
                      loss='soft_l1',f_scale=.005,max_nfev=40,xtol=1e-8,ftol=1e-8,gtol=1e-8)
    if not fit.success:return invalid('solver_not_converged')
    if np.max(np.abs(fit.x))>max_shift-1e-3:return invalid('search_boundary')
    return {'valid':True,'reason':'ok','xy':fit.x.tolist(),'rms':float(np.sqrt(np.mean(residual(fit.x)**2))),
            'min_information_eigenvalue':float(eig[0]),'observations_used':int(opt.sum())}


def summarize(rows):
    if not rows:raise ValueError('empty sequence')
    for key in ('scene_id','condition_id','method','protocol'):
        if len({r[key] for r in rows})!=1:raise ValueError(f'mixed {key}')
    frames=[r['frame'] for r in rows]
    if len(set(frames))!=len(frames):raise ValueError('duplicate frame')
    ordered=sorted(rows,key=lambda r:r['frame'])
    valid=[r for r in ordered if r['valid']]
    errors=np.asarray([np.asarray(r['xy'])-np.asarray(r['truth']) for r in valid])
    if errors.size and not np.isfinite(errors).all():raise ValueError('nonfinite valid position')
    steps=[]
    for a,b in zip(ordered,ordered[1:]):
        okay=a['valid'] and b['valid'] and b['frame']==a['frame']+1
        error=((np.asarray(b['xy'])-np.asarray(a['xy']))-(np.asarray(b['truth'])-np.asarray(a['truth']))).tolist() if okay else None
        steps.append({'start':a['frame'],'end':b['frame'],'valid':okay,'error':error})
    step_errors=[s['error'] for s in steps if s['valid']]
    return {'valid_count':len(valid),'failure_count':len(rows)-len(valid),
        'bias_xy':errors.mean(0).tolist() if len(valid) else None,
        'repeat_sd_xy':errors.std(0,ddof=1).tolist() if rows[0]['protocol']=='static' and len(valid)>1 else None,
        'step_sd_xy':np.std(step_errors,axis=0,ddof=1).tolist() if len(step_errors)>1 else None,'steps':steps}

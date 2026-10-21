"""Known-parameter operator tests, identifiability witnesses, and blind physical fit.

This is a diagnostic reference implementation, not a proposed production renderer.
"""
import csv, itertools, json, pathlib
import numpy as np
from scipy.special import ndtr, expit
from scipy.optimize import brentq, least_squares
from scipy.ndimage import gaussian_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

E=pathlib.Path(__file__).resolve().parents[1]
P=json.loads((E/'config/protocol.json').read_text(encoding='utf-8'))
OUT=E/'results'
def table(name,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def profile(t,family,scale,phase):
    z=(t-phase)/scale
    if family=='gaussian': return ndtr(z)
    if family=='logistic': return expit(z)
    if family=='asymmetric': return .8*ndtr(z+.4)+.2*ndtr((z-1.6)/1.3)
    raise ValueError(family)
def crossings(t,p):
    # Known plateaus; no per-output min-max fit hiding radiometry changes.
    out=[]
    for q in [.1,.5,.9]:
        ids=np.where((p[:-1]<=q)&(p[1:]>q))[0]
        if len(ids)!=1:return (np.nan,np.nan)
        i=ids[0]; out.append(t[i]+(q-p[i])*(t[i+1]-t[i])/(p[i+1]-p[i]))
    return out[1],out[2]-out[0]
def operator_matrix():
    cfg=P['operator_test']; rows=[];dense=np.arange(-64,64+cfg['dense_step_px']/2,cfg['dense_step_px']);pixel=np.arange(-64,65,dtype=float)
    for family,scale,phase,pol,levels in itertools.product(cfg['families'],cfg['scales_px'],cfg['phases_px'],cfg['polarity'],cfg['level_pairs']):
        lo,hi=levels;contrast=(hi-lo)*pol;offset=lo if pol>0 else hi
        true_c=brentq(lambda t:profile(t,family,scale,phase)-.5,-30,30)
        true_w=brentq(lambda t:profile(t,family,scale,phase)-.9,-40,40)-brentq(lambda t:profile(t,family,scale,phase)-.1,-40,40)
        for mode,t in [('dense_continuous',dense),('pixel_linear',pixel)]:
            raw=offset+contrast*profile(t,family,scale,phase)
            c0,w0=crossings(t,(raw-offset)/contrast)
            center=true_c if mode=='dense_continuous' else c0
            for delta,gain in itertools.product(cfg['translation_px'],cfg['compression']):
                coords=center+gain*(t-center-delta)
                if mode=='dense_continuous': y=offset+contrast*profile(coords,family,scale,phase)
                else:y=np.interp(coords,t,raw)
                c,w=crossings(t,(y-offset)/contrast)
                expected_c=(true_c if mode=='dense_continuous' else c0)+delta
                expected_w=(true_w if mode=='dense_continuous' else w0)/gain
                valid=bool(np.isfinite(c+w))
                pe=abs(c-expected_c) if valid else np.nan;we=abs(w-expected_w) if valid else np.nan
                rows.append({'mode':mode,'family':family,'scale':scale,'phase':phase,'polarity':pol,'contrast':hi-lo,'delta':delta,'gain':gain,'raw_width':w0,'position_error_px':pe,'width_error_px':we,'valid':valid,'position_pass':valid and pe<=cfg['position_tolerance_px'],'width_pass':valid and we<=cfg['width_tolerance_px'],'identity_max_error':float(np.max(abs(y-raw))) if delta==0 and gain==1 else ''})
    table('operator_matrix.csv',rows)
    summary={}
    for mode in ['dense_continuous','pixel_linear']:
        rr=[r for r in rows if r['mode']==mode]
        summary[mode]={'count':len(rr),'invalid':sum(not r['valid'] for r in rr),'position_fail':sum(not r['position_pass'] for r in rr),'width_fail':sum(not r['width_pass'] for r in rr),'max_position_error_px':max(r['position_error_px'] for r in rr),'max_width_error_px':max(r['width_error_px'] for r in rr),'identity_max_error':max(r['identity_max_error'] for r in rr if r['identity_max_error']!='')}
    # Explicitly demonstrate center errors and unrestricted-detail compensation.
    t=dense;center_error=.3;gain=1.5
    y=ndtr(center_error+gain*(t-center_error));c,_=crossings(t,y)
    shifted=ndtr((t-.4)/1.5);base=ndtr(t/1.5);residual=base-shifted
    # A zero-integral high-pass residual can also move the half-level.
    bump=.04*(np.exp(-t*t/2)-.5*np.exp(-t*t/8))
    c_bump,_=crossings(t,ndtr(t/1.5)+bump)
    details={'miscentered_width_only':{'anchor_error_px':center_error,'gain':gain,'predicted_drift_px':center_error*(1-1/gain),'measured_drift_px':c},'unrestricted_detail_compensation':{'position_shift_px':.4,'max_detail_gray':float(abs(residual).max()*255),'identical_final_output_max_error':float(abs(shifted+residual-base).max())},'zero_integral_detail':{'integral':float(np.trapz(bump,t)),'half_level_shift_px':c_bump,'meaning':'Zero total intensity does not protect an individual edge location.'}}
    return summary,details

def identifiability():
    t=np.arange(-24,25,dtype=float)
    # Object and PSF translation appear only through their sum, also after pixel integration.
    offsets=(np.arange(256)+.5)/256-.5
    observe=lambda c,mu,so,sp:ndtr((t[:,None]+offsets-c-mu)/np.hypot(so,sp)).mean(1)
    a=observe(0,.4,1,2);b=observe(.4,0,1,2)
    w1=observe(0,0,1,2);w2=observe(0,0,2,1)
    # Exact box-pixel alias: f and f+1 agree at integer centers with amplitude adjusted by sinc.
    f=.2; f2=1.2; amp=.05;amp2=amp*np.sinc(f)/np.sinc(f2)
    sampled1=.5+amp*np.sinc(f)*np.cos(2*np.pi*f*t)
    sampled2=.5+amp2*np.sinc(f2)*np.cos(2*np.pi*f2*t)
    fine=np.linspace(-3,3,3001);latent1=.5+amp*np.cos(2*np.pi*f*fine);latent2=.5+amp2*np.cos(2*np.pi*f2*fine)
    result={'object_vs_psf_shift':{'true_object_positions_px':[0,.4],'identical_observation_max_error':float(abs(a-b).max())},'object_vs_optical_width':{'intrinsic_width_parameters':[1,2],'psf_width_parameters':[2,1],'identical_observation_max_error':float(abs(w1-w2).max())},'unobserved_detail_alias':{'frequencies_cycles_per_pixel':[f,f2],'pixel_integrated_observation_max_error':float(abs(sampled1-sampled2).max()),'different_latent_max_error':float(abs(latent1-latent2).max()),'latent_intensity_ranges':[[float(latent1.min()),float(latent1.max())],[float(latent2.min()),float(latent2.max())]]}}
    fig,ax=plt.subplots(1,2,figsize=(10,3.6),layout='constrained');ax[0].plot(t,a,label='object 0; PSF +0.4');ax[0].plot(t,b,'--',label='object +0.4; PSF 0');ax[0].set(xlim=(-7,7),xlabel='Position (pixels)',ylabel='Observed intensity',title='Different object positions; identical image');ax[0].legend(fontsize=8)
    ax[1].plot(fine,latent1,label='latent A');ax[1].plot(fine,latent2,label='latent B');ax[1].plot(t,sampled1,'ko',label='same box-pixel samples');ax[1].set(xlim=(-3,3),xlabel='Position (pixels)',title='Different detail; identical samples');ax[1].legend(fontsize=8);fig.savefig(OUT/'identifiability.png',dpi=170);plt.close(fig)
    return result

# Sensor-integrated straight-edge model, analytic rather than the renderer's supersampling.
def phi(z):return np.exp(-.5*z*z)/np.sqrt(2*np.pi)
def integrated_edge(x,center,sigma):
    a=(x-.5-center)/sigma;b=(x+.5-center)/sigma
    return sigma*((b*ndtr(b)+phi(b))-(a*ndtr(a)+phi(a)))
def fit_edge(x,y):
    lo=float(np.median(y[:4]));hi=float(np.median(y[-4:]));norm=(y-lo)/(hi-lo) if hi-lo>1 else np.zeros_like(y)
    c,_=crossings(x,norm);c=0 if not np.isfinite(c) else np.clip(c,-5,5)
    fit=least_squares(lambda p:p[0]+p[1]*integrated_edge(x,p[2],p[3])-y,[lo,max(hi-lo,2),c,1.5],bounds=([-100,1,-8,.15],[350,400,8,8]),xtol=1e-10,ftol=1e-10,gtol=1e-10)
    return {'center':float(fit.x[2]),'sigma':float(fit.x[3]),'rms':float(np.sqrt(np.mean(fit.fun**2))),'fit_success':bool(fit.success),'bound_hit':bool(abs(fit.x[2])>7.99 or fit.x[3]>.799e1)}
def render(shape,sigma,phase,contrast,ss):
    n=96;axis=(np.arange(n*ss)+.5)/ss-n/2-.5
    xx,yy=np.meshgrid(axis,axis)
    if shape=='line':latent=xx>=phase
    else:
        radius=float(shape[6:]);latent=((xx-(phase-radius))**2+yy**2)>=radius**2
    # Smooth before sensor integration. The central row samples near the rightmost boundary.
    observed=gaussian_filter(latent.astype(float),sigma*ss,mode='nearest',truncate=5)
    pixels=observed.reshape(n,ss,n,ss).mean((1,3))
    x=np.arange(n)-n/2
    keep=abs(x)<=12
    return x[keep],80+contrast*pixels[n//2,keep]
def physical_fit():
    cfg=P['physical_fit'];rng=np.random.default_rng(cfg['seed']);rows=[];examples={};ss=cfg['supersample']
    # Render once per geometry/blur/phase/motion; noise and radiometry follow integration.
    for shape,sigma,phase,contrast in itertools.product(cfg['shapes'],cfg['psf_sigma_px'],cfg['phases_px'],cfg['contrast_gray']):
        x,clean0=render(shape,sigma,phase,contrast,ss);_,clean1=render(shape,sigma,phase+cfg['true_motion_px'],contrast,ss)
        for noise in cfg['noise_std_gray']:
            y0=clean0+rng.normal(0,noise,len(x));y1=clean1+rng.normal(0,noise,len(x));a=fit_edge(x,y0);b=fit_edge(x,y1)
            position_error=a['center']-phase;motion_error=(b['center']-a['center'])-cfg['true_motion_px']
            rows.append({'shape':shape,'psf_sigma':sigma,'phase':phase,'contrast':contrast,'noise':noise,'estimated_center':a['center'],'position_error_px':position_error,'motion_error_px':motion_error,'rms_gray':a['rms'],'fit_sigma':a['sigma'],'fit_success':a['fit_success'] and b['fit_success'],'bound_hit':a['bound_hit'] or b['bound_hit'],'position_pass':abs(position_error)<=cfg['position_tolerance_px'],'motion_pass':abs(motion_error)<=cfg['motion_tolerance_px']})
            if phase==0 and contrast==120 and noise==0 and sigma==3:examples[shape]=(x,y0,a)
    table('physical_fit.csv',rows)
    summary={}
    for shape in cfg['shapes']:
        rr=[r for r in rows if r['shape']==shape]
        summary[shape]={'count':len(rr),'fit_failure':sum(not r['fit_success'] for r in rr),'bound_hits':sum(r['bound_hit'] for r in rr),'position_failure':sum(not r['position_pass'] for r in rr),'motion_failure':sum(not r['motion_pass'] for r in rr),'median_signed_position_px':float(np.median([r['position_error_px'] for r in rr])),'worst_abs_position_px':max(abs(r['position_error_px']) for r in rr),'worst_abs_motion_px':max(abs(r['motion_error_px']) for r in rr)}
    # Re-render representative mismatch cases at 32x, retaining 8x records separately.
    convergence=[]
    for shape,sigma,phase in itertools.product(cfg['shapes'],cfg['psf_sigma_px'],[-.4,0,.4]):
        x,a=render(shape,sigma,phase,120,8);_,b=render(shape,sigma,phase,120,32)
        c8=fit_edge(x,a)['center'];c32=fit_edge(x,b)['center'];convergence.append({'shape':shape,'psf_sigma':sigma,'phase':phase,'center_8x':c8,'center_32x':c32,'difference_px':c8-c32})
    table('render_convergence.csv',convergence)
    fig,ax=plt.subplots(1,2,figsize=(10.5,3.8),layout='constrained')
    for shape,(x,y,a) in examples.items():ax[0].plot(x,(y-80)/120,label=f'{shape}, fit center {a["center"]:.2f}')
    ax[0].axvline(0,color='k',ls=':');ax[0].set(xlabel='Position (pixels)',ylabel='Normalized observation',title='Same physical boundary, different observed edges');ax[0].legend(fontsize=8)
    for i,shape in enumerate(cfg['shapes']):
        rr=[r for r in rows if r['shape']==shape];ax[1].scatter([i-.12]*len(rr),[r['position_error_px'] for r in rr],s=9,alpha=.35,color='C0');ax[1].scatter([i+.12]*len(rr),[r['motion_error_px'] for r in rr],s=9,alpha=.35,color='C1')
    ax[1].plot([],[],'o',color='C0',label='absolute position');ax[1].plot([],[],'o',color='C1',label='relative motion');ax[1].axhline(0,color='k',lw=.7);ax[1].set(xticks=range(4),xticklabels=cfg['shapes'],ylabel='Signed error (pixels)',title='Repeatability does not establish absolute accuracy');ax[1].legend(fontsize=8);fig.savefig(OUT/'physical_fit.png',dpi=170);plt.close(fig)
    return summary,{'count':len(convergence),'max_abs_center_difference_px':max(abs(r['difference_px']) for r in convergence)}

def main():
    op,detail=operator_matrix();ident=identifiability();phys,conv=physical_fit()
    summary={'operator':op,'detail_and_anchor':detail,'identifiability':ident,'physical_fit':phys,'render_convergence':conv,'scope':'Diagnostic observations, including failures. No trained model or universal 2D renderer is certified.'}
    (OUT/'operator_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

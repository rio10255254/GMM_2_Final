"""Readout candidates with no stage-command or expected-displacement input."""
from pathlib import Path
import sys
import numpy as np
from scipy import ndimage,optimize,special
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sources'))
from reference_circle_core import fit_lsc
from lsc_fixed_state import measure_inflection_lsc_fixed

def baseline(image,seed,radius,mag):
    m=measure_inflection_lsc_fixed(image,tuple(seed),radius,sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.,polarity='dark')
    return np.array([m.lsc.cx,m.lsc.cy,m.lsc.radius])

def radial_lsc(image,initial,mag):
    """Uniform 720-angle radial gradients, geometric circle fit, three recentering steps."""
    a=np.asarray(image,dtype=float);coeff=ndimage.spline_filter(a,order=3,mode='reflect');state=np.array(initial,dtype=float)
    theta=np.arange(720)*2*np.pi/720;ux=np.cos(theta);uy=np.sin(theta);half=2.4 if mag=='20x' else 4.
    offsets=np.arange(-half,half+.025,.05)
    for _ in range(3):
        radius=state[2]+offsets
        xx=state[0]+ux[:,None]*radius;yy=state[1]+uy[:,None]*radius
        profiles=ndimage.map_coordinates(coeff,[yy,xx],order=3,mode='reflect',prefilter=False)
        profiles=ndimage.gaussian_filter1d(profiles,.65/.05,axis=1,mode='nearest');deriv=np.gradient(profiles,.05,axis=1);peak=deriv.argmax(1)
        pos=offsets[peak].copy();good=(peak>0)&(peak<len(offsets)-1);ii=np.flatnonzero(good);k=peak[good]
        left=deriv[ii,k-1];middle=deriv[ii,k];right=deriv[ii,k+1];den=left-2*middle+right;safe=abs(den)>np.finfo(float).eps
        delta=np.zeros(len(ii));delta[safe]=np.clip(.5*(left[safe]-right[safe])/den[safe],-1,1);pos[good]+=.05*delta
        points=np.c_[state[0]+ux*(state[2]+pos),state[1]+uy*(state[2]+pos)]
        c=fit_lsc(points);state=np.array([c.cx,c.cy,c.radius])
    return state

def intensity_circle(image,initial):
    """Fit a blurred dark-circle profile plus a brightness plane; center remains free."""
    a=np.asarray(image,float);yy,xx=np.mgrid[:a.shape[0],:a.shape[1]];cx,cy,r=initial
    mask=np.hypot(xx-cx,yy-cy)<=r+min(5.,.6*r)
    x=xx[mask].astype(float);y=yy[mask].astype(float);v=a[mask]
    background=float(np.percentile(v,90));amplitude=max(float(np.percentile(v,90)-np.percentile(v,10)),.03)
    initial_sigma=max(.4,min(2.,r*.10));p0=np.array([cx,cy,r,initial_sigma,background,amplitude,0.,0.])
    def residual(p):
        px,py,rr,sigma,b,amp,gx,gy=p;distance=np.sqrt((x-px)**2+(y-py)**2+1e-12)
        profile=.5*special.erfc((distance-rr)/(np.sqrt(2)*sigma))
        return b-amp*profile+gx*(x-cx)+gy*(y-cy)-v
    bounds=([cx-2,cy-2,r*.75,.15,-.5,0,-.1,-.1],[cx+2,cy+2,r*1.25,4.,1.5,2,.1,.1])
    fit=optimize.least_squares(residual,p0,bounds=bounds,ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=80)
    if not fit.success or not np.isfinite(fit.x).all():raise RuntimeError('Circle intensity fit failed')
    return fit.x[:3]

def pair_translation(a,b,center_a,initial_delta,radius,background_plane=False):
    """Independent pillar translation, with only gain/offset as photometric nuisance terms."""
    a=np.asarray(a,float);b=np.asarray(b,float);cx,cy=center_a
    half=int(np.ceil(radius+min(3.,.3*radius)));gy,gx=np.mgrid[-half:half+1,-half:half+1]
    mask=(gx*gx+gy*gy)<=(radius+min(3.,.3*radius))**2
    x=cx+gx[mask];y=cy+gy[mask]
    ca=ndimage.spline_filter(a,order=3,mode='reflect');cb=ndimage.spline_filter(b,order=3,mode='reflect')
    template=ndimage.map_coordinates(ca,[y,x],order=3,mode='reflect',prefilter=False)
    design=np.c_[template,np.ones_like(template),x-cx,y-cy] if background_plane else np.c_[template,np.ones_like(template)]
    def residual(delta):
        observed=ndimage.map_coordinates(cb,[y+delta[1],x+delta[0]],order=3,mode='reflect',prefilter=False)
        coefficients=np.linalg.lstsq(design,observed,rcond=None)[0]
        return observed-design@coefficients
    start=np.asarray(initial_delta,float)
    fit=optimize.least_squares(residual,start,bounds=(start-1.5,start+1.5),diff_step=1e-3,ftol=1e-11,xtol=1e-11,gtol=1e-11,max_nfev=60)
    if not fit.success or not np.isfinite(fit.x).all():raise RuntimeError('Pair translation fit failed')
    return fit.x

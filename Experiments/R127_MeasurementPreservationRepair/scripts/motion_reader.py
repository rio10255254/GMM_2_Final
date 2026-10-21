"""Finite-domain correlation with explicit ambiguity; no requested-shift prior."""
import cv2
import numpy as np
from scipy.signal import fftconvolve

def features(a,kind):
    a=cv2.GaussianBlur(a.astype(np.float64),(0,0),1.)
    if kind=='intensity':return [a-cv2.GaussianBlur(a,(0,0),8.)]
    return [cv2.Sobel(a,cv2.CV_64F,1,0,ksize=3),cv2.Sobel(a,cv2.CV_64F,0,1,ksize=3)]

def integral(a):return np.pad(np.cumsum(np.cumsum(a,0),1),((1,0),(1,0)))
def rectangle(ii,x0,y0,x1,y1):return ii[y1,x1]-ii[y0,x1]-ii[y1,x0]+ii[y0,x0]

def surface(a,b,kind,max_shift=64):
    if a.shape!=b.shape or a.ndim!=2 or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('Equal finite gray images required')
    h,w=a.shape;limit=min(max_shift,min(h,w)//2);shifts=np.arange(-limit,limit+1);dx,dy=np.meshgrid(shifts,shifts)
    ax0=np.maximum(0,-dx);ay0=np.maximum(0,-dy);ax1=np.minimum(w,w-dx);ay1=np.minimum(h,h-dy)
    bx0=ax0+dx;by0=ay0+dy;bx1=ax1+dx;by1=ay1+dy;n=(ax1-ax0)*(ay1-ay0)
    numerator=np.zeros(dx.shape);var_a=numerator.copy();var_b=numerator.copy()
    for aa,bb in zip(features(a,kind),features(b,kind)):
        sums=[rectangle(integral(im),*box) for im,box in [(aa,(ax0,ay0,ax1,ay1)),(bb,(bx0,by0,bx1,by1)),(aa*aa,(ax0,ay0,ax1,ay1)),(bb*bb,(bx0,by0,bx1,by1))]]
        sa,sb,saa,sbb=sums;cross=fftconvolve(bb,aa[::-1,::-1],mode='full')[h-1+dy,w-1+dx]
        numerator+=cross-sa*sb/n;var_a+=saa-sa*sa/n;var_b+=sbb-sb*sb/n
    den=np.sqrt(np.maximum(var_a,0)*np.maximum(var_b,0));score=np.divide(numerator,den,out=np.full_like(numerator,-np.inf),where=den>1e-14)
    valid=(n>=h*w*.5)&np.isfinite(score);score=np.where(valid,score,-np.inf)
    return score,shifts,n/(h*w)

def estimate_feature(a,b,kind):
    score,shifts,overlap=surface(a,b,kind)
    if not np.isfinite(score).any():return {'valid_surface':False,'reason':'no_texture'},score
    py,px=np.unravel_index(np.argmax(score),score.shape);value=float(score[py,px]);dy,dx=np.mgrid[:score.shape[0],:score.shape[1]]
    competitors=score.copy();competitors[(dx-px)**2+(dy-py)**2<=16]=-np.inf
    second=float(np.max(competitors));gap=value-second
    offset=np.zeros(2);curvature_valid=False;edge=py in [0,len(shifts)-1] or px in [0,len(shifts)-1]
    if value>=1-1e-10:curvature_valid=True
    elif not edge and np.isfinite(score[py-1:py+2,px-1:px+2]).all():
        patch=score[py-1:py+2,px-1:px+2];gy=(patch[2,1]-patch[0,1])/2;gx=(patch[1,2]-patch[1,0])/2
        hxx=patch[1,2]-2*patch[1,1]+patch[1,0];hyy=patch[2,1]-2*patch[1,1]+patch[0,1];hxy=(patch[2,2]-patch[2,0]-patch[0,2]+patch[0,0])/4;hh=np.array([[hxx,hxy],[hxy,hyy]])
        if np.max(np.linalg.eigvalsh(hh))<-1e-8:
            candidate=-np.linalg.solve(hh,[gx,gy]);curvature_valid=bool(np.max(np.abs(candidate))<=1)
            if curvature_valid:offset=candidate
    row=dict(valid_surface=True,dx=float(shifts[px]+offset[0]),dy=float(shifts[py]+offset[1]),integer_dx=int(shifts[px]),integer_dy=int(shifts[py]),score=value,competing_score=second if np.isfinite(second) else None,peak_gap=gap if np.isfinite(gap) else None,overlap=float(overlap[py,px]),curvature_valid=curvature_valid,peak_at_search_boundary=bool(edge))
    return row,score

def measure(a,b):
    intensity,_=estimate_feature(a,b,'intensity');gradient,_=estimate_feature(a,b,'gradient');reasons=[]
    for name,r in [('intensity',intensity),('gradient',gradient)]:
        if not r['valid_surface']:reasons.append(name+':no_texture');continue
        if r['score']<.75:reasons.append(name+':poor_match')
        if r['peak_gap'] is None or r['peak_gap']<.02:reasons.append(name+':ambiguous_peak')
        if not r['curvature_valid']:reasons.append(name+':unstable_subpixel')
        if r['peak_at_search_boundary']:reasons.append(name+':search_boundary')
    disagreement=None
    if intensity['valid_surface'] and gradient['valid_surface']:
        disagreement=float(np.hypot(intensity['dx']-gradient['dx'],intensity['dy']-gradient['dy']))
        if disagreement>.5:reasons.append('intensity_gradient_disagree')
    accepted=not reasons
    return dict(accepted=accepted,dx=intensity.get('dx') if accepted else None,dy=intensity.get('dy') if accepted else None,reasons=reasons,intensity=intensity,gradient=gradient,feature_disagreement=disagreement,physical_stage_truth_available=False)

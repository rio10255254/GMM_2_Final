"""Locate with finite NCC, refine original pixels, scale ambiguity by residual.

V1's quadratic interpolation of filtered/cropped scores biased exact shifts.
V1's absolute-gap rule rejected near-perfect unique matches. Both failed tests
are retained; this revision is calibrated before any real candidate readout.
"""
from scipy.ndimage import map_coordinates,spline_filter
from scipy.optimize import least_squares
from motion_reader import estimate_feature,np

def refine_pixels(a,b,dx,dy):
    h,w=a.shape
    # One fixed, valid domain throughout optimization, including cubic support.
    x0=max(4,4-dx);x1=min(w-4,w-4-dx);y0=max(4,4-dy);y1=min(h-4,h-4-dy)
    yy,xx=np.mgrid[int(np.ceil(y0)):int(np.floor(y1)),int(np.ceil(x0)):int(np.floor(x1))]
    if xx.size<256:return {'accepted':False,'reason':'insufficient_refinement_support'}
    # Deterministic grid thinning for full frames; same domain in both axes.
    stride=max(1,int(np.ceil(np.sqrt(xx.size/50000))));yy=yy[::stride,::stride];xx=xx[::stride,::stride]
    reference=a[yy,xx].astype(float);coeff=spline_filter(b.astype(float),order=3)
    def residual(v,return_details=False):
        value=map_coordinates(coeff,[yy+v[1],xx+v[0]],order=3,prefilter=False,mode='constant')
        aa=reference-reference.mean();bb=value-value.mean();var=float(np.mean(bb**2))
        gain=float(np.mean(aa*bb)/max(var,1e-16));bias=float(reference.mean()-gain*value.mean());res=(gain*value+bias-reference)
        return (res,gain,bias) if return_details else res.ravel()
    result=least_squares(residual,[dx,dy],bounds=([dx-1,dy-1],[dx+1,dy+1]),diff_step=1e-4,ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=40)
    res,gain,bias=residual(result.x,True);edge=bool(np.any(np.abs(result.x-[dx,dy])>.99));accepted=bool(result.success and gain>0 and not edge)
    return dict(accepted=accepted,dx=float(result.x[0]),dy=float(result.x[1]),fitted_gain=gain,fitted_bias=bias,rms=float(np.sqrt(np.mean(res**2))),samples=int(xx.size),success=bool(result.success),at_refinement_boundary=edge)

def measure(a,b):
    intensity,_=estimate_feature(a,b,'intensity');gradient,_=estimate_feature(a,b,'gradient');reasons=[]
    for name,r in [('intensity',intensity),('gradient',gradient)]:
        if not r['valid_surface']:reasons.append(name+':no_texture');continue
        if r['score']<.75:reasons.append(name+':poor_match')
        ratio=r['peak_gap']/max(1-r['score'],1e-6) if r['peak_gap'] is not None else None
        r['peak_gap_relative_to_unexplained']=ratio
        if ratio is None or ratio<.5:reasons.append(name+':ambiguous_peak')
        if r['peak_at_search_boundary']:reasons.append(name+':search_boundary')
    disagreement=None;refined=None
    if intensity['valid_surface'] and gradient['valid_surface']:
        # Coarse integer localization is a separate independent-feature check.
        disagreement=float(np.hypot(intensity['integer_dx']-gradient['integer_dx'],intensity['integer_dy']-gradient['integer_dy']))
        if disagreement>1.5:reasons.append('intensity_gradient_disagree')
        if not reasons:
            refined=refine_pixels(a,b,intensity['integer_dx'],intensity['integer_dy'])
            if not refined['accepted']:reasons.append('original_pixel_refinement_failed')
    accepted=not reasons and refined is not None
    return dict(accepted=bool(accepted),dx=refined['dx'] if accepted else None,dy=refined['dy'] if accepted else None,reasons=reasons,intensity=intensity,gradient=gradient,feature_disagreement=disagreement,pixel_refinement=refined,physical_stage_truth_available=False)

"""Explicit image-derived diagnostics, not claims of independent material truth."""
import numpy as np,cv2

def crossings(profile,level):
    p=np.asarray(profile,float);i=np.flatnonzero((p[:-1]>=level)!=(p[1:]>=level))
    return i+(level-p[i])/(p[i+1]-p[i]),np.sign(p[i+1]-p[i]).astype(int)

def stats(values):
    a=np.asarray(values,float)
    if not a.size:return dict(count=0,median_signed=None,median_absolute=None,p95_absolute=None,maximum_absolute=None)
    return dict(count=int(a.size),median_signed=float(np.median(a)),median_absolute=float(np.median(np.abs(a))),p95_absolute=float(np.quantile(np.abs(a),.95)),maximum_absolute=float(np.max(np.abs(a))))

def compare_profile(raw,predicted,level,mode='Raw_anchored'):
    a,b=np.quantile(raw,[.1,.9]);threshold=a+level*(b-a)
    if mode=='self_normalized':
        c,d=np.quantile(predicted,[.1,.9]);other=c+level*(d-c)
    else:other=threshold
    x,sgn=crossings(raw,threshold);y,sy=crossings(predicted,other)
    result=dict(mode=mode,level=level,Raw_contrast_gray=float((b-a)*255),Raw_crossings=len(x),candidate_crossings=len(y),equal_counts_and_directions=bool(len(x)==len(y) and np.array_equal(sgn,sy)))
    if result['equal_counts_and_directions'] and len(x):
        result['edge_change_px']=stats(y-x)
        result['large_relative_to_spacing']=bool(len(x)>1 and np.max(np.abs(y-x))>.45*np.median(np.diff(x)))
        for sign,name in [(-1,'dark_line_width_change_px'),(1,'bright_gap_width_change_px')]:
            ids=np.flatnonzero((sgn[:-1]==sign)&(sgn[1:]==-sign))
            result[name]=stats((y[ids+1]-y[ids])-(x[ids+1]-x[ids]))
    else:
        result.update(edge_change_px=stats([]),dark_line_width_change_px=stats([]),bright_gap_width_change_px=stats([]),large_relative_to_spacing=None)
    return result

def corner_positions(image,points):
    a=np.asarray(image,np.float32);p=np.asarray(points,np.float32).reshape(-1,1,2).copy()
    q=cv2.cornerSubPix(a,p,(5,5),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,50,1e-5)).reshape(-1,2)
    eigen=cv2.cornerMinEigenVal(a,3,3);quality=[]
    for x,y in q:
        xx,yy=int(round(x)),int(round(y))
        quality.append(float(eigen[yy,xx]) if 0<=xx<a.shape[1] and 0<=yy<a.shape[0] else 0.)
    return q,np.asarray(quality)

def mask_diagnostics(reference,image,level,bright_foreground):
    truth=reference>=level if bright_foreground else reference<level
    mask=image>=level if bright_foreground else image<level
    union=np.sum(truth|mask);iou=float(np.sum(truth&mask)/max(1,union))
    def topology(a):
        n,_=cv2.connectedComponents(a.astype(np.uint8),connectivity=8)
        _,h=cv2.findContours(np.pad(a.astype(np.uint8),1),cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        holes=0 if h is None else int(np.sum(h[0,:,3]>=0))
        return dict(components=int(n-1),holes=holes)
    positions=[];unmatched=0;expected=0;actual=0;extra_lines=0;reference_lines=0
    for a,b in [(reference,image),(reference.T,image.T)]:
        for r,p in zip(a,b):
            x,s=crossings(r,level);y,t=crossings(p,level)
            expected+=len(x);actual+=len(y)
            if not len(x):
                if len(y):extra_lines+=1
                continue
            reference_lines+=1
            if len(x)==len(y) and np.array_equal(s,t):positions.extend((y-x).tolist())
            else:unmatched+=1
    return dict(mask_IoU=iou,reference_topology=topology(truth),image_topology=topology(mask),reference_crossings=expected,image_crossings=actual,reference_scanlines=reference_lines,unmatched_reference_scanlines=unmatched,spurious_crossing_scanlines=extra_lines,matched_crossing_error_px=stats(positions))

def self_test():
    p=np.r_[np.zeros(10),np.arange(1,11)/10,np.ones(10)]
    q=np.r_[np.zeros(12),np.arange(1,11)/10,np.ones(8)]
    a=compare_profile(p,q,.5);assert abs(a['edge_change_px']['median_signed']-2)<1e-12
    assert not compare_profile(np.tile([0.,0.,1.,1.],8),np.ones(32),.5)['equal_counts_and_directions']
    refs=[]
    yy,xx=np.mgrid[:65,:65]
    for cx,cy in [(31.,31.),(31.2,30.7),(33.1,30.4)]:
        for width in [1.,2.]:
            im=.2+.6*(1+np.tanh((xx-cx)/width)*np.tanh((yy-cy)/width))/2
            point,e=corner_positions(im,[[32.,32.]])
            error=float(np.linalg.norm(point[0]-[cx,cy]));assert error<.1
            assert e[0]>1e-6
            refs.append(dict(cx=cx,cy=cy,width=width,error_px=error))
    _,e=corner_positions(np.ones((65,65),np.float32),[[32.,32.]])
    assert e[0]==0
    return dict(passed=True,profile_known_shift_exact=True,missing_edges_retained=True,constant_corner_rejected=True,corner_fixture_results=refs)

"""Joint finite correlation and noise-stabilized pixel refinement.

No change to the0.1px accuracy or90percent known-crop coverage requirement.
V2 incorrectly required an individually unique low-frequency cue even when
the combined intensity/gradient surface uniquely localized the same object.
Smoothing both images before refinement reduces interpolation/noise coupling;
valid support is expanded to8pixels, independently of the desired motion.
"""
from motion_reader import surface,np,cv2
from motion_reader_v2 import refine_pixels

def measure(a,b):
    si,shifts,overlap=surface(a,b,'intensity');sg,_,_=surface(a,b,'gradient');joint=(si+sg)/2
    if not np.isfinite(joint).any():return dict(accepted=False,dx=None,dy=None,reasons=['no_texture'],physical_stage_truth_available=False)
    py,px=np.unravel_index(np.argmax(joint),joint.shape);value=float(joint[py,px]);yy,xx=np.mgrid[:joint.shape[0],:joint.shape[1]];other=joint.copy();other[(xx-px)**2+(yy-py)**2<=16]=-np.inf;second=float(other.max());gap=value-second;relative=gap/max(1-value,1e-6)
    iy,ix=np.unravel_index(np.argmax(si),si.shape);gy,gx=np.unravel_index(np.argmax(sg),sg.shape);disagreement=float(np.hypot(ix-gx,iy-gy));reasons=[]
    if si[py,px]<.75 or sg[py,px]<.75:reasons.append('poor_match')
    if relative<.5:reasons.append('ambiguous_joint_peak')
    if disagreement>1.5:reasons.append('intensity_gradient_disagree')
    if py in [0,len(shifts)-1] or px in [0,len(shifts)-1]:reasons.append('search_boundary')
    ref=None
    if not reasons:
        # Additional4pixel border excludes the preprocessing boundary; the
        # refinement utility then retains its own4pixel interpolation support.
        aa=cv2.GaussianBlur(a.astype(float),(0,0),1.)[4:-4,4:-4];bb=cv2.GaussianBlur(b.astype(float),(0,0),1.)[4:-4,4:-4]
        ref=refine_pixels(aa,bb,int(shifts[px]),int(shifts[py]))
        if not ref['accepted']:reasons.append('refinement_failed')
    accepted=not reasons and ref is not None
    return dict(accepted=bool(accepted),dx=ref['dx'] if accepted else None,dy=ref['dy'] if accepted else None,reasons=reasons,joint_score=value,competing_score=second,peak_gap=gap,relative_peak_gap=relative,integer_dx=int(shifts[px]),integer_dy=int(shifts[py]),feature_disagreement=disagreement,overlap=float(overlap[py,px]),pixel_refinement=ref,physical_stage_truth_available=False)

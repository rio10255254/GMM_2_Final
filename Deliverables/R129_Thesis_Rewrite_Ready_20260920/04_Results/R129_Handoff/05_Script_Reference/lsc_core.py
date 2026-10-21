"""Reuse thesis boundary/LSC math; new capture tracking is image-only."""
import os
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='1'
from common import *
import numpy as np,cv2
from scipy.optimize import linear_sum_assignment
import skimage.segmentation.morphsnakes as morphsnakes
CORE_PATH=REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/reference_circle_core.py'
core=module('r136_thesis_lsc_core',CORE_PATH)

def reset_curvature():
    morphsnakes._curvop=morphsnakes._fcycle([lambda x:morphsnakes.sup_inf(morphsnakes.inf_sup(x)),lambda x:morphsnakes.inf_sup(morphsnakes.sup_inf(x))])

def candidates(raw):
    roi=raw[250:650,650:1350];_,mask=cv2.threshold(roi,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    _,_,stats,centers=cv2.connectedComponentsWithStats(mask)
    use=(stats[:,4]>30)&(stats[:,4]<600)&(stats[:,2]<35)&(stats[:,3]<35)
    return centers[use]+[650,250],np.sqrt(stats[use,4]/np.pi)

def match(predicted,centers,max_distance):
    distance=np.linalg.norm(np.asarray(predicted)[:,None,:]-centers[None,:,:],axis=2);a,b=linear_sum_assignment(distance)
    assert np.array_equal(a,np.arange(len(predicted)))
    if distance[a,b].max()>max_distance:raise ValueError('Raw target association exceeds half-pitch neighborhood')
    return centers[b],b

def measure_image(image,centers,cfg):
    rows=[];points=[];coarse=[];strength=[]
    for pid,(x,y) in enumerate(centers,1):
        patch,pc,origin=core.crop_around(image,(float(x),float(y)),cfg['patch_half'])
        reset_curvature()
        result=core.measure_inflection_lsc(patch,pc,cfg['radius_px'],sample_count=cfg['sample_count'],acm_iterations=cfg['acm_iterations'],normal_half_width_px=cfg['normal_half_width_px'],polarity='dark')
        c=result.lsc;xy=result.inflection_points_xy+np.array(origin);circle=np.array([c.cx+origin[0],c.cy+origin[1]])
        radial=np.linalg.norm(xy-circle,axis=1)-c.radius
        assert np.isfinite([*circle,c.radius]).all()
        rows.append(dict(pillar_id=pid,center_x_px=float(circle[0]),center_y_px=float(circle[1]),radius_px=float(c.radius),seed_x_px=float(x),seed_y_px=float(y),radial_rms_px=float(np.sqrt(np.mean(radial**2))),gradient_median=float(np.median(result.signed_gradient_strength))))
        points.append(xy);coarse.append(result.coarse_contour_xy+np.array(origin));strength.append(result.signed_gradient_strength)
    return rows,dict(points=np.array(points),coarse=np.array(coarse),strength=np.array(strength))

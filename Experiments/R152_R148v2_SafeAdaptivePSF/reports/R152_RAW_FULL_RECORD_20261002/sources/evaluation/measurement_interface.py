import numpy as np
import skimage.segmentation.morphsnakes as morphsnakes
from evaluation import reference_circle_core as core

def reset_curvature():
    morphsnakes._curvop=morphsnakes._fcycle([lambda x:morphsnakes.sup_inf(morphsnakes.inf_sup(x)),lambda x:morphsnakes.inf_sup(morphsnakes.sup_inf(x))])

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

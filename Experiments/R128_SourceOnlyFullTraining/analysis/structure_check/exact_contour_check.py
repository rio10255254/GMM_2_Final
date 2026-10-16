"""Exact nearest segment distances; avoid point-resampling tangential error."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,contourpy
from scipy.spatial import cKDTree

def segments(image,level):
    curves=contourpy.contour_generator(z=np.asarray(image,float)).lines(level)
    if not curves:return np.empty((0,2)),np.empty((0,2))
    a=np.concatenate([c[:-1] for c in curves]);b=np.concatenate([c[1:] for c in curves]);keep=np.linalg.norm(b-a,axis=1)>1e-12
    return a[keep],b[keep]

def queries(a,b,spacing):
    points=[];weights=[]
    for x,y in zip(a,b):
        length=np.linalg.norm(y-x);n=max(1,int(np.ceil(length/spacing)))
        points.append(x+(y-x)*(np.arange(n)+.5)[:,None]/n);weights.append(np.full(n,length/n))
    if not points:return np.empty((0,2)),np.empty(0)
    return np.vstack([*points,a,b]),np.r_[*weights,np.zeros(len(a)*2)]

def nearest(query,a,b):
    if not len(query):return np.empty(0)
    mid=(a+b)/2;tree=cKDTree(mid);halfmax=float(np.linalg.norm(b-a,axis=1).max()/2)
    result=np.full(len(query),np.inf);pending=np.arange(len(query));k=min(8,len(a))
    while len(pending):
        d,ids=tree.query(query[pending],k=k)
        if k==1:d=d[:,None];ids=ids[:,None]
        start=a[ids];vec=b[ids]-start;offset=query[pending,None,:]-start
        t=(np.sum(offset*vec,axis=2)/np.sum(vec*vec,axis=2)).clip(0,1)
        exact=np.linalg.norm(offset-t[:,:,None]*vec,axis=2).min(axis=1)
        proven=(d[:,-1]-halfmax>=exact-1e-12) if k<len(a) else np.ones(len(pending),bool)
        result[pending[proven]]=exact[proven];pending=pending[~proven];k=min(k*2,len(a))
    return result

def metric(reference,image,level,spacing=.1):
    a,b=segments(reference,level);c,d=segments(image,level)
    qa,wa=queries(a,b,spacing);qb,wb=queries(c,d,spacing)
    inside=lambda q:np.all((q>=32)&(q<160),axis=1)
    ma=inside(qa);mb=inside(qb);qa,wa=qa[ma],wa[ma];qb,wb=qb[mb],wb[mb]
    if not len(qa) or not len(qb):return dict(available=False,reference_query_points=len(qa),image_query_points=len(qb))
    values=np.r_[nearest(qa,c,d),nearest(qb,a,b)];weights=np.r_[wa,wb]
    order=np.argsort(values);positive=weights[order]>0;v=values[order][positive];w=weights[order][positive];cdf=np.cumsum(w)/w.sum()
    return dict(available=True,arc_weighted_mean_px=float(np.sum(values*weights)/weights.sum()),arc_weighted_p95_px=float(v[np.searchsorted(cdf,.95)]),maximum_px=float(values.max()),query_spacing_px=spacing,exact_nearest_segments=True,query_core_size=128,support_margin=32)

def main():
    out=ROOT/'results/structure_check';controls=load(out/'controls.json')
    # Two representations of the same line must yield zero despite different
    # vertex placement. This catches the earlier point-cloud approximation.
    q=np.array([[0.,.23],[0.,.81],[0.,1.37]])
    a=np.array([[0.,0.],[0.,.9]]);b=np.array([[0.,.9],[0.,2.]])
    assert np.max(nearest(q,a,b))<1e-12
    x=np.arange(192)[None,:];ref=np.broadcast_to(((x>60)&(x<120)).astype(float),(192,192));shift=np.broadcast_to(((x>62)&(x<122)).astype(float),(192,192))
    test=metric(ref,shift,.5);assert abs(test['arc_weighted_mean_px']-2)<1e-12 and abs(test['maximum_px']-2)<1e-12
    rows=[];convergence=[]
    for row in controls:
        with np.load(out/'full_context_controls'/row['parent_id']/'images.npz') as f:target=f['target'];raw=f['Raw'];pred=f['output']
        level=row['threshold_gray']/255
        result=dict(parent_id=row['parent_id'],category=row['category'],Raw=metric(target,raw,level),candidate=metric(target,pred,level))
        rows.append(result)
        if row['category']=='clean_identity':
            fine=metric(target,pred,level,.05)
            convergence.append(dict(parent_id=row['parent_id'],mean_difference_px=abs(fine['arc_weighted_mean_px']-result['candidate']['arc_weighted_mean_px']),maximum_difference_px=abs(fine['maximum_px']-result['candidate']['maximum_px']),fine_result=fine))
    summary=[]
    for category in sorted({x['category'] for x in rows}):
        group=[x for x in rows if x['category']==category];both=[x for x in group if x['Raw']['available'] and x['candidate']['available']]
        summary.append(dict(category=category,parents=len(group),paired_measurable=len(both),candidate_unavailable=[x['parent_id'] for x in group if not x['candidate']['available']],mean_Raw_boundary_error_px=float(np.mean([x['Raw']['arc_weighted_mean_px'] for x in both])),mean_candidate_boundary_error_px=float(np.mean([x['candidate']['arc_weighted_mean_px'] for x in both])),candidate_worse_parents=sum(x['candidate']['arc_weighted_mean_px']>x['Raw']['arc_weighted_mean_px']+1e-12 for x in both),maximum_candidate_boundary_error_px=max(x['candidate']['maximum_px'] for x in both)))
    assert max(x['mean_difference_px'] for x in convergence)<.001
    save(out/'exact_contour_geometry.json',dict(completed=True,rows=rows,summary=summary,clean_control_sampling_convergence=convergence,tests=dict(same_line_different_vertices_exact_zero=True,known_two_pixel_translation_exact=True),previous_point_cloud_metrics_retained_as_approximation=True,source=record(__file__)))
    print(json.dumps(dict(summary=summary,convergence=convergence)),flush=True)

if __name__=='__main__':main()

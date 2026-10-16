"""Follow up flags without rewriting original readouts or declaring false motion."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from readouts import *
from evaluation.real import read_image
from scipy.spatial import cKDTree
import contourpy,pandas as pd

def contour_points(image,level,spacing=.1):
    curves=contourpy.contour_generator(z=np.asarray(image,float)).lines(level);parts=[]
    for curve in curves:
        for a,b in zip(curve[:-1],curve[1:]):
            n=max(1,int(np.ceil(np.linalg.norm(b-a)/spacing)))
            parts.append(a+(b-a)*np.arange(n)[:,None]/n)
    return np.concatenate(parts) if parts else np.empty((0,2))

def distances(reference,image,level):
    a=contour_points(reference,level);b=contour_points(image,level)
    if not len(a) or not len(b):return dict(available=False,reference_points=len(a),image_points=len(b))
    ab=cKDTree(b).query(a)[0];ba=cKDTree(a).query(b)[0];all_d=np.r_[ab,ba]
    return dict(available=True,reference_points=len(a),image_points=len(b),symmetric_mean_px=float(all_d.mean()),symmetric_p95_px=float(np.quantile(all_d,.95)),symmetric_maximum_px=float(all_d.max()),sampling_spacing_px=.1,no_point_identity_assumed=True)

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');inf=load(out/'inference.json');outputs={x['key']:x['output'] for x in inf['outputs']};sources={x['key']:x for x in plan['sources']}
    def images(key):
        raw=read_image(sources[key]['source'])
        p=outputs[key];assert sha(p['path'])==p['sha256']
        with np.load(p['path']) as d:pred=d['output']
        return raw,pred
    flag=next(x for x in plan['features'] if x['id']=='20x_1um_v0');raw,pred=images(flag['source_key']);x0,y0,x1,y1=flag['box']
    level=float(np.mean(np.quantile(np.median(raw[y0:y1,x0:x1],axis=0),[.1,.9])))
    original=[];expanded=[]
    for name,im in [('Raw',raw),('candidate',pred)]:
        old=np.median(im[y0:y1,x0:x1],axis=0);large=np.median(im[y0:y1,x0-16:x1+16],axis=0)
        a,da=crossings(old,level);b,db=crossings(large,level)
        original.append(dict(name=name,count=len(a),locations=a.tolist(),directions=da.tolist()))
        expanded.append(dict(name=name,count=len(b),locations_original_coordinates=(b-16).tolist(),directions=db.tolist()))
    a,b=expanded;assert a['count']==b['count']==51 and a['directions']==b['directions']
    shifts=np.asarray(b['locations_original_coordinates'])-a['locations_original_coordinates']
    boundary=dict(original_count=[x['count'] for x in original],expanded_count=[x['count'] for x in expanded],expansion_native_pixels=16,original_threshold_reused=True,expanded_edge_changes=stats(shifts),Raw_edge_near_right=698.8571427214358,candidate_edge_near_right=699.0648475911114,original_last_sample_coordinate=699,interpretation='The final crossing leaves the original699coordinate sampled segment; no missing interior line established',original=original,expanded=expanded)
    # Same Raw-selected44points, multiple declared fitting apertures. Keep all.
    sensitivity=[]
    for feature in plan['features']:
        if 'points' not in feature:continue
        raw,pred=images(feature['source_key']);pts=np.asarray(feature['points'],np.float32).reshape(-1,1,2)
        for window in [3,5,7,9]:
            refine=lambda im:cv2.cornerSubPix(im.astype(np.float32),pts.copy(),(window,window),(-1,-1),(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_MAX_ITER,50,1e-5)).reshape(-1,2)
            a,b=refine(raw),refine(pred)
            for i,(x,y) in enumerate(zip(a,b)):
                sensitivity.append(dict(id=feature['id'],feature_index=i,kind=feature['kind'],window_halfwidth=window,dx=float(y[0]-x[0]),dy=float(y[1]-x[1]),change_px=float(np.linalg.norm(y-x))))
    pd.DataFrame(sensitivity).to_csv(out/'corner_window_sensitivity.csv',index=False)
    # A correspondence-free2Ddistance prevents periodic edge-index swaps from
    # being described as actual object translations.
    controls=load(out/'controls.json');dist=[]
    for row in controls:
        with np.load(out/'controls'/row['parent_id']/'core.npz') as d:
            target=d['target'];a=d['Raw'];b=d['output']
        level=row['threshold_gray']/255
        dist.append(dict(parent_id=row['parent_id'],category=row['category'],Raw=distances(target,a,level),candidate=distances(target,b,level),ordered_maximum_px=row['candidate']['matched_crossing_error_px']['maximum_absolute']))
    save(out/'contour_distance_followup.json',dist)
    # Locate the one new mask-topology discrepancy; do not assume interior loss.
    row=next(x for x in controls if x['parent_id']=='r128_test_0055')
    with np.load(out/'controls/r128_test_0055/core.npz') as d:target=d['target'];candidate=d['output'];material=d['material']
    level=row['threshold_gray']/255;bright=float(np.median(target[material>.9]))>float(np.median(target[material<.1]))
    binary=lambda x:(x>=level if bright else x<level).astype(np.uint8)
    nt,truth,st,ct=cv2.connectedComponentsWithStats(binary(target),8);npred,pred,sp,cp=cv2.connectedComponentsWithStats(binary(candidate),8);components=[]
    for i in range(1,npred):
        x,y,w,h,area=sp[i];matches=np.unique(truth[pred==i]);components.append(dict(component=i,box=[int(x),int(y),int(w),int(h)],area=int(area),touches_core_boundary=bool(x==0 or y==0 or x+w==128 or y+h==128),overlaps_reference_components=[int(a) for a in matches if a]))
    save(out/'topology_flag_location.json',dict(parent='r128_test_0055',reference_components=nt-1,candidate_components=npred-1,candidate_components_detail=components))
    summary=[]
    for category in sorted({x['category'] for x in dist}):
        g=[x for x in dist if x['category']==category]
        summary.append(dict(category=category,parents=len(g),mean_Raw_symmetric_boundary_distance=float(np.mean([x['Raw']['symmetric_mean_px'] for x in g])),mean_candidate_symmetric_boundary_distance=float(np.mean([x['candidate']['symmetric_mean_px'] for x in g])),candidate_mean_distance_worse_parents=sum(x['candidate']['symmetric_mean_px']>x['Raw']['symmetric_mean_px']+1e-12 for x in g),worst_candidate_nearest_boundary_distance=max(x['candidate']['symmetric_maximum_px'] for x in g)))
    save(out/'flag_followup.json',dict(completed=True,profile_boundary_flag=boundary,contour_summary=summary,corner_window_groups=pd.DataFrame(sensitivity).groupby(['kind','window_halfwidth']).change_px.agg(['median','max']).reset_index().to_dict('records'),source=record(__file__),old_results_unchanged=True,interpretation='Neither periodic ordered-crossing distance nor corner-readout change is by itself a physical object displacement'))
    print(json.dumps(dict(profile_original_counts=boundary['original_count'],profile_expanded_counts=boundary['expanded_count'],expanded_edge_max=boundary['expanded_edge_changes']['maximum_absolute'],contours=summary,corner_sensitivity=pd.DataFrame(sensitivity).groupby(['kind','window_halfwidth']).change_px.agg(['median','max']).reset_index().to_dict('records'))),flush=True)

if __name__=='__main__':main()

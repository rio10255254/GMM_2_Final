"""Retain unavailable contours and distinguish crop artifacts from missing structure."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from readouts import *
from evaluation.real import read_image
from training.engine import create
from training.data import Bank
import torch,pandas as pd

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');inf=load(out/'inference.json')
    dist=load(out/'contour_distance_followup.json');summaries=[]
    for category in sorted({x['category'] for x in dist}):
        g=[x for x in dist if x['category']==category];common=[x for x in g if x['Raw']['available'] and x['candidate']['available']]
        summaries.append(dict(category=category,all_parents=len(g),common_measurable_parents=len(common),Raw_unavailable=[x['parent_id'] for x in g if not x['Raw']['available']],candidate_unavailable=[x['parent_id'] for x in g if not x['candidate']['available']],common_mean_Raw_boundary_distance=float(np.mean([x['Raw']['symmetric_mean_px'] for x in common])),common_mean_candidate_boundary_distance=float(np.mean([x['candidate']['symmetric_mean_px'] for x in common])),candidate_mean_distance_worse_common_parents=sum(x['candidate']['symmetric_mean_px']>x['Raw']['symmetric_mean_px']+1e-12 for x in common),maximum_candidate_nearest_boundary_distance_available=max(x['candidate']['symmetric_maximum_px'] for x in g if x['candidate']['available'])))
    feature=next(x for x in plan['features'] if x['id']=='20x_1um_v0');source=next(x for x in plan['sources'] if x['key']==feature['source_key']);output=next(x['output'] for x in inf['outputs'] if x['key']==feature['source_key']);raw=read_image(source['source'])
    with np.load(output['path']) as f:pred=f['output']
    x0,y0,x1,y1=feature['box'];p=np.median(raw[y0:y1,x0:x1],axis=0);level=float(np.mean(np.quantile(p,[.1,.9])));segments=[]
    for name,im in [('Raw',raw),('candidate',pred)]:
        small=np.median(im[y0:y1,x0:x1],axis=0);large=np.median(im[y0:y1,x0-16:x1+16],axis=0);a,da=crossings(small,level);b,db=crossings(large,level)
        segments.append(dict(name=name,original_count=len(a),expanded_count=len(b),expanded_positions_in_original_coordinates=(b-16).tolist(),directions=db.tolist()))
    a,b=segments;assert a['expanded_count']==b['expanded_count']==51 and a['directions']==b['directions']
    delta=np.asarray(b['expanded_positions_in_original_coordinates'])-a['expanded_positions_in_original_coordinates']
    exiting=[dict(Raw=x,candidate=y) for x,y in zip(a['expanded_positions_in_original_coordinates'],b['expanded_positions_in_original_coordinates']) if 0<=x<x1-x0-1 and not 0<=y<x1-x0-1]
    assert len(exiting)==1
    endpoint=dict(original_counts=[x['original_count'] for x in segments],expanded_counts=[x['expanded_count'] for x in segments],fixed_threshold_gray=level*255,exiting_crossing=exiting,expanded_edge_change=stats(delta),interpretation='One crossing passes outside the original last sampled coordinate; no interior missing line established',original_results_preserved=True)
    # Resolve the additional1pixel component at the crop boundary using actual
    # surrounding context; no original control or mask is overwritten.
    cfg=load(ROOT/'config/study.json');bank=Bank();model,opt=create(1285002,'cuda',cfg);model.load_state_dict(torch.load(plan['checkpoint']['path'],map_location='cpu')['model']);model.eval();batch=bank.batch('test',55,'cuda')
    with torch.inference_mode():whole=model(batch['source'])[0,0].cpu().numpy()
    with np.load(out/'controls/r128_test_0055/core.npz') as f:old=f['output'];material=f['material'];target=f['target']
    assert np.array_equal(whole[96:224,96:224],old)
    reference=batch['target'][0,0].cpu().numpy();raw_control=batch['source'][0,0].cpu().numpy();level=load(out/'controls/r128_test_0055/measurements.json')['threshold_gray']/255
    bright=np.median(target[material>.9])>np.median(target[material<.1]);binary=lambda x:(x>=level if bright else x<level).astype(np.uint8)
    target_big=reference[80:240,80:240];pred_big=whole[80:240,80:240];n,labels,component_stats,centroids=cv2.connectedComponentsWithStats(binary(pred_big),8)
    label=int(labels[78+16,16]);area=int(component_stats[label,4]) if label else 0;inside_core=np.zeros((160,160),bool);inside_core[16:144,16:144]=True
    outside_reference_overlap=int(np.sum((labels==label)&(binary(target_big)>0)&~inside_core)) if label else 0
    crop_flag=dict(parent='r128_test_0055',original_extra_component_area=1,original_extra_component_touches_crop_boundary=True,expanded_component_area=area,reference_overlap_outside_original_core=outside_reference_overlap,core_output_reproduced_exactly=True,interpretation='Boundary pixel belongs to a larger nearby structure in expanded context' if outside_reference_overlap>0 else 'Boundary discrepancy unresolved; no interior-object claim')
    np.savez_compressed(out/'topology_expanded_context.npz',target=target_big,Raw=raw_control[80:240,80:240],output=pred_big)
    corners=pd.read_csv(out/'corner_window_sensitivity.csv');corner_summary=corners.groupby(['kind','window_halfwidth']).change_px.agg(['median','max']).reset_index().to_dict('records')
    result=dict(completed=True,completed_utc=now(),contour_summary=summaries,profile_endpoint_diagnosis=endpoint,topology_crop_diagnosis=crop_flag,corner_aperture_sensitivity=corner_summary,interpretation='Ordered periodic edge pairing and corner-reader changes must not be interpreted as verified physical motion',source=record(__file__),initial_failed_aggregation_retained=True)
    save(out/'flag_followup.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()

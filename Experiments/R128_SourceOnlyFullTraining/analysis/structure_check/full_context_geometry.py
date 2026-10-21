"""Use real surrounding pixels for contour correspondence around the scored core."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from training.engine import create
from training.data import Bank
from confirm_findings import contour_points
from scipy.spatial import cKDTree
import numpy as np,torch

def metric(target,image,level):
    a=contour_points(target,level);b=contour_points(image,level)
    inside=lambda p:np.all((p>=32)&(p<160),axis=1)
    aq=a[inside(a)];bq=b[inside(b)]
    if not len(aq) or not len(bq):return dict(available=False,reference_core_points=len(aq),image_core_points=len(bq),reference_context_points=len(a),image_context_points=len(b))
    ab=cKDTree(b).query(aq)[0];ba=cKDTree(a).query(bq)[0];d=np.r_[ab,ba]
    return dict(available=True,reference_core_points=len(aq),image_core_points=len(bq),mean_px=float(np.mean(d)),p95_px=float(np.quantile(d,.95)),maximum_px=float(d.max()),reference_to_image_max_px=float(ab.max()),image_to_reference_max_px=float(ba.max()),query_core_size=128,actual_surrounding_context=32,sampling_spacing=.1)

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');controls=load(out/'controls.json');bank=Bank();model,opt=create(1285002,'cuda',load(ROOT/'config/study.json'));cp=plan['checkpoint'];assert sha(cp['path'])==cp['sha256'];model.load_state_dict(torch.load(cp['path'],map_location='cpu')['model']);model.eval();rows=[]
    for row in controls:
        b=bank.batch('test',row['index'],'cuda')
        with torch.inference_mode():whole=model(b['source'])[0,0].cpu().numpy()
        with np.load(out/'controls'/row['parent_id']/'core.npz') as d:old=d['output']
        assert np.array_equal(whole[96:224,96:224],old)
        target=b['target'][0,0,64:256,64:256].cpu().numpy();raw=b['source'][0,0,64:256,64:256].cpu().numpy();pred=whole[64:256,64:256]
        level=row['threshold_gray']/255
        result=dict(parent_id=row['parent_id'],category=row['category'],level=level,Raw=metric(target,raw,level),candidate=metric(target,pred,level),old_core_bitwise_preserved=True)
        rows.append(result);folder=out/'full_context_controls'/row['parent_id'];folder.mkdir(parents=True,exist_ok=False);np.savez_compressed(folder/'images.npz',target=target,Raw=raw,output=pred)
    summary=[]
    for category in sorted({x['category'] for x in rows}):
        g=[x for x in rows if x['category']==category];valid=[x for x in g if x['Raw']['available'] and x['candidate']['available']]
        summary.append(dict(category=category,parents=len(g),common_valid=len(valid),candidate_unavailable=[x['parent_id'] for x in g if not x['candidate']['available']],mean_Raw_boundary_distance=float(np.mean([x['Raw']['mean_px'] for x in valid])),mean_candidate_boundary_distance=float(np.mean([x['candidate']['mean_px'] for x in valid])),candidate_worse_parents=sum(x['candidate']['mean_px']>x['Raw']['mean_px']+1e-12 for x in valid),maximum_candidate_boundary_distance=max(x['candidate']['maximum_px'] for x in g if x['candidate']['available'])))
    save(out/'full_context_geometry.json',dict(completed=True,rows=rows,summary=summary,source=record(__file__),contour_source=record(Path(__file__).with_name('confirm_findings.py')),previous_cropped_metrics_retained=True,physical_reference_role='generated optical reference only'))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()

"""Match the original observed crossings using actual surrounding support."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from readouts import crossings
from evaluation.real import read_image
from scipy.optimize import linear_sum_assignment
import numpy as np

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');profiles=load(out/'real_profiles.json');outputs={x['key']:x['output'] for x in load(out/'inference.json')['outputs']};sources={x['key']:x for x in plan['sources']};features={x['id']:x for x in plan['features']};rows=[]
    for flag in profiles:
        if flag['equal_counts_and_directions']:continue
        feature=features[flag['id']];raw=read_image(sources[feature['source_key']]['source'])
        with np.load(outputs[feature['source_key']]['path']) as f:pred=f['output']
        x0,y0,x1,y1=feature['box'];axis=0 if feature['profile_axis']=='x' else 1
        rp=np.median(raw[y0:y1,x0:x1],axis=axis);pp=np.median(pred[y0:y1,x0:x1],axis=axis)
        lo,hi=np.quantile(rp,[.1,.9]);rlevel=lo+flag['level']*(hi-lo)
        plo,phi=np.quantile(pp,[.1,.9]);plevel=plo+flag['level']*(phi-plo) if flag['mode']=='self_normalized' else rlevel
        big=np.median(pred[y0:y1,x0-16:x1+16],axis=0) if axis==0 else np.median(pred[y0-16:y1+16,x0:x1],axis=1)
        a,da=crossings(rp,rlevel);b,db=crossings(big,plevel);b-=16
        cost=np.abs(a[:,None]-b[None,:]);cost[da[:,None]!=db[None,:]]=1e8;i,j=linear_sum_assignment(cost)
        margin=float(np.min(np.diff(a))/2);all_matched=bool(len(i)==len(a) and np.max(cost[i,j])<margin)
        assignments=[dict(Raw=float(a[x]),candidate=float(b[y]),change=float(b[y]-a[x]),outside_original_sampling_domain=bool(b[y]<0 or b[y]>len(rp)-1)) for x,y in zip(i,j)]
        outside=sum(x['outside_original_sampling_domain'] for x in assignments)
        rows.append(dict(id=flag['id'],mode=flag['mode'],level=flag['level'],original_Raw_count=len(a),original_candidate_count=flag['candidate_crossings'],all_original_crossings_matched=all_matched,matching_ambiguity_margin_px=margin,maximum_match_distance=float(cost[i,j].max()),outside_original_domain=outside,original_count_change_explained=bool(all_matched and outside==len(a)-flag['candidate_crossings']),assignments=assignments))
    save(out/'profile_flag_resolution.json',dict(completed=True,flags=rows,all_flags_explained=all(x['original_count_change_explained'] for x in rows),original_cropped_results_preserved=True,reason='Compare the originally observed reference edges with an expanded candidate domain; expanded-domain total counts can acquire a new endpoint artifact',source=record(__file__)))
    print(json.dumps(dict(flags=len(rows),explained=sum(x['original_count_change_explained'] for x in rows))),flush=True)

if __name__=='__main__':main()

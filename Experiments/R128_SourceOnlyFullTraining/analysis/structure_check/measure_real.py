"""Read all declared real features and first/last motion pairs, retaining failures."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from readouts import *
from evaluation.real import read_image,bidirectional
import pandas as pd

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');inf=load(out/'inference.json');assert inf['completed']
    save(out/'readout_tests.json',self_test())
    sources={x['key']:x for x in plan['sources']};outputs={x['key']:x['output'] for x in inf['outputs']}
    cache={}
    def images(key):
        if key not in cache:
            raw=read_image(sources[key]['source']);p=outputs[key];assert sha(p['path'])==p['sha256']
            with np.load(p['path']) as d:pred=d['output'].astype(float)
            cache[key]=(raw.astype(float),pred)
        return cache[key]
    profiles=[];corners=[];arrays={}
    for feature in plan['features']:
        raw,pred=images(feature['source_key']);name=feature['id']
        if 'profile' in feature['kind']:
            x0,y0,x1,y1=feature['box'];axis=0 if feature['profile_axis']=='x' else 1
            a=np.median(raw[y0:y1,x0:x1],axis=axis);b=np.median(pred[y0:y1,x0:x1],axis=axis)
            arrays[name+'_Raw']=a;arrays[name+'_candidate']=b
            for mode in ['Raw_anchored','self_normalized']:
                for level in [.3,.5,.7]:profiles.append(dict(id=name,source_key=feature['source_key'],kind=feature['kind'],box=feature['box'],**compare_profile(a,b,level,mode)))
        else:
            points=np.asarray(feature['points']);rp,rq=corner_positions(raw,points);pp,pq=corner_positions(pred,points)
            for i,(p0,p1,q0,q1) in enumerate(zip(rp,pp,rq,pq)):
                dx,dy=(p1-p0).astype(float);clearance=float(min(p0[0],p0[1],raw.shape[1]-1-p0[0],raw.shape[0]-1-p0[1])-5)
                corners.append(dict(id=name,feature_index=i,source_key=feature['source_key'],kind=feature['kind'],Raw_x=float(p0[0]),Raw_y=float(p0[1]),candidate_x=float(p1[0]),candidate_y=float(p1[1]),dx=dx,dy=dy,change_px=float(np.hypot(dx,dy)),Raw_quality=float(q0),candidate_quality=float(q1),valid=bool(q0>1e-6 and q1>1e-6),fully_neural_window=clearance>=80,physical_corner_truth=False))
    assert len(corners)==44 and len(profiles)==72
    save(out/'real_profiles.json',profiles);pd.DataFrame(corners).to_csv(out/'real_corners.csv',index=False);np.savez_compressed(out/'profiles.npz',**arrays)
    motion=[]
    original=load(ROOT/'runs/P_s1285002/evaluations/real_step8192/motion_measurements.json')
    for pair in plan['motion_pairs']:
        if pair['part']=='first':
            r=next(x for x in original if x['sequence']==pair['sequence'])
            motion.append(dict(sequence=pair['sequence'],part='first',Raw=r['Raw'],candidate=r['candidate'],change_vs_Raw_px=r['change_vs_Raw_px'],consistent_with_Raw=r['consistent_with_Raw'],reused_verified_original=True));continue
        first,last=[images(k) for k in pair['keys']]
        a=bidirectional(first[0][80:-80,80:-80],last[0][80:-80,80:-80])
        b=bidirectional(first[1][80:-80,80:-80],last[1][80:-80,80:-80])
        change=float(np.hypot(a['forward']['dx']-b['forward']['dx'],a['forward']['dy']-b['forward']['dy'])) if a['valid'] and b['valid'] else None
        motion.append(dict(sequence=pair['sequence'],part='last',Raw=a,candidate=b,change_vs_Raw_px=change,consistent_with_Raw=bool(change is not None and change<=.5),reused_verified_original=False))
        print(json.dumps(dict(last_pair=pair['sequence'],Raw_valid=a['valid'],candidate_valid=b['valid'],change_vs_Raw_px=change)),flush=True)
    save(out/'motion.json',motion)
    primary=[x for x in profiles if x['mode']=='Raw_anchored' and x['level']==.5]
    summary=dict(completed=True,profile_strips=len(primary),half_level_count_mismatches=sum(not x['equal_counts_and_directions'] for x in primary),maximum_matched_half_level_edge_change_px=max((x['edge_change_px']['maximum_absolute'] for x in primary if x['edge_change_px']['count']),default=None),corners=len(corners),invalid_corners=sum(not x['valid'] for x in corners),maximum_corner_readout_change_px=max(x['change_px'] for x in corners),all_corner_windows_fully_neural=all(x['fully_neural_window'] for x in corners),motion_pairs=len(motion),Raw_motion_invalid=sum(not x['Raw']['valid'] for x in motion),candidate_motion_invalid=sum(not x['candidate']['valid'] for x in motion),motion_pairs_consistent=sum(x['consistent_with_Raw'] for x in motion),maximum_reportable_motion_change_vs_Raw_px=max((x['change_vs_Raw_px'] for x in motion if x['change_vs_Raw_px'] is not None),default=None),real_geometry_is_Raw_relative_not_independent_truth=True,source=record(__file__),readout_source=record(Path(__file__).with_name('readouts.py')))
    save(out/'real_summary.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':main()

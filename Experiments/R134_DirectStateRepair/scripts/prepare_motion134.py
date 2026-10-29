from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    repo=ROOT.parent.parent;old=ROOT.parent/'R129_OpticalPriorHybrid/results/continuous_lsc/plan.json';plan=load(old);pairs=pd.read_csv(str(PROJECT_ROOT / plan['locked_pairs']['path']));selected=[]
    for sequence,g in pairs.groupby('sequence'):
        g=g.sort_values(['start_frame_index','end_frame_index'])
        for i in [0,len(g)//2,len(g)-1]:selected.append(dict(sequence=sequence,start=int(g.iloc[i].start_frame_index),end=int(g.iloc[i].end_frame_index),start_frame_index=int(g.iloc[i].start_frame_index),end_frame_index=int(g.iloc[i].end_frame_index),pair_rank_raw_locked=int(g.iloc[i].pair_rank_raw_locked)))
    frames=[]
    ids={(p['sequence'],j) for p in selected for j in [p['start'],p['end']]}
    for f in plan['frames']:
        if (f['sequence'],f['frame_index']) in ids:frames.append(f)
    save(ROOT/'config/motion_panel.json',dict(utc=now(),source_plan=record(old),configuration=plan['configuration'],sessions=plan['sessions'],pairs=selected,frames=frames,selection='First/middle/last ineachsource-locked30pairlist, before finalCoutcomes; no candidate-based selection',scope='12pairs, three persequence; smallscreen, not fulltemporalqualification',requires_stage1_pass=True,source=record(__file__)))
    print('Fixed motionpanel',len(frames),'frames',len(selected),'pairs',flush=True)
if __name__=='__main__':main()

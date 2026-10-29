"""Audit source-defined LSC windows against the existing full-FOV Raw guard."""
import sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from measure import reader
PROJECT_ROOT = Path(__file__).resolve().parents[4]

def main():
    out=ROOT/'results/lsc_comparison';p=load(out/'plan.json');cfg=load(str(PROJECT_ROOT / p['configuration']['path']));core,scope=reader(p)
    # Same required-halo formula as the frozen model, evaluated from its frozen configuration.
    c=load(ROOT/'config/study.json')['model'];perstep=math.ceil((2*(2+2*sum(c['dilations']))+3)/4)+1;halo=math.ceil((c['iterations']*perstep+2)/16)*16
    rows=[]
    for f in p['frames']:
        s=cfg['sequences'][f['sequence']];pitch=float(s['pitch_px']);half=int(np.ceil(.46*pitch));margin=int(np.ceil(.55*pitch));h,w=f['shape']
        pred=scope['session_prediction'](f['sequence'],f['frame_index'],np.asarray(s['centers'],float),float(s['expected_signed_dx_px']))
        rx0=max(0,int(np.floor(pred[:,1].min()))-margin);rx1=min(w,int(np.ceil(pred[:,1].max()))+margin+1)
        ry0=max(0,int(np.floor(pred[:,2].min()))-margin);ry1=min(h,int(np.ceil(pred[:,2].max()))+margin+1)
        for pid,x,y in pred:
            x0=max(rx0,int(np.floor(x))-half);x1=min(rx1,int(np.floor(x))+half+1);y0=max(ry0,int(np.floor(y))-half);y1=min(ry1,int(np.floor(y))+half+1)
            yy,xx=np.mgrid[y0:y1,x0:x1];distance=np.minimum.reduce([yy,h-1-yy,xx,w-1-xx]);weight=np.clip((distance-halo)/16,0,1)
            rows.append(dict(sequence=f['sequence'],frame_index=f['frame_index'],pillar_id=int(pid),patch_fully_neural=bool(np.all(weight==1)),patch_fully_Raw=bool(np.all(weight==0)),patch_Raw_fraction=float(np.mean(weight==0)),patch_neural_fraction=float(np.mean(weight==1)),patch_mean_weight=float(weight.mean()),x0=x0,y0=y0,x1=x1,y1=y1))
    t=pd.DataFrame(rows);t.to_csv(out/'source_boundary_context.csv',index=False)
    pairs=pd.read_csv(out/'locked_pairs.csv');flags=[];idx=t.set_index(['sequence','frame_index','pillar_id'])
    for pair in pairs.itertuples(index=False):
        count=0
        for pid,_,_ in cfg['sequences'][pair.sequence]['centers']:
            count+=int(idx.loc[(pair.sequence,pair.start_frame_index,pid),'patch_fully_neural'] and idx.loc[(pair.sequence,pair.end_frame_index,pid),'patch_fully_neural'])
        flags.append(dict(sequence=pair.sequence,start_frame_index=pair.start_frame_index,end_frame_index=pair.end_frame_index,fully_neural_pillars_both_frames=count,all9_fully_neural=count==9))
    flags=pd.DataFrame(flags);flags.to_csv(out/'source_boundary_pair_context.csv',index=False)
    summary=t.groupby('sequence').agg(pillar_frames=('pillar_id','size'),fully_neural=('patch_fully_neural','sum'),fully_Raw=('patch_fully_Raw','sum')).reset_index()
    save(out/'boundary_diagnostic_plan.json',dict(created_utc=now(),reason='Source-defined20xLSC windows approach the FOV edge. Separate the operational result from contributions of the existing Raw-retention guard.',
        primary_unchanged=True,halo=halo,transition=16,selection_uses_only_Raw_geometry=True,
        population='Same159frames/120pairs/9pillars, no exclusions. Report fully-neural subset only as source-defined diagnostic with all methods matched.',
        diagnostic='Measure saved unrestricted neural outputs from the identical frozen forward pass, uint8 same rounding, same LSC reader; do not adopt this output or claim missing physical context is validated.',
        paired_intervention='Samecheckpoint/forwardoutputs/frames/reader; remove only finalFOVRawguard. This diagnoses that postprocessing contribution, not training causality.',
        source_context=record(out/'source_boundary_context.csv'),pair_context=record(out/'source_boundary_pair_context.csv'),source=record(__file__),primary_plan=record(out/'plan.json'),summary=summary.to_dict('records')))
    print(summary.to_string(index=False));print(flags.groupby('sequence').all9_fully_neural.sum().to_string())

if __name__=='__main__':main()

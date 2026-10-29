"""Diagnostic only: same saved neural output without final FOV Raw retention."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from measure import reader,measure_frame,pair_table
PROJECT_ROOT = Path(__file__).resolve().parents[4]

def main():
    out=ROOT/'results/lsc_comparison';p=load(out/'plan.json');diag=load(out/'boundary_diagnostic_plan.json');cfg=load(str(PROJECT_ROOT / p['configuration']['path']))
    core,scope=reader(p);method='R128_no_FOV_guard_diagnostic';folder=out/'measurements'/method;folder.mkdir(parents=True,exist_ok=False)
    save(folder/'started.json',dict(started_utc=now(),diagnostic_plan=record(out/'boundary_diagnostic_plan.json'),source=record(__file__)))
    tables=[];records=[];start=time.perf_counter()
    for n,f in enumerate(p['frames'],1):
        rec=out/'R128_images'/f['sequence']/f"frame_{f['frame_index']:04d}"/'record.json'
        while not rec.is_file():time.sleep(1)
        data=load(rec);src=data['output_float'];assert sha(src['path'])==src['sha256']
        with np.load(src['path']) as payload:neural=payload['neural_output']
        image=np.rint(neural*255).clip(0,255).astype(np.uint8).astype(float)/255
        raw=scope['load_grayscale'](Path(PROJECT_ROOT / f['source']['path']))
        measured,points=measure_frame(core,scope,f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw,image,method)
        dest=folder/f['sequence']/f"frame_{f['frame_index']:04d}";dest.mkdir(parents=True,exist_ok=False)
        measured.to_csv(dest/'centers.csv',index=False);np.savez_compressed(dest/'boundaries.npz',**points)
        records.append(dict(sequence=f['sequence'],frame_index=f['frame_index'],neural_source=src,centers=record(dest/'centers.csv'),boundaries=record(dest/'boundaries.npz')));tables.append(measured)
        if n%20==0:print(json.dumps(dict(diagnostic=method,frames=n,total=len(p['frames']),seconds=round(time.perf_counter()-start,1))),flush=True)
    centers=pd.concat(tables,ignore_index=True);pairs,pp=pair_table(centers,pd.read_csv(out/'locked_pairs.csv'),cfg,method)
    centers.to_csv(folder/'centers.csv',index=False);pairs.to_csv(folder/'per_pair.csv',index=False);pp.to_csv(folder/'per_pillar_pair.csv',index=False)
    summary=scope['summarize_pairs'](pairs);summary.to_csv(folder/'summary.csv',index=False)
    save(folder/'complete.json',dict(completed_utc=now(),frames=len(p['frames']),center_rows=len(centers),pair_rows=len(pairs),records=records,source=record(__file__),reader_source=record(Path(__file__).with_name('measure.py')),summary=record(folder/'summary.csv'),centers=record(folder/'centers.csv'),pairs=record(folder/'per_pair.csv'),diagnostic_only=True))
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':main()

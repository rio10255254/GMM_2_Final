"""Conditional real displacement follow-up on all supported arms and controls."""
from pathlib import Path
import json,subprocess,sys
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def execute(command,log):
    with log.open('x') as stream:result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError('Real LSC step failed: '+str(log))

def main():
    decision=json.loads((ROOT/'results/assessment/decision.json').read_text());arms=decision['supported_arms_for_real_LSC']
    if not arms:
        print('No supported intervention; real-LSC follow-up not triggered');return
    matrix=json.loads((ROOT/'results/matrix_finished_v2.json').read_text())['runs'];rows=[]
    for entry in matrix:
        if entry['arm'] not in ['A',*arms]:continue
        name=entry['run_id'];checkpoint=ROOT/'runs'/name/'weights/epoch_012.pth'
        base=ROOT/'results/lsc'/name;base.mkdir(parents=True,exist_ok=False)
        execute([sys.executable,'-B','validation/prepare_lsc_recon.py','--checkpoint',str(checkpoint),'--output',str(base/'recon'),'--method',name],base/'recon.log')
        execute([sys.executable,'-B','validation/run_lsc.py','--method',name,'--recon-root',str(base/'recon'),'--output',str(base/'readout')],base/'readout.log')
        pairs=pd.read_csv(base/'readout/tables/candidate_lsc_per_pair.csv');assert len(pairs)==120
        for sequence,g in pairs.groupby('sequence'):
            assert len(g)==30
            rows.append({'method':name,'arm':entry['arm'],'seed':entry['seed'],'sequence':sequence,'step_sd_nm':float(g.measured_step_um.std(ddof=1)*1000),'cross_axis_median_nm':float(g.cross_axis_abs_nm.median())})
        print(json.dumps({'real_LSC_complete':name}),flush=True)
    f=pd.DataFrame(rows);f.to_csv(ROOT/'results/lsc/per_sequence_summary.csv',index=False,mode='x')
    guards=[]
    for seed in [1215001,1215002]:
        a=f[(f.seed==seed)&(f.arm=='A')].set_index('sequence')
        for arm in arms:
            v=f[(f.seed==seed)&(f.arm==arm)].set_index('sequence')
            assert set(v.index)==set(a.index) and len(v)==4
            ds=v.step_sd_nm-a.step_sd_nm;cross=v.cross_axis_median_nm-a.cross_axis_median_nm
            guards.append({'seed':seed,'arm':arm,'real_point_guard_pass':bool((ds<=1e-6).all() and (cross<=1e-6).all()),'step_sd_change_nm':ds.to_dict(),'cross_axis_change_nm':cross.to_dict()})
    with (ROOT/'results/lsc/decision.json').open('x') as stream:json.dump({'scope':'Frozen Raw-selected pairs; point estimates without a new uncertainty claim','guards':guards,'no_promotion':True},stream,indent=2)
    print(json.dumps(guards,indent=2))

if __name__=='__main__':main()

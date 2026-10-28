"""Re-run the historical submission backend from immutable snapshots, not R152."""
from pathlib import Path
import sys, json, time
import numpy as np
import pandas as pd

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as original

def main():
    original.CONFIG_PATH=ROOT/'sources/sequence_config.json'
    original.AUDIT_TABLE=ROOT/'sources/raw_eligibility.csv'
    original.SESSION_TABLE=ROOT/'sources/session_anchors.csv'
    original.SWEEP_ROOT=Path('D:/GMM_2_Final/PSF_Fitting/tests/artifacts/cd_verification_20260714')
    original.RESULTS=ROOT/'results/submission_replay'
    original.TABLES=original.RESULTS
    original.FIGURES=original.RESULTS
    original.RESULTS.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(original.CONFIG_PATH.read_text(encoding='utf-8-sig'))
    begin=time.perf_counter(); cs=[];ps=[]
    for seq in ['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um']:
        print('Replaying original Raw / Wiener / historical MOSR:',seq,flush=True)
        centers,pairs=original.process_sequence(seq,cfg,30)
        cs.append(centers);ps.append(pairs)
        centers.to_csv(original.RESULTS/(seq+'_centers.csv'),index=False)
        pairs.to_csv(original.RESULTS/(seq+'_pairs.csv'),index=False)
        print('Completed',seq,'centers',len(centers),'seconds',round(time.perf_counter()-begin,1),flush=True)
    newc=pd.concat(cs);newp=pd.concat(ps)
    oldc=pd.read_csv(ROOT/'sources/historical_centers.csv');oldp=pd.read_csv(ROOT/'sources/historical_per_pair.csv')
    checks={}
    for name,a,b,keys,cols in [
        ('centers',newc,oldc,['sequence','method','frame_index','pillar_id'],['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']),
        ('pairs',newp,oldp,['sequence','method','pair_rank_raw_locked'],['measured_step_um','nominal_abs_error_nm','within_grid_sd_nm'])]:
        a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index()
        assert a.index.equals(b.index)
        delta=abs(a[cols]-b[cols]); checks[name]={'rows':len(a),'max_abs_difference':delta.max().to_dict(),'passed':bool(delta.to_numpy().max()<1e-7)}
    summary=original.summarize_pairs(newp)
    summary.to_csv(original.RESULTS/'replayed_summary.csv',index=False)
    result=dict(scope='Historical submission replay only. Historical MOSR is V42, not R152.',checks=checks,passed=all(x['passed'] for x in checks.values()),seconds=time.perf_counter()-begin)
    (ROOT/'results/submission_replay_check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    if not result['passed']: raise SystemExit(2)

if __name__=='__main__':main()

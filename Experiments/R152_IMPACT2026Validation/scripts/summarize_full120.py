"""Original three statistics and original conditional paired resampling, all 120 pairs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/full120';OUT.mkdir(parents=True,exist_ok=True)
SEQS=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um']
METHODS=['Raw','Wiener','R152']
FIELDS=['step_sd_nm','nominal_mae_nm','median_within_grid_sd_nm']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def main():
    receipts=[load(ROOT/f'results/{d}/complete.json') for d in ['20x','50x_calibrated']]
    assert all(r['weights_and_buffers_unchanged'] for r in receipts)
    assert len({r['checkpoint_sha256'] for r in receipts})==1
    assert receipts[1]['optical_installation']['learned_parameters_unchanged']
    pairs=pd.concat([pd.read_csv(ROOT/f'results/{d}/per_pair.csv') for d in ['50x_calibrated','20x']],ignore_index=True)
    centers=pd.concat([pd.read_csv(ROOT/f'results/{d}/centers.csv') for d in ['50x_calibrated','20x']],ignore_index=True)
    assert len(pairs)==360 and len(centers)==4482
    locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    cond=[];data={}
    for seq in SEQS:
        expected=locked[locked.sequence==seq][['start_frame_index','end_frame_index']].to_numpy()
        for method in METHODS:
            p=pairs[(pairs.sequence==seq)&(pairs.method==method)].sort_values('pair_rank_raw_locked')
            assert len(p)==30 and np.array_equal(p[['start_frame_index','end_frame_index']].to_numpy(),expected)
            values=[p.measured_step_um.std(ddof=1)*1000,p.nominal_abs_error_nm.mean(),p.within_grid_sd_nm.median()]
            cond.append(dict(sequence=seq,magnification=p.magnification.iloc[0],method=method,n_pairs=30,**dict(zip(FIELDS,values))))
            data[(seq,method)]=p
    cond=pd.DataFrame(cond);agg=[]
    for scope,seqs in [('all120',SEQS),('20x',SEQS[2:]),('50x',SEQS[:2])]:
        for method in METHODS:
            c=cond[(cond.sequence.isin(seqs))&(cond.method==method)]
            p=pairs[(pairs.sequence.isin(seqs))&(pairs.method==method)]
            vals=[c.step_sd_nm.mean(),c.nominal_mae_nm.mean(),p.within_grid_sd_nm.median()]
            agg.append(dict(scope=scope,method=method,n_pairs=len(p),**dict(zip(FIELDS,vals))))
    agg=pd.DataFrame(agg)
    old=pd.read_csv(ROOT/'sources/historical_per_pair.csv')
    keys=['sequence','method','pair_rank_raw_locked'];cols=['measured_step_um','nominal_abs_error_nm','within_grid_sd_nm']
    a=pairs[pairs.method.isin(['Raw','Wiener'])].set_index(keys).sort_index()
    b=old[old.method.isin(['Raw','Wiener'])].set_index(keys).sort_index()
    assert a.index.equals(b.index);delta=abs(a[cols]-b[cols]).max();assert delta.max()<1e-7
    # This exactly follows the paper's resampling unit and RNG order, including shared indices across methods.
    rng=np.random.default_rng(20260824);boot=[];win=[];reductions=[]
    observed=agg[agg.scope=='all120'].set_index('method')
    def metrics(method,indices):
        arrays={field:np.stack([data[(seq,method)][field].to_numpy() for seq in SEQS]) for field in cols}
        step=np.take_along_axis(arrays['measured_step_um'][None,:,:],indices,axis=2)*1000
        mae=np.take_along_axis(arrays['nominal_abs_error_nm'][None,:,:],indices,axis=2)
        grid=np.take_along_axis(arrays['within_grid_sd_nm'][None,:,:],indices,axis=2)
        return np.stack([step.std(axis=2,ddof=1).mean(axis=1),mae.mean(axis=(1,2)),np.median(grid.reshape(len(indices),120),axis=1)],axis=1)
    for baseline in ['Raw','Wiener']:
        ix=rng.integers(0,30,size=(20000,4,30));diff=metrics(baseline,ix)-metrics('R152',ix)
        intervals=np.percentile(diff,[2.5,97.5],axis=0)
        for i,field in enumerate(FIELDS):
            original=float(observed.loc[baseline,field]);value=float(observed.loc['R152',field])
            boot.append(dict(baseline=baseline,metric=field,baseline_minus_r152_nm=original-value,ci95_low_nm=intervals[0,i],ci95_high_nm=intervals[1,i],resampling='within-condition matched pair bootstrap; conditional on locked pairs'))
            reductions.append(dict(scope='all120',baseline=baseline,metric=field,reduction_pct=(original-value)/original*100))
        for scope,seqs in [('all120',SEQS),('20x',SEQS[2:]),('50x',SEQS[:2])]:
            bv=np.concatenate([data[(s,baseline)].within_grid_sd_nm.to_numpy() for s in seqs]);rv=np.concatenate([data[(s,'R152')].within_grid_sd_nm.to_numpy() for s in seqs])
            win.append(dict(scope=scope,baseline=baseline,r152_lower=int((rv<bv).sum()),ties=int((rv==bv).sum()),total=len(rv)))
    for name,frame in [('per_pair',pairs),('centers',centers),('condition_summary',cond),('aggregate_summary',agg),('paired_intervals',pd.DataFrame(boot)),('within_grid_wins',pd.DataFrame(win)),('relative_changes',pd.DataFrame(reductions))]:frame.to_csv(OUT/f'{name}.csv',index=False)
    shared=pd.read_csv(ROOT/'results/shared_bank120/aggregate_summary.csv')
    comparison=agg.merge(shared,on=['scope','method','n_pairs'],suffixes=('_calibrated','_shared'))
    for field in FIELDS:comparison[field+'_calibrated_minus_shared']=comparison[field+'_calibrated']-comparison[field+'_shared']
    comparison.to_csv(OUT/'calibrated_vs_shared_optics.csv',index=False)
    save(OUT/'complete.json',dict(state='complete_objective_calibrated_full120',images=166,locked_pairs=120,methods=METHODS,center_rows=4482,pair_rows=360,checkpoint_sha256=receipts[0]['checkpoint_sha256'],effective_bank_sha256={'20x':receipts[0]['bank_sha256'],'50x':receipts[1]['bank_sha256']},r152_optics='native 20x 25-kernel bank; original 50x single kernel installed in both optical paths',wiener_optics='original magnification-specific calibration',measurement_protocol_unchanged=True,magnification_specific_optics=True,exact_submitted_model_implementation=False,single_psf_input_adapter_user_authorized=True,original_baseline_max_difference=delta.to_dict(),bootstrap_replicates=20000,bootstrap_seed=20260824,bootstrap_limit='Some adjacent pairs share frames; intervals are conditional on the original selected pairs and not independent repeated-scan or universal-generalization evidence.'))
    print(agg.to_string(index=False));print(pd.DataFrame(boot).to_string(index=False))
if __name__=='__main__':main()

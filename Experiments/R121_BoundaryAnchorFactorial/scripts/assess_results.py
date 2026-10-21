"""Apply predeclared paired gates; never update models or protected evidence."""
from pathlib import Path
import hashlib,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
BENCH=ROOT.parent/'R119_SequenceGeometryValidation/analysis/controlled_boundary_factors_20260906'

def save(path,value):
    def finite(v):
        if isinstance(v,dict):return {k:finite(x) for k,x in v.items()}
        if isinstance(v,list):return [finite(x) for x in v]
        if isinstance(v,float) and not np.isfinite(v):return None
        return v
    with path.open('x') as f:json.dump(finite(value),f,indent=2,allow_nan=False)

def summarize_controlled(matrix):
    out=ROOT/'results/controlled'
    groups=[('primary',json.loads((BENCH/'protocol.json').read_text())['cases']),('radiometry',json.loads((BENCH/'radiometry_protocol.json').read_text())['cases'])]
    rows=[]
    for bank,specs in groups:
        for spec in specs:
            cases={}
            for entry in matrix:
                name=entry['run_id']
                with np.load(out/name/f"{bank}_{spec['case_id']:03d}.npz") as f:cases[name]={k:f[k] for k in f.files}
            common=next(iter(cases.values()))['Raw_valid'].copy()
            for f in cases.values():common &= f['valid']
            theta=np.arange(720)*2*np.pi/720
            design=np.stack([np.ones(720),np.cos(theta),np.sin(theta)],1)
            raw=next(iter(cases.values()))
            old_folder='cases' if bank=='primary' else 'radiometry_cases'
            with np.load(BENCH/old_folder/f"{spec['case_id']:03d}"/'profiles.npz') as old:raw_width=old['Raw_width']
            for name,data in [('Raw',{'error':raw['Raw_error'],'valid':raw['Raw_valid'],'width':raw_width}),*cases.items()]:
                error=data['error'];cx=cy=None
                width_valid=common&np.isfinite(data['width'])&np.isfinite(raw['target_width'])
                width_error=float(np.median(np.abs(data['width'][width_valid]-raw['target_width'][width_valid]))) if width_valid.any() else None
                width_value=float(np.median(data['width'][width_valid])) if width_valid.any() else None
                if common.sum():
                    bias=float(np.median(error[common]));mae=float(np.mean(np.abs(error[common])))
                    if spec['shape']!='line' and common.sum()>=20:
                        fitted=np.linalg.lstsq(design[common],error[common],rcond=None)[0];cx,cy=float(fitted[1]),float(fitted[2])
                else:bias=mae=None
                rows.append({'method':name,'bank':bank,**spec,'own_valid_profiles':int(data['valid'].sum()),'common_valid_profiles':int(common.sum()),'signed_bias_px':bias,'boundary_mae_px':mae,'center_error_x_px':cx,'center_error_y_px':cy,'median_transition_width_px':width_value,'median_width_error_px':width_error,'width_valid_profiles':int(width_valid.sum())})
    frame=pd.DataFrame(rows);frame.to_csv(out/'paired_summary.csv',index=False,mode='x')
    motion=[]
    for keys,g in frame[(frame.bank=='primary')&(frame.group=='motion')&(frame['shape']!='line')].groupby(['method','shape','polarity','sensor']):
        baseline=g[(g.dx==0)&(g.dy==0)].iloc[0]
        values=np.hypot(g.center_error_x_px-baseline.center_error_x_px,g.center_error_y_px-baseline.center_error_y_px)
        motion.append(dict(zip(['method','shape','polarity','sensor'],keys),max_motion_error_px=float(values.max()) if np.isfinite(values).all() else None))
    motion=pd.DataFrame(motion);motion.to_csv(out/'motion_summary.csv',index=False,mode='x')
    return frame,motion

def main():
    matrix=json.loads((ROOT/'results/matrix_finished_v2.json').read_text())['runs']
    sem=pd.read_csv(ROOT/'results/sem/measurements.csv');dev=pd.read_csv(ROOT/'results/development/per_view.csv')
    assert len(sem)==7776 and not sem.duplicated(['method','reference','exposure','pillar']).any()
    controlled,motion=summarize_controlled(matrix)
    identity=json.loads((ROOT/'results/development/identity.json').read_text());assert len({(r['source'],r['target']) for r in identity.values()})==1
    if (sem.valid!=1).any():
        # All original rows remain; a candidate with missing shape outputs fails.
        sem_failures=sem[sem.valid!=1].to_dict(orient='records')
    else:sem_failures=[]
    effects=[];gates=[]
    for seed in [1215001,1215002]:
        names={e['arm']:e['run_id'] for e in matrix if e['seed']==seed};a=names['A']
        for arm,name in names.items():
            shape_pass=not ((sem.method.isin([name,a]))&(sem.valid!=1)).any();reference_effects={}
            for reference in ['historical','pitch_matched']:
                q=sem[sem.reference==reference].pivot(index=['exposure','pillar'],columns='method',values='boundary')
                delta=q[name]-q[a];raw_delta=q[name]-q.Raw
                pillar=delta.groupby(level='pillar').median();exposure=delta.groupby(level='exposure').median()
                rng=np.random.default_rng(1219001);ci=np.percentile(np.median(rng.choice(pillar.to_numpy(),(3000,36),replace=True),axis=1),[2.5,97.5])
                summary={'reference':reference,'seed':seed,'arm':arm,'method':name,'median_pillar_paired_effect_vs_A':float(pillar.median()),'bootstrap95_vs_A':ci.tolist(),
                         'worst_exposure_median_effect_vs_A':float(exposure.max()),'improved_pillars_vs_A':int((pillar<0).sum()),
                         'median_pillar_effect_vs_Raw':float(raw_delta.groupby(level='pillar').median().median()),
                         'improved_observations_vs_Raw':int((raw_delta<0).sum())}
                effects.append(summary);reference_effects[reference]=summary
                shape_pass &= bool(pillar.notna().all() and (pillar.median()<0 or arm=='A') and exposure.max()<=.01)
            own_control=controlled[controlled.method==name];a_control=controlled[controlled.method==a]
            own_motion=motion[motion.method==name].max_motion_error_px;am=motion[motion.method==a].max_motion_error_px
            own_invalid=int((720-own_control.own_valid_profiles).sum());a_invalid=int((720-a_control.own_valid_profiles).sum())
            motion_pass=bool(own_motion.notna().all() and own_motion.max()<=am.max()+.01 and own_invalid<=a_invalid and own_control.common_valid_profiles.min()>=684)
            t=dev[(dev.method==name)&(dev.role=='textured_edge')];at=dev[(dev.method==a)&(dev.role=='textured_edge')]
            ratio=float(t.highpass_mae_gray.mean()/at.highpass_mae_gray.mean())
            texture_pass=bool(np.isfinite(ratio) and ratio<=1.02)
            gates.append({'seed':seed,'arm':arm,'method':name,'shape_pass':bool(shape_pass),'controlled_motion_pass':motion_pass,'texture_pass':texture_pass,
                          'maximum_motion_error_px':float(own_motion.max()),'control_motion_error_px':float(am.max()),'invalid_profiles':own_invalid,'control_invalid_profiles':a_invalid,
                          'textured_highpass_error_ratio_vs_A':ratio,'paired_screen_pass':bool(shape_pass and motion_pass and texture_pass),'real_LSC':'not yet run; required for supported intervention before further-training readiness'})
    supported=[arm for arm in 'BCD' if all(g['paired_screen_pass'] for g in gates if g['arm']==arm)]
    out=ROOT/'results/assessment';out.mkdir(exist_ok=False)
    pd.DataFrame([{k:v for k,v in r.items() if k!='bootstrap95_vs_A'} for r in effects]).to_csv(out/'shape_effects.csv',index=False,mode='x')
    pd.DataFrame(gates).to_csv(out/'screen_gates.csv',index=False,mode='x')
    save(out/'decision.json',{'scope':'eight paired 12-epoch probes; preliminary paired screening, not promotion','supported_arms_for_real_LSC':supported,
                             'gates':gates,'shape_effects':effects,'sem_failures':sem_failures,
                             'decision':'Run matched real LSC checks for supported arms before readiness' if supported else 'No intervention passes both seeds and all predeclared guards; retain results, no epoch extension or long training',
                             'interrupted_v1_excluded':'probe_C_s1215001','historical_and_pitch_matched_references_both_used':True})
    print(json.dumps({'supported_arms':supported,'gates':gates},indent=2))

if __name__=='__main__':main()

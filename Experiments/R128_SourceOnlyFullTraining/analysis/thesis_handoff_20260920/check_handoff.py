"""Read-only source review for thesis planning; no refits, inference or training."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[4]

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/thesis_handoff_review_20260920'
PACKAGE=Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R128_Corrected_Corner9_Thesis_Handoff_20260920'))
DATA=PACKAGE/'01_Raw_R128_Comparison'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((PACKAGE/'MANIFEST.json').read_text(encoding='utf-8'))
for item in manifest:
    assert sha(PACKAGE/item['path'])==item['sha256'],item['path']
main=pd.read_csv(DATA/'main_comparison.csv').set_index(['scope','metric'])
displacement=pd.read_csv(DATA/'all_displacements_3600.csv')
contours=pd.read_csv(DATA/'all_contours_16740.csv')
sem=pd.read_csv(DATA/'SEM_group_mean_size.csv').set_index('model')
endpoint=pd.read_csv(DATA/'endpoint_30um.csv').set_index('model')
assert len(displacement)==3600 and len(contours)==16740
assert not displacement.duplicated(['model','run','kind','i','j']).any()
assert not contours.duplicated(['model','run','index','pillar_id']).any()
key=['run','kind','i','j']
a=displacement[displacement.model=='Raw'].sort_values(key).reset_index(drop=True)
b=displacement[displacement.model=='R128'].sort_values(key).reset_index(drop=True)
assert a[key].equals(b[key])
assert np.array_equal(a[['pi_dx_um','pi_dy_um']].values,b[['pi_dx_um','pi_dy_um']].values)
checks=[]
def check(name,actual,expected):
    difference=float(abs(actual-expected))
    assert np.isfinite(actual) and difference<1e-7,(name,actual,expected)
    checks.append(dict(name=name,recomputed=float(actual),reported=float(expected),difference=difference))
for model in ['Raw','R128']:
    d=displacement[displacement.model==model]
    assert d.run.nunique()==30
    for kind,g in d.groupby('kind'):
        assert len(g)==900 and (g.groupby('j').size()==30).all()
        check(f'{model}/{kind}/mae',g.error_nm.abs().mean(),main.loc[(kind,'mae_nm'),model+'_nm'])
        check(f'{model}/{kind}/repeat',g.groupby('j').error_nm.std(ddof=1).mean(),main.loc[(kind,'repeatability_nm'),model+'_nm'])
        check(f'{model}/{kind}/max',g.error_nm.abs().max(),main.loc[(kind,'maximum_error_nm'),model+'_nm'])
    end=d[(d.kind=='start')&(d.j==30)].error_nm
    check(f'{model}/endpoint/bias',end.mean(),endpoint.loc[model,'bias_nm'])
    check(f'{model}/endpoint/repeat',end.std(ddof=1),endpoint.loc[model,'repeatability_sd_nm'])
    c=contours[contours.model==model].sort_values(['run_index','index','pillar_id'])
    assert len(c)==8370 and (c.groupby(['index','pillar_id']).size()==30).all()
    check(f'{model}/diameter_from_radius_max_delta',np.max(np.abs(c.diameter_nm-2*c.radius_px*172.5)),0)
    diam=c.diameter_nm.values.reshape(30,31,9)
    check(f'{model}/diameter_repeat',np.sqrt(diam.var(axis=0,ddof=1).mean()),main.loc[('contour','diameter_repeat_sd_nm'),model+'_nm'])
    check(f'{model}/diameter_absmax',np.max(np.abs(diam-diam.mean(axis=0))),main.loc[('contour','diameter_repeat_absmax_nm'),model+'_nm'])
    check(f'{model}/diameter_mean',diam.mean(),sem.loc[model,'mean_diameter_nm'])
    check(f'{model}/SEM_group_difference',diam.mean()-sem.loc[model,'SEM_group_mean_diameter_nm'],sem.loc[model,'group_signed_diameter_difference_nm'])
    p=PACKAGE/'04_Source_and_Verification/radial_profiles'/f'{model}.npz'
    with np.load(p,allow_pickle=False) as z:
        # Stored profiles are float32; aggregate in float64, matching the report
        # and avoiding float32 reduction error. Source arrays are not modified.
        r=z['radius_nm'].astype(np.float64);assert r.shape==(30,31,9,720) and np.isfinite(r).all()
        assert list(z['runs'])==list(c.drop_duplicates('run_index').run)
    check(f'{model}/contour_repeat',np.sqrt(r.var(axis=0,ddof=1).mean()),main.loc[('contour','contour_repeat_sd_nm'),model+'_nm'])
    shape=r-r.mean(axis=-1,keepdims=True)
    check(f'{model}/shape_repeat',np.sqrt(shape.var(axis=0,ddof=1).mean()),main.loc[('contour','shape_repeat_sd_nm'),model+'_nm'])
for idx,row in main.iterrows():
    check('/'.join(idx)+'/reduction_percent',100*(1-row.R128_nm/row.Raw_nm),row.reduction_percent)
scan=displacement.groupby(['model','kind','run']).error_nm.apply(lambda x:x.abs().mean()).unstack('model')
wins={kind:int((g.R128<g.Raw).sum()) for kind,g in scan.groupby(level='kind')}
assert wins=={'adjacent':30,'start':21},wins
OUT.mkdir(parents=True,exist_ok=True)
result=dict(status='checked_for_thesis_planning',manifest_files_verified=len(manifest),
            scalar_checks=len(checks),max_absolute_scalar_difference=max(x['difference'] for x in checks),
            compared_displacements=3600,compared_contours=16740,improved_scans=wins,
            source_files_unchanged=True,no_training_or_inference=True,
            limits=['Recomputed aggregates from saved displacements, circles and radial profiles, not a new independent extraction or circle refit.',
                    'SEM reference value and inferred orientation not independently certified.',
                    'No resampling-interval rerun in this planning review.',
                    'No new causal conclusion about architecture or training objective.'],
            inputs={str(p.relative_to(PACKAGE)):sha(p) for p in [DATA/'all_displacements_3600.csv',DATA/'all_contours_16740.csv',DATA/'main_comparison.csv',DATA/'SEM_group_mean_size.csv']},checks=checks)
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
pd.DataFrame(checks).to_csv(OUT/'recomputed_claims.csv',index=False,encoding='utf-8-sig')
print(json.dumps({k:v for k,v in result.items() if k not in ['inputs','checks']},ensure_ascii=False,indent=2))

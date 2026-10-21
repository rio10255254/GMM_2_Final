"""Preserve protected inputs; verify arrays, repeated controls and independent interpolation."""
import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from scipy.interpolate import RegularGridInterpolator
import run as core
OUT=core.OUT

def alternative_positions(image,coords,inside,outside):
    y,x=image.shape
    interpolation=RegularGridInterpolator((np.arange(y),np.arange(x)),image.astype(np.float64),bounds_error=True)
    sampled=interpolation(np.moveaxis(coords,0,-1).reshape(-1,2)).reshape(720,-1)
    profile=(sampled-inside)/(outside-inside)
    result=[]
    for row in profile:
        crossings=np.flatnonzero((row[:-1]<.5)&(row[1:]>=.5))
        if len(crossings)!=1:result.append(np.nan);continue
        i=crossings[0];result.append(float(core.T[i]+(.5-row[i])*(core.T[i+1]-core.T[i])/(row[i+1]-row[i])))
    return np.asarray(result)

def main():
    snapshot=json.loads((OUT/'input_snapshot.json').read_text())
    assert all(core.sha(p)==h for p,h in snapshot.items())
    f=pd.read_csv(OUT/'measurements.csv');r=pd.read_csv(OUT/'radiometry_measurements.csv');real=pd.read_csv(OUT/'real_halfcontrast_measurements_v2.csv')
    assert len(f)==240*7 and len(r)==100*7 and len(real)==432*8
    image_count=0
    for directory in ['cases','radiometry_cases']:
        for folder in sorted((OUT/directory).iterdir()):
            with np.load(folder/'images.npz') as images:
                assert set(images.files)==set(core.METHODS+['reference'])
                for key in images.files:
                    image=images[key]
                    assert image.shape==(640,640) and np.isfinite(image).all()
                    assert image.min()>=0 and image.max()<=1
                    image_count+=1
    repeated=0
    for keys,g in f[(f.sigma==1.5)&(f.gain==.6)&(f.dx==0)&(f.dy==0)].groupby(['shape','polarity','sensor']):
        ids=sorted(g.case_id.unique());assert len(ids)==3
        with np.load(OUT/'cases'/f'{ids[0]:03d}'/'images.npz') as a:
            for case in ids[1:]:
                with np.load(OUT/'cases'/f'{case:03d}'/'images.npz') as b:
                    assert all(np.array_equal(a[key],b[key]) for key in a.files)
                    repeated+=1
    # Each report field is recomputed from the stored per-profile arrays.
    profile_aggregate_max=0.
    for frame,directory in [(f,'cases'),(r,'radiometry_cases')]:
        for case,g in frame.groupby('case_id'):
            with np.load(OUT/directory/f'{case:03d}'/'profiles.npz') as p:
                common=p['common_valid'];assert common.sum()>=684
                for row in g.itertuples():
                    error=p[row.method+'_position_error'][common]
                    difference=max(abs(float(np.median(error))-row.signed_bias_px),abs(float(np.mean(np.abs(error)))-row.boundary_mae_px))
                    profile_aggregate_max=max(profile_aggregate_max,difference)
                    assert difference<1e-12
    spots=[]
    primary_specs=json.loads((OUT/'protocol.json').read_text())['cases']
    secondary_specs=json.loads((OUT/'radiometry_protocol.json').read_text())['cases']
    for directory,specs,ids in [('cases',primary_specs,[0,5,14,26,80,85,94,166,225]),('radiometry_cases',secondary_specs,[24,61,74])]:
        for case in ids:
            row=specs[case];coords,_,_=core.samples(row['shape'],row.get('dx',0),row.get('dy',0))
            if 'inside' in row:inside,outside=row['inside'],row['outside']
            else:
                inside,outside=(.15,.75) if row['polarity']==-1 else (.75,.15)
                inside*=row['gain'];outside*=row['gain']
            folder=OUT/directory/f'{case:03d}'
            with np.load(folder/'images.npz') as images,np.load(folder/'profiles.npz') as profiles:
                target=alternative_positions(images['reference'],coords,inside,outside)
                errors=[]
                for name in core.METHODS:
                    value=alternative_positions(images[name],coords,inside,outside)-target
                    common=profiles['common_valid'];assert np.isfinite(value[common]).all()
                    errors.append(float(np.max(np.abs(value[common]-profiles[name+'_position_error'][common]))))
                assert max(errors)<1e-4
                spots.append({'directory':directory,'case_id':case,'max_independent_interpolator_error_px':max(errors)})
    calibration=json.loads((OUT/'real_profile_calibration_v2.json').read_text())
    assert len(calibration)==36 and max(x['max_geometry_fixture_bias_px'] for x in calibration)<.004
    # Preserve all failed per-profile readouts; they do not disappear in summaries.
    invalid_per_method=real.groupby('method').apply(lambda g:int((720-g.valid_profiles).sum()),include_groups=False).to_dict()
    core.save('verification.json',{'protected_inputs_unchanged':len(snapshot),'image_arrays_finite_and_bounded':image_count,'exact_repeated_control_pairs':repeated,
        'profile_summary_max_numeric_difference':profile_aggregate_max,'independent_interpolation_spots':spots,'real_invalid_profiles_by_method':invalid_per_method,
        'retained_failures':['Initial real-profile calibration stopped before optical comparison; v2 refines geometry-only reference coordinates and satisfies a stricter threshold.',
                            'Initial generic finite-number summary check incorrectly included declared null 2D centers of straight edges; corrected check requires those nulls and finite circle centers. No measurement values changed.'],
        'source_code_sha256':core.sha(__file__),'code_sha256':{p.name:core.sha(p) for p in OUT.glob('*.py')}})
    print(json.dumps({'images_checked':image_count,'control_repeats':repeated,'independent_interpolation_max_error_px':max(s['max_independent_interpolator_error_px'] for s in spots),'real_profile_failures_preserved':invalid_per_method,'protected_inputs_unchanged':len(snapshot)},indent=2))

if __name__=='__main__':main()

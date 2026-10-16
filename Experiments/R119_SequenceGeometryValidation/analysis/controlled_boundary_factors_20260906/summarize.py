"""Numerical decision summary of controlled and real-reference diagnostics."""
import json
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as core
OUT=core.OUT

def counts(frame,folder):
    rows=[]
    for case,g in frame.groupby('case_id'):
        with np.load(OUT/folder/f'{case:03d}'/'profiles.npz') as p:
            common=p['common_valid']
            error={m:float(np.median(np.abs(p[m+'_position_error'][common]))) for m in core.METHODS}
        first=g.iloc[0];row={k:first[k] for k in ['case_id','shape','polarity','group']}
        row.update({'common_valid':int(common.sum()),'raw_near_correct':error['Raw']<=.04,
                    'unnecessary_position_trigger':error['Raw']<=.04 and error['position_only']-error['Raw']>=.05,
                    'oracle_width_trigger':error['oracle_geometry_width']-error['Raw']>=.05,
                    'full_minus_raw_median_absolute_error':error['full']-error['Raw'],
                    'position_minus_raw_median_absolute_error':error['position_only']-error['Raw'],
                    'oracle_width_minus_raw_median_absolute_error':error['oracle_geometry_width']-error['Raw']})
        rows.append(row)
    return pd.DataFrame(rows)

def main():
    primary=pd.read_csv(OUT/'measurements.csv');radiometry=pd.read_csv(OUT/'radiometry_measurements.csv')
    real=pd.read_csv(OUT/'real_halfcontrast_measurements_v2.csv')
    assert len(primary)==1680 and len(radiometry)==700 and len(real)==3456
    for frame,keys in [(primary,['case_id','method']),(radiometry,['case_id','method']),(real,['exposure','pillar','method'])]:
        assert not frame.duplicated(keys).any() and frame.common_valid_profiles.min()>=.95*720
        metric='median_boundary_offset_px' if frame is real else 'boundary_mae_px'
        assert np.isfinite(frame[[metric,'valid_profiles','common_valid_profiles']].to_numpy()).all()
    # A straight edge has no two-dimensional center; these declared nulls must
    # remain null, not be mistaken for a failed or perfect center estimate.
    assert primary.loc[primary['shape']=='line',['center_error_x_px','center_error_y_px']].isna().all().all()
    assert primary.loc[primary['shape']!='line',['center_error_x_px','center_error_y_px']].notna().all().all()
    pc=counts(primary,'cases');rc=counts(radiometry,'radiometry_cases')
    pc.to_csv(OUT/'primary_triggers.csv',index=False,mode='x');rc.to_csv(OUT/'radiometry_triggers.csv',index=False,mode='x')
    clean_ids=primary[primary.sensor=='clean_float'].case_id.unique();pc_clean=pc[pc.case_id.isin(clean_ids)]
    motion=[]
    for keys,g in primary[(primary.group=='motion')&(primary['shape']!='line')].groupby(['shape','polarity','sensor','method']):
        baseline=g[(g.dx==0)&(g.dy==0)].iloc[0]
        error=np.hypot(g.center_error_x_px-baseline.center_error_x_px,g.center_error_y_px-baseline.center_error_y_px)
        motion.append(dict(zip(['shape','polarity','sensor','method'],keys),max_motion_error_px=float(error.max())))
    mf=pd.DataFrame(motion);mf.to_csv(OUT/'motion_residuals.csv',index=False,mode='x')
    real_table=real.groupby(['exposure','method']).median_boundary_offset_px.median().unstack('method')
    real_table.to_csv(OUT/'real_offsets_by_exposure.csv',mode='x')
    real_main=real[real.method.isin(['Raw','full','no_shift','attenuation'])]
    observed={method:{'median_offset_px':float(g.median_boundary_offset_px.median()),'outward_observations':int((g.median_boundary_offset_px>0).sum())} for method,g in real_main.groupby('method')}
    result={
        'decision':'Prioritize validating and repairing the synthetic-to-real optical boundary/reference relationship before architecture or loss-weight changes. Keep position correction; do not train a hardcoded inward offset or launch long training.',
        'scope':'240 primary cases plus 100 declared radiometric follow-up cases; three simple geometries; one frozen model. 432 existing real observations with a separately calibrated readout.',
        'primary_clean_cases':len(pc_clean),'primary_clean_unnecessary_position_triggers':int(pc_clean.unnecessary_position_trigger.sum()),
        'primary_clean_oracle_width_triggers':int(pc_clean.oracle_width_trigger.sum()),
        'radiometry_unnecessary_position_triggers':rc[rc.unnecessary_position_trigger].to_dict(orient='records'),
        'radiometry_oracle_width_triggers':int(rc.oracle_width_trigger.sum()),
        'primary_common_valid_min':int(primary.common_valid_profiles.min()),'radiometry_common_valid_min':int(radiometry.common_valid_profiles.min()),'real_common_valid_min':int(real.common_valid_profiles.min()),
        'real_offsets':observed,
        'real_own_level_sensitivity_median':{m:float(g.median_boundary_offset_px.median()) for m,g in real.groupby('method') if m.endswith('_own_levels')},
        'motion_max_error_by_sensor_method':mf.groupby(['sensor','method']).max_motion_error_px.max().reset_index().to_dict(orient='records'),
        'real_reference_calibration_max_px':max(r['max_geometry_fixture_bias_px'] for r in json.loads((OUT/'real_profile_calibration_v2.json').read_text())),
        'limits':['The physical cause of optical/SEM boundary mismatch is not yet identified; possible calibration, boundary definition and imaging effects must be separated.',
                  'Synthetic profile errors are relative to sampled synthetic truth; real offsets are relative to the SEM-mask-derived digital reference. Do not infer a universal physical correction coefficient.',
                  'Repeated baseline cases across parameter groups are explicitly duplicated controls, not independent samples.',
                  'No texture fidelity or full model qualification is established.']}
    core.save('decision.json',result)
    core.save('chart_contract.json',{'renderer':'standalone matplotlib','panels':['controlled dark circle48 blur vs geometric boundary error','independent brightness offset at fixed contrast .15 on a straight bright edge','existing real SEM-referenced edge offsets by exposure'],
        'units':'signed boundary offset pixels; positive outward','reference_scope':'different reference populations shown on separate axes; never pooled','source_rows':[1680,700,3456]})
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(16,5),layout='constrained')
    names={'Raw':'Raw','full':'Full E42','position_only':'Position only','no_shift':'Position off','oracle_geometry_width':'Known-geometry width'}
    colors={'Raw':'#646B73','full':'#374F8A','position_only':'#B25B37','no_shift':'#967CA2','oracle_geometry_width':'#4D7B78'}
    g=primary[(primary['shape']=='circle48')&(primary.polarity==-1)&(primary.sensor=='clean_float')&(primary.group=='blur')]
    for i,m in enumerate(['Raw','full','no_shift']):
        v=g[g.method==m];axes[0].plot(v.sigma,v.signed_bias_px,label=names[m],color=colors[m],marker=['o','s','^'][i],lw=1.5)
    axes[0].set_title('Known dark circle: blur creates inward bias',loc='left',fontsize=11);axes[0].set_xlabel('Gaussian blur sigma (px)');axes[0].set_ylabel('Signed boundary error vs sampled truth (px)')
    g=radiometry[(radiometry['shape']=='line')&(radiometry.polarity==1)&(radiometry.group=='independent_levels')&(radiometry.contrast==.15)]
    for i,m in enumerate(['Raw','full','position_only']):
        v=g[g.method==m];axes[1].plot(v.midpoint,v.signed_bias_px,label=names[m],color=colors[m],marker=['o','s','^'][i],lw=1.5)
    axes[1].set_title('Fixed contrast: intensity offset still matters',loc='left',fontsize=11);axes[1].set_xlabel('Mean of inside/outside intensity (0-1)');axes[1].set_ylabel('Signed boundary error vs sampled truth (px)')
    for i,m in enumerate(['Raw','full','no_shift']):
        axes[2].plot(real_table.index,real_table[m],label=names[m],color=colors[m],marker=['o','s','^'][i],lw=1.5)
    axes[2].set_title('Real Raw already lies outside the SEM edge',loc='left',fontsize=11);axes[2].set_xlabel('Existing exposure ID');axes[2].set_ylabel('Median offset vs SEM reference (px)');axes[2].set_ylim(bottom=0)
    for ax in axes:
        ax.axhline(0,color='#333333',lw=.8);ax.grid(axis='y',alpha=.15);ax.legend(fontsize=9)
    fig.suptitle('Controlled geometry and real boundary references require different corrections',x=.04,ha='left',fontsize=15)
    fig.savefig(OUT/'decision_evidence.png',dpi=170);plt.close(fig)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

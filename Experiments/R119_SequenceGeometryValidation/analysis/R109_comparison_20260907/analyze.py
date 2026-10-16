"""Readout-specific conclusions; incomplete peak coverage is never called consensus."""
from pathlib import Path
import json
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent
MAIN=['Raw','R109_full','R119_full']

def save(name,value):
    def clean(x):
        if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
        if isinstance(x,list):return [clean(v) for v in x]
        if isinstance(x,float) and not np.isfinite(x):return None
        return x
    with (OUT/name).open('x') as f:json.dump(clean(value),f,indent=2,allow_nan=False)

def paired_effect(frame,column,first,second):
    q=frame.pivot(index=['exposure','pillar'],columns='method',values=column)
    d=q[first]-q[second];pillars=d.groupby(level='pillar').median();exposure=d.groupby(level='exposure').median()
    return {'first':first,'second':second,'observations':int(d.notna().sum()),'median_observation_change':float(d.median()),
            'median_pillar_change':float(pillars.median()),'improved_pillars':int((pillars<0).sum()),'worsened_pillars':int((pillars>0).sum()),
            'negative_exposure_medians':int((exposure<0).sum()),'positive_exposure_medians':int((exposure>0).sum())}

def main():
    a=pd.read_csv(OUT/'acm_measurements.csv');p=pd.read_csv(OUT/'profile_measurements.csv')
    assert len(a)==7776 and a.valid.eq(1).all() and not a.duplicated(['reference','exposure','pillar','method']).any()
    assert len(p)==31104 and not p.duplicated(['reference','exposure','pillar','method','readout']).any()
    offsets=a[a.method=='Raw'][['reference','exposure','pillar','raw_offset_x','raw_offset_y']]
    merged=p.merge(offsets,on=['reference','exposure','pillar'],suffixes=('','_acm'),validate='many_to_one')
    assert (merged.raw_offset_x==merged.raw_offset_x_acm).all() and (merged.raw_offset_y==merged.raw_offset_y_acm).all()
    rows=[]
    for reference,g in a[a.method.isin(MAIN)].groupby('reference'):
        for metric in ['common_boundary','legacy_boundary']:
            for first,second in [('R109_full','Raw'),('R119_full','Raw'),('R119_full','R109_full')]:
                rows.append({'reference':reference,'readout':metric,'minimum_common_profiles':None,'cases_meeting_90pct':432,**paired_effect(g,metric,first,second)})
    for (reference,readout),g in p[p.method.isin(MAIN)].groupby(['reference','readout']):
        coverage=g[g.method=='Raw'].main_common_profiles
        for first,second in [('R109_full','Raw'),('R119_full','Raw'),('R119_full','R109_full')]:
            rows.append({'reference':reference,'readout':readout,'minimum_common_profiles':int(coverage.min()),'median_common_profiles':float(coverage.median()),
                         'cases_meeting_90pct':int((coverage>=648).sum()),**paired_effect(g,'main_common_mae_px',first,second)})
    comparisons=pd.DataFrame(rows);comparisons.to_csv(OUT/'readout_comparisons.csv',index=False,mode='x')
    paths=[]
    for (reference,method),g in a[~a.method.isin(MAIN)].groupby(['reference','method']):
        full='R109_full' if method.startswith('R109') else 'R119_full'
        selected=a[(a.reference==reference)&a.method.isin([method,full])]
        paths.append({'reference':reference,'method':method,'readout':'ACM_common',**paired_effect(selected,'common_boundary',method,full)})
    for (reference,readout,method),g in p[~p.method.isin(MAIN)].groupby(['reference','readout','method']):
        per_pillar=g.groupby('pillar').paired_mae_change_vs_full_px.median();per_exposure=g.groupby('exposure').paired_mae_change_vs_full_px.median()
        paths.append({'reference':reference,'method':method,'readout':readout,'observations':len(g),
                      'median_observation_change':float(g.paired_mae_change_vs_full_px.median()),'median_pillar_change':float(per_pillar.median()),
                      'improved_pillars':int((per_pillar<0).sum()),'worsened_pillars':int((per_pillar>0).sum()),
                      'negative_exposure_medians':int((per_exposure<0).sum()),'positive_exposure_medians':int((per_exposure>0).sum()),
                      'median_common_profiles':float(g.paired_full_profiles.median()),'cases_meeting_90pct':int((g.paired_full_profiles>=648).sum()),
                      'median_signed_change_vs_full_px':float(g.paired_signed_change_vs_full_px.median())})
    pd.DataFrame(paths).to_csv(OUT/'path_comparisons.csv',index=False,mode='x')
    # Secondary model-to-model intersection is explicitly separate from the
    # declared three-way population and cannot rescue Raw comparisons.
    secondary=[]
    for file in (OUT/'profile_arrays').glob('*.npz'):
        reference,pid,exp=file.stem.rsplit('_',2)
        with np.load(file) as f:
            for readout in ['half','peak075','peak125']:
                valid=f['R109_full_'+readout+'_valid']&f['R119_full_'+readout+'_valid']
                difference=np.abs(f['R119_full_'+readout+'_error'])-np.abs(f['R109_full_'+readout+'_error'])
                secondary.append({'reference':reference,'pillar':int(pid[1:]),'exposure':int(exp[1:]),'readout':readout,'common_profiles':int(valid.sum()),
                                  'R119_minus_R109_mae_px':float(np.mean(difference[valid])) if valid.any() else None})
    secondary=pd.DataFrame(secondary);secondary.to_csv(OUT/'secondary_model_pair_comparison.csv',index=False,mode='x')
    result={'main_comparisons':rows,'path_comparisons':paths,
            'decision':'Do not equate ACM improvement with physical midpoint restoration or copy R109 as ground truth. Preserve the reproducible R119 position-path harm relative to its full output, but first define/calibrate the desired edge and disentangle profile translation from profile compression before more training.',
            'peak_readout_limit':'Primary sigma0.75 peak has inadequate Raw three-way coverage. Sigma1.25 is a predeclared sensitivity, not a replacement success criterion. Secondary model-pair comparisons use a separately labeled population.',
            'operator_sanity':'Clean known-geometry tests confirm that the nominal position path also changes width, more strongly in R119. These are fixed-weight interventions, not retrained causal comparisons.',
            'no_training':True,'no_promotion':True}
    save('summary.json',result)
    plots(a,p,comparisons)
    print(comparisons[comparisons.reference=='historical'][['readout','first','second','median_pillar_change','improved_pillars','worsened_pillars','cases_meeting_90pct']].round(5).to_string(index=False))
    print(pd.DataFrame(paths).query("reference=='historical' and method in ['R109_no_position','R119_no_position','R119_no_detail']")[['method','readout','median_pillar_change','negative_exposure_medians','cases_meeting_90pct']].round(5).to_string(index=False))

def plots(a,p,comparisons):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors={'Raw':'#686D73','R109_full':'#3D648C','R119_full':'#B56940'}
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
    a=a[a.reference=='global_pitch_matched'];p=p[p.reference=='global_pitch_matched']
    for i,method in enumerate(MAIN):
        axes[0].bar(i,a[a.method==method].common_boundary.median(),color=colors[method])
        axes[1].bar(i,p[(p.method==method)&(p.readout=='half')].main_common_mae_px.median(),color=colors[method])
    axes[0].set_title('ACM contour error',loc='left');axes[0].set_ylabel('% of pillar pitch; lower is better')
    axes[1].set_title('Half-contrast position error',loc='left');axes[1].set_ylabel('Pixels; lower is better')
    raw=p[(p.method=='Raw')]
    for i,(readout,label) in enumerate([('half','Midpoint'),('peak075','Peak 0.75'),('peak125','Peak 1.25')]):
        axes[2].bar(i,100*raw[raw.readout==readout].main_common_profiles.median()/720,color='#717D8B')
    axes[2].axhline(90,color='#333',ls=':',lw=1);axes[2].set_ylim(0,105);axes[2].set_ylabel('Median shared valid profiles (%)');axes[2].set_title('Three-way readout coverage',loc='left')
    for ax in axes[:2]:ax.set_xticks(range(3),['Raw','R109','R119'])
    axes[2].set_xticks(range(3),['Midpoint','Peak 0.75','Peak 1.25'])
    fig.suptitle('Matched alignment does not make different edge definitions equivalent\nGlobal pitch-matched reference | 36 pillars x 12 exposures',x=.03,ha='left',fontsize=13)
    fig.savefig(OUT/'readout_comparison.png',dpi=170);plt.close(fig)
    q=p[p.readout=='half'];fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for method in MAIN:
        g=q[q.method==method].groupby('exposure').main_common_bias_px.median()
        axes[0].plot(g.index,g.values,marker='o',label=method.replace('_full',''),color=colors[method])
    axes[0].axhline(0,color='#333',lw=.8);axes[0].set_xlabel('Exposure ID');axes[0].set_ylabel('Signed midpoint offset (px; outward +)');axes[0].legend();axes[0].set_title('Midpoint bias across exposures',loc='left')
    for method,color in [('R109_no_position','#3D648C'),('R119_no_position','#B56940')]:
        g=q[q.method==method].groupby('exposure').paired_mae_change_vs_full_px.median()
        axes[1].plot(g.index,g.values,marker='o',label=method,color=color)
    axes[1].axhline(0,color='#333',lw=.8);axes[1].set_xlabel('Exposure ID');axes[1].set_ylabel('Position-off minus full error (px)');axes[1].legend(fontsize=8);axes[1].set_title('Removing position affects models differently',loc='left')
    fig.savefig(OUT/'position_path_effects.png',dpi=170);plt.close(fig)
    sanity=pd.read_csv(OUT/'operator_sanity.csv');g=sanity[(sanity['shape']=='line')&sanity.method.isin(['R109_position_only','R119_position_only'])]
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
    for method,color in [('R109_position_only','#3D648C'),('R119_position_only','#B56940')]:
        v=g[g.method==method];ax.plot(v.sigma,v.median_width_change_vs_Raw_px,marker='o',label=method,color=color)
    ax.axhline(0,color='#333',lw=.8);ax.set_xlabel('Input blur sigma (px)');ax.set_ylabel('Width change from position path alone (px)');ax.set_title('A position field also performs sharpening',loc='left');ax.legend(fontsize=9)
    fig.savefig(OUT/'position_width_coupling.png',dpi=170);plt.close(fig)

if __name__=='__main__':main()

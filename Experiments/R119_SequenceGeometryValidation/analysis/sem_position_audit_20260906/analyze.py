"""Independent recomputation and paired summaries of frozen SEM path diagnosis."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.ndimage import binary_erosion, distance_transform_edt, gaussian_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
METHODS=['Raw','base','no_shift','attenuation']
LABELS={'Raw':'Raw','base':'Full E42','no_shift':'Position off','attenuation':'Reduced full correction'}
COLORS={'Raw':'#646B73','base':'#374F8A','no_shift':'#B25B37','attenuation':'#967CA2'}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)

def centroid(mask):
    y,x=np.nonzero(mask);return np.array([x.mean(),y.mean()])

def translated(mask,dx,dy):
    result=np.zeros_like(mask);h,w=mask.shape
    sx0,sx1=max(0,-dx),min(w,w-dx);sy0,sy1=max(0,-dy),min(h,h-dy)
    if sx1>sx0 and sy1>sy0:result[sy0+dy:sy1+dy,sx0+dx:sx1+dx]=mask[sy0:sy1,sx0:sx1]
    return result

def boundary_distance(truth,predicted,pitch):
    delta=centroid(truth)-centroid(predicted)
    # MATLAB rounds ties away from zero; avoid relying on numpy banker's rounding.
    shift=(np.sign(delta)*np.floor(np.abs(delta)+.5)).astype(int)
    aligned=translated(predicted,*shift)
    te=truth ^ binary_erosion(truth,np.ones((3,3)))
    pe=aligned ^ binary_erosion(aligned,np.ones((3,3)))
    distances=np.r_[distance_transform_edt(~te)[pe],distance_transform_edt(~pe)[te]]
    return float(distances.mean()*100/pitch)

def counts(a):
    a=np.asarray(a);return {'improved':int((a < -1e-9).sum()),'tied':int((np.abs(a)<=1e-9).sum()),'worsened':int((a > 1e-9).sum())}

def main():
    if (OUT/'analysis_summary.json').exists():raise FileExistsError('Never overwrite a previous result')
    frame=pd.read_csv(OUT/'measurements.csv')
    assert len(frame)==1728 and not frame.duplicated(['exposure','pillar','method']).any()
    assert frame.valid.all() and frame.failure.isna().all()
    assert set(frame.exposure)==set(range(13,25)) and set(frame.pillar)==set(range(1,37))
    parity=frame[frame.method.isin(['Raw','base'])]
    assert len(parity)==864 and (parity.mask_parity==0).all()
    # Original cell export assertion failed: old display crops were contrast
    # normalized whereas new crops retain original intensity. Require an
    # independent source-to-crop and historical-normalization replay, never
    # overwrite the failed assertion or silently waive its comparison.
    cell_check=pd.read_csv(OUT/'cell_export_diagnosis.csv')
    assert len(cell_check)==864 and not cell_check.duplicated(['exposure','pillar','method']).any()
    assert (cell_check.normalized_export_difference==0).all()
    assert (cell_check.original_intensity_crop_difference==0).all()
    arrays=loadmat(OUT/'measured_arrays.mat',variable_names=['masks','cells','truth_masks','opt_pitch'])
    masks=arrays['masks'].astype(bool);cells=arrays['cells'];truth=arrays['truth_masks'].astype(bool)
    pitch=float(arrays['opt_pitch'].item())
    assert masks.shape==(104,104,36,12,4) and cells.shape==masks.shape
    independent=[]
    for row in frame.itertuples():
        p,e,m=row.pillar-1,row.exposure-13,METHODS.index(row.method)
        b=boundary_distance(truth[:,:,p],masks[:,:,p,e,m],pitch)
        area=100*(float(masks[:,:,p,e,m].sum())-truth[:,:,p].sum())/truth[:,:,p].sum()
        independent.append({'exposure':row.exposure,'pillar':row.pillar,'method':row.method,
                            'boundary_recomputed':b,'boundary_difference':b-row.boundary,'area_difference':area-row.signed_area})
    cross=pd.DataFrame(independent);cross.to_csv(OUT/'independent_recalculation.csv',index=False,mode='x')
    assert cross.boundary_difference.abs().max()<2e-6 and cross.area_difference.abs().max()<1e-10
    old=pd.read_csv(ROOT/'results/formal_sem/results/tables/primary_contour_metrics.csv')
    old['method']=old.method.replace({'R119_B_E42':'base'})
    # Explicit paired merge by pillar prevents false agreements from pooled averages.
    merged=parity.merge(old,left_on=['exposure','pillar','method'],right_on=['exposure','pillar_id','method'],validate='one_to_one')
    old_difference=float((merged.boundary-merged.mean_boundary_distance_pitch_pct).abs().max())
    assert old_difference<2e-6
    effects=frame.pivot(index=['exposure','pillar'],columns='method',values='boundary')
    area=frame.pivot(index=['exposure','pillar'],columns='method',values='signed_area')
    for method in ['base','no_shift','attenuation']:
        effects[f'{method}_minus_Raw']=effects[method]-effects.Raw
    effects['no_shift_minus_base']=effects.no_shift-effects.base
    effects['no_shift_minus_attenuation']=effects.no_shift-effects.attenuation
    effects['signed_area_no_shift_minus_base']=area.no_shift-area.base
    effects['signed_area_base_minus_Raw']=area.base-area.Raw
    effects['signed_area_no_shift_minus_Raw']=area.no_shift-area.Raw
    effects.to_csv(OUT/'paired_observations.csv',mode='x')
    by_exposure=[]
    for exposure,group in effects.groupby(level='exposure'):
        item={'exposure':int(exposure),'pillars':len(group)}
        for method in METHODS:
            item[method+'_median_boundary']=float(group[method].median())
            item[method+'_median_signed_area']=float(area.loc[exposure,method].median())
        for name in ['no_shift_minus_base','no_shift_minus_attenuation','no_shift_minus_Raw','base_minus_Raw']:
            item[name+'_median']=float(group[name].median())
            item.update({name+'_'+k:v for k,v in counts(group[name]).items()})
        by_exposure.append(item)
    exposure_frame=pd.DataFrame(by_exposure);exposure_frame.to_csv(OUT/'by_exposure.csv',index=False,mode='x')
    pillar_effect=effects.groupby(level='pillar').median();pillar_effect.to_csv(OUT/'by_pillar.csv',mode='x')
    rng=np.random.default_rng(20260906)
    pillar_delta=pillar_effect.no_shift_minus_base.to_numpy()
    bootstrap=np.median(rng.choice(pillar_delta,(5000,36),replace=True),axis=1)
    # Fixed SEM interior (8+ pixels from edge), shared across all images/methods.
    # Band-pass energy/correlation cannot prove unknown material texture fidelity.
    detail=[]
    for p in range(36):
        region=distance_transform_edt(truth[:,:,p])>8
        edge=(distance_transform_edt(truth[:,:,p])<=6)&(distance_transform_edt(~truth[:,:,p])<=6)
        assert region.sum()>100
        for e in range(12):
            images=[cells[:,:,p,e,m].astype(float) for m in range(4)]
            bands=[gaussian_filter(im,.7)-gaussian_filter(im,2.) for im in images]
            rec={'exposure':e+13,'pillar':p+1,'interior_pixels':int(region.sum()),
                 'no_shift_base_interior_mae_gray':float(np.abs(images[2]-images[1])[region].mean()),
                 'no_shift_base_edge_mae_gray':float(np.abs(images[2]-images[1])[edge].mean())}
            for i,method in enumerate(METHODS):
                rec[method+'_interior_band_rms']=float(np.sqrt(np.mean(bands[i][region]**2)))
                rec[method+'_correction_mae']=float(np.abs(images[i]-images[0]).mean())
            rec['no_shift_base_band_correlation']=float(np.corrcoef(bands[1][region],bands[2][region])[0,1])
            rec['no_shift_base_band_rms_ratio']=rec['no_shift_interior_band_rms']/rec['base_interior_band_rms']
            rec['attenuation_no_shift_correction_mismatch_pct']=100*(rec['attenuation_correction_mae']-rec['no_shift_correction_mae'])/max(rec['no_shift_correction_mae'],1e-12)
            detail.append(rec)
    df=pd.DataFrame(detail);df.to_csv(OUT/'detail_and_amplitude.csv',index=False,mode='x')
    summary={
        'scope':'Frozen E42 mechanism diagnosis, 36 pillars in one sample, 12 existing exposures; no new model qualification',
        'observations':432,'measurement_rows':len(frame),'failures':0,'historical_mask_and_cell_parity_checks':864,
        'initial_verification_failure':'Original direct cell-export parity assertion failed. Exact replay of historical mat2gray export and separate original-intensity crop parity both yield zero differences on all 864 pairs. Initial script, failed log and measurements retained.',
        'independent_boundary_max_abs_difference':float(cross.boundary_difference.abs().max()),
        'old_table_max_abs_difference':old_difference,
        'pooled_medians':{m:{'boundary_pitch_pct':float(effects[m].median()),'signed_area_pct':float(area[m].median())} for m in METHODS},
        'no_shift_vs_base_observations':counts(effects.no_shift_minus_base),
        'no_shift_vs_attenuation_observations':counts(effects.no_shift_minus_attenuation),
        'no_shift_vs_Raw_observations':counts(effects.no_shift_minus_Raw),
        'no_shift_vs_base_pillars':counts(pillar_delta),
        'median_within_pillar_effect_pitch_percentage_points':float(np.median(pillar_delta)),
        'pillar_bootstrap95':np.percentile(bootstrap,[2.5,97.5]).tolist(),
        'exposures_with_negative_median_no_shift_vs_base':int((exposure_frame.no_shift_minus_base_median<0).sum()),
        'exposures_with_negative_median_no_shift_vs_attenuation':int((exposure_frame.no_shift_minus_attenuation_median<0).sum()),
        'base_larger_than_Raw':int((effects.signed_area_base_minus_Raw>0).sum()),
        'no_shift_larger_than_Raw':int((effects.signed_area_no_shift_minus_Raw>0).sum()),
        'no_shift_area_smaller_than_base':int((effects.signed_area_no_shift_minus_base<0).sum()),
        'detail':{'interior_band_rms_ratio_median':float(df.no_shift_base_band_rms_ratio.median()),
                  'interior_band_rms_ratio_p05_p95':df.no_shift_base_band_rms_ratio.quantile([.05,.95]).tolist(),
                  'interior_band_correlation_median':float(df.no_shift_base_band_correlation.median()),
                  'interior_mae_gray_median':float(df.no_shift_base_interior_mae_gray.median()),
                  'edge_mae_gray_median':float(df.no_shift_base_edge_mae_gray.median()),
                  'limitation':'Known identical additive detail does not prove final real-texture truth. Band metrics describe preservation/change, not recovery accuracy.'},
        'per_pillar_amplitude_mismatch_pct':{'median':float(df.attenuation_no_shift_correction_mismatch_pct.median()),
                                            'p05_p95':df.attenuation_no_shift_correction_mismatch_pct.quantile([.05,.95]).tolist(),
                                            'max_abs':float(df.attenuation_no_shift_correction_mismatch_pct.abs().max())},
        'exceptions':effects.loc[effects.no_shift_minus_base>=-1e-9].reset_index().to_dict(orient='records'),
    }
    save('analysis_summary.json',summary)
    save('chart_contract.json',{'renderer':'standalone matplotlib scientific PNG',
         'question':'Is paired contour benefit consistent across exposures and pillars?',
         'takeaway':'See computed effect signs; no universal-model claim',
         'charts':[{'family':'comparison','variant':'exposure grouped dots','rows':48,'units':'boundary distance percent of pitch','zero_baseline':True},
                   {'family':'matrix','variant':'36 by 12 paired-effect heatmap','rows':432,'units':'pitch percentage points','center':0}],
         'visual_review':{'overview':'same preselected pillar 21 for all 12 exposures, same intensity mapping within each row and all four methods','detail_truth':'SEM contour only, no sharp optical intensity truth'}})
    charts(frame,effects,exposure_frame,cells,masks,truth)
    print(json.dumps(summary,indent=2,ensure_ascii=False))

def charts(frame,effects,exp,cells,masks,truth):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,1,figsize=(12,8),gridspec_kw={'height_ratios':[1,1.2]},layout='constrained')
    ax=axes[0]
    for i,method in enumerate(METHODS):
        ax.plot(exp.exposure,exp[method+'_median_boundary'],marker=['o','s','^','D'][i],ls=['--','-', '-',':'][i],color=COLORS[method],label=LABELS[method],lw=1.5,ms=5)
    ax.set_ylim(bottom=0);ax.set_xticks(range(13,25));ax.set_ylabel('Boundary error (% of pillar pitch)');ax.set_xlabel('Existing exposure ID (not exposure duration)')
    ax.set_title('All 36 pillars retained in each exposure',loc='left');ax.legend(ncol=4,fontsize=9,loc='lower right');ax.grid(axis='y',alpha=.18)
    values=effects.no_shift_minus_base.unstack('exposure').to_numpy();vmax=float(np.abs(values).max())
    image=axes[1].imshow(values,cmap='PuOr_r',vmin=-vmax,vmax=vmax,aspect='auto')
    axes[1].set_xticks(range(12),range(13,25));axes[1].set_yticks([0,5,11,17,23,29,35],[1,6,12,18,24,30,36])
    axes[1].set_xlabel('Exposure ID');axes[1].set_ylabel('Pillar ID');axes[1].set_title('Each cell: position off minus full E42; negative means a more accurate contour',loc='left')
    fig.colorbar(image,ax=axes[1],label='Boundary-error change (pitch percentage points)',shrink=.9)
    fig.suptitle('R119 frozen position-path diagnosis | 36 pillars x 12 exposures',x=.04,ha='left',fontsize=15)
    fig.savefig(OUT/'cross_exposure_results.png',dpi=170);plt.close(fig)
    # Fixed central pillar, never selected for a favorable result.
    pillar=21;fig,axes=plt.subplots(12,4,figsize=(9,23),layout='constrained')
    for e in range(12):
        lo,hi=np.percentile(cells[:,:,pillar-1,e,0],[1,99]);vmin,vmax=float(lo),float(max(hi,lo+1))
        for m,method in enumerate(METHODS):
            ax=axes[e,m];ax.imshow(cells[:,:,pillar-1,e,m],cmap='gray',vmin=vmin,vmax=vmax,interpolation='nearest')
            ax.set_xticks([]);ax.set_yticks([])
            if e==0:ax.set_title(LABELS[method],fontsize=10)
            if m==0:ax.set_ylabel('Exposure '+str(e+13))
    fig.suptitle('Same pillar 21 across every exposure\nShared Raw-derived display limits within each row; no independent contrast enhancement',fontsize=12)
    fig.savefig(OUT/'all_exposure_images.png',dpi=130);plt.close(fig)
    # Show all pillars at exposure 13 plus the least favorable exposure by paired median.
    least=int(exp.loc[exp.no_shift_minus_base_median.idxmax(),'exposure'])
    for e in sorted({13,least}):
        fig,axes=plt.subplots(6,6,figsize=(12,12),layout='constrained')
        for p,ax in enumerate(axes.ravel()):
            ax.imshow(cells[:,:,p,e-13,0],cmap='gray',vmin=0,vmax=255)
            ax.contour(truth[:,:,p],levels=[.5],colors=['#FFFFFF'],linewidths=.75)
            ax.contour(masks[:,:,p,e-13,1],levels=[.5],colors=[COLORS['base']],linewidths=.65)
            ax.contour(masks[:,:,p,e-13,2],levels=[.5],colors=[COLORS['no_shift']],linewidths=.65)
            ax.set_title('Pillar '+str(p+1),fontsize=9);ax.axis('off')
        fig.suptitle(f'Exposure {e}: all 36 pillars | white SEM, blue full, orange position off\nUnaligned image coordinates; scores use the historical translation-only comparison',fontsize=13)
        fig.savefig(OUT/f'all_pillars_exposure_{e}.png',dpi=140);plt.close(fig)

if __name__=='__main__':main()

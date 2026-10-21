"""Common-population result review, original readout reproduction and static figures."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/final_review'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd,cv2,torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from evaluation.real import sem_rows,read_image,predict,bidirectional
from training.engine import create

def main():
    assert load(OUT/'execution_audit.json')['passed']
    cfg=load(ROOT/'config/study.json');all_sem=[];summary=[];sources=[];recompute_error=0.
    panel=load(R125/'results/real_panel_v2/frozen_panel.json')
    for item in cfg['run_order']:
        name=f"{item['arm']}_s{item['seed']}";run=ROOT/'runs'/name;folder=run/'evaluations/real_step8192'
        df=pd.read_csv(folder/'SEM_measurements.csv');assert len(df)==72 and not df.duplicated(['exposure','pillar']).any()
        for exp in [13,24]:
            source=next(x['source'] for x in panel['full_images'] if x['name']==f'sem_optical_exposure{exp}')
            raw=read_image(source);path=folder/f'full_images/sem_optical_exposure{exp}/output_float.npz'
            with np.load(path) as f:output=f['output']
            rebuilt=pd.DataFrame(sem_rows(raw,output,exp)).sort_values('pillar')
            stored=df[df.exposure==exp].sort_values('pillar')
            for key in ['Raw_diameter_pitch_ratio','candidate_diameter_pitch_ratio','paired_error_change_lower','paired_error_change_upper','level_0.5_median_radius_change_px']:
                assert np.array_equal(rebuilt[key].isna(),stored[key].isna())
                delta=np.abs(rebuilt[key].to_numpy()-stored[key].to_numpy())
                error=float(np.nanmax(delta));recompute_error=max(recompute_error,error);assert error<1e-12
            assert rebuilt.direction.tolist()==stored.direction.tolist()
            sources += [record(path),source]
        # Independently verify that reference-band error extrema/signs were
        # computed with the original source population, not a candidate mask.
        for _,row in df.iterrows():
            if row.measurable:
                a,b=row.SEM_inner_ratio,row.SEM_outer_ratio;x,z=row.candidate_diameter_pitch_ratio,row.Raw_diameter_pitch_ratio
                pts=np.r_[np.linspace(a,b,101),np.clip([x,z],a,b)]
                change=np.abs(x-pts)-np.abs(z-pts)
                assert abs(change.min()-row.paired_error_change_lower)<1e-12 and abs(change.max()-row.paired_error_change_upper)<1e-12
        df['run']=name;all_sem.append(df)
        real=load(folder/'verification.json');test=load(run/'evaluations/test_step8192.json');dev=load(run/'evaluations/dev_step8192.json')
        inner=df[df.context_stratum=='all_readout_pixels_fully_neural'];dark=df[df.exposure==24]
        groups={}
        for (exp,context),g in df.groupby(['exposure','context_stratum']):
            groups[f'{exp}_{context}']=dict(objects=len(g),directions=g.direction.value_counts().to_dict(),median_half_level_radius_change_px=float(g['level_0.5_median_radius_change_px'].median()))
        summary.append(dict(run=name,arm=item['arm'],seed=item['seed'],SEM_improved=int((df.direction=='improves').sum()),SEM_worsened=int((df.direction=='worsens').sum()),SEM_unmeasurable=int((df.direction=='unmeasurable').sum()),normal_improved=int(((df.exposure==13)&(df.direction=='improves')).sum()),dark_improved=int((dark.direction=='improves').sum()),dark_worsened=int((dark.direction=='worsens').sum()),dark_inner_worsened=int(((inner.exposure==24)&(inner.direction=='worsens')).sum()),motion_pairs_consistent=real['motion_consistent'],maximum_motion_change_vs_Raw_px=real['maximum_motion_change_vs_Raw_px'],generated_test_MAE=test['overall']['mean_MAE_gray'],Raw_generated_test_MAE=test['overall']['Raw_mean_MAE_gray'],generated_test_worse_parents=test['overall']['worse_than_Raw_parents'],clean_test_MAE=test['categories']['clean_identity']['mean_MAE_gray'],clean_test_worst_pixel_error=test['categories']['clean_identity']['worst_pixel_error_gray'],dev_worst_parent_MAE=dev['overall']['worst_parent_MAE_gray'],SEM_groups=groups))
    joined=pd.concat(all_sem,ignore_index=True)
    keys=['exposure','pillar']
    ref=all_sem[0].set_index(keys)
    for df in all_sem[1:]:
        d=df.set_index(keys)
        for col in ['fixed_source_SEM_rays','Raw_diameter_pitch_ratio','SEM_inner_ratio','SEM_rim_ratio','SEM_outer_ratio','context_stratum']:
            assert d[col].equals(ref[col])
    assert all(x['dark_inner_worsened']==16 for x in summary)
    joined.to_csv(OUT/'all_final_SEM_rows.csv',index=False)
    pd.DataFrame([{k:v for k,v in x.items() if k!='SEM_groups'} for x in summary]).to_csv(OUT/'comparison.csv',index=False)
    selected='P_s1285002'
    # This is a follow-up engineering choice, not a retrospectively invented
    # pre-registered promotion gate or a claim of universally best performance.
    selection=dict(selected_for_further_repair=selected,selected_for_production=None,reason=['Complete72-object measurement coverage unlike I_s1285002/P_s1285001','Only candidate improves all36normal-exposure objects across the SEM definition band','More dark-exposure improvements than other candidates, but29/36dark objects still worsen','All6motion pairs remain source-consistent; generated restoration useful but not selection authority'],unresolved=['All16fully-neural dark objects worsen in every candidate','Clean generated references are modified by all candidates','Real material-edge equivalence and independent physical displacement are unqualified'],original_final_step8192_retained=True,one_final_application_model_required=True,no_additional_training_launched=True,not_a_claim_that_P_objective_is_causally_superior=True)
    save(OUT/'selection.json',selection)
    # Re-execute a full real image with the retained candidate, using image only.
    run=ROOT/'runs'/selected;cp=run/'checkpoints/step8192.pth'
    model,opt=create(1285002,'cuda',cfg);payload=torch.load(cp,map_location='cpu');model.load_state_dict(payload['model']);model.eval()
    src=next(x['source'] for x in panel['full_images'] if x['name']=='sem_optical_exposure24');raw=read_image(src)
    prediction,neural,weight=predict(model,raw)
    with np.load(run/'evaluations/real_step8192/full_images/sem_optical_exposure24/output_float.npz') as f:
        inference_error=float(np.max(np.abs(prediction-f['output'])));neural_error=float(np.max(np.abs(neural-f['neural_output'])))
    assert inference_error<2e-6 and neural_error<2e-6
    # Independently rerun the retained candidate's worst source-relative pair.
    motions=load(run/'evaluations/real_step8192/motion_measurements.json');worst=max(motions,key=lambda x:x['change_vs_Raw_px'])
    item=next(x for x in panel['motion_pairs'] if x['sequence']==worst['sequence']);raws=[read_image(s)[80:-80,80:-80].astype(float) for s in item['sources']];preds=[]
    for frame in [0,1]:
        with np.load(run/'evaluations/real_step8192/motion'/item['sequence']/f'frame{frame}/output_float.npz') as f:preds.append(f['output'][80:-80,80:-80].astype(float))
    mr,mp=bidirectional(*raws),bidirectional(*preds);assert mr['valid'] and mp['valid']
    motion_difference=float(np.hypot(mr['forward']['dx']-mp['forward']['dx'],mr['forward']['dy']-mp['forward']['dy']))
    assert abs(motion_difference-worst['change_vs_Raw_px'])<1e-9
    self_check=dict(SEM_all288_rows_recomputed=True,maximum_SEM_recompute_difference=recompute_error,source_SEM_population_identical_across_all_models=True,reference_band_error_extrema_independently_checked=True,full_dark_image_inference_max_difference=inference_error,unguarded_inference_max_difference=neural_error,worst_motion_pair_recomputed=item['sequence'],recomputed_worst_motion_change_px=motion_difference,checkpoint=record(cp))
    save(OUT/'comparison_verification.json',dict(passed=True,verified_utc=now(),checks=self_check,summary=summary,sources=sources,source=record(__file__),selection=record(OUT/'selection.json')))
    figdir=ROOT/'reports/figures';figdir.mkdir(exist_ok=True)
    contract=dict(question='Does final reconstruction improve current SEM-defined sizes at both real exposures?',takeaway='Every candidate worsens all16dark interior objects; one promising follow-up candidate but no production-ready winner',surface='standalone thesis-project PNG figures with Matplotlib',family='comparison stacked bars plus same-source image panels',grain='36objects perexposure percandidate,288measurements total',palette='two roots blue and orange plus neutral, hatch distinguishes failures',caveat='SEM definition sensitivity is not calibrated physical truth; outer20objects include Raw retention; all failures retained')
    save(OUT/'chart_contract.json',contract)
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei'
    labels=['第一組','第二組','第三組','第四組'];fig,axes=plt.subplots(1,2,figsize=(11,4.5),sharex=True)
    for ax,exp,title in zip(axes,[13,24],['一般亮度：36個物件','暗照片：36個物件']):
        start=np.zeros(4)
        for direction,color,hatch,label in [('improves','#356DA8',None,'比原圖改善'),('worsens','#D38638',None,'比原圖退步'),('unmeasurable','#D8D8D8','///','無法依固定位置量測')]:
            values=[int(((joined.run==x['run'])&(joined.exposure==exp)&(joined.direction==direction)).sum()) for x in summary]
            ax.barh(np.arange(4),values,left=start,color=color,hatch=hatch,label=label,height=.6,edgecolor='#333333',linewidth=.6)
            for y,(left,value) in enumerate(zip(start,values)):
                if value:ax.text(left+value/2,y,str(value),ha='center',va='center',color='white' if direction!='unmeasurable' else '#222222',fontsize=11)
            start+=values
        ax.set_yticks(range(4),labels);ax.invert_yaxis();ax.set_xlim(0,36);ax.set_xticks([0,12,24,36]);ax.set_xlabel('物件數');ax.set_title(title,fontsize=13);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('R128 最後模型的 SEM 尺寸比對',fontsize=16,y=.99)
    handles,names=axes[0].get_legend_handles_labels();fig.legend(handles,names,loc='lower center',ncol=3,bbox_to_anchor=(.5,.055),frameon=False)
    fig.text(.5,.012,'固定第8,192次結果；內外取邊範圍皆同方向才列改善／退步。尚非真實材料邊界精度認證。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.16,1,.91]);fig.savefig(figdir/'final_SEM_comparison.png',dpi=160);plt.close(fig)
    # Same predetermined central location, identical display scale within row.
    with np.load(R127/'results/sem_native_v2/native_references.npz') as f:center=f['optical_centers'].reshape(6,6,2)[2,2]
    x,y=np.rint(center).astype(int);half=58
    fig,axes=plt.subplots(2,5,figsize=(12,5.8))
    for row,exp in enumerate([13,24]):
        source=next(x['source'] for x in panel['full_images'] if x['name']==f'sem_optical_exposure{exp}');raw=read_image(source);images=[raw]
        for s in summary:
            with np.load(ROOT/'runs'/s['run']/f'evaluations/real_step8192/full_images/sem_optical_exposure{exp}/output_float.npz') as f:images.append(f['output'])
        for col,im in enumerate(images):
            axes[row,col].imshow(im[y-half:y+half,x-half:x+half],cmap='gray',vmin=0,vmax=1 if exp==13 else 64/255,interpolation='nearest');axes[row,col].set_xticks([]);axes[row,col].set_yticks([])
            if row==0:axes[row,col].set_title(['原圖',*labels][col],fontsize=12)
        axes[row,0].set_ylabel('一般亮度' if exp==13 else '暗照片',fontsize=12)
    fig.suptitle('同一個實拍物件的修復結果',fontsize=16)
    fig.text(.5,.02,'位置固定為原圖第3列第3行；每列顯示範圍相同。暗照片顯示放大至0–64灰階，僅供觀察。',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.05,1,.92]);fig.savefig(figdir/'final_real_object_comparison.png',dpi=160);plt.close(fig)
    print(json.dumps(dict(verification=self_check,selection=selection)),flush=True)

if __name__=='__main__':main()

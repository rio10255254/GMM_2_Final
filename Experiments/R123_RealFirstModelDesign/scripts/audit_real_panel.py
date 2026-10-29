"""Inventory real files and re-evaluate existing paired real results, read-only.

No neural model is instantiated. Only R123 output files are written.
"""
import hashlib,json,pathlib
import cv2,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
E=pathlib.Path(__file__).resolve().parents[1]
OLD=E.parent/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907'
fingerprints={}
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def protect(p):
    p=pathlib.Path(p);fingerprints[str(p)]=sha(p);return p
def image_read(p):
    v=cv2.imdecode(np.fromfile(p,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
    if v is None:raise ValueError(f'Unreadable real image {p}')
    return v
def main():
    catalog=json.loads((E/'config/real_sources.json').read_text(encoding='utf-8'))
    records=[];groups=[]
    for source in catalog['sources']:
        if source.get('alias_of'):continue
        root=pathlib.Path(PROJECT_ROOT / source['path'])
        if source.get('subdirectories'):
            files=[]
            for sub,n in source['subdirectories'].items():
                batch=sorted((root/sub).glob('*.bmp'));assert len(batch)==n,(sub,len(batch));files+=batch
        elif source.get('explicit_names'):files=[root/name for name in source['explicit_names']]
        else:files=sorted(root.glob('*.bmp'))
        assert len(files)==source['expected_images'],(source['id'],len(files))
        for p in files:
            protect(p);im=image_read(p)
            records.append({'source_id':source['id'],'file':str(p),'sha256':fingerprints[str(p)],'height':im.shape[0],'width':im.shape[1],'min_gray':int(im.min()),'max_gray':int(im.max()),'p01_gray':float(np.percentile(im,1)),'p99_gray':float(np.percentile(im,99)),'fraction_at_0':float(np.mean(im==0)),'fraction_at_255':float(np.mean(im==255)),'training_allowed':False})
        groups.append({'source_id':source['id'],'images':len(files),'role':source['role'],'independence':'reused or unqualified; folder count is not sample count'})
    pd.DataFrame(records).to_csv(E/'results/real_source_inventory.csv',index=False)
    # Recompute from actual paired rows, not a copied report headline.
    acm=pd.read_csv(protect(OLD/'acm_measurements.csv'));profiles=pd.read_csv(protect(OLD/'profile_measurements.csv'))
    all_pillars=[];all_exposures=[];summaries=[]
    for reference in ['historical','global_pitch_matched']:
        a=acm[(acm.reference==reference)&acm.method.isin(['Raw','R109_full','R119_full'])]
        assert len(a)==1296 and a.valid.eq(1).all()
        wide=a.pivot(index=['pillar','exposure'],columns='method',values='common_boundary')
        h=profiles[(profiles.reference==reference)&profiles.readout.eq('half')&profiles.method.isin(['Raw','R109_full','R119_full'])]
        assert len(h)==1296
        widths=h.pivot(index=['pillar','exposure'],columns='method',values='main_common_mae_px')
        coverage=h.pivot(index=['pillar','exposure'],columns='method',values='main_common_profiles')
        assert np.all(coverage.to_numpy()>=648), 'Historical half readout population changed'
        for method in ['R109_full','R119_full']:
            c=wide[method]-wide['Raw'];m=widths[method]-widths['Raw']
            per=pd.DataFrame({'acm_change_pp':c,'half_change_px':m}).groupby(level='pillar').median()
            ex=pd.DataFrame({'acm_change_pp':c,'half_change_px':m}).groupby(level='exposure').median()
            for pid,row in per.iterrows():all_pillars.append({'reference':reference,'method':method,'pillar':int(pid),**row.to_dict()})
            for exp,row in ex.iterrows():all_exposures.append({'reference':reference,'method':method,'exposure':int(exp),**row.to_dict()})
            cm=float(per.acm_change_pp.median());hm=float(per.half_change_px.median())
            if cm<0 and hm<0:decision='concordant_observed_improvement_but_mapping_and_guards_still_required'
            elif cm>=0 and hm>=0:decision='observed_real_geometry_regression'
            else:decision='readout_correspondence_unresolved_no_physical_success_claim'
            summaries.append({'reference':reference,'method':method,'observations':len(c),'pillars':len(per),'exposures':len(ex),'independent_sample_count':1,'median_pillar_acm_change_pp':cm,'median_pillar_half_change_px':hm,'acm_improved_pillars':int((per.acm_change_pp<0).sum()),'half_improved_pillars':int((per.half_change_px<0).sum()),'decision':decision})
    pd.DataFrame(all_pillars).to_csv(E/'results/historical_real_paired_pillars.csv',index=False)
    pd.DataFrame(all_exposures).to_csv(E/'results/historical_real_paired_exposures.csv',index=False)
    p=pd.DataFrame(all_pillars);p=p[p.reference.eq('global_pitch_matched')]
    fig,ax=plt.subplots(1,2,figsize=(10.8,3.7),layout='constrained')
    for method,color in [('R109_full','C0'),('R119_full','C1')]:
        sub=p[p.method.eq(method)].sort_values('pillar');ax[0].plot(sub.pillar,sub.acm_change_pp,'.-',color=color,label=method);ax[1].plot(sub.pillar,sub.half_change_px,'.-',color=color,label=method)
    for a in ax:a.axhline(0,color='black',lw=1);a.set_xlabel('Pillar (one reused sample; 12 exposures per pillar)');a.legend(fontsize=8)
    ax[0].set(ylabel='Change vs Raw (% pitch points)',title='SEM contour readout; lower is better')
    ax[1].set(ylabel='Change vs Raw (pixels)',title='Half-contrast readout; lower is better')
    fig.suptitle('Existing real results expose a readout conflict; no new model results',fontsize=12)
    fig.savefig(E/'results/real_baseline_replay.png',dpi=160);plt.close(fig)
    # View representative real challenges without synthesizing a proposed output.
    sem=pathlib.Path(PROJECT_ROOT / catalog['sources'][0]['path'])/'13.bmp'
    full=pathlib.Path(next(str(PROJECT_ROOT / s['path']) for s in catalog['sources'] if s['id']=='real_six_motion_suites'))/'5x_0p5um/frame_0000.bmp'
    check=pathlib.Path(next(r['file'] for r in records if r['source_id']=='real_checkerboard'))
    fig,ax=plt.subplots(1,3,figsize=(12,4.2),layout='constrained')
    for a,p,title in zip(ax,[sem,full,check],['SEM-linked optical sample','Real lines, dots, gaps and defects','Real checkerboard corners']):a.imshow(image_read(p),cmap='gray',vmin=0,vmax=255);a.set_title(title,fontsize=11);a.axis('off')
    fig.suptitle('Real inputs used to judge usefulness; these are not new model outputs',fontsize=12);fig.savefig(E/'results/real_input_panel.png',dpi=160);plt.close(fig)
    summary={'source_groups':groups,'physical_image_files_read':len(records),'aliases_not_double_counted':['real_nonpillar_full_fields'],'primary_reused_development_unique_files':12+301+51,'historical_real_results':summaries,'no_new_model_inference':True,'no_training':True,'no_confirmation_payload_access':True,'limitations':['Sample independence is not established by folder names.','SEM optical-to-material readout correspondence is not fully calibrated.','Real nonpillar detail and actual stage motion lack independent truth in this inventory.','Pixel-level source statistics do not establish camera saturation; rail fractions are only raw diagnostics.']}
    (E/'results/real_panel_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(E/'results/protected_inputs.json').write_text(json.dumps(fingerprints,indent=2),encoding='utf-8')
    print(json.dumps({'files':len(records),'primary_real_development_files':364,'historical_real_results':summaries},indent=2))
if __name__=='__main__':main()

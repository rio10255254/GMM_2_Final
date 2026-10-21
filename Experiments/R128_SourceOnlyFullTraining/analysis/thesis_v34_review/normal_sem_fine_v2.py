"""Use the thesis's refined SEM contour metrics on the fixed normal-exposure trio."""
import sys,ast,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from scipy.io import loadmat

def main():
    out=ROOT/'results/thesis_v34_review_20260912/normal_sem_fine_v2';assert (out/'input_cells.mat').is_file();assert not (out/'plan.json').exists()
    r80=ROOT.parent/'R80_InflectionReferenceCircleSEMValidation';src=r80/'scripts/run_sem36_contour_validation.py'
    sys.path.insert(0,str(r80/'scripts'));import reference_circle_core as core
    oldpath=ROOT.parent/'R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat';newpath=ROOT/'results/full_contour/masks.mat';tablepath=r80/'results/tables/sem36_per_exposure_reference_circles.csv'
    sources=[record(x) for x in [oldpath,newpath,tablepath,src,r80/'scripts/reference_circle_core.py',Path(__file__),out/'input_cells.mat',Path(__file__).with_name('prepare_normal_sem_cells.m'),ROOT.parent/'R69_ACMContourSEMValidation/scripts/run_acm_extraction.m']]
    save(out/'plan.json',dict(created_utc=now(),sources=sources,population='same36pillars xfixednormalimages13/14/15; one repeated specimen,not full12exposure thesisclaim',methods=['Raw','MOSR_V42','R128'],
        reference='ExacthistoricalR70SEMimages/masks andpitchscale usedin v34; notnewlyfittedtomodel.',
        reader='UnchangedR80maxgradientrefinement:180SEM/144opticalpoints,3pxnormalhalfwidth,automaticpolarity,720angularradialsignatureaboutownLSCcenter;LSC/MZC/MIC/MCCsamefunctions.',
        primary=['radial_shape_mae_nm','contour_correlation','lsc_abs_error_nm','mzc_roundness_abs_error_nm'],
        controls='Exacthistoricalim2uint8(mat2gray(cell))restored afterthe retainedinitialRawrepresentationmismatch; no candidate scores existedbeforethisrepair. Raw/V42existingnormal-exposure rows mustreproduce. R128normalPNGusespreviousfrozenACMmasks andimagecells,notretunedsegmentation.',no_new_training=True,no_confirmation_access=True))
    old=loadmat(oldpath,variable_names=['exposures','opt_pitch','truth_cells','truth_masks','raw_cells','raw_masks','recon_cells','recon_masks','global_index'])
    new=loadmat(newpath,variable_names=['cells','masks','truth_masks','opt_pitch','global_index'])
    assert np.array_equal(old['truth_masks'],new['truth_masks'][:,:,:,0]) and np.array_equal(old['raw_masks'][:,:,:,:3],new['masks'][:,:,:,:,0,0])
    normalized=loadmat(out/'input_cells.mat');raw_new=normalized['raw_cells']
    assert np.array_equal(raw_new,old['raw_cells'][:,:,:,:3])
    r128_cells=normalized['r128_cells'];r128_masks=new['masks'][:,:,:,:,1,0]
    scope=dict(np=np)
    tree=ast.parse(src.read_text(encoding='utf-8'));wanted={'mask_center_radius','radial_signature'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted];assert len(nodes)==2
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src),'exec'),scope)
    scale=5/float(old['opt_pitch'].item());truth={};rows=[];points={};start=time.perf_counter()
    for i in range(36):
        mask=old['truth_masks'][:,:,i].astype(bool);center,radius=scope['mask_center_radius'](mask)
        t=core.measure_boundary_and_circles(old['truth_cells'][:,:,i],center,radius,coarse_mask=mask,sample_count=180,normal_half_width_px=3.,polarity='auto')
        truth[i]=t;points[f'SEM_{i+1}']=t.inflection_points_xy
    for method,cells,masks in [('Raw',old['raw_cells'][:,:,:,:3],old['raw_masks'][:,:,:,:3]),('MOSR_V42',old['recon_cells'][:,:,:,:3],old['recon_masks'][:,:,:,:3]),('R128',r128_cells,r128_masks)]:
        for e in range(3):
            for i in range(36):
                mask=masks[:,:,i,e].astype(bool);center,radius=scope['mask_center_radius'](mask)
                m=core.measure_boundary_and_circles(cells[:,:,i,e],center,radius,coarse_mask=mask,sample_count=144,normal_half_width_px=3.,polarity='auto');t=truth[i]
                a=scope['radial_signature'](m);b=scope['radial_signature'](t)
                values=dict(radial_shape_mae_nm=float(np.mean(np.abs(a-b))*scale*1000),contour_correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),lsc_abs_error_nm=float(abs(m.circles.lsc.radius-t.circles.lsc.radius)*2*scale*1000),mzc_roundness_abs_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale*1000),measured_mzc_nm=float(m.circles.mzc_zone_width*scale*1000),SEM_mzc_nm=float(t.circles.mzc_zone_width*scale*1000))
                assert np.isfinite(list(values.values())).all()
                rows.append(dict(method=method,exposure=e+13,pillar_id=i+1,**values));points[f'{method}_{e+13}_{i+1}']=m.inflection_points_xy
            print(json.dumps(dict(method=method,exposure=e+13,rows=len(rows),seconds=round(time.perf_counter()-start,1))),flush=True)
    table=pd.DataFrame(rows);assert len(table)==324
    with (out/'per_measurement.csv').open('x',encoding='utf-8',newline='') as f:table.to_csv(f,index=False)
    np.savez_compressed(out/'boundary_points.npz',**points)
    previous=pd.read_csv(tablepath);previous=previous[previous.exposure.isin([13,14,15])].copy();previous['method']=previous.method.replace({'MOSR':'MOSR_V42'})
    matched=table.merge(previous,on=['method','exposure','pillar_id'],suffixes=('','_old'),validate='one_to_one');assert len(matched)==216
    metrics=['radial_shape_mae_nm','contour_correlation','lsc_abs_error_nm','mzc_roundness_abs_error_nm'];errors={k:float((matched[k]-matched[k+'_old']).abs().max()) for k in metrics};assert max(errors.values())<1e-6,errors
    per_pillar=table.groupby(['method','pillar_id'],as_index=False)[metrics].median();summary=per_pillar.groupby('method',as_index=False)[metrics].median();per_pillar.to_csv(out/'per_pillar.csv',index=False);summary.to_csv(out/'summary.csv',index=False)
    counts=[]
    a=per_pillar[per_pillar.method=='R128'].set_index('pillar_id')
    for method in ['Raw','MOSR_V42']:
        b=per_pillar[per_pillar.method==method].set_index('pillar_id')
        for metric in metrics:
            change=(a[metric]-b[metric])*(1 if metric=='contour_correlation' else -1)
            counts.append(dict(baseline=method,metric=metric,improved=int((change>1e-7).sum()),worsened=int((change< -1e-7).sum()),tied=int((change.abs()<=1e-7).sum()),median_paired_improvement=float(change.median())))
    pd.DataFrame(counts).to_csv(out/'paired_counts.csv',index=False)
    assert all(sha(s['path'])==s['sha256'] for s in sources)
    save(out/'verification.json',dict(completed_utc=now(),rows=324,all36objects_preserved=True,all_raw_cells_and_masks_match=True,SEM_reference_matches=True,Raw_V42_parity_max=errors,source_files_unchanged=True,full12exposure_claim=False,new_training_updates=0,summary=record(out/'summary.csv'),source=record(__file__)))
    print(summary.to_string(index=False),flush=True);print(pd.DataFrame(counts).to_string(index=False),flush=True)
if __name__=='__main__':main()

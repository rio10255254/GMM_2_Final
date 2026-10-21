from common133 import *
from analyze import circle,signature

def main():
    verify();assert load(ROOT/'results/inference_complete.json')['weights_unchanged'];real=ROOT/'results/real';t=pd.read_csv(real/'measurements.csv');assert len(t)==972 and t.valid.all()
    p=np.load(real/'points.npz');scale=load(real/'complete.json')['scale_nm_per_px'];truth={i:circle(p[f'SEM_{i}']) for i in range(1,37)};errors=[]
    for row in t.itertuples():
        xy=p[f'{row.arm}_{row.exposure}_{row.pillar}'];c,r=circle(xy);tc,tr=truth[row.pillar];a,b=signature(xy,c),signature(p[f'SEM_{row.pillar}'],tc)
        vals=dict(radial_nm=float(abs(a-b).mean()*scale),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),diameter_error_nm=float(2*abs(r-tr)*scale),signed_diameter_nm=float(2*(r-tr)*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]))
        e=max(abs(v-getattr(row,k)) for k,v in vals.items());assert e<1e-4;errors.append(dict(arm=row.arm,exposure=row.exposure,pillar=row.pillar,max_difference=e))
    pd.DataFrame(errors).to_csv(real/'independent_refits.csv',index=False)
    cdir=ROOT/'results/controls';ct=pd.read_csv(cdir/'measurements.csv');cp=np.load(cdir/'points.npz');assert len(ct)==640;ce=[]
    for row in ct.itertuples():
        c,r=circle(cp[f'{row.id}_{row.arm}']);e=max(abs(c[0]-row.cx),abs(c[1]-row.cy),abs(r-row.fitted_radius));assert e<1e-4;ce.append(dict(id=row.id,arm=row.arm,error_px=e))
    pd.DataFrame(ce).to_csv(cdir/'independent_refits.csv',index=False)
    # Recompute all generated metrics from saved arrays; images and targets are
    # identical across arms, image-scale errors are not geometry certificates.
    gt=pd.read_csv(ROOT/'results/generated/metrics.csv');checks=0;mx=0.
    for index in range(128):
        d=np.load(ROOT/f'results/generated/parent_{index:03d}.npz')
        for arm in ARMS:
            for view in [0,1]:
                r=d[arm][view]-d['target'][view];mae=float(abs(r).mean()*255);ge=float((abs(np.diff(r,-1 if False else 1,axis=-1)).mean()+abs(np.diff(r,axis=-2)).mean())*127.5)
                row=gt[(gt.parent==index)&(gt.arm==arm)&(gt.view==view)].iloc[0];e=max(abs(mae-row.mae_gray),abs(ge-row.gradient_error_gray));mx=max(mx,e);assert e<1e-5;checks+=1
    gt.groupby('arm')[['mae_gray','gradient_error_gray']].mean().to_csv(ROOT/'results/generated/summary.csv');gt.groupby(['category','arm'])[['mae_gray','gradient_error_gray']].mean().to_csv(ROOT/'results/generated/by_category.csv')
    ct['abs_diameter_bias_px']=abs(ct.diameter_bias_px);ct['abs_error_vs_target_reader_px']=abs(ct.diameter_change_vs_clean_readout_px)
    ct.groupby('arm')[['diameter_bias_px','abs_diameter_bias_px','abs_error_vs_target_reader_px','center_error_px']].agg(['median','max','min']).to_csv(cdir/'summary.csv')
    pvt=ct.pivot(index='id',columns='arm',values='diameter_bias_px');info=ct[ct.arm=='Final'].set_index('id')[['sigma','radius','polarity','contrast']];by=info.join(pvt);by['Final_minus_Raw']=by.Final-by.Raw;by.reset_index().to_csv(cdir/'paired_by_case.csv',index=False)
    pairs=[];byreal=pd.read_csv(real/'per_pillar.csv')
    for a,b in [('Optics','Raw'),('Neural','Optics'),('Final','Neural'),('Final','Raw'),('NoOptics','Final'),('ResidualHP','Final'),('ResidualHP','MatchedHP'),('DirectResidual','Final'),('DirectResidual','MatchedDirect')]:
        aa=byreal[byreal.arm==a].set_index('pillar');bb=byreal[byreal.arm==b].set_index('pillar')
        for key in ['diameter_error_nm','centered_shape_nm','correlation','radial_nm']:
            delta=aa[key]-bb[key];gain=delta if key=='correlation' else -delta;pairs.append(dict(candidate=a,reference=b,metric=key,median_change=float(delta.median()),improved=int((gain>1e-7).sum()),worsened=int((gain< -1e-7).sum()),tied=int((abs(gain)<=1e-7).sum())))
    pd.DataFrame(pairs).to_csv(real/'paired_effects.csv',index=False)
    conv=pd.read_csv(cdir/'render_convergence.csv');assert len(conv)==8
    save(ROOT/'results/audit_complete.json',dict(utc=now(),real_SEM_refits=len(errors),max_SEM_metric_difference=max(r['max_difference'] for r in errors),controlled_refits=len(ce),max_control_refit_difference=max(r['error_px'] for r in ce),generated_metric_recomputations=checks,max_generated_metric_difference=mx,max_8_to16_diameter_change_px=float(abs(conv.diameter_readout_16_minus8_px).max()),reader_target_bias_range=[float(pvt.Target.min()),float(pvt.Target.max())],controls_improved_vs_Raw=int((abs(pvt.Final)<abs(pvt.Raw)).sum()),controls_worsened_vs_Raw=int((abs(pvt.Final)>abs(pvt.Raw)).sum()),old_sources_preserved=True,MZC_shared_not_independently_reimplemented=True))
    print('R133 independent audits passed',flush=True)
if __name__=='__main__':main()

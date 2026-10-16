"""Independent saved-point fits, arithmetic, preserved-source and edge-impact checks."""
from common132 import *
from analyze import circle,signature
import traceback

def main():
    for w in WIDTHS:wait(ROOT/f'results/measurements/W{w}/complete.json')
    wait(ROOT/'results/all_sem/complete.json');verify()
    sem=ROOT/'results/all_sem';t=pd.read_csv(sem/'measurements.csv');p=np.load(sem/'points.npz');scale=load(sem/'complete.json')['scale_nm_per_px'];truth={i:circle(p[f'SEM_{i}']) for i in range(1,37)};errors=[]
    for row in t.itertuples():
        if not row.valid:continue
        xy=p[f'{row.case}_{row.pillar}'];c,r=circle(xy);tc,tr=truth[row.pillar];a,b=signature(xy,c),signature(p[f'SEM_{row.pillar}'],tc)
        derived=dict(radial_nm=float(abs(a-b).mean()*scale),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),diameter_error_nm=float(2*abs(r-tr)*scale),signed_diameter_nm=float(2*(r-tr)*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]))
        e=max(abs(v-getattr(row,k)) for k,v in derived.items());assert e<1e-4;errors.append(dict(case=row.case,pillar=row.pillar,max_metric_difference=e))
    pd.DataFrame(errors).to_csv(sem/'independent_refits.csv',index=False)
    by=pd.read_csv(sem/'per_pillar.csv');effects=[]
    for w in [64,32,16,0]:
        for population,ids in [('all36',by.pillar.unique()),('inner16',by[by.region=='inner16'].pillar.unique()),('outer20',by[by.region=='outer20'].pillar.unique())]:
            a=by[(by.width==w)&by.pillar.isin(ids)].set_index('pillar');b=by[(by.width==80)&by.pillar.isin(ids)].set_index('pillar')
            for k in ['radial_nm','diameter_error_nm','centered_shape_nm','correlation','MZC_error_nm']:
                delta=a[k]-b[k];gain=delta if k=='correlation' else -delta
                effects.append(dict(width=w,reference=80,population=population,metric=k,median_change=float(delta.median()),improved=int((gain>1e-7).sum()),worsened=int((gain< -1e-7).sum()),tied=int((abs(gain)<=1e-7).sum())))
    pd.DataFrame(effects).to_csv(sem/'paired_effects.csv',index=False)
    full=t[t.scope=='full'].copy();baseline=full[full.width==0][['exposure','pillar','radial_nm','diameter_error_nm','centered_shape_nm']]
    context=t[t.scope=='crop'].merge(baseline,on=['exposure','pillar'],suffixes=('','_full_W0'),validate='many_to_one')
    for k in ['radial_nm','diameter_error_nm','centered_shape_nm']:context[k+'_minus_full_W0']=context[k]-context[k+'_full_W0']
    context.to_csv(sem/'context_vs_full.csv',index=False)
    cfg=load(PLAN['configuration']['path']);summary=[];refits=[];pairdict={};centerdict={};worst=[]
    for w in WIDTHS:
        folder=ROOT/f'results/measurements/W{w}';ct=pd.read_csv(folder/'centers.csv');assert len(ct)==1809;centerdict[w]=ct
        for f in PLAN['frames']:
            case=f"{f['sequence']}/frame_{f['frame_index']:04d}";ft=pd.read_csv(folder/case/'centers.csv');points=np.load(folder/case/'boundaries.npz')['inflection_points']
            source=load(ROOT/'results/records'/(case+'.json'));output=next(r for r in source['outputs'] if r['width']==w);assert sha(output['path'])==output['sha256']
            for xy,row in zip(points,ft.itertuples()):
                c,r=circle(xy);e=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px),abs(r-row.lsc_radius_px));assert e<1e-4;refits.append(dict(width=w,sequence=f['sequence'],frame=f['frame_index'],pillar=row.pillar_id,max_difference_px=e))
        idx=ct.set_index(['sequence','frame_index','pillar_id'])
        for pop,count in [('locked120',120),('within_session194',194),('repositioning3',3)]:
            pp=pd.read_csv(folder/(pop+'_pairs.csv'));assert len(pp)==count;pairdict[w,pop]=pp
            for row in pp.itertuples():
                spec=cfg['sequences'][row.sequence];ids=[int(x[0]) for x in spec['centers']]
                a=idx.loc[[(row.sequence,row.start_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy();b=idx.loc[[(row.sequence,row.end_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy();v=(b-a)*spec['object_um_per_px'];dx,dy=np.median(v,0)
                vals=[abs(dx),abs(abs(dx)-spec['nominal_step_um'])*1000,np.std(v[:,0],ddof=1)*1000,abs(dy)*1000];expected=[row.measured_step_um,row.nominal_abs_error_nm,row.within_grid_sd_nm,row.cross_axis_abs_nm];assert max(abs(a-b) for a,b in zip(vals,expected))<1e-7
            if pop!='repositioning3':
                ss=pd.read_csv(folder/(pop+'_summary.csv'))
                for row in ss.itertuples():
                    g=pp if row.scope=='all_four_sequences' else pp[pp.sequence==row.sequence]
                    sd=float(np.mean([sg.measured_step_um.std(ddof=1)*1000 for _,sg in g.groupby('sequence')])) if row.scope=='all_four_sequences' else float(g.measured_step_um.std(ddof=1)*1000)
                    assert abs(sd-row.step_sd_nm)<1e-8
                    assert abs(g.nominal_abs_error_nm.mean()-row.mean_nominal_abs_error_nm)<1e-8
                    assert abs(g.within_grid_sd_nm.median()-row.median_within_grid_sd_nm)<1e-8
                ss['width']=w;ss['population']=pop;summary.append(ss)
                worst.append(dict(width=w,population=pop,max_nominal_error_nm=float(pp.nominal_abs_error_nm.max()),max_cross_axis_nm=float(pp.cross_axis_abs_nm.max())))
    pd.concat(summary).to_csv(ROOT/'results/motion_summary.csv',index=False);pd.DataFrame(refits).to_csv(ROOT/'results/motion_refits.csv',index=False);pd.DataFrame(worst).to_csv(ROOT/'results/motion_worst.csv',index=False)
    effects=[]
    for w in [64,32,16,0]:
        for pop in ['locked120','within_session194']:
            j=pairdict[w,pop].merge(pairdict[80,pop],on=['sequence','start_frame_index','end_frame_index'],suffixes=('','_W80'),validate='one_to_one')
            for key in ['nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm']:
                delta=j[key]-j[key+'_W80'];effects.append(dict(width=w,population=pop,metric=key,median_change=float(delta.median()),improved=int((delta< -1e-7).sum()),worsened=int((delta>1e-7).sum()),tied=int((abs(delta)<=1e-7).sum()),largest_regression=float(delta.max())))
    pd.DataFrame(effects).to_csv(ROOT/'results/motion_paired_effects.csv',index=False)
    flags=pd.read_csv(OLD/'source_boundary_context.csv');impact=[]
    for w in [64,32,16,0]:
        j=centerdict[w].merge(centerdict[80],on=['sequence','frame_index','pillar_id'],suffixes=('','_W80'),validate='one_to_one').merge(flags,on=['sequence','frame_index','pillar_id'],validate='one_to_one')
        j['center_change_px']=np.hypot(j.lsc_center_x_px-j.lsc_center_x_px_W80,j.lsc_center_y_px-j.lsc_center_y_px_W80)
        for group,g in [('whole',j),('window_beyond96',j[j.minimum_window_FOV_distance>=96]),('window_inside96',j[j.minimum_window_FOV_distance<96])]:
            if group=='window_beyond96':assert g.center_change_px.max()<1e-7
            impact.append(dict(width=w,population=group,rows=len(g),median_center_change_px=float(g.center_change_px.median()),max_center_change_px=float(g.center_change_px.max())))
    pd.DataFrame(impact).to_csv(ROOT/'results/motion_edge_impact.csv',index=False)
    verify();save(ROOT/'results/audit_complete.json',dict(utc=now(),sem_rows=len(t),invalid_sem_rows=int((~t.valid).sum()),independent_SEM_refits=len(errors),max_SEM_metric_difference=max(r['max_metric_difference'] for r in errors),independent_LSC_refits=len(refits),max_LSC_difference_px=max(r['max_difference_px'] for r in refits),pair_arithmetic_checks=1585,old_sources_preserved=True,MZC_shared_not_independently_reimplemented=True))
    print('R132 independent audit complete',flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        save(ROOT/f'results/failure_audit_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise

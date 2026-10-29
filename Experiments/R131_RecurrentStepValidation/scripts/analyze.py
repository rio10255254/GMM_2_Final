"""Independent numeric review plus paired stage effects; no selection by score."""
from study import *
from scipy.optimize import least_squares
import argparse,traceback
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def circle(xy):
    center0=xy.mean(0);z=xy-center0
    def residual(c):
        r=np.linalg.norm(z-c,axis=1);return r-r.mean()
    fit=least_squares(residual,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12)
    return fit.x+center0,np.linalg.norm(z-fit.x,axis=1).mean()

def signature(xy,c):
    z=xy-c;a=np.mod(np.arctan2(z[:,1],z[:,0]),2*np.pi);r=np.linalg.norm(z,axis=1);order=np.argsort(a);a=a[order];r=r[order]
    return np.interp(np.linspace(0,2*np.pi,720,endpoint=False),np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]])

def sem_audit():
    out=ROOT/'results/sem';complete=load(out/'complete.json');t=pd.read_csv(out/'measurements.csv');p=np.load(out/'points.npz');scale=complete['scale_nm_per_px'];errs=[]
    truth={i:circle(p[f'SEM_{i}']) for i in range(1,37)}
    for row in t.itertuples():
        xy=p[f'N{row.step}_{row.exposure}_{row.pillar}'];c,r=circle(xy);tc,tr=truth[row.pillar]
        a,b=signature(xy,c),signature(p[f'SEM_{row.pillar}'],tc)
        val=dict(radial_nm=float(abs(a-b).mean()*scale),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),diameter_error_nm=float(2*abs(r-tr)*scale),signed_diameter_nm=float(2*(r-tr)*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]))
        errors={k:abs(v-getattr(row,k)) for k,v in val.items()};err=max(errors.values());assert err<1e-4,(row.step,row.pillar,errors)
        errs.append(dict(step=row.step,exposure=row.exposure,pillar=row.pillar,max_metric_difference=err,center_radius_max_difference_px=float(max(abs(c[0]-row.cx),abs(c[1]-row.cy),abs(r-row.radius)))))
    pd.DataFrame(errs).to_csv(out/'independent_refits.csv',index=False)
    by=pd.read_csv(out/'per_pillar.csv');paired=[]
    for a,b in [(1,0),(2,1),(3,2),(4,3),(4,1),(4,2),(4,0)]:
        x=by[by.step==a].set_index('pillar');y=by[by.step==b].set_index('pillar')
        for key in ['radial_nm','diameter_error_nm','centered_shape_nm','MZC_error_nm','correlation']:
            d=x[key]-y[key];improve=-d if key!='correlation' else d
            paired.append(dict(candidate=a,reference=b,metric=key,median_candidate_minus_reference=float(d.median()),improved=int((improve>1e-7).sum()),worsened=int((improve< -1e-7).sum()),tied=int((abs(improve)<=1e-7).sum()),worst_candidate_minus_reference=float((d if key!='correlation' else -d).max())))
    pd.DataFrame(paired).to_csv(out/'paired_changes.csv',index=False)
    save(out/'independent_verified.json',dict(rows=len(t),max_metric_difference=max(x['max_metric_difference'] for x in errs),MZC_independently_reimplemented=False,paired_rows=len(paired),scope='Same SEM definitions and saved boundary points; not new physical reference qualification'))
    print('SEM independent checks',len(t),'passed',flush=True)

def final_audit():
    for n in range(5):assert load(ROOT/f'results/measurements/N{n}/complete.json')['frames']==201
    assert load(ROOT/'results/inference_complete.json')['four_step_old_PNG_parity_frames']==201
    verify_sources();start=load(ROOT/'results/inference_started.json');assert start['source']==rec(ROOT/'scripts/study.py')
    cfg=load(str(PROJECT_ROOT / PLAN['configuration']['path']));allsummary=[];refits=[];pairs_by={};changes=[];worst=[]
    for n in range(5):
        folder=ROOT/f'results/measurements/N{n}';t=pd.read_csv(folder/'centers.csv');assert len(t)==1809
        for f in PLAN['frames']:
            case=f"{f['sequence']}/frame_{f['frame_index']:04d}";saved=load(ROOT/'results/records'/(case+'.json'))
            for r in saved['images']:assert sha(r['path'])==r['sha256']
            ft=pd.read_csv(folder/case/'centers.csv');points=np.load(folder/case/'boundaries.npz')['inflection_points']
            for xy,row in zip(points,ft.itertuples()):
                c,r=circle(xy);err=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px),abs(r-row.lsc_radius_px));assert err<1e-4
                refits.append(dict(step=n,sequence=f['sequence'],frame=f['frame_index'],pillar=row.pillar_id,max_difference_px=err))
        indexed=t.set_index(['sequence','frame_index','pillar_id'])
        for pop,count in [('locked120',120),('within_session194',194),('repositioning3',3)]:
            pairs=pd.read_csv(folder/(pop+'_pairs.csv'));assert len(pairs)==count;pairs_by[n,pop]=pairs
            for row in pairs.itertuples():
                s=cfg['sequences'][row.sequence];ids=[int(i[0]) for i in s['centers']]
                a=indexed.loc[[(row.sequence,row.start_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy();b=indexed.loc[[(row.sequence,row.end_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy()
                v=(b-a)*s['object_um_per_px'];dx,dy=np.median(v,0)
                actual=[abs(dx),abs(abs(dx)-s['nominal_step_um'])*1000,np.std(v[:,0],ddof=1)*1000,abs(dy)*1000]
                expected=[row.measured_step_um,row.nominal_abs_error_nm,row.within_grid_sd_nm,row.cross_axis_abs_nm]
                assert max(abs(x-y) for x,y in zip(actual,expected))<1e-7
            if pop!='repositioning3':
                summ=pd.read_csv(folder/(pop+'_summary.csv'))
                for sr in summ.itertuples():
                    g=pairs if sr.scope=='all_four_sequences' else pairs[pairs.sequence==sr.sequence]
                    spread=float(np.mean([np.std(sg.measured_step_um,ddof=1)*1000 for _,sg in g.groupby('sequence')])) if sr.scope=='all_four_sequences' else float(np.std(g.measured_step_um,ddof=1)*1000)
                    assert abs(spread-sr.step_sd_nm)<1e-8
                    assert abs(float(np.mean(g.nominal_abs_error_nm))-sr.mean_nominal_abs_error_nm)<1e-8
                    assert abs(float(np.median(g.within_grid_sd_nm))-sr.median_within_grid_sd_nm)<1e-8
                    assert abs(float(np.median(g.cross_axis_abs_nm))-sr.median_cross_axis_abs_nm)<1e-8
                summ['step']=n;summ['population']=pop;allsummary.append(summ)
                for seq,g in pairs.groupby('sequence'):
                    worst.append(dict(step=n,population=pop,sequence=seq,max_nominal_error_nm=float(g.nominal_abs_error_nm.max()),p95_nominal_error_nm=float(g.nominal_abs_error_nm.quantile(.95)),max_cross_axis_nm=float(g.cross_axis_abs_nm.max()),wrong_direction_count=int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][seq]['expected_signed_dx_px'])).sum())))
    for pop in ['locked120','within_session194']:
        for a,b in [(1,0),(2,1),(3,2),(4,3),(4,1),(4,2),(4,0)]:
            joint=pairs_by[a,pop].merge(pairs_by[b,pop],on=['sequence','start_frame_index','end_frame_index'],suffixes=('_a','_b'),validate='one_to_one')
            for metric in ['nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm']:
                d=joint[metric+'_a']-joint[metric+'_b'];changes.append(dict(population=pop,candidate=a,reference=b,metric=metric,improved=int((d< -1e-7).sum()),worsened=int((d>1e-7).sum()),tied=int((abs(d)<=1e-7).sum()),median_difference=float(d.median()),largest_regression=float(d.max())))
    pd.concat(allsummary).to_csv(ROOT/'results/motion_summary.csv',index=False)
    pd.DataFrame(refits).to_csv(ROOT/'results/independent_motion_refits.csv',index=False)
    pd.DataFrame(changes).to_csv(ROOT/'results/motion_paired_changes.csv',index=False);pd.DataFrame(worst).to_csv(ROOT/'results/motion_worst.csv',index=False)
    save(ROOT/'results/analysis_verified.json',dict(utc=now(),sem_verified=rec(ROOT/'results/sem/independent_verified.json'),motion_refits=len(refits),max_motion_refit_difference_px=max(x['max_difference_px'] for x in refits),pair_arithmetic_checks=5*(120+194+3),images_per_step=204,all_source_checks_pass=True,original_R129_preserved=True,no_training_or_promotion=True))
    print('Full audit passed',len(refits),'circle refits',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['sem','final']);a=p.parse_args()
    try:sem_audit() if a.mode=='sem' else final_audit()
    except BaseException:
        save(ROOT/f'results/failure_audit_{a.mode}_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise

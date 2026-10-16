"""Independently refit saved boundaries and compare the predeclared populations."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from continuous_common import *
from scipy.optimize import least_squares

def main():
    plan=load(OUT/'plan.json');cfg=load(plan['configuration']['path']);core,scope=reader(plan)
    for method in ['Raw','R129']:assert load(OUT/'measurements'/method/'complete.json')['frames']==201
    inference=load(OUT/'inference_complete.json');assert len(inference['records'])==201
    for item in plan['protected_sources']+[plan['checkpoint']]:assert sha(item['path'])==item['sha256']
    for frame in plan['frames']:assert sha(frame['source']['path'])==frame['source']['sha256']
    assert inference['source']==load(OUT/'inference_started.json')['source']
    assert sha(inference['source']['path'])==inference['source']['sha256']
    for row in inference['records']:
        for key in ['image','output_float']:assert sha(row[key]['path'])==row[key]['sha256']
    summary=[];worsts=[];refits=[];context=[];all_tables={}
    # Selection uses only source-defined crop windows and the existing two FOV policies.
    rawcenters=pd.read_csv(OUT/'measurements/Raw/centers.csv')
    for frame in plan['frames']:
        s=cfg['sequences'][frame['sequence']];pred=scope['session_prediction'](frame['sequence'],frame['frame_index'],np.asarray(s['centers'],float),s['expected_signed_dx_px']);h,w=frame['shape'];pitch=s['pitch_px'];half=int(np.ceil(.46*pitch));margin=int(np.ceil(.55*pitch))
        gx=max(0,int(np.floor(pred[:,1].min()))-margin);gy=max(0,int(np.floor(pred[:,2].min()))-margin);ex=min(w,int(np.ceil(pred[:,1].max()))+margin+1);ey=min(h,int(np.ceil(pred[:,2].max()))+margin+1)
        for pid,px,py in pred:
            sx=max(gx,int(np.floor(px))-half);sy=max(gy,int(np.floor(py))-half);tx=min(ex,int(np.floor(px))+half+1);ty=min(ey,int(np.floor(py))+half+1)
            mind=min(sx,sy,w-tx,h-ty)
            context.append(dict(sequence=frame['sequence'],frame_index=frame['frame_index'],pillar_id=int(pid),minimum_window_FOV_distance=mind,fully_neural_both_R128_R129=mind>=96))
    context=pd.DataFrame(context);context.to_csv(OUT/'source_boundary_context.csv',index=False)
    for method in ['Raw','R129']:
        folder=OUT/'measurements'/method;complete=load(folder/'complete.json');centers=pd.read_csv(folder/'centers.csv')
        assert complete['source']==load(folder/'started.json')['source']
        assert sha(complete['source']['path'])==complete['source']['sha256']
        for rec in complete['records']:
            for key in ['centers','boundaries']:assert sha(rec[key]['path'])==rec[key]['sha256']
            points=np.load(rec['boundaries']['path']);table=pd.read_csv(rec['centers']['path'])
            for i,row in enumerate(table.itertuples()):
                xy=points['inflection_points'][i];origin=xy.mean(0);z=xy-origin
                def residual(c):
                    r=np.linalg.norm(z-c,axis=1);return r-r.mean()
                fit=least_squares(residual,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12);center=fit.x+origin;radius=np.linalg.norm(z-fit.x,axis=1).mean()
                diff=max(abs(center[0]-row.lsc_center_x_px),abs(center[1]-row.lsc_center_y_px),abs(radius-row.lsc_radius_px))
                assert diff<1e-4,(method,rec['sequence'],rec['frame_index'],row.pillar_id,diff)
                refits.append(dict(method=method,sequence=rec['sequence'],frame_index=rec['frame_index'],pillar_id=row.pillar_id,max_difference_px=diff))
        index=centers.set_index(['sequence','frame_index','pillar_id'])
        for population in ['locked120','within_session194','repositioning3']:
            pairs=pd.read_csv(folder/(population+'_pairs.csv'));all_tables[(method,population)]=pairs
            for row in pairs.itertuples():
                s=cfg['sequences'][row.sequence];ids=[int(x[0]) for x in s['centers']]
                a=np.array([[index.loc[(row.sequence,row.start_frame_index,i),k] for k in ['lsc_center_x_px','lsc_center_y_px']] for i in ids]);b=np.array([[index.loc[(row.sequence,row.end_frame_index,i),k] for k in ['lsc_center_x_px','lsc_center_y_px']] for i in ids]);v=(b-a)*s['object_um_per_px'];dx,dy=np.median(v,0)
                values=[abs(dx),abs(abs(dx)-s['nominal_step_um'])*1000,np.std(v[:,0],ddof=1)*1000,abs(dy)*1000]
                expected=[row.measured_step_um,row.nominal_abs_error_nm,row.within_grid_sd_nm,row.cross_axis_abs_nm]
                assert max(abs(a-b) for a,b in zip(values,expected))<1e-7
            if population!='repositioning3':
                s=scope['summarize_pairs'](pairs);s['population']=population;summary.append(s)
                for seq,g in pairs.groupby('sequence'):
                    worsts.append(dict(method=method,population=population,sequence=seq,max_nominal_error_nm=float(g.nominal_abs_error_nm.max()),p95_nominal_error_nm=float(g.nominal_abs_error_nm.quantile(.95)),max_cross_axis_nm=float(g.cross_axis_abs_nm.max()),wrong_direction_pairs=int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][seq]['expected_signed_dx_px'])).sum())))
    reference_root=REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/measurements'
    for method in ['R61v16_PSFOFF','R128_P_s1285002']:
        p=pd.read_csv(reference_root/method/'per_pair.csv');all_tables[(method,'locked120')]=p
        s=pd.read_csv(reference_root/method/'summary.csv');s['population']='locked120';summary.append(s)
        for seq,g in p.groupby('sequence'):
            worsts.append(dict(method=method,population='locked120',sequence=seq,max_nominal_error_nm=float(g.nominal_abs_error_nm.max()),p95_nominal_error_nm=float(g.nominal_abs_error_nm.quantile(.95)),max_cross_axis_nm=float(g.cross_axis_abs_nm.max()),wrong_direction_pairs=int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][seq]['expected_signed_dx_px'])).sum())))
    combined=pd.concat(summary,ignore_index=True);combined.to_csv(OUT/'comparison_summary.csv',index=False);pd.DataFrame(worsts).to_csv(OUT/'worst_case_summary.csv',index=False);pd.DataFrame(refits).to_csv(OUT/'independent_refits.csv',index=False)
    paired=[];largest=[]
    candidate=all_tables[('R129','locked120')]
    for other in ['Raw','R61v16_PSFOFF','R128_P_s1285002']:
        merged=candidate.merge(all_tables[(other,'locked120')],on=['sequence','start_frame_index','end_frame_index'],suffixes=('_candidate','_reference'),validate='one_to_one');assert len(merged)==120
        for metric in ['nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm']:
            delta=merged[metric+'_candidate']-merged[metric+'_reference'];paired.append(dict(reference=other,metric=metric,improved=int((delta< -1e-7).sum()),worsened=int((delta>1e-7).sum()),tied=int((abs(delta)<=1e-7).sum()),median_change=float(delta.median())))
            idx=delta.idxmax();row=merged.loc[idx];largest.append(dict(reference=other,metric=metric,sequence=row.sequence,start=int(row.start_frame_index),end=int(row.end_frame_index),candidate=float(row[metric+'_candidate']),reference_value=float(row[metric+'_reference']),difference=float(delta.loc[idx])))
    pd.DataFrame(paired).to_csv(OUT/'paired_changes.csv',index=False);pd.DataFrame(largest).to_csv(OUT/'largest_regressions.csv',index=False)
    flags=context.set_index(['sequence','frame_index','pillar_id']);selected=[]
    for row in candidate.itertuples():
        ids=[int(x[0]) for x in cfg['sequences'][row.sequence]['centers']]
        all9=all(flags.loc[(row.sequence,idx,pid),'fully_neural_both_R128_R129'] for idx in [row.start_frame_index,row.end_frame_index] for pid in ids)
        selected.append(dict(sequence=row.sequence,start_frame_index=row.start_frame_index,end_frame_index=row.end_frame_index,all9_fully_neural=all9))
    selections=pd.DataFrame(selected);selections.to_csv(OUT/'shared_neural_context_pairs.csv',index=False);subset=[]
    for method in ['Raw','R129','R61v16_PSFOFF','R128_P_s1285002']:
        p=all_tables[(method,'locked120')].merge(selections,on=['sequence','start_frame_index','end_frame_index']);p=p[p.all9_fully_neural]
        if len(p):
            s=scope['summarize_pairs'](p);s['population']='source_defined_full_neural_context'
            s.loc[s.scope=='all_four_sequences','scope']='combined_present_sequences_subset'
            subset.append(s)
    if subset:pd.concat(subset).to_csv(OUT/'shared_neural_context_summary.csv',index=False)
    save(OUT/'analysis_verified.json',dict(completed_utc=now(),source=record(__file__),plan=record(OUT/'plan.json'),inference=record(OUT/'inference_complete.json'),independent_circle_refits=len(refits),max_refit_difference_px=max(x['max_difference_px'] for x in refits),pair_arithmetic_recomputed=634,unique_method_adjacent_pairs_recomputed=394,frames_per_method=201,primary_pairs_per_method=120,within_session_pairs_per_method=194,repositioning_pairs_per_method=3,all_original_sources_unchanged=True,summary=record(OUT/'comparison_summary.csv'),pair_changes=record(OUT/'paired_changes.csv'),largest_regressions=largest,model_promoted=False))
    print(combined[combined.scope=='all_four_sequences'].to_string(index=False),flush=True)
if __name__=='__main__':main()

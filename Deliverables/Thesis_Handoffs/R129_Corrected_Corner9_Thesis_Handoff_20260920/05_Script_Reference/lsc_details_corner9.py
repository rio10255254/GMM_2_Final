from lsc_core import *
import argparse,pandas as pd
from scipy.optimize import least_squares

def independent_circle(points):
    origin=points.mean(0);p=points-origin
    def fun(c):
        r=np.linalg.norm(p-c,axis=1);return r-r.mean()
    def jac(c):
        delta=c-p;r=np.linalg.norm(delta,axis=1);j=delta/r[:,None];return j-j.mean(0)
    result=least_squares(fun,np.zeros(2),jac=jac,method='lm',ftol=1e-12,xtol=1e-12,gtol=1e-12)
    return result.x+origin,float(np.mean(np.linalg.norm(p-result.x,axis=1)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--models',nargs='+',default=['Raw','R61','R129']);ap.add_argument('--output',default='results/sem_corner9/analysis');args=ap.parse_args();out=ROOT/args.output;t=out/'tables';t.mkdir(parents=True,exist_ok=True)
    plan=load(ROOT/'config/plan.json');cfg=load(ROOT/'config/sem_corner9_lsc_plan.json');assert sha(cfg['core_source']['path'])==cfg['core_source']['sha256'];cal=load(t/'calibration.json');u=np.array(cal['axis_unit_vector'])
    allcenters=[];allpairs=[];audit=[];max_center_difference=0.;max_pair_difference=0.;count=0
    for model in args.models:
        assert load(ROOT/'results/sem_corner9/centers'/model/'complete.json')['centers']==8370
        for run in plan['runs']:
            name=run['run'];base=ROOT/'results/sem_corner9/centers'/model/name;c=pd.read_csv(base.with_suffix('.csv')).sort_values(['index','pillar_id']);assert len(c)==279
            with np.load(base.with_suffix('.npz')) as z:points=z['points'];assert points.shape==(31,9,64,2)
            values=c[['center_x_px','center_y_px','radius_px']].to_numpy().reshape(31,9,3);assert np.isfinite(values).all()
            for i in range(31):
                for k in range(9):
                    center,radius=independent_circle(points[i,k]);error=float(np.linalg.norm(center-values[i,k,:2]));max_center_difference=max(max_center_difference,error);count+=1
                    if error>1e-3:raise ValueError('Independent circle center disagrees: '+str((model,name,i,k,error)))
            pairs=pd.read_csv(ROOT/'results/sem_corner9/pillar_pairs'/model/(name+'.csv'));assert len(pairs)==540
            for key,g in pairs.groupby(['kind','i','j']):
                direct=values[int(key[2]),:,:2]-values[int(key[1]),:,:2];stored=g.sort_values('pillar_id')[['dx_px','dy_px']].to_numpy();err=float(np.max(np.abs(direct-stored)));max_pair_difference=max(max_pair_difference,err);assert err<1e-8
            pairs['along_error_nm']=(pairs[['dx_px','dy_px']].to_numpy()@u*.1725-pairs.pi_dy_um.to_numpy())*1000
            allcenters.append(c);allpairs.append(pairs);audit.append(dict(model=model,run=name,centers=len(c),pillar_pairs=len(pairs)))
    centers=pd.concat(allcenters,ignore_index=True);pairs=pd.concat(allpairs,ignore_index=True);centers.to_csv(t/'all_circle_centers.csv',index=False,encoding='utf-8-sig');pairs.to_csv(t/'all_individual_circle_pairs.csv',index=False,encoding='utf-8-sig')
    summaries=[]
    for (model,kind,pid),g in pairs.groupby(['model','kind','pillar_id']):
        e=g.along_error_nm;perpos=g.groupby('j').along_error_nm.std(ddof=1)
        summaries.append(dict(model=model,kind=kind,pillar_id=int(pid),pairs=len(g),mae_nm=float(e.abs().mean()),bias_nm=float(e.mean()),repeatability_nm=float(perpos.mean()),maximum_error_nm=float(e.abs().max())))
    pd.DataFrame(summaries).to_csv(t/'individual_circle_summary.csv',index=False,encoding='utf-8-sig')
    grids=pairs.groupby(['model','kind','run','run_index','i','j']).along_error_nm.std(ddof=1).reset_index(name='within_grid_sd_nm');grids.to_csv(t/'within_grid_variation.csv',index=False,encoding='utf-8-sig')
    checkrows=[];tracking=pd.read_csv(ROOT/'results/sem_corner9/tracking.csv')
    for model in args.models:
        for f in [plan['frames'][0],plan['frames'][-1]]:
            if model=='Raw':image=cv2.imread(f['source']['path'],0).astype(float)/255
            else:
                with np.load(ROOT/'results'/model/f['run']/f"{f['index']+1:02d}.npz") as z:image=z['output'].astype(float)
            seeds=tracking[(tracking.run==f['run'])&(tracking['index']==f['index'])].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy();rows,_=measure_image(image,seeds,cfg)
            stored=centers[(centers.model==model)&(centers.run==f['run'])&(centers['index']==f['index'])].sort_values('pillar_id');new=pd.DataFrame(rows);diff=float(np.max(np.abs(new[['center_x_px','center_y_px','radius_px']].to_numpy()-stored[['center_x_px','center_y_px','radius_px']].to_numpy())));assert diff<1e-8;checkrows.append(dict(model=model,run=f['run'],index=f['index'],max_replay_difference_px=diff))
    primary=pd.read_csv(t/'all_measurements.csv');max_arithmetic=0.
    for view,g in primary.groupby('view'):
        scale=cal['estimated_um_per_px'] if view=='calibrated_late24' else .1725;error=(g[['dx_px','dy_px']].to_numpy()@u*scale-g.pi_dy_um.to_numpy())*1000;max_arithmetic=max(max_arithmetic,float(np.max(np.abs(error-g.error_nm.to_numpy()))))
    assert max_arithmetic<.0001
    save(out/'verification.json',dict(complete=True,method='Thesis inflection-boundary geometric least-squares circle',models=args.models,centers_per_model=8370,independent_circle_fits=count,max_independent_center_difference_px=max_center_difference,max_direct_pair_difference_px=max_pair_difference,max_arithmetic_difference_nm=max_arithmetic,replayed_images=checkrows,source=record(CORE_PATH),completed_utc=now()))
    print('LSC verified',count,'centers; max independent discrepancy',max_center_difference,'px',flush=True)
if __name__=='__main__':main()

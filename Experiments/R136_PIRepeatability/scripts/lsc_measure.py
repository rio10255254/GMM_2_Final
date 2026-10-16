from lsc_core import *
import time,csv,traceback,argparse
import pandas as pd
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED

def measure_run(model,run):
    cv2.setNumThreads(1);cfg=load(ROOT/'config/lsc_plan.json');plan=load(ROOT/'config/plan.json');tracking=pd.read_csv(ROOT/'results/lsc/tracking.csv');tracking=tracking[tracking.run==run]
    frames=[f for f in plan['frames'] if f['run']==run];allrows=[];allpoints=[];allcoarse=[];start=time.perf_counter()
    out=ROOT/'results/lsc/centers'/model;out.mkdir(parents=True,exist_ok=True)
    for f in frames:
        if model=='Raw':image=cv2.imread(f['source']['path'],0).astype(np.float64)/255
        else:
            with np.load(ROOT/'results'/model/run/f"{f['index']+1:02d}.npz") as z:image=z['output'].astype(np.float64)
        seeds=tracking[tracking['index']==f['index']].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy();assert seeds.shape==(9,2)
        rows,points=measure_image(image,seeds,cfg)
        allrows.extend([dict(model=model,run=run,run_index=f['run_index'],index=f['index'],**r) for r in rows]);allpoints.append(points['points']);allcoarse.append(points['coarse'])
    centers=pd.DataFrame(allrows);assert len(centers)==279;centers.to_csv(out/(run+'.csv'),index=False,encoding='utf-8-sig')
    np.savez_compressed(out/(run+'.npz'),points=np.stack(allpoints),coarse=np.stack(allcoarse))
    matrix=centers.sort_values(['index','pillar_id'])[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2);radius=centers.sort_values(['index','pillar_id']).radius_px.to_numpy().reshape(31,9)
    readouts=[];pillar_pairs=[]
    for kind,i,j in [('adjacent',i-1,i) for i in range(1,31)]+[('start',0,i) for i in range(1,31)]:
        f,g=frames[i],frames[j];d=matrix[j]-matrix[i];median=np.median(d,axis=0)
        shared=dict(model=model,run=run,run_index=f['run_index'],time_block='early6' if f['run_index']<=6 else 'late24',kind=kind,i=i,j=j,pi_dx_um=g['pi_x_um']-f['pi_x_um'],pi_dy_um=g['pi_y_um']-f['pi_y_um'],recorded_at=g['recorded_at'])
        readouts.append(dict(**shared,roi='center9',reader='LSC',precision='full',status='ok',dx_px=float(median[0]),dy_px=float(median[1]),within_grid_x_sd_px=float(d[:,0].std(ddof=1)),within_grid_y_sd_px=float(d[:,1].std(ddof=1)),circle_count=9))
        for pid,v in enumerate(d,1):pillar_pairs.append(dict(**shared,pillar_id=pid,dx_px=float(v[0]),dy_px=float(v[1]),radius_change_px=float(radius[j,pid-1]-radius[i,pid-1])))
    rdir=ROOT/'results/lsc/readouts'/model;rdir.mkdir(parents=True,exist_ok=True);pd.DataFrame(readouts).to_csv(rdir/(run+'.csv'),index=False,encoding='utf-8-sig')
    pdir=ROOT/'results/lsc/pillar_pairs'/model;pdir.mkdir(parents=True,exist_ok=True);pd.DataFrame(pillar_pairs).to_csv(pdir/(run+'.csv'),index=False,encoding='utf-8-sig')
    result=dict(model=model,run=run,frames=31,centers=279,pairs=60,pillar_pairs=540,seconds=time.perf_counter()-start,completed_utc=now());save(out/(run+'.json'),result)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=4);args=ap.parse_args();plan=load(ROOT/'config/plan.json')
    pending=[(m,r['run']) for m in ['Raw','R61','R129'] for r in plan['runs'] if not (ROOT/'results/lsc/centers'/m/(r['run']+'.json')).exists()];finished=90-len(pending);futures={};start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        while pending or futures:
            for job in list(pending):
                model,run=job
                if len(futures)<args.workers and (model=='Raw' or (ROOT/'results'/model/run/'31.json').exists()):futures[pool.submit(measure_run,model,run)]=job;pending.remove(job)
            done,_=wait(futures,timeout=10,return_when=FIRST_COMPLETED) if futures else (set(),set())
            for f in done:
                job=futures.pop(f)
                try:result=f.result();finished+=1;print(result,flush=True)
                except BaseException:save(ROOT/'results/lsc/failure.json',dict(job=job,error=traceback.format_exc(),utc=now()));raise
            save(ROOT/'results/lsc/status.json',dict(status='running',finished_runs=finished,total_runs=90,active=list(futures.values()),pending=len(pending),updated_utc=now(),pid=os.getpid(),elapsed_s=time.perf_counter()-start))
            for model in ['Raw','R61','R129']:
                complete=ROOT/'results/lsc/centers'/model/'complete.json'
                if not complete.exists() and len(list((ROOT/'results/lsc/centers'/model).glob('*_XY_0.json')))==30:save(complete,dict(model=model,scans=30,frames=930,centers=8370,completed_utc=now()))
            if not futures and pending:time.sleep(10)
    save(ROOT/'results/lsc/complete.json',dict(status='complete',scans=90,centers_per_model=8370,completed_utc=now()));save(ROOT/'results/lsc/status.json',dict(status='complete',finished_runs=90,total_runs=90,updated_utc=now()))
if __name__=='__main__':main()

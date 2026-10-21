import os
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='1'
from common import *
from reader import measure
import argparse,csv,time,traceback
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import cv2,numpy as np

def measure_run(tag,run):
    cv2.setNumThreads(1);plan=load(ROOT/'config/plan.json');frames=[f for f in plan['frames'] if f['run']==run]
    images=[];tick=time.perf_counter()
    for f in frames:
        if tag=='Raw':im=cv2.imread(f['source']['path'],0).astype(np.float32)/255
        else:
            with np.load(ROOT/'results'/tag/run/f"{f['index']+1:02d}.npz") as z:im=z['output'].copy()
        images.append(im)
    rows=[]
    pairs=[('adjacent',i-1,i) for i in range(1,31)]+[('start',0,i) for i in range(1,31)]
    for kind,i,j in pairs:
        a,b=images[i],images[j];f,g=frames[i],frames[j]
        base=dict(model=tag,run=run,run_index=f['run_index'],time_block='early6' if f['run_index']<=6 else 'late24',kind=kind,i=i,j=j,pi_dx_um=g['pi_x_um']-f['pi_x_um'],pi_dy_um=g['pi_y_um']-f['pi_y_um'],recorded_at=g['recorded_at'])
        coarse=None
        for name,roi in plan['rois'].items():
            try:
                result=measure(a,b,roi,coarse=coarse)
                if name=='primary':coarse=np.array([-result['coarse_dy_px'],-result['coarse_dx_px']])
                rows.append(dict(**base,roi=name,reader='highpass',precision='full',status='ok',**result,error=''))
            except Exception as exc:rows.append(dict(**base,roi=name,reader='highpass',precision='full',status='failed',error=str(exc)))
        for mode,precision in [('intensity','full')]+([('highpass','8bit')] if tag!='Raw' else []):
            try:
                aa,bb=(np.rint(a*255)/255,np.rint(b*255)/255) if precision=='8bit' else (a,b)
                result=measure(aa,bb,plan['rois']['primary'],mode=mode,coarse=coarse)
                rows.append(dict(**base,roi='primary',reader=mode,precision=precision,status='ok',**result,error=''))
            except Exception as exc:rows.append(dict(**base,roi='primary',reader=mode,precision=precision,status='failed',error=str(exc)))
    out=ROOT/'results/readouts'/tag;out.mkdir(parents=True,exist_ok=True);path=out/(run+'.csv')
    fields=list(dict.fromkeys(k for r in rows for k in r));tmp=path.with_suffix('.writing')
    with tmp.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    os.replace(tmp,path);save(out/(run+'.json'),dict(model=tag,run=run,rows=len(rows),failed=sum(r['status']!='ok' for r in rows),seconds=time.perf_counter()-tick))
    return dict(model=tag,run=run,rows=len(rows),seconds=round(time.perf_counter()-tick,1))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);a=parser.parse_args();plan=load(ROOT/'config/plan.json')
    pending=[(m,r['run']) for m in ['Raw','R61','R129'] for r in plan['runs'] if not (ROOT/'results/readouts'/m/(r['run']+'.json')).exists()]
    futures={};finished=90-len(pending);start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        while pending or futures:
            for job in list(pending):
                m,r=job
                ready=m=='Raw' or (ROOT/'results'/m/r/'31.json').exists()
                if ready and len(futures)<a.workers:
                    futures[pool.submit(measure_run,m,r)]=job;pending.remove(job)
            done,_=wait(futures,timeout=15,return_when=FIRST_COMPLETED) if futures else (set(),set())
            for future in done:
                job=futures.pop(future)
                try:print(future.result(),flush=True);finished+=1
                except BaseException:
                    save(ROOT/'results/measurement_failure.json',dict(job=job,error=traceback.format_exc()));raise
            save(ROOT/'results/status_measurements.json',dict(finished_runs=finished,total_runs=90,pending_runs=len(pending),active_runs=list(futures.values()),elapsed_s=time.perf_counter()-start,updated_utc=now(),pid=os.getpid()))
            if not futures and pending:time.sleep(15)
    save(ROOT/'results/measurements_complete.json',dict(runs=finished,completed_utc=now(),elapsed_s=time.perf_counter()-start))
if __name__=='__main__':main()

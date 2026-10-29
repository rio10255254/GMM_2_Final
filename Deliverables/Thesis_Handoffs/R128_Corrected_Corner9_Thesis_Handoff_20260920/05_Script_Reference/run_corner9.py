from lsc_measure_corner9 import *
from concurrent.futures import ProcessPoolExecutor,as_completed
def main():
 plan=load(ROOT/'config/plan.json');dest=ROOT/'results/sem_corner9';jobs=[(m,r['run']) for m in ['Raw','R61','R129','R128'] for r in plan['runs'] if not (dest/'centers'/m/(r['run']+'.json')).exists()];done=120-len(jobs)
 with ProcessPoolExecutor(max_workers=2) as pool:
  futures={pool.submit(measure_run,*j):j for j in jobs}
  for f in as_completed(futures):
   try:r=f.result()
   except Exception:
    save(dest/'status.json',dict(status='failed',job=futures[f],error=traceback.format_exc()));raise
   done+=1;save(dest/'status.json',dict(status='running',finished=done,total=120,last=r,updated_utc=now()));print(done,r['model'],r['run'],flush=True)
 save(dest/'status.json',dict(status='centers_complete',finished=120,total=120,updated_utc=now()))
if __name__=='__main__':main()

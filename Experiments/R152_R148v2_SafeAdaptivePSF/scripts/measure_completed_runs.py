"""Measure a disjoint prefix of complete scans while reconstruction continues."""
from __future__ import annotations
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_real import measure_run
from utils import load,now,save

def main():
 plan=load(ROOT/'evaluation/capture_plan.json');runs=[item['run'] for item in plan['runs'][:20]];out=ROOT/'results/centers';out.mkdir(exist_ok=True)
 for index,run in enumerate(runs,1):
  complete=ROOT/'results/reconstruction'/run/'31.json';record=out/(run+'.json')
  while not complete.is_file():time.sleep(15)
  if not record.is_file():
   result=measure_run(run);print('MEASURED_EARLY',index,'/',len(runs),run,result['circles'],flush=True)
  else:print('EXISTING',index,run,flush=True)
 save(ROOT/'results/early_measurement_complete.json',dict(scans=len(runs),images=len(runs)*31,circles=len(runs)*279,completed_utc=now()))
if __name__=='__main__':main()

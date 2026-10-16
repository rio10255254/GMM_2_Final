from pathlib import Path
import argparse,os,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from utils import load,save,now
p=argparse.ArgumentParser();p.add_argument('--device',choices=['cpu','cuda'],required=True);p.add_argument('--threads',type=int,default=24);a=p.parse_args()
if not 1<=a.threads<=24:raise ValueError('Use1..24threads')
if (ROOT/'runs/formal_8192/training_complete.json').exists():raise RuntimeError('Training already complete; this command switches training only')
if not (HERE/'supervisor.json').exists():raise RuntimeError('Start the continuation supervisor first')
import psutil
info=load(HERE/'supervisor.json')
if not psutil.pid_exists(info['pid']) or abs(psutil.Process(info['pid']).create_time()-info['create_time'])>1:raise RuntimeError('Supervisor is not active')
if (HERE/'switch_request.json').exists():raise RuntimeError('A switch is already pending')
save(HERE/'switch_request.json',dict(device=a.device,threads=a.threads,requested_utc=now(),reason='Explicit manual user request'))
print('Requested',a.device,a.threads,'threads. The current batch completes, then weights and optimizer are saved before restart.')

"""Wait for actual outputs, then run the bounded independent review and publication."""
import sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import load
def main():
    out=ROOT/'results/continuous_lsc';deadline=time.monotonic()+7200
    required=[out/'inference_complete.json',out/'measurements/Raw/complete.json',out/'measurements/R129/complete.json']
    while not all(x.exists() for x in required):
        status=out/'inference_status.json'
        if status.exists() and load(status)['status']=='failed':raise RuntimeError('Inference failed; no completion accepted')
        if (out/'measurements/R129/failure.json').exists():raise RuntimeError('Measurement failed; no completion accepted')
        if time.monotonic()>deadline:raise TimeoutError('Waiting for actual required outputs timed out')
        time.sleep(3)
    for script in ['audit_continuous_lsc.py','replay_continuous_worst.py','publish_continuous_lsc.py']:
        subprocess.run([sys.executable,'-u','-B',str(ROOT/'scripts'/script)],check=True)
    print('Independent review and report ready for visual inspection',flush=True)
if __name__=='__main__':main()

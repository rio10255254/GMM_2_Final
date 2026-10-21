"""Run the fixed real sequence comparison when all32 training epochs actually finish."""
import time,sys,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    deadline=time.monotonic()+10800
    while not (ROOT/'runs/v42_clean/completion.json').exists():
        p=ROOT/'runs/v42_clean/status.json'
        if p.exists() and json.loads(p.read_text(encoding='utf-8'))['status']=='failed':raise RuntimeError('Training failed')
        if time.monotonic()>deadline:raise TimeoutError('Training did not finish')
        time.sleep(3)
    subprocess.run([sys.executable,'-u','-B',str(ROOT/'scripts/continuous.py')],check=True)
    print('Training and final real inference/LSC ready for independent audit',flush=True)
if __name__=='__main__':main()

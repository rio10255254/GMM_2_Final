"""Finish numeric checks as soon as all predeclared observations are available."""
from study import *
import subprocess,traceback

def main():
    needed=[ROOT/'results/inference_complete.json']+[ROOT/f'results/measurements/N{n}/complete.json' for n in range(5)]
    while not all(p.exists() for p in needed):
        failures=[p for p in (ROOT/'results').glob('failure_*.json') if 'preflight' not in p.name]
        if failures:raise RuntimeError('A study component failed: '+str(failures))
        time.sleep(2)
    for script,args in [('analyze.py',['final']),('figures.py',[])]:
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/script),*args],check=True)
    print('All measurement checks complete; runtime and final interpretation separate',flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        save(ROOT/f'results/failure_finish_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise

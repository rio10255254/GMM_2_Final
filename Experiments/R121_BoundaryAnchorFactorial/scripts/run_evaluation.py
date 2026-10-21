"""Wait for the valid paired matrix, then execute the frozen common evaluation."""
from pathlib import Path
import json,subprocess,sys,time,hashlib
ROOT=Path(__file__).resolve().parents[1]
def atomic(path,value):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)

def main():
    start=time.monotonic()
    while not (ROOT/'results/matrix_finished_v2.json').exists():
        marker=json.loads((ROOT/'runs/launcher_logs/active_formal_run.json').read_text())
        if marker['status']=='failed':raise RuntimeError('Matrix failed; evaluation not started')
        if time.monotonic()-start>3600:raise TimeoutError('Matrix wait exceeded one hour')
        time.sleep(3)
    code={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'scripts/evaluate_matrix.py',ROOT/'scripts/evaluate_sem.m',ROOT/'scripts/assess_results.py',ROOT/'scripts/verify_matrix.py']}
    with (ROOT/'config/evaluation_code_freeze.json').open('x') as f:json.dump(code,f,indent=2)
    phases=[('verify_matrix',[sys.executable,'-B','scripts/verify_matrix.py']),
            ('development',[sys.executable,'-B','scripts/evaluate_matrix.py','development']),
            ('controlled',[sys.executable,'-B','scripts/evaluate_matrix.py','controlled']),
            ('sem_render',[sys.executable,'-B','scripts/evaluate_matrix.py','sem']),
            ('sem_measure',[r'C:/Program Files/MATLAB/R2025b/bin/matlab.exe','-batch',f"addpath('{(ROOT/'scripts').as_posix()}');evaluate_sem"]),
            ('assess',[sys.executable,'-B','scripts/assess_results.py'])]
    rows=[]
    for name,command in phases:
        atomic(ROOT/'results/evaluation_progress.json',{'status':'running','phase':name,'completed_phases':rows})
        t=time.time()
        with (ROOT/'runs/launcher_logs'/f'eval_{name}.log').open('x') as stream:result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        rows.append({'phase':name,'returncode':result.returncode,'started_at_unix':t,'finished_at_unix':time.time()})
        print(json.dumps(rows[-1]),flush=True)
        if result.returncode:
            atomic(ROOT/'results/evaluation_progress.json',{'status':'failed','phase':name,'completed_phases':rows});raise RuntimeError(name+' failed; preserve outputs and inspect')
    atomic(ROOT/'results/evaluation_progress.json',{'status':'evaluation_executed_read_decision','completed_phases':rows})
    print('Evaluation executed; read scientific decision and any required real-LSC follow-up',flush=True)

if __name__=='__main__':main()

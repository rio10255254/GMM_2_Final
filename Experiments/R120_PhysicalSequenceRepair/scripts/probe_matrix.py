"""Run exactly four bounded scratch probes, with per-run subprocess logs."""
from pathlib import Path
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    matrix=[]
    output=ROOT/'results/probe_matrix.json'
    if output.exists():raise FileExistsError(output)
    for seed in [1185001,1185002]:
        for arm in ['A','B']:
            run_id=f'probe_{arm}_s{seed}'
            folder=ROOT/'results/launcher_logs';folder.mkdir(exist_ok=True)
            cmd=[sys.executable,str(ROOT/'training/train.py'),'--arm',arm,'--seed',str(seed),'--run-id',run_id]
            with (folder/f'{run_id}.log').open('x') as stream:
                result=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            matrix.append({'run_id':run_id,'arm':arm,'seed':seed,'returncode':result.returncode})
            print(json.dumps(matrix[-1]),flush=True)
            if result.returncode:raise RuntimeError(f'{run_id} failed; preserved log')
    output.write_text(json.dumps({'status':'complete','runs':matrix},indent=2))

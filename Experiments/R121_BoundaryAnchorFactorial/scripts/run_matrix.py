"""Execute exactly eight paired scratch probes; preserve failures and logs."""
from pathlib import Path
import json,hashlib,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,indent=2));temporary.replace(path)

def main():
    protocol=json.loads((ROOT/'config/protocol.json').read_text())
    smoke=json.loads((ROOT/'runs/smoke_D/SUMMARY.json').read_text())
    assert smoke['status']=='complete' and smoke['completed_epochs']==3 and smoke['steps']==6
    assert (ROOT/'results/pitch_matched_reference.mat').exists()
    assert not (ROOT/'runs/active.lock').exists()
    snapshot=json.loads((ROOT/'reports/protected_inputs.json').read_text())
    assert all(sha(p)==value for p,value in snapshot.items())
    frozen={str(p.relative_to(ROOT)):sha(p) for d in ['training','model','inference'] for p in (ROOT/d).glob('*.py')}
    for p in [ROOT/'config/experiment.json',ROOT/'config/protocol.json']:frozen[str(p.relative_to(ROOT))]=sha(p)
    with (ROOT/'config/source_freeze.json').open('x') as stream:json.dump(frozen,stream,indent=2)
    marker=ROOT/'runs/launcher_logs/active_formal_run.json'
    with marker.open('x') as stream:json.dump({'status':'running','scope':'bounded_probe_matrix_not_formal_long_training','pid':os.getpid(),'planned_runs':8,'completed_runs':0},stream,indent=2)
    rows=[]
    for seed in protocol['model_seeds']:
        for arm in 'ABCD':
            assert all(sha(ROOT/p)==value for p,value in frozen.items())
            run_id=f'probe_{arm}_s{seed}'
            command=[sys.executable,'-B',str(ROOT/'training/train.py'),'--arm',arm,'--seed',str(seed),'--run-id',run_id,'--epochs','12','--scenes','512','--batch','8','--workers','2']
            started=time.time()
            with (ROOT/'runs/launcher_logs'/f'{run_id}.log').open('x') as stream:
                result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            item={'run_id':run_id,'arm':arm,'seed':seed,'returncode':result.returncode,'started_at_unix':started,'finished_at_unix':time.time()}
            if result.returncode:
                rows.append(item);atomic(ROOT/'results/matrix_progress.json',{'status':'failed','runs':rows})
                atomic(marker,{'status':'failed','scope':'bounded_probe_matrix','failed_run':run_id,'completed_runs':len(rows)-1});raise RuntimeError(run_id+' failed; retained outputs')
            state=json.loads((ROOT/'runs'/run_id/'SUMMARY.json').read_text())
            assert state['status']=='complete' and state['completed_epochs']==12 and state['steps']==768
            item['initialization_sha256']=state['initialization_sha256'];rows.append(item)
            atomic(ROOT/'results/matrix_progress.json',{'status':'running' if len(rows)<8 else 'runs_executed_evaluation_pending','runs':rows})
            atomic(marker,{'status':'running' if len(rows)<8 else 'runs_executed_evaluation_pending','scope':'bounded_probe_matrix_not_formal_long_training','completed_runs':len(rows),'planned_runs':8})
            print(json.dumps(item),flush=True)
    for seed in protocol['model_seeds']:assert len({r['initialization_sha256'] for r in rows if r['seed']==seed})==1
    assert rows[0]['initialization_sha256']!=rows[4]['initialization_sha256']
    assert all(sha(p)==value for p,value in snapshot.items())
    with (ROOT/'results/matrix_finished.json').open('x') as stream:json.dump({'status':'runs_executed_evaluation_pending','runs':rows,'protected_inputs_unchanged':len(snapshot)},stream,indent=2)
    print('Eight runs executed; no scientific-success or promotion claim',flush=True)

if __name__=='__main__':main()

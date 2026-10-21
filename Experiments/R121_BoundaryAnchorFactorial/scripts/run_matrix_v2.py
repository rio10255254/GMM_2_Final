"""Finish the valid factorial: preserve A/B controls and replace invalid C v1."""
from pathlib import Path
import json,hashlib,os,subprocess,sys,time,shutil
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(path,value):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)
def check(run_id):
    folder=ROOT/'runs'/run_id;state=json.loads((folder/'SUMMARY.json').read_text())
    assert state['status']=='complete' and state['completed_epochs']==12 and state['steps']==768
    assert not (folder/'failure.json').exists()
    for e in [4,8,12]:assert (folder/'weights'/f'epoch_{e:03d}.pth').is_file()
    return state

def main():
    protocol=json.loads((ROOT/'config/protocol_v2.json').read_text())
    smoke=json.loads((ROOT/'runs/smoke_D_v2/SUMMARY.json').read_text());assert smoke['status']=='complete' and smoke['completed_epochs']==3
    assert not (ROOT/'runs/active.lock').exists()
    frozen={str(p.relative_to(ROOT)):sha(p) for d in ['training','model','inference'] for p in (ROOT/d).glob('*.py')}
    for p in [ROOT/'config/experiment.json',ROOT/'config/protocol_v2.json']:frozen[str(p.relative_to(ROOT))]=sha(p)
    with (ROOT/'config/source_freeze_v2.json').open('x') as f:json.dump(frozen,f,indent=2)
    original=json.loads((ROOT/'results/matrix_progress.json').read_text())['runs']
    rows=[];marker=ROOT/'runs/launcher_logs/active_formal_run.json'
    shutil.copy2(marker,marker.with_name('matrix_v1_interrupted.json'))
    atomic(marker,{'status':'running','scope':'bounded_factorial_v2','pid':os.getpid(),'planned_valid_runs':8,'completed_valid_runs':2})
    for seed in protocol['model_seeds']:
        for arm in 'ABCD':
            assert all(sha(ROOT/p)==value for p,value in frozen.items())
            if seed==1215001 and arm in 'AB':
                run_id=f'probe_{arm}_s{seed}';state=check(run_id)
                item={**next(r for r in original if r['run_id']==run_id),'reused_valid_control':True,'checkpoint_sha256':sha(ROOT/'runs'/run_id/'weights/epoch_012.pth')}
            else:
                run_id=f'probe_{arm}_s{seed}_v2'
                command=[sys.executable,'-B',str(ROOT/'training/train_v2.py'),'--arm',arm,'--seed',str(seed),'--run-id',run_id,'--epochs','12','--scenes','512','--batch','8','--workers','2']
                started=time.time()
                with (ROOT/'runs/launcher_logs'/f'{run_id}.log').open('x') as stream:result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
                if result.returncode:
                    atomic(marker,{'status':'failed','scope':'bounded_factorial_v2','run_id':run_id});raise RuntimeError(run_id+' failed; outputs retained')
                state=check(run_id);item={'run_id':run_id,'arm':arm,'seed':seed,'returncode':result.returncode,'started_at_unix':started,'finished_at_unix':time.time(),'initialization_sha256':state['initialization_sha256'],'reused_valid_control':False,'checkpoint_sha256':sha(ROOT/'runs'/run_id/'weights/epoch_012.pth')}
            rows.append(item)
            atomic(ROOT/'results/matrix_progress_v2.json',{'status':'running' if len(rows)<8 else 'runs_executed_evaluation_pending','runs':rows})
            atomic(marker,{'status':'running' if len(rows)<8 else 'runs_executed_evaluation_pending','scope':'bounded_factorial_v2','pid':os.getpid(),'completed_valid_runs':len(rows),'planned_valid_runs':8})
            print(json.dumps(item),flush=True)
    for seed in protocol['model_seeds']:assert len({r['initialization_sha256'] for r in rows if r['seed']==seed})==1
    assert rows[0]['initialization_sha256']!=rows[4]['initialization_sha256']
    snapshot=json.loads((ROOT/'reports/protected_inputs.json').read_text());assert all(sha(p)==value for p,value in snapshot.items())
    with (ROOT/'results/matrix_finished_v2.json').open('x') as f:json.dump({'status':'runs_executed_evaluation_pending','runs':rows,'excluded_interrupted_run':'probe_C_s1215001','protected_inputs_unchanged':len(snapshot)},f,indent=2)

if __name__=='__main__':main()

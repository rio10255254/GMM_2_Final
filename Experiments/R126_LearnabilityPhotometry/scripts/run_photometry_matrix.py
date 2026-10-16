"""Complete all fixed initial/evaluated final pairs without selecting a winner."""
import subprocess,os,traceback
from common import *

def main():
    cfg=json.loads((ROOT/'config/photometry_pilot.json').read_text())
    scale=json.loads((ROOT/'results/update_scale_summary.json').read_text())
    assert all(r['learnability_signal'] for r in scale['runs'])
    assert json.loads((ROOT/'results/photometry_admission.json').read_text())['pilot_admitted']
    assert json.loads((ROOT/'results/derivative_precision.json').read_text())['passed']
    evaluator=json.loads((ROOT/'results/evaluator_semantic_check.json').read_text())
    assert evaluator['passed'] and evaluator['adapted_sha256']==sha(ROOT/'scripts/evaluate_real.py')
    state=dict(status='running',round='R126',pid=os.getpid(),planned_training_updates=512,completed_training_updates=0,completed_fixed_diagnostic_updates=768,planned_total_updates=1280,initial_evaluations=0,final_evaluations=0,formal_training=False,formal_promotion=False)
    marker=ROOT/'runs/launcher_logs/active_formal_run.json';save(marker,state,False)
    logs=ROOT/'runs/launcher_logs';evals=[];events=[]
    def call(name,*args):
        t=time.time();path=logs/f'{name}.log'
        with path.open('x') as f:
            result=subprocess.run([sys.executable,*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        events.append(dict(name=name,started_unix=t,finished_unix=time.time(),exit_code=result.returncode,log=str(path),sha256=sha(path)))
        save(ROOT/'runs/matrix_events.json',events,False)
        if result.returncode:raise RuntimeError(f'{name} failed; original log retained')
    try:
        call('photo_prepare','scripts/train_photometry.py','--prepare')
        for seed in cfg['seeds']:
            for arm in ['P','Q']:
                path=ROOT/'results'/f'real_{arm}_s{seed}_step0000';evals.append(str(path))
                call(f'real_{arm}_s{seed}_step0000','scripts/evaluate_real.py','--checkpoint',str(ROOT/'runs/photometry_initial'/f'{arm}_s{seed}_step0000.pth'),'--output',str(path),'--device','cuda')
                state['initial_evaluations']+=1;save(marker,state,False)
        for seed in cfg['seeds']:
            for arm in ['P','Q']:
                call(f'photo_{arm}_s{seed}','scripts/train_photometry.py','--arm',arm,'--seed',str(seed));state['completed_training_updates']+=128;save(marker,state,False)
                path=ROOT/'results'/f'real_{arm}_s{seed}_step0128';evals.append(str(path))
                call(f'real_{arm}_s{seed}_step0128','scripts/evaluate_real.py','--checkpoint',str(ROOT/'runs'/f'photo_{arm}_s{seed}'/'step0128.pth'),'--output',str(path),'--device','cuda')
                state['final_evaluations']+=1;save(marker,state,False)
        call('real_aggregate','scripts/evaluate_real.py','--aggregate',*evals,'--output',str(ROOT/'results/real_comparison'))
        state.update(status='bounded_matrix_complete_independent_audit_pending',finished_unix=time.time())
        save(ROOT/'runs/matrix_summary.json',state);save(marker,state,False)
    except BaseException as e:
        state.update(status='failed',error=repr(e),traceback=traceback.format_exc());save(ROOT/'runs/matrix_failure.json',state);save(marker,state,False);raise

if __name__=='__main__':main()

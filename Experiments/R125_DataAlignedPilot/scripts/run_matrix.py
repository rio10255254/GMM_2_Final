"""Serialize the bounded training/evaluation matrix; every stage keeps its own log."""
import argparse,json,pathlib,subprocess,sys,time,traceback
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def main():
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--audit',required=True);args=p.parse_args()
    config=load(ROOT/'config/pilot.json');audit=load(pathlib.Path(args.audit))
    if audit.get('pilot_admitted') is not True:raise ValueError('Dataset is not admitted')
    if load(ROOT/'results/factorized_runtime.json').get('status')!='passed' or load(ROOT/'results/context_equivalence.json').get('status')!='passed':raise ValueError('Actual runtime/context checks are incomplete')
    stagefile=ROOT/'runs/matrix_state.json'
    if stagefile.exists():raise FileExistsError('Matrix already has evidence; do not overwrite')
    state={'status':'running','phase':'initialize','started':time.time(),'events':[],'planned_updates':384,'formal_promotion':False};save(stagefile,state)
    def execute(tag,arguments):
        log=ROOT/'runs/launcher_logs'/f'{tag}.log'
        if log.exists():raise FileExistsError(log)
        state.update(phase=tag);save(stagefile,state);print(json.dumps({'stage':tag,'status':'started'}),flush=True)
        t=time.perf_counter()
        with log.open('x',encoding='utf-8') as stream:
            result=subprocess.run([sys.executable,*map(str,arguments)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        event={'stage':tag,'returncode':result.returncode,'elapsed_seconds':time.perf_counter()-t,'log':str(log)};state['events'].append(event);save(stagefile,state);print(json.dumps(event),flush=True)
        if result.returncode:raise RuntimeError(f'{tag} failed; preserve log')
    try:
        execute('matrix_initializations',['training/train_pilot.py','--package',args.package,'--prepare'])
        initialdirs=[];finaldirs=[]
        for seed in config['model_seeds']:
            for arm in config['arms']:
                label=f'{arm}_s{seed}';ck=ROOT/'runs/initializations'/f'{label}_step0000.pth';out=ROOT/'results'/f'real_{label}_step0000'
                execute('eval_'+label+'_step0000',['scripts/evaluate_real_pilot_v2.py','--checkpoint',ck,'--output',out,'--device','cuda']);initialdirs.append(out)
        state['initial_evaluations_complete_before_optimizer_updates']=True;save(stagefile,state)
        for seed in config['model_seeds']:
            for arm in config['arms']:
                label=f'{arm}_s{seed}'
                execute('train_'+label,['training/train_pilot.py','--package',args.package,'--audit',args.audit,'--arm',arm,'--seed',seed])
                ck=ROOT/'runs'/label/'checkpoints/step0064.pth';out=ROOT/'results'/f'real_{label}_step0064'
                execute('eval_'+label+'_step0064',['scripts/evaluate_real_pilot_v2.py','--checkpoint',ck,'--output',out,'--device','cuda']);finaldirs.append(out)
        execute('aggregate_real',['scripts/evaluate_real_pilot_v2.py','--aggregate',*initialdirs,*finaldirs,'--output',ROOT/'results/real_comparison'])
        state.update(status='bounded_matrix_completed_not_promoted',completed_updates=384,elapsed_seconds=time.time()-state['started']);save(stagefile,state)
    except BaseException as exc:
        state.update(status='failed',error=repr(exc),traceback=traceback.format_exc());save(stagefile,state);raise
    print(json.dumps({'status':state['status'],'updates':384}),flush=True)
if __name__=='__main__':main()

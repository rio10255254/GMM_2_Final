"""Reconcile every actual update/input, fixed roles and saved real outputs."""
import ast
from common import *

def main():
    failures=[];checks=[]
    def require(condition,message):
        checks.append(dict(check=message,passed=bool(condition)))
        if not condition:failures.append(message)
    replay=json.loads((ROOT/'results/independent_input_replay.json').read_text());expected={(r['arm'],r['step']):r for r in replay['records']}
    identities=json.loads((ROOT/'runs/photometry_initial/manifest.json').read_text())['records'];runs=[]
    for entry in identities:
        arm,seed=entry['arm'],entry['seed'];initial=Path(entry['path']);out=ROOT/'runs'/f'photo_{arm}_s{seed}'
        summary=json.loads((out/'summary.json').read_text());rows=[json.loads(s) for s in (out/'ledger.jsonl').read_text().splitlines()]
        require(sha(initial)==entry['sha256']==summary['initial_sha256'],f'{arm}/{seed} initial identity')
        require(len(rows)==128 and [r['step'] for r in rows]==list(range(1,129)),f'{arm}/{seed} exact128updates')
        require(sha(out/'ledger.jsonl')==summary['ledger_sha256'],f'{arm}/{seed} ledger identity')
        for row in rows:
            ref=expected[arm,row['step']]
            require(row['actual_input_sha256']==ref['actual_input_sha256'] and row['actual_input_shape']==ref['input_shape'],f'{arm}/{seed}/{row["step"]} independent actual input')
            require(row['window']['window']==ref['window'] and row['window']['core']==ref['core'],f'{arm}/{seed}/{row["step"]} physical context')
            require(row['source_original_arrays_sha256']==ref['source_arrays_sha256'] and not row['targets_enter_forward'],f'{arm}/{seed}/{row["step"]} source and forward role')
        before=torch.load(initial,map_location='cpu',weights_only=True);final=Path(summary['checkpoint']);after=torch.load(final,map_location='cpu',weights_only=True)
        require(sha(final)==summary['checkpoint_sha256'] and after['step']==128,f'{arm}/{seed} final checkpoint identity')
        require(after['model_config']==before['model_config'],f'{arm}/{seed} architecture unchanged')
        changed=[n for n,v in before['model_state'].items() if isinstance(v,torch.Tensor) and not n.startswith('observation.') and not torch.equal(v,after['model_state'][n])]
        require(set(changed)==set(summary['changed_parameters']) and bool(changed),f'{arm}/{seed} actual learned changes')
        require(not any(n.startswith('geometry_head.') for n in changed),f'{arm}/{seed} frozen geometry preserved')
        require(after['protocol_sha256']==before['protocol_sha256']==sha(ROOT/'config/photometry_pilot.json'),f'{arm}/{seed} protocol unchanged')
        require(all(sha(p)==h for p,h in after['implementation_sources'].items()),f'{arm}/{seed} executed source identities')
        require(after['optimizer_state']['state'] and all(int(v['step'])==128 for v in after['optimizer_state']['state'].values()),f'{arm}/{seed} optimizer actual steps')
        runs.append(dict(arm=arm,seed=seed,updates=128,changed=changed))
    for seed in [1265001,1265002]:
        a,b=[r for r in identities if r['seed']==seed]
        require(a['learned_hashes']==b['learned_hashes'],f'seed{seed} shared complete initial parameters')
    events=json.loads((ROOT/'runs/matrix_events.json').read_text());initial_events=[e for e in events if e['name'].startswith('real_') and e['name'].endswith('step0000')];train_events=[e for e in events if e['name'].startswith(('photo_P_','photo_Q_'))]
    require(len(initial_events)==4 and len(train_events)==4 and max(e['finished_unix'] for e in initial_events)<min(e['started_unix'] for e in train_events),'all initial real evaluations before first photometry update')
    require(all(e['exit_code']==0 and sha(e['log'])==e['sha256'] for e in events),'all matrix child runs and exact logs complete')
    files=0;real=[]
    for arm in ['P','Q']:
        for seed in [1265001,1265002]:
            for step in [0,128]:
                out=ROOT/'results'/f'real_{arm}_s{seed}_step{step:04d}';s=json.loads((out/'summary.json').read_text());binding=s['checkpoint_identity']
                require(s['status']=='bounded_real_pilot_evaluation_complete' and len(s['output_records'])==18,f'{arm}/{seed}/{step}18 real outputs')
                for r in s['output_records']:
                    p=r['output_float'];require(sha(p['path'])==p['sha256'],f'real output {p["path"]}');files+=1
                    with np.load(p['path']) as a:require(bool(np.isfinite(a['output']).all()),'finite real output')
                require(binding['panel_sha256']==sha(R125/'results/real_panel_v2/frozen_panel.json') and not binding['calibration_qualified'],f'{arm}/{seed}/{step} same real panel and unqualified optics')
                real.append(dict(arm=arm,seed=seed,step=step,summary_sha256=sha(out/'summary.json')))
    fixed=[]
    for report in ['fixed_example_summary.json','update_scale_summary.json']:
        for r in json.loads((ROOT/'results'/report).read_text())['runs']:
            out=ROOT/'runs'/r['run_id'];rows=[json.loads(s) for s in (out/'ledger.jsonl').read_text().splitlines()]
            require(len(rows)==128 and len(set(x['actual_input_sha256'] for x in rows))==1,f'{r["run_id"]} fixed inputs and128updates')
            require(sha(out/'step0128.pth')==r['checkpoint_sha256'] and sha(out/'ledger.jsonl')==r['ledger_sha256'],f'{r["run_id"]} exact checkpoint and ledger')
            with np.load(out/'outputs.npz') as a:mae=float(np.abs(a['output'].astype(float)-a['target'].astype(float)).mean()*255)
            require(abs(mae-r['after']['native_mae_gray'])<1e-5,f'{r["run_id"]} independently recomputed actual image error')
            fixed.append(dict(run_id=r['run_id'],actual_mae=mae,updates=128))
    for arm in ['A','B']:
        original=torch.load(ROOT/'runs'/f'fixed_{arm}_full'/'step0000.pth',map_location='cpu',weights_only=True)
        followup=torch.load(ROOT/'runs'/f'fixed_{arm}_full_lr001'/'step0000.pth',map_location='cpu',weights_only=True)
        require(original['model_config']==followup['model_config'] and original['training_source_manifest_sha256']==followup['training_source_manifest_sha256'],f'fixed{arm} update-scale intervention same model and data')
        require(all(torch.equal(v,followup['model_state'][n]) for n,v in original['model_state'].items() if isinstance(v,torch.Tensor)),f'fixed{arm} exact same initial tensors across update scales')
    source_checks=verify_protection();require(source_checks['unchanged'],'original R119 expectations and all R125 artifacts unchanged')
    comparison=json.loads((ROOT/'results/real_comparison/summary.json').read_text());require(comparison['sem_rows']==1152 and comparison['motion_rows']==48,'all8 common-population evaluations complete')
    result=dict(execution_integrity_passed=not failures,failures=failures,checks=checks,photometry_runs=runs,fixed_runs=fixed,verified_optimizer_updates=1280,independent_inputs_rebuilt=256,real_output_files_verified=files,real_evaluations=real,old_protection=source_checks,primary_sem_rows=1152,primary_motion_rows=48,model_adopted=False,calibration_qualified=False,scientific_success_not_inferred_from_execution=True)
    save(ROOT/'results/execution_audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['checks','photometry_runs','fixed_runs','real_evaluations']}),flush=True)
    if failures:raise RuntimeError('Execution reconciliation failed; preserved discrepancies')

if __name__=='__main__':main()

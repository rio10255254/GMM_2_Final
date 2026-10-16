"""Post-training reconciliation; never rewrites original evidence or expectations."""
import sys,json,math,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/final_review'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'recovery/20260909_progress_io_v1'))
from common import load,save,sha,record,now
from train import verify_binding
from run_child import verify_recovery
from training.data import Bank
from training.engine import lr_at
import torch,numpy as np

def main():
    start=time.perf_counter();OUT.mkdir(parents=True,exist_ok=True)
    cfg=load(ROOT/'config/study.json');verify_binding(load(ROOT/'config/frozen_training.json'));verify_recovery()
    manifest=load(ROOT/'data/package/manifest.json')
    for e in manifest['entries']:
        for key,hkey in [('arrays_path','arrays_sha256'),('metadata_path','metadata_sha256')]:
            assert sha(ROOT/'data/package'/e[key])==e[hkey]
    train_entries={e['parent_id']:e for e in manifest['entries'] if e['split']=='train'}
    bank=Bank();allrows={};audits=[];replay_total=0;max_formula_error=0.;outputs_checked=0
    for item in cfg['run_order']:
        name=f"{item['arm']}_s{item['seed']}";run=ROOT/'runs'/name
        done=load(run/'completion.json');assert done['completed_updates']==8192
        for rec in done['records']:assert sha(rec['path'])==rec['sha256']
        rows={};replay=0
        for p in sorted(run.glob('updates_*.jsonl')):
            for line in p.read_text(encoding='utf-8').splitlines():
                row=json.loads(line);step=row['update']
                assert math.isfinite(row['loss']) and math.isfinite(row['gradient_norm'])
                if step in rows:
                    keys=['arm','learning_rate','loss','terms','gradient_norm','actual_input_sha256','source_uint8_sha256','parent_id','parent_arrays_sha256','noise_seed','kernel_sha256','epoch','position']
                    assert all(row[k]==rows[step][k] for k in keys);replay+=1
                rows[step]=row
        assert sorted(rows)==list(range(1,8193))
        for step,row in rows.items():
            epoch=(step-1)//512;position=(step-1)%512;index=int(bank.order(epoch)[position])
            assert row['parent_id']==f'r128_train_{index:04d}' and row['epoch']==epoch and row['position']==position
            assert row['parent_arrays_sha256']==train_entries[row['parent_id']]['arrays_sha256']
            assert row['noise_seed']==[cfg['online_noise_seed'],epoch,index]
            assert row['learning_rate']==lr_at(step,cfg)
            value=sum(cfg['loss_weights'][k]*row['terms'][k] for k in cfg['loss_weights'])+cfg['arms'][item['arm']]['observation_loss_weight']*row['terms']['observation_noise_units']
            err=abs(value-row['loss'])/max(1,abs(value));max_formula_error=max(max_formula_error,err);assert err<1e-5
        cp=torch.load(run/'checkpoints/step8192.pth',map_location='cpu')
        assert cp['step']==8192 and cp['arm']==item['arm'] and cp['seed']==item['seed']
        assert all(int(v['step'])==8192 for v in cp['optimizer']['state'].values())
        h=hashlib.sha256()
        for k,v in cp['model'].items():h.update(k.encode());h.update(v.contiguous().numpy().tobytes())
        assert h.hexdigest()==cp['parameter_sha256']==done['final_parameter_sha256']
        assert not any(s in k for k in cp['model'] for s in ['observation','geometry','confidence'])
        generated=[]
        for split,steps in [('dev',cfg['dev_checkpoints']),('test',[8192])]:
            for step in steps:
                v=load(run/'evaluations'/f'{split}_step{step:04d}.json')
                assert len(v['rows'])==128 and len({x['parent_id'] for x in v['rows']})==128
                assert all(x['parent_id'].startswith('r128_'+split+'_') for x in v['rows'])
                generated.append(dict(split=split,step=step,parents=128))
        real=[]
        for step in [1024,4096,8192]:
            v=load(run/'evaluations'/f'real_step{step:04d}'/'verification.json')
            assert v['completed'] and v['SEM_rows']==72 and v['motion_pairs']==6
            for p,h in v['output_sha256'].items():assert sha(p)==h;outputs_checked+=1
            real.append(dict(step=step,images=18,SEM_rows=72,motion_pairs=6))
        audits.append(dict(run=name,unique_updates=8192,replayed_calls=replay,checkpoint=record(run/'checkpoints/step8192.pth'),generated_evaluations=generated,real_evaluations=real,completion=record(run/'completion.json')))
        replay_total+=replay;allrows[name]=rows
        print(json.dumps(dict(audited=name,replayed_calls=replay)),flush=True)
    reference=allrows['I_s1285001'];match_keys=['actual_input_sha256','source_uint8_sha256','parent_id','parent_arrays_sha256','noise_seed','kernel_sha256','learning_rate','epoch','position']
    for name,rows in allrows.items():
        assert all(all(rows[s][k]==reference[s][k] for k in match_keys) for s in reference)
    checks=[]
    # Deterministically spread spot checks over all16passes; all8192logged inputs
    # have already been reconciled across arms and the frozen scene/order map.
    for epoch in range(16):
        for position in [0,127,255,511]:
            step=epoch*512+position+1;index=int(bank.order(epoch)[position]);b=bank.batch('train',index,'cpu',epoch)
            assert b['cpu_input_sha256']==reference[step]['actual_input_sha256']
            checks.append(dict(step=step,parent=b['metadata']['parent_id'],exact=True))
    protected=load(ROOT/'config/protected_before.json');changed=[p for p,h in protected.items() if sha(p)!=h];assert not changed,changed
    result=dict(passed=True,verified_utc=now(),unique_training_updates=32768,replayed_calls_not_counted_twice=replay_total,total_full_training_optimizer_calls=32768+replay_total,all_four_runs_same_actual_inputs_and_order=True,independently_rebuilt_actual_inputs=checks,maximum_loss_formula_relative_error=max_formula_error,all768_data_files_and_metadata_unchanged=True,historical_protected_files_unchanged=len(protected),real_output_files_verified=outputs_checked,runs=audits,completed_UTC=load(ROOT/'results/full_training_execution_complete.json')['updated_utc'],source=record(__file__),seconds=time.perf_counter()-start,scientific_effectiveness_not_implied_by_execution=True)
    save(OUT/'execution_audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['runs','independently_rebuilt_actual_inputs']}),flush=True)

if __name__=='__main__':main()

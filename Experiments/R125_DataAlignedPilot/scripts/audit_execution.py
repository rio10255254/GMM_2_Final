"""Independent CPU-only execution audit of the bounded six-run R125 matrix.

No run, checkpoint, data, source, expected hash, or ledger is edited. Completion
requires actual input reconstruction, checkpoint/optimizer evidence, initial
tensor matching, frozen source identity, and real-evaluation artifacts together.
This is an execution-integrity audit, not an efficacy or promotion decision.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
HASH_CACHE={}


def sha(path):
    path=Path(path);stat=path.stat();key=(str(path.resolve()),stat.st_size,stat.st_mtime_ns)
    if key in HASH_CACHE:return HASH_CACHE[key]
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    HASH_CACHE[key]=h.hexdigest()
    return HASH_CACHE[key]


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def array_hash(array):return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()
def tensor_hash(tensor):return array_hash(tensor.detach().cpu().contiguous().numpy())
def learned(state):return {name:value for name,value in state.items() if isinstance(value,torch.Tensor) and not name.startswith('observation.')}
def finite(value):return isinstance(value,(int,float)) and math.isfinite(value)


def expected_window(config,metadata):
    radius=(len(metadata['profile']['kernel']['values'])-1)//2
    m=config['model'];s=m['sampling_factor']
    prior_radius=2*(2+2*sum(m['dilations']))+1
    unrounded=math.ceil(m['iterations']*(3*(radius+s-1)+prior_radius)/s)+3
    model_halo=math.ceil(unrounded/16)*16
    motion=math.ceil(max(abs(float(v)) for v in metadata['shift_xy'])) if metadata['motion_observable'] else 0
    halo=math.ceil((model_halo+math.ceil(radius/s)+motion+2)/16)*16
    if halo>256:raise ValueError('The generated context cannot cover the objective')
    return [256-halo,384+halo,256-halo,384+halo],[halo,halo+128,halo,halo+128]


class Audit:
    def __init__(self):self.failures=[];self.pending=[]
    def require(self,condition,scope,reason,actual=None):
        if not condition:self.failures.append({'scope':scope,'reason':reason,'actual':actual})
        return bool(condition)
    def hash_record(self,record,scope):
        try:
            path=Path(record['path'])
            return self.require(path.is_file() and sha(path)==record['sha256'],scope,'artifact_hash_mismatch',str(path))
        except Exception as exc:
            self.require(False,scope,'artifact_unreadable',repr(exc));return False


def source_interface(audit):
    path=ROOT/'training/train_pilot.py';tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    forward=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='forward_details']
    objectives=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='objective']
    good=len(forward)==1 and len(objectives)==1 and len(forward[0].args)==1 and isinstance(forward[0].args[0],ast.Name) and forward[0].args[0].id=='source' and forward[0].lineno<objectives[0].lineno
    audit.require(good,'source_interface','model_forward_not_source_only_before_objective')
    return {'trainer_sha256':sha(path),'forward_calls':[{'line':x.lineno,'call':ast.unparse(x)} for x in forward],
            'objective_lines':[x.lineno for x in objectives],'source_only_forward_then_targets_in_objective':good,
            'independent_data_flow_evidence':'Every actual forward input hash is independently reconstructed from uint8 source pixels and the logged physical crop, without target arrays.'}


def inspect_data(config,audit):
    package=ROOT/'data/package_v2';manifest_path=package/'manifest.json';manifest=load(manifest_path);mh=sha(manifest_path)
    admission=load(ROOT/'results/data_audit_v2.json')
    audit.require(admission.get('pilot_admitted') is True and admission.get('manifest_sha256')==mh,'data','exact_package_not_admitted')
    audit.require(len(manifest['scenes'])==64,'data','wrong_scene_count',len(manifest['scenes']))
    rows={}
    for entry in manifest['scenes']:
        scope='data/'+entry['scene_id'];ap=(package/entry['arrays_path']).resolve();mp=(package/entry['metadata_path']).resolve()
        audit.require(ap.is_relative_to(package.resolve()) and mp.is_relative_to(package.resolve()),scope,'path_escapes_package')
        audit.require(sha(ap)==entry['sha256']['arrays'] and sha(mp)==entry['sha256']['metadata'],scope,'data_or_metadata_changed')
        meta=load(mp)
        with np.load(ap,allow_pickle=False) as saved:source=saved['source']
        audit.require(source.shape==(2,640,640) and source.dtype==np.uint8,scope,'invalid_actual_source_schema')
        window,core=expected_window(config,meta);y0,y1,x0,x1=window
        actual=(source.astype(np.float32)/np.float32(255))[:,None,y0:y1,x0:x1]
        kernel=np.asarray(meta['profile']['kernel']['values'],dtype=np.float32)
        if meta['profile']['kernel_convention']=='physical_psf':kernel=kernel[::-1,::-1]
        original_hashes=[array_hash(source[v]) for v in range(2)]
        audit.require(original_hashes==meta['source_original_sha256'],scope,'original_source_view_hashes_mismatch')
        rows[entry['scene_id']]={'entry':entry,'metadata':meta,'actual_forward_input_sha256':array_hash(actual),
             'actual_input_shape':list(actual.shape),'physical_window':window,'local_core':core,
             'actual_kernel_sha256':array_hash(kernel),'original_source_sha256':original_hashes}
    expected_order=[manifest['scenes'][i]['scene_id'] for i in np.random.default_rng(config['sample_order_seed']).permutation(64)]
    return manifest,mh,rows,expected_order


def inspect_initializations(config,mh,audit):
    initial_manifest=load(ROOT/'runs/initializations/manifest.json')
    audit.require(initial_manifest['training_manifest_sha256']==mh,'initializations','wrong_data_binding')
    audit.require(len(initial_manifest['records'])==6,'initializations','expected_six_initializations')
    payloads={};records={};banks={};source_bank=None
    for record in initial_manifest['records']:
        label=f"{record['arm']}_s{record['seed']}";scope='initial/'+label
        audit.hash_record(record,scope)
        ck=torch.load(record['path'],map_location='cpu',weights_only=True)
        tensors=learned(ck['model_state']);hashes={k:tensor_hash(v) for k,v in tensors.items()}
        audit.require(ck['step']==0 and ck['optimizer_state'] is None,scope,'initial_checkpoint_is_not_untrained_step0')
        audit.require(ck['arm']==record['arm'] and ck['seed']==record['seed'],scope,'arm_seed_identity_mismatch')
        audit.require(ck['model_config']['observation_steps']==config['arms'][record['arm']]['observation_steps'],scope,'initial_arm_mechanism_wrong')
        audit.require(ck['training_source_manifest_sha256']==mh and ck['pilot_config_sha256']==sha(ROOT/'config/pilot.json'),scope,'data_or_protocol_changed')
        audit.require(hashes==record['shared_non_observation_tensor_hashes'],scope,'recorded_initial_tensor_hashes_wrong')
        audit.require(all(torch.isfinite(v).all().item() for v in tensors.values()),scope,'nonfinite_initial_weights')
        if record['seed'] in banks:audit.require(hashes==banks[record['seed']],scope,'shared_initial_tensors_differ_between_arms')
        else:banks[record['seed']]=hashes
        implementation=ck['implementation_source_sha256']
        if source_bank is None:source_bank=implementation
        else:audit.require(implementation==source_bank,scope,'initial_implementation_identities_differ')
        for path,expected in implementation.items():audit.require(sha(path)==expected,scope,'implementation_changed',path)
        payloads[label]=ck;records[label]=record
    audit.require(len(banks)==2 and banks.get(config['model_seeds'][0])!=banks.get(config['model_seeds'][1]),'initializations','two_model_seeds_not_distinct')
    return payloads,records,source_bank


def inspect_evaluation(label,step,checkpoint_path,expected_ck_hash,mh,panel_hash,audit):
    folder=ROOT/'results'/f'real_{label}_step{step:04d}';path=folder/'summary.json';scope='evaluation/'+folder.name
    if not path.exists():audit.pending.append(scope);return None
    summary=load(path);identity=summary['checkpoint_identity'];bound=identity['checkpoint']
    audit.require(summary.get('status')=='bounded_real_pilot_evaluation_complete',scope,'evaluation_not_complete')
    audit.require(identity['step']==step and bound['sha256']==expected_ck_hash and Path(bound['path']).resolve()==Path(checkpoint_path).resolve(),scope,'wrong_checkpoint_binding')
    audit.hash_record(bound,scope)
    audit.require(identity['training_source_manifest_sha256']==mh and identity['panel_sha256']==panel_hash,scope,'data_or_real_panel_binding_differs')
    audit.require(identity['observation_rebound']['sha256']==sha(ROOT/'config/real_observation_v2.json'),scope,'real_profile_changed_or_last_training_profile_used')
    audit.require(summary['full_image_outputs']==6 and summary['motion_context_outputs']==12 and len(summary['output_records'])==18,scope,'wrong_real_output_population')
    for record in summary['output_records']:
        audit.hash_record(record['source'],scope)
        audit.hash_record(record['output_float'],scope)
        with np.load(record['output_float']['path'],allow_pickle=False) as saved:output=saved['output']
        audit.require(list(output.shape)==record['shape_hw'] and output.dtype==np.float32 and np.isfinite(output).all(),scope,'invalid_real_image_output',record['output_float']['path'])
    with (folder/'sem/per_pillar.csv').open(encoding='utf-8-sig',newline='') as stream:sem_rows=sum(1 for _ in csv.DictReader(stream))
    audit.require(sem_rows==288==summary['sem']['rows'] and summary['sem']['raw_parity_cases']==144,scope,'incomplete_SEM_comparison_population')
    audit.require(len(summary['motion'])==6,scope,'incomplete_motion_population')
    for record in load(folder/'protected_sources_before.json'):audit.hash_record(record,scope+'/protected')
    audit.require(summary['protected_sources_unchanged'] is True,scope,'evaluation_reported_source_change')
    audit.require(not summary['scientific_promotion'] and not summary['calibration_qualified'] and not summary['new_holdout'],scope,'unsupported_promotion_or_calibration_claim')
    return {'path':str(path),'sha256':sha(path),'completed_utc':summary['completed_utc'],'checkpoint_sha256':expected_ck_hash,
            'actual_output_files_checked':18,'actual_SEM_rows':sem_rows,'motion_pairs':len(summary['motion']),
            'learned_tensor_sha256':identity['learned_tensor_sha256'],'calibration_qualified':False,'scientific_promotion':False}


def inspect_run(label,arm,seed,config,mh,data,order,initial,record,source_bank,panel_hash,audit):
    folder=ROOT/'runs'/label;summary_path=folder/'summary.json';scope='run/'+label
    if not summary_path.exists():audit.pending.append(scope);return None
    before_failure_count=len(audit.failures);summary=load(summary_path)
    ledger_path=folder/'sample_ledger.jsonl'
    lines=ledger_path.read_text(encoding='utf-8').splitlines();ledger=[json.loads(line) for line in lines]
    audit.require(len(ledger)==64,scope,'ledger_does_not_have64_updates',len(ledger))
    audit.require([r['optimizer_update'] for r in ledger]==list(range(1,65)),scope,'optimizer_update_sequence_wrong')
    ids=[r['scene_id'] for r in ledger]
    audit.require(ids==order and len(set(ids))==64,scope,'scene_order_changed_or_repeated')
    audit.require(sum(r['view_count'] for r in ledger)==128,scope,'wrong_view_count')
    for row in ledger:
        sid=row['scene_id'];s=scope+'/'+str(row['optimizer_update']);expected=data[sid];meta=expected['metadata'];entry=expected['entry']
        checks={
          'forward_input_hash':row['actual_forward_input_sha256']==expected['actual_forward_input_sha256'],
          'forward_input_shape':row['actual_input_shape']==expected['actual_input_shape'],
          'source_hashes':row['source_arrays_sha256']==entry['sha256']['arrays'] and row['source_metadata_sha256']==entry['sha256']['metadata'],
          'original_source_view_hashes':row['source_original_sha256']==expected['original_source_sha256'],
          'original_kernel_hash':row['actual_observation_original_kernel_sha256']==expected['actual_kernel_sha256'],
          'physical_window':row['physical_window_in_generated_scene']==expected['physical_window'],
          'same128_supervision':row['supervised_core_in_forward_input']==expected['local_core'],
          'generated640_source':row['generated_source_shape']==[2,1,640,640],
          'same_pair_profile':row['observation_profile']==meta['profile'] and row['view_count']==2,
          'physical_motion':row['shift_xy']==meta['shift_xy'],
          'new_source_ancestry':row['source_ancestors']==meta['source_ancestors'] and row['parent_latent_id']==meta['parent_latent_id'],
          'condition_metadata':row['photometry']==meta['photometry'] and row['core_stats']==meta['core_stats'] and row['category']==meta['category'],
          'seed_identity':row['model_seed']==seed and row['sample_order_seed']==config['sample_order_seed'] and row['data_seed']==meta['effective_seed'],
          'source_only_model_input':row['model_forward_inputs']==['source','known_simulation_profile'] and row['target_fields_enter_forward'] is False,
          'declared_arm':row['active_modules']=={'prior':True,**config['arms'][arm]},
        }
        for name,ok in checks.items():audit.require(ok,s,name+'_mismatch')
        terms=row['loss_components'];weighted=sum(config['loss_weights'][k]*v for k,v in terms.items())
        audit.require(set(terms)==set(config['loss_weights']) and all(finite(v) and v>=0 for v in terms.values()),s,'invalid_or_missing_loss_components')
        audit.require(math.isclose(weighted,row['weighted_loss'],rel_tol=2e-6,abs_tol=1e-5),s,'weighted_loss_does_not_match_frozen_weights')
        audit.require(finite(row['gradient_norm_before_clip']) and row['gradient_norm_before_clip']>=0,s,'invalid_gradient_norm')
        if arm in ('A','B'):audit.require(all(terms[k]==0 for k in terms if k.startswith('geometry_')),s,'geometry_loss_enabled_in_control')
        factor=row['operator_implementation']
        audit.require(factor['original_kernel_retained'] is True and factor['exact_original_kernel_claimed'] is False and factor['kernel_L1_tolerance']==1e-6 and factor['measured_kernel_L1_error']<=1e-6,s,'unbounded_or_refitted_operator')
    checkpoint=Path(summary['checkpoint']);audit.require(sha(checkpoint)==summary['checkpoint_sha256'],scope,'final_checkpoint_changed')
    audit.require(sha(ledger_path)==summary['ledger_sha256'],scope,'ledger_changed_since_completion')
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True)
    audit.require(ck['step']==64 and ck['seed']==seed and ck['arm']==arm,scope,'final_checkpoint_identity_wrong')
    audit.require(ck['model_config']['observation_steps']==config['arms'][arm]['observation_steps'],scope,'final_arm_mechanism_wrong')
    audit.require(ck['formal_promotion'] is False and ck['real_calibration_qualified'] is False and ck['uncertainty_calibrated'] is False,scope,'unsupported_checkpoint_qualification')
    audit.require(ck['training_source_manifest_sha256']==mh and ck['initial_checkpoint_sha256']==record['sha256'],scope,'final_data_or_initial_binding_wrong')
    audit.require(ck['pilot_config_sha256']==sha(ROOT/'config/pilot.json') and ck['implementation_source_sha256']==source_bank,scope,'protocol_or_source_changed_during_runs')
    for path,expected in ck['implementation_source_sha256'].items():audit.require(sha(path)==expected,scope,'current_implementation_mismatch',path)
    first,last=learned(initial['model_state']),learned(ck['model_state'])
    audit.require(set(first)==set(last) and all(torch.isfinite(v).all().item() for v in last.values()),scope,'learned_tensor_schema_or_finiteness_wrong')
    changed=[name for name in first if not torch.equal(first[name],last[name])]
    audit.require(set(changed)==set(summary['changed_parameter_names']) and bool(changed),scope,'reported_parameter_changes_wrong')
    geometry=[name for name in first if name.startswith('geometry_head.')]
    audit.require(('prior.head.weight' in changed),scope,'reconstruction_head_did_not_learn')
    if arm=='A':audit.require('observation_logits' not in changed,scope,'A_observation_step_logits_changed')
    if arm in ('A','B'):audit.require(not any(name in changed for name in geometry),scope,'control_geometry_parameters_changed')
    if arm=='C':audit.require(any(name in changed for name in geometry),scope,'C_geometry_parameters_did_not_change')
    active=[name for name in first if not (arm=='A' and name=='observation_logits') and not (arm in ('A','B') and name in geometry)]
    optimizer=ck['optimizer_state'];param_ids=[pid for group in optimizer['param_groups'] for pid in group['params']]
    audit.require(len(param_ids)==len(active) and len(set(param_ids))==len(active),scope,'optimizer_parameter_membership_wrong')
    audit.require(set(optimizer['state'])==set(param_ids),scope,'missing_optimizer_parameter_history')
    steps=[float(optimizer['state'][pid]['step']) for pid in param_ids]
    audit.require(all(step==64 for step in steps),scope,'optimizer_steps_not64',sorted(set(steps)))
    for name,pid in zip(active,param_ids):
        state=optimizer['state'][pid]
        audit.require(state['exp_avg'].shape==last[name].shape and torch.isfinite(state['exp_avg']).all().item() and torch.isfinite(state['exp_avg_sq']).all().item(),scope,'optimizer_moment_shape_or_finiteness_wrong',name)
    for group in optimizer['param_groups']:
        audit.require(group['lr']==config['optimizer']['lr'] and group['weight_decay']==config['optimizer']['weight_decay'],scope,'optimizer_hyperparameters_changed')
    last_profile=data[order[-1]]['metadata']['profile'];os=ck['model_state'];extra=os['observation._extra_state']
    audit.require(tensor_hash(os['observation.kernel'])==data[order[-1]]['actual_kernel_sha256'] and extra['calibration_id']==last_profile['calibration_id'],scope,'last_simulation_profile_binding_wrong')
    implemented=os['observation.vertical_factors'].double().T@os['observation.horizontal_factors'].double()
    actual_error=float((implemented-os['observation.kernel'].double()).abs().sum())
    audit.require(actual_error<=1e-6 and math.isclose(actual_error,extra['factorization']['measured_kernel_L1_error'],abs_tol=1e-12,rel_tol=0),scope,'final_factorization_record_mismatch')
    evaluation=inspect_evaluation(label,64,checkpoint,summary['checkpoint_sha256'],mh,panel_hash,audit)
    return {'label':label,'ledger_rows':len(ledger),'unique_scenes':len(set(ids)),'views':sum(r['view_count'] for r in ledger),
            'input_hashes_reconstructed_and_matched':all(row['actual_forward_input_sha256']==data[row['scene_id']]['actual_forward_input_sha256'] for row in ledger),
            'same_scene_order':ids==order,'checkpoint_sha256':summary['checkpoint_sha256'],'ledger_sha256':summary['ledger_sha256'],
            'actual_changed_parameter_names':changed,'optimizer_parameter_count':len(active),'optimizer_steps':sorted(set(steps)),
            'real_evaluation':evaluation,'failure_count':len(audit.failures)-before_failure_count}


def run_audit(final=False,output_path=None):
    torch.set_num_threads(2);audit=Audit();started=time.monotonic();config=load(ROOT/'config/pilot.json')
    manifest,mh,data,order=inspect_data(config,audit)
    initial,initial_records,source_bank=inspect_initializations(config,mh,audit)
    panel_hash=sha(ROOT/config['real_panel']);labels=[f'{arm}_s{seed}' for seed in config['model_seeds'] for arm in config['arms']]
    initial_evals=[];runs=[]
    for label in labels:
        record=initial_records[label]
        initial_evals.append(inspect_evaluation(label,0,record['path'],record['sha256'],mh,panel_hash,audit))
    for seed in config['model_seeds']:
        for arm in config['arms']:
            label=f'{arm}_s{seed}';result=inspect_run(label,arm,seed,config,mh,data,order,initial[label],initial_records[label],source_bank,panel_hash,audit)
            if result:runs.append(result)
            print(json.dumps({'run':label,'completed_artifacts_audited':result is not None,'failures_so_far':len(audit.failures),'pending':len(audit.pending)}),flush=True)
    matrix=load(ROOT/'runs/matrix_state.json');events=matrix['events'];stages=[e['stage'] for e in events]
    expected=['matrix_initializations']+['eval_'+label+'_step0000' for label in labels]
    for label in labels:expected+=['train_'+label,'eval_'+label+'_step0064']
    expected+=['aggregate_real']
    audit.require(stages==expected[:len(stages)] and len(stages)<=len(expected),'matrix','stage_order_differs_from_serialized_plan')
    audit.require(all(e['returncode']==0 for e in events),'matrix','stage_returned_failure')
    for event in events:audit.require(Path(event['log']).is_file() and Path(event['log']).stat().st_size>0,'matrix','missing_stage_execution_log',event['stage'])
    first_training=next((i for i,s in enumerate(stages) if s.startswith('train_')),None)
    all_initial_before_training=first_training is not None and set(stages[:first_training])==set(expected[:7]) and all(e is not None for e in initial_evals)
    audit.require(all_initial_before_training,'matrix','all_initial_real_evaluations_not_proven_before_training')
    log_birth=None;latest_initial=None
    if all_initial_before_training:
        log_path=Path(events[first_training]['log']);stat=log_path.stat();log_birth=getattr(stat,'st_birthtime',stat.st_ctime)
        latest_initial=max(datetime.fromisoformat(e['completed_utc']).timestamp() for e in initial_evals)
        audit.require(latest_initial<=log_birth,'matrix','initial_evaluation_timestamp_after_first_training_log_creation',{'latest_initial':latest_initial,'first_training_log_creation':log_birth})
    aggregate_path=ROOT/'results/real_comparison/summary.json'
    if aggregate_path.exists():audit.require(load(aggregate_path).get('status')=='bounded_real_pilot_comparison_complete','matrix','real_aggregation_not_complete')
    else:audit.pending.append('real_aggregation')
    complete=matrix.get('status')=='bounded_matrix_completed_not_promoted' and len(stages)==len(expected) and len(runs)==6 and not audit.pending
    if final:audit.require(complete,'matrix','matrix_not_fully_complete',matrix.get('status'))
    report={'schema_version':1,'completed_utc':datetime.now(timezone.utc).isoformat(),'scope':'execution integrity only; no efficacy promotion',
            'audit_implementation_sha256':sha(Path(__file__)),
            'manifest_sha256':mh,'protocol_sha256':sha(ROOT/'config/pilot.json'),'frozen_real_panel_sha256':panel_hash,
            'implementation_source_sha256':source_bank,'source_interface_review':source_interface(audit),
            'unique_actual_source_pairs_reconstructed':64,'expected_common_scene_order':order,
            'independently_recomputed_forward_inputs':[{key:row[key] for key in ('actual_forward_input_sha256','actual_input_shape','physical_window','local_core','actual_kernel_sha256')}|{'scene_id':sid} for sid,row in data.items()],
            'initial_shared_tensor_equality_by_seed_checked':True,'initial_evaluations':initial_evals,'runs':runs,
            'matrix_events_verified':events,'initial_evaluations_before_any_training':all_initial_before_training,
            'latest_initial_completed_epoch':latest_initial,'first_training_log_created_epoch':log_birth,
            'completed_optimizer_updates_verified':sum(r['ledger_rows'] for r in runs),
            'all_runs_complete':complete,'pending':audit.pending,'failures':audit.failures,
            'execution_integrity_passed':complete and not audit.failures,
            'calibration_qualified':False,'scientific_promotion':False,'unseen_holdout_claimed':False,
            'limitations':['Current and captured checkpoint source identities are compared; this is not continuous filesystem surveillance.',
                           'Real output files, bindings, populations and protected inputs are checked; efficacy conclusions require the separate scientific readout.',
                           'Scene input pixels are recomputed once for all64 shared scenes, then matched against all384 ledger entries.'],
            'elapsed_seconds':time.monotonic()-started}
    if final:
        if not complete and matrix.get('status') not in ('failed','bounded_matrix_completed_not_promoted'):
            print(json.dumps({'status':'still_running_no_final_report_written','failures':audit.failures,'pending':audit.pending}))
            return report
        destination=Path(output_path) if output_path is not None else ROOT/'results/execution_audit.json'
        encoded=json.dumps(report,indent=2,allow_nan=False)
        with destination.open('x',encoding='utf-8') as stream:stream.write(encoded)
    return report


def self_test():
    config={'model':{'sampling_factor':4,'dilations':[1,2,4,2],'iterations':4}}
    meta={'profile':{'kernel':{'values':[[1.0]]}},'shift_xy':[0,0],'motion_observable':True}
    assert expected_window(config,meta)==([176,464,176,464],[80,208,80,208])
    source=np.arange(2*8*8,dtype=np.uint8).reshape(2,8,8)
    normalized=source.astype(np.float32)/np.float32(255)
    assert array_hash(normalized)!=array_hash(source)
    a=Audit();assert not a.require(False,'fixture','injected_failure') and len(a.failures)==1
    print('execution audit self-tests passed')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');parser.add_argument('--self-test',action='store_true');parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.self_test:self_test();raise SystemExit(0)
    result=run_audit(args.final,args.output)
    print(json.dumps({'execution_integrity_passed':result['execution_integrity_passed'],'completed_updates':result['completed_optimizer_updates_verified'],
                      'completed_runs':len(result['runs']),'pending':result['pending'],'failures':result['failures']},indent=2))
    raise SystemExit(0 if not result['failures'] and (not args.final or result['execution_integrity_passed']) else 2)

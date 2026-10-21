"""Source-bound, bounded64-update training; old prototype code remains immutable."""
from __future__ import annotations
import argparse,hashlib,json,os,sys,time,traceback
from pathlib import Path
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent/'R124_RealFirstPrototype'
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from model.network import build_model
from model.calibration import load_observation,observation_from_profile
from training.objectives import objective

CFG=json.loads((ROOT/'config/pilot.json').read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def digest_tensor(t):return hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
def write_json(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf-8')
def model_config(arm):return {**CFG['model'],'observation_steps':CFG['arms'][arm]['observation_steps']}
def new_model(arm,seed,device='cpu'):
    torch.manual_seed(seed)
    return build_model(model_config(arm),load_observation(BASE/'config/gaussian_diagnostic.json',device)).to(device)
def artifact(model,arm,seed,step,manifest_hash,initial_hash,optimizer=None):
    return {'schema_version':1,'kind':'bounded_exploratory_model','arm':arm,'model_seed':seed,'seed':seed,'step':step,
            'model_config':model.config_dict(),'model_state':{k:v.detach().cpu() if isinstance(v,torch.Tensor) else v for k,v in model.state_dict().items()},
            'optimizer_state':optimizer.state_dict() if optimizer is not None else None,
            'training_source_manifest_sha256':manifest_hash,'initial_checkpoint_sha256':initial_hash,
            'pilot_config_sha256':sha(ROOT/'config/pilot.json'),'observation_qualification':'unqualified_diagnostic',
            'real_calibration_qualified':False,'uncertainty_calibrated':False,'formal_promotion':False,
            'note':'Observation buffers are last simulation condition. Real evaluation must explicitly bind the frozen diagnostic real profile and load learned tensors only.'}

def prepare(package):
    manifest=Path(package)/'manifest.json';mh=sha(manifest);out=ROOT/'runs/initializations';out.mkdir(exist_ok=False)
    records=[]
    for seed in CFG['model_seeds']:
        common=new_model('B',seed);common_state=common.state_dict();hashes={k:digest_tensor(v) for k,v in common_state.items() if isinstance(v,torch.Tensor) and not k.startswith('observation.')}
        for arm in CFG['arms']:
            model=new_model(arm,seed);model.load_state_dict(common_state,strict=True)
            current={k:digest_tensor(v) for k,v in model.state_dict().items() if isinstance(v,torch.Tensor) and not k.startswith('observation.')};assert current==hashes
            p=out/f'{arm}_s{seed}_step0000.pth'
            with p.open('xb') as f:torch.save(artifact(model,arm,seed,0,mh,None),f)
            records.append({'arm':arm,'seed':seed,'path':str(p),'sha256':sha(p),'shared_non_observation_tensor_hashes':hashes})
    write_json(out/'manifest.json',{'status':'all_initial_tensors_matched_by_seed','training_manifest_sha256':mh,'records':records})
    print(json.dumps({'initializations':len(records),'output':str(out)}),flush=True)

def run(package,arm,seed,audit_path):
    package=Path(package);manifest_path=package/'manifest.json';manifest=json.loads(manifest_path.read_text());mh=sha(manifest_path)
    audit=json.loads(Path(audit_path).read_text(encoding='utf-8-sig'))
    # An explicit audit admission token is written only after all predefined
    # numerical/structural source checks, not inferred from file existence.
    if audit.get('pilot_admitted') is not True or audit.get('manifest_sha256')!=mh:
        raise ValueError('Data audit does not admit this exact package for the known-simulation pilot')
    initial=ROOT/'runs/initializations'/f'{arm}_s{seed}_step0000.pth';init_hash=sha(initial);payload=torch.load(initial,map_location='cpu',weights_only=True)
    if payload['training_source_manifest_sha256']!=mh:raise ValueError('Initialization binds a different data manifest')
    assert len(manifest['scenes'])==CFG['updates_per_run']==64
    out=ROOT/'runs'/f'{arm}_s{seed}';out.mkdir(exist_ok=False);(out/'checkpoints').mkdir()
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(2);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    model=new_model(arm,seed,device);model.load_state_dict(payload['model_state'],strict=True);model.research_status='exploratory_training'
    model.observation_logits.requires_grad_(CFG['arms'][arm]['observation_steps'])
    for p in model.geometry_head.parameters():p.requires_grad_(CFG['arms'][arm]['geometry_losses'])
    parameters=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(parameters,lr=CFG['optimizer']['lr'],weight_decay=CFG['optimizer']['weight_decay'])
    order=np.random.default_rng(CFG['sample_order_seed']).permutation(len(manifest['scenes'])).tolist()
    initial_parameters={n:digest_tensor(p) for n,p in model.named_parameters()}
    state={'status':'running','arm':arm,'seed':seed,'planned_updates':64,'completed_updates':0,'manifest_sha256':mh,'initial_sha256':init_hash,'device':device,'formal_promotion':False,'real_calibration_qualified':False}
    write_json(out/'state.json',state);ledger=out/'sample_ledger.jsonl';started=time.perf_counter()
    try:
        with ledger.open('x',encoding='utf-8') as log:
            for step,index in enumerate(order,1):
                entry=manifest['scenes'][index];ap=(package/entry['arrays_path']).resolve();mp=(package/entry['metadata_path']).resolve()
                if not ap.is_relative_to(package.resolve()) or not mp.is_relative_to(package.resolve()):raise ValueError('Package path escapes root')
                if sha(ap)!=entry['sha256']['arrays'] or sha(mp)!=entry['sha256']['metadata']:raise ValueError('Training source changed')
                meta=json.loads(mp.read_text());assert meta['external_training_inputs']==[] and meta['existing_test_answer_access'] is False
                with np.load(ap) as d:
                    source=torch.from_numpy(d['source'].astype(np.float32)/255)[:,None].to(device)
                    arrays={k:torch.from_numpy(d[k])[:,None].to(device) for k in ['target','latent_target','sdf','boundary']}
                model.observation=observation_from_profile(meta['profile'],device)
                if model.required_halo>256:raise ValueError('Generated context does not cover this actual model')
                model.train();optimizer.zero_grad(set_to_none=True);torch.cuda.reset_peak_memory_stats() if device=='cuda' else None
                t=time.perf_counter();details=model.forward_details(source,trace=False)
                loss,terms=objective(model,details,source,arrays,meta,CFG['loss_weights'],CFG['arms'][arm]['geometry_losses'])
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite training loss')
                loss.backward()
                if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in parameters):raise FloatingPointError('Nonfinite gradient')
                grad=float(torch.nn.utils.clip_grad_norm_(parameters,CFG['optimizer']['gradient_clip_norm']))
                optimizer.step()
                if any(not torch.isfinite(p).all() for p in parameters):raise FloatingPointError('Nonfinite learned parameter')
                row={'run_id':f'{arm}_s{seed}','optimizer_update':step,'loader_id':'single_new_procedural_pair','scene_id':meta['scene_id'],'category':meta['category'],'parent_latent_id':meta['parent_latent_id'],'source_ancestors':meta['source_ancestors'],'source_arrays_sha256':entry['sha256']['arrays'],'source_metadata_sha256':entry['sha256']['metadata'],'source_original_sha256':meta['source_original_sha256'],'data_seed':meta['effective_seed'],'model_seed':seed,'sample_order_seed':CFG['sample_order_seed'],'split':'new_procedural_training','view_count':2,'actual_input_shape':list(source.shape),'core_stats':meta['core_stats'],'shift_xy':meta['shift_xy'],'observation_profile':meta['profile'],'photometry':meta['photometry'],'target_truth_kind':'independent4x_procedural_optical_intensity_and_geometry','model_forward_inputs':['source','known_simulation_profile'],'target_fields_enter_forward':False,'loss_components':{k:float(v.detach()) for k,v in terms.items()},'weighted_loss':float(loss.detach()),'active_modules':{'prior':True,'observation_steps':CFG['arms'][arm]['observation_steps'],'geometry_losses':CFG['arms'][arm]['geometry_losses']},'gradient_norm_before_clip':grad,'peak_allocated_gib':torch.cuda.max_memory_allocated()/2**30 if device=='cuda' else None,'elapsed_seconds':time.perf_counter()-t}
                log.write(json.dumps(row,allow_nan=False)+'\n');log.flush();os.fsync(log.fileno())
                state.update(completed_updates=step,last_scene_id=meta['scene_id'],last_loss=row['weighted_loss'],elapsed_seconds=time.perf_counter()-started);write_json(out/'state.json',state)
                if step==1 or step%8==0:print(json.dumps({k:state[k] for k in ['arm','seed','completed_updates','last_loss','elapsed_seconds']}),flush=True)
                del details,loss,terms,source,arrays
        model.eval();final=out/'checkpoints/step0064.pth'
        with final.open('xb') as f:torch.save(artifact(model,arm,seed,64,mh,init_hash,optimizer),f)
        changed=[n for n,p in model.named_parameters() if digest_tensor(p)!=initial_parameters[n]]
        assert changed,'No model parameters updated'
        if not CFG['arms'][arm]['geometry_losses']:assert not any(n.startswith('geometry_head.') for n in changed)
        if not CFG['arms'][arm]['observation_steps']:assert 'observation_logits' not in changed
        assert sha(manifest_path)==mh and sha(initial)==init_hash
        state.update(status='training_complete_real_evaluation_pending',completed_updates=64,checkpoint=str(final),checkpoint_sha256=sha(final),changed_parameter_names=changed,ledger_sha256=sha(ledger),unique_scenes_consumed=len(set(order)),elapsed_seconds=time.perf_counter()-started)
        write_json(out/'state.json',state);write_json(out/'summary.json',state)
    except BaseException as exc:
        state.update(status='failed',error=repr(exc),traceback=traceback.format_exc(),elapsed_seconds=time.perf_counter()-started);write_json(out/'failure.json',state);write_json(out/'state.json',state);raise
    print(json.dumps({'arm':arm,'seed':seed,'status':state['status'],'checkpoint':state['checkpoint']}),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--arm',choices=['A','B','C']);p.add_argument('--seed',type=int);p.add_argument('--audit');args=p.parse_args()
    if args.prepare:prepare(args.package)
    else:
        if args.arm is None or args.seed not in CFG['model_seeds'] or not args.audit:p.error('run requires --arm, valid --seed and --audit')
        run(args.package,args.arm,args.seed,args.audit)
if __name__=='__main__':main()

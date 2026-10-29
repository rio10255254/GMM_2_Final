"""Freeze a single fresh V42 run on the existing source-only R129 data."""
import json,hashlib,datetime,shutil,ast,sys
from pathlib import Path
import numpy as np,torch
from scipy.io import savemat
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rec(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def main():
    legacy=REPO/'Deliverables/Standalone_Models/V42_SoftLabelSNR_FullStandalone_20260709'
    package=REPO/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912'
    cp=legacy/'results/training_results/training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713/epoch_120.pth.tar'
    payload=torch.load(cp,map_location='cpu');state=payload['state_dict'];assert sha(cp)=='89942bc9b31125e836a17b6a3490d078126807e1c8bd179b73588a38c2301f83'
    for name in ['model','config','calibration','validation','training','runs/launcher_logs','results','reports']: (ROOT/name).mkdir(parents=True,exist_ok=True)
    source=(legacy/'model_v42.py').read_text(encoding='utf-8-sig')
    (ROOT/'model/model_original.py').write_text(source,encoding='utf-8')
    converted=source.replace('import torch.nn.functional as F','from deterministic_ops import functional as F, ReflectPad, BilinearUpsample2x').replace('nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False)','BilinearUpsample2x()').replace('nn.ReflectionPad2d(1)','ReflectPad(1)')
    (ROOT/'model/model_v42.py').write_text(converted,encoding='utf-8')
    kernels=state['physics_layer.PSFs'][0].numpy();candidates=state['weak_psf_block.PSFs'][0].numpy()
    ids=[int(np.abs(kernels-k).sum((1,2)).argmin()) for k in candidates]
    assert all(np.array_equal(kernels[i],k) for i,k in zip(ids,candidates))
    savemat(ROOT/'calibration/shared_psf.mat',{'psf_grid':kernels.transpose(1,2,0)})
    args=dict(in_ch=1,base=int(state['e1.0.conv.weight'].shape[0]),use_physics_layer=True,use_sigmoid_output=True,use_band_limit=False,weak_psf_enable=True,weak_psf_k=4,weak_psf_indices=ids,weak_psf_inject='y2',weak_psf_reg=30.,weak_psf_beta_init=.02,weak_psf_psf_temp=2.5,weak_psf_entropy_mix=0.,weak_psf_lowfreq_ratio=.25,weak_psf_beta_scale_max=.35,psf_deconv_reg=10.,psf_phys_alpha_init=.10,learnable_blur=False,boundary_residual_adapter_enable=True,boundary_residual_adapter_hidden=16,boundary_residual_adapter_max=.006,boundary_residual_adapter_gate_bias=-2.,boundary_residual_adapter_delta_bias=True,boundary_residual_adapter_zero_mean=False,boundary_residual_adapter_edge_gate=False,boundary_residual_adapter_polarity_split=False,boundary_residual_adapter_orientation_inputs=True,raw_anchor_output_mode='detail',raw_anchor_output_alpha=.1,raw_anchor_output_sigma=2.,raw_anchor_output_detail_gain=.35,quality_gate_enable=True,quality_gate_hidden=8,quality_gate_scale_min=.78,quality_gate_scale_max=1.08)
    save(ROOT/'config/architecture.json',args)
    cfg=dict(model_name='R130_CleanV42',seed=1309001,epochs=32,parents_per_epoch=512,parents_per_update=4,images_per_update=8,updates=4096,order_seed=1299002,noise_seed=1299003,optimizer=dict(peak_lr=.0003,minimum_lr=.00001,warmup_updates=128,weight_decay=.00001,gradient_clip=5.),splits=dict(train=512,dev=128,test=128),data_root=str(package/'training_data'),validation_epochs=[0,8,16,24,32],final_continuous_frames=201,loss=dict(image=1.,gradient=.2,pair=.2),model_initialization='Fresh constructor, no legacy learned tensor or teacher transferred',fixed_reference='Existing R129 final8192 unchanged',shared_calibration_limitation='Same inherited V42 optical data as R129; not newly independently calibrated or free of all historical SEM ancestry',weak_branch_policy='Fresh V42 constructor beta_scale=1, effective clamp.35; legacy saved beta_scale0 is not copied. No extra R129 neural modules',inference='Native full field, reflect pad to multiple8 for V42 encoder, crop back; same final80/16Raw boundary rule as frozenR129',primary_endpoint=32,selection='Report fixed32epoch endpoint and all scheduled real checks; no best-step substitution',comparison='Practical fixedR129 versus source-only freshV42, not fully balanced causal architecture comparison',training_budget_note='16384parent pairs, close to R129 lineage8192R128+24pilot+8192long=16408; batching/optimizer/objectives differ',no_R129_changes=True,no_teacher=True,no_real_or_SEM_training_targets=True)
    save(ROOT/'config/training.json',cfg)
    for name in ['panel.json','sem_reference.mat','reference_circle_core.py','readout_helpers.py','extract_sem.m','__init__.py']:shutil.copy2(package/'validation'/name,ROOT/'validation'/name)
    shutil.copytree(package/'validation/inputs',ROOT/'validation/inputs')
    modeltree=ast.parse((REPO/'Experiments/R129_OpticalPriorHybrid/model/organized/operators.py').read_text(encoding='utf-8-sig'))
    node=next(n for n in modeltree.body if isinstance(n,ast.ClassDef) and n.name=='Bilinear2x')
    (ROOT/'model/bilinear_adjoint.py').write_text('import torch\nfrom torch.nn import functional as F\n\n'+ast.unparse(node)+'\n',encoding='utf-8')
    helper=ast.parse((package/'objectives.py').read_text(encoding='utf-8-sig'));nodes=[n for n in helper.body if isinstance(n,ast.FunctionDef)]
    (ROOT/'training/objectives_base.py').write_text('import math\nimport torch\n\n'+'\n\n'.join(ast.unparse(n) for n in nodes)+'\n',encoding='utf-8')
    shutil.copy2(package/'model/inference_policy.py',ROOT/'model/output_guard.py')
    # The shared reader is copied with only runtime import and V42 activity metadata adapted.
    evaluation=(package/'evaluate_real.py').read_text(encoding='utf-8-sig').replace('from runtime import *','from common import *').replace('from model.inference_policy import guard','from output_guard import guard').replace("optical_weights=details.optical['weights'].cpu().tolist()","weak_effective_beta=float(model.network.weak_psf_block.last_beta)")
    (ROOT/'scripts/evaluate_real.py').write_text(evaluation,encoding='utf-8')
    r129=REPO/'Experiments/R129_OpticalPriorHybrid';protected=[rec(cp),rec(legacy/'model_v42.py'),rec(package/'training_data/manifest.json'),rec(package/'results/training/r129_long_01/checkpoints/step08192.pth'),rec(package/'PACKAGE_MANIFEST.json')]
    protected += [rec(p) for p in (package/'model').glob('*.py')]
    protected += [rec(r129/'results/continuous_lsc/comparison_summary.csv'),rec(r129/'results/long_training_review_20260913_v2/trajectory.csv')]
    save(ROOT/'config/provenance.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=rec(__file__),legacy_checkpoint_read_only_for_architecture_metadata_and_fixed_calibration=True,learned_legacy_parameters_loaded_into_new_model=False,shared_PSF_indices=ids,legacy_saved_weak_scale=float(state['weak_psf_block.beta_scale']),fresh_weak_effective_scale=.35,protected=protected,legacy_neural_probe={'e1.0.conv.weight':state['e1.0.conv.weight'].flatten()[:8].tolist(),'out.weight':state['out.weight'].flatten()[:8].tolist()}))
    reg=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';registry=json.loads(reg.read_text(encoding='utf-8-sig'));save(ROOT/'config/storage_before.json',registry)
    registry['entries'].append(dict(id='r130_clean_v42',path=ROOT.relative_to(REPO).as_posix(),tier='active',state='preparing_single32epoch_cleanV42',budget_gib=5,action='protect',priority=0,keep='FreshV42 only;shared clean data referenced,originalR129/V42 untouched;32epochs and fixed real comparison;retain failures and checkpoints',blocked_by=[]))
    reg.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='preparing',model='R130_CleanV42',epochs=32,planned_updates=4096))
    (ROOT/'README.md').write_text('# R130 Clean V42 comparison\n\nOne32epoch fresh V42 on the same512source-only parents as R129, four parents per update. R129 weights/data/results are read-only. This is a practical comparison, not matched initialization or a claim of unseen generalization. Shared historical optical calibration remains a limitation. No legacy neural weights/teacher/realSEM targets are used. Architecture retains V42 encoder-decoder, AA, direction-aware boundary head, Raw anchor and quality gate.\n\nLocal branch codex/r130-clean-v42. No external issue/message requested. See config/training.json and reports/R130_RESULTS.md for actual execution.\n',encoding='utf-8')
    (ROOT/'MANIFEST.md').write_text('# R130 manifest\n\nProfile: local model/trainer with immutable shared data, not another bulk data copy. Same source-only512/128/128 splits;32epochs,onefreshseed,16384parents,4096updates. V42 original model source retained alongside arithmetic-equivalent deterministic adaptation. No learned tensor is imported from legacy V42/V41 or R129. Fixed PSF data shared withR129 are separately recorded, not independent new calibration.\n',encoding='utf-8')
    (ROOT/'results/README.md').write_text('# Results\n\nPreflight and actual training are separate; all fixed endpoint comparisons remain research-only. Original failures and old evidence remain unchanged.\n',encoding='utf-8')
    print('Prepared fresh V42 plan',args['base'],ids,flush=True)
if __name__=='__main__':main()

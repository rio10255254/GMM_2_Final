"""Register admissible A/C tests; do not fabricate independent calibration B/D."""
from pathlib import Path
import sys,json,shutil,hashlib,datetime
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent.parent
PKG=REPO/'Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912'
def rec(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def main():
    for d in ['config','net','calibration','results','reports','runs/launcher_logs','validation']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    for p in (PKG/'model').glob('*.py'):shutil.copy2(p,ROOT/'net'/p.name)
    shutil.copy2(PKG/'calibration/measured_psf_bank.npz',ROOT/'calibration/measured_psf_bank.npz')
    for name in ['extract_sem.m','sem_reference.mat','reference_circle_core.py','readout_helpers.py','panel.json','__init__.py']:shutil.copy2(PKG/'validation'/name,ROOT/'validation'/name)
    shutil.copytree(PKG/'validation/inputs',ROOT/'validation/inputs')
    old=json.loads((PKG/'config/training.json').read_text(encoding='utf-8-sig'))
    cfg=dict(model_name='R134_DirectStateRepair',seeds=[1342001,1342002],arms=['A','C'],data_root=str(PKG/'training_data'),splits={'train':512,'dev':128,'test':128},updates=512,order_seed=1344001,noise_seed=1344002,
             optimizer=dict(peak_lr=.001,minimum_lr=.00001,warmup_updates=32,weight_decay=.00001,gradient_clip=5),loss=dict(image=1.,gradient=.2,pair=.2),dev_steps=[0,128,256,512],checkpoint_every=128,
             initialization='Fresh shared initialization withinseed; bothsingleoutputheads zero. No oldneuralweight loaded; this changeshistoricalconstructorinitbutnotarmscomparability.',
             A='Original R129 optical-conditioned initialimage/features and finalRaw+HP(neural) output.',
             C='Raw-initialized image state, opticalconditioned-minus-current image feature, Rawderivatives and directfinalimage; same7channels/sameweights/shapes/fourupdates/AA.',
             factor='Whole image-state/output contract, not a claim isolating one formula',
             admission=dict(B='pending independent material-optical calibration',D='pending independent material-optical calibration',A='eligible existing isolated synthetic data',C='eligible existing isolated synthetic data'),
             screens=dict(type='Prospective engineering screening for worthiness of long research training, NOT physical accuracy certification',
                          generated='Bothseeds devMAE belowRaw; cleanidentity devMAE<=1gray',
                          sem='Bothseeds C vsA: median paired size andcenteredshape deterioration<=2percent ofmatchedA; at least one ofthese medianpairedimprovement>=5percent. C notworse thanRaw by>2percent onbothsize andcenteredshape. All36valid.',
                          next='Only a C that passesbothseeds proceeds to12source-fixedfull-fieldmotionpairs vsA andRaw; then fixeddev-selectedseed toall201 againstexistingRaw/R129 references before longtraining package.',
                          motion='On12pairs C median nominal/within-grid/cross-axis metrics<=1.05 timesmatchedA orRaw(bestbaseline not required); no increase in invalidpairs orwrongdirections. These are provisional research tolerances.',
                          no_posthoc_relaxation=True),
             packages='Each admitted longtraininggeneration must haveitsownlocalcode/data/weights/calibration/evaluation/manifest/manualstart-pause-resume menu; no mixedgeneration folders.',
             no_old_confirmation_access=True,no_full_training_until_screened=True)
    save(ROOT/'config/study.json',cfg)
    sources=[rec(p) for p in [PKG/'training_data/manifest.json',PKG/'config/training.json',REPO/'Experiments/R133_SizeMechanismDiagnosis/reports/R133_REPAIR_DESIGN.md',REPO/'Experiments/R123_RealFirstModelDesign/config/real_sources.json']]
    save(ROOT/'config/source_protection.json',dict(sources=sources))
    calib=REPO/'Thesis_MOSR_Evidence/20250605_PSF_Calibration';photos=list(calib.glob('*.bmp'))
    save(ROOT/'results/calibration_admission.json',dict(optical_calibration_images=len(photos),files=[rec(p) for p in photos],existing_reference='R123/R127 records: no independently qualified material-edge correspondence',physical_boundary_definition='not established from existing thesis wording; asked user',new_qualified_forward_data=False,B_D_not_executed=True,source_based_not_assumed_new_sample=True))
    (ROOT/'README.md').write_text('# R134 直接影像狀態修正\n\nA/C兩個接口、兩個全新初始化、各512次更新。現有合成資料來源分離；B/D新成像規則仍缺獨立材料校準，不能代造。通過事先研究條件的版本才各自整合獨立長訓練套件。\n\n原R129與資料不改，沒有SEM評估答案或舊權重進入訓練。分支codex/r134-direct-state。\n',encoding='utf-8')
    (ROOT/'MANIFEST.md').write_text('# R134 Manifest\n\nProfile:localmodel/trainer, immutable shareddata. A/C wholeinterface factor;B/D pending actualcalibration. Preservealltrials/failures; noauto-acceptofoldhashes. Longworthyversions packagedindividually, no automatic promotion.\n',encoding='utf-8')
    (ROOT/'reports/R134_METHODOLOGY.md').write_text('# R134 固定短測方法\n\n```json\n'+json.dumps(cfg,ensure_ascii=False,indent=2)+'\n```\n\n篩選百分比是新一輪工程判斷，不是已認證物理容差；不能按結果放寬。資料與接口以外的共同條件固定。A/C不是完整A/B/C/D完成宣告。\n',encoding='utf-8')
    reg=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=json.loads(reg.read_text(encoding='utf-8-sig'));save(ROOT/'config/storage_before.json',v);v['entries'].append(dict(id='r134_direct_state',path=ROOT.relative_to(REPO).as_posix(),tier='active',state='prepared_A_C_pending_calibration_B_D',budget_gib=6,action='protect',priority=0,keep='MatchedA/Cshorttrials;longqualifiedgenerationsseparatepackages;preserveoriginals',blocked_by=[]));reg.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='prepared',A_C_updates=2048,B_D='pending calibration',long_training=False));print('R134 A/C registered; B/D not falsely admitted',flush=True)
if __name__=='__main__':main()

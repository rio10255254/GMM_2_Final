from pathlib import Path
import json,shutil,hashlib,datetime,subprocess
PROJECT_ROOT = Path(__file__).resolve().parents[3]
R=Path(str(PROJECT_ROOT / 'Experiments/R130_Clean'));P=Path(str(PROJECT_ROOT / 'Experiments/R137_WeakPSFFeature'));repo=R.parents[1]
assert not P.exists();P.mkdir()
for d in ['scripts','reports','results','runs/launcher_logs','config','calibration','optical']:(P/d).mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['utils.py','model_r130_clean.py','dataset_r130_clean.py','losses_r130_clean.py','train_r130_clean.py','infer_r130_clean.py','evaluate_generated.py','evaluate_real_measurement.py','compare_measurements.py']:
 text=(R/name).read_text(encoding='utf-8').replace('r130_clean','r137_psf').replace('R130-Clean','R137-WeakPSF')
 (P/name.replace('r130_clean','r137_psf')).write_text(text,encoding='utf-8')
shutil.copytree(R/'evaluation',P/'evaluation',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(R/'results/centers',P/'evaluation/baseline_centers/R130-Clean')
# Shared immutable training arrays, no second bulk payload.
subprocess.run(['cmd','/c','mklink','/J',str(P/'data'),str(R/'data')],check=True,capture_output=True)
h=Path(r'H:\GMM_2_Final_Archive\active_runs\R137_WeakPSF_20260921\reconstruction');h.mkdir(parents=True,exist_ok=False)
subprocess.run(['cmd','/c','mklink','/J',str(P/'results/reconstruction'),str(h)],check=True,capture_output=True)
source=Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_OpticalHybrid_Standalone_20260912/calibration/measured_psf_bank.npz'))
shutil.copy2(source,P/'calibration/measured_psf_bank.npz');shutil.copy2(repo/'Experiments/R129_OpticalPriorHybrid/data/PSF_PROVENANCE.json',P/'calibration/INHERITED_PROVENANCE.json')
cfg=json.loads((R/'config_r130_clean.yaml').read_text());cfg['model_name']='R137-WeakPSF';cfg['model'].update(optical_mode='feature_single',optical_gain=.02,optical_reg=.0565,psf_bank='calibration/measured_psf_bank.npz');cfg['comparisons']=['Raw','R129','R130-Clean','R137-WeakPSF'];cfg['dataset_source']=str(R/'data');cfg['decisions'].update(PSF='User explicitly selected the existing 25-PSF bank for a weak test; normalize each kernel then average; no invented spatial mapping.',optical_scope='Global FFT cue calculated once on complete available observation; feature-level gain .02, bounded adapter; Raw unmodified. Training cue computed on original384 field then cropped to320.',locality='Neural readout remains local conditional on fixed optical cue; total optical path is global. Do not reuse pure-R130 global locality claims.')
save(P/'config_r137_psf.yaml',cfg)
save(P/'config/evaluation_manifest.json',dict(local_files={str(q.relative_to(P)).replace('\\','/'):sha(q) for q in (P/'evaluation').rglob('*') if q.is_file()}))
protected=json.loads((R/'config/protected_sources.json').read_text())
protected += [dict(path=str(R/rel),sha256=digest) for rel,digest in json.loads((R/'config/source_lock.json').read_text()).items()]
protected += [dict(path=str(R/'runs/formal_8192/checkpoints/step08192.pth'),sha256=sha(R/'runs/formal_8192/checkpoints/step08192.pth')),dict(path=str(source),sha256=sha(source))]
save(P/'config/protected_sources.json',protected)
(P/'config/USER_SPECIFICATION.md').write_text('2026-09-21 使用者授權：開啟 PSF 再訓練與驗證；明確選擇過去幾輪使用的25顆PSF，權重調小，僅作測試。R130及全部既有結果保留。延續R130第二階段feature-level輔助，非輸入端強制改寫。',encoding='utf-8')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();branch='codex/r137-weak-psf';subprocess.run(['git','branch',branch,head],cwd=repo,check=True)
save(P/'config/execution_context.json',dict(git_head=head,reserved_branch=branch,checkout_unchanged=True,python='python'))
(P/'README.md').write_text('# R137 弱 PSF 特徵測試\n\n狀態：建立與測試中，尚未正式訓練。\n\n使用原25顆PSF正規化後平均，Wiener線索進入局部特徵，強度固定0.02；原圖不改寫。從零訓練8192次，沿用512/128/128合成資料及930張共同實拍驗證。訓練前必須驗證PSF有作用、可精確關閉、梯度與固定光學線索下分塊一致性。\n\n自包含程式包，訓練資料以唯讀來源雜湊約束的目錄連接共用R130 data；不複製大型資料。大型重建位於H槽。舊PSF可能來自SEM校準，不宣稱獨立SEM確認；沒有重新指定25顆視野位置。\n',encoding='utf-8')
(P/'MANIFEST.md').write_text('本輪獨立程式與設定、訓練紀錄、模型及報告保留D槽；930張重建存H槽，約14GiB。正式執行前鎖定新程式和PSF來源；不更新原R130受保護雜湊。',encoding='utf-8')
(P/'results/README.md').write_text('本輪檢查、統計與圖表；reconstruction連到H槽本輪專用位置。程序退出不代表完成，須核對8192次更新、930影像及8370圓量測。',encoding='utf-8')
save(P/'runs/launcher_logs/active_formal_run.json',dict(state='preparing_not_training',expected_updates=8192,expected_images=930,new_training_updates=0))
registry=repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=json.loads(registry.read_text(encoding='utf-8-sig'));shutil.copy2(registry,P/'config/storage_registry_before.json');v['entries'].append(dict(id='r137_weak_psf_feature',path='Experiments/R137_WeakPSFFeature',tier='active',state='preparing',size_gib_snapshot=0,action='protect',priority=0,keep='User-authorized weak existing25PSF feature test. Budget D2GiB,H16GiB. Shared immutable R130 training arrays, separate scratch8192 run and full930 evaluation. Preserve all prior evidence.',blocked_by=[]));save(registry,v)
print(P)

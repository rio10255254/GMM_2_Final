from pathlib import Path
import shutil,subprocess,hashlib,json
PROJECT_ROOT = Path(__file__).resolve().parents[3]
P=Path(str(PROJECT_ROOT / 'Experiments/R139_UNetRecurrentPrototype'));repo=P.parents[1];ref=repo/'Experiments/R130_Clean';old=repo/'Experiments/R138_V42PSF8'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
assert not (P/'config/TRAIN.json').exists()
(P/'runs/launcher_logs').mkdir(parents=True,exist_ok=True);(P/'evaluation').mkdir(exist_ok=True)
for src,dest in [(ref/'dataset_r130_clean.py',P/'dataset.py'),(ref/'losses_r130_clean.py',P/'losses.py')]:shutil.copy2(src,dest);assert sha(src)==sha(dest)
shutil.copytree(old/'evaluation',P/'evaluation',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(old/'results/centers',P/'evaluation/baseline_centers/R138-V42PSF8')
data_source=ref/'data';assert data_source.is_dir() and (data_source/'manifest.json').is_file()
subprocess.run(['cmd','/c','mklink','/J',str(P/'data'),str(data_source)],capture_output=True,check=True)
H=Path(r'H:\GMM_2_Final_Archive\active_runs\R139_UNetRecurrent_20260923\reconstruction');H.mkdir(parents=True,exist_ok=False)
subprocess.run(['cmd','/c','mklink','/J',str(P/'results/reconstruction'),str(H)],capture_output=True,check=True)
(P/'config/DATA_REFERENCE.json').write_text(json.dumps(dict(source=str(data_source),manifest_sha256=sha(data_source/'manifest.json'),same_array_payload=True,not_copied=True,train=512,dev=128,test=128),ensure_ascii=False,indent=2),encoding='utf-8')
(P/'config/EVALUATION_REFERENCE.json').write_text(json.dumps(dict(source=str(old/'evaluation'),local_files={f.relative_to(P).as_posix():sha(f) for f in (P/'evaluation').rglob('*') if f.is_file()},reconstruction_archive=str(H),method='same corrected corner9, calibration, ACM/LSC, SEM mappings as R138'),ensure_ascii=False,indent=2),encoding='utf-8')
(P/'config/TRAIN.json').write_text(json.dumps(dict(model_seed=1309001,order_seed=1309002,noise_seed=1309003,splits=dict(train=512,dev=128,test=128),updates=8192,epochs=16,warmup=128,save_every=128,dev_every=512,optimizer=dict(name='AdamW',max_lr=.001,min_lr=.00001,weight_decay=.00001,gradient_clip=5.0),loss=dict(image=1.0,gradient=.2,pair=.2),precision='FP32',tf32=False,deterministic=True,device='cuda',train_crop=[32,352,32,352],supervised_core=[96,224],real_validation_after_final_checkpoint_only=True,model_selection='last step08192 fixed before real evaluation',optical_policy='training_policy.py: first2 epochs off, then scale .12→.28 by epoch8; optical lr 0.05×; beta raw projected after optimizer step'),ensure_ascii=False,indent=2),encoding='utf-8')
(P/'config/PROTECTED_SOURCES.json').write_text(json.dumps([dict(path=str(p),sha256=sha(p)) for p in [old/'runs/formal_8192/checkpoints/step08192.pth',old/'results/final_audit.json',ref/'data/manifest.json',old/'calibration/measured_psf_bank.npz',old/'evaluation/capture_plan.json']],ensure_ascii=False,indent=2),encoding='utf-8')
print('Shared dataset, six-method evaluation, and separate H-drive output prepared')

from pathlib import Path
import shutil,subprocess,json,hashlib
R=Path(r'D:\GMM_2_Final\Experiments\R139_UNetRecurrentPrototype');P=R.parent/'R140_StableUNet';repo=R.parents[1];assert not P.exists();P.mkdir()
for d in ['config','optical','formal','scripts','reports','results','runs/launcher_logs','evaluation']:(P/d).mkdir(parents=True,exist_ok=True)
files=['model.py','training_policy.py','dataset.py','losses.py','utils.py','infer_model.py','evaluate_real_measurement.py','compare_measurements.py','final_audit.py','write_report.py','formal/train.py','formal/launch.py','formal/preflight.py','formal/closeout.py','formal/monitor.py','optical/feature.py','optical/__init__.py','config/measured_psf_bank.npz','config/INHERITED_PSF_PROVENANCE.json']
for name in files:
 src=R/name;dst=P/name;shutil.copy2(src,dst)
 if dst.suffix=='.py':
  s=dst.read_text(encoding='utf-8-sig').replace('R139-UNetRecurrentPrototype','R140-StableUNet').replace('R139-UNetRecurrent','R140-StableUNet').replace('R139','R140').replace('r139','r140')
  dst.write_text(s,encoding='utf-8')
shutil.copytree(R/'evaluation',P/'evaluation',dirs_exist_ok=True)
shutil.copytree(R/'results/centers',P/'evaluation/baseline_centers/R139-UNetRecurrent')
subprocess.run(['cmd','/c','mklink','/J',str(P/'data'),str(R/'data')],capture_output=True,check=True)
H=Path(r'H:\GMM_2_Final_Archive\active_runs\R140_StableUNet_20260923\reconstruction');H.mkdir(parents=True,exist_ok=False)
subprocess.run(['cmd','/c','mklink','/J',str(P/'results/reconstruction'),str(H)],capture_output=True,check=True)
import hashlib
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
ref=repo/'Experiments/R130_Clean';c=json.loads((R/'config/TRAIN.json').read_text(encoding='utf-8-sig'));c['model_selection']='fixed last step08192, contingent on predeclared early synthetic stability gate';c['optimizer']['max_lr']=0.0003;c['optimizer']['min_lr']=0.000003;c['optimizer']['gradient_clip']=1.0;c['stability_gate']=dict(check_steps=[32,128,256],logit_abs_p99_max=4.0,saturation_fraction_abs_gt8_max=0.001,head_gradient_norm_min=1e-10,dev16_loss_max_ratio_to_initial=1.05);c['intentional_differences']='per-pixel channel normalization, reduced LR and tighter gradient clip; all other dataset/measurement conditions unchanged';(P/'config/TRAIN.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
m=json.loads((R/'config/model.json').read_text(encoding='utf-8-sig'));m.update(model_name='R140-StableUNet',status='pretraining_stability_probe',normalization='per_pixel_channel_only',output_logit_gain=0.1);(P/'config/model.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
(P/'config/DATA_REFERENCE.json').write_text(json.dumps(dict(source=str(ref/'data'),manifest_sha256=sha(ref/'data/manifest.json'),same_array_payload=True,not_copied=True,train=512,dev=128,test=128),ensure_ascii=False,indent=2),encoding='utf-8')
(P/'config/EVALUATION_REFERENCE.json').write_text(json.dumps(dict(source=str(R/'evaluation'),local_files={p.relative_to(P).as_posix():sha(p) for p in (P/'evaluation').rglob('*') if p.is_file()},reconstruction_archive=str(H),method='same corrected corner9, PI axis, ACM/LSC and two SEM mappings as R139'),ensure_ascii=False,indent=2),encoding='utf-8')
original=[R/'runs/formal_8192/checkpoints/step08192.pth',R/'results/final_audit.json',R/'reports/R139_CAUSAL_AUDIT.md',ref/'data/manifest.json',R/'config/measured_psf_bank.npz',R/'evaluation/capture_plan.json']
(P/'config/PROTECTED_SOURCES.json').write_text(json.dumps([dict(path=str(p),sha256=sha(p)) for p in original],ensure_ascii=False,indent=2),encoding='utf-8')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();subprocess.run(['git','branch','codex/r140-stable-unet',head],cwd=repo,check=True);(P/'config/BASE_GIT_HEAD.txt').write_text(head+'\n',encoding='ascii')
print(P)

from pathlib import Path
import shutil,subprocess,json,hashlib
R=Path(r'D:\GMM_2_Final\Experiments\R140_StableUNet');P=R.parent/'R140v2_StableUNet';repo=R.parents[1];assert not P.exists();P.mkdir()
for d in ['config','optical','formal','scripts','reports','results','runs/launcher_logs','evaluation']:(P/d).mkdir(parents=True,exist_ok=True)
files=['model.py','training_policy.py','utils.py','infer_model.py','evaluate_real_measurement.py','compare_measurements.py','final_audit.py','write_report.py','formal/train.py','formal/launch.py','formal/preflight.py','formal/closeout.py','formal/monitor.py','scripts/pilot.py','optical/feature.py','optical/__init__.py','config/measured_psf_bank.npz','config/INHERITED_PSF_PROVENANCE.json','config/TRAIN.json','config/model.json']
for name in files:
 src=R/name;dst=P/name;shutil.copy2(src,dst)
 if dst.suffix=='.py':dst.write_text(dst.read_text(encoding='utf-8-sig').replace('R140-StableUNet','R140v2-StableUNet').replace('R140_StableUNet','R140v2_StableUNet').replace('R140','R140v2').replace('r140','r140v2'),encoding='utf-8')
 elif dst.name in ['TRAIN.json','model.json']:
  s=dst.read_text(encoding='utf-8-sig').replace('R140-StableUNet','R140v2-StableUNet').replace('R140_StableUNet','R140v2_StableUNet').replace('R140','R140v2');dst.write_text(s,encoding='utf-8')
# Training reader/loss are copied byte-for-byte from the canonical R130 round.
ref=repo/'Experiments/R130_Clean';shutil.copy2(ref/'dataset_r130_clean.py',P/'dataset.py');shutil.copy2(ref/'losses_r130_clean.py',P/'losses.py')
shutil.copytree(R/'evaluation',P/'evaluation',dirs_exist_ok=True)
subprocess.run(['cmd','/c','mklink','/J',str(P/'data'),str(ref/'data')],capture_output=True,check=True)
H=Path(r'H:\GMM_2_Final_Archive\active_runs\R140v2_StableUNet_20260923\reconstruction');H.mkdir(parents=True,exist_ok=False)
subprocess.run(['cmd','/c','mklink','/J',str(P/'results/reconstruction'),str(H)],capture_output=True,check=True)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
assert sha(P/'dataset.py')==sha(ref/'dataset_r130_clean.py') and sha(P/'losses.py')==sha(ref/'losses_r130_clean.py')
(P/'config/DATA_REFERENCE.json').write_text(json.dumps(dict(source=str(ref/'data'),manifest_sha256=sha(ref/'data/manifest.json'),same_array_payload=True,not_copied=True,train=512,dev=128,test=128),ensure_ascii=False,indent=2),encoding='utf-8')
(P/'config/EVALUATION_REFERENCE.json').write_text(json.dumps(dict(source=str(R/'evaluation'),local_files={p.relative_to(P).as_posix():sha(p) for p in (P/'evaluation').rglob('*') if p.is_file()},reconstruction_archive=str(H),method='same corrected corner9, PI axis, ACM/LSC and two SEM mappings as R139'),ensure_ascii=False,indent=2),encoding='utf-8')
original=[R/'config/FORMAL_SOURCE_LOCK.json',R/'results/pilot_256.json',repo/'Experiments/R139_UNetRecurrentPrototype/reports/R139_CAUSAL_AUDIT.md',ref/'data/manifest.json',R/'config/measured_psf_bank.npz',R/'evaluation/capture_plan.json']
(P/'config/PROTECTED_SOURCES.json').write_text(json.dumps([dict(path=str(p),sha256=sha(p)) for p in original],ensure_ascii=False,indent=2),encoding='utf-8')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();subprocess.run(['git','branch','codex/r140v2-stable-unet',head],cwd=repo,check=True);(P/'config/BASE_GIT_HEAD.txt').write_text(head+'\n',encoding='ascii')
(P/'config/PRELAUNCH_CORRECTION.json').write_text(json.dumps(dict(original_attempt=str(R),original_attempt_lock_sha256=sha(R/'config/FORMAL_SOURCE_LOCK.json'),original_attempt_formal_updates=0,issue='Canonical R130 reader/loss contents matched but Windows newline bytes differed, so source hash comparison correctly rejected formal launch.',correction='Create independent R140v2 with exact byte copies; rerun short pilot and create new lock only after passing.',original_lock_not_rebased=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('R140v2 prepared with exact original loader/loss bytes and independent calibration/evaluation artifacts')

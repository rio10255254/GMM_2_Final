"""Build a verified, navigable library of the most useful MOSR experiments."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,shutil
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO=Path(str(PROJECT_ROOT))
TARGET=REPO/"Thesis_MOSR_Evidence"/"Research_Round_Library_20260926"
EXPERIMENTS={
"01_Foundations_and_Failure_Modes":[
 ("R121_BoundaryAnchorFactorial","直接加亮暗與位置要求的負結果；保存反例、尺度核對與公平短測方法。"),
 ("R122_OperatorPrinciples","位置、寬度與單張影像歧義的原理層整理；包含資料重用稽核。"),
 ("R127_MeasurementPreservationRepair","修正尺度、位移讀法與有條件原樣保留，分開影像變化與量測跳值。"),
 ("R131_RecurrentStepValidation","逐次拆解反覆重建，證明不同次數在位移、尺寸與形狀間有取捨。"),
 ("R133_SizeMechanismDiagnosis","定位尺寸改變發生階段，否決直接替換輸出公式的捷徑。"),
 ("R134_DirectStateRepair","直接影像狀態短測與量化偏移診斷；保留未通過條件。"),
 ("R135_UnifiedModelComparison","跨模型統一比較與R61訓練答案祖源稽核。"),
],
"02_Core_Model_Line":[
 ("R128_SourceOnlyFullTraining","來源獨立的生成資料與完整訓練，是後續R129及PSF配對母場景。"),
 ("R129_OpticalPriorHybrid","論文候選的光學提示與共享四次重建；位移與尺寸限制均保留。"),
 ("R130_Clean","移除PSF的乾淨從零對照，界定純神經主幹能力。"),
 ("R136_PIRepeatability","固定30趟、930張、九顆圓的共同量測與重拍協議。"),
 ("R137_WeakPSFFeature","原尺寸局部主幹加弱PSF提示；直徑重拍與短步表現的重要參照。"),
 ("R140v2_StableUNet","穩定U-Net四次共享模型；近期短步位移最佳主要對照。"),
],
"03_PSF_Experiment_Line":[
 ("R138_V42PSF8","V42八候選PSF對照，保留自適應選擇的限制。"),
 ("R139_UNetRecurrentPrototype","早期飽和退化的失敗模型，促成R140v2穩定修正。"),
 ("R143_PSF25_MatchedPairs","25顆PSF重製配對；SEM平均差改善但位置與尺寸重拍退步。"),
 ("R145_Center9PSF25_CorrectedPairs","修正九顆編號PSF；輪廓重拍較佳，選擇器仍未學成。"),
 ("R146_SEMCoreHaloPSF25_MatchedPairs","來源預測較好的研究PSF，卻未轉成量測全面改善。"),
 ("R147_FullResPSFConsistency","修正PSF原點與尺度後的原尺寸成像一致性；直徑穩、短步退。"),
],
"04_Current_Optimization":[
 ("R148_MeasurementStableNativePSF","純原尺寸共享四次方案；62次停止，累積依賴超出訓練邊界。"),
 ("R148v2_HybridContextNativePSF","一次多尺度脈絡加三個獨立原尺寸階段；目前正式背景訓練中。"),
]}
ALL_RESULTS={"R121_BoundaryAnchorFactorial","R122_OperatorPrinciples"}
SELECTED_DIRS={
"R127_MeasurementPreservationRepair":{"native_size_comparison","sem_native_v2","real_motion_v4","readout_definition_probe","cli_checks"},
"R129_OpticalPriorHybrid":{"long_training_review_20260913_v2","figures","sem","thesis_revision_20260918","organization"},
"R131_RecurrentStepValidation":{"measurements","sem","records","edge_diagnostic"},
"R134_DirectStateRepair":{"cross_axis_analysis","full_motion_recovery_v2","sem_native_v2"},
"R136_PIRepeatability":{"lsc","shape_size","sem_corner9","sem_reference_followup","r61_analysis","progress_tables","readouts","r129_uncertainty","independent_review_20260917"},
"R137_WeakPSFFeature":{"comparison","centers"},"R138_V42PSF8":{"comparison","centers"},"R139_UNetRecurrentPrototype":{"comparison","centers"},"R140v2_StableUNet":{"comparison","centers"},
"R143_PSF25_MatchedPairs":{"comparison","centers","stability_diagnosis"},"R145_Center9PSF25_CorrectedPairs":{"comparison","centers","deep_diagnosis"},"R146_SEMCoreHaloPSF25_MatchedPairs":{"comparison","centers","deep_diagnosis"},"R147_FullResPSFConsistency":{"comparison","centers","internal_audit"},
}
TABLE_EXT={".csv",".json",".md",".txt",".yaml",".yml",".xlsx",".xls",".mat",".log",".ndjson"}
ARCH_ROOT_NAMES={"README.md","MANIFEST.md","START_HERE.md","FORMAL_RUN.md","model.py","dataset.py","losses.py","training_policy.py","train.py","infer.py","utils.py","model_r137_psf.py","infer_r137_psf.py","infer_model.py","evaluate_real_measurement.py","compare_measurements.py","final_audit.py","write_report.py"}
ARCH_EXT={".py",".ps1",".json",".yaml",".yml",".md",".txt",".npz",".mat"}
records=[];excluded=[]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def copy(src,dst,role):
 if dst.exists():raise FileExistsError(dst)
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 a,b=sha(src),sha(dst)
 if a!=b:raise RuntimeError(f"Hash mismatch {src}")
 records.append(dict(role=role,source=str(src),destination=str(dst.relative_to(TARGET)),bytes=src.stat().st_size,sha256=a))
def directory_stats(path):
 files=[p for p in path.rglob('*') if p.is_file()] if path.exists() else []
 return len(files),sum(p.stat().st_size for p in files)
def copy_reports(exp,dst):
 root=exp/'reports'
 if root.exists():
  for p in root.rglob('*'):
   if p.is_file():copy(p,dst/'reports'/p.relative_to(root),'canonical_report_or_figure')
def copy_architecture(exp,dst):
 for p in exp.iterdir():
  if p.is_file() and (p.name in ARCH_ROOT_NAMES or p.name.startswith(('model','train','infer','loss','dataset')) and p.suffix in ARCH_EXT):copy(p,dst/'architecture'/p.name,'architecture_or_entrypoint')
 for name in ('config','optical','model','training','inference','scripts','calibration'):
  root=exp/name
  if not root.exists():continue
  for p in root.rglob('*'):
   if p.is_file() and p.suffix.lower() in ARCH_EXT and p.stat().st_size<=25*1024**2:copy(p,dst/'architecture'/name/p.relative_to(root),'architecture_or_provenance')
 for p in (exp/'data').rglob('*') if (exp/'data').exists() else []:
  if p.is_file() and (p.name.lower() in ('manifest.json','readme.md','generation_complete.json') or 'lock' in p.name.lower()) and p.stat().st_size<=25*1024**2:copy(p,dst/'architecture'/'data_manifests'/p.relative_to(exp/'data'),'data_manifest_or_lock')
def allowed_result(exp_name,rel,p):
 if exp_name in ALL_RESULTS:return p.stat().st_size<=100*1024**2
 if len(rel.parts)==1:return p.suffix.lower() in TABLE_EXT or (p.suffix.lower()=='.png' and p.stat().st_size<=15*1024**2)
 top=rel.parts[0]
 if top in SELECTED_DIRS.get(exp_name,set()):return p.stat().st_size<=100*1024**2
 if exp_name in ('R133_SizeMechanismDiagnosis','R134_DirectStateRepair','R135_UnifiedModelComparison','R128_SourceOnlyFullTraining','R130_Clean','R138_V42PSF8','R139_UNetRecurrentPrototype'):
  return p.suffix.lower() in TABLE_EXT or (p.suffix.lower()=='.png' and p.stat().st_size<=15*1024**2)
 if exp_name=='R129_OpticalPriorHybrid' and top=='continuous_lsc':return p.suffix.lower() in TABLE_EXT
 if exp_name=='R127_MeasurementPreservationRepair' and top=='fullfield_motion':return p.suffix.lower() in TABLE_EXT or p.suffix.lower()=='.png'
 return False
def copy_results(exp_name,exp,dst):
 root=exp/'results'
 if not root.exists():return
 for p in root.rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(root)
  if allowed_result(exp_name,rel,p):copy(p,dst/'results'/rel,'numeric_result_or_figure')
 top_dirs=[p for p in root.iterdir() if p.is_dir()]
 for d in top_dirs:
  if exp_name in ALL_RESULTS or d.name in SELECTED_DIRS.get(exp_name,set()):continue
  count,size=directory_stats(d)
  if count:excluded.append(dict(experiment=exp_name,path=str(d),files=count,bytes=size,reason='large_or_rebuildable_payload_not_duplicated'))
def copy_run_receipts(exp,dst):
 runs=exp/'runs'
 if not runs.exists():return
 for p in runs.rglob('*'):
  if not p.is_file() or 'checkpoints' in p.parts:continue
  if p.suffix.lower() in ('.json','.jsonl','.log') and p.stat().st_size<=20*1024**2:copy(p,dst/'run_receipts'/p.relative_to(runs),'run_receipt_no_weights')
def write_round_readme(path,name,summary,source):
 text=f"""# {name}\n\n## 為何收錄\n\n{summary}\n\n## 本資料夾怎麼看\n\n- `reports/`：原實驗正式報告與圖，未改寫。\n- `architecture/`：模型、訓練、推論、設定、PSF與來源鎖。\n- `results/`：已保存的完整結構化比較、圓心／輪廓、統計表與代表圖。\n- `run_receipts/`：完成狀態、訓練摘要與雜湊；不重複保存大型權重。\n\n## 原件\n\n`{source}`\n\n大型重建影像、訓練payload或重複權重若未複製，請讀全包根目錄的 `SOURCE_POINTERS.csv`。本包的評論集中於 `05_Cross_Round_Analysis/`，此處保留原證據。\n"""
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
 records.append(dict(role='generated_navigation',source='generated',destination=str(path.relative_to(TARGET)),bytes=path.stat().st_size,sha256=sha(path)))
def main():
 if TARGET.exists():raise FileExistsError(TARGET)
 TARGET.mkdir(parents=True)
 for theme,items in EXPERIMENTS.items():
  for name,summary in items:
   source=REPO/'Experiments'/name
   if not source.exists():raise FileNotFoundError(source)
   dst=TARGET/theme/name;dst.mkdir(parents=True);write_round_readme(dst/'README.md',name,summary,source);copy_reports(source,dst);copy_architecture(source,dst);copy_results(name,source,dst);copy_run_receipts(source,dst)
 with (TARGET/'SOURCE_POINTERS.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=['experiment','path','files','bytes','reason']);w.writeheader();w.writerows(excluded)
 records.append(dict(role='generated_pointer_index',source='generated',destination='SOURCE_POINTERS.csv',bytes=(TARGET/'SOURCE_POINTERS.csv').stat().st_size,sha256=sha(TARGET/'SOURCE_POINTERS.csv')))
 generated=datetime.now(timezone.utc).isoformat();manifest=dict(schema_version=1,generated_utc=generated,root=str(TARGET),experiments=sum(len(v) for v in EXPERIMENTS.values()),files=len(records),bytes=sum(r['bytes'] for r in records),records=records,excluded_payloads=excluded)
 (TARGET/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 with (TARGET/'MANIFEST.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=['role','source','destination','bytes','sha256']);w.writeheader();w.writerows(records)
 print(json.dumps({k:manifest[k] for k in ('experiments','files','bytes')},indent=2))
if __name__=='__main__':main()

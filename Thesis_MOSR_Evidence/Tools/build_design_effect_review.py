"""Build a lightweight, hash-verified design/effect review of selected MOSR rounds."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_research_round_library import EXPERIMENTS,REPO
TARGET=REPO/'Thesis_MOSR_Evidence'/'Research_Design_Effect_Review_20260926'
RESULT_EXT={'.csv','.json','.md','.txt','.log','.xlsx','.xls'}
RESULT_WORDS=('summary','result','complete','audit','comparison','interval','stability','effect','parity','preflight','evaluation','endpoint','position','shape','size','displacement','sem','edge','training','geometry','status','metric','repeat','uncertainty','verdict','analysis')
SKIP_PARTS={'reconstruction','recon','images','outputs','centers','baseline_centers','payload','checkpoints','weights','crops'}
SCRIPT_WORDS=('train','infer','model','loss','dataset','generate','preflight','evaluate','compare','audit','diagnos','analysis','measure','probe','launch','network','policy')
ROOT_FILES={'README.md','MANIFEST.md','START_HERE.md','FORMAL_RUN.md','model.py','dataset.py','losses.py','training_policy.py','train.py','infer.py','utils.py','model_r137_psf.py','infer_r137_psf.py','infer_model.py'}
records=[];sources=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def copy(src,dst,role):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);a=sha(src);b=sha(dst)
 if a!=b:raise RuntimeError(src)
 records.append(dict(role=role,source=str(src),destination=str(dst.relative_to(TARGET)),bytes=src.stat().st_size,sha256=a))
def stats(path):
 f=[p for p in path.rglob('*') if p.is_file()] if path.exists() else []
 return len(f),sum(x.stat().st_size for x in f)
def result_wanted(root,p):
 rel=p.relative_to(root);low=[x.lower() for x in rel.parts]
 if any(x in SKIP_PARTS for x in low):return False
 if p.suffix.lower() not in RESULT_EXT or p.stat().st_size>12*1024**2:return False
 if len(rel.parts)==1:return True
 text='/'.join(low)
 return any(w in text for w in RESULT_WORDS)
def architecture_wanted(exp,p):
 rel=p.relative_to(exp);low='/'.join(x.lower() for x in rel.parts)
 if p.stat().st_size>8*1024**2:return False
 if len(rel.parts)==1:return p.name in ROOT_FILES or (p.suffix.lower() in ('.py','.json','.yaml','.yml') and any(w in p.name.lower() for w in SCRIPT_WORDS))
 if rel.parts[0].lower()=='config':return p.suffix.lower() in ('.json','.yaml','.yml','.md','.txt')
 if rel.parts[0].lower() in ('optical','model','training','inference'):return p.suffix.lower() in ('.py','.json','.yaml','.yml','.md')
 if rel.parts[0].lower()=='scripts':return p.suffix.lower() in ('.py','.ps1','.md','.json','.yaml','.yml') and any(w in p.name.lower() for w in SCRIPT_WORDS)
 if rel.parts[0].lower()=='data':return p.name.lower() in ('manifest.json','readme.md','generation_complete.json','payload_lock.json','base_data_lock.json') or 'lock' in p.name.lower()
 if rel.parts[0].lower()=='calibration':return p.suffix.lower() in ('.json','.md','.txt')
 return False
def write_round(path,name,summary,source):
 path.write_text(f"# {name}\n\n## 收錄理由\n\n{summary}\n\n## 閱讀順序\n\n1. `COMMENTARY.md`：這一輪在整條研究線中的意義與我的判讀。\n2. `reports/`：原始正式報告與代表圖。\n3. `architecture/`：模型、資料、訓練與推論設計。\n4. `key_results/`：影響結論的表格與完成收據。\n\n完整重建、權重和訓練資料仍在原實驗：`{source}`。\n",encoding='utf-8')
def commentary(name,summary):
 verdict={
 'R121_BoundaryAnchorFactorial':'價值在負結果：合理的局部位置與亮暗要求沒有保住真實輪廓，提醒我們控制分數不能取代實拍。',
 'R122_OperatorPrinciples':'最重要的原理層：位置穩定不等於尺寸正確，單張影像也可能無法分開物體移動與光學中心偏移。',
 'R127_MeasurementPreservationRepair':'把模型失敗與讀法失敗分開；後續所有位移比較都應先確認影像含有足夠線索。',
 'R131_RecurrentStepValidation':'直接證明更多反覆次數不是單調更好；不同步數各自在形狀、尺寸與位移間交換。',
 'R133_SizeMechanismDiagnosis':'尺寸偏大主要由網路影像改動產生，關掉光學或換最後公式都沒有直接解決。',
 'R134_DirectStateRepair':'浮點輸出與8位元量化可造成不同結論；目前新系列保留浮點量測是正確方向。',
 'R135_UnifiedModelComparison':'提醒所有模型排名必須附帶祖源與答案重用資格，不能只看分數。',
 'R128_SourceOnlyFullTraining':'提供較乾淨的生成母場景與來源分割，是後續配對訓練的共同基礎。',
 'R129_OpticalPriorHybrid':'適合作為論文量測候選與歷史主線，但尺寸偏差、資料祖源與長距離限制需保留。',
 'R130_Clean':'純神經對照證明不少收益來自主幹本身；PSF有用與否必須靠匹配對照回答。',
 'R136_PIRepeatability':'這是近期模型公平比較的共同尺；30趟能回答重拍穩定，不能單獨證明絕對準確。',
 'R137_WeakPSFFeature':'目前直徑重拍最好，原尺寸主幹的位置相位控制亦最乾淨；但SEM平均尺寸差仍大。',
 'R140v2_StableUNet':'目前短步位移主要贏家。U-Net有取樣相位弱點，但不能因一項弱點就刪除其整體形狀能力。',
 'R138_V42PSF8':'說明增加PSF候選不等於模型真的會逐張選對；需看已知標籤和實拍選擇是否有變化。',
 'R139_UNetRecurrentPrototype':'典型失敗控制：網路飽和後幾乎等於原圖，完整跑完流程不代表模型有效。',
 'R143_PSF25_MatchedPairs':'尺寸平均差改善主要來自幾乎一致的圓縮；同時位置與直徑重拍退步，不能解讀成普遍更準。',
 'R145_Center9PSF25_CorrectedPairs':'輪廓重拍表現最好，證明穩定輪廓不必是最銳利影像；PSF直接作用仍極弱。',
 'R146_SEMCoreHaloPSF25_MatchedPairs':'最有價值的反例：來源PSF預測更好，量測卻退步；光學來源正確與模型目標正確是兩個問題。',
 'R147_FullResPSFConsistency':'讓PSF真正影響輸出並改善直徑重拍，但短步更差；成功修正物理路徑仍不足以解決量測取捨。',
 'R148_MeasurementStableNativePSF':'過度修正的設計：純原尺寸共享四次像反覆ResNet，累積依賴超出訓練邊界，於62次停止是正確決定。',
 'R148v2_HybridContextNativePSF':'目前設計最合理：多尺度只供脈絡、三個獨立原尺寸階段處理邊界；短測收益小而一致，正式結果仍待驗證。'}[name]
 return f"# 我的判讀\n\n{summary}\n\n{verdict}\n\n## 使用時要注意\n\n這一輪只支持原報告明確涵蓋的資料與指標。視覺銳利、短步位移、長距離位移、直徑重拍、輪廓重拍與SEM平均差應分開判斷。\n"
def main():
 if TARGET.exists():raise FileExistsError(TARGET)
 TARGET.mkdir(parents=True)
 for theme,items in EXPERIMENTS.items():
  for name,summary in items:
   src=REPO/'Experiments'/name;dst=TARGET/theme/name;dst.mkdir(parents=True);write_round(dst/'README.md',name,summary,src);(dst/'COMMENTARY.md').write_text(commentary(name,summary),encoding='utf-8')
   for generated in (dst/'README.md',dst/'COMMENTARY.md'):records.append(dict(role='generated_review',source='generated',destination=str(generated.relative_to(TARGET)),bytes=generated.stat().st_size,sha256=sha(generated)))
   reports=src/'reports'
   if reports.exists():
    for p in reports.rglob('*'):
     if p.is_file():copy(p,dst/'reports'/p.relative_to(reports),'canonical_report_or_figure')
   for p in src.rglob('*'):
    if p.is_file() and architecture_wanted(src,p):copy(p,dst/'architecture'/p.relative_to(src),'architecture_design')
   results=src/'results'
   if results.exists():
    for p in results.rglob('*'):
     if p.is_file() and result_wanted(results,p):copy(p,dst/'key_results'/p.relative_to(results),'key_result_table')
   runs=src/'runs'
   if runs.exists():
    for p in runs.rglob('*'):
     if p.is_file() and 'checkpoints' not in [x.lower() for x in p.parts] and p.name.lower() in ('training_complete.json','short_complete.json','test_final.json','dev_initial.json','latest.json','status.json','active_formal_run.json','run_config.json'):copy(p,dst/'run_receipts'/p.relative_to(runs),'run_receipt')
   fcount,b=stats(src);sources.append(dict(experiment=name,source_path=str(src),source_files=fcount,source_bytes=b,review_folder=str(dst.relative_to(TARGET))))
 with (TARGET/'SOURCE_INDEX.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=sources[0].keys());w.writeheader();w.writerows(sources)
 records.append(dict(role='generated_source_index',source='generated',destination='SOURCE_INDEX.csv',bytes=(TARGET/'SOURCE_INDEX.csv').stat().st_size,sha256=sha(TARGET/'SOURCE_INDEX.csv')))
 manifest=dict(schema_version=1,generated_utc=datetime.now(timezone.utc).isoformat(),experiments=len(sources),files=len(records),bytes=sum(r['bytes'] for r in records),records=records)
 (TARGET/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 with (TARGET/'MANIFEST.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=records[0].keys());w.writeheader();w.writerows(records)
 print(json.dumps({k:manifest[k] for k in ('experiments','files','bytes')},indent=2))
if __name__=='__main__':main()

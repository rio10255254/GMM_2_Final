from pathlib import Path
import json,hashlib,shutil,re
import pandas as pd
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';V=B/'R129_revalidation_20260920';O=B/'Raw_R129_comparison';REPO=R.parents[1]
D=REPO/'Deliverables/R129_Corrected_Corner9_Thesis_Handoff_20260920';D.mkdir(parents=True,exist_ok=True)
copies=[]
def cp(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);h=hashlib.sha256(src.read_bytes()).hexdigest();assert hashlib.sha256(dst.read_bytes()).hexdigest()==h;copies.append(dict(source=str(src),path=dst.relative_to(D).as_posix(),sha256=h))
def tree(src,dst):
 for p in src.rglob('*'):
  if p.is_file():cp(p,dst/p.relative_to(src))
# Preserve the exact current model identity; this is not R129_W16.
plan=json.loads((R/'config/plan.json').read_text(encoding='utf-8-sig'));model=plan['models']['R129']
verification=json.loads((O/'verification.json').read_text());verification['figures_visually_reviewed']=10;(O/'verification.json').write_text(json.dumps(verification,indent=2))
lead='本次2026-09-20重新驗證：Raw/R129共16740個圓擬合獨立重算，16740條輪廓的720方向重新計算，120組位移統計及60個R129不確定度分量重算，4張影像重播定位通過。重用固定模型已完成的浮點重建，沒有重新訓練或新推論。短步30/30次平均PI差距改善；起點相對全路徑20/30次改善、10次較差。約30μm終點偏差Raw+40.892nm、R129+42.933nm，並未改善。'
for p in [O/'README.md',R/'reports/R136_RAW_R129_CORNER9_RESULTS.md']:
 t=p.read_text(encoding='utf-8');t=t.replace('## 主要比較',lead+'\n\n## 主要比較',1);p.write_text(t,encoding='utf-8')
tree(O,D/'01_Raw_R129_Comparison');tree(V/'uncertainty',D/'02_R129_Uncertainty')
unc=pd.read_csv(V/'uncertainty/r129_uncertainty_by_position.csv');assert len(unc)==60 and (unc.n==30).all();end=unc.query("kind=='start' and position_index==30").iloc[0]
(D/'02_R129_Uncertainty/README.md').write_text(f'''# R129新九顆不確定度分量重新驗證

本表來自最新十字交界九顆，名義0.1725μm/px，相同30次拍攝與PI實際回授。60個固定步／位置每組30次。

- single_session_repeatability_s_nm：單次讀值的本次重拍標準差。
- mean_uA_time_model_nm：在時間漂移、前6／後24區塊及時間相關模型下，30次平均值的A類標準不確定度分量。
- mean_UA_k2_time_model_nm：上一分量乘2，不是完整總不確定度，也未保證95%總涵蓋率。
- bias_nm：影像位移減PI的平均值，未套偏差修正。

約30μm終點：平均PI差{end.bias_nm:.6f}nm；單次重拍標準差{end.single_session_repeatability_s_nm:.6f}nm；平均值A類分量{end.mean_uA_time_model_nm:.6f}nm；其k=2顯示值{end.mean_UA_k2_time_model_nm:.6f}nm。

完整方法見method.json，逐點見r129_uncertainty_by_position.csv。每個位置的時間相關計算已和另一實作核對，並提供不同延遲長度敏感度。PI校正、實際倍率、SEM尺度、跨日等未知分量沒有設為零，完整系統u與U仍為未知。不要把小的平均值分量用來掩蓋約42.933nm的平均偏差。
''',encoding='utf-8')
for name in ['selected_nine.png','selection_verification.json','sem_mapping_candidates.json','sem_direction_document_check.json','sem_nine_reference_sizes.csv','sem_nine_original_reference_points.npz']:
 cp(B/name,D/'03_Sampling_and_SEM'/name)
tree(B/'direction_evidence',D/'03_Sampling_and_SEM/direction_evidence')
for name in ['SEM_center36_file_mapping.csv','SEM_P_V_pairing_map.png','P_3x3_verified_order.png','V_3x3_verified_order.png']:
 cp(R/'results/sem_reference_followup'/name,D/'03_Sampling_and_SEM/historical_reference'/name)
for name in ['sem_corner9_lsc_plan.json','plan.json']:cp(R/'config'/name,D/'04_Verification_and_Sources/config'/name)
(D/'04_Verification_and_Sources/config/R129_FIXED_MODEL.json').write_text(json.dumps(model,indent=2),encoding='utf-8')
for m in ['Raw','R129']:
 tree(B/'centers'/m,D/'04_Verification_and_Sources/centers'/m)
 cp(B/f'shape_size/{m}_radial_profiles.npz',D/f'04_Verification_and_Sources/radial_profiles/{m}.npz')
tree(V/'analysis',D/'04_Verification_and_Sources/revalidated_analysis')
cp(V/'shape_and_model_verification.json',D/'04_Verification_and_Sources/shape_and_model_verification.json');cp(V/'paired_shape_size_intervals.csv',D/'04_Verification_and_Sources/paired_shape_size_intervals.csv');cp(B/'tracking.csv',D/'04_Verification_and_Sources/tracking.csv');cp(V/'figure_review_contact_sheet.png',D/'04_Verification_and_Sources/figure_review_contact_sheet.png')
for name in ['raw_r129_corner9_report.py','raw_r129_overlap_bands.py','r129_corner9_audit.py','r129_corner9_revalidate_uncertainty.py','lsc_details_corner9.py','lsc_core.py','common.py','analyze.py']:
 cp(R/'scripts'/name,D/'05_Script_Reference'/name)
(D/'05_Script_Reference/README.md').write_text('本資料夾是實際分析程式副本，仍依賴原專案量測核心與來源資料，不是完整獨立推論工具。讀取本包圖表、CSV及驗證檔案完整性不需要原專案或模型權重。\n',encoding='utf-8')
summary=pd.read_csv(O/'main_comparison.csv')
handoff='''# R129修正取樣位置後：論文改寫交接

2026-09-20重新驗證，與R128修正位置版使用完全相同的十字交界九顆、原圖、PI與量法。R128包保持原狀；本包只含Raw/R129的主資料。

## 版本與取樣

- 固定R129 r129_long_01 step08192；權重SHA256：086608339c6418b9dfd650f6809b1f7b45e65b6eb11452afe7df45c5b24ff1fd。
- 原80/16邊界政策，不是歷史SEM比較中的R129_W16；不能引用W16的8.46nm形狀分數作本批結果。
- Basler acA2040-120um、20倍；名義0.1725μm/px。PI x/y為實際同步回授、μm。
- 30次×31位置＝每方法930張、8370輪廓。每方法900個相鄰短步及900個起點相對位移。原64點邊界、720方向插值，不增加物理解析度。
- 新九顆首張座標約x1592/1621/1650、y726/755/784。追蹤源於Raw；四模型原始實驗共用相同物體，本包只抽Raw/R129。部分CSV仍沿用roi=center9，名稱不代表旧中央九顆。
- 主位移為九顆圓心差的分量中位數，再與PI比較。逐顆位移另存，不能把其指標與九顆合併指標混用。

## 本次確實重做的核對

重新核對固定權重雜湊與80/16設定；Raw/R129全部16740個圓心獨立擬合、逐顆位移及PI算式核對，並重播4張影像的完整邊界定位。全部16740條輪廓重新計算720方向，與保存值最大差約0.000061nm（浮點保存差）。重新計算配對掃描的形狀／尺寸範圍、120組位移平均及標準差、60個R129不確定度分量。10張圖已查看。沒有再訓練或重新推論930張。

## 主要結果

下表nm，reduction_percent為相對Raw降低百分比。adjacent約1μm短步；start是起點相對1～30μm整段。

'''+summary.round(3).to_markdown(index=False)+'''

短步平均PI差30/30次改善，配對95%差距範圍R129−Raw為−4.408至−3.677nm；全路徑20/30次改善、10次較差，範圍−1.979至−0.278nm。以完整掃描重抽，另有連續三次掃描成組敏感度；不是把900步視為獨立樣本。

## 必須保留的限制與不利結果

- 約30μm終點：Raw平均PI差+40.892nm，R129+42.933nm；平均偏差未改善。重拍標準差由16.124降至14.299nm。
- 平均直徑Raw2799.621nm、R1292838.911nm、SEM九顆2614.439nm。尺寸偏大差距185.182→224.472nm，增加39.290nm，不能稱尺寸準確度改善。
- 目前推定SEM方向下，去平均半徑的形狀差Raw56.348nm、R12932.636nm，形狀較接近；但含尺寸的輪廓差98.511→112.690nm，完整邊界差距變大。另一方向亦保留，不能挑有利方向。
- 新九顆集合22,23,24,28,29,30,34,35,36；左右鏡像是工作推定，非唯一方向認證。鏡像／90度候選在同十字區相關近乎相同；逐顆SEM圖保留推定標示。九顆集合平均尺寸与重拍統計不受兩種排列互換影響。
- SEM ID28邊界局部不規則完整保留，尚未證明是實物缺陷。
- 不將舊中央九顆R129短步4.092nm等結果混入；新版是4.125nm。不要把R128數值或舊36顆50倍光學SEM對照結果當成本批。
- PI校正、實際倍率、SEM尺度及边界判讀等未知分量未全部合入。完整總不確定度未建立；MAE、重拍SD與±1SD陰影不是95%總不確定度。
- 論文結論限定同片／同工作階段／九顆／20倍／目前讀取方法，未自動升級正式baseline。

## 建議圖表與閱讀順序

先看01_Raw_R129_Comparison/README.md；主圖figures/09_mean_error_sd_overlay.png與同名SVG，Raw灰、R129藍，實線30次平均、陰影±1樣本標準差。輪廓看起點／終點3×3疊圖；尺寸與不利結果看04_diameter_and_SEM.png。

02_R129_Uncertainty是本次重新計算的R129資料內不確定度分量，先讀該資料夾README，避免把平均值分量當成單次量測總不確定度。04_Verification_and_Sources保留獨立核對、模型設定、來源與原邊界點；JSON中的絕對路徑為原專案來源。

建議論文主張：R129在此實驗降低短步位移與輪廓的重拍變異，但尺寸偏大及長距離終點偏差仍存在；結果支持讀取穩定性改善，不支持全面絕對準確度改善。
'''
(D/'HANDOFF_FOR_THESIS.md').write_text(handoff,encoding='utf-8')
(D/'START_HERE.md').write_text('''# R129修正取樣位置後的獨立驗證與論文交接包

2026-09-20。相同新九顆、30次／930張；包含Raw對照、10張圖、完整明細、重新核對結果與R129不確定度分量。舊R128包與原始資料均保留。

1. [論文改寫交接說明](HANDOFF_FOR_THESIS.md)
2. [Raw／R129完整比較及圖表](01_Raw_R129_Comparison/README.md)
3. [R129不確定度分量解讀](02_R129_Uncertainty/README.md)
4. [修正後九顆位置](03_Sampling_and_SEM/selected_nine.png)
5. [平均曲線與波動帶主圖](01_Raw_R129_Comparison/figures/09_mean_error_sd_overlay.png)

每個子資料夾的CSV可獨立閱讀。04_Verification_and_Sources提供原邊界、圓心、徑向輪廓、固定模型記錄與本次核對；05只為分析程式副本，非完整獨立推論環境。

不包含930張全量原圖／重建或模型權重，來源位置留在設定與雜湊記錄。SEM逐顆方向仍為推定，並未因重新驗證而變成唯一證實；總不確定度缺項亦保留。verify_package.py使用標準Python核對根目錄MANIFEST.json。
''',encoding='utf-8')
(D/'SOURCE_COPIES.json').write_text(json.dumps(copies,ensure_ascii=False,indent=2),encoding='utf-8')
check='''from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
items=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
for item in items:
 p=root/item['path'];assert p.is_file(),str(p);assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],str(p)
print('PASS:',len(items),'payload files verified')
'''
(D/'verify_package.py').write_text(check,encoding='utf-8')
assert len(pd.read_csv(D/'01_Raw_R129_Comparison/all_contours_16740.csv'))==16740
assert len(pd.read_csv(D/'01_Raw_R129_Comparison/all_displacements_3600.csv'))==3600
for p in [D/'START_HERE.md',D/'01_Raw_R129_Comparison/README.md']:
 for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):assert (p.parent/link).exists(),(p,link)
# No accidentally retained R128-specific claims in reader-facing reports.
for p in [D/'01_Raw_R129_Comparison/README.md']:
 assert 'R128' not in p.read_text(encoding='utf-8')
files=[p for p in D.rglob('*') if p.is_file() and p.name!='MANIFEST.json'];(D/'MANIFEST.json').write_text(json.dumps([dict(path=p.relative_to(D).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],ensure_ascii=False,indent=2),encoding='utf-8')
exec(compile(check,str(D/'verify_package.py'),'exec'),{'__file__':str(D/'verify_package.py'),'__name__':'__main__'})
print('Folder:',D,'files',len(files)+1,'MB',sum(p.stat().st_size for p in files)/1e6)

"""Create a self-contained reading/evidence handoff, preserving original experiment files."""
from pathlib import Path
import json,hashlib,shutil,re
import pandas as pd
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';REPO=R.parents[1]
D=REPO/'Deliverables/Thesis_Handoffs/R128_Corrected_Corner9_Thesis_Handoff_20260920'
D.mkdir(parents=True,exist_ok=True);copies=[]
def cp(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 h=hashlib.sha256(src.read_bytes()).hexdigest();assert hashlib.sha256(dst.read_bytes()).hexdigest()==h
 copies.append(dict(source=str(src),package_path=dst.relative_to(D).as_posix(),sha256=h))
def tree(src,dst):
 for p in src.rglob('*'):
  if p.is_file():cp(p,dst/p.relative_to(src))
tree(B/'Raw_R128_comparison',D/'01_Raw_R128_Comparison')
tree(B/'R128_detail',D/'02_R128_Detailed_Results')
for name in ['selected_nine.png','selection_verification.json','sem_mapping_candidates.json','sem_direction_document_check.json','sem_nine_reference_sizes.csv','sem_nine_original_reference_points.npz']:
 cp(B/name,D/'03_Sampling_and_SEM'/name)
tree(B/'direction_evidence',D/'03_Sampling_and_SEM/direction_evidence')
for name in ['SEM_center36_file_mapping.csv','SEM_P_V_pairing_map.png','P_3x3_verified_order.png','V_3x3_verified_order.png']:
 cp(R/'results/sem_reference_followup'/name,D/'03_Sampling_and_SEM/historical_reference'/name)
cp(R/'reports/R136_SEM_DIRECTION_RESULTS.md',D/'03_Sampling_and_SEM/SEM_DIRECTION_REPORT.md')
for name in ['sem_corner9_lsc_plan.json','r128_extension.json','plan.json']:
 cp(R/'config'/name,D/'04_Source_and_Verification/config'/name)
for model in ['Raw','R128']:
 tree(B/'centers'/model,D/'04_Source_and_Verification/centers'/model)
 cp(B/f'shape_size/{model}_radial_profiles.npz',D/f'04_Source_and_Verification/radial_profiles/{model}.npz')
cp(B/'tracking.csv',D/'04_Source_and_Verification/tracking.csv')
for name in ['verification.json','tables/calibration.json','tables/uncertainty_scope.json']:
 cp(B/'analysis'/name,D/'04_Source_and_Verification'/name)
for name in ['prepare_corner9.py','run_corner9.py','lsc_measure_corner9.py','lsc_details_corner9.py','shape_size_corner9.py','corner9_sem_compare.py','raw_r128_corner9_report.py','raw_r128_overlap_bands.py','r128_corner9_detail.py','lsc_core.py','common.py','analyze.py']:
 cp(R/'scripts'/name,D/'05_Script_Reference'/name)
(D/'05_Script_Reference/README.md').write_text('這些是實際使用的分析程式副本，供核對方法。它們仍依賴原專案的量測核心、資料與環境，並非整套獨立推論工具。閱讀報告、CSV、圖表與核對資料完整性不需要原專案，也不需要重新訓練。\n',encoding='utf-8')
intro='''# 論文改寫交接：R128修正取樣位置後的實驗

整理日期：2026-09-20。本包只把已核對的成果集中供論文改寫，未重新訓練、未改論文Word、未搬動或覆寫原始資料。

## 先讀順序

1. [論文改寫交接與結論界線](HANDOFF_FOR_THESIS.md)
2. [Raw與R128完整比較、10張圖及逐顆資料](01_Raw_R128_Comparison/README.md)
3. [R128單獨的詳細結果與4張图](02_R128_Detailed_Results/README.md)
4. [新舊取樣位置示意](03_Sampling_and_SEM/selected_nine.png)

推薦論文主圖：[Raw/R128平均曲線＋±1標準差疊圖](01_Raw_R128_Comparison/figures/09_mean_error_sd_overlay.png)，同名SVG可放大排版。[九顆起點輪廓](01_Raw_R128_Comparison/figures/03_contours_position00.png)與[終點輪廓](01_Raw_R128_Comparison/figures/03_contours_position30.png)保留30次觀測與相同尺度。

## 資料夾內容

- 01_Raw_R128_Comparison：主報告、位移／尺寸／輪廓／SEM對照、10張PNG與一張SVG、所有統計明細。
- 02_R128_Detailed_Results：R128專頁、逐顆／逐位置／逐方向數據、4張細節圖。
- 03_Sampling_and_SEM：修正後九顆的位置、SEM編號與方向證據；歷史SEM排序已確定，九月相對方向仍是工作推定。
- 04_Source_and_Verification：Raw/R128原邊界點、圓心、追蹤、徑向輪廓、固定模型設定、來源路徑及已完成核對。
- 05_Script_Reference：實際分析程式副本及使用範圍說明。
- SOURCE_COPIES.json與MANIFEST.json：原檔來源、逐檔雜湊；verify_package.py可用標準Python核對。

未加入全部原圖、重建影像或模型權重；其原始位置保留在來源記錄。JSON與程式中的絕對路徑屬原專案來源，報告、CSV及本資料夾内圖片可獨立閱讀。資料夹内旧package_manifest.json描述原成果子包；本交接包以根目錄MANIFEST.json為完整清單。
'''
(D/'START_HERE.md').write_text(intro,encoding='utf-8')
handoff='''# 給接續改寫論文的對話

使用者要求：以修正取樣位置後的R128實驗成果改寫論文，必須加入Raw公平比較，保留不利結果。請以本包的新十字中心九顆結果為此次資料來源。此前對話對R128的選擇不代表正式模型基線已升級。

## 這一版究竟是哪批資料

- 同一片樣品的30次拍攝；每次31位置，約1μm步距、相對起點最遠約30μm。每方法930影像、8370輪廓。
- 相機Basler acA2040-120um、20倍；名義尺度0.1725μm/px。PI x/y為拍攝時實際回授，單位μm。
- 已改選柱陣列最靠近右下十字交界的3×3九顆，首張座標約x1592/1621/1650、y726/755/784。01及02的全部數據均使用新位置。
- 固定R128為P_s1285002 step8192，SHA256：9fbdffa3bebe0a37e3f7c2b09239e2e00de6b0522feb101571fcfb7a42699abf；原64/16邊界政策。沒有為本批重拍重新訓練或調權重。
- 採論文LSC圓心與邊界量法。9顆逐顆位移後取分量中位數為主位移結果；每顆單獨位移另存。原64邊界點插值720方向，不增加物理解析度。
- 固定位置與固定顆粒跨30次計算重拍波動；抽樣比較保留完整掃描，不把顆粒、角度或900筆位移當成900次獨立實驗。
- 某些CSV的roi欄仍稱center9，這是沿用欄位名稱，並非舊九顆；以本包位置圖、取樣設定與來源資料夾判斷。

## 可直接引用的主要結果（nm）

| 指標 | Raw | R128 | 相對降低 |
|---|---:|---:|---:|
| 約1μm短步平均絕對PI差距 | 8.167 | 3.708 | 54.6% |
| 短步平均重拍標準差 | 9.725 | 3.708 | 61.9% |
| 短步觀察到的最大絕對差距 | 39.299 | 15.535 | 60.5% |
| 相對起點全路徑平均絕對PI差距 | 19.081 | 17.864 | 6.4% |
| 相對起點平均重拍標準差 | 13.763 | 10.095 | 26.6% |
| 直徑重拍波動 | 32.750 | 9.527 | 70.9% |
| 含尺寸變化的輪廓重拍波動 | 63.758 | 13.835 | 78.3% |
| 去除平均半徑變化的形狀重拍波動 | 61.667 | 13.005 | 78.9% |

精確未四捨五入值見01/main_comparison.csv。位移重拍指標是固定位置標準差的平均；尺寸與輪廓重拍指標是固定位置／顆粒／方向變異數平均後開根號，兩種彙整定义不要混寫。

短步平均差距30/30次改善；相對起點21/30次改善、9/30次較差。以完整掃描配對的95%差值範圍：短步R128−Raw為−4.813至−4.088nm；全路徑為−2.084至−0.401nm。連續三次成組重抽結果亦保留在paired_displacement_evidence.csv。

## 必須保留的不利結果

- 約30μm終點：Raw平均PI差+40.892nm、R128+41.966nm；R128終點平均偏差未改善。終點重拍標準差則由16.124降至14.193nm。不可把全路徑平均差距當成終點偏差。
- 九顆平均直徑：Raw2799.621nm、R1282836.478nm；現有SEM九顆平均2614.439nm。因此Raw偏大185.182nm、R128偏大222.040nm，R128平均尺寸差距增加36.858nm。尺寸更穩定不等於尺寸更準。
- 以目前推定方向比較SEM，去除平均半徑的形狀差距Raw56.348nm、R12829.884nm；但保留尺寸的完整輪廓差距Raw98.511nm、R128111.605nm。需交代方向與尺度限制，不可只挑形狀改善。

## SEM方向與準確度界線

SEM有明確歷史36顆排序；使用者確認九月與舊SEM是同片。所選九顆集合為22,23,24,28,29,30,34,35,36。依明暗分類及整視野對位，採左右鏡像作工作推定，排列22/23/24、28/29/30、34/35/36。

這不是唯一已證實的轉向：相同十字區域鏡像和90度候選相關0.978951/0.978681，近乎同分。另一方向排列22/28/34、23/29/35、24/30/36保留在SEM_direction_sensitivity.csv。逐顆SEM輪廓請標示推定；九顆集合平均尺寸與重拍統計不受兩種排列互換影響。

SEM ID28局部參考邊界不規則，完整保留，尚未認證為實物缺陷。不能把像素尺度、SEM邊界與參考誤差視為已消除。

## 論文中避免混用

- 不引用先前中央九顆的R128短步MAE4.025nm／尺寸重拍13.558nm；新版對應數值是3.708nm／9.527nm。
- 不把舊36顆、50倍配對光學影像的SEM結果，混作這批20倍／30次的準確度證據。
- 不將R129不確定度報告的數字寫成R128。本包的R128是重拍統計與比較，不是完整總不確定度預算。
- PI／倍率／SEM尺度與邊界判讀的未知分量未全部合入，完整總不確定度仍未定。標準差、±1SD陰影或MAE都不能直接改稱95%總不確定度。
- 結論限定本片樣品、本次工作階段、九顆、20倍及目前量法，不宣稱跨樣品、跨日期、所有距離普遍最佳。

## 建議章節用途與圖表

- 實驗方法：新取樣位置圖、30×31設計、同步PI、固定模型、相同LSC與追蹤方式。
- 位移结果：01/figures/09_mean_error_sd_overlay.png（另有SVG）為主圖；線為30次平均、陰影為±1樣本標準差，不是95%信賴區間。補02_displacement_repeatability.png與約30μm終點表。
- 輪廓重拍：03_contours_position00.png和03_contours_position30.png，Raw灰／R128紫，30次淡線、圓心對齊、相同尺度。
- 尺寸與限制：04_diameter_and_SEM.png呈現改善與偏差並存；08_SEM_inferred_comparison.png必須保留方向推定標示。
- 附錄：3600合併位移、32400逐顆位移、16740輪廓、120固定位置表，以及來源／驗證紀錄。

建議核心敘述：在此30次重拍實驗中，R128降低短步位移與輪廓讀取的重拍變異，顯示量測穩定性改善；但平均尺寸相對SEM偏大的差距增加，且約30μm終點偏差未改善，故不能將穩定性改善等同全面準確度改善。
'''
(D/'HANDOFF_FOR_THESIS.md').write_text(handoff,encoding='utf-8')
(D/'SOURCE_COPIES.json').write_text(json.dumps(copies,ensure_ascii=False,indent=2),encoding='utf-8')
verify='''from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
for item in manifest:
 p=root/item['path']
 assert p.is_file(),str(p)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],str(p)
print('PASS:',len(manifest),'files verified')
'''
(D/'verify_package.py').write_text(verify,encoding='utf-8')
# Check package counts and local markdown images/links before handing it off.
assert len(pd.read_csv(D/'01_Raw_R128_Comparison/all_contours_16740.csv'))==16740
assert len(pd.read_csv(D/'01_Raw_R128_Comparison/all_displacements_3600.csv'))==3600
assert len(pd.read_csv(D/'01_Raw_R128_Comparison/individual_circle_displacements_32400.csv'))==32400
bad=[]
for p in [D/'START_HERE.md',D/'01_Raw_R128_Comparison/README.md',D/'02_R128_Detailed_Results/README.md']:
 for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
  if not (p.parent/link).exists():bad.append([str(p),link])
assert not bad,bad
files=[p for p in D.rglob('*') if p.is_file() and p.name!='MANIFEST.json']
(D/'MANIFEST.json').write_text(json.dumps([dict(path=p.relative_to(D).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],ensure_ascii=False,indent=2),encoding='utf-8')
print(D);print('Files:',len(files)+1,'MB:',sum(p.stat().st_size for p in files)/1e6,'copied files:',len(copies),'local Markdown links checked')
if __name__=='__main__':exec(compile(verify,str(D/'verify_package.py'),'exec'),{'__file__':str(D/'verify_package.py'),'__name__':'__main__'})

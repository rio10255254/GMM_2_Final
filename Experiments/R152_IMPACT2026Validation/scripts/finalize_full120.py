"""Current reports and poster text; preserve the earlier blocked-stage history."""
from pathlib import Path
import json,shutil,re
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT.parents[1]
DATA=ROOT/'results/full120';POSTER=ROOT/'poster_assets/full120'
FIELDS=['step_sd_nm','nominal_mae_nm','median_within_grid_sd_nm']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def mdtable(frame,scope_col):
    text=['| 範圍 | 方法 | 配對數 | 步距波動 nm | 名義步距平均差 nm | 九顆差異中位數 nm |','|---|---|---:|---:|---:|---:|']
    for r in frame.itertuples():text.append(f'| {getattr(r,scope_col)} | {r.method} | {r.n_pairs} | {r.step_sd_nm:.6f} | {r.nominal_mae_nm:.6f} | {r.median_within_grid_sd_nm:.6f} |')
    return '\n'.join(text)
def main():
    done=load(DATA/'complete.json');assert done['state']=='complete_objective_calibrated_full120'
    POSTER.mkdir(parents=True,exist_ok=True)
    history=ROOT/'reports/history_20x_stage';history.mkdir(exist_ok=True)
    for rel in ['reports/R152_AUDIT.md','reports/R152_RESULTS.md','results/preflight_status.json','results/delivery_verification.json']:
        p=ROOT/rel;dest=history/p.name
        if p.exists() and not dest.exists():shutil.copyfile(p,dest)
    agg=pd.read_csv(DATA/'aggregate_summary.csv');cond=pd.read_csv(DATA/'condition_summary.csv');ci=pd.read_csv(DATA/'paired_intervals.csv');wins=pd.read_csv(DATA/'within_grid_wins.csv')
    changes=pd.read_csv(DATA/'relative_changes.csv');shared=pd.read_csv(ROOT/'results/shared_bank120/aggregate_summary.csv');adapter=load(ROOT/'results/objective_adapter_preflight.json')
    mainrows=agg[agg.scope=='all120'].set_index('method');r=mainrows.loc['R152']
    result_lines=[]
    for baseline in ['Raw','Wiener']:
        vals=changes[changes.baseline==baseline].set_index('metric')
        words=[f'{label}{"降低" if vals.loc[f,"reduction_pct"]>=0 else "增加"}{abs(vals.loc[f,"reduction_pct"]):.2f}%' for f,label in zip(FIELDS,['步距波動','名義步距平均差','九顆差異'])]
        result_lines.append(f'- 相對{baseline}：'+ '、'.join(words)+'。')
    ranges=['| 對照 | 指標 | 對照減R152 nm | 95%區間 nm |','|---|---|---:|---|']
    for row in ci.itertuples():ranges.append(f'| {row.baseline} | {row.metric} | {row.baseline_minus_r152_nm:.6f} | [{row.ci95_low_nm:.6f}, {row.ci95_high_nm:.6f}] |')
    modelnotes='''20×保持原R152的25顆原生光學資料；50×接入原投稿Wiener所用、可追溯到50×校正影像的單顆光學資料。兩者使用同一交付保存點、相同已學得權重、倍率1；沒有重新訓練。50×需要本工作區新增的光學輸入轉接，因此應稱「R152加倍率光學輸入轉接」，不能說交付原程式完全未改。

依使用者「暫用、維持通融性」要求，改動放在可選、可還原的資料入口。未指定外部單核時保留原生25顆及選擇器；暫用單核後可還原，核心入口不綁定倍率或特定檔案。原生→單核→原生→單核的切換實測均可逐像素精確回到原輸出；最終可還原介面重播已保存的一張完整50×結果也逐像素一致。沒有把核心模型永久改成單核模型。

50×只有一顆已校正資料，權重固定1；原25顆選擇器的參數完整保留，但50×不執行多顆选择。不將單顆複製成25顆，不宣稱50×也具多位置自適應能力。20×原生主體與附加支路保持原狀。

原50×核略不對稱，中心相對第50個樣點約(-0.027514, +0.158538)像素；保留原核的排列、中心和形狀，未平移、縮放或強制對稱。光學變動接入原主體的模糊提示及新增頻域支路兩處，不只換表面上的檔名。
'''
    results='''# R152 IMPACT2026 完整四條件結果

## 完成範圍與模型身分

原四組120鎖定配對、166張不同影像已全部完成。Raw、Fixed Wiener與R152共4482筆圓心、360筆配對。主結果使用20×原生光學資料及50×原有校正資料；先前共用20×光學資料的50×測試完整保留為附加比較。主結果設定由使用者最後指令決定，不按分數挑版本。

'''+modelnotes+'\n## 主結果\n\n'+mdtable(agg[agg.scope=='all120'],'scope')+'\n\n'+'\n'.join(result_lines)+'\n\n## 各倍率與各條件\n\n'+mdtable(agg[agg.scope!='all120'],'scope')+'\n\n'+mdtable(cond,'sequence')+'''

三項分別報告；正負結果均保留。名義步距是設定參照，不是独立絕對長度真值。每條件30組相鄰影像配對不是30趟獨立重拍。

## 與原稿協議的關係

- 原四組、原120配對、九顆身分、裁切搜尋、暗柱方向、量測程式與物方比例不變。
- 每組步距取九顆有號水平位移中位數的絕對值；不是二維向量長度。
- Step SD是四條件各30步樣本標準差的平均；Nominal MAE是四條件對名義步距的平均絕對差之平均；Median within-grid SD是120個九顆樣本標準差的中位數。
- 20×原取邊64點、50×96點均保留；沒有自行改成另一條720方向量測路線。
- Raw與Wiener完整重跑後，240列配對結果與投稿原表一致。原投稿歷史MOSR是V42，沒有把其數字改名為R152。
- 現在兩倍率使用各自對應的光學資料，但50×採單核轉接；與原稿量測協議一致，不代表模型實作與投稿歷史版本完全相同。

## 配對區間

沿用原投稿的條件內配對重抽樣方法，20000次、固定種子20260824，每次三方法共享同一抽樣索引。正值代表R152較低，跨零不能稱為該差異明確成立。

'''+ '\n'.join(ranges)+'''

這些區間條件化於原來選出的影像配對。相鄰配對可能共用影像，不能將這些區間當成完全獨立重拍或跨設備泛化證據。

## 共用光學資料的附加比較

這份比較來自使用者上一則「50×也用同一組」指令，之後依使用者最後指令改以50×原校正作主結果。共用版本沒有刪除，詳表在 `results/shared_bank120/`；兩版本逐項差值在 `results/full120/calibrated_vs_shared_optics.csv`。

'''+mdtable(shared[shared.scope.isin(['all120','50x'])],'scope')+'''

與共用光學版本相比，各倍率校正的主結果總步距波動7.133636→7.125267 nm、名義步距平均差5.556398→5.542029 nm略低，但合併九顆差異中位數4.330726→4.353063 nm略高。因此不能說換50×校正讓所有總指標都改善。兩版本差異均保留，主結果選擇依使用者指定的物理校正來源。

## 驗證與交付

- 50×轉接前後所有學得參數逐項一致；僅兩条光學路徑的3個固定資料欄位換為實測50×核。推論期間所有參數和固定內容再核對不變。可還原入口切回原生25顆的輸出逐像素相同。
- 模糊與反濾波分別對照獨立計算通過；一張完整實拍的整張／分塊比較通過。
- 166張主結果各有原圖、模型、光學資料及輸出核對值；20×已有結果保留原樣。
- 最終另由存下的圓心重新算360筆配對與全部摘要，並重新核對來源、輸出和正式基準。
- 所有科學圖皆由主結果表和原影像生成；代表影像固定取各條件第一個鎖定配對起點，沒有看結果挑有利圖片。

本輪可以支持此樣品與四條件下的實測比較；不能單憑本輪稱為任何倍率、樣品或設備都適用的萬用模型。未改D槽的模型、既有結果或正式基準。

最新圖文入口：`poster_assets/full120/START_HERE.md`。
'''
    (ROOT/'reports/R152_RESULTS.md').write_text(results,encoding='utf-8')
    audit='''# R152 IMPACT2026 來源、接線與協議核對

## 現況

完整四條件已完成，50×缺項已依使用者授權的小幅輸入修改解除。先前20×完成、50×等待資料的紀錄保存在 `history_20x_stage/`，不是目前狀態。

原四組120配對及166張不同原圖已找回並逐檔核對。各組不同影像數為50×0.5 μm：44、50×1.0 μm：42、20×0.5 μm：39、20×1.0 μm：41。原影像清單在 `results/raw_frame_manifest.csv`；小型來源快照在 `sources/`，完整來源與核對值在 `results/source_manifest.json`。

原配對來自R80的 `displacement_raw_locked_selection_all.csv`。依原Raw eligibility規則重新核對同一名單，沒有重新排序選取新的配對。原規則在可用性門檻後按Raw名義步距差選30組，不是隨機樣本。

## 原稿重播

原量測兩個來源程式的快照逐位元相符。四組Raw／Wiener／舊MOSR完整實際重播4482筆圓心、360筆配對通過。歷史三方法三項總數為Raw 8.884944／7.001601／12.547376，Wiener 7.906361／6.417996／5.983640，舊MOSR 7.292303／5.742972／4.885544 nm，與投稿表格一致。

這些舊MOSR數字屬V42，與本次R152新結果分開。原稿只用名義步距，不把R152另一次930張驗證的PI回授數字搬入本輪。投稿PDF已全文閱讀及逐頁檢視，副本、全文及原頁面在sources和qa。

## 光學資料及接線

'''+modelnotes+'''

原50×來源為 `D:/GMM_2_Final/PSF_Fitting/tests/artifacts/cd_verification_20260714/50x_deconvolution_sweep.mat` 的 `psf`，並逐元素對照原 `PSF_Fitting/output/pillar_via_junction_psf_20260713/50x/fit_result/PSF_fitted_2D_FOVstack.mat`。物方比例0.069 μm/px由該目錄的 `selected_frame.json` 證實。20×R152保留原銀行0.1725 μm/px；Wiener仍各用原倍率校正及固定正規量0.0565。

本工作區的 `scripts/objective_optics.py` 提供可選且可還原的推論專用光學入口，不更改D槽來源。核心 `configure_optical_input(..., kernel=None)` 還原原生25顆；傳入已核對的單顆校正則暫時使用單核。倍率與檔案來源只在本實驗的 `install_50x` 外層處理。單核擷取檔 `config/50x_calibrated_psf.npz` 有完整來源鎖；只做總能量正規化，未改實測輪廓。新增入口禁用訓練、拒絕不存在的光學編號，切換時清除舊的頻域快取。

## 實際接線檢查

'''+f'- 獨立模糊運算最大差：{adapter["independent_convolution_max_error"]:.9g}（0–1亮度）。\n- 獨立反濾波運算最大差：{adapter["independent_inverse_filter_max_error"]:.9g}。\n- 一張完整50×原圖整張／分塊最大差：{adapter["full_vs_tiled_real_frame_max_difference"]:.9g}。\n- 真實裁切共用／50×校正輸出最大差：{adapter["shared_vs_calibrated_patch_max_difference"]:.9g}，確認光學替換實際參與输出。\n'+'''
20×／50×推論全部採FP32、關閉TF32、固定交付倍率1。原交付來源鎖32項及完整紀錄29個連結核對通過；訓練保存點不變。最終稽核在 `results/full120/delivery_verification.json`。

## 協議與主張界線

量測資料、配對、尺度及三項定義一致。R152是此次新比較的模型，50×增加單核輸入適配；不能把此改動隱去或宣稱50×執行了25顆實測PSF選擇。原稿的歷史抗混疊消融也不能直接當成本次R152元件因果證明。

目前沒有阻擋本輪比較的缺項。若要進一步聲稱50×多位置自適應、跨樣品通用或獨立絕對準確度，仍需要對應的新證據；這些不屬本次已完成的120配對比較。
'''
    (ROOT/'reports/R152_AUDIT.md').write_text(audit,encoding='utf-8')
    status=load(ROOT/'results/preflight_status.json');status.update(status='COMPLETE_OBJECTIVE_CALIBRATED_FULL120',blocking_items=[],full_r152_inference_started=True,full_four_condition_result_available=True,objective_adapter_verified=True,latest_authorization='config/objective_optics_authorization.json',magnification_specific_optics=True,measurement_protocol_matches_paper=True,exact_submitted_model_implementation=False)
    save(ROOT/'results/preflight_status.json',status)
    poster=f'''# IMPACT2026 R152 poster text

## Title

Measurement-Oriented Microscopy Reconstruction for Cross-Magnification Micro-Displacement Inspection

## Experiment identification

R152 follow-up evaluation using the original four conditions and 120 locked pairs. The learned weights are fixed. R152 uses its native 25-kernel optical bank at 20x and the original calibrated single PSF through an inference input adapter at 50x. This is the current main result; the shared-bank run is supplementary.

## Motivation

Sharper microscopic images do not necessarily give more stable position measurements. Reconstruction should therefore be assessed through a common measurement procedure, with the same images and feature identities held fixed.

## Method

The delivered R152 weights were used without retraining. Its frozen reconstruction path combines image context and bounded native-grid corrections, followed by a bounded Fourier optical correction. At 20x, the original 25-PSF bank was retained. At 50x, an optional and reversible inference-only adapter installed the original measured 50x PSF in both optical paths. With one calibrated kernel, the optical weight is exactly one; no multi-PSF selection is claimed at 50x. Learned neural parameters and output correction strengths were unchanged. Removing the temporary optical input restores native 25-PSF inference.

Raw, fixed Wiener and R152 were measured by the original common backend: coarse active contour, correct-polarity maximum-gradient boundary refinement, and geometric least-squares circle center. The absolute median horizontal shift of nine pillars defines the array step. Native coordinates are converted using 0.1725 and 0.0690 micrometers per pixel for 20x and 50x, respectively.

## Experiment

The four conditions combine 20x and 50x objectives with nominal 0.5 and 1.0 micrometer steps. Thirty original adjacent-frame pairs per condition were retained: 120 pairs from 166 distinct frames. Pair identities, nine pillar identities, localization windows, intensity polarity and measurement settings were fixed. Wiener retained the original objective-specific calibration and fixed regularization.

## Main results

Across the 120 original pairs, R152 yielded Step SD of {r.step_sd_nm:.2f} nm, nominal MAE of {r.nominal_mae_nm:.2f} nm, and median within-grid SD of {r.median_within_grid_sd_nm:.2f} nm. All four condition-level results are retained; very small numerical differences are not treated as proof of practical superiority.

'''+mdtable(agg[agg.scope=='all120'],'scope')+'''

## Metric definitions

Step SD is the mean of the four condition-level sample standard deviations. Nominal MAE is the mean of the four condition-level mean absolute deviations from the nominal step. Median within-grid SD is the median of the 120 pair-level sample standard deviations of the nine signed horizontal pillar shifts. The three criteria are reported separately.

## Interpretation and limits

The results evaluate this specimen and these four acquisition conditions. Agreement with nominal stage steps is not independent absolute length accuracy. Adjacent pairs can share frames; paired resampling intervals are conditional on the original selected pairs. The single calibrated 50x PSF does not establish spatially adaptive PSF selection at 50x, and this experiment alone does not establish a universal model across specimens, objectives or devices.

## Figure captions

**Figure 1. Measurement protocol.** Original four-condition, 120-pair evaluation with fixed learned R152 weights, native 20x optical information and the original single calibrated 50x PSF. All image methods share one boundary-and-center measurement backend.

**Figure 2. Aggregate displacement results.** Step SD and nominal MAE are means of four condition-level values; median within-grid SD is the median of 120 pair-level nine-pillar standard deviations. Values are in nanometers and lower is better.

**Figure 3. Condition-level results.** All three metrics are shown separately for the original 50x/0.5, 50x/1.0, 20x/0.5 and 20x/1.0 micrometer conditions, each with 30 locked pairs. No condition has been excluded.

**Figure 4. Representative outputs.** The start frame of the first locked pair in each condition is shown for all methods at the same 0–1 display range. Scale bars are 2 micrometers. Images were selected by original pair order, not reconstruction quality; quantitative measurements use the original numeric outputs.

## 中文交付說明

主結果採用各倍率對應的光學資料。R152沒有重訓；只在50×增加能讀入原單顆校正資料的入口。完整數據、正負結果、原配對及共用光學資料的附加比較均保留。此素材可用於本輪海報，但不要將原投稿V42的數字或元件效果直接套在R152上。
'''
    poster=poster.replace('| 範圍 | 方法 | 配對數 | 步距波動 nm | 名義步距平均差 nm | 九顆差異中位數 nm |','| Scope | Method | Pairs | Step SD (nm) | Nominal MAE (nm) | Median within-grid SD (nm) |')
    (POSTER/'POSTER_TEXT.md').write_text(poster,encoding='utf-8')
    (POSTER/'START_HERE.md').write_text('''# 最新海報素材：R152完整120配對

主結果已完成：20×原生光學資料，50×原校正單核；同一套已學好的權重，沒有重新訓練。

- [海報文字、方法、結果和英文圖說](POSTER_TEXT.md)
- [三項主結果 PNG](01_aggregate_results.png) / [可編輯 SVG](01_aggregate_results.svg)
- [四條件完整對照 PNG](02_condition_results.png) / [可編輯 SVG](02_condition_results.svg)
- [四條件代表影像 PNG](03_representative_outputs.png) / [可編輯 SVG](03_representative_outputs.svg)
- [方法流程圖 PNG](04_measurement_protocol.png) / [可編輯 SVG](04_measurement_protocol.svg)
- [完整結果報告](../../reports/R152_RESULTS.md)
- [來源與接線核對](../../reports/R152_AUDIT.md)

四張圖皆有高解析PNG及可編輯SVG。代表圖內的顯微影像維持點陣內容，文字、座標和其他圖形可編輯。上一階段的20×圖文和「等待50×」方法圖留作過程紀錄，不是最新海報入口。
''',encoding='utf-8')
    (ROOT/'README.md').write_text('''# R152 IMPACT2026：完整四條件交付

原四組120配對、166張原始影像的Raw／Fixed Wiener／R152比較已完成。20×使用R152原生光學資料，50×使用原校正單核並增加小幅推論輸入適配；同一套學得權重，沒有重訓。

- [主結果](reports/R152_RESULTS.md)
- [協議、光學來源與接線核對](reports/R152_AUDIT.md)
- [最新海報素材入口](poster_assets/full120/START_HERE.md)
- [最終驗證](results/full120/delivery_verification.json)
- [四條件總表](results/full120/aggregate_summary.csv)
- [各條件表](results/full120/condition_summary.csv)
- [全部逐對明細](results/full120/per_pair.csv)
- [與共用光學資料版本比較](results/full120/calibrated_vs_shared_optics.csv)

主結果設定來自使用者最後指令，不按量測結果選版本。原共用光學版本保存在results/shared_bank120及results/50x_shared_bank；早期缺項紀錄保存在reports/history_20x_stage。

工作區分支sandbox/r152-impact2026。D:/GMM_2_Final的原模型、光學檔、影像、既有結果與正式基準保持原樣；大型來源唯讀引用，小型程式和配對有核對副本。本工作區根層其餘專案內容可能來自較早Git提交，當次來源專案現況在sources/source_project_state.md。

## 重跑入口

使用C:/Users/Rio/anaconda3/python.exe，從本目錄執行：

```text
python -B scripts/check_objective_adapter.py
python -B scripts/run_50x_calibrated.py
python -B scripts/summarize_full120.py
python -B scripts/build_full120_assets.py
python -B scripts/finalize_full120.py
python -B scripts/verify_full120.py
```

已完成的20×輸出持續沿用。如需重做20×，使用scripts/run_20x.py；既有影像收據會核對後復用。所有入口不包含重新訓練。
''',encoding='utf-8')
    (ROOT/'MANIFEST.md').write_text('''# R152 IMPACT2026 manifest

- Role: validation-only follow-up; no model training or promotion.
- Profile: shared-mainline read-only references to D:/GMM_2_Final; independent branch sandbox/r152-impact2026.
- Main scope: 166 native frames, 120 original locked pairs, Raw/Fixed Wiener/R152, 4482 centers and 360 pair measurements.
- R152 identity: delivered checkpoint 17bf7c63f070520a5ef8d4428010340686f465bf1fa03ef8225c0a2eadad4a61, multiplier 1, learned parameters unchanged.
- Optical inputs: original native 25-kernel 20x bank; original single calibrated 50x PSF through the authorized inference-only adapter.
- Main outputs: results/full120; results/20x; results/50x_calibrated.
- Supplement: results/shared_bank120 and results/50x_shared_bank. Retained irrespective of comparative scores.
- Current reports: reports/R152_RESULTS.md and reports/R152_AUDIT.md. Earlier stage: reports/history_20x_stage.
- Poster entry: poster_assets/full120/START_HERE.md.
- Provenance: results/source_manifest.json; config/objective_optics_authorization.json; results/objective_adapter_preflight.json; per-image reconstruction receipts.
- Verification: results/full120/delivery_verification.json.
- Retention: preserve the whole audit and inference package plus all referenced D paths. No source model, image, prior result, or formal baseline modified.
''',encoding='utf-8')
    policy_path=WORK/'ESTIMATOR_POLICY.json';policy=load(policy_path)
    policy['r152_impact2026_worktree_note']=dict(status='full120_objective_calibrated_complete',formal_baseline_unchanged=True,external_compare='Original IMPACT nominal-step maximum-gradient/LSC protocol; not external GMF.',notes='Same delivered learned weights; native 20x 25PSF and original 50x single calibrated PSF with authorized input adapter. Shared-bank run retained as supplement. No promotion.',report='Experiments/R152_IMPACT2026Validation/reports/R152_RESULTS.md')
    save(policy_path,policy)
    note='2026-09-29 本獨立工作區R152四條件120配對完成：20×原生25顆光學資料、50×原校正單核及推論輸入轉接；相同學得權重、未重訓。原配對及量測協議不變，共用光學版本保留為附加比較。正式基準不變。[完整結果](Experiments/R152_IMPACT2026Validation/reports/R152_RESULTS.md)'
    statepath=WORK/'PROJECT_STATE.md';state=statepath.read_text(encoding='utf-8');state=re.sub(r'2026-09-29 本獨立工作區完成R152[^\n]*',note,state);statepath.write_text(state,encoding='utf-8')
    indexpath=WORK/'Experiments/INDEX.md';text=indexpath.read_text(encoding='utf-8');text=re.sub(r'\[R152 IMPACT2026部分結果\][^\n]*','[R152 IMPACT2026完整結果](R152_IMPACT2026Validation/reports/R152_RESULTS.md)：四條件120配對完成，20×原生光學及50×原校正單核轉接；未重訓、未更換正式基準。',text);indexpath.write_text(text,encoding='utf-8')
    print(mainrows.to_string())
if __name__=='__main__':main()

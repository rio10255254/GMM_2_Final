# Lab R56：只修答案邊緣太軟的核心區域

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R55](<../R55_SourceStyleRealisticTraining/FILE_GUIDE.md>) · [下一輪 Lab R57](<../R57_GeometryConstrainedMOSR/FILE_GUIDE.md>)

**一句話：** R55 把答案改成原圖的灰階風格之後，有些答案的邊緣核心太軟。R56 只重建這些弱邊緣（7,740 組裡的 589 組），其他照舊、從零訓練 50 輪。角點中位數跟 R55 一樣，但大偏移變多，所以沒過角點門檻；有趣的是，6/18 的外部 GMF 裡 R56 best 反而是所有候選中最好的。

| | |
|---|---|
| 結果 | **未採用**（實拍角點門檻沒過；外部 GMF 排第一但只比原圖好 2.2%） |
| 時間 | 2026-06-18 |
| 實驗條件 | C：實驗室顯微系統；驗證用 2025-06-05 拍的實拍棋盤序列（20×，51 張、358 個角點） |
| 訓練 | 從零 50 輪，批次 16，PSF 前向損失關閉，與 R55 相同 |

## 這輪在問什麼

R55 的答案已經不再是假的黑白二值，但部分答案的邊緣梯度太弱。只把這些核心修清楚，能不能在不動整體資料組成的前提下改善實拍角點？

## 怎麼做

- 以 R55 的 6,000 組訓練資料與 1,740 組驗證資料為底，找出邊緣梯度比低於 1.5 的答案，從原圖的局部亮度重建邊緣核心；舊的 CAD 答案只用來找邊界帶，不直接貼回黑白填色。訓練集修了 452 組，驗證集 137 組。
- 訓練設定完全沿用 R55，方便直接比較。

## 結果

**實拍棋盤角點**（角點反應位置相對原圖的偏移；門檻是跟 Lab R40 比，中位數要更好、大偏移比例和第 75 百分位不能更差）：

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 | 門檻 |
|---|---:|---:|---:|---|
| 原圖 | 1.414 | 2.236 | 1.7% | — |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% | 基準 |
| Lab R55 best | 2.828 | 3.606 | 21.8% | 通過 |
| **R56 best** | 2.828 | 9.899 | 26.8% | 未過 |
| R56 latest | 9.899 | 9.899 | 59.8% | 未過 |

**外部 GMF**（同一序列，Y 方向步距標準差，跳過第一步）：R56 best 0.2580 px 在 11 個候選中排第一，原圖 0.2639 px、R40 對照 0.2581 px、R55 best 0.2667 px。

## 讀這些數字要知道的事

1. **角點和 GMF 給出相反的排序。** 角點門檻上 R55 best 最好、R56 best 沒過；外部 GMF 上 R56 best 最好、R55 best 反而比原圖差。兩邊差距都很小，GMF 的差異只有 1～3%。
2. **所有模型的角點都比原圖差很多。** 原圖只有 1.7% 的角點偏移超過 5 px，最好的模型也有 20% 以上。門檻是跟 R40 比，不是跟原圖比。
3. **latest 又一次比 best 差很多。** 內部驗證到第 50 輪還在進步（PSNR 26.40、SSIM 0.9333），實拍角點卻退到 59.8%；這是 R53 以來反覆出現的現象。
4. 下一輪 R57 從 R55 best 起步，不是從 R56。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 啟動、重建、角點驗證程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 答案修補摘要與資料清單 | [修補摘要](<results/archive_retained_20260926/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration/REPAIR_SUMMARY.md>)；修補程式在 [`Training_Data/scripts/repair_source_style_label_core.py`](<../../Training_Data/scripts/repair_source_style_label_core.py>) |
| 外部 GMF 分數 | [R51～R56 外部 GMF 摘要](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/Y_DISPLACEMENT_SUMMARY.md>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 7,740 組修補後的訓練資料與完整訓練紀錄，2026-09-26 已移到外接硬碟的完整封存（見 [封存入口](<ARCHIVE_POINTER_R56_20260926.md>)），原電腦與 GitHub 只保留報告、程式和資料清單。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 設計、訓練與重建的路徑 |
| [R56 結果](<reports/R56_RESULTS.md>) | 為什麼做這輪、結果與判讀 |
| [實拍棋盤驗證](<reports/R56_CHECKBOARD_VALIDATION.md>) | 完整角點表與門檻結果 |
| [封存入口](<ARCHIVE_POINTER_R56_20260926.md>) | 2026-09-26 的封存與清理紀錄 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R56_LabelCoreRepairTraining.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。

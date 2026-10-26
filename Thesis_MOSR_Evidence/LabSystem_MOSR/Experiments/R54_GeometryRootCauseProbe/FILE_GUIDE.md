# Lab R54：角點到底是怎麼被弄壞的

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R53](<../R53_RealisticDatasetCalibration/FILE_GUIDE.md>) · [下一輪 Lab R55](<../R55_SourceStyleRealisticTraining/FILE_GUIDE.md>)

**一句話：** R53 用更大、更真實的資料從零訓練 100 輪，實拍角點反而更差。R54 先不再長訓練，改做診斷：用 36 組嚴格矩形 CAD 參考，只在可信區域與邊界帶上做小樣本過擬合。結果模型在 CAD 區域內學得很好（誤差從 61 降到 9），但同一個模型拿去重建實拍棋盤，60% 的角點偏移超過 5 px。結論是模型學得會邊緣，問題在於它會把真實影像改得太多。

| | |
|---|---|
| 結果 | **分析**（確認「可信區域內學得會，轉到實體全圖就失敗」；這個檢查點不能當模型用） |
| 時間 | 2026-06-16 |
| 實驗條件 | C：實驗室顯微系統；6/13 的嚴格矩形 CAD 參考，驗證用 2025-06-05 的實拍棋盤序列 |
| 起點 | Lab R40 的 `best_tradeoff`，在 72 組小資料上訓練 20 輪 |

## 這輪在問什麼

重複的實拍角點失敗，是因為訓練量不夠，還是重建本身就在改變角點幾何？

## 怎麼做

1. **整理證據，列假設。** 原圖只有 1.7% 的角點偏移超過 5 px，所有重建都在 24.6%（R40）到 58.9%（R53 latest）之間。四個假設的判斷：
   - 重建本身會損壞實拍角點：**支持**
   - 更多通用資料就夠：**相反**（R53 資料更大，角點更差）
   - 嚴格矩形 CAD 可以當小樣本監督：**支持**（36 組全部通過邊緣品質檢查）
   - PSF 是唯一原因：**未證實**
2. **小樣本過擬合。** 第一版的可信區域幾乎都落在平坦的內部、把邊界排除掉了，模型只學會把局部變白，結果不算數。修正後的版本加上 CAD 邊界帶，每一組都包含真正的邊界，共 72 組。

## 結果

**CAD 小資料包內**（可信區域內與答案的平均絕對誤差，灰階）：

| 影像 | 區域內誤差 | 區域外漂移 |
|---|---:|---:|
| 原圖 | 61.1 | 0 |
| Lab R40 | 50.1 | 5.9 |
| R54 第 5 輪 | 13.8 | 4.4 |
| R54 第 20 輪 | 9.3 | 7.2 |

**實拍棋盤角點**：R54 第 20 輪的中位數偏移 9.22 px，60.1% 的角點超過 5 px；跟原圖逐角點比，358 個角點裡 286 個變差。它對實拍影像的平均改動是 7.3 灰階，其他模型大約 1.4～1.5。

**外部 GMF**：R54 的分數檔有重複的檔名，步距標準差 1.53 px，完全失真（見 [R51～R56 外部 GMF 摘要](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/Y_DISPLACEMENT_SUMMARY.md>)）。

## 讀這些數字要知道的事

1. **CAD 參考只能當局部監督。** 可信區域的中位數覆蓋率只有 1.6%，不能當整張影像的答案。
2. **小樣本是為了回答問題，不是為了得到模型。** 報告明確寫不要從這個檢查點繼續訓練。
3. 報告引用的 `results/` 不在 git 裡。其中 15 個小檔（診斷 JSON、假設表等，共約 0.4 MB）在 release 附件裡，但分散在 5 個大附件中（要下載約 5 GB）；對照圖和預覽圖只在原電腦上。可用 `cloud_locator.py where` 逐檔查。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 診斷、小樣本建置、啟動、評估、重建程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub；指令見 [README](<README.md>) |
| 訓練資料路徑清單 | [reports/R54_TRAINING_DATASET_PATHS.txt](<reports/R54_TRAINING_DATASET_PATHS.txt>) |
| 6/13 的嚴格矩形 CAD 參考 | 見 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 報告 | 內容 |
|---|---|
| [診斷](<reports/R54_DIAGNOSTIC.md>) | 角點損壞證據、CAD 參考品質、四個假設 |
| [小樣本過擬合](<reports/R54_MASKED_SMALL_PROBE.md>) | 第一版為什麼無效、修正版在 CAD 區域內的結果 |
| [實拍棋盤驗證](<reports/R54_CHECKBOARD_VALIDATION.md>) | 角點表與逐角點比較 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 設計、輸入與所有產出位置 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__R54_GeometryRootCauseProbe.md>)與 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。

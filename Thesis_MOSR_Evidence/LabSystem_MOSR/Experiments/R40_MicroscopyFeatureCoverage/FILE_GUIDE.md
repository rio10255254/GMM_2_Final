# Lab R40：在 Lab 光學條件下重做顯微特徵版

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [同時進行的 Lab R39](<../R39_ShapeGeneralization/FILE_GUIDE.md>) · [下一輪 Lab R46](<../R46_CornerAwareFineTune/FILE_GUIDE.md>) · [主專案的 R40](<../../../../Experiments/R40_MicroscopyFeatureCoverage/FILE_GUIDE.md>)

**一句話：** Lab 研究的起點之一。沿用主專案 R40 的做法（顯微特徵覆蓋），但改用實驗室自己量的 25 位置 PSF 和自己生成的 1,300 組資料，從 COMBO 的權重起步，6/8 先跑 25 輪、6/9 正式跑 100 輪。內部品質比 Lab R39 低；但它的 `best_tradeoff`（第 44 輪）在實拍棋盤上角點最穩，成為之後 R46～R56 所有角點門檻的對照基準。

| | |
|---|---|
| 結果 | **研究候選**（當後續角點實驗的固定對照） |
| 時間 | 2026-06-08 25 輪起步；06-09 正式 100 輪；06-11 實拍 GMF 與角點驗證 |
| 實驗條件 | C：實驗室顯微系統、Lab 25 位置 BADS PSF；驗證用 2025-06-05 的實拍棋盤序列（20×） |
| 起點 | COMBO 權重（拿掉舊的 PSF 緩衝區，改用 Lab PSF 重建） |

這是 LabSystem 的 R40，跟主專案的 R40 不是同一份訓練。

## 這輪在問什麼

主專案 R40 的顯微特徵資料，搬到實驗室的光學條件下重做，能不能得到可用的 Lab 模型？

## 怎麼做

- **資料：** 1,300 組 Lab 顯微訓練資料（矩形 50 組、微格線 80 組，**沒有棋盤**），另有 100 組顯微驗證。
- **模型搬移：** COMBO 的權重保留，只拿掉 4 個和舊 PSF 網格綁在一起的緩衝區，建模型時用 Lab 的 25 位置 PSF 重建。
- **訓練：** 6/8 先 25 輪驗證流程可行；6/9 正式 100 輪，不使用快速驗證。

## 結果

| 項目 | Lab R39 | Lab R40 |
|---|---:|---:|
| 100 輪最佳 PSNR／SSIM | 33.43／0.9808 | 29.01／0.9394 |
| 訓練程式挑的 `best_tradeoff` | 第 21 輪 | 第 44 輪 |
| 外部 GMF（實拍棋盤，對原圖）latest／tradeoff | −1.16%／−2.39% | −2.02%／−2.01% |
| 角點中位偏移 latest／tradeoff（px） | 3.606／9.220 | 3.606／**4.243** |
| 角點超過 5 px 的比例 latest／tradeoff | 47.8%／52.5% | 38.3%／**24.6%** |

（原圖：外部 GMF 步距標準差 0.2607 px；角點中位偏移 1.414 px，超過 5 px 只有 1.7%。）

## 讀這些數字要知道的事

1. **GMF 的小改善主要被一個共同的異常步距影響。** 16:07:42 到 16:08:18 那一步五個案例都跳到約 7.4 px；只為診斷把它拿掉後，tradeoff 兩個保存點小贏原圖，latest 打平或略差。
2. **角點驗證才是關鍵發現。** 所有重建都把角點的最強反應移離原本的位置，而 R39、R40 的訓練資料裡完全沒有棋盤；這引出了 R46 以後的整條角點研究。
3. **這個資料夾沒有自己的報告。** README 是建立時寫的（「只放了資料建置程式」），訓練與驗證的報告都在共用的 [Lab reports 資料夾](<../reports>)。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 外部 GMF 原始分數 | [`external_gmf_results/`](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_results/README.md>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 報告 | 內容 |
|---|---|
| [Lab 訓練起步（6/8）](<../reports/LAB_TRAINING_BOOTSTRAP_20250608.md>) | 權重搬移方式、25 輪結果、快速驗證的注意事項（檔名日期寫成 2025，內容是 2026-06-08） |
| [第一次 100 輪正式訓練（6/9）](<../reports/LAB_FORMAL_TRAINING_100E_20260609.md>) | R39、R40 的完整訓練與保存點 |
| [實拍棋盤外部 GMF（6/11）](<../reports/LAB_CHECKBOARD_EXTERNAL_GMF_20260611.md>)、[GMF 診斷](<../reports/LAB_CHECKBOARD_GMF_DIAGNOSTIC_20260611.md>)、[GMF 根因深查](<../reports/LAB_GMF_ROOT_CAUSE_DEEP_PROBE_20260611.md>) | 為什麼主專案 GMF 改善明顯、Lab 卻很小 |
| [實拍棋盤角點驗證（6/11）](<../reports/LAB_CHECKBOARD_CORNER_VALIDATION_20260611.md>) | 角點被移走的證據與訓練資料覆蓋稽核 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__R40_MicroscopyFeatureCoverage.md>)與 [Lab 全線的五個共用階段](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>)。

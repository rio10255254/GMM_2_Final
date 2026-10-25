# Lab R39：在 Lab 光學條件下重做多形狀版

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [同時進行的 Lab R40](<../R40_MicroscopyFeatureCoverage/FILE_GUIDE.md>) · [下一輪 Lab R46](<../R46_CornerAwareFineTune/FILE_GUIDE.md>) · [主專案的 R39](<../../../../Experiments/R39_ShapeGeneralization/FILE_GUIDE.md>)

**一句話：** Lab 研究的起點之一。沿用主專案 R39 的多形狀資料做法，改用實驗室自己量的 25 位置 PSF 和自己生成的 1,240 組資料，從 COMBO 的權重起步，6/8 先跑 25 輪、6/9 正式跑 100 輪。內部品質是兩條線中最好的（PSNR 33.43），也是 R46、R47、R48 的起點；但在實拍棋盤上，它會把角點移走，tradeoff 保存點超過一半的角點偏移超過 5 px。

| | |
|---|---|
| 結果 | **研究候選**（當後續角點實驗的起點與對照） |
| 時間 | 2026-06-08 25 輪起步；06-09 正式 100 輪；06-11 實拍 GMF 與角點驗證 |
| 實驗條件 | C：實驗室顯微系統、Lab 25 位置 BADS PSF；驗證用 2025-06-05 的實拍棋盤序列（20×） |
| 起點 | COMBO 權重（拿掉舊的 PSF 緩衝區，改用 Lab PSF 重建） |

這是 LabSystem 的 R39，跟主專案的 R39 不是同一份訓練。

## 這輪在問什麼

主專案 R39 的多形狀資料，搬到實驗室的光學條件下重做，能不能當 Lab 的第一個可用模型？

## 怎麼做

- **資料：** `r39_shape_mix_safe` 1,240 組（矩形只有 20 組，**沒有棋盤**），另有較強版本 1,590 組與 210 組形狀驗證。Lab 的基礎資料是 stage01～33 共 2,968 張生成影像，比主專案的 8,668 張少。
- **模型搬移與訓練：** 跟 Lab R40 相同，見 [Lab R40](<../R40_MicroscopyFeatureCoverage/FILE_GUIDE.md>)。

## 結果

| 項目 | Lab R39 | Lab R40 |
|---|---:|---:|
| 100 輪最佳 PSNR／SSIM | **33.43／0.9808** | 29.01／0.9394 |
| 訓練程式挑的 `best_tradeoff` | 第 21 輪 | 第 44 輪 |
| 外部 GMF（實拍棋盤，對原圖）latest／tradeoff | −1.16%／**−2.39%** | −2.02%／−2.01% |
| 角點中位偏移 latest／tradeoff（px） | 3.606／9.220 | 3.606／4.243 |
| 角點超過 5 px 的比例 latest／tradeoff | 47.8%／52.5% | 38.3%／24.6% |

## 讀這些數字要知道的事

1. **外部 GMF 和角點給出不同的答案。** R39 tradeoff 的外部 GMF 是五個案例中最好的，角點卻是最差的；之後 Lab 研究改以角點門檻為主，對照選了 R40 tradeoff。
2. **自動挑的 tradeoff 不是驗證品質最好的保存點。** 6/9 報告建議下一步先用第 100 輪（latest）做推論。
3. **這個資料夾沒有自己的報告**，訓練與驗證的報告都在共用的 [Lab reports 資料夾](<../reports>)，清單見 [Lab R40](<../R40_MicroscopyFeatureCoverage/FILE_GUIDE.md>) 的原始報告一節。
4. 主專案後來另外做了 [R39 外部 GMF 的形狀推廣](<../../../../Experiments/R39_ShapeGeneralization/FILE_GUIDE.md>)，那是條件 A（公司圓環影像），數字不能跟這裡比。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 外部 GMF 原始分數 | [`external_gmf_results/`](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_results/README.md>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

見 [Lab R40 的原始報告一節](<../R40_MicroscopyFeatureCoverage/FILE_GUIDE.md#原始報告>)：6/8 起步、6/9 正式訓練、6/11 的外部 GMF、GMF 診斷與角點驗證，都是 R39、R40 一起寫的。

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__R39_ShapeGeneralization.md>)與 [Lab 全線的五個共用階段](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>)。

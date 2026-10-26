# R116：先建幾何錨點，再只加局部零均值的細節

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R115](<../R115_R109DecoupledNormalProfileScratch/FILE_GUIDE.md>) · [下一輪 R117](<../R117_CenterLockedSubpixelScratch/FILE_GUIDE.md>) · [證據來源 R109](<../R109_StagedMidpointWidthScratch/FILE_GUIDE.md>)、[R112](<../R112_V42R109GMFMechanismDecomposition/FILE_GUIDE.md>)、[R113](<../R113_CausalStructureDissection/FILE_GUIDE.md>)、[R114](<../R114_ConfidenceGatedRecoverableScratch/FILE_GUIDE.md>)

**一句話：** 整合 R109～R115 的證據，R116 不再把「修不修、移多少、變多窄、補多少細節」塞進同一條路徑：邊界座標、寬度、位移、細節用各自獨立的可訓練塔；寬度與位移沿局部輪廓方向保持連續（不是二維模糊）；原圖先依法線位移變形成「幾何錨點」，之後只加有原圖證據、局部平均為零、幅度受限的細節。2026-09 初從零訓練 48 輪（第一次在第 7 輪因 BF16 數值問題停下，修好後重來）。第 42 輪是主要研究候選：實拍位移六組都通過、SEM 36/36 顆粗輪廓改善；但 LSC 位移仍落後 R109／V42，R74 兩類退步，SEM 周長變差。

| | |
|---|---|
| 結果 | **研究候選**（修正 BF16 錯誤後重新從零，第 42 輪為主要版本） |
| 時間 | 2026-09-03～09-04 |
| 實驗條件 | 程式資料：5,512 個不重複場景，訓練與驗證零重疊、零真實像素；訓練可用同一形狀的多個合成觀測，部署仍是一次一張 |
| 起點 | 隨機初始化 |

## 結果（第 42 輪）

| 項目 | 結果 |
|---|---|
| R73 邊界 | 改善 22.95%，五類全部改善 |
| R74 邊界 | **退步 4.28%**，低對比與混合困難仍弱 |
| 36 顆柱 SEM 粗輪廓 | 36/36 顆改善，中位改善 0.0326% 柱距（95% 區間 0.0262～0.0356），最暗曝光多數也改善 |
| SEM 周長 | 28/36 顆變差 |
| 實拍位移 | 六組全部通過，方向一致 100% |
| LSC 位移 | 步距標準差 8.067 nm、九顆柱內標準差 5.456 nm，**落後 R109／V42** |
| 切塊一致 | 最差平均 0.00035、p99 0.0025、最大 0.018 灰階 |

## 讀這些數字要知道的事

1. **三個保存點各有角色：** 第 24 輪是幾何與 LSC 的備用；第 42 輪是主要研究候選；第 48 輪雖然改善了部分合成校準指標，但共用 SEM 明顯退步，所以不選。
2. **外部 GMF 包已備好（101 張），但沒有分數。** 第 42 輪對均華影像的中位改動只有 0.0084 灰階。
3. **第一次正式訓練作廢。** 第 7 輪時寬度可信度損失裡的 BF16 機率截斷剛好捨入成 1；之後所有損失的歸約改用 FP32，原本出錯的第 59 批與全部 138 個寬度批次都通過，才授權第二次從零訓練。
4. **不能取代 R109、R61 或 V42。**

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 架構驗證、資料準備、訓練、反事實探針與其他程式 | 本資料夾，已在 GitHub；入口見 [README](<README.md>) |
| 詳細驗證的總表 | [results/detailed_validation/](<results/detailed_validation/R116_DETAILED_VALIDATION_ZH.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [架構決策](<reports/R116_ARCHITECTURE_DECISION_ZH.md>) | 過去證據怎麼導向這個設計、六項根本改動、訓練策略、升格條件 |
| [詳細驗證](<results/detailed_validation/R116_DETAILED_VALIDATION_ZH.md>) | 通過與沒通過的項目、各保存點的角色 |
| [README](<README.md>) | 目前狀態與 BF16 修正 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R116_CoherentGeometryAnchorScratch.md>)。

# R102：局部主幹同時恢復細節與位置，結果輸出跟原圖一樣

[研究時間線](<../../docs/research/TIMELINE.md>) · [根因設計 R101](<../R101_HighFrequencyDesignValidation/FILE_GUIDE.md>) · [前一輪 R101 短測](<../R101_HighFrequencyCausalAblation/FILE_GUIDE.md>) · [下一輪 R103](<../R103_RecoverableDetailScratch/FILE_GUIDE.md>)

**一句話：** R102 依 R101 的方向做一次正式從零訓練，用 R92 的 5,000 個觀察加上確定性的擴增。2026-08-15 啟動，計畫 48 輪；但到第 40 輪模型在數值上、視覺上都還是原圖：對四張實拍的平均改動只有約 0.0001 灰階，輪廓與紋理驗證都沒有改善，使用者在第 41 輪中途停下。

| | |
|---|---|
| 結果 | **中止**（輸出塌縮成原樣；第 41 輪中途停止，最後保存第 40 輪） |
| 時間 | 2026-08-15（12:55 啟動，14:21 停止） |
| 實驗條件 | R92 固定合成資料（16.9 GiB 不複製，只存參照）加確定性擴增 |
| 起點 | 隨機初始化，種子 1020053；初始等同原圖 |

## 結果：塌縮診斷

**第 40 輪對四張實拍的平均改動（灰階）：** 5× 密集 0.000086、20× 混合 0.000086、50× 陣列 0.000086、中心九顆柱 0.00015。

**資料本身就在要求平滑：** 基礎資料的來源與答案高頻相關係數只有 0.039，答案的高頻幅度（1.16 灰階）遠小於來源（5.49 灰階）；連「創新」資料的相關係數也只有 0.059。

## 讀這些數字要知道的事

1. **停止紀錄與塌縮診斷不在 GitHub 程式樹上**（`reports/USER_STOP_AND_IDENTITY_COLLAPSE_20260815.json`、`deep_identity_collapse.json` 等五個小 JSON，共約 31 KB），在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 的壓縮包裡（要下載的附件約 2 GB）；上面的數字是從那兩份讀的。
2. **不續訓、另開新實驗。** 停止紀錄寫明替代方式是新的隔離實驗與隨機初始化，也就是 R103。
3. 診斷程式 [analysis/deep_identity_collapse.py](<analysis/deep_identity_collapse.py>) 在 GitHub 上。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 設定、資料參照、模型、訓練、推論、評估、測試、診斷程式 | 本資料夾 [config/](<config>)、[data/](<data>)、[model/](<model>)、[training/](<training>)、[inference/](<inference>)、[evaluation/](<evaluation>)、[tests/](<tests>)、[analysis/](<analysis>)，已在 GitHub |
| 訓練從零開始的證明 | [runs/](<runs>) 的 `scratch_proof.txt` |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R102_UniversalDetailScratch.md>)。

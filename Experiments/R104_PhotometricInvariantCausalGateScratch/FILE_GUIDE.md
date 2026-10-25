# R104：形狀判斷只看局部相對亮度，不看絕對亮度

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R103](<../R103_RecoverableDetailScratch/FILE_GUIDE.md>) · [下一輪 R105A](<../R105A_GeometryRendererFalsification/FILE_GUIDE.md>) · [R100～R104 完整結果的閱讀入口](<../../docs/reproducibility/project_completion/curated/FAILURE_LINEAGE_READING.md>)

**一句話：** R103 的 SEM 反應在第 18 號曝光附近翻轉，幾何明明沒變；它保留了共用照明，而不是學到不受照明影響的形狀證據；信心最低也只能把修正縮到 0.75。R104 保留 R103 的主幹，讓形狀與「需不需要修」的判斷只用局部相對線索，形狀用有號距離場預測（不假設圓），亮暗、照明、輪廓、紋理的提案各自跟一個真正 0～1 的需求閘分開，同一幾何在多種曝光與照明下要做出一致的判斷。2026-08-15 從零完成 48 輪。結果形狀頭沒有直接形成最終邊界，SEM 上 36 顆全部比原圖差。

| | |
|---|---|
| 結果 | **未採用**（幾何頭沒有直接形成最終邊界，交給 R105 驗證） |
| 時間 | 2026-08-15（22:28 啟動，48 輪） |
| 實驗條件 | R92 固定合成資料，每輪線上產生 5,000 個觀察；實拍與 SEM 只用於後測 |
| 起點 | 隨機初始化，種子 1040059 |

## 結果（36 顆柱 SEM，12 張曝光）

| 方法 | IoU 中位數 | 平均邊界距離（% 柱距） | 周長誤差 |
|---|---:|---:|---:|
| 原圖 | 0.9490 | 0.5697 | 2.86% |
| R61 v16 | **0.9584** | **0.4413** | 3.71% |
| R104 第 48 輪 | 0.9449 | 0.6171 | 3.53% |

R104 對原圖的 IoU 改善中位數 −0.0039，**0/36 顆改善**（Wilcoxon p = 2.9e-11）。

## 讀這些數字要知道的事

1. **README 寫「正式訓練尚未授權」**，那是設計時的狀態；實際已完成 48 輪並做完實拍與 SEM 後測。
2. **完成的原件不代表當時所有構想都成真。** 形狀頭預測了有號距離場，但最終輸出的邊界不是由它直接畫出；R105A 就是去驗證「直接用預測的幾何畫邊界」行不行。
3. 第 48 輪是內部測試選出的。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 完整後測表（50 檔，含 SEM 整體與逐曝光結果） | 本資料夾 [results/posttraining_validation/](<results/posttraining_validation>)，已在 GitHub |
| 模型、訓練、推論、設計前檢查 | 本資料夾 [model/](<model>)、[training/](<training>)、[inference/](<inference>)、[reports/](<reports>) |
| 訓練資料參照 | [data/TRAINING_DATA_REFERENCE.json](<data/TRAINING_DATA_REFERENCE.json>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [SEM 輪廓摘要](<results/posttraining_validation/sem_contour/summary.json>) | 整體與每個曝光的結果 |
| [曝光相關的輪廓對照圖](<results/posttraining_validation/sem_contour/figures/exposure_comparison.png>) | 保留較差的結果 |
| [精選結果閱讀紀錄](<reports/R104_SELECTED_RESULT_RECORDS_20261021.md>) | 2026-10-21 補的閱讀脈絡 |
| [README](<README.md>) | 為什麼開這輪與七項介入（設計時的版本） |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R104_PhotometricInvariantCausalGateScratch.md>)。

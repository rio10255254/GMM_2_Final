# R100：在原有形狀上加入輪廓外的程式紋理

[研究時間線](<../../docs/research/TIMELINE.md>) · [訓練前的設計檢查](<../R100_DesignValidation/FILE_GUIDE.md>) · [前一輪 R99](<../R99_GeometryTextureCoherentScratch/FILE_GUIDE.md>) · [下一輪 R101](<../R101_HighFrequencyCausalAblation/FILE_GUIDE.md>) · [R100～R104 完整結果的閱讀入口](<../../docs/reproducibility/project_completion/curated/FAILURE_LINEAGE_READING.md>)

**一句話：** R92 的 1,250 個場景、5,000 個觀察逐位元不變，R100 只在記憶體裡多加少量不接觸輪廓的程式紋理觀察，2026-08-14 從零訓練 40 輪（預先固定的終點）。後測顯示 SEM 輪廓幾乎跟原圖一樣（IoU 只多 0.00016，36 顆中 32 顆小幅改善）；真實影像看起來接近原圖，但那不代表答案準確。之後 R101 拆解為什麼細頻細節學不起來。

| | |
|---|---|
| 結果 | **未採用**（40 輪；另有訓練前的設計檢查） |
| 時間 | 2026-08-14 |
| 實驗條件 | R92 固定合成資料加線上紋理；實拍 301 張與 36 顆柱 SEM 只用於後測 |
| 起點 | 隨機初始化 |

## 結果（36 顆柱 SEM，12 張曝光）

| 方法 | IoU 中位數 | 平均邊界距離（% 柱距） |
|---|---:|---:|
| 原圖 | 0.9492 | 0.5677 |
| R61 v16 | 0.9554 | 0.4898 |
| V42 第 120 輪 | 0.9512 | 0.5448 |
| R100 第 40 輪 | 0.9493 | — |

（R100 的 SEM 後測與 R69 用的是同一批柱與曝光，但數值是這次重新擷取的，所以原圖、R61 的數字跟 R69 略有差異。）

實拍位移有 6,672 筆鎖定量測，跨方法共同有效 5,860 筆。

## 讀這些數字要知道的事

1. **第 40 輪是事先固定的終點，不是挑出來的最佳輪。**
2. **SEM 只能解釋成對的形狀**，不能當光學亮度或紋理的真實答案；12 張曝光是重複觀察，不增加獨立樣本。
3. 為什麼 R100 的細節學不起來，見 [R101 設計檢查](<../R101_HighFrequencyDesignValidation/FILE_GUIDE.md>)：E8 起實拍細節倍率從 1.02 掉到 0.84，之後一直沒恢復。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 完整後測表（內部測試、模型內部、實拍泛化、SEM 輪廓，共 28 檔） | 本資料夾 [results/posttraining_validation/](<results/posttraining_validation>)，已在 GitHub |
| 模型、訓練、推論程式 | 本資料夾 [model/](<model>)、[training/](<training>)、[inference/](<inference>) |
| 第 40 輪模型的身分與位置 | 見 [R100～R104 閱讀入口](<../../docs/reproducibility/project_completion/curated/FAILURE_LINEAGE_READING.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 啟動與資料安排（啟動前的說明，原樣保留） |
| [精選結果閱讀紀錄](<reports/R100_SELECTED_RESULT_RECORDS_20261021.md>) | 2026-10-21 補的閱讀脈絡 |
| [SEM 外形對照圖](<results/posttraining_validation/sem_contour/figures/r100_sem_contour_overlay.png>) | 要跟完整七方法表一起看 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R100_CausalOperatorScratch.md>)。

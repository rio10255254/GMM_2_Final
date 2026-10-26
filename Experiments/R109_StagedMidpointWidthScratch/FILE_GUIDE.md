# R109：先找邊界，再學「沿法線移動」與「收窄寬度」

[研究時間線](<../../docs/research/TIMELINE.md>) · [依據 R108G](<../R108G_MidpointWidthFactorizedProfileMicroprobe/FILE_GUIDE.md>) · [延伸探針 R110](<../R110_TimeCapacityVisibilityProbes/FILE_GUIDE.md>) · [能不能取代 V42：R111](<../R111_R109V42ThesisReplacementQualification/FILE_GUIDE.md>) · [機制拆解 R112](<../R112_V42R109GMFMechanismDecomposition/FILE_GUIDE.md>)、[R113](<../R113_CausalStructureDissection/FILE_GUIDE.md>)

**一句話：** 把 R108G 的核心做成第一個完整的從零訓練：單張輸入、可切塊的局部運算，邊界中點的法線位移與過渡寬度修正是兩個分開、單調的因子，不能輸出自由的影像殘差，也不能超出局部原圖的亮度範圍。先訓練偵測器找邊界再凍結，之後訓練渲染器。2026-08-26 完成 48 輪，第 48 輪在 R73、R74、SEM、實拍位移上都比原圖好，是當時最強的新一代從零候選；但 SEM 專項仍不如 R79 第 23 輪。

| | |
|---|---|
| 結果 | **研究候選**（48 輪；內部量法與外部 GMF 判讀不同） |
| 時間 | 2026-08-26 |
| 實驗條件 | 程式生成：5,000 個訓練場景（硬連結自 R107 的資料，不多佔 1.35 GB）、512 個固定驗證場景，每個場景同時有退化圖與完全清楚的反例 |
| 起點 | 隨機初始化；前 6 輪只學輪廓位置並凍結，後 42 輪學連續的位移與寬度倍率 |

## 結果（第 48 輪）

| 測試 | 原圖 | R109 |
|---|---:|---:|
| R73 邊界距離 | 0.2847 px | **0.1658 px** |
| R74 邊界距離 | 7.2418 px | **2.4989 px** |
| SEM 每柱邊界距離（% 柱距） | 0.5697 | **0.5345** |
| SEM 每柱周長誤差 | 2.8647% | **2.6920%** |
| 實拍位移（301 張、6,672 筆） | — | 六組全部通過 |

5× 幾乎保持原圖、20× 中度增強、50× 明顯增強，沒有肉眼可見的黑環。

## 讀這些內容要知道的事

1. **第一次正式訓練作廢。** `r109_formal_scratch_20260826` 在第 8 輪停下，因為「需不需要修」的二元判斷一直分不開；完整資料證明這個開關無法區分「天然較寬的清楚邊界」與「被模糊的窄邊界」，所以正式版拿掉開關，清楚影像的正確答案就是位移 0、倍率 1。新的正式訓練是 `r109_formal_scratch_continuous_20260826`。
2. **跟 R79 第 23 輪比，SEM 專項仍明顯較弱**（R79 是 0.2405% 柱距）；最終要替代必須經過封閉比較。
3. **內部量法與外部 GMF 的判讀不同：** R111 用確定性 LSC 量時 R109 跟 V42 相當，但均華的外部 GMF 上 V42 穩定得多，見 R111、R112。
4. **R113 後來發現**，R109 的「邊界支撐」判斷幾乎是常數（0.432），沒有真正學起來。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料準備、模型、訓練、推論、驗證程式與 PowerShell 入口 | 本資料夾，已在 GitHub；用法見 [README](<README.md>) |
| 選定的第 48 輪權重（2.6 MB） | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，原路徑 `weights/selected/R109.pth`（同一個附件約 1.6 GB） |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R108C 到 R109 的設計與證據鏈](<reports/R108C_TO_R109_DECISION_CHAIN_ZH.md>) | 先讀這份：R108C～G 每一步學到什麼、SEM 邊界剖面揭露 R79 做對的事、R109 的正式策略 |
| [第 48 輪最終選擇](<reports/R109_FINAL_SELECTION_ZH.md>) | 選定權重與主要數字 |
| [README](<README.md>) | 架構與使用方式 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R109_StagedMidpointWidthScratch.md>)。

# R88：把歷代失敗全部列成清單，再從零訓練一次

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R87](<../R87_TileNativeScratchGeneralization/FILE_GUIDE.md>) · [下一輪 R89](<../R89_MeasurementNativeScratch/FILE_GUIDE.md>)

**一句話：** R88 先把 R39 到 R87 每一輪暴露的問題整理成一份「歷代問題清單」，每個設計都對應一條失敗證據，再完全從隨機權重訓練：答案 8 倍繪製、正負與零位移用相同成像、近原圖資料約束不亂改、修正量受限而且信心不足就保留原圖、大圖推論固定每邊 192 px 上下文。結果模型太保守，對真實 50× 影像幾乎原圖照抄，沒有任何驗證輪次過關，2026-08-11 在第 87 輪停下。

| | |
|---|---|
| 結果 | **中止**（停在第 87 輪；保留為失敗案例，不續跑、不當起點） |
| 時間 | 2026-08-10 啟動，08-11 00:08 停止（最後保存第 85 輪） |
| 實驗條件 | 純合成：1,280 個正式場景、5,120 個觀察，另有 384 個封存盲測場景 |
| 起點 | 隨機初始化 |

## 這輪在問什麼

如果一次就把輪廓、ACM、位移、真實紋理、大圖切塊一致性全部當成要過的門檻，從零訓練能不能同時達到？

## 結果：近原圖輸出的根因

| 訊號 | 數字 |
|---|---|
| 第 50 輪對真實 50× 的平均改動 | 0.81 灰階（九顆柱區域最多只改 1 階） |
| 第 70 輪未經信心限制的候選修正 | 5.76 灰階，最後只保留 42.6% |
| 第 70 輪合成輪廓 | 比原圖改善 13.5%，但紋理退化 3.2% |
| 第 70 輪位移誤差 | 預定上限的 4.73 倍 |
| 位移驗證視圖裡完全沒有前景的 | 8/40 個 |

診斷列出的原因：模型一開始就被設計成原圖直通、只在有把握時加小修正，不熟悉的影像最安全的答案就是不動；資料完全是程式合成、連允許的匿名光學統計都沒實際導入；部分答案與輸入的差距超過模型允許的最大修正；位移裁切常常沒有前景；同一個模型同時承受太多互相拉扯的目標。

## 讀這些內容要知道的事

1. **歷代問題清單本身很有價值。** 它用已完成的報告數字，整理了 R39～R87 每一類失敗，是讀第五、六階段的好入口。
2. **驗收門檻是事先鎖定的**（`config/acceptance_gates.json`，人讀版在 [R88_ACCEPTANCE_GATES.md](<reports/R88_ACCEPTANCE_GATES.md>)），包括參考圓量法下要達到 R81 的最佳值。
3. **真實 50× 位移的中途診斷**只是探索，不參與選模；外部 GMF 當時沒有授權，用類似原理的區域圖樣對齊代替，不能稱為外部 GMF 分數。
4. 原首頁停留在啟動時的狀態，2026-10-21 才改成正確的停止狀態；修正前的原文另有保存。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 鎖定的設計、門檻、授權與實作雜湊；模型、訓練、推論、資料生成程式 | 本資料夾 [config/](<config>)、[model/](<model/README.md>)、[training/](<training/README.md>)、[inference/](<inference/README.md>)、[scripts/](<scripts/README.md>)，已在 GitHub |
| 診斷與中途位移報告 | [results/](<results/README.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 合成資料只在原電腦上。正式與短測的權重不在 GitHub 程式樹上，在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 的壓縮包裡。

## 原始報告

| 文件 | 什麼時候讀 |
|---|---|
| [歷代問題清單](<reports/R88_PROBLEM_LEDGER.md>) | 想快速知道 R39～R87 各自錯在哪 |
| [實驗設計](<reports/R88_EXPERIMENT_DESIGN.md>)、[文獻整理](<reports/R88_LITERATURE_SYNTHESIS.md>)、[驗收門檻](<reports/R88_ACCEPTANCE_GATES.md>) | 設計與事先鎖定的門檻 |
| [近原圖輸出的根因診斷](<results/diagnosis_near_identity_behavior/DIAGNOSIS_zh-TW.md>) | 為什麼模型幾乎不改原圖 |
| [真實 50× 1 µm 位移中途診斷](<results/exploratory_real_motion_x1um/REPORT_zh-TW.md>) | 第 50、70 輪對原圖的位移比較 |
| [停止紀錄](<reports/R88_ABORTED_AT_E87.md>) | 停止時間與理由 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R88_MeasurementFaithfulScratch.md>)。

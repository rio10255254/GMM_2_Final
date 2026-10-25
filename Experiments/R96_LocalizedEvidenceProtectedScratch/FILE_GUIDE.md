# R96：保護每個分支的目標，不被聯合訓練抵消

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R95](<../R95_CounterfactualGateRepairScratch/FILE_GUIDE.md>) · [正式設計前的舊方案](<../R96_Design_Archive/FILE_GUIDE.md>) · [下一輪 R97](<../R97_DirectCausalPhaseScratch/FILE_GUIDE.md>)

**一句話：** R95 的後期細節會退步。R96 保留局部、切塊完全一致的結構，改學習策略：需求與證據控制逐通道學與量；局部對比、邊界、紋理改用平滑的支撐感知監督；從第 27 輪起，五個分支的私有目標在聯合訓練中各自受保護，不能因為總損失還在下降就讓某個分支反向；每 8 批加入一個清楚的反事實樣本。2026-08-13 從零訓練 44 輪。結果很自然、沒有黑暈，但對 SEM 輪廓與實拍細節太保守。

| | |
|---|---|
| 結果 | **未採用**（44 輪；自然但太保守） |
| 時間 | 2026-08-13（13:14 啟動） |
| 實驗條件 | R93 固定合成資料（依鎖定雜湊讀取）；實拍與 SEM 只用於驗證 |
| 起點 | 隨機初始化，種子 960041 |

## 讀這些內容要知道的事

1. **這輪沒有文字結果報告。** 結論是從下一輪 R97 的[根因矩陣](<../R97_DirectCausalPhaseScratch/reports/root_cause_matrix.md>)讀出來的：需求分離最後只剩 0.00195，細節與紋理的實際修正遠小於分支原本的預測（需求與證據兩個圖又把已監督的修正乘了一次）；紋理梯度比主要目標小好幾個數量級；外部 GMF 第 26、29 張選到大約相鄰一個 72 px 週期的位置，但影像之間直接比較並沒有這個平移，也就是量測器鎖到了旁邊的重複結構。
2. **啟動前的檢查很完整**：6 個測試、17 項架構檢查、整張與切塊重建完全相同、64 個隱藏階段逐像素重播、838 個視圖的容量檢查都通過。
3. 第 32 輪做過實拍保留驗證，最後一輪做過 SEM 輪廓比較，都只保存了圖。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 設定（含第 32 輪實拍驗證與最終驗證協定）、模型、推論、分析與診斷程式 | 本資料夾 [config/](<config>)、[model/](<model>)、[inference/](<inference>)、[scripts/](<scripts>)，已在 GitHub |
| SEM 輪廓比較圖、第 32 輪實拍對照圖 | [results/final_validation/](<results/final_validation>)、[results/real_holdout_epoch_032/](<results/real_holdout_epoch_032>) |
| 1 µm 序列的反事實重建與外部 GMF 分數（原圖、R96、打開細節閘、打開全部閘、相位安全細節） | [results/x1um_counterfactual_reconstruction/](<results/x1um_counterfactual_reconstruction>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 權重與訓練紀錄不在 GitHub 程式樹上。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 改了什麼、獨立性與資料、啟動前檢查 |
| [R97 根因矩陣](<../R97_DirectCausalPhaseScratch/reports/root_cause_matrix.md>) | R96 暴露的問題與 R97 的對應修正 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R96_LocalizedEvidenceProtectedScratch.md>)。

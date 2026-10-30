# Diagnostics：估計器本身就偏離真值（選分支的診斷矩陣）

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [起因 Round 20](<../round20/FILE_GUIDE.md>) · [選出的分支 Branch E](<../branch_e/FILE_GUIDE.md>)

**一句話：** 2026-03-14 晚間，Round 20 之後、Round 21 之前的診斷。不產生新模型、不做外部重建，只回答一件事：下一步該修估計器（Branch E）還是修標籤（Branch L）？做法是用訓練資料產生器（`Training_Data/Data_Simulaion.py`）的確定性重播重建真實中心，直接檢查兩種幾何估計器在乾淨、卷積模糊、Round 18 超解析三種影像上偏多少。結論：估計器在乾淨與卷積影像上就已經明顯偏離真值，所以選 Branch E。

| | |
|---|---|
| 結果 | **分析**（選定 Branch E：先修估計器） |
| 時間 | 2026-03-14 |
| 實驗條件 | 程式資料：產生器重播的真實中心；三個尺度（0.08、0.8、8 px）各 150～318 張影格；評估權重是 Round 18 的選定保存點 |
| 起點 | 不訓練 |

## 0.8 px 的關鍵數字

| 影像 | 估計器 | 絕對中心誤差（px） | 相鄰位移誤差（px） |
|---|---|---:|---:|
| 乾淨 | 邊緣重心 | 83.57 | 1.142 |
| 乾淨 | 代數擬合 | 138.79 | 0.798 |
| 卷積模糊 | 邊緣重心 | 122.64 | 3.002 |
| 卷積模糊 | 代數擬合 | 138.77 | 0.798 |
| Round 18 超解析 | 邊緣重心 | 85.85 | 1.170 |
| Round 18 超解析 | 代數擬合 | 138.77 | 0.797 |

## 讀這些數字要知道的事

1. **偏差在超解析之前就出現了**：乾淨與卷積影像上的估計就已失真，所以問題不是先從標籤或超解析才開始。報告的判讀是，前面 Round 19、20 以邊緣重心、代數擬合、中心權重為核心的訓練優化，等於是在對一個已失真的上游幾何代理量做優化。
2. **這裡的絕對中心誤差是以產生器座標為準**（數值到幾十 px），跟其他輪次的中心誤差讀法不同，不能放在一起比。
3. 早期的煙霧測試與一版錯誤判讀保留在 `archive/`，根層只留最新的正式版本。

## 拿資料與重做

可重做程度：**historical-only**，只供閱讀與稽核。原始矩陣 JSON 與摘要 JSON 的位置：查 `python Tools/cloud_locator.py where Experiments/Legacy/organized_20260314/diagnostics/<檔名>`。

## 原始報告

[診斷矩陣摘要](<DIAGNOSTIC_MATRIX_SUMMARY_20260314_232403.md>)、[Round 21 分支決策](<ROUND21_BRANCH_DECISION.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本面保存紀錄](<../../../../docs/reproducibility/experiments/legacy__diagnostics.md>)。

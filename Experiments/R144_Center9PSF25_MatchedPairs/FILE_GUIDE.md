# R144：改用新拍攝的中心九顆擬合出來的 25 顆 PSF（中途中止）

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R143](<../R143_PSF25_MatchedPairs/FILE_GUIDE.md>) · [用修正後 PSF 重做的 R145](<../R145_Center9PSF25_CorrectedPairs/FILE_GUIDE.md>)

**一句話：** 2026-09-24 依使用者提供的 `PSF_20260924_center9_25_normalized.mat`（用九顆 SEM 直徑校準系統模糊、5×5 排列、20× 下每像素 0.1725 µm），同時替換訓練配對的模糊來源與模型內的 25 顆 PSF，其餘條件跟 R143 完全相同。但訓練開始後，原 PSF 校準流程發現 SEM 圓柱方向要修正，把這份檔案移到 `diagnostics_prior_orientation/` 並重新擬合。R144 用的是搬走之前的舊檔，所以在第 160 次更新停下（最後完整保存點是第 128 次），沒有做 930 張驗證。

| | |
|---|---|
| 結果 | **中止**（使用的 PSF 來源已被修正方向後的版本取代，第 160 次停止） |
| 時間 | 2026-09-24 |
| 實驗條件 | 訓練用程式資料：與 R143 相同的 768 個母場景、分組、位移、雜訊與 PSF 指派索引，只換 25 顆 PSF |
| 起點 | 隨機初始化（不載入 R143） |

## 讀這些內容要知道的事

1. **這是唯一指定變更的設計**：R143 與 R144 同模型、同資料指派，只換 PSF 銀行，原本適合用來比較新舊 PSF 的影響。這個比較最後由 R145 用修正後的 PSF 完成。
2. **用 SEM 校準 PSF 是合理的光學校準**，網路的訓練答案仍是合成場景的清楚影像，SEM 直徑沒有當作訓練標籤；但之後拿同九顆、同一張 SEM 表檢查尺寸，只能叫「校準所用參照的同樣本對照」，不是獨立的尺寸準確度驗證。
3. 這個包只保留作來源沿革。精確的來源、步數與中止原因在 `runs/formal_8192/ABORTED_SOURCE_SUPERSEDED.json`。

## 原始報告

[README](<README.md>)、[固定驗證計畫](<reports/R144_VALIDATION_PLAN.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R144_Center9PSF25_MatchedPairs.md>)。

# R100 設計檢查：訓練前先回答四個問題

[研究時間線](<../../docs/research/TIMELINE.md>) · [正式的 R100](<../R100_CausalOperatorScratch/FILE_GUIDE.md>) · [前一輪 R99](<../R99_GeometryTextureCoherentScratch/FILE_GUIDE.md>)

**一句話：** 定 R100 架構之前，2026-08-14 先做一個只分析、不能啟動訓練的前置檢查：來源與答案幾何已經對齊時，幾何監督會不會剛好變成零？對稱、有原圖支撐的細節運算能不能改善細結構又不移動輪廓、不破壞位移？這些結論在合成真值、5×／20×／50× 實拍、精確切塊、實拍 1 µm 序列上都成立嗎？Chan–Vese ACM 在保幾何的光度變化下夠不夠穩，能不能當唯一的挑選訊號？

| | |
|---|---|
| 結果 | **分析**（訓練前檢查；沒有定義 R100 模型） |
| 時間 | 2026-08-14 |
| 實驗條件 | 合成真值、5×／20×／50× 實拍、實拍 1 µm 序列（大型資料唯讀引用） |

## 讀這些內容要知道的事

1. **這一輪沒有文字結論報告**；執行入口是 `scripts\Run_Validation.ps1`，產出寫在 `results` 與 `reports`。
2. R101 的設計檢查引用了一份「R100 前置稽核」：336 個觀測中只有 2.08% 要求原圖支撐的增強，71.13% 反而要求去噪，答案／來源的最適細節倍率中位數只有 0.484。

## 拿資料與重做

本資料夾的程式與設定已在 GitHub，執行方式見 [README](<README.md>)。查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R100_DesignValidation.md>)。

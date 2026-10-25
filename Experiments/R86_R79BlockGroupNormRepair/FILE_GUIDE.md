# R86：不訓練，只把全圖的正規化換成固定區塊

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一種修法 R85](<../R85_R79SharedCanvasOpticalRepair/FILE_GUIDE.md>) · [三輪總結案在 R84](<../R84_R79TileStableRootRepair/FILE_GUIDE.md>) · [下一輪 R87](<../R87_TileNativeScratchGeneralization/FILE_GUIDE.md>)

**一句話：** 既然 R79 的切塊差異來自它會依整張影像調整特徵分布，R86 直接保留 R79 的權重與光學輸入，只把全圖範圍的 GroupNorm 換成固定、相位對齊的 8×8 特徵區塊，先做不訓練的零樣本檢查。2026-08-10 的結果是切塊一致性通過，但重建誤差變成 R79 的 1.41 倍、邊界誤差 1.96 倍，所以依規則不啟動訓練。

| | |
|---|---|
| 結果 | **未採用**（零樣本檢查就不合格，沒有訓練） |
| 時間 | 2026-08-10 |
| 實驗條件 | 程式生成的檢查資料與切塊一致性檢查 |
| 起點 | R79 的精確權重 |

## 讀這些內容要知道的事

1. **規則是先過零樣本門檻才准訓練**，所以這一輪只有探測，沒有新權重。
2. 三輪的總結與後來的決定寫在 [R84 的結案報告](<../R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md>)。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 零樣本探測、推論程式、改過的模型、設定 | 本資料夾 [scripts/probe_zero_shot.py](<scripts/probe_zero_shot.py>)、[inference/](<inference>)、[model/](<model>)、[config/](<config>)，已在 GitHub |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 設計與最終狀態 |
| [三輪總結案](<../R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md>) | R84、R85、R86 的比較與最後的修改 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R86_R79BlockGroupNormRepair.md>)。

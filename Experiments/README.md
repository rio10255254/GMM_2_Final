# 實驗

主專案每做一輪實驗，就在這裡開一個資料夾（R26 到 R153）。一輪的問題、程式、設定、結果，連失敗的也一樣，都留在自己的資料夾裡。

實驗室那台顯微鏡的研究線另外放在 [LabSystem_MOSR](../LabSystem_MOSR/README.md)。編號可能跟這裡重複（Lab 的 R39 跟主專案的 R39 是兩回事），所以不混在一起。

## 從哪裡開始

| 我想… | 打開 |
|---|---|
| 看每一輪現在是完成、停止還是沒採用 | [實驗索引](INDEX.md) |
| 用編號查某一輪（R1 到 R153，含同號的支線） | [逐號對照表](../docs/reproducibility/lineage/ROUND_NUMBER_MAP.md) |
| 先搞懂每一輪做了什麼、結果怎樣 | [逐輪閱讀](../docs/reproducibility/EXPERIMENTS.md) |
| 看論文目前用的結果 | [R153 論文交接](R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md) |
| 找 R34、R35、R37 這幾輪 | [只在舊分支的輪次](../docs/reproducibility/lineage/HISTORICAL_BRANCHES.md) |

## 一輪資料夾怎麼讀

R33 以後大多照這個順序：先讀 `README.md` 知道這輪在問什麼，再看 `reports/` 的結論，要重做才去看 `config/`、`scripts/`，數字和圖在 `results/`。從零訓練的輪次另外有 `model/`、`training/`、`inference/`、`data/`、`runs/`、`weights/`，整輪自己就是一套完整的程式。R26 等較早的輪次照當時的寫法保留，沒有為了整齊硬改。

**結論以各輪 `reports/` 裡的正式報告為準。** 閱讀卡、圖冊這些都是導讀。有些輪次只留了幾張代表圖，完整影像放在 Releases 附件，取回方式寫在那一輪的說明裡。

## 兩個不算輪次的共用區

| 資料夾 | 是什麼 |
|---|---|
| [Legacy](Legacy/README.md) | 最早期的訓練、選模和失敗紀錄（2026-03 的 `organized_*` 批次） |
| [Training_Runs](Training_Runs/README.md) | 用 `Model/` 的訓練程式每訓練一次，留下的一個紀錄資料夾 |

這兩個原本是最上層的 `Traing_Progress` 資料夾（少一個 i 是當年的拼字），2026-10-28 拆成兩個放到這裡。

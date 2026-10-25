# R93：拆開「去雜訊」和「恢復可辨識的細節」，留下第二套共用資料

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R92](<../R92_PhysicalTransitionBalancedScratch/FILE_GUIDE.md>) · [下一輪 R94](<../R94_EvidenceConditionalScratch/FILE_GUIDE.md>) · [R89～R93 的設計演進](<../../docs/reproducibility/scratch_lineage/README.md>) · [R93 共用資料取回與重算](<../../docs/reproducibility/r93_shared/README.md>)

**一句話：** R93 想把「去掉感測雜訊」和「恢復成像中仍可辨識的細節」分開，同時保護本來已清楚的輸入、輪廓、位移與切塊一致性。每個程式生成場景都保存清楚目標 T、無雜訊但已成像退化的 B、含雜訊的 S，讓後面幾輪能在同一個場景上建立不同的校正目標。2026-08-12 從零訓練，預計 64 輪、在第 60 輪後由使用者停下，事後依原規則選第 48 輪。**這份固定資料後來被 R94～R98 共用。**

| | |
|---|---|
| 結果 | **研究候選**（停在第 60 輪，綜合候選第 48 輪；資料被 R94～R98 共用） |
| 時間 | 2026-08-12 |
| 實驗條件 | 純合成：1,250 個場景、每個四種觀測共 5,000 個；訓練 1,000、驗證 125、內部測試 125 個場景 |
| 起點 | 隨機初始化，種子 930041 |

## 這份資料的組成

| 用途 | 場景數 |
|---|---:|
| 可恢復細節 | 250 |
| 持續細節組 | 200 |
| 清楚輸入保護 | 175 |
| 困難輪廓 | 188 |
| 曝光組 | 150 |
| 正負次像素位移 | 112 |
| 跨切塊密集圖 | 100 |
| 嚴重但可恢復的退化 | 75 |

15,004 個檔案、約 29.7 GB，內容身分 `6494719a…`。這是合成資料，不是 9/3 的相機原拍。

## 結果：怎麼選出第 48 輪

原分析比較已觀察的第 32～60 輪（每兩輪一個，共 15 個候選），五個面向各自依最小、最大值換算差距，先找「最差面向也較平衡」的，再用平均差距處理同分：

| 目的 | 選到的輪次 |
|---|---:|
| 綜合平衡 | **48** |
| 細節 | 44 |
| 清楚輸入改動、平均位移 | 52 |
| 輪廓、曝光 | 60 |

第 60 輪的輪廓與曝光持續改善，但細節和位移尾端比早期最佳點退步，清楚輸入仍會被改動。

## 讀這些內容要知道的事

1. **舊說明的標題和種子是錯的。** 早期 README 沿用了前一輪的「Round 92」標題、種子 920041 和 80 輪的句子；實際是種子 930041、預計 64 輪、停在 60 輪。2026-10-20 的審查改正首頁，原文另有保存。
2. **R92 和 R93 是兩套不同的共用資料。** R94～R98 用這一份，R99、R100、R102～R104 用 R92；不能互換。
3. **共用資料不代表同一個實驗。** 後面各輪的模型與損失都不同。
4. **選擇可以不下載大檔就重算**：用 `Tools/replay_r93_stopped_results.py` 和 36 KB 的 `r93-result-replay.zip`。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 只想重算當時的選擇（不需要影像、模型、Torch） | Release [`r93-complete-record-20261020`](https://github.com/rio10255254/GMM_2_Final/releases/tag/r93-complete-record-20261020) 的 `r93-result-replay.zip`，用法見 [R93 共用資料取回](<../../docs/reproducibility/r93_shared/README.md>) |
| 34 個模型檔、250 張比較與測試影像、完整數字 | 同一個 Release 的完整附件 |
| 五輪共用的完整訓練資料（約 12.6 GB 下載） | Release [`research-shared-sources-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016)，只下載 R93 前綴即可 |
| 原圖快速查看（標明實拍與合成） | [R93 圖庫](<../../docs/reproducibility/r93_shared/GALLERY.md>) |
| 設定、模型、訓練程式 | 本資料夾 [config/](<config/README.md>) 等，已在 GitHub |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。原電腦上的大陣列 2026-10-22 已清理，恢復方式見 [資料封存入口](<data/ARCHIVE_POINTER_20261022.md>)。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R93 審查](<reports/R93_AUDIT.md>) | 實際做了什麼、真正的資料身分、停在哪裡與怎麼選、保存與選圖、重做入口 |
| [資料生產來源](<reports/R93_GENERATION_SOURCE_GUIDE_20261021.md>) | 種子、局部修正（11 場景、44 觀測）、哪些輪次引用 |
| [reports/](<reports/README.md>) | 失敗的正式前檢查與煙霧測試，全部保留 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R93_RecoverableDetailSeparatedScratch.md>)。

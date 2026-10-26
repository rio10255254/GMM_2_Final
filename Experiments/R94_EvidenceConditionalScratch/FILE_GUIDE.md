# R94：按成像順序分工，另外學「要不要修」

[研究時間線](<../../docs/research/TIMELINE.md>) · [資料來源 R93](<../R93_RecoverableDetailSeparatedScratch/FILE_GUIDE.md>) · [下一輪 R95](<../R95_CounterfactualGateRepairScratch/FILE_GUIDE.md>) · [R94～R98 四輪的取回入口](<../../docs/reproducibility/four_rounds/README.md>)

**一句話：** R93 的細節、輪廓、保持原圖、位移幾個目標互相牽制。R94 把感測雜訊、亮度、局部對比衰減、對稱邊界、材質紋理分成五個分支，再用兩套獨立控制判斷「是否需要修正」和「原圖是否還有足夠證據」。2026-08-12 從零訓練，計畫 48 輪，但第 9 輪在存檔前被記憶體保護停下，只留下第 1～8 輪。R95 的前置診斷由這次失敗找出控制與訓練動力的問題。

| | |
|---|---|
| 結果 | **中止**（第 9 輪存檔前被記憶體保護停下） |
| 時間 | 2026-08-12（18:15 預檢，19:19 前後正式啟動） |
| 實驗條件 | R93 固定合成資料（1,250 場景、5,000 觀測）；四張實拍只當預覽 |
| 起點 | 隨機初始化，種子 940041；2,303,717 個參數 |

## 讀這些內容要知道的事

1. **停止原因是估算，不是實測。** 保護程式估算剩餘 −0.48 GiB 就停了，不能寫成顯示卡實際只剩這麼多。
2. **R95 前置診斷找到的問題：** 需求目標有微小的常數底值、控制被過度關閉、早期平均權重的設定、快取重複計算。
3. **程式版本很多。** 這一輪共有 19 版模型定義、訓練程式與設定，2026-10-22 全部依原核對碼找回，放在 [archive/recovered_sources_20261022/](<archive/recovered_sources_20261022/README.md>)；同名檔案不能互換，要按原紀錄配套使用。
4. **R97 曾在事後分析打開過 R93 的歷史內部測試集**，所以那部分不能再稱為未見或仍封存。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 全部模型、影像、數字與失敗紀錄 | Release [`r94-complete-record-20261021`](https://github.com/rio10255254/GMM_2_Final/releases/tag/r94-complete-record-20261021)（151 個原位置、20 個模型檔、51 張影像） |
| 四輪共用的取回與驗證方式 | [R94～R98 取回入口](<../../docs/reproducibility/four_rounds/README.md>)、[重要原圖與不利案例](<../../docs/reproducibility/four_rounds/GALLERY.md#r94>) |
| 共用訓練資料 | 見 [R93](<../R93_RecoverableDetailSeparatedScratch/FILE_GUIDE.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。不要直接在保存的歷史目錄開新訓練，重做請用另外的工作目錄。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R94 審查](<reports/R94_AUDIT.md>) | 方法、實際完成範圍、固定來源、完整保存、最後提交的驗證數字 |
| [找回的早期程式](<archive/recovered_sources_20261022/README.md>) | 19 版原件與對應的執行階段 |
| [README](<README.md>) | 摘要與入口 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R94_EvidenceConditionalScratch.md>)。

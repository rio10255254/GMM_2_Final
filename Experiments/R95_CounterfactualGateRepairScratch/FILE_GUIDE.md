# R95：修 R94 的控制與學習動力

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R94](<../R94_EvidenceConditionalScratch/FILE_GUIDE.md>) · [下一輪 R96](<../R96_LocalizedEvidenceProtectedScratch/FILE_GUIDE.md>) · [R94～R98 四輪的取回入口](<../../docs/reproducibility/four_rounds/README.md>)

**一句話：** 保留 R94 的成像分工與局部切塊設計，改成清楚輸入的「需求答案」確實為零，並對同一場景的清楚、無雜訊、含雜訊三種輸入直接監督控制；初始控制更中性、逐步交接、早期改用自適應平均權重。2026-08-13 從零訓練，48 輪完成，但中途因保護停下又接續兩次；第 40 輪的診斷顯示清楚案例仍被誤改、邊界控制被壓低、紋理分支極弱。

| | |
|---|---|
| 結果 | **未採用**（48 輪完成，但清楚案例誤改、邊界控制被壓低、紋理分支極弱） |
| 時間 | 2026-08-13（00:22 預檢，00:31 正式啟動） |
| 實驗條件 | R93 固定合成資料；四張實拍只當預覽 |
| 起點 | 隨機初始化，種子 950041；2,303,717 個參數 |

## 讀這些內容要知道的事

1. **訓練不是一次連續跑完的。** 第一次在未提交的第 10 輪被保護停下，回到第 8 輪的模型，但當時的訓練程式沒有保存優化器狀態（`optimizer_state_restored=false`），所以模型和平均權重接續、更新狀態重新建立；之後從第 11、32 輪再接續才有完整狀態。原表 49 列，重跑的第 9 輪取代舊列，兩筆都保留。不能稱為三次完全連續，也不是四次獨立訓練。
2. **早期訓練程式版本**有兩版從本機 git 物件找回、三版在 2026-10-22 補齊，內容都符合當年核對碼；同名檔案不能互換。
3. 48 輪完成不等於問題解決，第 40 輪診斷列出的三個機制問題仍在。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 全部模型、影像、數字與失敗紀錄 | Release [`r95-complete-record-20261021`](https://github.com/rio10255254/GMM_2_Final/releases/tag/r95-complete-record-20261021)（308 個原位置、31 個模型檔、148 張影像） |
| 四輪共用的取回與驗證方式 | [R94～R98 取回入口](<../../docs/reproducibility/four_rounds/README.md>)、[重要原圖與不利案例](<../../docs/reproducibility/four_rounds/GALLERY.md#r95>) |
| 找回的早期程式 | [archive/recovered_sources_20261022/](<archive/recovered_sources_20261022/README.md>)、[archive/recovered_training_sources_20261021/](<archive/recovered_training_sources_20261021/README.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R95 審查](<reports/R95_AUDIT.md>) | 方法、實際完成範圍與接續歷程、固定來源、完整保存、最後驗證數字 |
| [README](<README.md>) | 摘要與入口 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R95_CounterfactualGateRepairScratch.md>)。

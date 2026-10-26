# R97：拿掉幅度閘，直接學每個分支實際施加的修正

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R96](<../R96_LocalizedEvidenceProtectedScratch/FILE_GUIDE.md>) · [下一輪 R98](<../R98_AggressiveTextureScratch/FILE_GUIDE.md>) · [R94～R98 四輪的取回入口](<../../docs/reproducibility/four_rounds/README.md>)

**一句話：** R96 的需求圖與證據圖把已監督的修正又乘了一次，修正被壓得太小。R97 拿掉這兩個幅度閘，讓每個分支直接預測對 S、B、T 三種輸入實際要施加的修正；依每個場景的答案能量調整稀疏分支的學習尺度；紋理只能由原圖對稱頻帶組合；另外在記憶體產生條紋、點、圓環、矩形格，教模型分辨正確位置與錯一個週期的位置。2026-08-13 從零完成 48 輪，固定第 48 輪平均權重。實拍可見的邊緣與細節增加了，但紋理分支在實拍上幾乎不動，各分支修正互相抵銷。

| | |
|---|---|
| 結果 | **未採用**（48 輪完成） |
| 時間 | 2026-08-13（20:06 啟動） |
| 實驗條件 | R93 固定合成資料；301 張實拍只用於驗證 |
| 起點 | 隨機初始化，種子 970043；2,433,774 個參數 |

## 讀這些內容要知道的事

1. **正式訓練前當機過一次。** 512 px 的加速候選用 8 個場景一批，顯示卡用到 48,488 MiB、只剩 84 MiB，Windows 出現顯示驅動逾時（`VIDEO_TDR_FAILURE`）重新開機。當時還沒有正式訓練，只損失一個可丟棄的煙霧測試。之後永久禁止這個批量，加速候選低於 6 GiB 或超過 120 秒就終止。
2. **正式第 1 輪後遇到檔案存取被拒**，從同一輪模型恢復一次；原表 1～48 沒有重複。這跟上面的當機是兩件事。
3. **實拍細節增加不等於量測更準。** 301 張實拍沒有乾淨真值；週期測試沒有錯一格，也不代表真實位移絕對準確。
4. **驗證範圍：** 最後的 final_validation 是 768／384 視野、每個角色 2 個場景的固定小面板，不是全部 125 個驗證場景；R98 用不同的裁切種子，不能只拿兩輪最後的數字當公平比較。
5. **R97 在事後分析打開過 R93 的歷史內部測試集。**

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 全部模型、影像、數字與失敗紀錄 | Release [`r97-complete-record-20261021`](https://github.com/rio10255254/GMM_2_Final/releases/tag/r97-complete-record-20261021)（512 個原位置、28 個模型檔、396 張影像） |
| 四輪共用的取回與驗證方式 | [R94～R98 取回入口](<../../docs/reproducibility/four_rounds/README.md>)、[重要原圖與不利案例](<../../docs/reproducibility/four_rounds/GALLERY.md#r97>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R97 審查](<reports/R97_AUDIT.md>) | 方法、實際完成範圍、固定來源、完整保存、驗證取樣與端點的界限 |
| [根因矩陣](<reports/root_cause_matrix.md>) | 每個改動對應 R96 的哪個證據 |
| [GPU 當機紀錄](<reports/gpu_incident_20260813.md>)、[同次訓練中斷恢復驗證](<reports/recovery_validation_20260813.md>) | 正式前的當機與恢復機制的驗證 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R97_DirectCausalPhaseScratch.md>)。

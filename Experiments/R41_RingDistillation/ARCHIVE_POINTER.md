# R41 完整歷史位置與恢復方式

封存日期：2026-08-01

## 為什麼封存

R41 已完成訓練與所有本地檢查。它證明顯微特徵能力可以保留，但沒有任何候選同時通過顯微能力與環形守門，因此沒有升級，也沒有送外部 GMF。正式結論不再需要依賴數千張候選重建圖長期占用 D 槽。

封存只改變大型歷史檔案的位置，不改變 R41 的研究結論。

## H 槽完整內容

根目錄：`H:\GMM_2_Final_Archive\experiments\R41_RingDistillation\20260801_full_history`

| 子目錄 | 原始位置 | 內容 |
|---|---|---|
| `experiment` | `Experiments/R41_RingDistillation` | 封存前的整個實驗資料夾，包含全部結果與候選輸出 |
| `training_run` | `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r41_kd_from_a045_20260505_103028` | 30 輪正式訓練與權重 |
| `training_data` | `Training_Data/r41_ring_distillation` | R41 專用訓練與驗證資料 |

三部分合計 6,075 個檔案、7.375 GiB。三份 SHA-256 清單已逐檔驗證通過，零缺漏、零不一致。

## D 槽留下什麼

- 實驗 README、MANIFEST 與本說明。
- `reports/` 的正式結論。
- `scripts/` 與 `tests/`，可重做資料、訓練與評估。
- `results/` 中已納入版本紀錄的數字摘要、掃描摘要與小型證據。
- `selected_checkpoint/best_tradeoff.pth.tar`，供快速研究檢查的代表模型；其內容指紋已和 H 槽清單核對一致。

D 槽只移除已在 H 槽完整保存的大型候選重建、掃描 checkpoint、正式訓練目錄與 R41 專用資料包。

執行結果：29 個預覽目標已於 2026-08-01 移除，D 槽先回收 6.74 GiB；補回 50.20 MiB 代表模型後淨回收約 6.69 GiB。沒有刪除任何已納入版本紀錄的檔案。

## 如何恢復

若要完整恢復 R41，先把以下三個資料夾複製回各自原始位置：

```powershell
robocopy H:\GMM_2_Final_Archive\experiments\R41_RingDistillation\20260801_full_history\experiment Experiments/R41_RingDistillation /E /COPY:DAT /DCOPY:DAT
robocopy H:\GMM_2_Final_Archive\experiments\R41_RingDistillation\20260801_full_history\training_run Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r41_kd_from_a045_20260505_103028 /E /COPY:DAT /DCOPY:DAT
robocopy H:\GMM_2_Final_Archive\experiments\R41_RingDistillation\20260801_full_history\training_data Training_Data/r41_ring_distillation /E /COPY:DAT /DCOPY:DAT
```

恢復後使用 `Tools/project_storage_guard.py verify-manifest` 搭配中央索引列出的三份清單再次核對。核對通過後，內容才算完整恢復。

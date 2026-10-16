# R63 / R88–R93 封存狀態

更新時間：2026-09-25

七個實驗資料夾已完整複製到 H 槽；封存副本逐檔通過 SHA-256、檔案數和資料夾結構核對，共 125,158 個檔案、214,562,988,182 bytes（199.827 GiB）。原始資料夾仍完整保留在 D 槽。

| 實驗 | 檔案數 | 封存容量 | H 槽完整副本 |
|---|---:|---:|---|
| R89 Measurement Native Scratch | 23,740 | 41,691,508,070 bytes | H:\GMM_2_Final_Archive\experiments\R89_MeasurementNativeScratch\20260925_full_history |
| R93 Recoverable Detail Separated Scratch | 20,028 | 37,281,057,297 bytes | H:\GMM_2_Final_Archive\experiments\R93_RecoverableDetailSeparatedScratch\20260925_full_history |
| R63 Causal Boundary Motion Ablation | 25,298 | 34,376,429,430 bytes | H:\GMM_2_Final_Archive\experiments\R63_CausalBoundaryMotionAblation\20260925_full_history |
| R90 Exposure Coherent Scratch | 15,138 | 28,080,889,897 bytes | H:\GMM_2_Final_Archive\experiments\R90_ExposureCoherentScratch\20260925_full_history |
| R88 Measurement Faithful Scratch | 14,213 | 24,973,265,874 bytes | H:\GMM_2_Final_Archive\experiments\R88_MeasurementFaithfulScratch\20260925_full_history |
| R91 Detail Decoupled Scratch | 13,573 | 24,813,983,956 bytes | H:\GMM_2_Final_Archive\experiments\R91_DetailDecoupledScratch\20260925_full_history |
| R92 Physical Transition Balanced Scratch | 13,168 | 23,345,853,658 bytes | H:\GMM_2_Final_Archive\experiments\R92_PhysicalTransitionBalancedScratch\20260925_full_history |

## D 槽清理狀態

D 槽尚未清理。自動命令審查拒絕了遞迴刪除，回覆為「blocked by policy」；沒有刪除任何原件。封存驗證前建立的清理計畫列出 116,677 個檔案、206,313,176,858 bytes（192.144 GiB），但這些容量目前仍在 D 槽。清理計畫建立時 D 槽可用 96.803 GiB；後續可用空間降至 0 bytes。本次清理實際回收 0 bytes。NTFS 壓縮試做回報錯誤；R89 試驗檔內容和大小未變，與 H 槽副本相符。

R93 的資料仍位於原始 D 槽路徑。R97 和 R98 會讀取該位置的共享資料；若日後完成清理，必須在原路徑保留通往 H 槽 R93 封存資料的資料夾連結。

清理前需參照 H 槽操作記錄中的 cleanup_plan_20260925.json。清理項目刻意保留實驗說明、報告、程式、測試、代表權重及 R63 的摘要、圖表、測量結果和品質檢查資料。

清理遭拒紀錄：H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\cleanup_blocked_20260925.json
壓縮試做紀錄：H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\space_recovery_trial_20260925.json

## 驗證記錄

完整的來源 SHA-256 清單：H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\source_files.csv

H 槽副本 SHA-256 清單：H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\archive_files.csv

全部核對結果：H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\verification_summary.json

複製記錄：H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\robocopy.log


## 後續只讀盤點

後續只讀盤點（2026-09-25）：六個已封存目標目錄目前不在 D 槽，按封存前清單合計原始大小 126.856 GiB；D 槽當時可用 106.791 GiB。仍在 D 槽、且清單允許直接清理的其他目錄共 9 個，合計原始大小約 31.897 GiB。R93 共用資料仍留在原路徑。完整項目見 H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\followup_inventory_20260925.json.
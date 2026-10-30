# 專案歷史封存索引

Last updated: 2026-09-26

## 用途

這是 D 槽工作專案通往 H 槽完整歷史的中央索引。封存只改變大型檔案的存放位置，不改變實驗結論、正式基準或候選身分。

正式封存根目錄：`H:\GMM_2_Final_Archive`

截至 2026-08-24，已完成 13 個大型執行批次，涵蓋 23 個獨立快照或封存單位；H 槽保存約 208.940 GiB 完整歷史，D 槽累計淨回收約 161.555 GiB。所有批次都保留正式結論、代表成果與恢復入口，且不改變任何模型身分。

## 2026-09-26 R87 已結案實驗完整封存（D 原件保留）

2026-09-26 已建立 R87 完整 H 副本：5,588 檔、11.7650 GiB，來源與副本逐檔 SHA-256 一致，複製期間來源未變。D 槽原件（包括合成資料、完整正式 run、權重、失敗與驗證證據）全部保留；本批實際回收 0 bytes。中央登錄仍標示保護，後續須另核對下游資料相依及可重建配方才精簡。

完整副本：H:\GMM_2_Final_Archive\experiments\R87_TileNativeScratchGeneralization\20260926_full_history。[R87 原位置恢復入口](../../Experiments/R87_TileNativeScratchGeneralization/ARCHIVE_POINTER_R87_20260926.md)

## 2026-09-26 20x／5x 分析區完整封存（D 精簡待執行）

52 個歷史重建目錄、10,500 個檔案、30.772 GiB 的獨立 H 相容副本已逐檔 SHA-256 核對通過。它與 91.517 GiB 的完整 H 歷史副本分開，D 槽原路徑及原件尚未切換或移除，本批 D 回收 0 bytes。後續僅對這 52 個精確目錄進行路徑相容切換，仍須重核活動程序並採正式核准；不操作原始照片及正式量測。


已完成 32,262 檔、約 91.517 GiB 的完整 H 副本，來源與副本逐檔 SHA-256 一致，複製期間來源未變；D 原件仍在，這批尚未回收 D 空間。引用核對顯示 442 個大型候選資料夾中 440 個名稱見於其他專案文字檔，另兩個沒有精確名稱引用但仍待證實。

完整副本：H:\GMM_2_Final_Archive\analyses\20260704_20x_5x_analysis\20260926_full_history。D 原始照片、正式量測及引用結果仍在原位置；下一步需先驗證保持舊路徑可讀的方案。[引用核對與恢復入口](ANALYSIS_20260704_STORAGE_AUDIT_20260926.md)

## 2026-09-26 R53/R56 正式核准清理收尾

19 個指定歷史目錄已移除。兩份完整 H 封存共 79,160 檔與 D 保留內容在移除後重核通過；D 當下可用空間增加 25.6136 GiB。下方未清理說明為先前狀態，最新以各輪收尾記錄為準。[實際執行](PROJECT_STORAGE_MIGRATION_EXECUTION_20260926.md)

## 2026-09-26 Lab R56 完整封存（D 槽精簡已完成）

七個來源、39,499 檔、18,020,375,797 bytes（16.7828 GiB）完整保存到 H:/GMM_2_Final_Archive/lab_system/R56_LabelCoreRepairTraining/20260926_full_history，逐檔內容核對通過。D 保留 23 檔資料清單與代表影像，原正式訓練成果 38 檔再次核對通過，報告與角點驗證仍在 D。封存資料讀取 6,000 組配對的檢查通過。四個精確待清理目錄約 15.8983 GiB 尚未移除，實際回收 0 bytes。[完整收尾與精確清單](R56_STORAGE_CLOSEOUT_20260926.md)

## 2026-09-26 Lab R53 完整封存（D 槽精簡已完成）

19 個精確來源、39,661 個檔案、20,085,159,214 bytes（18.7058 GiB）已完整保存到 H:/GMM_2_Final_Archive/lab_system/R53_RealisticDatasetCalibration/20260926_full_history。來源與副本逐檔 SHA-256 全部通過，來源在複製期間未變；原啟動程式使用封存資料能讀到 6,000 組配對。D 槽另保留 121 個已核對的設定、日誌、資料清單及代表影像（128.203 MiB），正式 batch16 run、報告及角點驗證仍在原位置。

15 個精確 D 清理目錄約 17.1641 GiB 的移除命令遭執行工具自動審查拒絕，本次回收 0 bytes，來源仍存在。此批已按使用者「無關目前程序的來源可操作」授權做相依檢查；目前工作沒有 R53 來源交集。完整記錄與手動精確清單見 [R53 封存狀態](R53_STORAGE_CLOSEOUT_20260926.md)。沒有更改 R53 未採用的研究判決。

## 2026-09-25 R63 / R88–R93 完整封存副本（D 槽清理待處理）

| 批次 | H 槽完整內容 | SHA-256 核對 | D 槽目前狀態 | 封存入口 |
|---|---:|---|---|---|
| R63、R88、R89、R90、R91、R92、R93 | 125,158 檔、214,562,988,182 bytes（199.827 GiB） | 七個來源與副本逐檔通過；零缺檔、零雜湊差異 | 原件未刪；遞迴清理遭自動命令審查拒絕；D 槽未回收空間 | Experiments/ARCHIVE_STATUS_20260925.md |

七個封存單位已增加 H 槽完整歷史約 199.827 GiB；連同 2026-08-24 前保存的約 208.940 GiB，H 槽完整歷史約 408.767 GiB。D 槽本次尚未回收空間；清理計畫建立時可用 96.803 GiB，後續複核時可用 0 bytes，實際回收 0 bytes。NTFS 壓縮試做失敗，檔案未變。預定清理 116,677 檔、206,313,176,858 bytes（192.144 GiB），不代表已完成。

逐實驗保存位置、原始檔案數及容量見 Experiments/ARCHIVE_STATUS_20260925.md。來源清單、副本清單、逐檔結果和清理計畫保存在 H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925。R93 的共享資料仍留在 D 槽原位置，維持 R97／R98 現有讀取路徑；目前尚未建立資料夾連結。

後續只讀盤點（2026-09-25）：六個已封存目標目錄目前不在 D 槽，按封存前清單合計原始大小 126.856 GiB；D 槽當時可用 106.791 GiB。仍在 D 槽、且清單允許直接清理的其他目錄共 9 個，合計原始大小約 31.897 GiB。R93 共用資料仍留在原路徑。完整項目見 H:\GMM_2_Final_Archive\operation_logs\Experiments_R63_R88_R93_20260925\followup_inventory_20260925.json.

## 2026-08-24 R1–R51 全面整理

| 執行批次 | H 槽完整內容 | D 槽精簡 | 實測回收 | 核對 |
|---|---:|---:|---:|---|
| R16–R31：`organized_20260313`–`16` | 10,220 檔、34.1530 GiB | 39 個精確目錄、9,376 檔 | 32.7585 GiB | 四份完整清單刪除前後 PASS |
| 主專案已結案輪次：R32、R33Contrast、R38Seq、R42、R44、R45、R46 | 31,925 檔、20.3528 GiB | 27 個精確目錄、30,889 檔 | 20.1237 GiB | 七份完整清單刪除前後 PASS |
| Lab R46／R47 | 13,697 檔、約 9.0876 GiB | 19 個精確目錄、13,599 檔 | 5.5963 GiB | 21 份來源清單刪除前後 PASS，最終實驗脈絡再次 PASS |
| 主專案共享訓練歷史 | 3,751 檔、52.718 GiB | 61 個已結案／失敗／探針／消融 run | 22.4152 GiB | 完整清單刪除前後 PASS |

本次新增 H 槽完整歷史 124,888,598,605 bytes（116.3116 GiB）；四次精簡當下實測回收 86,858,862,592 bytes（80.8936 GiB）。補回代表模型、Lab 核心證據與 R26 相容包後，D 槽可用容量淨增加 85,523,742,720 bytes（79.6502 GiB）。R30 前任基準、COMBO、R33、R38v2、R39/R40 核准核心、Lab R39/R40/R51、原始量測與名稱未能可靠對應的舊主線歷史均未移除。

主要恢復入口：

- R16–R31：各 `Experiments/Legacy/organized_20260313`–`16` 根目錄的 `ARCHIVE_POINTER_20260824.md`
- 主專案七輪：各實驗根目錄的 `ARCHIVE_POINTER_20260824.md`
- Lab R46／R47：各 Lab 實驗根目錄的 `ARCHIVE_POINTER_20260824.md`
- 共享訓練歷史：`Experiments/Legacy/ARCHIVE_POINTER_STANDALONE_20260824.md`
- 完整決策與停止邊界：`docs/operations/PROJECT_R1_R51_STORAGE_REVIEW_20260824.md`

## 2026-08-24 新完成封存

| 批次 | 原始角色 | 封存內容 | 檔案數 | 容量 | 核對 | H 槽位置 | D 槽目前狀態 |
|---|---|---|---:|---:|---|---|---|
| Lab R52 / 2026-08-13–24 | 完成 100 輪但真實角點守門失敗、不可升級的負結果 | 4000/700 對資料、正式與 smoke 訓練、兩組重建、兩組 GMF-ready 影像、角點驗證及完整實驗脈絡 | 23,858 | 11.870 GiB | 八份 SHA-256 清單在 D 精簡前後全部 PASS；最終 61 檔實驗脈絡清單重建後再次 PASS | `H:\GMM_2_Final_Archive\lab_system\R52_CornerStabilityGuard\20260813_full_history` | 保留正式報告、程式、測試、兩份資料清單、訓練紀錄、三個代表模型、完整角點證據、恢復入口與執行紀錄；實際回收 9.4306 GiB |

## 已完成封存

| 批次 | 原始角色 | 封存內容 | 檔案數 | 容量 | 核對 | H 槽位置 | D 槽保留內容 |
|---|---|---|---:|---:|---|---|---|
| R41 / 2026-08-01 | 已結案、未升級、未送外部 GMF 的研究輪次 | 實驗資料夾完整快照、30 輪正式訓練、R41 專用訓練與驗證資料 | 6,075 | 7.375 GiB | 三份 SHA-256 清單全部 PASS，零缺漏、零不一致 | `H:\GMM_2_Final_Archive\experiments\R41_RingDistillation\20260801_full_history` | README、MANIFEST、正式報告、程式、測試、數字摘要、代表模型與恢復指引 |
| Lab R48 / 2026-08-01 | 完成 200 輪但真實角點驗證失敗、不可升級的負結果 | 6000 對訓練資料、1200 對驗證資料、四次訓練、三組重建、三組 GMF 準備影像、角點驗證與完整實驗脈絡 | 36,494 | 18.470 GiB | 13 份 SHA-256 清單在 D 精簡前後兩次全部 PASS | `H:\GMM_2_Final_Archive\lab_system\R48_RealCornerTransfer\20260801_full_history` | 正式報告、資料 manifest、程式、測試、訓練紀錄與曲線、角點證據、共享資料及恢復入口 |
| Lab R49 / 2026-08-10 | 完成 100 輪但真實角點驗證失敗、不可升級的負結果 | CAD-anchor 來源與訓練資料、正式與 smoke 訓練、三組重建與 GMF 影像、角點驗證及完整實驗脈絡 | 22,752 | 11.1838 GiB | 13 份 SHA-256 清單在 D 精簡前後兩次全部 PASS；最終說明同步後再次 PASS | `H:\GMM_2_Final_Archive\lab_system\R49_CADAnchorRealGeometry\20260809_full_history` | 正式報告、資料 manifest、程式、測試、訓練紀錄與曲線、角點證據、推論紀錄及恢復入口 |
| organized_20260311 / 2026-08-01 | Round12–14 舊長跑、checkpoint audit、corridor 與外部重建歷史 | 封存前整個 `organized_20260311` 時間點快照 | 6,912 | 31.624 GiB | SHA-256 清單 PASS，零缺漏、零不一致 | `H:\GMM_2_Final_Archive\legacy\organized_20260311\20260801_full_history\snapshot` | `selected/` 精選報告與代表 run、`pending/`、README、MANIFEST、恢復指引 |
| organized_20260307 / 2026-08-01 | 早期 seed 搜尋與 autotune 歷史，已被後續驗證鏈取代 | 封存前整個 `organized_20260307` 時間點快照 | 440 | 4.370 GiB | SHA-256 清單 PASS，零缺漏、零不一致 | `H:\GMM_2_Final_Archive\legacy\organized_20260307\20260801_full_history\snapshot` | `selected/` 代表模型與種子、少量 archive/pending、README、MANIFEST、恢復指引 |
| organized_20260312 / 2026-08-01 | Round 15 center-lock 長跑、checkpoint audit 與外部驗證歷史 | 封存前整個 `organized_20260312` 時間點快照 | 1,152 | 3.829 GiB | SHA-256 清單 PASS，零缺漏、零不一致 | `H:\GMM_2_Final_Archive\legacy\organized_20260312\20260801_full_history\snapshot` | `selected/` 報告與種子、少量 pending、1 份代表模型、README、MANIFEST、恢復指引 |
| organized_20260309 / 2026-08-01 | 早期外部 GMF 驗證、視覺比較與候選測試歷史 | 封存前整個 `organized_20260309` 時間點快照 | 295 | 1.716 GiB | SHA-256 清單 PASS，零缺漏、零不一致 | `H:\GMM_2_Final_Archive\legacy\organized_20260309\20260801_full_history\snapshot` | 外部 GMF 證據、視覺比較、精選摘要、少量 pending、README、MANIFEST、恢復指引 |
| organized_20260310 / 2026-08-01 | 多尺度外部驗證、SeqVal/crossscale 比較與 uint16 microstep 探測歷史 | 封存前整個 `organized_20260310` 時間點快照 | 928 | 2.190 GiB | SHA-256 清單 PASS，零缺漏、零不一致 | `H:\GMM_2_Final_Archive\legacy\organized_20260310\20260801_full_history\snapshot` | 根層報告、pending/debug 小型歷史、38 份核心驗證證據、README、MANIFEST、恢復指引 |

R41 完成核對後，D 槽移除 29 個已預覽的大型未追蹤目標，先回收 6.74 GiB；補回 50.20 MiB 代表模型後淨回收約 6.69 GiB。邏輯檔案大小與實際回收量的差異來自原檔共用底層空間；H 槽仍保存完整 7.375 GiB 歷史。

Lab R48 完成核對後，D 槽移除資料包影像與幾何副本、四次訓練的逐輪模型與監看影像，以及三組完整重建與三組重複 GMF 準備影像，共 105 個精確目標，實際回收 14.977 GiB。兩份資料 manifest、訓練曲線與紀錄、正式報告、角點驗證證據、程式、測試與恢復入口仍在 D 槽；共享第 53–56 組資料因 R52 仍會引用而完全保留。H 槽在 D 精簡後再次核對 36,494 個檔案全部 PASS。

Lab R49 完成核對後，D 槽移除 CAD-anchor 大型影像與幾何副本、正式與 smoke 訓練的大型模型及監看影像，以及三組完整重建與三組 GMF 影像，共 62 個精確目標、22,694 個檔案。表面大小為 11.1686 GiB；因部分資料共用底層內容，實際回收 8.7816 GiB。正式負結果、三份報告、資料 manifest、訓練紀錄與曲線、角點證據、程式、測試及恢復入口仍在 D 槽；H 槽在 D 精簡後再次核對全部 PASS。R53 若要重建，需先從 H 恢復 R49 的來源資料包。

Lab R52 完成核對後，D 槽只移除七個清單列明的大型來源，共 23,797 個檔案、表面大小 11.687 GiB；因訓練資料包含共用底層內容，實際回收 9.4306 GiB。正式負結果、資料清單、訓練紀錄與曲線、三個代表模型、完整角點驗證、程式、測試及恢復入口仍在 D 槽；H 槽在 D 精簡後再次核對八份清單全部 PASS，最終實驗脈絡同步後又重建並驗證為 61 個檔案。

organized_20260311 完成核對後，D 槽移除 `archive/` 與 `external_validation/`，實際回收約 30.31 GiB。D 槽仍保留 60 個精選檔案、2 份代表模型及完整閱讀與恢復入口；H 槽在 D 副本移除後再次逐檔核對 PASS。

organized_20260307 完成核對後，D 槽移除 `rejected/`，實際回收 4.320 GiB。D 槽仍保留 11 個精選檔案、1 份代表模型與完整說明；H 槽刪除後核對 PASS。

organized_20260312 完成核對後，D 槽移除 `archive/` 與 `external_validation/`，實際回收 3.831 GiB。D 槽仍保留 13 份歷史報告與種子、少量 pending 紀錄、1 份代表模型與完整說明；H 槽刪除後核對 PASS。

organized_20260309 完成核對後，D 槽只移除已明確歸入 `rejected/` 的候選包，實際回收 1.373 GiB。外部 GMF 原始證據、分析結果、視覺比較與精選摘要仍留在 D 槽；H 槽刪除後核對 PASS。

organized_20260310 完成核對後，D 槽移除大型 `external_validation/`，實際回收 2.191 GiB。D 槽另留 38 份原始 GMF 分數、分析結果、比較摘要與重建清單，連同根層報告與少量 pending/debug 歷史；H 槽刪除後核對 PASS。

## R41 清單

- 實驗完整快照：`H:\GMM_2_Final_Archive\manifests\R41_20260801_experiment.csv`
- 正式訓練：`H:\GMM_2_Final_Archive\manifests\R41_20260801_training_run.csv`
- 專用訓練資料：`H:\GMM_2_Final_Archive\manifests\R41_20260801_training_data.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\R41_20260801_*_robocopy.log`
- D 槽恢復說明：`Experiments/R41_RingDistillation/ARCHIVE_POINTER.md`

## Lab R48 清單

- 13 份完整快照清單：`H:\GMM_2_Final_Archive\manifests\Lab_R48_*_20260801.csv`
- H 槽批次紀錄：`H:\GMM_2_Final_Archive\lab_system\R48_RealCornerTransfer\20260801_full_history\ARCHIVE_RECORD.md`
- D 槽恢復說明：`LabSystem_MOSR/Experiments/R48_RealCornerTransfer/ARCHIVE_POINTER_R48_20260801.md`
- 精確封存範圍：`LabSystem_MOSR/Experiments/R48_RealCornerTransfer/ARCHIVE_SCOPE_R48_20260801.json`

## Lab R49 清單

- 13 份完整快照清單：`H:\GMM_2_Final_Archive\manifests\Lab_R49_*_20260809.csv`
- H 槽批次紀錄：`H:\GMM_2_Final_Archive\lab_system\R49_CADAnchorRealGeometry\20260809_full_history\ARCHIVE_RECORD.md`
- D 槽恢復說明：`LabSystem_MOSR/Experiments/R49_CADAnchorRealGeometry/ARCHIVE_POINTER_R49_20260809.md`
- 精確封存範圍：`LabSystem_MOSR/Experiments/R49_CADAnchorRealGeometry/ARCHIVE_SCOPE_R49_20260809.json`
- 精確移除清單與結果：`LabSystem_MOSR/Experiments/R49_CADAnchorRealGeometry/ARCHIVE_DELETE_PLAN_R49_20260809.json`

## Lab R52 清單（已完成）

- 八份完整快照清單：`H:\GMM_2_Final_Archive\manifests\Lab_R52_*_20260813.csv`
- H 槽批次紀錄：`H:\GMM_2_Final_Archive\lab_system\R52_CornerStabilityGuard\20260813_full_history\ARCHIVE_RECORD.md`
- D 槽恢復說明：`LabSystem_MOSR/Experiments/R52_CornerStabilityGuard/ARCHIVE_POINTER_R52_20260813.md`
- 精確封存範圍：`LabSystem_MOSR/Experiments/R52_CornerStabilityGuard/ARCHIVE_SCOPE_R52_20260813.json`
- 精確移除清單與結果：`LabSystem_MOSR/Experiments/R52_CornerStabilityGuard/ARCHIVE_DELETE_PLAN_R52_20260813.json`
- 最終執行紀錄：`LabSystem_MOSR/Experiments/R52_CornerStabilityGuard/ARCHIVE_EXECUTION_R52_20260824.json`
- D 槽精簡保留包：`LabSystem_MOSR/Experiments/R52_CornerStabilityGuard/results/archive_retained_20260813/`

## organized_20260311 清單

- 完整快照清單：`H:\GMM_2_Final_Archive\manifests\organized_20260311_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260311_20260801_robocopy.log`
- D 槽恢復說明：`Experiments/Legacy/organized_20260311/ARCHIVE_POINTER.md`

## organized_20260307 清單

- 完整快照清單：`H:\GMM_2_Final_Archive\manifests\organized_20260307_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260307_20260801_robocopy.log`
- D 槽恢復說明：`Experiments/Legacy/organized_20260307/ARCHIVE_POINTER.md`

## organized_20260312 清單

- 完整快照清單：`H:\GMM_2_Final_Archive\manifests\organized_20260312_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260312_20260801_robocopy.log`
- D 槽恢復說明：`Experiments/Legacy/organized_20260312/ARCHIVE_POINTER.md`

## organized_20260309 清單

- 完整快照清單：`H:\GMM_2_Final_Archive\manifests\organized_20260309_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260309_20260801_robocopy.log`
- D 槽恢復說明：`Experiments/Legacy/organized_20260309/ARCHIVE_POINTER.md`

## organized_20260310 清單

- 完整快照清單：`H:\GMM_2_Final_Archive\manifests\organized_20260310_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260310_20260801_robocopy.log`
- D 槽恢復說明：`Experiments/Legacy/organized_20260310/ARCHIVE_POINTER.md`

## 判讀原則

1. `PROJECT_STATE.md`、`Experiments/INDEX.md` 與各實驗 `reports/` 仍是日常判讀入口。
2. H 槽保存完整歷史，不因封存而把研究失敗改寫成成功，也不把研究候選改成正式模型。
3. 恢復任何內容時，先複製回 D 槽，再用對應清單核對。
4. H 槽不是活動中訓練位置，也不是唯一的正式成果備份。

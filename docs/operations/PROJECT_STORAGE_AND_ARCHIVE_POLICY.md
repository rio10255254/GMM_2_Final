# 專案容量與歷史封存規則

Last updated: 2026-08-13

## 目的

這份規則用來避免實驗資料無限制增生，同時確保正式模型、負結果、論文證據與原始輸入不會因清理容量而遺失。

容量巡檢入口：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py status
```

機器可讀設定：`docs/operations/PROJECT_STORAGE_POLICY.json`。

大型區塊中央登錄：`docs/operations/PROJECT_STORAGE_REGISTRY.json`。

第二階段執行與防失控計畫：`docs/operations/PROJECT_STORAGE_LIFECYCLE_PLAN.md`。

LabSystem 逐輪封存清單：`docs/operations/LABSYSTEM_ARCHIVE_QUEUE.md`。

正式封存位置：`H:\GMM_2_Final_Archive`。H 槽是獨立的 8 TB 內接硬碟；E 槽不作為本專案的正式歷史倉庫。

已完成批次與恢復入口：`docs/operations/PROJECT_ARCHIVE_INDEX.md`。

## 四個保存層級

### 1. 活動中

正在訓練、重建、擬合、渲染或人工審查的工作。

- 不移動、不改名、不刪除。
- 活動標記與實際程序必須同時檢查。
- 每次正式訓練、續訓、長時間重建或大量資料產生都必須在程序啟動前寫入目前程序的活動標記；同一實驗再次續行時，必須用新程序與新輸出位置更新標記，不能沿用上一段已完成狀態。
- 程序退出不等於完成；只有預定輪數、完成摘要與必要輸出均核對通過後，活動標記才能改為完成。失敗或輸出不完整時必須保留阻擋狀態。
- 守門工具會相容讀取近期自包含實驗留下的 `runs/active_run.json`，但它不是未來標準。缺少有效程序編號、狀態不明、失敗、中止或仍宣告 active 的標記一律顯示為待核對並阻擋大量操作，不能被解讀成已完成。
- 分支尚未收尾時，不進行版本歷史壓縮、活動輪次搬移或 D 槽大型來源移除。
- 緊急線以下若要替無關的已結案輪次預先建立 H 槽快照，必須取得使用者明確同意，先量測實際磁碟負載與佇列，只准單執行緒、限速、可續傳的複製與逐檔核對；活動輪次仍完全不碰，負載升高即停止，D 槽來源一律等活動工作完成並核對後才可移除。
- 即使活動標記讀取失敗，也必須先用實際程序確認；工具顯示 `BLOCKED` 時不得繞過。

### 2. 正式保留

專案正式真相與不可替代內容：

- 正式 baseline 與已核准替代模型。
- 正式報告、設定、清單、外部量測原始分數與代表圖。
- 原始實驗影像、SEM、Step、100MG、20x、5x 等採集資料。
- 正式 PSF 輸出與能重建正式結果的程式。
- 論文實際採用的圖表及其來源數據。

這一層不因容量不足直接刪除。

### 3. 歷史封存

已完成、已失敗或研究用途的完整訓練與評估過程。

工作區至少保留：

1. 正式結論報告。
2. 實驗清單與設定。
3. 採用或最有代表性的權重。
4. 代表圖與最終數字。
5. 原始輸入位置與重做方法。

完整 epoch、候選重建、逐張評估與大量中間檔可移到外部封存區，但必須先建立含 SHA-256 的檔案清單，並在封存位置驗證通過。

### 4. 可重建內容

測試快取、頁面渲染、重複聯絡表、臨時解壓縮、候選重建及已確認中斷的工具暫存。

只有在以下條件都成立時才能刪除：

- 沒有活動中的程序使用它。
- 正式結果不直接引用它，或正式替代品已確認存在。
- 需要重做時有程式、設定與原始輸入。
- 清理目標與預估容量已單獨列出。

身分仍有一點疑慮的暫存，不直接永久刪除；先移到 H 槽 `quarantine/` 隔離 30 天。D 槽移除前仍需建立清單並核對，隔離期限到期後才可考慮刪除 H 槽副本。

## 磁碟警戒線

| D 槽剩餘容量 | 狀態 | 動作 |
|---:|---|---|
| 300 GiB 以上 | 正常 | 依實驗節奏定期封存 |
| 150–300 GiB | 警告 | 暫停產生非必要候選，優先清理快取與封存已完成實驗 |
| 150 GiB 以下 | 緊急 | 不開始新的長訓練；先確保活動中工作能安全完成 |

## 新實驗的容量規則

1. 每個實驗必須把資料來源寫進 manifest，不靠完整複製來表達版本。
2. 同一資料集只改少量內容時，優先保存差異清單或由腳本重建；不要再複製整套資料。
3. 訓練過程可保留定期 checkpoint，但實驗完成後只在日常工作區保留正式採用、最後一版及必要診斷版本。
4. `results` 超過三個一級項目或 1 GiB 時必須有 README，標出正式成果、代表內容與封存候選；不強制所有實驗使用名為 `selected` 的資料夾。
5. 負結果保留報告與關鍵證據，不要求把所有可重建影像永遠放在快速工作磁碟。
6. 新實驗開始前要在容量中央登錄新增身分、預估容量、保留規則與封存時點。
7. 實驗完成後 7 天內 closeout：D 槽最多留採用、最後與一份必要診斷模型。
8. 暫存預設 14 天到期；大量重建完成報告後 7 天內進入封存候選。
9. 正式工作啟動器必須維護 `runs/launcher_logs/active_formal_run.json`，至少記錄實驗、狀態、程序、開始時間、預定輪數與輸出位置；續訓要覆寫為目前程序，結束後寫入可核對的完成狀態。

## 封存流程

建立含雜湊值的清單：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py manifest `
  --source Experiments\R40_MicroscopyFeatureCoverage `
  --output H:\GMM_2_Final_Archive\manifests\R40_manifest.csv `
  --hash
```

資料複製到封存磁碟後驗證：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py verify-manifest `
  --manifest H:\GMM_2_Final_Archive\manifests\R40_manifest.csv `
  --root H:\GMM_2_Final_Archive\experiments\R40_MicroscopyFeatureCoverage
```

只有驗證回報 `PASS`，而且清理目標已再次確認，才可移除原工作區的大型副本。

## 日常巡檢

每月或大型結構調整前，建立一份完整唯讀清冊。每次使用全新的日期資料夾，不覆寫舊清冊：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_file_inventory.py `
  --root D:\GMM_2_Final `
  --output H:\GMM_2_Final_Archive\inventory_snapshots\YYYYMMDD_full_project `
  --largest 2000 `
  --duplicate-min-mib 32
```

這份清冊包含隱藏、被忽略與 `.git` 內容，但不追蹤接合點，也不逐檔計算大型內容雜湊。它用來找容量、路徑與文件結構問題；不能取代正式封存所需的來源 SHA-256 清單。

快速狀態：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py status
```

列出已知清理候選但不刪除：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py cleanup-plan
```

檢查所有大型區塊的身分與活動阻擋：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py lifecycle-audit
```

計算某區下一層的容量：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py scan --root Experiments
```

這個工具本身不提供刪除指令，避免日常巡檢誤傷研究成果。

# organized_20260311 完整歷史位置與恢復方式

封存日期：2026-08-01

## 完整快照

- H 槽位置：`H:\GMM_2_Final_Archive\legacy\organized_20260311\20260801_full_history\snapshot`
- 內容清單：`H:\GMM_2_Final_Archive\manifests\organized_20260311_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260311_20260801_robocopy.log`
- 規模：6,912 個檔案、31.624 GiB
- 核對結果：PASS；零缺漏、零內容不一致

H 槽快照包含封存前的整個 `organized_20260311`，包括 D 槽仍保留的精選內容，以及移出的 `archive/` 和 `external_validation/`。

執行結果：D 槽的兩個大型資料夾已於 2026-08-01 完整移除，實際回收約 30.31 GiB。5 個超長檔名模型透過版本工具的長路徑模式完成處理；H 槽快照在刪除後再次逐檔核對 PASS。

## D 槽留下什麼

- `selected/`：當時精選的種子、代表 run 與 Round12–14 摘要。
- `pending/`：少量歷史執行紀錄。
- `README.md`、`MANIFEST.md` 與本恢復說明。

## D 槽移出什麼

- `archive/`：未選中的完整 run、audit runs、舊 root run 與狀態快照。
- `external_validation/`：universal、corridor 與 Round11 defect 三套完整外部重建。

## 完整恢復

```powershell
robocopy H:\GMM_2_Final_Archive\legacy\organized_20260311\20260801_full_history\snapshot Traing_Progress/organized_20260311 /E /COPY:DAT /DCOPY:DAT
```

恢復後核對：

```powershell
C:\Users\Rio\anaconda3\python.exe Tools\project_storage_guard.py verify-manifest `
  --manifest H:\GMM_2_Final_Archive\manifests\organized_20260311_20260801_full.csv `
  --root Traing_Progress/organized_20260311
```

核對回報 PASS 後，才算完整恢復。

# organized_20260307 完整歷史與恢復方式

封存日期：2026-08-01

- 完整快照：`H:\GMM_2_Final_Archive\legacy\organized_20260307\20260801_full_history\snapshot`
- 內容清單：`H:\GMM_2_Final_Archive\manifests\organized_20260307_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260307_20260801_robocopy.log`
- 規模：440 個檔案、4.370 GiB
- 核對：PASS，零缺漏、零不一致

D 槽留下 `selected/` 的 11 個精選檔案與 1 份代表模型；移出的 `rejected/` 包含已明確不採用的 autotune 與候選重建歷史。

執行結果：`rejected/` 已於 2026-08-01 移除，實際回收 4.320 GiB；刪除後 H 槽 440 個檔案再次核對 PASS。

完整恢復：

```powershell
robocopy H:\GMM_2_Final_Archive\legacy\organized_20260307\20260801_full_history\snapshot Traing_Progress/organized_20260307 /E /COPY:DAT /DCOPY:DAT
```

恢復後使用中央清單逐檔核對，回報 PASS 才算完整恢復。

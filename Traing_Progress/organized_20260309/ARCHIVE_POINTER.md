# organized_20260309 完整歷史與恢復方式

封存日期：2026-08-01

- 完整快照：`H:\GMM_2_Final_Archive\legacy\organized_20260309\20260801_full_history\snapshot`
- 內容清單：`H:\GMM_2_Final_Archive\manifests\organized_20260309_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260309_20260801_robocopy.log`
- 規模：295 個檔案、1.716 GiB
- 核對：PASS，零缺漏、零不一致

D 槽保留當時的外部 GMF 原始證據、分析結果、視覺比較與精選摘要；H 槽完整保留被明確歸入 `rejected/` 的候選重建與測試歷史。

執行結果：`rejected/` 已於 2026-08-01 移除，實際回收 1.373 GiB；刪除後 H 槽 295 個檔案再次核對 PASS。

完整恢復：

```powershell
robocopy H:\GMM_2_Final_Archive\legacy\organized_20260309\20260801_full_history\snapshot Traing_Progress/organized_20260309 /E /COPY:DAT /DCOPY:DAT
```

恢復後使用中央清單逐檔核對，回報 PASS 才算完整恢復。
